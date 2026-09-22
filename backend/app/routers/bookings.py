from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Booking, BookingStatus, Room
from app.schemas import BookingCreate, BookingOut
from app.security import booking_limiters

router = APIRouter(prefix="/api/bookings", tags=["bookings"])


@router.post(
    "",
    response_model=BookingOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(limiter) for limiter in booking_limiters],
)
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

    # Блокируют даты только подтверждённые заявки: иначе любой мог бы занять календарь фальшивыми.
    taken = db.scalar(
        select(Booking.id)
        .where(
            Booking.room_id == room.id,
            Booking.status == BookingStatus.CONFIRMED,
            Booking.check_in < payload.check_out,
            Booking.check_out > payload.check_in,
        )
        .limit(1)
    )
    if taken is not None:
        raise HTTPException(
            status_code=409,
            detail="Номер уже занят на выбранные даты. Выберите другие даты или другой номер",
        )

    booking = Booking(**payload.model_dump())
    db.add(booking)
    db.commit()
    db.refresh(booking)
    return booking
