from collections.abc import Callable

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session
from test_bookings import NOW, MakeUser, booking_payload, day, set_clock

from app.booking_rules import calculate_price, promo_discount
from app.models import Booking, Promo, PromoKind, Room, User
from conftest import login

MakePromo = Callable[..., Promo]
QUOTE = "/api/rooms/standart/quote"
# Стандарт стоит 4500 ₽ за ночь: 3 ночи = 13 500 ₽, 10% = 1 350 ₽.
STAY = {"check_in": day(10).isoformat(), "check_out": day(13).isoformat(), "guests": 2}


@pytest.fixture(autouse=True)
def frozen_clock(monkeypatch: pytest.MonkeyPatch) -> None:
    set_clock(monkeypatch, NOW)


@pytest.fixture
def make_promo(db: Session) -> MakePromo:
    def create(code: str = "TEN", **fields: object) -> Promo:
        values: dict[str, object] = {
            "code": code,
            "title": "Скидка 10%",
            "description": "",
            "kind": PromoKind.PERCENT,
            "value": 10,
            "valid_from": day(-5),
            "valid_to": day(60),
            "min_nights": 1,
        }
        values.update(fields)
        promo = Promo(**values)
        db.add(promo)
        db.flush()
        return promo

    return create


def quote(client: TestClient, code: str | None, **stay: object) -> dict[str, object]:
    response = client.get(QUOTE, params={**STAY, **stay, **({"promo_code": code} if code else {})})
    return {"status": response.status_code, **response.json()}


# --- Расчёт скидки и потолки ------------------------------------------------------------------------------------


def terms(kind: PromoKind, value: int) -> Promo:
    """Акция без базы: для расчёта скидки нужны только вид и значение."""
    return Promo(kind=kind, value=value)


def test_percent_discount_is_counted_from_stay_cost() -> None:
    price = calculate_price(4500, day(10), day(13), terms(PromoKind.PERCENT, 10))
    assert (price.subtotal, price.discount, price.total) == (13500, 1350, 12150)


def test_without_promo_there_is_no_discount() -> None:
    price = calculate_price(4500, day(10), day(13))
    assert (price.discount, price.total) == (0, 13500)


def test_percent_discount_is_capped_at_half() -> None:
    # Акция «−80%» даёт не больше 50% от стоимости проживания.
    assert promo_discount(terms(PromoKind.PERCENT, 80), 10000) == 5000
    assert promo_discount(terms(PromoKind.PERCENT, 50), 10000) == 5000
    assert promo_discount(terms(PromoKind.PERCENT, 51), 10001) == 5000


def test_fixed_discount_is_capped_at_stay_cost() -> None:
    assert promo_discount(terms(PromoKind.FIXED, 20000), 9000) == 9000
    assert promo_discount(terms(PromoKind.FIXED, 500), 9000) == 500


def test_caps_apply_in_quote_and_booking(guest_client: TestClient, make_promo: MakePromo) -> None:
    make_promo("HALF", value=90)
    got = quote(guest_client, "HALF")
    assert (got["discount"], got["total"]) == (6750, 6750)

    created = guest_client.post("/api/bookings", json=booking_payload(nights=3, promo_code="HALF"))
    assert created.status_code == 201
    assert (created.json()["discount"], created.json()["total_price"]) == (6750, 6750)


def test_quote_shows_discount_and_promo_title(guest_client: TestClient, make_promo: MakePromo) -> None:
    make_promo()
    got = quote(guest_client, "TEN")
    assert (got["status"], got["subtotal"], got["discount"], got["total"]) == (200, 13500, 1350, 12150)
    assert got["promo_title"] == "Скидка 10%"


def test_code_is_case_and_space_insensitive(guest_client: TestClient, make_promo: MakePromo) -> None:
    make_promo("SUMMER-10")
    assert quote(guest_client, "  summer-10 ")["discount"] == 1350


# --- Причины отказа: по тесту на каждую -------------------------------------------------------------------------


def refusal(client: TestClient, code: str = "TEN", **stay: object) -> str:
    got = quote(client, code, **stay)
    assert got["status"] == 400
    return str(got["detail"])


def test_unknown_code(guest_client: TestClient) -> None:
    assert refusal(guest_client, "NOPE") == "Промокод не найден"


def test_inactive_promo(guest_client: TestClient, make_promo: MakePromo) -> None:
    make_promo(is_active=False)
    assert refusal(guest_client) == "Акция больше не действует"


def test_promo_not_started_yet(guest_client: TestClient, make_promo: MakePromo) -> None:
    make_promo(valid_from=day(3), valid_to=day(30))
    assert refusal(guest_client) == f"Акция начнётся {day(3):%d.%m.%Y}"


def test_promo_expired_in_the_past(guest_client: TestClient, make_promo: MakePromo) -> None:
    make_promo(valid_from=day(-30), valid_to=day(-1))
    assert refusal(guest_client) == f"Срок действия промокода истёк {day(-1):%d.%m.%Y}"


def test_validity_is_checked_on_request_date_not_on_check_in(guest_client: TestClient, make_promo: MakePromo) -> None:
    # Акция действует сегодня, а заезд уже после её окончания — всё равно применима: считается дата заявки.
    make_promo(valid_from=day(-1), valid_to=day(2))
    assert quote(guest_client, "TEN")["discount"] == 1350


def test_validity_bounds_are_inclusive(guest_client: TestClient, make_promo: MakePromo) -> None:
    make_promo("FIRST", valid_from=day(0), valid_to=day(0))
    assert quote(guest_client, "FIRST")["status"] == 200


def test_min_nights(guest_client: TestClient, make_promo: MakePromo) -> None:
    make_promo(min_nights=4)
    assert refusal(guest_client) == "Минимум ночей для этого промокода: 4"
    assert quote(guest_client, "TEN", check_out=day(14).isoformat())["status"] == 200


def test_room_restriction(guest_client: TestClient, db: Session, make_promo: MakePromo) -> None:
    lux = db.scalars(select(Room).where(Room.slug == "lyuks")).one()
    make_promo(room_id=lux.id)
    assert refusal(guest_client) == "Промокод действует только для другого номера"
    own = guest_client.get("/api/rooms/lyuks/quote", params={**STAY, "promo_code": "TEN"})
    assert own.status_code == 200


def test_foreign_personal_code_is_refused(guest_client: TestClient, make_user: MakeUser, make_promo: MakePromo) -> None:
    other = make_user("other@example.com")
    make_promo(user_id=other.id)
    assert refusal(guest_client) == "Этот промокод недоступен для вашего аккаунта"
    created = guest_client.post("/api/bookings", json=booking_payload(promo_code="TEN"))
    assert created.status_code == 400
    assert created.json()["detail"] == "Этот промокод недоступен для вашего аккаунта"


def test_personal_code_needs_login(client: TestClient, guest: User, make_promo: MakePromo) -> None:
    make_promo(user_id=guest.id)
    assert refusal(client) == "Этот промокод недоступен для вашего аккаунта"


def test_own_personal_code_works(guest_client: TestClient, guest: User, make_promo: MakePromo) -> None:
    make_promo(user_id=guest.id)
    assert quote(guest_client, "TEN")["discount"] == 1350


def test_general_code_works_for_everyone(client: TestClient, guest_client: TestClient, make_promo: MakePromo) -> None:
    make_promo()
    assert quote(client, "TEN")["discount"] == 1350
    created = guest_client.post("/api/bookings", json=booking_payload(nights=3, promo_code="TEN"))
    assert created.status_code == 201
    assert created.json()["promo"] == {"code": "TEN", "title": "Скидка 10%"}


def test_refused_code_creates_no_booking(guest_client: TestClient, db: Session) -> None:
    response = guest_client.post("/api/bookings", json=booking_payload(promo_code="NOPE"))
    assert response.status_code == 400
    assert response.json()["detail"] == "Промокод не найден"
    assert db.scalars(select(Booking)).all() == []


# --- Одноразовость ----------------------------------------------------------------------------------------------


def book(client: TestClient, code: str = "TEN", start: int = 10) -> dict[str, object]:
    response = client.post("/api/bookings", json=booking_payload(start=start, nights=3, promo_code=code))
    return {"status_code": response.status_code, **response.json()}


def test_code_is_single_use_while_booking_holds_it(
    guest_client: TestClient, make_user: MakeUser, make_promo: MakePromo
) -> None:
    make_promo()
    first = book(guest_client)
    assert (first["status_code"], first["status"]) == (201, "confirmed")

    other_client = login(make_user("other@example.com").email)
    second = book(other_client, start=20)
    assert second["status_code"] == 400
    assert second["detail"] == "Этот промокод уже использован в другой брони"
    assert refusal(other_client) == "Этот промокод уже использован в другой брони"


def test_pending_booking_also_holds_the_code(
    guest_client: TestClient, make_user: MakeUser, make_promo: MakePromo
) -> None:
    make_promo()
    pending = guest_client.post(
        "/api/bookings", json=booking_payload(nights=3, promo_code="TEN", comment="Нужна детская кроватка")
    )
    assert pending.json()["status"] == "pending"
    assert refusal(login(make_user("other@example.com").email)) == "Этот промокод уже использован в другой брони"


def test_cancel_frees_the_code(guest_client: TestClient, make_user: MakeUser, make_promo: MakePromo) -> None:
    make_promo()
    first = book(guest_client)
    other_client = login(make_user("other@example.com").email)
    assert refusal(other_client) == "Этот промокод уже использован в другой брони"

    cancelled = guest_client.post(f"/api/account/bookings/{first['id']}/cancel")
    assert cancelled.status_code == 200
    assert quote(other_client, "TEN")["discount"] == 1350
    assert book(other_client, start=20)["status_code"] == 201


def test_decline_frees_the_code(
    guest_client: TestClient, admin_client: TestClient, make_user: MakeUser, make_promo: MakePromo
) -> None:
    make_promo()
    pending = guest_client.post(
        "/api/bookings", json=booking_payload(nights=3, promo_code="TEN", comment="Ранний заезд")
    ).json()
    declined = admin_client.post(f"/api/admin/bookings/{pending['id']}/decline", json={"reason": "Номер на ремонте"})
    assert declined.status_code == 200

    other_client = login(make_user("other@example.com").email)
    assert quote(other_client, "TEN")["discount"] == 1350


def test_same_guest_cannot_reuse_code_in_second_booking(guest_client: TestClient, make_promo: MakePromo) -> None:
    make_promo()
    assert book(guest_client)["status_code"] == 201
    assert book(guest_client, start=30)["status_code"] == 400


# --- Снимок в брони ---------------------------------------------------------------------------------------------


def test_booking_keeps_discount_snapshot(guest_client: TestClient, db: Session, make_promo: MakePromo) -> None:
    promo = make_promo()
    booking = book(guest_client)
    assert (booking["nights"], booking["price_per_night"], booking["discount"], booking["total_price"]) == (
        3,
        4500,
        1350,
        12150,
    )

    promo.value = 30
    db.flush()
    again = guest_client.get(f"/api/account/bookings/{booking['id']}").json()["booking"]
    assert (again["discount"], again["total_price"]) == (1350, 12150)


def test_deactivating_promo_does_not_touch_pending_booking(
    guest_client: TestClient, admin_client: TestClient, make_promo: MakePromo
) -> None:
    promo = make_promo()
    pending = guest_client.post(
        "/api/bookings", json=booking_payload(nights=3, promo_code="TEN", comment="Парковка")
    ).json()

    body = {
        "code": "TEN", "title": "Скидка 10%", "description": "", "kind": "percent", "value": 10,
        "valid_from": day(-5).isoformat(), "valid_to": day(60).isoformat(), "min_nights": 1,
        "room_id": None, "user_id": None, "is_active": False,
    }  # fmt: skip
    response = admin_client.patch(f"/api/admin/promos/{promo.id}", json=body)
    assert response.status_code == 200
    assert (response.json()["is_active"], response.json()["in_use"]) == (False, True)

    after = guest_client.get(f"/api/account/bookings/{pending['id']}").json()["booking"]
    assert (after["status"], after["discount"], after["total_price"]) == ("pending", 1350, 12150)


# --- Кабинет: персональные предложения --------------------------------------------------------------------------


def test_account_promos_lists_own_and_general_active_unused(
    guest_client: TestClient, guest: User, make_user: MakeUser, make_promo: MakePromo
) -> None:
    other = make_user("other@example.com")
    make_promo("GENERAL", title="Общая")
    make_promo("MINE", title="Моя", user_id=guest.id, valid_to=day(5))
    make_promo("THEIRS", user_id=other.id)
    make_promo("OFF", is_active=False)
    make_promo("OLD", valid_from=day(-30), valid_to=day(-1))
    make_promo("FUTURE", valid_from=day(2), valid_to=day(9))

    offers = guest_client.get("/api/account/promos").json()
    assert [offer["code"] for offer in offers] == ["MINE", "GENERAL"]
    assert [offer["is_personal"] for offer in offers] == [True, False]
    assert offers[0]["valid_to"] == day(5).isoformat()
    assert "user_id" not in offers[0]


def test_account_promos_hides_used_code(guest_client: TestClient, make_promo: MakePromo) -> None:
    make_promo()
    book(guest_client)
    assert guest_client.get("/api/account/promos").json() == []


def test_account_promos_empty_and_needs_login(client: TestClient, guest_client: TestClient) -> None:
    assert guest_client.get("/api/account/promos").json() == []
    assert client.get("/api/account/promos").status_code == 401


# --- Админка акций ----------------------------------------------------------------------------------------------


def promo_body(**overrides: object) -> dict[str, object]:
    body: dict[str, object] = {
        "code": "welcome15",
        "title": "Приветственная скидка",
        "description": "Для новых гостей",
        "kind": "percent",
        "value": 15,
        "valid_from": day(0).isoformat(),
        "valid_to": day(30).isoformat(),
        "min_nights": 2,
        "room_id": None,
        "user_id": None,
        "is_active": True,
    }
    body.update(overrides)
    return body


def test_admin_creates_general_promo(admin_client: TestClient) -> None:
    response = admin_client.post("/api/admin/promos", json=promo_body())
    assert response.status_code == 201
    created = response.json()
    assert (created["code"], created["is_personal"], created["in_use"], created["bookings_count"]) == (
        "WELCOME15",
        False,
        False,
        0,
    )
    assert admin_client.get("/api/admin/promos").json()[0]["code"] == "WELCOME15"


def test_admin_issues_personal_promo_and_guest_sees_it(
    admin_client: TestClient, guest_client: TestClient, guest: User
) -> None:
    body = promo_body(code="VIP10", title="Личная скидка 10%", value=10, user_id=guest.id)
    created = admin_client.post("/api/admin/promos", json=body)
    assert created.status_code == 201
    assert created.json()["is_personal"] is True
    assert created.json()["user"]["email"] == guest.email

    offers = guest_client.get("/api/account/promos").json()
    assert [offer["code"] for offer in offers] == ["VIP10"]

    booking = guest_client.post("/api/bookings", json=booking_payload(nights=3, promo_code="VIP10")).json()
    assert (booking["discount"], booking["total_price"]) == (1350, 12150)
    assert guest_client.get("/api/account/promos").json() == []

    guest_client.post(f"/api/account/bookings/{booking['id']}/cancel")
    assert [offer["code"] for offer in guest_client.get("/api/account/promos").json()] == ["VIP10"]


def test_admin_promo_filter_by_kind(admin_client: TestClient, guest: User) -> None:
    admin_client.post("/api/admin/promos", json=promo_body(code="GEN"))
    admin_client.post("/api/admin/promos", json=promo_body(code="PERS", user_id=guest.id))

    def codes(personal: bool) -> list[str]:
        response = admin_client.get("/api/admin/promos", params={"personal": personal})
        return [promo["code"] for promo in response.json()]

    assert codes(True) == ["PERS"]
    assert codes(False) == ["GEN"]


def test_admin_promos_empty_list(admin_client: TestClient) -> None:
    assert admin_client.get("/api/admin/promos").json() == []


def test_duplicate_code_is_conflict(admin_client: TestClient) -> None:
    admin_client.post("/api/admin/promos", json=promo_body())
    response = admin_client.post("/api/admin/promos", json=promo_body(code="WELCOME15"))
    assert response.status_code == 409
    assert response.json()["detail"] == "Промокод с таким кодом уже есть"


@pytest.mark.parametrize(
    "overrides",
    [
        {"code": "ab"},
        {"code": "BAD CODE"},
        {"title": "x"},
        {"value": 0},
        {"kind": "percent", "value": 101},
        {"kind": "bonus"},
        {"valid_from": "2026-12-01", "valid_to": "2026-11-01"},
        {"min_nights": 0},
    ],
)
def test_invalid_promo_is_rejected(admin_client: TestClient, overrides: dict[str, object]) -> None:
    assert admin_client.post("/api/admin/promos", json=promo_body(**overrides)).status_code == 422


def test_unknown_room_or_client_is_rejected(admin_client: TestClient, admin_user: User) -> None:
    assert admin_client.post("/api/admin/promos", json=promo_body(room_id=9999)).json()["detail"] == "Номер не найден"
    assert admin_client.post("/api/admin/promos", json=promo_body(user_id=9999)).json()["detail"] == "Клиент не найден"
    # Персональная акция — только для гостя, не для администратора.
    assert admin_client.post("/api/admin/promos", json=promo_body(user_id=admin_user.id)).status_code == 400


def test_admin_updates_promo_and_keeps_own_code(admin_client: TestClient) -> None:
    created = admin_client.post("/api/admin/promos", json=promo_body()).json()
    response = admin_client.patch(
        f"/api/admin/promos/{created['id']}", json=promo_body(title="Новое название", value=20)
    )
    assert response.status_code == 200
    assert (response.json()["title"], response.json()["value"]) == ("Новое название", 20)
    assert admin_client.patch("/api/admin/promos/9999", json=promo_body()).status_code == 404


def test_cannot_delete_promo_used_in_bookings(
    admin_client: TestClient, guest_client: TestClient, make_promo: MakePromo
) -> None:
    used = make_promo("USED")
    free = make_promo("FREE")
    guest_client.post("/api/bookings", json=booking_payload(nights=3, promo_code="USED"))

    blocked = admin_client.delete(f"/api/admin/promos/{used.id}")
    assert blocked.status_code == 409
    assert "деактивировать" in blocked.json()["detail"]
    assert admin_client.delete(f"/api/admin/promos/{free.id}").status_code == 204
    assert admin_client.delete(f"/api/admin/promos/{free.id}").status_code == 404


def test_cancelled_booking_still_blocks_deleting_promo(
    admin_client: TestClient, guest_client: TestClient, make_promo: MakePromo
) -> None:
    promo = make_promo("USED")
    booking = book(guest_client, "USED")
    guest_client.post(f"/api/account/bookings/{booking['id']}/cancel")
    assert admin_client.delete(f"/api/admin/promos/{promo.id}").status_code == 409


def test_bookings_in_admin_show_promo(
    admin_client: TestClient, guest_client: TestClient, make_promo: MakePromo
) -> None:
    make_promo()
    book(guest_client)
    item = admin_client.get("/api/admin/bookings").json()["items"][0]
    assert item["promo"]["code"] == "TEN"


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("GET", "/api/admin/promos"),
        ("POST", "/api/admin/promos"),
        ("PATCH", "/api/admin/promos/1"),
        ("DELETE", "/api/admin/promos/1"),
    ],
)
def test_promo_admin_is_forbidden_for_guest(
    guest_client: TestClient, client: TestClient, method: str, path: str
) -> None:
    body = promo_body() if method in ("POST", "PATCH") else None
    assert guest_client.request(method, path, json=body).status_code == 403
    assert client.request(method, path, json=body).status_code == 401
