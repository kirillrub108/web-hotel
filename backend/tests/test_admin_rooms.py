from datetime import timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import hotel_time
from app.models import Booking, BookingStatus, Room, User

VALID = {"price_per_night": 5000, "description": "Обновлённое описание номера", "is_available": True}


def standart(db: Session) -> Room:
    return db.scalars(select(Room).where(Room.slug == "standart")).one()


def test_admin_lists_rooms(admin_client: TestClient) -> None:
    response = admin_client.get("/api/admin/rooms")
    assert response.status_code == 200
    assert len(response.json()) == 6


def test_admin_updates_room(db: Session, admin_client: TestClient) -> None:
    room = standart(db)
    response = admin_client.patch(f"/api/admin/rooms/{room.id}", json={**VALID, "is_available": False})
    assert response.status_code == 200
    assert response.json()["price_per_night"] == 5000
    db.refresh(room)
    assert (room.price_per_night, room.description, room.is_available) == (5000, VALID["description"], False)


@pytest.mark.parametrize(
    ("change", "message"),
    [
        ({"price_per_night": 0}, "Цена за ночь"),
        ({"price_per_night": -100}, "Цена за ночь"),
        ({"description": ""}, "Описание не может быть пустым"),
        ({"description": "   "}, "Описание не может быть пустым"),
        ({"description": "я" * 2001}, "не длиннее 2000"),
        ({"is_available": None}, ""),
    ],
)
def test_invalid_room_is_rejected(db: Session, admin_client: TestClient, change: dict[str, Any], message: str) -> None:
    room = standart(db)
    response = admin_client.patch(f"/api/admin/rooms/{room.id}", json={**VALID, **change})
    assert response.status_code == 422
    assert message in response.json()["detail"][0]["msg"]
    db.refresh(room)
    assert room.price_per_night == 4500


def test_unknown_room_is_404(admin_client: TestClient) -> None:
    assert admin_client.patch("/api/admin/rooms/9999", json=VALID).status_code == 404


def test_guest_and_anonymous_are_refused(db: Session, guest_client: TestClient, client: TestClient) -> None:
    room_id = standart(db).id
    assert guest_client.patch(f"/api/admin/rooms/{room_id}", json=VALID).status_code == 403
    assert guest_client.get("/api/admin/rooms").status_code == 403
    assert client.patch(f"/api/admin/rooms/{room_id}", json=VALID).status_code == 401
    assert db.get(Room, room_id).price_per_night == 4500  # type: ignore[union-attr]


def test_unavailable_room_keeps_bookings_but_refuses_new_ones(
    db: Session, admin_client: TestClient, guest: User, guest_client: TestClient
) -> None:
    room = standart(db)
    today = hotel_time.hotel_today()
    existing = Booking(
        user=guest,
        room=room,
        guest_name="Иван Петров",
        phone="+7 900 123-45-67",
        check_in=today + timedelta(days=10),
        check_out=today + timedelta(days=12),
        guests=1,
        status=BookingStatus.CONFIRMED,
        nights=2,
        price_per_night=4500,
        discount=0,
        total_price=9000,
    )
    db.add(existing)
    db.flush()

    assert admin_client.patch(f"/api/admin/rooms/{room.id}", json={**VALID, "is_available": False}).status_code == 200

    db.refresh(existing)
    assert existing.status == BookingStatus.CONFIRMED
    response = guest_client.post(
        "/api/bookings",
        json={
            "room_id": room.id,
            "guest_name": "Иван Петров",
            "phone": "+7 900 123-45-67",
            "check_in": str(today + timedelta(days=20)),
            "check_out": str(today + timedelta(days=22)),
            "guests": 1,
        },
    )
    assert response.status_code == 400
