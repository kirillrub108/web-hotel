from fastapi import APIRouter, BackgroundTasks, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app import hotel_time
from app.booking_lifecycle import (
    change_status,
    expire_stale_pending,
    get_booking,
    guest_can_cancel,
    guest_cancel_deadline,
    load_hotel,
)
from app.database import get_db
from app.models import Actor, Booking, BookingStatus, Promo, User
from app.promos import available_promos
from app.schemas import GuestBookingDetail, GuestBookingOut, ProfileUpdate, PromoOffer, UserOut
from app.sessions import require_user

router = APIRouter(prefix="/api/account", tags=["account"])


@router.get("/profile", response_model=UserOut)
def get_profile(user: User = Depends(require_user)) -> User:
    return user


@router.patch("/profile", response_model=UserOut)
def update_profile(payload: ProfileUpdate, user: User = Depends(require_user), db: Session = Depends(get_db)) -> User:
    user.full_name = payload.full_name
    user.phone = payload.phone
    db.commit()
    return user


@router.get("/promos", response_model=list[PromoOffer])
def list_my_promos(user: User = Depends(require_user), db: Session = Depends(get_db)) -> list[Promo]:
    """Предложения клиента: его персональные и общие акции, которые действуют сегодня и ещё не использованы."""
    query = available_promos(user, hotel_time.hotel_today()).options(joinedload(Promo.room))
    return list(db.scalars(query))


def booking_detail(db: Session, booking: Booking) -> dict[str, object]:
    hotel = load_hotel(db)
    deadline = guest_cancel_deadline(booking, hotel) if booking.status == BookingStatus.CONFIRMED else None
    return {
        "booking": booking,
        "events": booking.events,
        "cancel_deadline": deadline,
        "can_cancel": guest_can_cancel(booking, hotel),
    }


@router.get("/bookings", response_model=list[GuestBookingOut])
def list_my_bookings(
    background: BackgroundTasks, user: User = Depends(require_user), db: Session = Depends(get_db)
) -> list[Booking]:
    expire_stale_pending(db, background)
    db.commit()
    query = (
        select(Booking)
        .options(joinedload(Booking.room), joinedload(Booking.promo))
        .where(Booking.user_id == user.id)
        .order_by(Booking.check_in.desc(), Booking.id.desc())
    )
    return list(db.scalars(query))


@router.get("/bookings/{booking_id}", response_model=GuestBookingDetail)
def get_my_booking(
    booking_id: int, background: BackgroundTasks, user: User = Depends(require_user), db: Session = Depends(get_db)
) -> dict[str, object]:
    expire_stale_pending(db, background)
    db.commit()
    return booking_detail(db, get_booking(db, booking_id, owner_id=user.id))


@router.post("/bookings/{booking_id}/cancel", response_model=GuestBookingDetail)
def cancel_my_booking(
    booking_id: int, background: BackgroundTasks, user: User = Depends(require_user), db: Session = Depends(get_db)
) -> dict[str, object]:
    # Просрочка, отмена и их письма — одна транзакция: при ошибке не сохранится ничего.
    expire_stale_pending(db, background)
    booking = get_booking(db, booking_id, owner_id=user.id, lock=True)
    change_status(db, booking, BookingStatus.CANCELLED, Actor.GUEST, background, actor_user_id=user.id)
    db.commit()
    return booking_detail(db, booking)
