from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event
from sqlalchemy.orm import Session
from test_bookings import NOW, MakeBooking, MakeUser, booking_payload, day, set_clock

from app.booking_rules import Segment, client_segment
from app.database import engine
from app.models import BookingStatus, CrmStatus, User, UserRole
from conftest import login


@pytest.fixture(autouse=True)
def frozen_clock(monkeypatch: pytest.MonkeyPatch) -> None:
    set_clock(monkeypatch, NOW)


def clients(client: TestClient, **params: object) -> dict[str, object]:
    response = client.get("/api/admin/clients", params=params)
    assert response.status_code == 200, response.text
    return response.json()


def names(page: dict[str, object]) -> list[str]:
    return [item["full_name"] for item in page["items"]]  # type: ignore[index, union-attr]


def by_id(page: dict[str, object], user: User) -> dict[str, object]:
    return next(item for item in page["items"] if item["id"] == user.id)  # type: ignore[union-attr, index]


# --- Показатели -------------------------------------------------------------------------------------------------


def test_segments() -> None:
    assert [client_segment(n) for n in (0, 1, 2, 5)] == [Segment.NEW, Segment.GUEST, Segment.REGULAR, Segment.REGULAR]


def test_metrics_are_computed_from_bookings(admin_client: TestClient, guest: User, make_booking: MakeBooking) -> None:
    # Завершённые: выезд раньше сегодня и выезд ровно сегодня (граница включена).
    make_booking(day(-20), day(-18), status=BookingStatus.CONFIRMED)  # 2 ночи
    make_booking(day(-3), day(0), status=BookingStatus.CONFIRMED, room_slug="studiya")  # 3 ночи, 5600 ₽
    # Не завершены или не считаются.
    make_booking(day(5), day(7), status=BookingStatus.CONFIRMED)  # подтверждена, но впереди: только в выручке
    make_booking(day(-10), day(-8), status=BookingStatus.CANCELLED)
    make_booking(day(-30), day(-28), status=BookingStatus.DECLINED)
    make_booking(day(20), day(22), status=BookingStatus.PENDING)

    got = by_id(clients(admin_client), guest)
    assert got["stays"] == 2
    assert got["nights"] == 5
    assert got["revenue"] == 2 * 4500 + 3 * 5600 + 2 * 4500
    assert got["last_stay_at"] == day(0).isoformat()
    assert got["segment"] == "regular"


def test_one_stay_is_guest_and_none_is_new(
    admin_client: TestClient, guest: User, make_user: MakeUser, make_booking: MakeBooking
) -> None:
    newcomer = make_user("new@example.com", full_name="Новичок")
    make_booking(day(-5), day(-3), status=BookingStatus.CONFIRMED)
    page = clients(admin_client)
    assert by_id(page, guest)["segment"] == "guest"
    fresh = by_id(page, newcomer)
    assert (fresh["segment"], fresh["stays"], fresh["nights"], fresh["revenue"], fresh["last_stay_at"]) == (
        "new",
        0,
        0,
        0,
        None,
    )


def test_stays_of_different_clients_do_not_mix(
    admin_client: TestClient, guest: User, make_user: MakeUser, make_booking: MakeBooking
) -> None:
    other = make_user("other@example.com", full_name="Пётр Сидоров")
    make_booking(day(-5), day(-3), status=BookingStatus.CONFIRMED)
    make_booking(day(-5), day(-1), status=BookingStatus.CONFIRMED, user=other, room_slug="lyuks")
    page = clients(admin_client)
    assert (by_id(page, guest)["nights"], by_id(page, other)["nights"]) == (2, 4)
    assert (by_id(page, guest)["revenue"], by_id(page, other)["revenue"]) == (9000, 4 * 9900)


def test_list_has_only_guests(admin_client: TestClient, admin_user: User, guest: User) -> None:
    page = clients(admin_client)
    assert page["total"] == 1
    assert names(page) == [guest.full_name]
    assert "email" in page["items"][0]  # type: ignore[index]


def test_list_runs_constant_number_of_queries(
    admin_client: TestClient, make_user: MakeUser, make_booking: MakeBooking
) -> None:
    """Показатели считаются агрегацией в одном запросе: число запросов не растёт с числом клиентов."""
    statements: list[str] = []

    def count(*args: object) -> None:
        statements.append("query")

    def run() -> int:
        statements.clear()
        event.listen(engine, "before_cursor_execute", count)
        try:
            assert clients(admin_client)["total"] > 0
        finally:
            event.remove(engine, "before_cursor_execute", count)
        return len(statements)

    few = run()
    for index in range(8):
        user = make_user(f"many{index}@example.com", full_name=f"Клиент {index}")
        make_booking(day(-60 + 3 * index), day(-58 + 3 * index), status=BookingStatus.CONFIRMED, user=user)
    assert run() == few


# --- Список: поиск, порядок, страницы ---------------------------------------------------------------------------


@pytest.fixture
def people(db: Session, make_user: MakeUser) -> dict[str, User]:
    anna = make_user("anna.volkova@example.com", full_name="Анна Волкова")
    boris = make_user("boris@mail.test", full_name="Борис Орлов")
    anna.phone = "+7 (900) 111-22-33"
    boris.phone = "8 915 555-66-77"
    db.flush()
    return {"anna": anna, "boris": boris}


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("волк", ["Анна Волкова"]),
        ("ОРЛОВ", ["Борис Орлов"]),
        ("anna.volkova@", ["Анна Волкова"]),
        ("mail.test", ["Борис Орлов"]),
        ("900 111", ["Анна Волкова"]),
        ("+79001112233", ["Анна Волкова"]),
        ("915-555", ["Борис Орлов"]),
        ("  Анна  ", ["Анна Волкова"]),
        ("нет такого", []),
        ("%", []),
        ("_", []),
    ],
)
def test_search(admin_client: TestClient, people: dict[str, User], text: str, expected: list[str]) -> None:
    page = clients(admin_client, search=text)
    assert names(page) == expected
    assert page["total"] == len(expected)


def test_search_by_phone_from_booking(
    admin_client: TestClient, people: dict[str, User], make_booking: MakeBooking
) -> None:
    # В профиле Бориса другой номер, но в его брони указан «+7 900 123-45-67».
    make_booking(day(-5), day(-3), status=BookingStatus.CONFIRMED, user=people["boris"])
    assert names(clients(admin_client, search="123-45-67")) == ["Борис Орлов"]


def test_search_requires_a_real_match_for_short_digit_input(admin_client: TestClient, people: dict[str, User]) -> None:
    # Меньше трёх цифр по телефону не ищем — иначе «7» нашёл бы всех.
    assert clients(admin_client, search="7")["total"] == 0


def test_sorted_by_last_activity(admin_client: TestClient, people: dict[str, User], db: Session) -> None:
    now = datetime.now(UTC)
    people["anna"].last_login_at = now - timedelta(days=5)
    people["boris"].last_login_at = now + timedelta(days=1)
    db.flush()
    assert names(clients(admin_client))[:2] == ["Борис Орлов", "Анна Волкова"]
    people["anna"].last_login_at = now + timedelta(days=2)
    db.flush()
    assert names(clients(admin_client))[:2] == ["Анна Волкова", "Борис Орлов"]


def test_booking_counts_as_activity(
    admin_client: TestClient, people: dict[str, User], db: Session, make_booking: MakeBooking
) -> None:
    long_ago = datetime.now(UTC) - timedelta(days=100)
    for person in people.values():
        person.last_login_at = long_ago
    db.flush()
    make_booking(day(30), day(32), user=people["boris"])
    order = names(clients(admin_client))
    assert order.index("Борис Орлов") < order.index("Анна Волкова")


def test_pagination(admin_client: TestClient, make_user: MakeUser, db: Session) -> None:
    now = datetime.now(UTC)
    for index in range(5):
        user = make_user(f"p{index}@example.com", full_name=f"Клиент {index}")
        user.last_login_at = now + timedelta(hours=index)
    db.flush()
    first = clients(admin_client, limit=2, offset=0)
    second = clients(admin_client, limit=2, offset=2)
    last = clients(admin_client, limit=2, offset=4)
    assert (first["total"], names(first), names(second)) == (5, ["Клиент 4", "Клиент 3"], ["Клиент 2", "Клиент 1"])
    assert names(last) == ["Клиент 0"]
    assert admin_client.get("/api/admin/clients", params={"limit": 0}).status_code == 422


def test_empty_client_list(admin_client: TestClient) -> None:
    assert clients(admin_client) == {"items": [], "total": 0}


# --- Карточка и изменение ---------------------------------------------------------------------------------------


def test_client_detail(admin_client: TestClient, guest: User, make_booking: MakeBooking) -> None:
    make_booking(day(-5), day(-3), status=BookingStatus.CONFIRMED)
    make_booking(day(10), day(12))
    detail = admin_client.get(f"/api/admin/clients/{guest.id}").json()
    assert detail["client"]["email"] == guest.email
    assert [item["status"] for item in detail["bookings"]] == ["pending", "confirmed"]
    assert detail["promos"] == []


def test_client_detail_is_404_for_missing_and_admin(admin_client: TestClient, admin_user: User) -> None:
    assert admin_client.get("/api/admin/clients/9999").status_code == 404
    assert admin_client.get(f"/api/admin/clients/{admin_user.id}").status_code == 404
    assert admin_client.patch(f"/api/admin/clients/{admin_user.id}", json={"crm_status": "vip"}).status_code == 404


def test_update_status_and_note(admin_client: TestClient, guest: User, db: Session) -> None:
    response = admin_client.patch(
        f"/api/admin/clients/{guest.id}", json={"crm_status": "vip", "crm_note": "  Просит тихий номер  "}
    )
    assert response.status_code == 200
    assert (response.json()["crm_status"], response.json()["crm_note"]) == ("vip", "Просит тихий номер")

    # Присланное только поле заметки статус не трогает; пустая заметка очищается.
    cleared = admin_client.patch(f"/api/admin/clients/{guest.id}", json={"crm_note": " "}).json()
    assert (cleared["crm_status"], cleared["crm_note"]) == ("vip", None)
    db.refresh(guest)
    assert guest.crm_status == CrmStatus.VIP


@pytest.mark.parametrize("body", [{"crm_status": "gold"}, {"crm_note": "x" * 2001}])
def test_update_validates(admin_client: TestClient, guest: User, body: dict[str, object]) -> None:
    assert admin_client.patch(f"/api/admin/clients/{guest.id}", json=body).status_code == 422


def test_note_is_not_visible_to_guest(admin_client: TestClient, guest_client: TestClient, guest: User) -> None:
    admin_client.patch(f"/api/admin/clients/{guest.id}", json={"crm_note": "Внутренняя заметка"})
    assert "Внутренняя заметка" not in guest_client.get("/api/auth/me").text
    assert "Внутренняя заметка" not in guest_client.get("/api/account/profile").text


# --- Доступ -----------------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("method", "path"),
    [("GET", "/api/admin/clients"), ("GET", "/api/admin/clients/1"), ("PATCH", "/api/admin/clients/1")],
)
def test_crm_is_forbidden_for_guest(guest_client: TestClient, client: TestClient, method: str, path: str) -> None:
    body = {"crm_status": "vip"} if method == "PATCH" else None
    forbidden = guest_client.request(method, path, json=body)
    assert (forbidden.status_code, forbidden.json()["detail"]) == (403, "Доступ только для администратора")
    assert client.request(method, path, json=body).status_code == 401


# --- CRM-статус влияет на авто-решение --------------------------------------------------------------------------


def set_crm(admin_client: TestClient, user: User, crm_status: str) -> None:
    assert admin_client.patch(f"/api/admin/clients/{user.id}", json={"crm_status": crm_status}).status_code == 200


def test_blocking_in_crm_declines_new_bookings_but_keeps_existing(
    admin_client: TestClient, guest_client: TestClient, guest: User
) -> None:
    existing = guest_client.post("/api/bookings", json=booking_payload(start=10, comment="Просьба")).json()
    assert existing["status"] == "pending"

    set_crm(admin_client, guest, "blocked")
    assert guest_client.get(f"/api/account/bookings/{existing['id']}").json()["booking"]["status"] == "pending"

    declined = guest_client.post("/api/bookings", json=booking_payload(start=30)).json()
    assert declined["status"] == "declined"
    detail = admin_client.get(f"/api/admin/bookings/{declined['id']}").json()
    assert detail["booking"]["reason_codes"] == ["client_blocked"]

    # Снятие блокировки возвращает обычные правила.
    set_crm(admin_client, guest, "regular")
    assert guest_client.post("/api/bookings", json=booking_payload(start=50)).json()["status"] == "confirmed"


def test_vip_in_crm_gets_long_stay_confirmed(
    admin_client: TestClient, make_user: MakeUser, guest: User, guest_client: TestClient
) -> None:
    long_stay = booking_payload(start=10, nights=10)
    assert guest_client.post("/api/bookings", json=long_stay).json()["status"] == "pending"

    other = make_user("vip@example.com", full_name="Ольга Белова")
    other_client = login(other.email)
    assert other_client.post("/api/bookings", json=booking_payload(start=40, nights=10)).json()["status"] == "pending"

    set_crm(admin_client, other, "vip")
    vip_booking = other_client.post("/api/bookings", json=booking_payload(start=60, nights=10)).json()
    assert (vip_booking["status"], vip_booking["reasons"]) == (
        "confirmed",
        ["Даты свободны — бронь подтверждена автоматически"],
    )


def test_admin_role_is_not_a_client(admin_client: TestClient, admin_user: User) -> None:
    assert admin_user.role == UserRole.ADMIN
    assert clients(admin_client)["total"] == 0
