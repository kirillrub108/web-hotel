from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from test_bookings import NOW, MakeBooking, MakeUser, day, set_clock

from app import hotel_time
from app.housekeeping import create_stay_tasks
from app.models import (
    Booking,
    BookingStatus,
    HousekeepingKind,
    HousekeepingSlot,
    HousekeepingStatus,
    HousekeepingTask,
    OrderStatus,
    Service,
    ServiceOrder,
)
from conftest import login
from seed import SERVICES, seed_services


@pytest.fixture(autouse=True)
def frozen_clock(monkeypatch: pytest.MonkeyPatch) -> None:
    set_clock(monkeypatch, NOW)


def at(offset: int, clock: str) -> str:
    """Время заказа в формате поля datetime-local: без пояса, по часам отеля."""
    return f"{day(offset).isoformat()}T{clock}"


def service_id(db: Session, slug: str) -> int:
    return db.scalars(select(Service).where(Service.slug == slug)).one().id


def order_body(db: Session, slug: str, when: str, **extra: object) -> dict[str, object]:
    return {"service_id": service_id(db, slug), "scheduled_at": when, **extra}


def tasks_of(db: Session, booking: Booking) -> list[HousekeepingTask]:
    return list(
        db.scalars(
            select(HousekeepingTask)
            .where(HousekeepingTask.booking_id == booking.id)
            .order_by(HousekeepingTask.date, HousekeepingTask.kind)
        )
    )


def confirmed_with_tasks(db: Session, make_booking: MakeBooking, start: int, end: int, **kwargs: object) -> Booking:
    """Подтверждённая бронь с уборками — как после подтверждения, но с любыми датами, в том числе уже начатыми."""
    booking = make_booking(day(start), day(end), status=BookingStatus.CONFIRMED, **kwargs)
    create_stay_tasks(db, booking)
    return booking


# --- Уборки при подтверждении и отмене брони -------------------------------------------------------------------


@pytest.mark.parametrize("nights", [1, 2, 5])
def test_confirm_creates_daily_and_checkout_tasks(
    nights: int, admin_client: TestClient, make_booking: MakeBooking, db: Session
) -> None:
    booking = make_booking(day(5), day(5 + nights))

    response = admin_client.post(f"/api/admin/bookings/{booking.id}/confirm", json={})
    assert response.status_code == 200, response.text

    tasks = tasks_of(db, booking)
    daily = [task.date for task in tasks if task.kind == HousekeepingKind.DAILY]
    # Ежедневные — строго между заездом и выездом: ночей минус одна; после выезда — ровно одна.
    assert daily == [day(5 + offset) for offset in range(1, nights)]
    checkout = [task for task in tasks if task.kind == HousekeepingKind.CHECKOUT]
    assert [task.date for task in checkout] == [day(5 + nights)]
    assert all(task.slot == HousekeepingSlot.MORNING and task.status == HousekeepingStatus.PLANNED for task in tasks)
    assert all(task.room_id == booking.room_id for task in tasks)


def test_decline_creates_no_tasks(admin_client: TestClient, make_booking: MakeBooking, db: Session) -> None:
    booking = make_booking(day(5), day(8))
    admin_client.post(f"/api/admin/bookings/{booking.id}/decline", json={"reason": "Нет мест на эти даты"})
    assert tasks_of(db, booking) == []


def test_cancel_removes_planned_tasks_and_open_orders(
    guest_client: TestClient, admin_client: TestClient, make_booking: MakeBooking, db: Session
) -> None:
    booking = make_booking(day(5), day(8))
    admin_client.post(f"/api/admin/bookings/{booking.id}/confirm", json={})
    done_task = tasks_of(db, booking)[0]
    done_task.status = HousekeepingStatus.DONE
    db.flush()

    ids = []
    for slug in ("transfer-aeroport", "spa", "prachechnaya"):
        response = guest_client.post(
            f"/api/account/bookings/{booking.id}/service-orders", json=order_body(db, slug, at(6, "10:00"))
        )
        assert response.status_code == 201, response.text
        ids.append(response.json()["orders"][-1]["id"])
    admin_client.patch(f"/api/admin/service-orders/{ids[1]}", json={"status": "accepted"})
    admin_client.patch(f"/api/admin/service-orders/{ids[2]}", json={"status": "accepted"})
    admin_client.patch(f"/api/admin/service-orders/{ids[2]}", json={"status": "done"})

    response = guest_client.post(f"/api/account/bookings/{booking.id}/cancel")
    assert response.status_code == 200, response.text

    # Остаётся только закрытая уборка, новые и принятые заказы отменены, выполненный сохранён.
    assert [task.id for task in tasks_of(db, booking)] == [done_task.id]
    statuses = {order.id: order.status for order in db.scalars(select(ServiceOrder))}
    assert [statuses[order_id] for order_id in ids] == [
        OrderStatus.CANCELLED,
        OrderStatus.CANCELLED,
        OrderStatus.DONE,
    ]


def test_cancel_pending_booking_touches_nothing(guest_client: TestClient, make_booking: MakeBooking) -> None:
    booking = make_booking(day(5), day(8))
    assert guest_client.post(f"/api/account/bookings/{booking.id}/cancel").status_code == 200


# --- Заказы услуг ----------------------------------------------------------------------------------------------


def test_order_snapshots_price_and_total(
    guest_client: TestClient, admin_client: TestClient, make_booking: MakeBooking, db: Session
) -> None:
    booking = make_booking(day(2), day(5), status=BookingStatus.CONFIRMED)

    response = guest_client.post(
        f"/api/account/bookings/{booking.id}/service-orders",
        json=order_body(db, "zavtrak-v-nomer", at(3, "09:00"), quantity=2, comment="  Без лука  "),
    )

    assert response.status_code == 201, response.text
    detail = response.json()
    order = detail["orders"][0]
    assert (order["quantity"], order["unit_price"], order["total"]) == (2, 650, 1300)
    assert order["comment"] == "Без лука"
    assert order["status"] == "new" and order["can_cancel"] is True
    assert detail["services_total"] == 1300
    # Время без пояса — время отеля: 09:00 по Москве.
    stored = db.scalars(select(ServiceOrder)).one().scheduled_at
    assert stored.astimezone(hotel_time.HOTEL_TZ).hour == 9

    # Цена в каталоге выросла — заказ хранит прежнюю.
    service = db.scalars(select(Service).where(Service.slug == "zavtrak-v-nomer")).one()
    service.price = 900
    db.flush()
    order = admin_client.get("/api/admin/service-orders").json()[0]
    assert (order["unit_price"], order["total"]) == (650, 1300)


def test_per_stay_service_ignores_quantity(guest_client: TestClient, make_booking: MakeBooking, db: Session) -> None:
    booking = make_booking(day(2), day(5), status=BookingStatus.CONFIRMED)
    response = guest_client.post(
        f"/api/account/bookings/{booking.id}/service-orders",
        json=order_body(db, "transfer-aeroport", at(2, "15:00"), quantity=5),
    )
    assert response.status_code == 201
    assert (response.json()["orders"][0]["quantity"], response.json()["services_total"]) == (1, 1800)


@pytest.mark.parametrize("quantity", [0, 21])
def test_order_quantity_out_of_range_is_rejected(
    quantity: int, guest_client: TestClient, make_booking: MakeBooking, db: Session
) -> None:
    booking = make_booking(day(2), day(5), status=BookingStatus.CONFIRMED)
    response = guest_client.post(
        f"/api/account/bookings/{booking.id}/service-orders",
        json=order_body(db, "syrniki", at(3, "09:00"), quantity=quantity),
    )
    assert response.status_code == 422


# Бронь: заезд день+2 (14:00), выезд день+5 (12:00); «сейчас» — день 0, 12:00.
@pytest.mark.parametrize(
    ("slug", "when"),
    [
        ("transfer-aeroport", at(2, "13:59")),  # до заезда
        ("transfer-aeroport", at(5, "12:30")),  # после выезда
        ("syrniki", at(6, "09:00")),  # на следующий день после выезда
        ("syrniki", at(3, "07:59")),  # кухня ещё закрыта
        ("syrniki", at(3, "23:00")),  # кухня уже закрыта: конец интервала не включается
        ("syrniki", at(3, "23:30")),
    ],
)
def test_order_time_outside_rules_is_400(
    slug: str, when: str, guest_client: TestClient, make_booking: MakeBooking, db: Session
) -> None:
    booking = make_booking(day(2), day(5), status=BookingStatus.CONFIRMED)
    response = guest_client.post(
        f"/api/account/bookings/{booking.id}/service-orders", json=order_body(db, slug, when)
    )
    assert response.status_code == 400, response.text
    assert db.scalar(select(func.count(ServiceOrder.id))) == 0


def test_order_in_the_past_is_400(guest_client: TestClient, make_booking: MakeBooking, db: Session) -> None:
    # Проживание уже идёт: окно началось вчера, но 10:00 сегодняшнего дня прошло (сейчас 12:00).
    booking = make_booking(day(-1), day(3), status=BookingStatus.CONFIRMED)
    response = guest_client.post(
        f"/api/account/bookings/{booking.id}/service-orders", json=order_body(db, "transfer-aeroport", at(0, "10:00"))
    )
    assert response.status_code == 400
    assert "прошедшее" in response.json()["detail"]


@pytest.mark.parametrize(
    ("clock", "expected"), [("08:00", 201), ("22:59", 201), ("07:59", 400), ("23:00", 400)]
)
def test_food_only_during_room_service_hours(
    clock: str, expected: int, guest_client: TestClient, make_booking: MakeBooking, db: Session
) -> None:
    booking = make_booking(day(2), day(5), status=BookingStatus.CONFIRMED)
    response = guest_client.post(
        f"/api/account/bookings/{booking.id}/service-orders", json=order_body(db, "sudak", at(3, clock))
    )
    assert response.status_code == expected


def test_non_food_ignores_room_service_hours(guest_client: TestClient, make_booking: MakeBooking, db: Session) -> None:
    booking = make_booking(day(2), day(5), status=BookingStatus.CONFIRMED)
    response = guest_client.post(
        f"/api/account/bookings/{booking.id}/service-orders", json=order_body(db, "spa", at(3, "07:00"))
    )
    assert response.status_code == 201


@pytest.mark.parametrize(
    ("booking_status", "start", "end"),
    [
        (BookingStatus.PENDING, 2, 5),
        (BookingStatus.DECLINED, 2, 5),
        (BookingStatus.CANCELLED, 2, 5),
        # Проживание закончилось: выезд был вчера.
        (BookingStatus.CONFIRMED, -4, -1),
    ],
)
def test_order_to_unsuitable_booking_is_409(
    booking_status: BookingStatus,
    start: int,
    end: int,
    guest_client: TestClient,
    make_booking: MakeBooking,
    db: Session,
) -> None:
    booking = make_booking(day(start), day(end), status=booking_status)
    response = guest_client.post(
        f"/api/account/bookings/{booking.id}/service-orders", json=order_body(db, "spa", at(3, "12:00"))
    )
    assert response.status_code == 409, response.text


def test_foreign_booking_and_unknown_service_are_404(
    guest_client: TestClient, make_booking: MakeBooking, make_user: MakeUser, db: Session
) -> None:
    other = make_user("other@example.com")
    foreign = make_booking(day(2), day(5), status=BookingStatus.CONFIRMED, user=other)
    mine = make_booking(day(7), day(9), status=BookingStatus.CONFIRMED)

    body = order_body(db, "spa", at(3, "12:00"))
    assert guest_client.post(f"/api/account/bookings/{foreign.id}/service-orders", json=body).status_code == 404
    unknown = {**body, "service_id": 999_999, "scheduled_at": at(8, "12:00")}
    assert guest_client.post(f"/api/account/bookings/{mine.id}/service-orders", json=unknown).status_code == 404


def test_inactive_service_cannot_be_ordered_but_stays_in_old_order(
    guest_client: TestClient, make_booking: MakeBooking, db: Session
) -> None:
    booking = make_booking(day(2), day(5), status=BookingStatus.CONFIRMED)
    path = f"/api/account/bookings/{booking.id}/service-orders"
    assert guest_client.post(path, json=order_body(db, "spa", at(3, "12:00"))).status_code == 201

    service = db.scalars(select(Service).where(Service.slug == "spa")).one()
    service.is_active = False
    db.flush()

    assert guest_client.post(path, json=order_body(db, "spa", at(3, "13:00"))).status_code == 400
    orders = guest_client.get(f"/api/account/bookings/{booking.id}").json()["orders"]
    assert [(o["service"]["title"], o["service"]["is_active"]) for o in orders] == [("SPA-программа", False)]


# --- Статусы заказа --------------------------------------------------------------------------------------------


def place_order(guest_client: TestClient, db: Session, booking: Booking) -> int:
    response = guest_client.post(
        f"/api/account/bookings/{booking.id}/service-orders", json=order_body(db, "spa", at(3, "12:00"))
    )
    assert response.status_code == 201, response.text
    return int(response.json()["orders"][-1]["id"])


def test_guest_cancels_only_new_order(
    guest_client: TestClient, admin_client: TestClient, make_booking: MakeBooking, db: Session
) -> None:
    booking = make_booking(day(2), day(5), status=BookingStatus.CONFIRMED)
    first, second = place_order(guest_client, db, booking), place_order(guest_client, db, booking)
    admin_client.patch(f"/api/admin/service-orders/{second}", json={"status": "accepted"})

    response = guest_client.post(f"/api/account/service-orders/{first}/cancel")
    assert response.status_code == 200
    detail = response.json()
    assert [o["status"] for o in detail["orders"]] == ["cancelled", "accepted"]
    # Отменённый заказ в итог не входит.
    assert detail["services_total"] == 3200

    assert guest_client.post(f"/api/account/service-orders/{second}/cancel").status_code == 409
    assert guest_client.post(f"/api/account/service-orders/{first}/cancel").status_code == 409


def test_cannot_cancel_foreign_order(
    guest_client: TestClient, make_booking: MakeBooking, make_user: MakeUser, db: Session
) -> None:
    booking = make_booking(day(2), day(5), status=BookingStatus.CONFIRMED)
    order_id = place_order(guest_client, db, booking)
    stranger = login(make_user("stranger@example.com").email)
    assert stranger.post(f"/api/account/service-orders/{order_id}/cancel").status_code == 404


def test_admin_order_transitions(
    guest_client: TestClient, admin_client: TestClient, make_booking: MakeBooking, db: Session
) -> None:
    booking = make_booking(day(2), day(5), status=BookingStatus.CONFIRMED)
    order_id = place_order(guest_client, db, booking)
    path = f"/api/admin/service-orders/{order_id}"

    assert admin_client.patch(path, json={"status": "done"}).status_code == 409  # new → done нельзя
    assert admin_client.patch(path, json={"status": "accepted"}).json()["status"] == "accepted"
    assert admin_client.patch(path, json={"status": "new"}).status_code == 409
    assert admin_client.patch(path, json={"status": "done"}).json()["status"] == "done"
    # Выполненный заказ не меняется и не отменяется.
    assert admin_client.patch(path, json={"status": "cancelled"}).status_code == 409
    assert admin_client.patch("/api/admin/service-orders/999999", json={"status": "accepted"}).status_code == 404


def test_admin_cancels_accepted_order(
    guest_client: TestClient, admin_client: TestClient, make_booking: MakeBooking, db: Session
) -> None:
    booking = make_booking(day(2), day(5), status=BookingStatus.CONFIRMED)
    order_id = place_order(guest_client, db, booking)
    path = f"/api/admin/service-orders/{order_id}"
    admin_client.patch(path, json={"status": "accepted"})
    assert admin_client.patch(path, json={"status": "cancelled"}).json()["status"] == "cancelled"


def test_admin_orders_filters(
    guest_client: TestClient, admin_client: TestClient, make_booking: MakeBooking, db: Session
) -> None:
    booking = make_booking(day(2), day(6), status=BookingStatus.CONFIRMED)
    path = f"/api/account/bookings/{booking.id}/service-orders"
    guest_client.post(path, json=order_body(db, "spa", at(3, "12:00")))
    guest_client.post(path, json=order_body(db, "spa", at(4, "12:00")))
    second = guest_client.get(f"/api/account/bookings/{booking.id}").json()["orders"][1]["id"]
    admin_client.patch(f"/api/admin/service-orders/{second}", json={"status": "accepted"})

    def listing(query: str) -> list[int]:
        return [order["id"] for order in admin_client.get(f"/api/admin/service-orders?{query}").json()]

    assert len(listing("")) == 2
    assert listing("status=accepted") == [second]
    assert len(listing(f"date={day(3).isoformat()}")) == 1
    assert listing(f"date={day(3).isoformat()}&status=accepted") == []
    first = admin_client.get("/api/admin/service-orders").json()[0]
    assert first["booking"]["room"]["name"] and first["booking"]["guest_name"] == "Иван Петров"


# --- Уборки: слот гостя и расписание администратора -------------------------------------------------------------


def test_booking_detail_lists_tasks_and_order_window(
    guest_client: TestClient, make_booking: MakeBooking, db: Session
) -> None:
    booking = confirmed_with_tasks(db, make_booking, 2, 5)
    detail = guest_client.get(f"/api/account/bookings/{booking.id}").json()
    assert detail["can_order"] is True
    assert detail["order_window"]["start"].startswith(f"{day(2).isoformat()}T14:00")
    assert detail["order_window"]["end"].startswith(f"{day(5).isoformat()}T12:00")
    assert detail["room_service_hours"] == "08:00–23:00"
    assert [(t["date"], t["kind"], t["can_change_slot"]) for t in detail["housekeeping"]] == [
        (day(3).isoformat(), "daily", True),
        (day(4).isoformat(), "daily", True),
        (day(5).isoformat(), "checkout", False),
    ]


def test_guest_sets_slot_and_dnd_for_future_date(
    guest_client: TestClient, make_booking: MakeBooking, db: Session
) -> None:
    booking = confirmed_with_tasks(db, make_booking, -1, 3)
    tomorrow = next(task for task in tasks_of(db, booking) if task.date == day(1))

    response = guest_client.patch(f"/api/account/housekeeping/{tomorrow.id}", json={"slot": "dnd"})
    assert response.status_code == 200, response.text
    assert tomorrow.slot == HousekeepingSlot.DND
    response = guest_client.patch(f"/api/account/housekeeping/{tomorrow.id}", json={"slot": "evening"})
    assert response.json()["housekeeping"][1]["slot"] == "evening"
    assert guest_client.patch(f"/api/account/housekeeping/{tomorrow.id}", json={"slot": "night"}).status_code == 422


def test_guest_cannot_change_slot_for_today_past_checkout_or_closed_task(
    guest_client: TestClient, make_booking: MakeBooking, db: Session
) -> None:
    booking = confirmed_with_tasks(db, make_booking, -2, 3)
    by_date = {task.date: task for task in tasks_of(db, booking)}

    def change(task: HousekeepingTask) -> int:
        return guest_client.patch(f"/api/account/housekeeping/{task.id}", json={"slot": "day"}).status_code

    assert change(by_date[day(-1)]) == 409  # прошедшая дата
    assert change(by_date[day(0)]) == 409  # сегодня
    assert change(by_date[day(3)]) == 409  # уборка после выезда
    tomorrow = by_date[day(1)]
    tomorrow.status = HousekeepingStatus.DONE
    db.flush()
    assert change(tomorrow) == 409  # выполненная
    assert tomorrow.slot == HousekeepingSlot.MORNING


def test_today_follows_hotel_time_zone(
    guest_client: TestClient, make_booking: MakeBooking, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    booking = confirmed_with_tasks(db, make_booking, -1, 3)
    tomorrow = next(task for task in tasks_of(db, booking) if task.date == day(1))
    # 00:30 по Москве: по UTC это ещё вчера, но по часам отеля уже следующие сутки — «завтра» стало «сегодня».
    set_clock(monkeypatch, datetime.combine(day(1), datetime.min.time(), hotel_time.HOTEL_TZ) + timedelta(minutes=30))
    assert guest_client.patch(f"/api/account/housekeeping/{tomorrow.id}", json={"slot": "day"}).status_code == 409


def test_cannot_change_foreign_task(
    make_booking: MakeBooking, make_user: MakeUser, db: Session
) -> None:
    booking = confirmed_with_tasks(db, make_booking, 0, 4)
    task = tasks_of(db, booking)[1]
    stranger = login(make_user("stranger@example.com").email)
    assert stranger.patch(f"/api/account/housekeeping/{task.id}", json={"slot": "day"}).status_code == 404


def test_board_arrival_today_flag_and_order(
    admin_client: TestClient, make_booking: MakeBooking, make_user: MakeUser, db: Session
) -> None:
    # Выезды в один день из двух номеров: в «Стандарт» в тот же день заезжает другая бронь, в «Люкс» — нет.
    # «Люкс» создан раньше, поэтому без сортировки он стоял бы первым.
    quiet = confirmed_with_tasks(db, make_booking, -2, 1, room_slug="lyuks")
    leaving = confirmed_with_tasks(db, make_booking, -2, 1)
    confirmed_with_tasks(db, make_booking, 1, 3, user=make_user("next@example.com"))
    # Заезд на ту же дату в «Люкс» — заявка на рассмотрении, она номер не занимает и флаг не ставит.
    make_booking(day(1), day(2), room_slug="lyuks")

    board = admin_client.get(f"/api/admin/housekeeping?date={day(1).isoformat()}").json()

    assert [(row["booking"]["id"], row["arrival_today"]) for row in board["checkout"]] == [
        (leaving.id, True),
        (quiet.id, False),
    ]
    assert board["date"] == day(1).isoformat()
    assert all(row["kind"] == "checkout" for row in board["checkout"])


def test_board_groups_daily_by_slot_and_lists_housekeeping_orders(
    admin_client: TestClient, guest_client: TestClient, make_booking: MakeBooking, make_user: MakeUser, db: Session
) -> None:
    rooms = ["standart", "lyuks", "apartamenty", "studiya"]
    bookings = [
        confirmed_with_tasks(db, make_booking, -1, 3, room_slug=slug, user=make_user(f"g{i}@example.com"))
        for i, slug in enumerate(rooms)
    ]
    slots = [HousekeepingSlot.EVENING, HousekeepingSlot.DND, HousekeepingSlot.MORNING, HousekeepingSlot.DAY]
    for booking, slot in zip(bookings, slots, strict=True):
        next(task for task in tasks_of(db, booking) if task.date == day(1)).slot = slot
    db.flush()
    # Уборка на другую дату в расписание дня не попадает.
    mine = bookings[0]
    guest_client = login(mine.user.email)
    for slug, clock in [("dop-uborka", "15:00"), ("smena-belya", "16:00"), ("sudak", "13:00")]:
        guest_client.post(
            f"/api/account/bookings/{mine.id}/service-orders", json=order_body(db, slug, at(1, clock))
        )

    board = admin_client.get(f"/api/admin/housekeeping?date={day(1).isoformat()}").json()

    assert [row["booking"]["id"] for row in board["daily"]["morning"]] == [bookings[2].id]
    assert [row["booking"]["id"] for row in board["daily"]["day"]] == [bookings[3].id]
    assert [row["booking"]["id"] for row in board["daily"]["evening"]] == [bookings[0].id]
    assert [row["booking"]["id"] for row in board["dnd"]] == [bookings[1].id]
    assert board["checkout"] == []
    # Только заказы категории «уборка»: еда в расписание не попадает.
    assert [order["service"]["title"] for order in board["orders"]] == ["Дополнительная уборка", "Смена белья"]


def test_board_defaults_to_today(admin_client: TestClient, make_booking: MakeBooking, db: Session) -> None:
    confirmed_with_tasks(db, make_booking, -1, 3)
    board = admin_client.get("/api/admin/housekeeping").json()
    assert board["date"] == day(0).isoformat()
    assert len(board["daily"]["morning"]) == 1


def test_admin_marks_task_done_and_skipped(admin_client: TestClient, make_booking: MakeBooking, db: Session) -> None:
    booking = confirmed_with_tasks(db, make_booking, -1, 3)
    task = next(task for task in tasks_of(db, booking) if task.date == day(0))

    board = admin_client.patch(f"/api/admin/housekeeping/{task.id}", json={"status": "done"}).json()
    row = board["daily"]["morning"][0]
    assert row["status"] == "done" and row["done_at"] is not None

    board = admin_client.patch(f"/api/admin/housekeeping/{task.id}", json={"status": "skipped"}).json()
    row = board["daily"]["morning"][0]
    assert row["status"] == "skipped" and row["done_at"] is None
    assert admin_client.patch("/api/admin/housekeeping/999999", json={"status": "done"}).status_code == 404
    assert admin_client.patch(f"/api/admin/housekeeping/{task.id}", json={"status": "bogus"}).status_code == 422


# --- Каталог услуг ---------------------------------------------------------------------------------------------


def service_body(**overrides: object) -> dict[str, object]:
    body: dict[str, object] = {
        "slug": "late-dinner",
        "title": "Поздний ужин",
        "description": "Ужин из трёх блюд.",
        "category": "food",
        "price": 1200,
        "unit": "per_item",
        "is_active": True,
        "sort_order": 15,
    }
    return {**body, **overrides}


def test_public_catalog_lists_only_active_services_in_order(
    client: TestClient, admin_client: TestClient, db: Session
) -> None:
    services = client.get("/api/services").json()
    assert len(services) == len(SERVICES)
    assert [item["slug"] for item in services][:2] == ["zavtrak-v-nomer", "syrniki"]
    assert {"id", "slug", "title", "description", "category", "price", "unit"} == set(services[0])

    db.scalars(select(Service).where(Service.slug == "spa")).one().is_active = False
    db.flush()
    assert "spa" not in [item["slug"] for item in client.get("/api/services").json()]


def test_admin_service_crud(admin_client: TestClient, client: TestClient) -> None:
    created = admin_client.post("/api/admin/services", json=service_body())
    assert created.status_code == 201, created.text
    service_id_ = created.json()["id"]
    assert created.json()["orders_count"] == 0

    assert admin_client.post("/api/admin/services", json=service_body()).status_code == 409

    updated = admin_client.patch(f"/api/admin/services/{service_id_}", json=service_body(price=1500, is_active=False))
    assert updated.status_code == 200 and updated.json()["price"] == 1500
    assert admin_client.patch("/api/admin/services/999999", json=service_body()).status_code == 404
    assert "late-dinner" not in [item["slug"] for item in client.get("/api/services").json()]
    assert "late-dinner" in [item["slug"] for item in admin_client.get("/api/admin/services").json()]

    assert admin_client.delete(f"/api/admin/services/{service_id_}").status_code == 204
    assert admin_client.delete(f"/api/admin/services/{service_id_}").status_code == 404


@pytest.mark.parametrize(
    "overrides",
    [{"slug": "Bad Slug"}, {"title": "a"}, {"price": -1}, {"category": "spa"}, {"unit": "per_hour"}],
)
def test_admin_service_validation(overrides: dict[str, object], admin_client: TestClient) -> None:
    assert admin_client.post("/api/admin/services", json=service_body(**overrides)).status_code == 422


def test_service_with_orders_cannot_be_deleted(
    admin_client: TestClient, guest_client: TestClient, make_booking: MakeBooking, db: Session
) -> None:
    booking = make_booking(day(2), day(5), status=BookingStatus.CONFIRMED)
    place_order(guest_client, db, booking)
    spa = service_id(db, "spa")

    response = admin_client.delete(f"/api/admin/services/{spa}")
    assert response.status_code == 409
    assert "деактивировать" in response.json()["detail"]
    row = next(item for item in admin_client.get("/api/admin/services").json() if item["id"] == spa)
    assert row["orders_count"] == 1


def test_seed_services_is_idempotent(db: Session) -> None:
    assert 10 <= len(SERVICES) <= 14
    assert len({row[0] for row in SERVICES}) == len(SERVICES)
    assert db.scalar(select(func.count(Service.id))) == len(SERVICES)

    # Правка администратора переживает повторный сид, удалённая услуга возвращается.
    db.scalars(select(Service).where(Service.slug == "spa")).one().price = 4000
    db.delete(db.scalars(select(Service).where(Service.slug == "tsezar")).one())
    db.flush()
    seed_services(db)
    seed_services(db)

    assert db.scalar(select(func.count(Service.id))) == len(SERVICES)
    assert db.scalars(select(Service.price).where(Service.slug == "spa")).one() == 4000


# --- Доступ ----------------------------------------------------------------------------------------------------

ADMIN_ENDPOINTS: list[tuple[str, str]] = [
    ("get", "/api/admin/services"),
    ("post", "/api/admin/services"),
    ("patch", "/api/admin/services/1"),
    ("delete", "/api/admin/services/1"),
    ("get", "/api/admin/service-orders"),
    ("patch", "/api/admin/service-orders/1"),
    ("get", "/api/admin/housekeeping"),
    ("patch", "/api/admin/housekeeping/1"),
]


@pytest.mark.parametrize(("method", "path"), ADMIN_ENDPOINTS)
def test_admin_endpoints_forbidden_for_guest(method: str, path: str, guest_client: TestClient) -> None:
    assert guest_client.request(method, path, json={}).status_code == 403


@pytest.mark.parametrize(("method", "path"), ADMIN_ENDPOINTS)
def test_admin_endpoints_need_login(method: str, path: str, client: TestClient) -> None:
    assert client.request(method, path, json={}).status_code == 401


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("post", "/api/account/bookings/1/service-orders"),
        ("post", "/api/account/service-orders/1/cancel"),
        ("patch", "/api/account/housekeeping/1"),
    ],
)
def test_account_endpoints_need_login(method: str, path: str, client: TestClient) -> None:
    assert client.request(method, path, json={}).status_code == 401

