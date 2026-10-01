"""Номера в админке: список и правка цены, описания и доступности. Права — те же, что у остальных /api/admin/*."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Room
from app.schemas import RoomIn, RoomOut
from app.sessions import require_admin

router = APIRouter(prefix="/api/admin/rooms", tags=["admin-rooms"], dependencies=[Depends(require_admin)])


@router.get("", response_model=list[RoomOut])
def list_rooms(db: Session = Depends(get_db)) -> list[Room]:
    return list(db.scalars(select(Room).order_by(Room.price_per_night, Room.id)))


@router.patch("/{room_id}", response_model=RoomOut)
def update_room(room_id: int, payload: RoomIn, db: Session = Depends(get_db)) -> Room:
    room = db.get(Room, room_id)
    if room is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Номер не найден")
    # Существующие брони хранят цену снимком, а снятие с продажи проверяется только при создании новой брони.
    for field, value in payload.model_dump().items():
        setattr(room, field, value)
    db.commit()
    return room
