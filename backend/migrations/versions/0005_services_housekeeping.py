"""Услуги, заказы услуг и еды в номер, расписание уборок

Revision ID: 0005
Revises: 0004
"""
import sqlalchemy as sa
from alembic import op

revision: str = "0005"
down_revision: str | None = "0004"


def upgrade() -> None:
    op.create_table(
        "services",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("slug", sa.String(60), nullable=False, unique=True),
        sa.Column("title", sa.String(120), nullable=False),
        sa.Column("description", sa.Text, nullable=False, server_default=""),
        sa.Column("category", sa.String(20), nullable=False),
        sa.Column("price", sa.Integer, nullable=False),
        sa.Column("unit", sa.String(10), nullable=False),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("sort_order", sa.Integer, nullable=False, server_default="100"),
        sa.CheckConstraint(
            "category IN ('food', 'housekeeping', 'transfer', 'wellness', 'other')", name="services_category_check"
        ),
        sa.CheckConstraint("unit IN ('per_item', 'per_stay')", name="services_unit_check"),
        sa.CheckConstraint("price >= 0", name="services_price_check"),
    )

    op.create_table(
        "service_orders",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("booking_id", sa.Integer, sa.ForeignKey("bookings.id", ondelete="CASCADE"), nullable=False),
        # RESTRICT: услугу, по которой есть заказы, нельзя удалить — только деактивировать.
        sa.Column("service_id", sa.Integer, sa.ForeignKey("services.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("quantity", sa.Integer, nullable=False),
        # Цена услуги на момент заказа и итог: изменение каталога уже сделанные заказы не меняет.
        sa.Column("unit_price", sa.Integer, nullable=False),
        sa.Column("total", sa.Integer, nullable=False),
        sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("comment", sa.Text, nullable=True),
        sa.Column("status", sa.String(10), nullable=False, server_default="new"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("quantity BETWEEN 1 AND 20", name="service_orders_quantity_check"),
        sa.CheckConstraint("status IN ('new', 'accepted', 'done', 'cancelled')", name="service_orders_status_check"),
    )
    op.create_index("ix_service_orders_booking_id", "service_orders", ["booking_id"])
    op.create_index("ix_service_orders_service_id", "service_orders", ["service_id"])
    op.create_index("ix_service_orders_scheduled_at", "service_orders", ["scheduled_at"])

    op.create_table(
        "housekeeping_tasks",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("booking_id", sa.Integer, sa.ForeignKey("bookings.id", ondelete="CASCADE"), nullable=False),
        sa.Column("room_id", sa.Integer, sa.ForeignKey("rooms.id"), nullable=False),
        sa.Column("date", sa.Date, nullable=False),
        sa.Column("kind", sa.String(10), nullable=False),
        sa.Column("slot", sa.String(10), nullable=False, server_default="morning"),
        sa.Column("status", sa.String(10), nullable=False, server_default="planned"),
        sa.Column("done_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("kind IN ('daily', 'checkout')", name="housekeeping_tasks_kind_check"),
        sa.CheckConstraint("slot IN ('morning', 'day', 'evening', 'dnd')", name="housekeeping_tasks_slot_check"),
        sa.CheckConstraint("status IN ('planned', 'done', 'skipped')", name="housekeeping_tasks_status_check"),
        sa.UniqueConstraint("booking_id", "date", "kind", name="housekeeping_tasks_unique"),
    )
    op.create_index("ix_housekeeping_tasks_room_id", "housekeeping_tasks", ["room_id"])
    # Администратор открывает расписание за день, поэтому индекс по дате.
    op.create_index("ix_housekeeping_tasks_date", "housekeeping_tasks", ["date"])


def downgrade() -> None:
    op.drop_table("housekeeping_tasks")
    op.drop_table("service_orders")
    op.drop_table("services")
