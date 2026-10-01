from datetime import date, timedelta

import pytest
from fastapi import HTTPException, Request
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import Room
from app.security import RateLimiter
from seed import ROOMS

STANDART_ID = 2  # порядок вставки в seed.ROOMS: сид создаёт номера один раз, тесты откатывают свои изменения


def days_ahead(days: int) -> str:
    return (date.today() + timedelta(days=days)).isoformat()


def booking(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "room_id": STANDART_ID,
        "guest_name": "Иван Петров",
        "phone": "+7 900 123-45-67",
        "email": "ivan@example.com",
        "check_in": days_ahead(10),
        "check_out": days_ahead(13),
        "guests": 2,
        "comment": None,
    }
    payload.update(overrides)
    return payload


def test_health(client: TestClient) -> None:
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_hotel(client: TestClient) -> None:
    response = client.get("/api/hotel")
    assert response.status_code == 200
    assert response.json()["name"] == "Kivana"


def test_list_rooms(client: TestClient) -> None:
    response = client.get("/api/rooms")
    assert response.status_code == 200
    assert len(response.json()) == len(ROOMS)


def test_filter_rooms_by_max_price(client: TestClient) -> None:
    response = client.get("/api/rooms", params={"max_price": 5000})
    prices = [room["price_per_night"] for room in response.json()]
    assert prices
    assert all(price <= 5000 for price in prices)


def test_filter_rooms_returns_empty_list(client: TestClient) -> None:
    response = client.get("/api/rooms", params={"max_price": 1})
    assert response.status_code == 200
    assert response.json() == []


def test_get_room_by_slug(client: TestClient) -> None:
    response = client.get("/api/rooms/lyuks")
    assert response.status_code == 200
    assert response.json()["slug"] == "lyuks"


def test_get_room_unknown_slug_returns_404(client: TestClient) -> None:
    assert client.get("/api/rooms/net-takogo-nomera").status_code == 404


def test_create_booking(client: TestClient) -> None:
    response = client.post("/api/bookings", json=booking(comment="Ранний заезд"))
    assert response.status_code == 201
    assert response.json()["status"] == "new"


@pytest.mark.parametrize(
    "overrides",
    [
        {"check_out": days_ahead(10)},
        {"check_in": days_ahead(-1), "check_out": days_ahead(2)},
        {"phone": "12345"},
        {"email": "not-an-email"},
        {"guests": 0},
        {"guest_name": "  "},
        {"check_in": days_ahead(366), "check_out": days_ahead(369)},
        {"check_in": days_ahead(10), "check_out": days_ahead(101)},
    ],
    ids=[
        "check_out_not_after_check_in",
        "check_in_in_past",
        "short_phone",
        "bad_email",
        "zero_guests",
        "blank_name",
        "check_in_too_far_ahead",
        "stay_too_long",
    ],
)
def test_invalid_booking_returns_422(client: TestClient, overrides: dict[str, object]) -> None:
    assert client.post("/api/bookings", json=booking(**overrides)).status_code == 422


@pytest.mark.parametrize(
    "overrides",
    [
        {"check_in": days_ahead(365), "check_out": days_ahead(367)},
        {"check_in": days_ahead(10), "check_out": days_ahead(100)},
    ],
    ids=["check_in_exactly_365_days_ahead", "stay_exactly_90_nights"],
)
def test_valid_booking_at_business_rule_boundary(client: TestClient, overrides: dict[str, object]) -> None:
    assert client.post("/api/bookings", json=booking(**overrides)).status_code == 201


def test_booking_over_capacity_returns_400(client: TestClient) -> None:
    response = client.post("/api/bookings", json=booking(guests=3))
    assert response.status_code == 400
    assert response.json()["detail"] == "Максимальное число гостей в номере — 2"


def test_booking_unknown_room_returns_404(client: TestClient) -> None:
    assert client.post("/api/bookings", json=booking(room_id=999)).status_code == 404


def test_booking_unavailable_room_returns_400(client: TestClient, db: Session) -> None:
    db.get_one(Room, STANDART_ID).is_available = False
    db.flush()
    assert client.post("/api/bookings", json=booking()).status_code == 400


def test_new_bookings_do_not_block_dates(client: TestClient) -> None:
    assert client.post("/api/bookings", json=booking()).status_code == 201
    assert client.post("/api/bookings", json=booking()).status_code == 201


def test_confirmed_booking_blocks_overlapping_dates(admin_client: TestClient) -> None:
    booking_id = admin_client.post("/api/bookings", json=booking()).json()["id"]
    assert admin_client.patch(f"/api/admin/bookings/{booking_id}", json={"status": "confirmed"}).status_code == 200

    overlapping = admin_client.post("/api/bookings", json=booking(check_in=days_ahead(12), check_out=days_ahead(15)))
    assert overlapping.status_code == 409

    same_day_turnover = admin_client.post("/api/bookings", json=booking(check_in=days_ahead(13), check_out=days_ahead(15)))
    assert same_day_turnover.status_code == 201


def test_confirming_second_overlapping_booking_returns_409(admin_client: TestClient) -> None:
    first = admin_client.post("/api/bookings", json=booking()).json()["id"]
    second = admin_client.post("/api/bookings", json=booking()).json()["id"]

    assert admin_client.patch(f"/api/admin/bookings/{first}", json={"status": "confirmed"}).status_code == 200
    assert admin_client.patch(f"/api/admin/bookings/{second}", json={"status": "confirmed"}).status_code == 409
    assert admin_client.patch(f"/api/admin/bookings/{second}", json={"status": "cancelled"}).status_code == 200


def test_admin_lists_and_filters_bookings(admin_client: TestClient) -> None:
    first = admin_client.post("/api/bookings", json=booking()).json()["id"]
    admin_client.post("/api/bookings", json=booking())
    admin_client.patch(f"/api/admin/bookings/{first}", json={"status": "cancelled"})

    everything = admin_client.get("/api/admin/bookings").json()
    assert everything["total"] == 2
    assert everything["items"][0]["room"]["slug"] == "standart"

    cancelled = admin_client.get("/api/admin/bookings", params={"status": "cancelled"}).json()
    assert [item["id"] for item in cancelled["items"]] == [first]


def test_booking_rate_limit(client: TestClient) -> None:
    statuses = [client.post("/api/bookings", json=booking()).status_code for _ in range(6)]
    assert statuses == [201] * 5 + [429]


def test_site_wide_limit_ignores_client_address() -> None:
    limiter = RateLimiter(limit=2, window_seconds=60, per_client=False)
    first, second, third = (Request({"type": "http", "client": (ip, 1)}) for ip in ("1.1.1.1", "2.2.2.2", "3.3.3.3"))
    limiter(first)
    limiter(second)
    with pytest.raises(HTTPException) as rejected:
        limiter(third)
    assert rejected.value.status_code == 429
