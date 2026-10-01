from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.models import Booking, BookingStatus
from app.schemas import AdminBookingPage, BookingOut, BookingStatusUpdate
from app.sessions import require_admin

router = APIRouter(prefix="/api/admin", tags=["admin"], dependencies=[Depends(require_admin)])


@router.get("/bookings", response_model=AdminBookingPage)
def list_bookings(
    status_filter: BookingStatus | None = Query(default=None, alias="status"),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    query = select(Booking).options(joinedload(Booking.room))
    count_query = select(func.count(Booking.id))
    if status_filter is not None:
        query = query.where(Booking.status == status_filter)
        count_query = count_query.where(Booking.status == status_filter)

    items = db.scalars(query.order_by(Booking.created_at.desc(), Booking.id.desc()).limit(limit).offset(offset))
    return {"items": list(items), "total": db.scalar(count_query)}


@router.patch("/bookings/{booking_id}", response_model=BookingOut)
def update_booking_status(
    booking_id: int,
    payload: BookingStatusUpdate,
    db: Session = Depends(get_db),
) -> Booking:
    booking = db.get(Booking, booking_id)
    if booking is None:
        raise HTTPException(status_code=404, detail="Заявка не найдена")

    booking.status = payload.status
    try:
        db.commit()
    except IntegrityError:
        # Сработало ограничение bookings_no_overlap из миграции 0001.
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="На эти даты в номере уже есть подтверждённая заявка",
        ) from None
    db.refresh(booking)
    return booking
