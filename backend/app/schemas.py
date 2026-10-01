import os
import re
from datetime import date, datetime
from typing import Annotated

from pydantic import (
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    StringConstraints,
    computed_field,
    field_validator,
    model_validator,
)

from app import hotel_time
from app.booking_rules import DisplayStatus, Segment, client_segment, display_status, reason_texts
from app.housekeeping import guest_can_change_slot
from app.models import (
    Actor,
    BookingStatus,
    CrmStatus,
    HousekeepingKind,
    HousekeepingSlot,
    HousekeepingStatus,
    OrderStatus,
    PromoKind,
    ServiceCategory,
    ServiceUnit,
    UserRole,
)
from app.passwords import PASSWORD_MAX_LENGTH

EMAIL_PATTERN = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"
MAX_LEAD_DAYS = int(os.getenv("MAX_LEAD_DAYS", "365"))
MAX_STAY_NIGHTS = int(os.getenv("MAX_STAY_NIGHTS", "30"))


def validate_phone(value: str) -> str:
    if not 10 <= len(re.sub(r"\D", "", value)) <= 15:
        raise ValueError("Укажите телефон полностью, например +7 900 000-00-00")
    return value


class HotelOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    tagline: str
    description: str
    address: str
    phone: str
    email: str
    check_in_time: str
    check_out_time: str


class RoomOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    slug: str
    name: str
    description: str
    price_per_night: int
    capacity: int
    area: int
    amenities: list[str]
    image: str
    is_available: bool


class StayIn(BaseModel):
    """Даты и число гостей: общие проверки для котировки и создания брони."""

    check_in: date
    check_out: date
    guests: int = Field(ge=1, le=20)
    # Промокод необязателен; применимость кода проверяет backend при расчёте цены.
    promo_code: str | None = Field(default=None, max_length=32)

    @field_validator("promo_code")
    @classmethod
    def empty_promo_to_none(cls, value: str | None) -> str | None:
        return (value or "").strip() or None

    @model_validator(mode="after")
    def check_dates(self) -> "StayIn":
        today = hotel_time.hotel_today()
        if self.check_in < today:
            raise ValueError("Дата заезда не может быть в прошлом")
        if (self.check_in - today).days > MAX_LEAD_DAYS:
            raise ValueError(f"Заезд можно запланировать не дальше чем на {MAX_LEAD_DAYS} дней вперёд")
        if self.check_out <= self.check_in:
            raise ValueError("Дата выезда должна быть позже даты заезда")
        if (self.check_out - self.check_in).days > MAX_STAY_NIGHTS:
            raise ValueError(f"Максимальная длительность проживания — {MAX_STAY_NIGHTS} ночей")
        return self


class BookingCreate(StayIn):
    model_config = ConfigDict(str_strip_whitespace=True)

    room_id: int
    guest_name: str = Field(min_length=2, max_length=120)
    phone: str = Field(max_length=40)
    comment: str | None = Field(default=None, max_length=1000)

    @field_validator("phone")
    @classmethod
    def check_phone(cls, value: str) -> str:
        return validate_phone(value)

    @field_validator("comment")
    @classmethod
    def empty_comment_to_none(cls, value: str | None) -> str | None:
        # Комментарий из одних пробелов после обрезки пуст и не должен отправлять заявку на ручной разбор.
        return value or None


class QuoteOut(BaseModel):
    available: bool
    unavailable_reason: str | None
    nights: int
    price_per_night: int
    subtotal: int
    discount: int
    total: int
    promo_title: str | None


class RoomShort(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    slug: str
    name: str


class PromoShort(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    code: str
    title: str


class ReasonsOut(BaseModel):
    """Причины решения: коды и текст администратора превращаются в список фраз простыми словами.

    Коды наружу не отдаются: гость видит только тексты. Схемы админки добавляют коды отдельным полем.
    """

    model_config = ConfigDict(from_attributes=True)

    reason_codes: list[str] = Field(exclude=True)
    reason_text: str | None = Field(exclude=True)

    @computed_field
    @property
    def reasons(self) -> list[str]:
        return reason_texts(self.reason_codes, self.reason_text)


class BookingEventOut(ReasonsOut):
    id: int
    from_status: BookingStatus | None
    to_status: BookingStatus
    actor: Actor
    created_at: datetime


class GuestBookingOut(ReasonsOut):
    id: int
    room: RoomShort
    guest_name: str
    phone: str
    check_in: date
    check_out: date
    guests: int
    comment: str | None
    status: BookingStatus
    nights: int
    price_per_night: int
    discount: int
    total_price: int
    promo: PromoShort | None
    created_at: datetime
    cancelled_at: datetime | None

    @computed_field
    @property
    def display_status(self) -> DisplayStatus:
        return display_status(self.status, self.check_in, self.check_out, hotel_time.hotel_today())


class ServiceOut(BaseModel):
    """Услуга в каталоге: то, что видит гость."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    slug: str
    title: str
    description: str
    category: ServiceCategory
    price: int
    unit: ServiceUnit


class ServiceShort(BaseModel):
    """Услуга в заказе. Есть и у деактивированной услуги: заказ остаётся читаемым."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    category: ServiceCategory
    unit: ServiceUnit
    is_active: bool


class ServiceOrderOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    service: ServiceShort
    quantity: int
    unit_price: int
    total: int
    scheduled_at: datetime
    comment: str | None
    status: OrderStatus
    created_at: datetime


class GuestServiceOrderOut(ServiceOrderOut):
    @computed_field
    @property
    def can_cancel(self) -> bool:
        return self.status == OrderStatus.NEW


class HousekeepingTaskOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    kind: HousekeepingKind
    slot: HousekeepingSlot
    status: HousekeepingStatus
    done_at: datetime | None
    date: date

    @computed_field
    @property
    def can_change_slot(self) -> bool:
        return guest_can_change_slot(self.kind, self.status, self.date)


class OrderWindow(BaseModel):
    """Когда можно назначить заказ. Время — по часам отеля, со смещением часового пояса."""

    start: datetime
    end: datetime


class GuestBookingDetail(BaseModel):
    booking: GuestBookingOut
    events: list[BookingEventOut]
    # Дедлайн бесплатной отмены — только у подтверждённой брони; can_cancel учитывает и статус, и время.
    cancel_deadline: datetime | None
    can_cancel: bool
    orders: list[GuestServiceOrderOut]
    # Итог по заказам без отменённых; оплата услуг — на ресепшене, онлайн-оплаты нет.
    services_total: int
    # Можно ли сейчас заказывать услуги и в какое окно должно попасть время заказа.
    can_order: bool
    order_window: OrderWindow | None
    # Часы приёма заказов еды, например «08:00–23:00».
    room_service_hours: str
    housekeeping: list[HousekeepingTaskOut]


class UserShort(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    full_name: str
    crm_status: CrmStatus


class AdminBookingOut(GuestBookingOut):
    reason_codes: list[str]
    user: UserShort
    decided_by: Actor | None
    cancelled_by: Actor | None


class AdminBookingEventOut(BookingEventOut):
    reason_codes: list[str]


class AdminBookingDetail(BaseModel):
    booking: AdminBookingOut
    events: list[AdminBookingEventOut]


class AdminBookingPage(BaseModel):
    items: list[AdminBookingOut]
    total: int


class AdminConfirmIn(BaseModel):
    reason: str | None = Field(default=None, max_length=1000)

    @field_validator("reason")
    @classmethod
    def empty_reason_to_none(cls, value: str | None) -> str | None:
        return (value or "").strip() or None


class AdminReasonIn(BaseModel):
    """Отказ и отмена администратором: причина обязательна, её увидит гость."""

    reason: str = Field(max_length=1000)

    @field_validator("reason")
    @classmethod
    def check_reason(cls, value: str) -> str:
        value = value.strip()
        if len(value) < 3:
            raise ValueError("Укажите причину — её увидит гость")
        return value


def normalize_email(value: object) -> object:
    return value.strip().lower() if isinstance(value, str) else value


# Пароли в схемах не обрезаются по краям: пробел — допустимый символ пароля.
Email = Annotated[str, BeforeValidator(normalize_email), Field(pattern=EMAIL_PATTERN, max_length=254)]
FullName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=120)]
CurrentPassword = Annotated[str, Field(min_length=1, max_length=PASSWORD_MAX_LENGTH)]


class RegisterIn(BaseModel):
    email: Email
    full_name: FullName
    password: str
    consent: bool

    @field_validator("consent")
    @classmethod
    def check_consent(cls, value: bool) -> bool:
        if not value:
            raise ValueError("Нужно согласие на обработку персональных данных")
        return value


class LoginIn(BaseModel):
    email: Email
    password: CurrentPassword


class EmailIn(BaseModel):
    email: Email


class TokenIn(BaseModel):
    token: str = Field(max_length=100)


class ResetPasswordIn(TokenIn):
    password: str


class ChangePasswordIn(BaseModel):
    current_password: CurrentPassword
    new_password: str


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    full_name: str
    phone: str | None
    role: UserRole
    email_verified_at: datetime | None
    created_at: datetime


class ProfileUpdate(BaseModel):
    full_name: FullName
    phone: str | None = Field(default=None, max_length=40)

    @field_validator("phone")
    @classmethod
    def check_phone(cls, value: str | None) -> str | None:
        value = (value or "").strip()
        return validate_phone(value) if value else None


class PromoOffer(BaseModel):
    """Предложение гостю в кабинете: условия акции без служебных полей."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    code: str
    title: str
    description: str
    kind: PromoKind
    value: int
    valid_from: date
    valid_to: date
    min_nights: int
    room_id: int | None
    room: RoomShort | None
    user_id: int | None = Field(exclude=True)

    @computed_field
    @property
    def is_personal(self) -> bool:
        return self.user_id is not None


class PromoIn(BaseModel):
    """Создание и изменение акции администратором. Изменение — полное: приходят все поля."""

    model_config = ConfigDict(str_strip_whitespace=True)

    code: Annotated[str, BeforeValidator(lambda v: v.strip().upper() if isinstance(v, str) else v)] = Field(
        pattern=r"^[A-Z0-9_-]{3,32}$"
    )
    title: str = Field(min_length=2, max_length=120)
    description: str = Field(default="", max_length=1000)
    kind: PromoKind
    value: int = Field(ge=1, le=1_000_000)
    valid_from: date
    valid_to: date
    min_nights: int = Field(default=1, ge=1, le=MAX_STAY_NIGHTS)
    room_id: int | None = None
    user_id: int | None = None
    is_active: bool = True

    @model_validator(mode="after")
    def check_terms(self) -> "PromoIn":
        if self.kind == PromoKind.PERCENT and self.value > 100:
            raise ValueError("Процент скидки — от 1 до 100")
        if self.valid_to < self.valid_from:
            raise ValueError("Дата окончания не может быть раньше даты начала")
        return self


class AdminPromoOut(PromoOffer):
    is_active: bool
    created_at: datetime
    user: UserShort | None
    # Занят ли код бронью в статусе pending или confirmed, и сколько всего броней на нём было.
    in_use: bool
    bookings_count: int


class ClientOut(BaseModel):
    """Клиент в CRM. Показатели вычисляются запросом (crm.client_select), в таблице users их нет."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    full_name: str
    phone: str | None
    crm_status: CrmStatus
    crm_note: str | None
    created_at: datetime
    last_activity_at: datetime
    # Завершённые проживания: подтверждённые брони с выездом не позже сегодняшнего дня.
    stays: int
    nights: int
    # Выручка — по всем подтверждённым броням, в том числе предстоящим.
    revenue: int
    last_stay_at: date | None

    @computed_field
    @property
    def segment(self) -> Segment:
        return client_segment(self.stays)


class ClientPage(BaseModel):
    items: list[ClientOut]
    total: int


class ClientDetail(BaseModel):
    client: ClientOut
    bookings: list[AdminBookingOut]
    promos: list[AdminPromoOut]


class ClientUpdate(BaseModel):
    """Частичное изменение: сохраняются только присланные поля."""

    crm_status: CrmStatus | None = None
    crm_note: str | None = Field(default=None, max_length=2000)

    @field_validator("crm_note")
    @classmethod
    def empty_note_to_none(cls, value: str | None) -> str | None:
        return (value or "").strip() or None


class ServiceOrderIn(BaseModel):
    service_id: int
    quantity: int = Field(default=1, ge=1, le=20)
    # Время без пояса считается временем отеля: так его присылает поле datetime-local.
    scheduled_at: datetime
    comment: str | None = Field(default=None, max_length=500)

    @field_validator("scheduled_at")
    @classmethod
    def attach_hotel_zone(cls, value: datetime) -> datetime:
        return value if value.tzinfo else value.replace(tzinfo=hotel_time.HOTEL_TZ)

    @field_validator("comment")
    @classmethod
    def empty_comment_to_none(cls, value: str | None) -> str | None:
        return (value or "").strip() or None


class HousekeepingSlotIn(BaseModel):
    slot: HousekeepingSlot


class ServiceIn(BaseModel):
    """Создание и изменение услуги администратором. Изменение — полное: приходят все поля."""

    model_config = ConfigDict(str_strip_whitespace=True)

    slug: str = Field(pattern=r"^[a-z0-9]+(-[a-z0-9]+)*$", max_length=60)
    title: str = Field(min_length=2, max_length=120)
    description: str = Field(default="", max_length=1000)
    category: ServiceCategory
    price: int = Field(ge=0, le=1_000_000)
    unit: ServiceUnit
    is_active: bool = True
    sort_order: int = Field(default=100, ge=0, le=10_000)


class AdminServiceOut(ServiceOut):
    is_active: bool
    sort_order: int
    orders_count: int


class OrderStatusIn(BaseModel):
    status: OrderStatus


class HousekeepingStatusIn(BaseModel):
    status: HousekeepingStatus


class OrderBookingShort(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    guest_name: str
    phone: str
    room: RoomShort


class AdminServiceOrderOut(ServiceOrderOut):
    booking: OrderBookingShort


class AdminHousekeepingTaskOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    kind: HousekeepingKind
    slot: HousekeepingSlot
    status: HousekeepingStatus
    done_at: datetime | None
    room: RoomShort
    booking: OrderBookingShort
    # Уборка после выезда, а в этот же номер сегодня заезжает другая бронь.
    arrival_today: bool
    date: date


class DailySlots(BaseModel):
    morning: list[AdminHousekeepingTaskOut]
    day: list[AdminHousekeepingTaskOut]
    evening: list[AdminHousekeepingTaskOut]


class HousekeepingBoard(BaseModel):
    checkout: list[AdminHousekeepingTaskOut]
    daily: DailySlots
    dnd: list[AdminHousekeepingTaskOut]
    orders: list[AdminServiceOrderOut]
    date: date
