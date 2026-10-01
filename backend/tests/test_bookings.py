from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta
from itertools import product

import pytest
from fastapi import BackgroundTasks, HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import hotel_time, mail
from app.booking_lifecycle import change_status
from app.booking_rules import REASON_TEXTS, Reason
from app.models import Actor, Booking, BookingEvent, BookingStatus, CrmStatus, Room, User
from app.routers import bookings as bookings_router
from conftest import login

# Часы отеля в тестах стоят на полудне 1 октября 2026 года по Москве; все даты считаются от них.
NOW = datetime(2026, 10, 1, 12, 0, tzinfo=hotel_time.HOTEL_TZ)
STANDART_ID = 2  # порядок вставки в seed.ROOMS: «Стандарт», 4500 ₽ за ночь, до 2 гостей
HOTEL_PHONE = "+7 (4852) 30-14-70"

MakeBooking = Callable[..., Booking]
MakeUser = Callable[..., User]


def day(offset: int) -> date:
    return NOW.date() + timedelta(days=offset)


def set_clock(monkeypatch: pytest.MonkeyPatch, moment: datetime) -> None:
    monkeypatch.setattr(hotel_time, "hotel_now", lambda: moment)


@pytest.fixture(autouse=True)
def frozen_clock(monkeypatch: pytest.MonkeyPatch) -> None:
    set_clock(monkeypatch, NOW)


def booking_payload(start: int = 10, nights: int = 2, **overrides: object) -> dict[str, object]:
    """Заявка на «Стандарт»: заезд через start дней от «сегодня», nights ночей; overrides заменяют поля."""
    payload: dict[str, object] = {
        "room_id": STANDART_ID,
        "guest_name": "Иван Петров",
        "phone": "+7 900 123-45-67",
        "check_in": day(start).isoformat(),
        "check_out": day(start + nights).isoformat(),
        "guests": 2,
        "comment": None,
    }
    payload.update(overrides)
    return payload


def sent() -> list[tuple[str, str]]:
    return [(letter.to, letter.subject) for letter in mail.outbox]


def counts(db: Session) -> tuple[int | None, int | None]:
    return db.scalar(select(func.count(Booking.id))), db.scalar(select(func.count(BookingEvent.id)))


# --- Доступ и предварительные проверки -------------------------------------------------------------------------


def test_booking_requires_login(client: TestClient) -> None:
    assert client.post("/api/bookings", json=booking_payload()).status_code == 401


def test_unverified_user_gets_403(unverified_client: TestClient) -> None:
    response = unverified_client.post("/api/bookings", json=booking_payload())
    assert response.status_code == 403
    assert response.json()["detail"] == "Подтвердите email, чтобы бронировать номера"


@pytest.mark.parametrize(
    "overrides",
    [
        {"check_out": day(10).isoformat()},
        {"check_in": day(-1).isoformat(), "check_out": day(2).isoformat()},
        {"phone": "12345"},
        {"guests": 0},
        {"guest_name": "  "},
        {"check_in": day(366).isoformat(), "check_out": day(368).isoformat()},
        {"check_out": day(41).isoformat()},
    ],
    ids=[
        "check_out_not_after_check_in",
        "check_in_in_past",
        "short_phone",
        "zero_guests",
        "blank_name",
        "check_in_too_far_ahead",
        "stay_too_long",
    ],
)
def test_invalid_booking_returns_422(guest_client: TestClient, overrides: dict[str, object]) -> None:
    assert guest_client.post("/api/bookings", json=booking_payload(**overrides)).status_code == 422


@pytest.mark.parametrize(
    "overrides",
    [
        {"check_in": day(365).isoformat(), "check_out": day(367).isoformat()},
        {"check_out": day(40).isoformat()},
    ],
    ids=["check_in_exactly_365_days_ahead", "stay_exactly_30_nights"],
)
def test_booking_at_limit_boundary_is_accepted(guest_client: TestClient, overrides: dict[str, object]) -> None:
    assert guest_client.post("/api/bookings", json=booking_payload(**overrides)).status_code == 201


def test_booking_over_capacity_returns_400(guest_client: TestClient) -> None:
    response = guest_client.post("/api/bookings", json=booking_payload(guests=3))
    assert response.status_code == 400
    assert response.json()["detail"] == "Максимальное число гостей в номере — 2"


def test_booking_unknown_room_returns_404(guest_client: TestClient) -> None:
    assert guest_client.post("/api/bookings", json=booking_payload(room_id=999)).status_code == 404


def test_booking_unavailable_room_returns_400(guest_client: TestClient, db: Session) -> None:
    db.get_one(Room, STANDART_ID).is_available = False
    db.flush()
    assert guest_client.post("/api/bookings", json=booking_payload()).status_code == 400


def test_confirmed_dates_block_new_booking(guest_client: TestClient, make_user: MakeUser) -> None:
    assert guest_client.post("/api/bookings", json=booking_payload()).json()["status"] == "confirmed"
    make_user("second@example.com")
    second = login("second@example.com")

    overlapping = second.post("/api/bookings", json=booking_payload(start=11))
    assert overlapping.status_code == 409
    assert overlapping.json()["detail"] == "Номер уже занят на выбранные даты. Выберите другие даты или другой номер"

    same_day_turnover = second.post("/api/bookings", json=booking_payload(start=12))
    assert same_day_turnover.json()["status"] == "confirmed"


def test_pending_limit_returns_429(guest_client: TestClient) -> None:
    for offset in (10, 20, 30):
        response = guest_client.post("/api/bookings", json=booking_payload(start=offset, comment="Кроватка"))
        assert response.json()["status"] == "pending"

    response = guest_client.post("/api/bookings", json=booking_payload(start=40, comment="Кроватка"))
    assert response.status_code == 429


def test_expired_pending_do_not_count_towards_limit(guest_client: TestClient, make_booking: MakeBooking) -> None:
    for offset in (-3, -2, -1):
        make_booking(day(offset), day(offset + 5))

    response = guest_client.post("/api/bookings", json=booking_payload(comment="Кроватка"))
    assert response.status_code == 201

    statuses = sorted(item["status"] for item in guest_client.get("/api/account/bookings").json())
    assert statuses == ["declined", "declined", "declined", "pending"]


def test_booking_rate_limit(guest_client: TestClient) -> None:
    statuses = [
        guest_client.post("/api/bookings", json=booking_payload(start=10 + 3 * attempt)).status_code
        for attempt in range(6)
    ]
    assert statuses == [201] * 5 + [429]


# --- Авто-решения и письма -------------------------------------------------------------------------------------


def test_short_stay_is_confirmed_automatically_with_one_mail(guest_client: TestClient, guest: User) -> None:
    response = guest_client.post("/api/bookings", json=booking_payload(nights=2))
    assert response.status_code == 201
    body = response.json()
    assert (body["status"], body["display_status"]) == ("confirmed", "confirmed")
    assert body["reasons"] == [REASON_TEXTS[Reason.AUTO_OK]]
    assert (body["nights"], body["price_per_night"], body["discount"], body["total_price"]) == (2, 4500, 0, 9000)
    assert "reason_codes" not in body
    # Событие создания идёт в журнал без письма: гость получает одно письмо об итоге.
    assert sent() == [(guest.email, "Бронь подтверждена — Kivana")]

    events = guest_client.get(f"/api/account/bookings/{body['id']}").json()["events"]
    assert [(event["from_status"], event["to_status"], event["actor"]) for event in events] == [
        (None, "pending", "guest"),
        ("pending", "confirmed", "system"),
    ]


def test_long_stay_goes_to_review(guest_client: TestClient, guest: User) -> None:
    body = guest_client.post("/api/bookings", json=booking_payload(nights=10)).json()
    assert body["status"] == "pending"
    assert body["reasons"] == [REASON_TEXTS[Reason.LONG_STAY]]
    assert sent() == [(guest.email, "Заявка на рассмотрении — Kivana")]
    assert REASON_TEXTS[Reason.LONG_STAY] in mail.outbox[0].text


def test_review_notifies_admin_when_configured(guest_client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(bookings_router, "ADMIN_NOTIFY_EMAIL", "ops@kivana.ru")
    body = guest_client.post("/api/bookings", json=booking_payload(nights=10, comment="Поздний заезд")).json()
    assert body["reasons"] == [REASON_TEXTS[Reason.LONG_STAY], REASON_TEXTS[Reason.HAS_COMMENT]]

    [to_guest, to_admin] = mail.outbox
    assert to_guest.subject == "Заявка на рассмотрении — Kivana"
    assert to_admin.to == "ops@kivana.ru"
    assert all(reason in to_admin.text for reason in body["reasons"])


def test_blank_comment_does_not_trigger_review(guest_client: TestClient) -> None:
    body = guest_client.post("/api/bookings", json=booking_payload(comment="   ")).json()
    assert (body["comment"], body["status"]) == (None, "confirmed")


def test_blocked_client_is_declined_with_neutral_text(
    guest_client: TestClient, guest: User, admin_client: TestClient, db: Session
) -> None:
    guest.crm_status = CrmStatus.BLOCKED
    db.flush()

    response = guest_client.post("/api/bookings", json=booking_payload())
    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "declined"
    assert body["reasons"] == ["Не можем подтвердить бронирование онлайн — свяжитесь с отелем"]
    assert "reason_codes" not in body

    [declined] = mail.outbox
    assert declined.subject == "Бронь не подтверждена — Kivana"
    assert REASON_TEXTS[Reason.CLIENT_BLOCKED] in declined.text
    assert "блок" not in (declined.text + declined.html).lower()

    # Код причины и CRM-статус видит только администратор.
    admin_view = admin_client.get(f"/api/admin/bookings/{body['id']}").json()["booking"]
    assert admin_view["reason_codes"] == ["client_blocked"]
    assert admin_view["user"]["crm_status"] == "blocked"


def test_check_in_today_uses_hotel_time_zone(guest_client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    # 21:30 UTC 30 сентября — в Москве уже 00:30 1 октября: «сегодня» для отеля — 1 октября.
    set_clock(monkeypatch, datetime(2026, 9, 30, 21, 30, tzinfo=UTC).astimezone(hotel_time.HOTEL_TZ))

    today = guest_client.post("/api/bookings", json=booking_payload(check_in="2026-10-01", check_out="2026-10-03"))
    assert today.json()["status"] == "pending"
    assert today.json()["reasons"] == [REASON_TEXTS[Reason.SAME_DAY]]

    yesterday = guest_client.post("/api/bookings", json=booking_payload(check_in="2026-09-30", check_out="2026-10-02"))
    assert yesterday.status_code == 422


# --- Гонки и связанные заявки ----------------------------------------------------------------------------------
# Настоящую конкурентность гарантирует EXCLUDE bookings_no_overlap; тесты эмулируют проигравший запрос:
# подтверждённая бронь на те же даты появляется в базе в обход предварительных проверок.


def test_auto_confirm_race_returns_409_without_partial_data(
    guest_client: TestClient,
    make_booking: MakeBooking,
    make_user: MakeUser,
    monkeypatch: pytest.MonkeyPatch,
    db: Session,
) -> None:
    make_booking(day(10), day(12), status=BookingStatus.CONFIRMED, user=make_user("rival@example.com"))
    # Подготовка фиксируется: откат внутри запроса не должен её задеть, как и в настоящей гонке.
    db.commit()
    # Предварительная проверка «не увидела» соседнюю бронь — как если бы та подтвердилась мгновением позже.
    monkeypatch.setattr(bookings_router, "dates_taken", lambda *args: False)
    before = counts(db)

    response = guest_client.post("/api/bookings", json=booking_payload())

    assert response.status_code == 409
    assert response.json()["detail"] == "Эти даты только что заняли — выберите другие"
    assert counts(db) == before
    assert mail.outbox == []


def test_admin_confirm_race_returns_409_and_keeps_booking_pending(
    admin_client: TestClient, make_booking: MakeBooking, make_user: MakeUser, db: Session
) -> None:
    pending = make_booking(day(10), day(12))
    make_booking(day(11), day(13), status=BookingStatus.CONFIRMED, user=make_user("rival@example.com"))
    db.commit()
    before = counts(db)

    response = admin_client.post(f"/api/admin/bookings/{pending.id}/confirm", json={})

    assert response.status_code == 409
    assert response.json()["detail"] == "Эти даты только что заняли — выберите другие"
    assert admin_client.get(f"/api/admin/bookings/{pending.id}").json()["booking"]["status"] == "pending"
    assert counts(db) == before
    assert mail.outbox == []


def test_admin_confirm_declines_overlapping_pending(
    guest_client: TestClient, guest: User, admin_client: TestClient, make_user: MakeUser
) -> None:
    first = guest_client.post("/api/bookings", json=booking_payload(comment="Ранний заезд")).json()
    make_user("second@example.com")
    second = login("second@example.com").post("/api/bookings", json=booking_payload(start=11)).json()
    assert second["reasons"] == [REASON_TEXTS[Reason.PENDING_CONFLICT]]
    mail.outbox.clear()

    response = admin_client.post(
        f"/api/admin/bookings/{first['id']}/confirm", json={"reason": "Ранний заезд согласовали"}
    )
    assert response.status_code == 200
    assert response.json()["status"] == "confirmed"

    declined = admin_client.get(f"/api/admin/bookings/{second['id']}").json()
    assert declined["booking"]["status"] == "declined"
    assert declined["booking"]["reason_codes"] == ["dates_taken"]
    assert declined["events"][-1]["actor"] == "system"
    assert sorted(sent()) == [
        ("guest@example.com", "Бронь подтверждена — Kivana"),
        ("second@example.com", "Бронь не подтверждена — Kivana"),
    ]

    # Гость видит решение администратора в таймлайне вместе с причиной.
    timeline = guest_client.get(f"/api/account/bookings/{first['id']}").json()["events"]
    assert timeline[-1]["actor"] == "admin"
    assert timeline[-1]["reasons"] == ["Ранний заезд согласовали"]


# --- Отмена ----------------------------------------------------------------------------------------------------


def test_guest_cancels_pending_any_time(guest_client: TestClient, guest: User, make_booking: MakeBooking) -> None:
    pending = make_booking(day(1), day(3))

    response = guest_client.post(f"/api/account/bookings/{pending.id}/cancel")

    assert response.status_code == 200
    detail = response.json()
    assert (detail["booking"]["status"], detail["can_cancel"]) == ("cancelled", False)
    assert [(event["from_status"], event["actor"]) for event in detail["events"]] == [("pending", "guest")]
    assert sent() == [(guest.email, "Бронь отменена — Kivana")]


@pytest.mark.parametrize(
    ("shift", "expected_status"),
    [(timedelta(minutes=-1), 200), (timedelta(0), 409), (timedelta(minutes=1), 409)],
    ids=["minute_before_deadline", "exactly_at_deadline", "minute_after_deadline"],
)
def test_guest_cancel_deadline_boundary(
    guest_client: TestClient,
    make_booking: MakeBooking,
    monkeypatch: pytest.MonkeyPatch,
    shift: timedelta,
    expected_status: int,
) -> None:
    booking = make_booking(day(10), day(12), status=BookingStatus.CONFIRMED)
    # Заезд 11 октября в 14:00 по Москве (время заезда отеля) минус 48 часов.
    deadline = datetime(2026, 10, 9, 14, 0, tzinfo=hotel_time.HOTEL_TZ)
    set_clock(monkeypatch, deadline + shift)

    detail = guest_client.get(f"/api/account/bookings/{booking.id}").json()
    assert datetime.fromisoformat(detail["cancel_deadline"]) == deadline
    assert detail["can_cancel"] is (expected_status == 200)

    response = guest_client.post(f"/api/account/bookings/{booking.id}/cancel")
    assert response.status_code == expected_status
    if expected_status == 409:
        assert response.json()["detail"] == (
            f"Отмена онлайн недоступна менее чем за 48 ч до заезда — позвоните нам: {HOTEL_PHONE}"
        )


def test_cancelled_booking_frees_dates(guest_client: TestClient, client: TestClient) -> None:
    booking = guest_client.post("/api/bookings", json=booking_payload()).json()
    params = {"check_in": day(10).isoformat(), "check_out": day(12).isoformat(), "guests": 2}
    assert client.get("/api/rooms/standart/quote", params=params).json()["available"] is False

    assert guest_client.post(f"/api/account/bookings/{booking['id']}/cancel").status_code == 200
    assert client.get("/api/rooms/standart/quote", params=params).json()["available"] is True


@pytest.mark.parametrize("action", ["decline", "cancel"])
def test_admin_decline_and_cancel_require_reason(
    admin_client: TestClient, make_booking: MakeBooking, action: str
) -> None:
    booking = make_booking(day(10), day(12))
    assert admin_client.post(f"/api/admin/bookings/{booking.id}/{action}", json={}).status_code == 422
    assert admin_client.post(f"/api/admin/bookings/{booking.id}/{action}", json={"reason": "  "}).status_code == 422


def test_admin_cancel_reason_reaches_guest(admin_client: TestClient, make_booking: MakeBooking) -> None:
    booking = make_booking(day(10), day(12), status=BookingStatus.CONFIRMED)

    response = admin_client.post(f"/api/admin/bookings/{booking.id}/cancel", json={"reason": "Ремонт в номере"})

    assert response.status_code == 200
    body = response.json()
    assert (body["status"], body["cancelled_by"], body["reasons"]) == ("cancelled", "admin", ["Ремонт в номере"])
    [cancelled] = mail.outbox
    assert cancelled.subject == "Бронь отменена — Kivana"
    assert "Ремонт в номере" in cancelled.text


def test_admin_cancels_during_stay_but_not_after_check_out(
    admin_client: TestClient, make_booking: MakeBooking
) -> None:
    in_stay = make_booking(day(-1), day(2), status=BookingStatus.CONFIRMED)
    completed = make_booking(day(-5), day(-2), status=BookingStatus.CONFIRMED)

    early_leave = admin_client.post(f"/api/admin/bookings/{in_stay.id}/cancel", json={"reason": "Ранний выезд"})
    assert early_leave.status_code == 200
    response = admin_client.post(f"/api/admin/bookings/{completed.id}/cancel", json={"reason": "Ошибка"})
    assert response.status_code == 409
    assert response.json()["detail"] == "Проживание уже закончилось — отменить бронь нельзя"


# --- Просрочка, кабинет, админка, котировка --------------------------------------------------------------------


def test_stale_pending_expires_lazily_and_once(
    admin_client: TestClient, guest: User, make_booking: MakeBooking, db: Session
) -> None:
    stale = make_booking(day(-1), day(2))
    today = make_booking(day(0), day(2))

    page = admin_client.get("/api/admin/bookings", params={"status": "declined"}).json()
    assert [item["id"] for item in page["items"]] == [stale.id]
    assert page["items"][0]["reason_codes"] == ["expired"]
    assert sent() == [(guest.email, "Бронь не подтверждена — Kivana")]

    admin_client.get("/api/admin/bookings")
    events = db.scalars(select(BookingEvent).where(BookingEvent.booking_id == stale.id)).all()
    assert [(event.to_status, event.actor) for event in events] == [("declined", "system")]
    assert len(mail.outbox) == 1
    assert admin_client.get(f"/api/admin/bookings/{today.id}").json()["booking"]["status"] == "pending"


def test_account_list_shows_computed_statuses(guest_client: TestClient, make_booking: MakeBooking) -> None:
    make_booking(day(-1), day(2), status=BookingStatus.CONFIRMED)
    make_booking(day(-5), day(-2), status=BookingStatus.CONFIRMED)
    make_booking(day(10), day(12), status=BookingStatus.CONFIRMED)

    items = guest_client.get("/api/account/bookings").json()

    assert [item["display_status"] for item in items] == ["confirmed", "in_stay", "completed"]


def test_foreign_booking_is_404(
    guest_client: TestClient, make_booking: MakeBooking, make_user: MakeUser, db: Session
) -> None:
    foreign = make_booking(day(10), day(12), user=make_user("stranger@example.com"))

    assert guest_client.get(f"/api/account/bookings/{foreign.id}").status_code == 404
    assert guest_client.post(f"/api/account/bookings/{foreign.id}/cancel").status_code == 404
    db.refresh(foreign)
    assert foreign.status == BookingStatus.PENDING


def test_admin_review_queue_is_sorted_by_check_in(admin_client: TestClient, make_booking: MakeBooking) -> None:
    later = make_booking(day(20), day(22))
    sooner = make_booking(day(5), day(7))
    make_booking(day(30), day(32), status=BookingStatus.CONFIRMED)

    pending = admin_client.get("/api/admin/bookings", params={"status": "pending"}).json()
    assert pending["total"] == 2
    assert [item["id"] for item in pending["items"]] == [sooner.id, later.id]
    assert pending["items"][0]["user"]["email"] == "guest@example.com"

    second_page = admin_client.get("/api/admin/bookings", params={"limit": 1, "offset": 1}).json()
    assert (second_page["total"], len(second_page["items"])) == (3, 1)


def test_quote_counts_price_and_availability(client: TestClient, make_booking: MakeBooking) -> None:
    params = {"check_in": day(10).isoformat(), "check_out": day(13).isoformat(), "guests": 2}
    assert client.get("/api/rooms/standart/quote", params=params).json() == {
        "available": True,
        "unavailable_reason": None,
        "nights": 3,
        "price_per_night": 4500,
        "subtotal": 13500,
        "discount": 0,
        "total": 13500,
    }

    make_booking(day(11), day(12), status=BookingStatus.CONFIRMED)
    taken = client.get("/api/rooms/standart/quote", params=params).json()
    assert (taken["available"], taken["unavailable_reason"]) == (False, "Номер уже занят на выбранные даты")

    crowded = client.get("/api/rooms/standart/quote", params={**params, "guests": 3}).json()
    assert crowded["unavailable_reason"] == "Максимальное число гостей в номере — 2"
    assert client.get("/api/rooms/standart/quote", params={**params, "check_out": day(10)}).status_code == 422


# --- Матрица переходов -----------------------------------------------------------------------------------------

ALLOWED = {
    (BookingStatus.PENDING, BookingStatus.CONFIRMED, Actor.SYSTEM),
    (BookingStatus.PENDING, BookingStatus.CONFIRMED, Actor.ADMIN),
    (BookingStatus.PENDING, BookingStatus.DECLINED, Actor.SYSTEM),
    (BookingStatus.PENDING, BookingStatus.DECLINED, Actor.ADMIN),
    (BookingStatus.PENDING, BookingStatus.CANCELLED, Actor.GUEST),
    (BookingStatus.PENDING, BookingStatus.CANCELLED, Actor.ADMIN),
    (BookingStatus.CONFIRMED, BookingStatus.CANCELLED, Actor.GUEST),
    (BookingStatus.CONFIRMED, BookingStatus.CANCELLED, Actor.ADMIN),
}


@pytest.mark.parametrize(("from_status", "to_status", "actor"), list(product(BookingStatus, BookingStatus, Actor)))
def test_transition_matrix(
    db: Session,
    make_booking: MakeBooking,
    from_status: BookingStatus,
    to_status: BookingStatus,
    actor: Actor,
) -> None:
    booking = make_booking(day(30), day(32), status=from_status)

    if (from_status, to_status, actor) in ALLOWED:
        change_status(db, booking, to_status, actor, BackgroundTasks())
        assert booking.status == to_status
        assert [(event.from_status, event.to_status, event.actor) for event in booking.events] == [
            (from_status, to_status, actor)
        ]
    else:
        with pytest.raises(HTTPException) as rejected:
            change_status(db, booking, to_status, actor, BackgroundTasks())
        assert rejected.value.status_code == 409
        assert booking.status == from_status
        assert booking.events == []
