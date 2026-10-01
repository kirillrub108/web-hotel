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
from app.booking_rules import DisplayStatus, display_status, reason_texts
from app.models import Actor, BookingStatus, CrmStatus, UserRole
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


class RoomShort(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    slug: str
    name: str


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
    created_at: datetime
    cancelled_at: datetime | None

    @computed_field
    @property
    def display_status(self) -> DisplayStatus:
        return display_status(self.status, self.check_in, self.check_out, hotel_time.hotel_today())


class GuestBookingDetail(BaseModel):
    booking: GuestBookingOut
    events: list[BookingEventOut]
    # Дедлайн бесплатной отмены — только у подтверждённой брони; can_cancel учитывает и статус, и время.
    cancel_deadline: datetime | None
    can_cancel: bool


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
