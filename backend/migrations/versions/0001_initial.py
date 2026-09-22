"""Начальная схема: гостиница, номера, заявки

Revision ID: 0001
Revises:
"""
import sqlalchemy as sa
from alembic import op

revision: str = "0001"
down_revision: str | None = None


def upgrade() -> None:
    # btree_gist нужен, чтобы в одном EXCLUDE-ограничении сравнивать и room_id (=), и диапазон дат (&&).
    op.execute("CREATE EXTENSION IF NOT EXISTS btree_gist")

    op.create_table(
        "hotels",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("tagline", sa.String(200), nullable=False),
        sa.Column("description", sa.Text, nullable=False),
        sa.Column("address", sa.String(200), nullable=False),
        sa.Column("phone", sa.String(40), nullable=False),
        sa.Column("email", sa.String(120), nullable=False),
        sa.Column("check_in_time", sa.String(10), nullable=False),
        sa.Column("check_out_time", sa.String(10), nullable=False),
    )

    op.create_table(
        "rooms",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("slug", sa.String(60), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("description", sa.Text, nullable=False),
        sa.Column("price_per_night", sa.Integer, nullable=False),
        sa.Column("capacity", sa.Integer, nullable=False),
        sa.Column("area", sa.Integer, nullable=False),
        sa.Column("amenities", sa.JSON, nullable=False),
        sa.Column("image", sa.String(200), nullable=False),
        sa.Column("is_available", sa.Boolean, nullable=False),
    )
    op.create_index("ix_rooms_slug", "rooms", ["slug"], unique=True)

    op.create_table(
        "bookings",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("room_id", sa.Integer, sa.ForeignKey("rooms.id"), nullable=False),
        sa.Column("guest_name", sa.String(120), nullable=False),
        sa.Column("phone", sa.String(40), nullable=False),
        sa.Column("email", sa.String(120), nullable=False),
        sa.Column("check_in", sa.Date, nullable=False),
        sa.Column("check_out", sa.Date, nullable=False),
        sa.Column("guests", sa.Integer, nullable=False),
        sa.Column("comment", sa.Text, nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="new"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("check_out > check_in", name="bookings_dates_check"),
        sa.CheckConstraint("guests >= 1", name="bookings_guests_check"),
        sa.CheckConstraint("status IN ('new', 'confirmed', 'cancelled')", name="bookings_status_check"),
    )
    op.create_index("ix_bookings_room_id", "bookings", ["room_id"])

    # Два подтверждённых заезда в один номер на пересекающиеся даты база не примет даже при гонке запросов.
    # daterange по умолчанию полуоткрытый [check_in, check_out): выезд утром и заезд днём в тот же день не конфликтуют.
    op.execute(
        "ALTER TABLE bookings ADD CONSTRAINT bookings_no_overlap "
        "EXCLUDE USING gist (room_id WITH =, daterange(check_in, check_out) WITH &&) "
        "WHERE (status = 'confirmed')"
    )


def downgrade() -> None:
    op.drop_table("bookings")
    op.drop_table("rooms")
    op.drop_table("hotels")
