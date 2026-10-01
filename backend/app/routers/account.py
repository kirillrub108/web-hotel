from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app import hotel_time
from app.booking_lifecycle import (
    change_status,
    expire_stale_pending,
    get_booking,
    guest_can_cancel,
    guest_cancel_deadline,
    load_hotel,
)
from app.database import get_db
from app.housekeeping import guest_can_change_slot
from app.models import (
    Actor,
    Booking,
    BookingStatus,
    HousekeepingTask,
    OrderStatus,
    Promo,
    Service,
    ServiceOrder,
    User,
)
from app.promos import available_promos
from app.room_service import (
    ROOM_SERVICE_END,
    ROOM_SERVICE_START,
    can_order,
    change_order_status,
    create_order,
    order_window,
    services_total,
)
from app.schemas import (
    GuestBookingDetail,
    GuestBookingOut,
    HousekeepingSlotIn,
    ProfileUpdate,
    PromoOffer,
    ServiceOrderIn,
    UserOut,
)
from app.sessions import require_user

router = APIRouter(prefix="/api/account", tags=["account"])


@router.get("/profile", response_model=UserOut)
def get_profile(user: User = Depends(require_user)) -> User:
    return user


@router.patch("/profile", response_model=UserOut)
def update_profile(payload: ProfileUpdate, user: User = Depends(require_user), db: Session = Depends(get_db)) -> User:
    user.full_name = payload.full_name
    user.phone = payload.phone
    db.commit()
    return user


@router.get("/promos", response_model=list[PromoOffer])
def list_my_promos(user: User = Depends(require_user), db: Session = Depends(get_db)) -> list[Promo]:
    """Предложения клиента: его персональные и общие акции, которые действуют сегодня и ещё не использованы."""
    query = available_promos(user, hotel_time.hotel_today()).options(joinedload(Promo.room))
    return list(db.scalars(query))


def booking_detail(db: Session, booking: Booking) -> dict[str, object]:
    hotel = load_hotel(db)
    deadline = guest_cancel_deadline(booking, hotel) if booking.status == BookingStatus.CONFIRMED else None
    orders = list(
        db.scalars(
            select(ServiceOrder)
            .where(ServiceOrder.booking_id == booking.id)
            .options(joinedload(ServiceOrder.service))
            .order_by(ServiceOrder.scheduled_at, ServiceOrder.id)
        )
    )
    tasks = db.scalars(
        select(HousekeepingTask)
        .where(HousekeepingTask.booking_id == booking.id)
        .order_by(HousekeepingTask.date, HousekeepingTask.id)
    )
    ordering = can_order(booking)
    start, end = order_window(booking, hotel)
    return {
        "booking": booking,
        "events": booking.events,
        "cancel_deadline": deadline,
        "can_cancel": guest_can_cancel(booking, hotel),
        "orders": orders,
        "services_total": services_total(orders),
        "can_order": ordering,
        "order_window": {"start": start, "end": end} if ordering else None,
        "room_service_hours": f"{ROOM_SERVICE_START:%H:%M}–{ROOM_SERVICE_END:%H:%M}",
        "housekeeping": list(tasks),
    }


@router.get("/bookings", response_model=list[GuestBookingOut])
def list_my_bookings(
    background: BackgroundTasks, user: User = Depends(require_user), db: Session = Depends(get_db)
) -> list[Booking]:
    expire_stale_pending(db, background)
    db.commit()
    query = (
        select(Booking)
        .options(joinedload(Booking.room), joinedload(Booking.promo))
        .where(Booking.user_id == user.id)
        .order_by(Booking.check_in.desc(), Booking.id.desc())
    )
    return list(db.scalars(query))


@router.get("/bookings/{booking_id}", response_model=GuestBookingDetail)
def get_my_booking(
    booking_id: int, background: BackgroundTasks, user: User = Depends(require_user), db: Session = Depends(get_db)
) -> dict[str, object]:
    expire_stale_pending(db, background)
    db.commit()
    return booking_detail(db, get_booking(db, booking_id, owner_id=user.id))


@router.post("/bookings/{booking_id}/cancel", response_model=GuestBookingDetail)
def cancel_my_booking(
    booking_id: int, background: BackgroundTasks, user: User = Depends(require_user), db: Session = Depends(get_db)
) -> dict[str, object]:
    # Просрочка, отмена и их письма — одна транзакция: при ошибке не сохранится ничего.
    expire_stale_pending(db, background)
    booking = get_booking(db, booking_id, owner_id=user.id, lock=True)
    change_status(db, booking, BookingStatus.CANCELLED, Actor.GUEST, background, actor_user_id=user.id)
    db.commit()
    return booking_detail(db, booking)


@router.post(
    "/bookings/{booking_id}/service-orders", response_model=GuestBookingDetail, status_code=status.HTTP_201_CREATED
)
def order_service(
    booking_id: int, payload: ServiceOrderIn, user: User = Depends(require_user), db: Session = Depends(get_db)
) -> dict[str, object]:
    # Блокировка брони: заказ и параллельная отмена брони идут по очереди.
    booking = get_booking(db, booking_id, owner_id=user.id, lock=True)
    service = db.get(Service, payload.service_id)
    if service is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Услуга не найдена")
    create_order(db, booking, load_hotel(db), service, payload.quantity, payload.scheduled_at, payload.comment)
    db.commit()
    return booking_detail(db, booking)


@router.post("/service-orders/{order_id}/cancel", response_model=GuestBookingDetail)
def cancel_service_order(
    order_id: int, user: User = Depends(require_user), db: Session = Depends(get_db)
) -> dict[str, object]:
    # Чужой заказ неотличим от несуществующего (404), как и чужая бронь.
    order = db.scalar(
        select(ServiceOrder)
        .join(Booking)
        .where(ServiceOrder.id == order_id, Booking.user_id == user.id)
        .with_for_update(of=ServiceOrder)
    )
    if order is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Заказ не найден")
    change_order_status(order, OrderStatus.CANCELLED, Actor.GUEST)
    db.commit()
    return booking_detail(db, order.booking)


@router.patch("/housekeeping/{task_id}", response_model=GuestBookingDetail)
def choose_housekeeping_slot(
    task_id: int, payload: HousekeepingSlotIn, user: User = Depends(require_user), db: Session = Depends(get_db)
) -> dict[str, object]:
    task = db.scalar(
        select(HousekeepingTask)
        .join(Booking)
        .where(HousekeepingTask.id == task_id, Booking.user_id == user.id)
        .with_for_update(of=HousekeepingTask)
    )
    if task is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Уборка не найдена")
    if not guest_can_change_slot(task.kind, task.status, task.date):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Слот этой уборки изменить нельзя: можно менять только запланированные уборки на следующие дни",
        )
    task.slot = payload.slot
    db.commit()
    return booking_detail(db, task.booking)
