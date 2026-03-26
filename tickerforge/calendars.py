from __future__ import annotations

from functools import lru_cache
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from tickerforge.schedule import ExchangeSchedule

try:
    import exchange_calendars as xcals
except ImportError:  # pragma: no cover
    xcals = None  # type: ignore[assignment,unused-ignore]

EXCHANGE_CALENDAR_ALIASES: dict[str, str] = {
    "B3": "BVMF",
    "CME": "CMES",
    "EUREX": "XEUR",
    "ICE": "IEPA",
}

_SCHEDULES: dict[str, ExchangeSchedule] = {}


def register_schedules(schedules: dict[str, ExchangeSchedule]) -> None:
    _SCHEDULES.update(schedules)
    get_calendar.cache_clear()


def _resolve_calendar_name(exchange_code: str) -> str:
    if xcals is None:
        raise RuntimeError(
            "exchange_calendars is not installed and no spec schedule is available "
            f"for exchange '{exchange_code}'"
        )
    code = exchange_code.upper()
    candidates = [EXCHANGE_CALENDAR_ALIASES.get(code), code]

    for candidate in candidates:
        if not candidate:
            continue
        try:
            xcals.get_calendar(candidate)
            return candidate
        except Exception:
            continue

    for name in xcals.get_calendar_names():
        if name.upper() == code:
            return name

    raise ValueError(f"No calendar found for exchange '{exchange_code}'")


@lru_cache(maxsize=16)
def get_calendar(exchange_code: str):
    code = exchange_code.upper()
    if code in _SCHEDULES:
        from tickerforge.schedule import SpecCalendar

        return SpecCalendar(_SCHEDULES[code])

    calendar_name = _resolve_calendar_name(exchange_code)
    return xcals.get_calendar(calendar_name)
