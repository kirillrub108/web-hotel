from dataclasses import asdict
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.booking_lifecycle import dates_taken
from app.booking_rules import calculate_price
from app.database import get_db
from app.models import Room, User
from app.promos import find_promo
from app.schemas import QuoteOut, RoomOut, StayIn
from app.sessions import get_current_user

router = APIRouter(prefix="/api/rooms", tags=["rooms"])


@router.get("", response_model=list[RoomOut])
def list_rooms(
    capacity: int | None = Query(default=None, ge=1, description="Минимальная вместимость"),
    max_price: int | None = Query(default=None, ge=0, description="Максимальная цена за ночь"),
    db: Session = Depends(get_db),
) -> list[Room]:
    query = select(Room).order_by(Room.price_per_night)
    if capacity is not None:
        query = query.where(Room.capacity >= capacity)
    if max_price is not None:
        query = query.where(Room.price_per_night <= max_price)
    return list(db.scalars(query))


def room_by_slug(db: Session, slug: str) -> Room:
    room = db.scalar(select(Room).where(Room.slug == slug))
    if room is None:
        raise HTTPException(status_code=404, detail="Номер не найден")
    return room


@router.get("/{slug}", response_model=RoomOut)
def get_room(slug: str, db: Session = Depends(get_db)) -> Room:
    return room_by_slug(db, slug)


@router.get("/{slug}/quote", response_model=QuoteOut)
def quote_room(
    slug: str,
    stay: Annotated[StayIn, Query()],
    user: User | None = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    """Котировка для формы брони: свободен ли номер и сколько будет стоить. Цену считает та же функция,
    что и при создании брони, поэтому сумма в форме совпадёт с суммой в брони. Неприменимый промокод — 400."""
    room = room_by_slug(db, slug)
    promo = (
        find_promo(db, stay.promo_code, user=user, room=room, check_in=stay.check_in, check_out=stay.check_out)
        if stay.promo_code
        else None
    )
    unavailable_reason = None
    if not room.is_available:
        unavailable_reason = "Этот номер сейчас недоступен для брони"
    elif stay.guests > room.capacity:
        unavailable_reason = f"Максимальное число гостей в номере — {room.capacity}"
    elif dates_taken(db, room.id, stay.check_in, stay.check_out):
        unavailable_reason = "Номер уже занят на выбранные даты"
    price = calculate_price(room.price_per_night, stay.check_in, stay.check_out, promo)
    return {
        "available": unavailable_reason is None,
        "unavailable_reason": unavailable_reason,
        "promo_title": promo.title if promo else None,
        **asdict(price),
    }
