"""CRM: показатели клиентов считаются запросом из броней и нигде не хранятся.

client_select — один запрос на всех клиентов (агрегация по броням, без N+1): и для списка, и для карточки.
"""

from datetime import date, datetime

from sqlalchemy import Row, Select, and_, exists, func, or_, select
from sqlalchemy.sql import ColumnElement

from app import hotel_time
from app.models import Booking, BookingStatus, User, UserRole


def digits(value: ColumnElement[str]) -> ColumnElement[str]:
    """Только цифры телефона: «+7 (900) 123-45-67» → «79001234567»."""
    return func.regexp_replace(value, r"\D", "", "g")


def escape_like(text: str) -> str:
    return text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def search_condition(text: str) -> ColumnElement[bool]:
    """Поиск по имени, email и телефону: регистр не важен, телефон — по цифрам, как бы его ни записали.

    Телефон берётся из профиля и из броней клиента: в профиле его может не быть.
    """
    pattern = f"%{escape_like(text.strip())}%"
    conditions = [User.full_name.ilike(pattern), User.email.ilike(pattern)]
    phone_digits = "".join(ch for ch in text if ch.isdigit())
    if len(phone_digits) >= 3:
        digits_pattern = f"%{phone_digits}%"
        conditions.append(digits(func.coalesce(User.phone, "")).like(digits_pattern))
        conditions.append(exists().where(Booking.user_id == User.id, digits(Booking.phone).like(digits_pattern)))
    return or_(*conditions)


def client_select() -> Select[tuple[User, int, int, int, date | None, datetime]]:
    """Клиенты (role=guest) с показателями. Условия, сортировка и пагинация добавляются снаружи."""
    today = hotel_time.hotel_today()
    completed = and_(Booking.status == BookingStatus.CONFIRMED, Booking.check_out <= today)
    stats = (
        select(
            Booking.user_id.label("user_id"),
            func.count().filter(completed).label("stays"),
            func.coalesce(func.sum(Booking.nights).filter(completed), 0).label("nights"),
            func.coalesce(func.sum(Booking.total_price).filter(Booking.status == BookingStatus.CONFIRMED), 0).label(
                "revenue"
            ),
            func.max(Booking.check_out).filter(completed).label("last_stay_at"),
            func.max(Booking.created_at).label("last_booking_at"),
        )
        .group_by(Booking.user_id)
        .subquery()
    )
    # Последняя активность: самое позднее из регистрации, входа и создания брони (GREATEST игнорирует NULL).
    last_activity = func.greatest(User.created_at, User.last_login_at, stats.c.last_booking_at)
    return (
        select(
            User,
            func.coalesce(stats.c.stays, 0).label("stays"),
            func.coalesce(stats.c.nights, 0).label("nights"),
            func.coalesce(stats.c.revenue, 0).label("revenue"),
            stats.c.last_stay_at.label("last_stay_at"),
            last_activity.label("last_activity_at"),
        )
        .outerjoin(stats, stats.c.user_id == User.id)
        .where(User.role == UserRole.GUEST)
    )


def client_dict(row: Row[tuple[User, int, int, int, date | None, datetime]]) -> dict[str, object]:
    """Строка client_select в виде словаря для схемы ClientOut."""
    user = row.User
    return {
        "id": user.id,
        "email": user.email,
        "full_name": user.full_name,
        "phone": user.phone,
        "crm_status": user.crm_status,
        "crm_note": user.crm_note,
        "created_at": user.created_at,
        "last_activity_at": row.last_activity_at,
        "stays": row.stays,
        "nights": row.nights,
        "revenue": row.revenue,
        "last_stay_at": row.last_stay_at,
    }
