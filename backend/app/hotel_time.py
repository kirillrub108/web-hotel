"""Время гостиницы. «Сегодня» для заездов, просрочки и дедлайнов везде считается здесь, в часовом поясе отеля:
по часам сервера (UTC) в первые часы московских суток была бы ещё вчерашняя дата.

Функции вызываются через модуль — hotel_time.hotel_today(): тесты подменяют hotel_now
и так «переводят часы» для всего приложения.
"""
import os
from datetime import date, datetime, time
from zoneinfo import ZoneInfo

HOTEL_TZ = ZoneInfo(os.getenv("HOTEL_TZ", "Europe/Moscow"))


def hotel_now() -> datetime:
    """Текущий момент в поясе отеля."""
    return datetime.now(HOTEL_TZ)


def hotel_today() -> date:
    return hotel_now().date()


def hotel_datetime(day: date, clock: str) -> datetime:
    """Момент «день + время по часам отеля», например дата заезда и время заезда «14:00»."""
    return datetime.combine(day, time.fromisoformat(clock), HOTEL_TZ)
