"""Жизненный цикл брони: таблица переходов, функция перехода, ленивая просрочка, дедлайн отмены.

Статус брони меняет только change_status: она проверяет переход, пишет событие в журнал и ставит письмо гостю.
Здесь же подтверждение создаёт уборки на проживание, а отмена подтверждённой брони снимает уборки и заказы услуг.
"""
import os
from collections.abc import Callable
from datetime import date, datetime, timedelta

from fastapi import BackgroundTasks, HTTPException, status
from sqlalchemy import Select, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import hotel_time
from app.booking_rules import Reason
from app.housekeeping import create_stay_tasks, delete_planned_tasks
from app.mail import Mail, send_mail
from app.mail_templates import booking_cancelled_mail, booking_confirmed_mail, booking_declined_mail
from app.models import Actor, Booking, BookingEvent, BookingStatus, Hotel
from app.room_service import cancel_open_orders

FREE_CANCEL_HOURS = int(os.getenv("FREE_CANCEL_HOURS", "48"))

# Разрешённые переходы и кто их выполняет. Перехода нет в таблице — ответ 409.
TRANSITIONS: dict[tuple[str | None, str], set[Actor]] = {
    # Создание заявки: до него статуса нет.
    (None, BookingStatus.PENDING): {Actor.GUEST},
    (BookingStatus.PENDING, BookingStatus.CONFIRMED): {Actor.SYSTEM, Actor.ADMIN},
    (BookingStatus.PENDING, BookingStatus.DECLINED): {Actor.SYSTEM, Actor.ADMIN},
    (BookingStatus.PENDING, BookingStatus.CANCELLED): {Actor.GUEST, Actor.ADMIN},
    # Ещё и по времени: гость — до дедлайна бесплатной отмены, администратор — до даты выезда.
    (BookingStatus.CONFIRMED, BookingStatus.CANCELLED): {Actor.GUEST, Actor.ADMIN},
}

# Письмо гостю об итоге перехода. Письмо «на рассмотрении» отправляет код создания брони.
STATUS_MAILS: dict[str, Callable[[Booking], Mail]] = {
    BookingStatus.CONFIRMED: booking_confirmed_mail,
    BookingStatus.DECLINED: booking_declined_mail,
    BookingStatus.CANCELLED: booking_cancelled_mail,
}


def overlapping(room_id: int, check_in: date, check_out: date, booking_status: str) -> Select[tuple[Booking]]:
    """Брони номера в статусе booking_status, пересекающиеся с [check_in, check_out).

    Выезд и заезд в один день не пересекаются — так же считает daterange в bookings_no_overlap.
    """
    return select(Booking).where(
        Booking.room_id == room_id,
        Booking.status == booking_status,
        Booking.check_in < check_out,
        Booking.check_out > check_in,
    )


def dates_taken(db: Session, room_id: int, check_in: date, check_out: date) -> bool:
    """Заняты ли даты подтверждённой бронью. Заявки на рассмотрении даты не блокируют."""
    return bool(db.scalar(select(overlapping(room_id, check_in, check_out, BookingStatus.CONFIRMED).exists())))


def load_hotel(db: Session) -> Hotel:
    return db.scalars(select(Hotel).order_by(Hotel.id).limit(1)).one()


def guest_cancel_deadline(booking: Booking, hotel: Hotel) -> datetime:
    """До этого момента гость отменяет подтверждённую бронь сам: заезд по часам отеля минус FREE_CANCEL_HOURS."""
    return hotel_time.hotel_datetime(booking.check_in, hotel.check_in_time) - timedelta(hours=FREE_CANCEL_HOURS)


def guest_can_cancel(booking: Booking, hotel: Hotel) -> bool:
    if booking.status == BookingStatus.PENDING:
        return True
    return booking.status == BookingStatus.CONFIRMED and hotel_time.hotel_now() < guest_cancel_deadline(booking, hotel)


def get_booking(db: Session, booking_id: int, owner_id: int | None = None, *, lock: bool = False) -> Booking:
    """Бронь по id. С owner_id ищется только бронь этого гостя: чужая неотличима от несуществующей (404).

    lock=True — для действий: строка блокируется до конца транзакции, и два перехода одной брони идут по очереди.
    """
    query = select(Booking).where(Booking.id == booking_id)
    if owner_id is not None:
        query = query.where(Booking.user_id == owner_id)
    if lock:
        query = query.with_for_update()
    booking = db.scalar(query)
    if booking is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Бронь не найдена")
    return booking


def change_status(
    db: Session,
    booking: Booking,
    to_status: BookingStatus,
    actor: Actor,
    background: BackgroundTasks,
    *,
    actor_user_id: int | None = None,
    reason_codes: list[Reason] | None = None,
    reason_text: str | None = None,
) -> None:
    """Единственная функция перехода: проверка, поля брони, событие в журнале, письмо гостю.

    Не коммитит: вызывающий код фиксирует переход вместе с остальными изменениями запроса.
    Письма уходят фоновыми задачами только после успешного ответа, поэтому при ошибке они не отправятся.
    """
    from_status = booking.status
    if actor not in TRANSITIONS.get((from_status, to_status), set()):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Это действие недоступно в текущем статусе брони"
        )
    if from_status == BookingStatus.CONFIRMED and to_status == BookingStatus.CANCELLED:
        if actor == Actor.GUEST:
            hotel = load_hotel(db)
            if not guest_can_cancel(booking, hotel):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Отмена онлайн недоступна менее чем за {FREE_CANCEL_HOURS} ч до заезда — "
                    f"позвоните нам: {hotel.phone}",
                )
        elif hotel_time.hotel_today() >= booking.check_out:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT, detail="Проживание уже закончилось — отменить бронь нельзя"
            )

    codes = [str(code) for code in reason_codes or []]
    booking.status = to_status
    booking.reason_codes = codes
    booking.reason_text = reason_text
    if to_status in (BookingStatus.CONFIRMED, BookingStatus.DECLINED):
        booking.decided_by = actor
    if to_status == BookingStatus.CANCELLED:
        booking.cancelled_by = actor
        booking.cancelled_at = hotel_time.hotel_now()
    db.add(
        BookingEvent(
            booking=booking,
            from_status=from_status,
            to_status=to_status,
            actor=actor,
            actor_user_id=actor_user_id,
            reason_codes=codes,
            reason_text=reason_text,
        )
    )
    try:
        # Флаш сразу после перехода: у новой брони появляется id для письма,
        # а при подтверждении здесь же срабатывает bookings_no_overlap.
        db.flush()
    except IntegrityError:
        # Переход может нарушить только bookings_no_overlap: эти даты подтвердили в параллельном запросе.
        # Откатывается весь запрос, поэтому частично записанных данных не остаётся.
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Эти даты только что заняли — выберите другие"
        ) from None

    if to_status == BookingStatus.CONFIRMED:
        create_stay_tasks(db, booking)
        # Пересекающиеся заявки на рассмотрении больше не исполнимы — они отклоняются.
        # SKIP LOCKED пропускает заявки, которые прямо сейчас меняет параллельный запрос: взаимных блокировок нет.
        others = overlapping(booking.room_id, booking.check_in, booking.check_out, BookingStatus.PENDING)
        for other in db.scalars(others.with_for_update(skip_locked=True)).all():
            # Глубина рекурсии ровно 1: переход в declined ничего не каскадирует.
            change_status(
                db, other, BookingStatus.DECLINED, Actor.SYSTEM, background, reason_codes=[Reason.DATES_TAKEN]
            )

    if from_status == BookingStatus.CONFIRMED and to_status == BookingStatus.CANCELLED:
        delete_planned_tasks(db, booking)
        cancel_open_orders(db, booking)

    if to_status in STATUS_MAILS:
        background.add_task(send_mail, STATUS_MAILS[to_status](booking))


def expire_stale_pending(db: Session, background: BackgroundTasks) -> None:
    """Ленивая просрочка вместо планировщика: заявки на рассмотрении с прошедшей датой заезда отклоняются.

    Идемпотентна: повторный вызов уже ничего не найдёт. Коммитит вызывающий код: в действиях просрочка идёт
    в одной транзакции с действием, и если действие закончится ошибкой, откатятся и статусы, и письма.
    """
    stale = db.scalars(
        select(Booking)
        .where(Booking.status == BookingStatus.PENDING, Booking.check_in < hotel_time.hotel_today())
        .with_for_update(skip_locked=True)
    ).all()
    for booking in stale:
        change_status(db, booking, BookingStatus.DECLINED, Actor.SYSTEM, background, reason_codes=[Reason.EXPIRED])
