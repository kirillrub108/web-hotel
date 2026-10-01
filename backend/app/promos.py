"""Промокоды: поиск акции по коду, проверка применимости и занятость кода бронями.

Правила применимости и расчёт скидки — в booking_rules (promo_refusal, calculate_price): здесь только факты из базы.
"""

from datetime import date

from fastapi import HTTPException, status
from sqlalchemy import ColumnElement, Row, Select, exists, func, select
from sqlalchemy.orm import Session, joinedload

from app import hotel_time
from app.booking_rules import promo_refusal
from app.models import Booking, BookingStatus, Promo, Room, User

# Статусы, в которых бронь занимает свой промокод. Отказ и отмена код освобождают: отдельного счётчика нет.
HOLDING_STATUSES = (BookingStatus.PENDING, BookingStatus.CONFIRMED)


def normalize_code(code: str) -> str:
    return code.strip().upper()


def code_in_use(promo_id: int | ColumnElement[int]) -> ColumnElement[bool]:
    """Условие «код занят бронью в статусе pending или confirmed»; promo_id — число или колонка внешнего запроса."""
    return exists().where(Booking.promo_id == promo_id, Booking.status.in_(HOLDING_STATUSES))


def find_promo(
    db: Session, code: str, *, user: User | None, room: Room, check_in: date, check_out: date, lock: bool = False
) -> Promo:
    """Акция по промокоду или 400 с причиной по-русски.

    lock=True — для создания брони: строка акции блокируется до конца транзакции, и две параллельные брони
    с одним кодом идут по очереди: вторая увидит первую и получит отказ «уже использован».
    """
    query = select(Promo).where(Promo.code == normalize_code(code))
    promo = db.scalar(query.with_for_update() if lock else query)
    if promo is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Промокод не найден")
    refusal = promo_refusal(
        promo,
        user_id=user.id if user else None,
        room_id=room.id,
        nights=(check_out - check_in).days,
        today=hotel_time.hotel_today(),
        in_use=bool(db.scalar(select(code_in_use(promo.id)))),
    )
    if refusal:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=refusal)
    return promo


def available_promos(user: User, today: date) -> Select[tuple[Promo]]:
    """Предложения клиента: общие и его персональные акции — действующие по датам и ещё не занятые бронью."""
    return (
        select(Promo)
        .where(
            Promo.is_active,
            Promo.valid_from <= today,
            Promo.valid_to >= today,
            (Promo.user_id.is_(None)) | (Promo.user_id == user.id),
            ~code_in_use(Promo.id),
        )
        .order_by(Promo.user_id.is_(None), Promo.valid_to, Promo.id)
    )


def promo_select() -> Select[tuple[Promo, int, bool]]:
    """Акции для админки: сама акция, число броней на её коде за всё время и занят ли код сейчас."""
    bookings_count = (
        select(Booking.promo_id.label("promo_id"), func.count().label("n")).group_by(Booking.promo_id).subquery()
    )
    return (
        select(
            Promo, func.coalesce(bookings_count.c.n, 0).label("bookings_count"), code_in_use(Promo.id).label("in_use")
        )
        .outerjoin(bookings_count, bookings_count.c.promo_id == Promo.id)
        .options(joinedload(Promo.room), joinedload(Promo.user))
    )


def promo_dict(row: Row[tuple[Promo, int, bool]]) -> dict[str, object]:
    """Строка promo_select в виде словаря для схемы AdminPromoOut."""
    promo = row.Promo
    return {
        "id": promo.id,
        "code": promo.code,
        "title": promo.title,
        "description": promo.description,
        "kind": promo.kind,
        "value": promo.value,
        "valid_from": promo.valid_from,
        "valid_to": promo.valid_to,
        "min_nights": promo.min_nights,
        "room_id": promo.room_id,
        "room": promo.room,
        "user_id": promo.user_id,
        "user": promo.user,
        "is_active": promo.is_active,
        "created_at": promo.created_at,
        "bookings_count": row.bookings_count,
        "in_use": row.in_use,
    }
