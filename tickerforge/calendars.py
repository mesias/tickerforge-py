from __future__ import annotations

from functools import lru_cache

import exchange_calendars as xcals

EXCHANGE_CALENDAR_ALIASES: dict[str, str] = {
    "B3": "BVMF",
    "CME": "CMES",
    "EUREX": "XEUR",
    "ICE": "IEPA",
}


def _resolve_calendar_name(exchange_code: str) -> str:
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
    calendar_name = _resolve_calendar_name(exchange_code)
    return xcals.get_calendar(calendar_name)
