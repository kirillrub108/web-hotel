from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health() -> None:
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_list_rooms() -> None:
    response = client.get("/api/rooms")
    assert response.status_code == 200
    rooms = response.json()
    assert len(rooms) == 6
    assert {"slug", "name", "price_per_night", "capacity", "amenities"} <= rooms[0].keys()


def test_filter_rooms_by_max_price() -> None:
    response = client.get("/api/rooms", params={"max_price": 5000})
    assert response.status_code == 200
    prices = [room["price_per_night"] for room in response.json()]
    assert prices
    assert all(price <= 5000 for price in prices)


def test_filter_rooms_returns_empty_list() -> None:
    response = client.get("/api/rooms", params={"max_price": 1})
    assert response.status_code == 200
    assert response.json() == []


def test_get_room_by_slug() -> None:
    response = client.get("/api/rooms/lyuks")
    assert response.status_code == 200
    assert response.json()["slug"] == "lyuks"


def test_get_room_unknown_slug_returns_404() -> None:
    response = client.get("/api/rooms/net-takogo-nomera")
    assert response.status_code == 404


def test_create_booking_with_wrong_dates_returns_422() -> None:
    response = client.post(
        "/api/bookings",
        json={
            "room_id": 1,
            "guest_name": "Иван Петров",
            "phone": "+79001234567",
            "email": "ivan@example.com",
            "check_in": "2026-10-10",
            "check_out": "2026-10-10",
            "guests": 1,
            "comment": None,
        },
    )
    assert response.status_code == 422
