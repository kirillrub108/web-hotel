from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator

EMAIL_PATTERN = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"


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
    room_id: int
    guest_name: str = Field(min_length=2, max_length=120)
    phone: str = Field(min_length=5, max_length=40)
    email: str = Field(pattern=EMAIL_PATTERN, max_length=120)
    check_in: date
    check_out: date
    guests: int = Field(ge=1)
    comment: str | None = Field(default=None, max_length=1000)

    @model_validator(mode="after")
    def check_dates(self) -> "BookingCreate":
        if self.check_out <= self.check_in:
            raise ValueError("Дата выезда должна быть позже даты заезда")
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
    created_at: datetime
