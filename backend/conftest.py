import os
from collections.abc import Callable, Iterator
from datetime import UTC, date, datetime
from pathlib import Path

from sqlalchemy.engine import make_url

# Тесты работают в отдельной базе kivana_test на том же сервере, рабочие данные не трогаются.
# Переменные задаются до первого импорта app: модули читают их при импорте.
MAIN_DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql+psycopg://kivana:kivana@localhost:5432/kivana")
TEST_DATABASE_NAME = "kivana_test"
os.environ["DATABASE_URL"] = (
    make_url(MAIN_DATABASE_URL).set(database=TEST_DATABASE_NAME).render_as_string(hide_password=False)
)
os.environ["MAIL_BACKEND"] = "memory"

import pytest  # noqa: E402
from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine, select, text  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app import mail  # noqa: E402
from app.booking_rules import calculate_price  # noqa: E402
from app.database import engine, get_db  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Booking, BookingStatus, Room, User, UserRole  # noqa: E402
from app.passwords import hash_password  # noqa: E402
from app.security import account_limiters, booking_limiters, login_limiters  # noqa: E402
from seed import seed  # noqa: E402

PASSWORD = "lantern copper orbit meadow"
# Argon2 намеренно медленный: один хэш на все тестовые аккаунты заметно ускоряет прогон.
PASSWORD_HASH = hash_password(PASSWORD)
ALEMBIC_CONFIG = Config(str(Path(__file__).parent / "alembic.ini"))


@pytest.fixture(scope="session", autouse=True)
def test_database() -> Iterator[None]:
    server = create_engine(MAIN_DATABASE_URL, isolation_level="AUTOCOMMIT")
    with server.connect() as connection:
        exists = connection.scalar(
            text("SELECT 1 FROM pg_database WHERE datname = :name"), {"name": TEST_DATABASE_NAME}
        )
        if not exists:
            connection.execute(text(f"CREATE DATABASE {TEST_DATABASE_NAME}"))
    server.dispose()

    # Схему создают те же миграции, что и в рабочей базе: в них btree_gist и ограничение на пересечение броней.
    command.upgrade(ALEMBIC_CONFIG, "head")
    seed()
    yield
    engine.dispose()


@pytest.fixture(autouse=True)
def db() -> Iterator[Session]:
    """Каждый тест идёт внутри транзакции, которая в конце откатывается.

    commit() в коде приложения фиксирует только точку сохранения (savepoint),
    поэтому после теста база возвращается к состоянию сразу после сида.
    """
    connection = engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint", autoflush=False)

    def override_get_db() -> Session:
        return session

    app.dependency_overrides[get_db] = override_get_db
    for limiter in booking_limiters + login_limiters + account_limiters:
        limiter.hits.clear()
    mail.outbox.clear()

    yield session

    app.dependency_overrides.clear()
    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture
def make_user(db: Session) -> Callable[..., User]:
    def create(
        email: str,
        *,
        role: UserRole = UserRole.GUEST,
        verified: bool = True,
        full_name: str = "Иван Петров",
    ) -> User:
        now = datetime.now(UTC)
        user = User(
            email=email,
            password_hash=PASSWORD_HASH,
            full_name=full_name,
            role=role,
            email_verified_at=now if verified else None,
            consent_at=now,
        )
        db.add(user)
        db.flush()
        return user

    return create


@pytest.fixture
def guest(make_user: Callable[..., User]) -> User:
    return make_user("guest@example.com")


@pytest.fixture
def unverified_guest(make_user: Callable[..., User]) -> User:
    return make_user("new-guest@example.com", verified=False)


@pytest.fixture
def admin_user(make_user: Callable[..., User]) -> User:
    return make_user("boss@example.com", role=UserRole.ADMIN, full_name="Анна Смирнова")


@pytest.fixture
def make_booking(db: Session, guest: User) -> Callable[..., Booking]:
    """Бронь в нужном статусе напрямую в базе, минуя функцию перехода и журнал: так готовятся исходные состояния."""

    def create(
        check_in: date,
        check_out: date,
        *,
        status: BookingStatus = BookingStatus.PENDING,
        user: User | None = None,
        room_slug: str = "standart",
    ) -> Booking:
        room = db.scalars(select(Room).where(Room.slug == room_slug)).one()
        price = calculate_price(room.price_per_night, check_in, check_out)
        booking = Booking(
            user=user or guest,
            room=room,
            guest_name="Иван Петров",
            phone="+7 900 123-45-67",
            check_in=check_in,
            check_out=check_out,
            guests=1,
            status=status,
            nights=price.nights,
            price_per_night=price.price_per_night,
            discount=price.discount,
            total_price=price.total,
        )
        db.add(booking)
        db.flush()
        return booking

    return create


def login(email: str, password: str = PASSWORD) -> TestClient:
    client = TestClient(app)
    response = client.post("/api/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    return client


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture
def guest_client(guest: User) -> TestClient:
    return login(guest.email)


@pytest.fixture
def unverified_client(unverified_guest: User) -> TestClient:
    return login(unverified_guest.email)


@pytest.fixture
def admin_client(admin_user: User) -> TestClient:
    return login(admin_user.email)
