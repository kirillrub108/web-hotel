"""CRM и акции: заметка о клиенте, промокоды, ссылка брони на применённую акцию

Revision ID: 0004
Revises: 0003
"""
import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"


def upgrade() -> None:
    op.add_column("users", sa.Column("crm_note", sa.Text, nullable=True))

    op.create_table(
        "promos",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("code", sa.String(32), nullable=False, unique=True),
        sa.Column("title", sa.String(120), nullable=False),
        sa.Column("description", sa.Text, nullable=False, server_default=""),
        sa.Column("kind", sa.String(10), nullable=False),
        sa.Column("value", sa.Integer, nullable=False),
        sa.Column("valid_from", sa.Date, nullable=False),
        sa.Column("valid_to", sa.Date, nullable=False),
        sa.Column("min_nights", sa.Integer, nullable=False, server_default="1"),
        # NULL — акция для любого номера.
        sa.Column("room_id", sa.Integer, sa.ForeignKey("rooms.id"), nullable=True),
        # NULL — общая акция, иначе персональная: код принадлежит одному клиенту.
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id"), nullable=True),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("kind IN ('percent', 'fixed')", name="promos_kind_check"),
        sa.CheckConstraint("value >= 1", name="promos_value_check"),
        sa.CheckConstraint("valid_to >= valid_from", name="promos_dates_check"),
        sa.CheckConstraint("min_nights >= 1", name="promos_min_nights_check"),
    )
    op.create_index("ix_promos_room_id", "promos", ["room_id"])
    op.create_index("ix_promos_user_id", "promos", ["user_id"])

    # RESTRICT: акцию, на которую ссылаются брони, нельзя удалить — только деактивировать.
    op.add_column(
        "bookings", sa.Column("promo_id", sa.Integer, sa.ForeignKey("promos.id", ondelete="RESTRICT"), nullable=True)
    )
    op.create_index("ix_bookings_promo_id", "bookings", ["promo_id"])


def downgrade() -> None:
    op.drop_index("ix_bookings_promo_id", "bookings")
    op.drop_column("bookings", "promo_id")
    op.drop_table("promos")
    op.drop_column("users", "crm_note")
