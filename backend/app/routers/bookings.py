import os

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy import exists, func, select
from sqlalchemy.orm import Session

from app import hotel_time
from app.booking_lifecycle import change_status, dates_taken, expire_stale_pending, overlapping
from app.booking_rules import calculate_price, decide
from app.database import get_db
from app.mail import send_mail
from app.mail_templates import admin_review_mail, booking_review_mail
from app.models import Actor, Booking, BookingStatus, Room, User
from app.schemas import BookingCreate, GuestBookingOut
from app.security import booking_limiters
from app.sessions import require_verified_user

MAX_PENDING_PER_CLIENT = int(os.getenv("MAX_PENDING_PER_CLIENT", "3"))
# Куда писать о заявках на ручном разборе; пусто — не писать.
ADMIN_NOTIFY_EMAIL = os.getenv("ADMIN_NOTIFY_EMAIL", "")

router = APIRouter(prefix="/api/bookings", tags=["bookings"])


@router.post(
    "",
    response_model=GuestBookingOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(limiter) for limiter in booking_limiters],
)
def create_booking(
    payload: BookingCreate,
    background: BackgroundTasks,
    user: User = Depends(require_verified_user),
    db: Session = Depends(get_db),
) -> Booking:
    room = db.get(Room, payload.room_id)
    if room is None:
        raise HTTPException(status_code=404, detail="Номер не найден")
    if not room.is_available:
        raise HTTPException(status_code=400, detail="Этот номер сейчас недоступен для брони")
    if payload.guests > room.capacity:
        raise HTTPException(
            status_code=400,
            detail=f"Максимальное число гостей в номере — {room.capacity}",
        )
    if dates_taken(db, room.id, payload.check_in, payload.check_out):
        raise HTTPException(
            status_code=409,
            detail="Номер уже занят на выбранные даты. Выберите другие даты или другой номер",
        )

    # Просрочка в той же транзакции: иначе заявки с прошедшей датой заезда занимали бы место в лимите.
    expire_stale_pending(db, background)
    pending_count = db.scalar(
        select(func.count(Booking.id)).where(Booking.user_id == user.id, Booking.status == BookingStatus.PENDING)
    )
    if (pending_count or 0) >= MAX_PENDING_PER_CLIENT:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Заявок на рассмотрении не может быть больше {MAX_PENDING_PER_CLIENT}. "
            "Дождитесь решения по ним или отмените лишние",
        )

    # Факты для движка правил собираются здесь: сам decide() в базу не ходит.
    today = hotel_time.hotel_today()
    price = calculate_price(room.price_per_night, payload.check_in, payload.check_out)
    has_completed_stay = db.scalar(
        select(
            exists().where(
                Booking.user_id == user.id,
                Booking.status == BookingStatus.CONFIRMED,
                Booking.check_out <= today,
            )
        )
    )
    has_pending_conflict = db.scalar(
        select(overlapping(room.id, payload.check_in, payload.check_out, BookingStatus.PENDING).exists())
    )
    decision = decide(
        crm_status=user.crm_status,
        nights=price.nights,
        total=price.total,
        check_in=payload.check_in,
        today=today,
        has_comment=payload.comment is not None,
        has_completed_stay=bool(has_completed_stay),
        has_pending_conflict=bool(has_pending_conflict),
    )

    booking = Booking(
        user=user,
        room=room,
        guest_name=payload.guest_name,
        phone=payload.phone,
        check_in=payload.check_in,
        check_out=payload.check_out,
        guests=payload.guests,
        comment=payload.comment,
        nights=price.nights,
        price_per_night=price.price_per_night,
        discount=price.discount,
        total_price=price.total,
    )
    db.add(booking)
    # Заявка рождается в pending: событие создания пишется в журнал без письма.
    # Гость получает ровно одно письмо — об итоговом статусе после decide().
    on_review = decision.status == BookingStatus.PENDING
    change_status(
        db,
        booking,
        BookingStatus.PENDING,
        Actor.GUEST,
        background,
        actor_user_id=user.id,
        reason_codes=decision.reasons if on_review else [],
    )
    if on_review:
        # Перехода нет — заявка остаётся в pending, поэтому письмо «на рассмотрении» отправляется здесь.
        background.add_task(send_mail, booking_review_mail(booking))
        if ADMIN_NOTIFY_EMAIL:
            background.add_task(send_mail, admin_review_mail(ADMIN_NOTIFY_EMAIL, booking))
    else:
        # Письмо «подтверждена» или «отклонена» отправляет сам системный переход.
        change_status(db, booking, decision.status, Actor.SYSTEM, background, reason_codes=decision.reasons)
    db.commit()
    return booking
