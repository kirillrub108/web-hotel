"""Правила брони без обращений к БД: цена и скидка по промокоду, авто-решение по новой заявке, отображаемый статус,
тексты причин.

Все факты приходят аргументами, поэтому правила проверяются табличными тестами без базы.
"""
import os
from dataclasses import dataclass
from datetime import date
from enum import StrEnum

from app.models import BookingStatus, CrmStatus, Promo, PromoKind

AUTO_CONFIRM_MAX_NIGHTS = int(os.getenv("AUTO_CONFIRM_MAX_NIGHTS", "7"))
AUTO_CONFIRM_MAX_TOTAL = int(os.getenv("AUTO_CONFIRM_MAX_TOTAL", "60000"))
AUTO_CONFIRM_MAX_LEAD_DAYS = int(os.getenv("AUTO_CONFIRM_MAX_LEAD_DAYS", "180"))
# Потолок процентной скидки: акция «−80%» всё равно даёт не больше половины стоимости проживания.
PROMO_MAX_PERCENT = int(os.getenv("PROMO_MAX_PERCENT", "50"))


def rubles(amount: int) -> str:
    """60000 → «60 000 ₽» с неразрывными пробелами."""
    return f"{amount:,}".replace(",", " ") + " ₽"


class Reason(StrEnum):
    AUTO_OK = "auto_ok"
    CLIENT_BLOCKED = "client_blocked"
    PENDING_CONFLICT = "pending_conflict"
    LONG_STAY = "long_stay"
    HIGH_TOTAL = "high_total"
    SAME_DAY = "same_day"
    FAR_FUTURE = "far_future"
    HAS_COMMENT = "has_comment"
    EXPIRED = "expired"
    DATES_TAKEN = "dates_taken"


# Тексты причин для гостя и администратора: в API, письмах и журнале показываются они, а не коды.
REASON_TEXTS: dict[str, str] = {
    Reason.AUTO_OK: "Даты свободны — бронь подтверждена автоматически",
    # Нейтральный текст: гость не должен узнать о внутренней отметке. Код причины видит только администратор.
    Reason.CLIENT_BLOCKED: "Не можем подтвердить бронирование онлайн — свяжитесь с отелем",
    Reason.PENDING_CONFLICT: "На эти даты уже есть другая заявка на этот номер",
    Reason.LONG_STAY: f"Проживание дольше {AUTO_CONFIRM_MAX_NIGHTS} ночей",
    Reason.HIGH_TOTAL: f"Сумма больше {rubles(AUTO_CONFIRM_MAX_TOTAL)}, а проживаний у нас ещё не было",
    Reason.SAME_DAY: "Заезд сегодня — администратор проверит готовность номера",
    Reason.FAR_FUTURE: f"Заезд больше чем через {AUTO_CONFIRM_MAX_LEAD_DAYS} дней",
    Reason.HAS_COMMENT: "К заявке есть комментарий — его прочитает администратор",
    Reason.EXPIRED: "Дата заезда наступила, а заявку не успели рассмотреть",
    Reason.DATES_TAKEN: "Эти даты заняла другая бронь",
}


def reason_texts(codes: list[str], text: str | None) -> list[str]:
    """Причины простыми словами: тексты по кодам и свободный текст администратора, если он есть."""
    return [REASON_TEXTS[code] for code in codes] + ([text] if text else [])


@dataclass(frozen=True)
class Price:
    nights: int
    price_per_night: int
    subtotal: int
    discount: int
    total: int


def promo_discount(promo: Promo, subtotal: int) -> int:
    """Скидка акции в рублях. Процентная — не больше PROMO_MAX_PERCENT от стоимости проживания,
    фиксированная — не больше самой стоимости, поэтому итог никогда не уходит в минус."""
    if promo.kind == PromoKind.PERCENT:
        return min(subtotal * promo.value // 100, subtotal * PROMO_MAX_PERCENT // 100)
    return min(promo.value, subtotal)


def calculate_price(price_per_night: int, check_in: date, check_out: date, promo: Promo | None = None) -> Price:
    """Единственный расчёт цены: им пользуются и котировка, и создание брони.

    Применимость акции здесь не проверяется — это делает promo_refusal; сюда приходит уже проверенная акция.
    """
    nights = (check_out - check_in).days
    subtotal = nights * price_per_night
    discount = promo_discount(promo, subtotal) if promo else 0
    return Price(nights, price_per_night, subtotal, discount, subtotal - discount)


def promo_refusal(
    promo: Promo, *, user_id: int | None, room_id: int, nights: int, today: date, in_use: bool
) -> str | None:
    """Почему промокод нельзя применить, или None, если можно. Тексты показываются гостю как есть.

    Порядок: сначала владелец — чужой персональный код не должен раскрывать условия акции.
    in_use — код уже занят бронью в статусе pending или confirmed (код одноразовый).
    """
    if promo.user_id is not None and promo.user_id != user_id:
        return "Этот промокод недоступен для вашего аккаунта"
    if not promo.is_active:
        return "Акция больше не действует"
    if today < promo.valid_from:
        return f"Акция начнётся {promo.valid_from:%d.%m.%Y}"
    if today > promo.valid_to:
        return f"Срок действия промокода истёк {promo.valid_to:%d.%m.%Y}"
    if nights < promo.min_nights:
        return f"Минимум ночей для этого промокода: {promo.min_nights}"
    if promo.room_id is not None and promo.room_id != room_id:
        return "Промокод действует только для другого номера"
    if in_use:
        return "Этот промокод уже использован в другой брони"
    return None


class Segment(StrEnum):
    """Сегмент клиента в CRM: считается по числу завершённых проживаний и нигде не хранится."""

    NEW = "new"
    GUEST = "guest"
    REGULAR = "regular"


REGULAR_MIN_STAYS = 2


def client_segment(completed_stays: int) -> Segment:
    if completed_stays == 0:
        return Segment.NEW
    return Segment.REGULAR if completed_stays >= REGULAR_MIN_STAYS else Segment.GUEST


@dataclass(frozen=True)
class Decision:
    # CONFIRMED — подтвердить, DECLINED — отклонить, PENDING — оставить на ручной разбор.
    status: BookingStatus
    reasons: list[Reason]


def decide(
    *,
    crm_status: str,
    nights: int,
    total: int,
    check_in: date,
    today: date,
    has_comment: bool,
    has_completed_stay: bool,
    has_pending_conflict: bool,
) -> Decision:
    """Авто-решение по новой заявке.

    Порядок проверки: отказ → ручной разбор → подтверждение. Отказ первым, потому что он окончательный
    и причины разбора для отклонённой брони ничего не значат. Причины разбора собираются все, а не первая:
    администратор сразу видит, что именно проверить. Подтверждение — только если не сработало ни одно правило.
    """
    if crm_status == CrmStatus.BLOCKED:
        return Decision(BookingStatus.DECLINED, [Reason.CLIENT_BLOCKED])

    # VIP-клиенту отель доверяет: длительность, сумма и дальний заезд для него не повод для проверки.
    is_vip = crm_status == CrmStatus.VIP
    reasons: list[Reason] = []
    if has_pending_conflict:
        reasons.append(Reason.PENDING_CONFLICT)
    if not is_vip and nights > AUTO_CONFIRM_MAX_NIGHTS:
        reasons.append(Reason.LONG_STAY)
    if not is_vip and total > AUTO_CONFIRM_MAX_TOTAL and not has_completed_stay:
        reasons.append(Reason.HIGH_TOTAL)
    if check_in == today:
        reasons.append(Reason.SAME_DAY)
    if not is_vip and (check_in - today).days > AUTO_CONFIRM_MAX_LEAD_DAYS:
        reasons.append(Reason.FAR_FUTURE)
    if has_comment:
        reasons.append(Reason.HAS_COMMENT)

    if reasons:
        return Decision(BookingStatus.PENDING, reasons)
    return Decision(BookingStatus.CONFIRMED, [Reason.AUTO_OK])


class DisplayStatus(StrEnum):
    """Статус для показа: «Проживание» и «Завершена» вычисляются из подтверждённой брони и не хранятся."""

    PENDING = "pending"
    CONFIRMED = "confirmed"
    IN_STAY = "in_stay"
    COMPLETED = "completed"
    DECLINED = "declined"
    CANCELLED = "cancelled"


def display_status(status: str, check_in: date, check_out: date, today: date) -> DisplayStatus:
    if status == BookingStatus.CONFIRMED:
        if today >= check_out:
            return DisplayStatus.COMPLETED
        if today >= check_in:
            return DisplayStatus.IN_STAY
    return DisplayStatus(status)
