import re
from datetime import date, datetime
from typing import Annotated

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, StringConstraints, field_validator, model_validator

from app.models import BookingStatus, UserRole
from app.passwords import PASSWORD_MAX_LENGTH

EMAIL_PATTERN = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"
MAX_CHECK_IN_ADVANCE_DAYS = 365
MAX_STAY_NIGHTS = 90


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


class BookingCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    room_id: int
    guest_name: str = Field(min_length=2, max_length=120)
    phone: str = Field(max_length=40)
    email: str = Field(pattern=EMAIL_PATTERN, max_length=120)
    check_in: date
    check_out: date
    guests: int = Field(ge=1, le=20)
    comment: str | None = Field(default=None, max_length=1000)

    @field_validator("phone")
    @classmethod
    def check_phone(cls, value: str) -> str:
        return validate_phone(value)

    @model_validator(mode="after")
    def check_dates(self) -> "BookingCreate":
        # ponytail: «сегодня» по часам сервера (UTC); в первые часы суток по Москве
        # примется и вчерашняя дата. Нужна точность — сравнивать в часовом поясе гостиницы.
        if self.check_in < date.today():
            raise ValueError("Дата заезда не может быть в прошлом")
        if (self.check_in - date.today()).days > MAX_CHECK_IN_ADVANCE_DAYS:
            raise ValueError("Дата заезда не может быть позже, чем через год")
        if self.check_out <= self.check_in:
            raise ValueError("Дата выезда должна быть позже даты заезда")
        if (self.check_out - self.check_in).days > MAX_STAY_NIGHTS:
            raise ValueError(f"Максимальная длительность проживания — {MAX_STAY_NIGHTS} ночей")
        return self


class BookingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    room_id: int
    guest_name: str
    phone: str
    email: str
    check_in: date
    check_out: date
    guests: int
    comment: str | None
    status: BookingStatus
    created_at: datetime


class RoomShort(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    slug: str
    name: str


class AdminBookingOut(BookingOut):
    room: RoomShort


class AdminBookingPage(BaseModel):
    items: list[AdminBookingOut]
    total: int


class BookingStatusUpdate(BaseModel):
    status: BookingStatus


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
