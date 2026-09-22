import re
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models import BookingStatus

EMAIL_PATTERN = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"
MAX_CHECK_IN_ADVANCE_DAYS = 365
MAX_STAY_NIGHTS = 90


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
        if not 10 <= len(re.sub(r"\D", "", value)) <= 15:
            raise ValueError("Укажите телефон полностью, например +7 900 000-00-00")
        return value

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


class AdminLogin(BaseModel):
    username: str = Field(max_length=120)
    password: str = Field(max_length=200)
