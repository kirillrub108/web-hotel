"""Заказы услуг и еды в номер: правила времени, итог по брони и единственная функция смены статуса заказа."""
import os
from datetime import date, datetime, time, timedelta

from fastapi import HTTPException, status
from sqlalchemy import Select, select
from sqlalchemy.orm import Session, joinedload

from app import hotel_time
from app.booking_rules import DisplayStatus, display_status
from app.models import (
    Actor,
    Booking,
    BookingStatus,
    Hotel,
    OrderStatus,
    Service,
    ServiceCategory,
    ServiceOrder,
    ServiceUnit,
)

# Часы, когда кухня принимает заказы еды, «ЧЧ:ММ-ЧЧ:ММ» по времени отеля. Конец не включается: на 23:00 уже не готовят.
ROOM_SERVICE_HOURS = os.getenv("ROOM_SERVICE_HOURS", "08:00-23:00")
ROOM_SERVICE_START, ROOM_SERVICE_END = (time.fromisoformat(part) for part in ROOM_SERVICE_HOURS.split("-"))

# Разрешённые переходы заказа и кто их выполняет. Перехода нет в таблице — ответ 409.
# Гость отменяет только новый заказ; отмена брони (SYSTEM) снимает и принятые, но ещё не выполненные.
ORDER_TRANSITIONS: dict[tuple[OrderStatus, OrderStatus], set[Actor]] = {
    (OrderStatus.NEW, OrderStatus.ACCEPTED): {Actor.ADMIN},
    (OrderStatus.ACCEPTED, OrderStatus.DONE): {Actor.ADMIN},
    (OrderStatus.NEW, OrderStatus.CANCELLED): {Actor.GUEST, Actor.ADMIN, Actor.SYSTEM},
    (OrderStatus.ACCEPTED, OrderStatus.CANCELLED): {Actor.ADMIN, Actor.SYSTEM},
}


def order_window(booking: Booking, hotel: Hotel) -> tuple[datetime, datetime]:
    """Когда можно заказывать: от заезда (дата + время заезда) до выезда (дата + время выезда)."""
    return (
        hotel_time.hotel_datetime(booking.check_in, hotel.check_in_time),
        hotel_time.hotel_datetime(booking.check_out, hotel.check_out_time),
    )


def can_order(booking: Booking) -> bool:
    """Заказывать можно к подтверждённой брони, пока проживание не завершено."""
    if booking.status != BookingStatus.CONFIRMED:
        return False
    shown = display_status(booking.status, booking.check_in, booking.check_out, hotel_time.hotel_today())
    return shown != DisplayStatus.COMPLETED


def check_order_time(service: Service, scheduled_at: datetime, booking: Booking, hotel: Hotel) -> None:
    start, end = order_window(booking, hotel)
    if not start <= scheduled_at <= end:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Время заказа должно быть в пределах проживания: с {start:%d.%m %H:%M} по {end:%d.%m %H:%M}",
        )
    if scheduled_at < hotel_time.hotel_now():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Нельзя заказать на прошедшее время")
    local_time = scheduled_at.astimezone(hotel_time.HOTEL_TZ).time()
    if service.category == ServiceCategory.FOOD and not ROOM_SERVICE_START <= local_time < ROOM_SERVICE_END:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Еду в номер заказывают с {ROOM_SERVICE_START:%H:%M} до {ROOM_SERVICE_END:%H:%M}",
        )


def create_order(
    db: Session,
    booking: Booking,
    hotel: Hotel,
    service: Service,
    quantity: int,
    scheduled_at: datetime,
    comment: str | None,
) -> ServiceOrder:
    """Проверяет бронь, услугу и время, затем сохраняет заказ с ценой на этот момент. Не коммитит."""
    if not can_order(booking):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Услуги можно заказать только к подтверждённой брони, пока проживание не закончилось",
        )
    if not service.is_active:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Эта услуга сейчас недоступна")
    check_order_time(service, scheduled_at, booking, hotel)
    # Услуга «за проживание» заказывается один раз за заказ: количество к ней не применяется.
    quantity = 1 if service.unit == ServiceUnit.PER_STAY else quantity
    order = ServiceOrder(
        booking=booking,
        service=service,
        quantity=quantity,
        unit_price=service.price,
        total=service.price * quantity,
        scheduled_at=scheduled_at,
        comment=comment,
    )
    db.add(order)
    db.flush()
    return order


def change_order_status(order: ServiceOrder, to_status: OrderStatus, actor: Actor) -> None:
    """Единственная функция смены статуса заказа: проверяет переход по таблице. Не коммитит."""
    if actor not in ORDER_TRANSITIONS.get((OrderStatus(order.status), to_status), set()):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Это действие недоступно в текущем статусе заказа"
        )
    order.status = to_status


def cancel_open_orders(db: Session, booking: Booking) -> None:
    """При отмене брони снимаются новые и принятые заказы; выполненные остаются в истории."""
    open_orders = db.scalars(
        select(ServiceOrder).where(
            ServiceOrder.booking_id == booking.id,
            ServiceOrder.status.in_([OrderStatus.NEW, OrderStatus.ACCEPTED]),
        )
    )
    for order in open_orders:
        change_order_status(order, OrderStatus.CANCELLED, Actor.SYSTEM)


def services_total(orders: list[ServiceOrder]) -> int:
    """Итог по услугам брони: отменённые заказы не считаются. Оплата — на ресепшене."""
    return sum(order.total for order in orders if order.status != OrderStatus.CANCELLED)


def day_bounds(day: date) -> tuple[datetime, datetime]:
    """Границы суток по времени отеля: заказ относится к дню, на который он назначен."""
    return hotel_time.hotel_datetime(day, "00:00"), hotel_time.hotel_datetime(day + timedelta(days=1), "00:00")


def orders_select(day: date | None = None, order_status: OrderStatus | None = None) -> Select[tuple[ServiceOrder]]:
    query = (
        select(ServiceOrder)
        .join(Service)
        .options(joinedload(ServiceOrder.service), joinedload(ServiceOrder.booking).joinedload(Booking.room))
    )
    if day is not None:
        start, end = day_bounds(day)
        query = query.where(ServiceOrder.scheduled_at >= start, ServiceOrder.scheduled_at < end)
    if order_status is not None:
        query = query.where(ServiceOrder.status == order_status)
    return query.order_by(ServiceOrder.scheduled_at, ServiceOrder.id)
