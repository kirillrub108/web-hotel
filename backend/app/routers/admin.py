from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.models import Booking, BookingStatus
from app.schemas import AdminBookingPage, AdminLogin, BookingOut, BookingStatusUpdate
from app.security import (
    ADMIN_PASSWORD,
    ADMIN_USERNAME,
    COOKIE_SECURE,
    SESSION_COOKIE,
    SESSION_TTL_SECONDS,
    credentials_match,
    login_limiters,
    make_session_token,
    require_admin,
)

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.post(
    "/login",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(limiter) for limiter in login_limiters],
)
def login(payload: AdminLogin, response: Response) -> None:
    if not ADMIN_PASSWORD:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Вход отключён: задайте переменную окружения ADMIN_PASSWORD",
        )
    if not credentials_match(payload.username, payload.password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Неверный логин или пароль")

    response.set_cookie(
        SESSION_COOKIE,
        make_session_token(),
        max_age=SESSION_TTL_SECONDS,
        httponly=True,
        samesite="lax",
        secure=COOKIE_SECURE,
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(response: Response) -> None:
    response.delete_cookie(SESSION_COOKIE)


@router.get("/me", dependencies=[Depends(require_admin)])
def me() -> dict[str, str]:
    return {"username": ADMIN_USERNAME}


@router.get("/bookings", response_model=AdminBookingPage, dependencies=[Depends(require_admin)])
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


@router.patch("/bookings/{booking_id}", response_model=BookingOut, dependencies=[Depends(require_admin)])
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
