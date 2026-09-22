from alembic import context
from sqlalchemy import create_engine

from app.database import DATABASE_URL, Base
from app import models  # noqa: F401  — регистрирует таблицы в Base.metadata

connectable = create_engine(DATABASE_URL)

with connectable.connect() as connection:
    context.configure(connection=connection, target_metadata=Base.metadata)
    with context.begin_transaction():
        context.run_migrations()
