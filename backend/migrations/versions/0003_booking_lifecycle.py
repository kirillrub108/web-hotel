"""Жизненный цикл брони: бронь привязана к аккаунту, журнал событий, CRM-статус клиента

Revision ID: 0003
Revises: 0002
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0003"
down_revision: str | None = "0002"


def upgrade() -> None:
    # Брони прошлой версии создавались без аккаунта и были демо-данными. Привязать их к пользователю нельзя,
    # а без этого не встанет NOT NULL на user_id, поэтому они удаляются.
    op.execute("DELETE FROM bookings")

    op.drop_constraint("bookings_status_check", "bookings", type_="check")
    op.alter_column("bookings", "status", server_default="pending")
    op.create_check_constraint(
        "bookings_status_check", "bookings", "status IN ('pending', 'confirmed', 'declined', 'cancelled')"
    )
    # Предикат bookings_no_overlap из 0001 — WHERE (status = 'confirmed') — остаётся верным и в новой модели:
    # даты блокирует только подтверждённая бронь, а pending, declined и cancelled — нет.

    # Email гостя теперь берётся из аккаунта; имя и телефон остаются снимком на момент брони.
    op.drop_column("bookings", "email")
    op.add_column("bookings", sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id"), nullable=False))
    op.create_index("ix_bookings_user_id", "bookings", ["user_id"])
    op.add_column("bookings", sa.Column("decided_by", sa.String(20), nullable=True))
    op.add_column(
        "bookings",
        sa.Column("reason_codes", postgresql.ARRAY(sa.String(32)), nullable=False, server_default="{}"),
    )
    op.add_column("bookings", sa.Column("reason_text", sa.Text, nullable=True))
    # Цена — снимок на момент брони: изменение прайса не меняет уже сделанные брони.
    op.add_column("bookings", sa.Column("nights", sa.Integer, nullable=False))
    op.add_column("bookings", sa.Column("price_per_night", sa.Integer, nullable=False))
    op.add_column("bookings", sa.Column("discount", sa.Integer, nullable=False, server_default="0"))
    op.add_column("bookings", sa.Column("total_price", sa.Integer, nullable=False))
    op.add_column("bookings", sa.Column("cancelled_by", sa.String(20), nullable=True))
    op.add_column("bookings", sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True))
    op.create_check_constraint("bookings_decided_by_check", "bookings", "decided_by IN ('system', 'admin')")
    op.create_check_constraint("bookings_cancelled_by_check", "bookings", "cancelled_by IN ('guest', 'admin')")
    op.create_check_constraint(
        "bookings_price_check",
        "bookings",
        "nights >= 1 AND price_per_night >= 0 AND discount >= 0 AND total_price >= 0",
    )

    op.create_table(
        "booking_events",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("booking_id", sa.Integer, sa.ForeignKey("bookings.id", ondelete="CASCADE"), nullable=False),
        # NULL — событие создания заявки: до него статуса не было.
        sa.Column("from_status", sa.String(20), nullable=True),
        sa.Column("to_status", sa.String(20), nullable=False),
        sa.Column("actor", sa.String(20), nullable=False),
        sa.Column("actor_user_id", sa.Integer, sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("reason_codes", postgresql.ARRAY(sa.String(32)), nullable=False, server_default="{}"),
        sa.Column("reason_text", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("actor IN ('system', 'admin', 'guest')", name="booking_events_actor_check"),
    )
    op.create_index("ix_booking_events_booking_id", "booking_events", ["booking_id"])

    op.add_column("users", sa.Column("crm_status", sa.String(20), nullable=False, server_default="regular"))
    op.create_check_constraint("users_crm_status_check", "users", "crm_status IN ('regular', 'vip', 'blocked')")


def downgrade() -> None:
    op.drop_constraint("users_crm_status_check", "users", type_="check")
    op.drop_column("users", "crm_status")

    op.drop_table("booking_events")

    # Downgrade восстанавливает схему, но не данные: в старой схеме у брони обязателен email и нет статусов
    # pending и declined, поэтому брони удаляются.
    op.execute("DELETE FROM bookings")

    op.drop_constraint("bookings_price_check", "bookings", type_="check")
    op.drop_constraint("bookings_cancelled_by_check", "bookings", type_="check")
    op.drop_constraint("bookings_decided_by_check", "bookings", type_="check")
    for column in (
        "cancelled_at",
        "cancelled_by",
        "total_price",
        "discount",
        "price_per_night",
        "nights",
        "reason_text",
        "reason_codes",
        "decided_by",
    ):
        op.drop_column("bookings", column)
    op.drop_index("ix_bookings_user_id", "bookings")
    op.drop_column("bookings", "user_id")
    op.add_column("bookings", sa.Column("email", sa.String(120), nullable=False))

    op.drop_constraint("bookings_status_check", "bookings", type_="check")
    op.alter_column("bookings", "status", server_default="new")
    op.create_check_constraint("bookings_status_check", "bookings", "status IN ('new', 'confirmed', 'cancelled')")
