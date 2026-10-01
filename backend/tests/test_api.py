import pytest
from fastapi import HTTPException, Request
from fastapi.testclient import TestClient

from app.security import RateLimiter
from seed import ROOMS


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


def test_site_wide_limit_ignores_client_address() -> None:
    limiter = RateLimiter(limit=2, window_seconds=60, per_client=False)
    first, second, third = (Request({"type": "http", "client": (ip, 1)}) for ip in ("1.1.1.1", "2.2.2.2", "3.3.3.3"))
    limiter(first)
    limiter(second)
    with pytest.raises(HTTPException) as rejected:
        limiter(third)
    assert rejected.value.status_code == 429
