from datetime import date, timedelta

import pytest

from app.booking_rules import (
    AUTO_CONFIRM_MAX_LEAD_DAYS,
    AUTO_CONFIRM_MAX_NIGHTS,
    AUTO_CONFIRM_MAX_TOTAL,
    REASON_TEXTS,
    Decision,
    DisplayStatus,
    Price,
    Reason,
    calculate_price,
    decide,
    display_status,
    reason_texts,
)
from app.models import BookingStatus, CrmStatus

TODAY = date(2026, 10, 1)
CONFIRMED = Decision(BookingStatus.CONFIRMED, [Reason.AUTO_OK])


def facts(**overrides: object) -> dict[str, object]:
    """Факты обычной заявки, которую движок подтверждает; тест меняет только то, что проверяет."""
    base: dict[str, object] = {
        "crm_status": CrmStatus.REGULAR,
        "nights": 2,
        "total": 9000,
        "check_in": TODAY + timedelta(days=10),
        "today": TODAY,
        "has_comment": False,
        "has_completed_stay": False,
        "has_pending_conflict": False,
    }
    base.update(overrides)
    return base


def review(*reasons: Reason) -> Decision:
    return Decision(BookingStatus.PENDING, list(reasons))


@pytest.mark.parametrize(
    ("overrides", "expected"),
    [
        ({}, CONFIRMED),
        ({"crm_status": CrmStatus.BLOCKED}, Decision(BookingStatus.DECLINED, [Reason.CLIENT_BLOCKED])),
        (
            {"crm_status": CrmStatus.BLOCKED, "has_comment": True, "nights": AUTO_CONFIRM_MAX_NIGHTS + 1},
            Decision(BookingStatus.DECLINED, [Reason.CLIENT_BLOCKED]),
        ),
        ({"has_pending_conflict": True}, review(Reason.PENDING_CONFLICT)),
        ({"nights": AUTO_CONFIRM_MAX_NIGHTS + 1}, review(Reason.LONG_STAY)),
        ({"nights": AUTO_CONFIRM_MAX_NIGHTS}, CONFIRMED),
        ({"total": AUTO_CONFIRM_MAX_TOTAL + 1}, review(Reason.HIGH_TOTAL)),
        ({"total": AUTO_CONFIRM_MAX_TOTAL}, CONFIRMED),
        ({"total": AUTO_CONFIRM_MAX_TOTAL + 1, "has_completed_stay": True}, CONFIRMED),
        ({"check_in": TODAY}, review(Reason.SAME_DAY)),
        ({"check_in": TODAY + timedelta(days=AUTO_CONFIRM_MAX_LEAD_DAYS + 1)}, review(Reason.FAR_FUTURE)),
        ({"check_in": TODAY + timedelta(days=AUTO_CONFIRM_MAX_LEAD_DAYS)}, CONFIRMED),
        ({"has_comment": True}, review(Reason.HAS_COMMENT)),
    ],
    ids=[
        "auto_ok",
        "client_blocked",
        "decline_wins_over_review",
        "pending_conflict",
        "long_stay",
        "max_nights_is_still_auto",
        "high_total",
        "max_total_is_still_auto",
        "high_total_with_completed_stay",
        "same_day",
        "far_future",
        "max_lead_is_still_auto",
        "has_comment",
    ],
)
def test_decide_rules(overrides: dict[str, object], expected: Decision) -> None:
    assert decide(**facts(**overrides)) == expected


@pytest.mark.parametrize(
    ("overrides", "expected"),
    [
        ({"nights": AUTO_CONFIRM_MAX_NIGHTS + 1}, CONFIRMED),
        ({"total": AUTO_CONFIRM_MAX_TOTAL + 1}, CONFIRMED),
        ({"check_in": TODAY + timedelta(days=AUTO_CONFIRM_MAX_LEAD_DAYS + 1)}, CONFIRMED),
        ({"has_pending_conflict": True}, review(Reason.PENDING_CONFLICT)),
        ({"check_in": TODAY}, review(Reason.SAME_DAY)),
        ({"has_comment": True}, review(Reason.HAS_COMMENT)),
    ],
    ids=[
        "long_stay_skipped",
        "high_total_skipped",
        "far_future_skipped",
        "pending_conflict",
        "same_day",
        "has_comment",
    ],
)
def test_vip_skips_only_stay_total_and_lead_rules(overrides: dict[str, object], expected: Decision) -> None:
    assert decide(**facts(crm_status=CrmStatus.VIP, **overrides)) == expected


@pytest.mark.parametrize(
    ("check_in", "date_reason"),
    [
        (TODAY, Reason.SAME_DAY),
        (TODAY + timedelta(days=AUTO_CONFIRM_MAX_LEAD_DAYS + 1), Reason.FAR_FUTURE),
    ],
    ids=["with_same_day", "with_far_future"],
)
def test_decide_collects_every_review_reason(check_in: date, date_reason: Reason) -> None:
    decision = decide(
        **facts(
            has_pending_conflict=True,
            nights=AUTO_CONFIRM_MAX_NIGHTS + 1,
            total=AUTO_CONFIRM_MAX_TOTAL + 1,
            check_in=check_in,
            has_comment=True,
        )
    )
    assert decision == review(
        Reason.PENDING_CONFLICT, Reason.LONG_STAY, Reason.HIGH_TOTAL, date_reason, Reason.HAS_COMMENT
    )


def test_calculate_price() -> None:
    assert calculate_price(4500, TODAY, TODAY + timedelta(days=3)) == Price(
        nights=3, price_per_night=4500, subtotal=13500, discount=0, total=13500
    )


@pytest.mark.parametrize(
    ("status", "today", "expected"),
    [
        (BookingStatus.CONFIRMED, date(2026, 10, 9), DisplayStatus.CONFIRMED),
        (BookingStatus.CONFIRMED, date(2026, 10, 10), DisplayStatus.IN_STAY),
        (BookingStatus.CONFIRMED, date(2026, 10, 11), DisplayStatus.IN_STAY),
        (BookingStatus.CONFIRMED, date(2026, 10, 12), DisplayStatus.COMPLETED),
        (BookingStatus.PENDING, date(2026, 10, 12), DisplayStatus.PENDING),
        (BookingStatus.CANCELLED, date(2026, 10, 10), DisplayStatus.CANCELLED),
    ],
    ids=["before_stay", "check_in_day", "last_night", "check_out_day", "pending_stays_pending", "cancelled"],
)
def test_display_status(status: BookingStatus, today: date, expected: DisplayStatus) -> None:
    assert display_status(status, date(2026, 10, 10), date(2026, 10, 12), today) == expected


def test_every_reason_has_text() -> None:
    assert set(REASON_TEXTS) == set(Reason)


def test_reason_texts_append_admin_text() -> None:
    assert reason_texts([Reason.LONG_STAY], "Звонили, гость подтвердил даты") == [
        REASON_TEXTS[Reason.LONG_STAY],
        "Звонили, гость подтвердил даты",
    ]
