from datetime import date, datetime
from enum import StrEnum

from sqlalchemy import JSON, Date, DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import ARRAY
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
    PENDING = "pending"
    CONFIRMED = "confirmed"
    DECLINED = "declined"
    CANCELLED = "cancelled"


class Actor(StrEnum):
    """Кто выполнил переход: движок правил, администратор или сам гость."""

    SYSTEM = "system"
    ADMIN = "admin"
    GUEST = "guest"


# Запрет пересечения подтверждённых броней и CHECK-ограничения живут в миграциях 0001 и 0003:
# EXCLUDE по daterange SQLAlchemy-моделью не описывается.
class Booking(Base):
    __tablename__ = "bookings"

    id: Mapped[int] = mapped_column(primary_key=True)
    room_id: Mapped[int] = mapped_column(ForeignKey("rooms.id"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    # Имя и телефон — снимок на момент брони, email берётся из аккаунта.
    guest_name: Mapped[str] = mapped_column(String(120))
    phone: Mapped[str] = mapped_column(String(40))
    check_in: Mapped[date] = mapped_column(Date)
    check_out: Mapped[date] = mapped_column(Date)
    guests: Mapped[int]
    comment: Mapped[str | None] = mapped_column(Text, default=None)
    # Статус меняет только booking_lifecycle.change_status. До первого перехода он None.
    status: Mapped[str] = mapped_column(String(20))
    decided_by: Mapped[str | None] = mapped_column(String(20), default=None)
    # Коды причин последнего решения (ключи booking_rules.REASON_TEXTS) и свободный текст администратора.
    reason_codes: Mapped[list[str]] = mapped_column(ARRAY(String(32)), default=list)
    reason_text: Mapped[str | None] = mapped_column(Text, default=None)
    nights: Mapped[int]
    price_per_night: Mapped[int]
    discount: Mapped[int] = mapped_column(default=0)
    total_price: Mapped[int]
    # Применённая акция: скидка выше сохранена снимком, а промокод считается занятым, пока бронь pending или confirmed.
    promo_id: Mapped[int | None] = mapped_column(ForeignKey("promos.id", ondelete="RESTRICT"), index=True, default=None)
    cancelled_by: Mapped[str | None] = mapped_column(String(20), default=None)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    room: Mapped[Room] = relationship()
    user: Mapped["User"] = relationship()
    promo: Mapped["Promo | None"] = relationship()
    # По id, а не по created_at: события одной транзакции получают одинаковое время now().
    events: Mapped[list["BookingEvent"]] = relationship(back_populates="booking", order_by="BookingEvent.id")


class BookingEvent(Base):
    """Журнал переходов брони: запись добавляется при каждом переходе и больше не меняется."""

    __tablename__ = "booking_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    booking_id: Mapped[int] = mapped_column(ForeignKey("bookings.id", ondelete="CASCADE"), index=True)
    from_status: Mapped[str | None] = mapped_column(String(20))
    to_status: Mapped[str] = mapped_column(String(20))
    actor: Mapped[str] = mapped_column(String(20))
    actor_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    reason_codes: Mapped[list[str]] = mapped_column(ARRAY(String(32)), default=list)
    reason_text: Mapped[str | None] = mapped_column(Text, default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    booking: Mapped[Booking] = relationship(back_populates="events")


class UserRole(StrEnum):
    GUEST = "guest"
    ADMIN = "admin"


class CrmStatus(StrEnum):
    REGULAR = "regular"
    VIP = "vip"
    BLOCKED = "blocked"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    # Email хранится в нижнем регистре: так уникальный индекс не пропустит «Ivan@» рядом с «ivan@».
    email: Mapped[str] = mapped_column(String(254), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(200))
    full_name: Mapped[str] = mapped_column(String(120))
    phone: Mapped[str | None] = mapped_column(String(40), default=None)
    role: Mapped[str] = mapped_column(String(20), default=UserRole.GUEST)
    # Отметка администратора о клиенте; по ней движок правил решает судьбу новых броней.
    crm_status: Mapped[str] = mapped_column(String(20), default=CrmStatus.REGULAR)
    # Заметка администратора о клиенте: гость её не видит.
    crm_note: Mapped[str | None] = mapped_column(Text, default=None)
    is_active: Mapped[bool] = mapped_column(default=True)
    email_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    consent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)


class PromoKind(StrEnum):
    PERCENT = "percent"
    FIXED = "fixed"


class Promo(Base):
    """Акция с промокодом. user_id пуст — общая акция, заполнен — персональная."""

    __tablename__ = "promos"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(32), unique=True)
    title: Mapped[str] = mapped_column(String(120))
    description: Mapped[str] = mapped_column(Text, default="")
    kind: Mapped[str] = mapped_column(String(10))
    # Для percent — проценты, для fixed — рубли.
    value: Mapped[int]
    valid_from: Mapped[date] = mapped_column(Date)
    valid_to: Mapped[date] = mapped_column(Date)
    min_nights: Mapped[int] = mapped_column(default=1)
    room_id: Mapped[int | None] = mapped_column(ForeignKey("rooms.id"), index=True, default=None)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), index=True, default=None)
    is_active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    room: Mapped[Room | None] = relationship()
    user: Mapped[User | None] = relationship()


class ServiceCategory(StrEnum):
    FOOD = "food"
    HOUSEKEEPING = "housekeeping"
    TRANSFER = "transfer"
    WELLNESS = "wellness"
    OTHER = "other"


class ServiceUnit(StrEnum):
    """За что берётся цена: за штуку (количество можно менять) или за всё проживание (заказ один)."""

    PER_ITEM = "per_item"
    PER_STAY = "per_stay"


class Service(Base):
    """Услуга из каталога гостиницы. Деактивированная скрывается из каталога, но остаётся в уже сделанных заказах."""

    __tablename__ = "services"

    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String(60), unique=True)
    title: Mapped[str] = mapped_column(String(120))
    description: Mapped[str] = mapped_column(Text, default="")
    category: Mapped[str] = mapped_column(String(20))
    price: Mapped[int]
    unit: Mapped[str] = mapped_column(String(10))
    is_active: Mapped[bool] = mapped_column(default=True)
    sort_order: Mapped[int] = mapped_column(default=100)


class OrderStatus(StrEnum):
    NEW = "new"
    ACCEPTED = "accepted"
    DONE = "done"
    CANCELLED = "cancelled"


class ServiceOrder(Base):
    """Заказ услуги или еды в номер к подтверждённой брони. Статус меняет только room_service.change_order_status."""

    __tablename__ = "service_orders"

    id: Mapped[int] = mapped_column(primary_key=True)
    booking_id: Mapped[int] = mapped_column(ForeignKey("bookings.id", ondelete="CASCADE"), index=True)
    service_id: Mapped[int] = mapped_column(ForeignKey("services.id", ondelete="RESTRICT"), index=True)
    quantity: Mapped[int]
    # Снимок цены на момент заказа.
    unit_price: Mapped[int]
    total: Mapped[int]
    scheduled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    comment: Mapped[str | None] = mapped_column(Text, default=None)
    status: Mapped[str] = mapped_column(String(10), default=OrderStatus.NEW)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    booking: Mapped[Booking] = relationship()
    service: Mapped[Service] = relationship()


class HousekeepingKind(StrEnum):
    DAILY = "daily"
    CHECKOUT = "checkout"


class HousekeepingSlot(StrEnum):
    """Время ежедневной уборки: утро 09–12, день 12–15, вечер 15–18 или «не беспокоить»."""

    MORNING = "morning"
    DAY = "day"
    EVENING = "evening"
    DND = "dnd"


class HousekeepingStatus(StrEnum):
    PLANNED = "planned"
    DONE = "done"
    SKIPPED = "skipped"


class HousekeepingTask(Base):
    """Уборка номера на дату. Создаются при подтверждении брони (housekeeping.create_stay_tasks)."""

    __tablename__ = "housekeeping_tasks"

    id: Mapped[int] = mapped_column(primary_key=True)
    booking_id: Mapped[int] = mapped_column(ForeignKey("bookings.id", ondelete="CASCADE"), index=True)
    room_id: Mapped[int] = mapped_column(ForeignKey("rooms.id"), index=True)
    date: Mapped[date] = mapped_column(Date, index=True)
    kind: Mapped[str] = mapped_column(String(10))
    slot: Mapped[str] = mapped_column(String(10), default=HousekeepingSlot.MORNING)
    status: Mapped[str] = mapped_column(String(10), default=HousekeepingStatus.PLANNED)
    done_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)

    booking: Mapped[Booking] = relationship()
    room: Mapped[Room] = relationship()


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
