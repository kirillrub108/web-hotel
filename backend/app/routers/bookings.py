from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Booking, Room
from app.schemas import BookingCreate, BookingOut

router = APIRouter(prefix="/api/bookings", tags=["bookings"])


@router.post("", response_model=BookingOut, status_code=status.HTTP_201_CREATED)
def create_booking(payload: BookingCreate, db: Session = Depends(get_db)) -> Booking:
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

    booking = Booking(**payload.model_dump())
    db.add(booking)
    db.commit()
    db.refresh(booking)
    return booking
