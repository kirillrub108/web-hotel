import os
from collections.abc import Iterator
from pathlib import Path

from sqlalchemy.engine import make_url

# Тесты работают в отдельной базе kivana_test на том же сервере, рабочие данные не трогаются.
# Переменные задаются до первого импорта app: database.py и security.py читают их при импорте.
MAIN_DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql+psycopg://kivana:kivana@localhost:5432/kivana")
TEST_DATABASE_NAME = "kivana_test"
os.environ["DATABASE_URL"] = (
    make_url(MAIN_DATABASE_URL).set(database=TEST_DATABASE_NAME).render_as_string(hide_password=False)
)
os.environ["ADMIN_USERNAME"] = "admin"
os.environ["ADMIN_PASSWORD"] = "test-password"

import pytest  # noqa: E402
from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402
from sqlalchemy import create_engine, text  # noqa: E402

from app.database import engine  # noqa: E402
from app.security import booking_limiters, login_limiters  # noqa: E402
from seed import seed  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def test_database() -> Iterator[None]:
    server = create_engine(MAIN_DATABASE_URL, isolation_level="AUTOCOMMIT")
    with server.connect() as connection:
        connection.execute(text(f"DROP DATABASE IF EXISTS {TEST_DATABASE_NAME} WITH (FORCE)"))
        connection.execute(text(f"CREATE DATABASE {TEST_DATABASE_NAME}"))

    command.upgrade(Config(str(Path(__file__).parent / "alembic.ini")), "head")
    yield

    engine.dispose()
    with server.connect() as connection:
        connection.execute(text(f"DROP DATABASE {TEST_DATABASE_NAME} WITH (FORCE)"))
    server.dispose()


@pytest.fixture(autouse=True)
def fresh_data() -> None:
    with engine.begin() as connection:
        connection.execute(text("TRUNCATE bookings, rooms, hotels RESTART IDENTITY CASCADE"))
    seed()
    for limiter in booking_limiters + login_limiters:
        limiter.hits.clear()
