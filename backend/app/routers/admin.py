from fastapi import APIRouter, BackgroundTasks, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from app.booking_lifecycle import change_status, expire_stale_pending, get_booking
from app.database import get_db
from app.models import Actor, Booking, BookingStatus, User
from app.schemas import AdminBookingDetail, AdminBookingOut, AdminBookingPage, AdminConfirmIn, AdminReasonIn
from app.sessions import require_admin

router = APIRouter(prefix="/api/admin", tags=["admin"], dependencies=[Depends(require_admin)])


@router.get("/bookings", response_model=AdminBookingPage)
def list_bookings(
    background: BackgroundTasks,
    status_filter: BookingStatus | None = Query(default=None, alias="status"),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    expire_stale_pending(db, background)
    db.commit()

    query = select(Booking).options(joinedload(Booking.room), joinedload(Booking.user), joinedload(Booking.promo))
    count_query = select(func.count(Booking.id))
    if status_filter is not None:
        query = query.where(Booking.status == status_filter)
        count_query = count_query.where(Booking.status == status_filter)

    # На разборе сначала ближайшие заезды — их решать срочнее. В остальных вкладках новые сверху.
    if status_filter == BookingStatus.PENDING:
        query = query.order_by(Booking.check_in, Booking.id)
    else:
        query = query.order_by(Booking.created_at.desc(), Booking.id.desc())

    items = db.scalars(query.limit(limit).offset(offset))
    return {"items": list(items), "total": db.scalar(count_query)}


@router.get("/bookings/{booking_id}", response_model=AdminBookingDetail)
def get_booking_detail(
    booking_id: int, background: BackgroundTasks, db: Session = Depends(get_db)
) -> dict[str, object]:
    expire_stale_pending(db, background)
    db.commit()
    booking = get_booking(db, booking_id)
    return {"booking": booking, "events": booking.events}


def admin_transition(
    db: Session,
    background: BackgroundTasks,
    booking_id: int,
    to_status: BookingStatus,
    admin: User,
    reason: str | None,
) -> Booking:
    # Просрочка и действие — одна транзакция: если действие не пройдёт, не сохранится ничего.
    expire_stale_pending(db, background)
    booking = get_booking(db, booking_id, lock=True)
    change_status(db, booking, to_status, Actor.ADMIN, background, actor_user_id=admin.id, reason_text=reason)
    db.commit()
    return booking


@router.post("/bookings/{booking_id}/confirm", response_model=AdminBookingOut)
def confirm_booking(
    booking_id: int,
    payload: AdminConfirmIn,
    background: BackgroundTasks,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> Booking:
    return admin_transition(db, background, booking_id, BookingStatus.CONFIRMED, admin, payload.reason)


@router.post("/bookings/{booking_id}/decline", response_model=AdminBookingOut)
def decline_booking(
    booking_id: int,
    payload: AdminReasonIn,
    background: BackgroundTasks,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> Booking:
    return admin_transition(db, background, booking_id, BookingStatus.DECLINED, admin, payload.reason)


@router.post("/bookings/{booking_id}/cancel", response_model=AdminBookingOut)
def cancel_booking(
    booking_id: int,
    payload: AdminReasonIn,
    background: BackgroundTasks,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> Booking:
    return admin_transition(db, background, booking_id, BookingStatus.CANCELLED, admin, payload.reason)
