"""Расписание уборок: задачи создаются из подтверждённой брони, гость выбирает слот, администратор ведёт день."""
from datetime import date, timedelta

from sqlalchemy import delete, select
from sqlalchemy.orm import Session, joinedload

from app import hotel_time
from app.models import (
    Booking,
    BookingStatus,
    HousekeepingKind,
    HousekeepingSlot,
    HousekeepingStatus,
    HousekeepingTask,
    OrderStatus,
    Service,
    ServiceCategory,
    ServiceOrder,
)
from app.room_service import orders_select

# Слоты ежедневной уборки в порядке показа; «не беспокоить» выводится отдельным списком.
DAILY_SLOTS = (HousekeepingSlot.MORNING, HousekeepingSlot.DAY, HousekeepingSlot.EVENING)


def create_stay_tasks(db: Session, booking: Booking) -> None:
    """Уборки на проживание: ежедневная — на каждую дату строго между заездом и выездом, после выезда — одна.

    Заезд и выезд ежедневной уборкой не покрываются, поэтому проживание на одну ночь даёт только уборку после выезда.
    Не коммитит.
    """
    day = booking.check_in + timedelta(days=1)
    while day < booking.check_out:
        db.add(HousekeepingTask(booking=booking, room_id=booking.room_id, date=day, kind=HousekeepingKind.DAILY))
        day += timedelta(days=1)
    db.add(
        HousekeepingTask(
            booking=booking, room_id=booking.room_id, date=booking.check_out, kind=HousekeepingKind.CHECKOUT
        )
    )
    db.flush()


def delete_planned_tasks(db: Session, booking: Booking) -> None:
    """При отмене брони запланированные уборки снимаются; уже выполненные и пропущенные остаются в истории."""
    db.execute(
        delete(HousekeepingTask).where(
            HousekeepingTask.booking_id == booking.id, HousekeepingTask.status == HousekeepingStatus.PLANNED
        )
    )


def guest_can_change_slot(kind: str, task_status: str, day: date) -> bool:
    """Гость меняет слот только запланированной ежедневной уборки и только для дат позже сегодняшней:
    уборка на сегодня уже в работе, а после выезда время выбирать не нужно."""
    return (
        kind == HousekeepingKind.DAILY
        and task_status == HousekeepingStatus.PLANNED
        and day > hotel_time.hotel_today()
    )


def set_task_status(task: HousekeepingTask, to_status: HousekeepingStatus) -> None:
    """Отметка администратора. Можно поправить ошибочную отметку: done и skipped меняются друг на друга."""
    task.status = to_status
    task.done_at = hotel_time.hotel_now() if to_status == HousekeepingStatus.DONE else None


def day_board(db: Session, day: date) -> dict[str, object]:
    """Расписание дня: уборки после выезда (сначала с заездом в тот же день), ежедневные по слотам, «не беспокоить»
    и заказы услуг уборки на эту дату."""
    tasks = db.scalars(
        select(HousekeepingTask)
        .join(Booking)
        .where(HousekeepingTask.date == day, Booking.status == BookingStatus.CONFIRMED)
        .options(joinedload(HousekeepingTask.room), joinedload(HousekeepingTask.booking))
        .order_by(HousekeepingTask.id)
    ).all()
    # Номера, в которые сегодня заезжает подтверждённая бронь: их после выезда надо убрать до заезда.
    arrivals = set(
        db.scalars(select(Booking.room_id).where(Booking.status == BookingStatus.CONFIRMED, Booking.check_in == day))
    )
    rows = [
        {
            "id": task.id,
            "date": task.date,
            "kind": task.kind,
            "slot": task.slot,
            "status": task.status,
            "done_at": task.done_at,
            "room": task.room,
            "booking": task.booking,
            "arrival_today": task.kind == HousekeepingKind.CHECKOUT and task.room_id in arrivals,
        }
        for task in tasks
    ]

    # Уборки после выезда с заездом в тот же день идут первыми; sorted стабилен, порядок по id сохраняется.
    checkout = sorted(
        (row for row in rows if row["kind"] == HousekeepingKind.CHECKOUT), key=lambda row: not row["arrival_today"]
    )
    daily = [row for row in rows if row["kind"] == HousekeepingKind.DAILY]
    orders = db.scalars(
        orders_select(day).where(
            Service.category == ServiceCategory.HOUSEKEEPING, ServiceOrder.status != OrderStatus.CANCELLED
        )
    ).all()
    return {
        "date": day,
        "checkout": checkout,
        "daily": {slot.value: [row for row in daily if row["slot"] == slot] for slot in DAILY_SLOTS},
        "dnd": [row for row in daily if row["slot"] == HousekeepingSlot.DND],
        "orders": list(orders),
    }
