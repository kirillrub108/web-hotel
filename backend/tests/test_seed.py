import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

import seed
from app import hotel_time, mail
from app.database import Base
from app.models import (
    Booking,
    BookingEvent,
    BookingStatus,
    CrmStatus,
    HousekeepingTask,
    OrderStatus,
    Promo,
    Room,
    ServiceOrder,
    User,
)
from app.passwords import check_password


def row_counts(db: Session) -> dict[str, int]:
    return {
        table.name: db.scalar(select(func.count()).select_from(table)) or 0 for table in Base.metadata.sorted_tables
    }


@pytest.fixture
def demo(db: Session) -> dict[str, int]:
    """Демо-данные в тестовой транзакции; возвращает число записей после первого запуска."""
    seed.seed_demo(db)
    return row_counts(db)


def test_demo_seed_twice_changes_nothing(db: Session, demo: dict[str, int]) -> None:
    baseline = row_counts(db)
    assert baseline["users"] > 0 and baseline["bookings"] > 0

    seed.seed_demo(db)

    assert row_counts(db) == baseline


def test_whole_seed_twice_changes_nothing(db: Session, demo: dict[str, int]) -> None:
    seed.seed_reference_data(db)
    seed.create_admin(db, seed.ADMIN_EMAIL, seed.ADMIN_PASSWORD)
    seed.seed_demo(db)

    assert row_counts(db) == demo


def test_test_database_has_no_demo_by_default(db: Session) -> None:
    assert not seed.SEED_DEMO
    assert db.scalar(select(func.count(User.id)).where(User.email.like(f"%{seed.DEMO_EMAIL_DOMAIN}"))) == 0


def test_every_booking_has_events(db: Session, demo: dict[str, int]) -> None:
    without_events = db.scalars(
        select(Booking.id).where(~select(BookingEvent.id).where(BookingEvent.booking_id == Booking.id).exists())
    ).all()
    assert without_events == []


def test_current_stay_has_housekeeping_and_orders(db: Session, demo: dict[str, int]) -> None:
    today = hotel_time.hotel_today()
    current = db.scalars(
        select(Booking).where(
            Booking.status == BookingStatus.CONFIRMED, Booking.check_in < today, Booking.check_out > today
        )
    ).all()
    assert len(current) == 1
    tasks = db.scalars(select(HousekeepingTask).where(HousekeepingTask.booking_id == current[0].id)).all()
    assert {task.status for task in tasks} == {"done", "planned"}
    orders = db.scalars(select(ServiceOrder).where(ServiceOrder.booking_id == current[0].id)).all()
    assert {order.status for order in orders} == {OrderStatus.NEW, OrderStatus.ACCEPTED, OrderStatus.DONE}


def test_confirmed_bookings_do_not_overlap(db: Session, demo: dict[str, int]) -> None:
    confirmed = db.scalars(select(Booking).where(Booking.status == BookingStatus.CONFIRMED)).all()
    assert len(confirmed) >= 5
    for first in confirmed:
        for second in confirmed:
            if first.id < second.id and first.room_id == second.room_id:
                assert first.check_out <= second.check_in or second.check_out <= first.check_in


def test_demo_covers_every_scenario(db: Session, demo: dict[str, int]) -> None:
    bookings = list(db.scalars(select(Booking)).all())
    today = hotel_time.hotel_today()

    pending = [b for b in bookings if b.status == BookingStatus.PENDING]
    assert [set(b.reason_codes) for b in pending] == [{"long_stay", "has_comment"}]

    declined = [b for b in bookings if b.status == BookingStatus.DECLINED]
    assert [b.reason_codes for b in declined] == [["client_blocked"]]
    assert declined[0].user.crm_status == CrmStatus.BLOCKED

    cancelled = [b for b in bookings if b.status == BookingStatus.CANCELLED]
    assert [b.cancelled_by for b in cancelled] == ["guest"]

    vip = [b for b in bookings if b.user.crm_status == CrmStatus.VIP and b.status == BookingStatus.CONFIRMED]
    assert any(b.check_out <= today for b in vip) and any(b.check_in > today for b in vip)

    assert any(b.status == BookingStatus.CONFIRMED and b.check_out <= today for b in bookings)
    assert any(b.status == BookingStatus.CONFIRMED and b.check_in > today for b in bookings)
    assert sum(b.promo_id is not None for b in bookings) == 1

    promos = db.scalars(select(Promo)).all()
    assert sum(promo.user_id is not None for promo in promos) == 3
    assert sum(promo.user_id is None for promo in promos) == 1


def test_demo_clients(db: Session, demo: dict[str, int]) -> None:
    clients = db.scalars(select(User).where(User.email.like(f"%{seed.DEMO_EMAIL_DOMAIN}"))).all()
    assert 3 <= len(clients) <= 4
    assert all(client.email_verified_at is not None for client in clients)
    assert sum(client.crm_note is not None for client in clients) >= 2
    assert {client.crm_status for client in clients} >= {CrmStatus.VIP, CrmStatus.BLOCKED}


def test_demo_password_passes_policy_and_logs_in(db: Session, demo: dict[str, int], client: TestClient) -> None:
    assert check_password(seed.DEMO_PASSWORD, email=f"anna{seed.DEMO_EMAIL_DOMAIN}", full_name="Анна Лебедева") is None
    response = client.post(
        "/api/auth/login", json={"email": f"anna{seed.DEMO_EMAIL_DOMAIN}", "password": seed.DEMO_PASSWORD}
    )
    assert response.status_code == 200


def test_demo_sends_no_mail(db: Session, demo: dict[str, int]) -> None:
    assert mail.outbox == []


def test_seed_keeps_admin_edits_of_rooms(db: Session) -> None:
    room = db.scalars(select(Room).where(Room.slug == "econom")).one()
    room.price_per_night = 3300
    room.is_available = False
    db.flush()

    seed.seed_rooms(db)

    db.refresh(room)
    assert room.price_per_night == 3300 and room.is_available is False
