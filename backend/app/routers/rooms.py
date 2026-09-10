from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Room
from app.schemas import RoomOut

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


@router.get("/{slug}", response_model=RoomOut)
def get_room(slug: str, db: Session = Depends(get_db)) -> Room:
    room = db.scalar(select(Room).where(Room.slug == slug))
    if room is None:
        raise HTTPException(status_code=404, detail="Номер не найден")
    return room
