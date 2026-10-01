import re
from datetime import UTC, datetime, timedelta

from argon2 import PasswordHasher
from fastapi.testclient import TestClient
from httpx import Response
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app import mail
from app.main import app
from app.models import EmailToken, User, UserSession
from app.passwords import verify_password
from app.sessions import SESSION_COOKIE
from conftest import PASSWORD, login

NEW_PASSWORD = "violet harbor morning tram"


def register(client: TestClient, email: str = "maria@example.com", **overrides: object) -> int:
    payload: dict[str, object] = {
        "email": email,
        "full_name": "Мария Иванова",
        "password": PASSWORD,
        "consent": True,
    }
    payload.update(overrides)
    return client.post("/api/auth/register", json=payload).status_code


def last_token() -> str:
    found = re.search(r"token=([\w-]+)", mail.outbox[-1].text)
    assert found, mail.outbox[-1].text
    return found.group(1)


def field_errors(response: Response) -> dict[str, str]:
    detail = response.json()["detail"]
    return {item["loc"][-1]: item["msg"] for item in detail}


def age_email_tokens(db: Session, delta: timedelta) -> None:
    """Сдвигает выпуск всех токенов в прошлое — как будто с последнего письма прошло время."""
    db.execute(update(EmailToken).values(created_at=EmailToken.created_at - delta))


# --- Регистрация и подтверждение email ---


def test_register_verify_login(client: TestClient) -> None:
    assert register(client, " Maria@Example.COM ") == 204
    assert client.get("/api/auth/me").status_code == 401, "регистрация не входит в аккаунт"
    assert [sent.to for sent in mail.outbox] == ["maria@example.com"]
    assert "/verify-email?token=" in mail.outbox[0].text

    assert client.post("/api/auth/verify-email", json={"token": last_token()}).status_code == 204

    response = client.post("/api/auth/login", json={"email": "MARIA@example.com", "password": PASSWORD})
    assert response.status_code == 200
    me = client.get("/api/auth/me").json()
    assert me["email"] == "maria@example.com"
    assert me["role"] == "guest"
    assert me["email_verified_at"] is not None


def test_register_requires_consent(client: TestClient) -> None:
    assert register(client, consent=False) == 422


def test_register_rejects_weak_password_under_field(client: TestClient) -> None:
    response = client.post(
        "/api/auth/register",
        json={"email": "maria@example.com", "full_name": "Мария", "password": "maria@example.com", "consent": True},
    )
    assert response.status_code == 422
    assert field_errors(response) == {"password": "Похож на ваш email или имя"}


def test_login_before_verification_allowed(unverified_client: TestClient) -> None:
    assert unverified_client.get("/api/auth/me").json()["email_verified_at"] is None


def test_verify_token_is_single_use(client: TestClient) -> None:
    register(client)
    token = last_token()
    assert client.post("/api/auth/verify-email", json={"token": token}).status_code == 204

    again = client.post("/api/auth/verify-email", json={"token": token})
    assert again.status_code == 400
    assert "уже использована" in again.json()["detail"]


def test_expired_and_unknown_tokens(client: TestClient, db: Session) -> None:
    register(client)
    db.execute(update(EmailToken).values(expires_at=datetime.now(UTC) - timedelta(seconds=1)))

    expired = client.post("/api/auth/verify-email", json={"token": last_token()})
    assert expired.status_code == 400
    assert "истёк" in expired.json()["detail"]

    unknown = client.post("/api/auth/verify-email", json={"token": "nonexistent"})
    assert unknown.status_code == 400
    assert "недействительна" in unknown.json()["detail"]


def test_resend_verification_replaces_token_and_is_throttled(unverified_client: TestClient, db: Session) -> None:
    assert unverified_client.post("/api/auth/resend-verification").status_code == 204
    first = last_token()
    assert unverified_client.post("/api/auth/resend-verification").status_code == 429, "не чаще раза в минуту"

    age_email_tokens(db, timedelta(seconds=61))
    assert unverified_client.post("/api/auth/resend-verification").status_code == 204
    second = last_token()

    replaced = unverified_client.post("/api/auth/verify-email", json={"token": first})
    assert replaced.status_code == 400
    assert "заменена более новой" in replaced.json()["detail"]
    assert unverified_client.post("/api/auth/verify-email", json={"token": second}).status_code == 204
    assert unverified_client.post("/api/auth/resend-verification").status_code == 400, "email уже подтверждён"


def test_resend_verification_hourly_limit(unverified_client: TestClient, db: Session) -> None:
    for _ in range(5):
        assert unverified_client.post("/api/auth/resend-verification").status_code == 204
        age_email_tokens(db, timedelta(minutes=2))
    assert unverified_client.post("/api/auth/resend-verification").status_code == 429


def test_resend_verification_requires_login(client: TestClient) -> None:
    assert client.post("/api/auth/resend-verification").status_code == 401


# --- Защита от перечисления аккаунтов ---


def test_register_on_taken_email_looks_the_same(client: TestClient, guest: User) -> None:
    new = client.post(
        "/api/auth/register",
        json={"email": "other@example.com", "full_name": "Мария", "password": PASSWORD, "consent": True},
    )
    taken = client.post(
        "/api/auth/register",
        json={"email": "GUEST@example.com", "full_name": "Мария", "password": PASSWORD, "consent": True},
    )
    assert (new.status_code, new.content) == (taken.status_code, taken.content) == (204, b"")
    assert [sent.subject for sent in mail.outbox] == ["Подтвердите email — Kivana", "Аккаунт уже существует — Kivana"]
    assert mail.outbox[1].to == guest.email


def test_forgot_password_answers_the_same(client: TestClient, guest: User) -> None:
    known = client.post("/api/auth/forgot-password", json={"email": guest.email})
    unknown = client.post("/api/auth/forgot-password", json={"email": "nobody@example.com"})
    assert (known.status_code, known.content) == (unknown.status_code, unknown.content) == (204, b"")
    assert [sent.to for sent in mail.outbox] == [guest.email]


def test_login_error_is_the_same(client: TestClient, guest: User) -> None:
    wrong_password = client.post("/api/auth/login", json={"email": guest.email, "password": NEW_PASSWORD})
    unknown_email = client.post("/api/auth/login", json={"email": "nobody@example.com", "password": PASSWORD})
    assert wrong_password.status_code == unknown_email.status_code == 401
    assert wrong_password.json() == unknown_email.json() == {"detail": "Неверный email или пароль"}


def test_forgot_password_limited_per_email(client: TestClient, guest: User, db: Session) -> None:
    for _ in range(3):
        assert client.post("/api/auth/forgot-password", json={"email": guest.email}).status_code == 204
    assert len(mail.outbox) == 1, "второе письмо раньше чем через минуту не уходит"

    age_email_tokens(db, timedelta(seconds=61))
    client.post("/api/auth/forgot-password", json={"email": guest.email})
    assert len(mail.outbox) == 2


def test_account_endpoints_rate_limited_by_ip(client: TestClient) -> None:
    statuses = [
        client.post("/api/auth/forgot-password", json={"email": "a@example.com"}).status_code for _ in range(11)
    ]
    assert statuses == [204] * 10 + [429]


# --- Сессии ---


def test_sessions_on_two_devices(guest: User) -> None:
    phone, laptop = login(guest.email), login(guest.email)
    assert phone.get("/api/auth/me").status_code == 200
    assert laptop.get("/api/auth/me").status_code == 200

    assert phone.post("/api/auth/logout").status_code == 204
    assert phone.get("/api/auth/me").status_code == 401
    assert laptop.get("/api/auth/me").status_code == 200, "выход на одном устройстве не трогает другое"


def test_logout_deletes_session_from_db(guest_client: TestClient, db: Session) -> None:
    token = guest_client.cookies[SESSION_COOKIE]
    guest_client.post("/api/auth/logout")
    assert db.scalar(select(UserSession)) is None

    stolen = TestClient(app, cookies={SESSION_COOKIE: token})
    assert stolen.get("/api/auth/me").status_code == 401


def test_expired_session_rejected(guest_client: TestClient, db: Session) -> None:
    db.execute(update(UserSession).values(expires_at=datetime.now(UTC) - timedelta(seconds=1)))
    assert guest_client.get("/api/auth/me").status_code == 401


def test_session_ttl_depends_on_role(guest: User, admin_user: User, db: Session) -> None:
    login(guest.email)
    login(admin_user.email)
    expires = dict(db.execute(select(UserSession.user_id, UserSession.expires_at)).tuples().all())
    now = datetime.now(UTC)
    assert timedelta(days=13) < expires[guest.id] - now <= timedelta(days=14)
    assert timedelta(hours=11) < expires[admin_user.id] - now <= timedelta(hours=12)


def test_inactive_user_cannot_login_and_loses_sessions(guest_client: TestClient, guest: User, db: Session) -> None:
    guest.is_active = False
    db.flush()
    assert guest_client.get("/api/auth/me").status_code == 401

    response = guest_client.post("/api/auth/login", json={"email": guest.email, "password": PASSWORD})
    assert response.status_code == 401
    assert response.json() == {"detail": "Неверный email или пароль"}


def test_login_rehashes_outdated_hash(guest: User, db: Session) -> None:
    guest.password_hash = PasswordHasher(time_cost=1, memory_cost=8192).hash(PASSWORD)
    db.flush()
    outdated = guest.password_hash

    login(guest.email)

    db.refresh(guest)
    assert guest.password_hash != outdated
    assert verify_password(guest.password_hash, PASSWORD)
    assert guest.last_login_at is not None


# --- Смена и сброс пароля ---


def test_change_password_ends_other_sessions(guest: User) -> None:
    current, other = login(guest.email), login(guest.email)
    response = current.post(
        "/api/auth/change-password",
        json={"current_password": PASSWORD, "new_password": NEW_PASSWORD},
    )
    assert response.status_code == 204
    assert current.get("/api/auth/me").status_code == 200, "текущая сессия остаётся"
    assert other.get("/api/auth/me").status_code == 401, "остальные сессии удалены"
    login(guest.email, NEW_PASSWORD)


def test_change_password_errors_under_fields(guest_client: TestClient) -> None:
    wrong_current = guest_client.post(
        "/api/auth/change-password",
        json={"current_password": NEW_PASSWORD, "new_password": NEW_PASSWORD},
    )
    assert field_errors(wrong_current) == {"current_password": "Текущий пароль указан неверно"}

    weak = guest_client.post(
        "/api/auth/change-password",
        json={"current_password": PASSWORD, "new_password": "qwertyqwerty12345"},
    )
    assert field_errors(weak) == {"new_password": "Слишком распространённый пароль"}


def test_reset_password_ends_all_sessions(guest: User, client: TestClient) -> None:
    devices = [login(guest.email), login(guest.email)]
    client.post("/api/auth/forgot-password", json={"email": guest.email})
    token = last_token()
    assert "/reset-password?token=" in mail.outbox[-1].text

    weak = client.post("/api/auth/reset-password", json={"token": token, "password": "qwertyqwerty12345"})
    assert field_errors(weak) == {"password": "Слишком распространённый пароль"}

    # Отказ по слабому паролю не тратит ссылку: можно ввести другой пароль.
    assert client.post("/api/auth/reset-password", json={"token": token, "password": NEW_PASSWORD}).status_code == 204
    for device in devices:
        assert device.get("/api/auth/me").status_code == 401

    login(guest.email, NEW_PASSWORD)
    reused = client.post("/api/auth/reset-password", json={"token": token, "password": NEW_PASSWORD})
    assert reused.status_code == 400


def test_reset_password_confirms_email(unverified_guest: User, client: TestClient, db: Session) -> None:
    client.post("/api/auth/forgot-password", json={"email": unverified_guest.email})
    client.post("/api/auth/reset-password", json={"token": last_token(), "password": NEW_PASSWORD})
    db.refresh(unverified_guest)
    assert unverified_guest.email_verified_at is not None


# --- Права доступа и профиль ---


def test_admin_api_requires_admin_role(client: TestClient, guest_client: TestClient, admin_client: TestClient) -> None:
    for caller, expected in ((client, 401), (guest_client, 403), (admin_client, 200)):
        assert caller.get("/api/admin/bookings").status_code == expected
    assert client.post("/api/admin/bookings/1/confirm", json={}).status_code == 401
    assert guest_client.post("/api/admin/bookings/1/confirm", json={}).status_code == 403


def test_profile(guest_client: TestClient, client: TestClient) -> None:
    assert client.get("/api/account/profile").status_code == 401
    assert guest_client.get("/api/account/profile").json()["full_name"] == "Иван Петров"

    updated = guest_client.patch(
        "/api/account/profile",
        json={"full_name": "  Иван Сидоров ", "phone": "+7 900 111-22-33"},
    )
    assert updated.status_code == 200
    assert (updated.json()["full_name"], updated.json()["phone"]) == ("Иван Сидоров", "+7 900 111-22-33")

    cleared = guest_client.patch("/api/account/profile", json={"full_name": "Иван Сидоров", "phone": "  "})
    assert cleared.json()["phone"] is None
    assert guest_client.patch("/api/account/profile", json={"full_name": "Иван", "phone": "12"}).status_code == 422
