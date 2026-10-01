from datetime import date, datetime
from enum import StrEnum

from sqlalchemy import JSON, Date, DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Hotel(Base):
    __tablename__ = "hotels"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    tagline: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text)
    address: Mapped[str] = mapped_column(String(200))
    phone: Mapped[str] = mapped_column(String(40))
    email: Mapped[str] = mapped_column(String(120))
    check_in_time: Mapped[str] = mapped_column(String(10))
    check_out_time: Mapped[str] = mapped_column(String(10))


class Room(Base):
    __tablename__ = "rooms"

    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String(60), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(120))
    description: Mapped[str] = mapped_column(Text)
    price_per_night: Mapped[int]
    capacity: Mapped[int]
    area: Mapped[int]
    amenities: Mapped[list[str]] = mapped_column(JSON)
    image: Mapped[str] = mapped_column(String(200))
    is_available: Mapped[bool] = mapped_column(default=True)


class BookingStatus(StrEnum):
    NEW = "new"
    CONFIRMED = "confirmed"
    CANCELLED = "cancelled"


# Запрет пересечения подтверждённых заявок и CHECK-ограничения живут в миграции 0001:
# EXCLUDE по daterange SQLAlchemy-моделью не описывается.
class Booking(Base):
    __tablename__ = "bookings"

    id: Mapped[int] = mapped_column(primary_key=True)
    room_id: Mapped[int] = mapped_column(ForeignKey("rooms.id"), index=True)
    guest_name: Mapped[str] = mapped_column(String(120))
    phone: Mapped[str] = mapped_column(String(40))
    email: Mapped[str] = mapped_column(String(120))
    check_in: Mapped[date] = mapped_column(Date)
    check_out: Mapped[date] = mapped_column(Date)
    guests: Mapped[int]
    comment: Mapped[str | None] = mapped_column(Text, default=None)
    status: Mapped[str] = mapped_column(String(20), default=BookingStatus.NEW)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    room: Mapped[Room] = relationship()


class UserRole(StrEnum):
    GUEST = "guest"
    ADMIN = "admin"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    # Email хранится в нижнем регистре: так уникальный индекс не пропустит «Ivan@» рядом с «ivan@».
    email: Mapped[str] = mapped_column(String(254), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(200))
    full_name: Mapped[str] = mapped_column(String(120))
    phone: Mapped[str | None] = mapped_column(String(40), default=None)
    role: Mapped[str] = mapped_column(String(20), default=UserRole.GUEST)
    is_active: Mapped[bool] = mapped_column(default=True)
    email_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    consent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)


class UserSession(Base):
    __tablename__ = "sessions"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class TokenPurpose(StrEnum):
    VERIFY_EMAIL = "verify_email"
    RESET_PASSWORD = "reset_password"


class EmailToken(Base):
    __tablename__ = "email_tokens"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    purpose: Mapped[str] = mapped_column(String(20))
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)

    user: Mapped[User] = relationship()
