from __future__ import annotations

from calendar import monthrange
from datetime import date

from tickerforge.models import ContractSpec, ExpirationRule

WEEKDAY_NAME_TO_NUMBER = {
    "monday": 0,
    "tuesday": 1,
    "wednesday": 2,
    "thursday": 3,
    "friday": 4,
    "saturday": 5,
    "sunday": 6,
}


def _month_sessions(calendar, year: int, month: int) -> list[date]:
    last_day = monthrange(year, month)[1]
    month_start = date(year, month, 1)
    month_end = date(year, month, last_day)
    cal_first = calendar.first_session.date()
    cal_last = calendar.last_session.date()
    if month_end < cal_first or month_start > cal_last:
        return []
    clip_start = max(month_start, cal_first)
    clip_end = min(month_end, cal_last)
    if clip_start > clip_end:
        return []
    sessions = calendar.sessions_in_range(
        clip_start.isoformat(),
        clip_end.isoformat(),
    )
    return [session.date() for session in sessions]


def _resolve_first_business_day(calendar, year: int, month: int) -> date:
    sessions = _month_sessions(calendar, year, month)
    return sessions[0]


def _resolve_last_business_day(calendar, year: int, month: int) -> date:
    sessions = _month_sessions(calendar, year, month)
    return sessions[-1]


def _resolve_nth_business_day(calendar, year: int, month: int, n: int) -> date:
    sessions = _month_sessions(calendar, year, month)
    if n < 1 or n > len(sessions):
        raise ValueError(f"Invalid nth business day '{n}' for {year}-{month:02d}")
    return sessions[n - 1]


def _resolve_fixed_day(calendar, year: int, month: int, day: int) -> date:
    last_day = monthrange(year, month)[1]
    target = date(year, month, min(day, last_day))
    sessions = _month_sessions(calendar, year, month)
    for session_day in sessions:
        if session_day >= target:
            return session_day
    return sessions[-1]


def _resolve_nearest_weekday_to_day(
    calendar,
    year: int,
    month: int,
    weekday_name: str,
    day: int,
) -> date:
    weekday_number = WEEKDAY_NAME_TO_NUMBER[weekday_name.lower()]
    sessions = _month_sessions(calendar, year, month)
    weekday_sessions = [
        session_day
        for session_day in sessions
        if session_day.weekday() == weekday_number
    ]
    if not weekday_sessions:
        raise ValueError(
            f"No sessions on weekday '{weekday_name}' for {year}-{month:02d}"
        )

    last_day = monthrange(year, month)[1]
    target = date(year, month, min(day, last_day))
    return min(weekday_sessions, key=lambda value: (abs((value - target).days), value))


def _resolve_nth_weekday_of_month(
    calendar,
    year: int,
    month: int,
    weekday_name: str,
    n: int,
) -> date:
    weekday_number = WEEKDAY_NAME_TO_NUMBER[weekday_name.lower()]
    sessions = _month_sessions(calendar, year, month)
    weekday_sessions = [
        session_day
        for session_day in sessions
        if session_day.weekday() == weekday_number
    ]
    if n < 1 or n > len(weekday_sessions):
        raise ValueError(
            f"Invalid nth weekday '{n}' for weekday '{weekday_name}' "
            f"in {year}-{month:02d}"
        )
    return weekday_sessions[n - 1]


def _resolve_last_weekday_of_month(
    calendar,
    year: int,
    month: int,
    weekday_name: str,
) -> date:
    weekday_number = WEEKDAY_NAME_TO_NUMBER[weekday_name.lower()]
    sessions = _month_sessions(calendar, year, month)
    weekday_sessions = [
        session_day
        for session_day in sessions
        if session_day.weekday() == weekday_number
    ]
    if not weekday_sessions:
        raise ValueError(
            f"No sessions on weekday '{weekday_name}' for {year}-{month:02d}"
        )
    return weekday_sessions[-1]


def _resolve_second_business_day_prior_to_month(
    calendar,
    year: int,
    month: int,
) -> date:
    prev_year = year
    prev_month = month - 1
    if prev_month == 0:
        prev_month = 12
        prev_year -= 1
    sessions = _month_sessions(calendar, prev_year, prev_month)
    if len(sessions) < 2:
        raise ValueError(
            f"Not enough sessions in preceding month for {year}-{month:02d}"
        )
    return sessions[-2]


def _resolve_business_day_prior_to_day_of_preceding_month(
    calendar,
    year: int,
    month: int,
    day: int,
) -> date:
    prev_year = year
    prev_month = month - 1
    if prev_month == 0:
        prev_month = 12
        prev_year -= 1
    from calendar import monthrange

    last_day = monthrange(prev_year, prev_month)[1]
    target = date(prev_year, prev_month, min(day, last_day))
    sessions = [
        s for s in _month_sessions(calendar, prev_year, prev_month) if s < target
    ]
    if not sessions:
        raise ValueError("No sessions found before target day in preceding month")
    return sessions[-1]


def _resolve_nth_business_day_from_end(
    calendar,
    year: int,
    month: int,
    n: int,
) -> date:
    sessions = _month_sessions(calendar, year, month)
    if n < 1 or n > len(sessions):
        raise ValueError(
            f"Invalid nth business day from end '{n}' for {year}-{month:02d}"
        )
    return sessions[-n]


def resolve_expiration(
    contract: ContractSpec,
    year: int,
    month: int,
    expiration_rule: ExpirationRule,
    calendar,
) -> date:
    # Expiration can be rule-based; kept for future product-specific logic.
    del contract

    rule_type = expiration_rule.type
    if rule_type == "first_business_day":
        return _resolve_first_business_day(calendar, year, month)
    if rule_type == "last_business_day":
        return _resolve_last_business_day(calendar, year, month)
    if rule_type == "nth_business_day":
        if expiration_rule.n is None:
            raise ValueError("nth_business_day rule requires 'n'")
        return _resolve_nth_business_day(calendar, year, month, expiration_rule.n)
    if rule_type == "fixed_day":
        if expiration_rule.day is None:
            raise ValueError("fixed_day rule requires 'day'")
        return _resolve_fixed_day(calendar, year, month, expiration_rule.day)
    if rule_type == "nearest_weekday_to_day":
        if expiration_rule.weekday is None or expiration_rule.day is None:
            raise ValueError("nearest_weekday_to_day rule requires 'weekday' and 'day'")
        return _resolve_nearest_weekday_to_day(
            calendar,
            year,
            month,
            expiration_rule.weekday,
            expiration_rule.day,
        )
    if rule_type == "nth_weekday_of_month":
        if expiration_rule.weekday is None or expiration_rule.n is None:
            raise ValueError("nth_weekday_of_month rule requires 'weekday' and 'n'")
        return _resolve_nth_weekday_of_month(
            calendar,
            year,
            month,
            expiration_rule.weekday,
            expiration_rule.n,
        )
    if rule_type == "last_weekday_of_month":
        if expiration_rule.weekday is None:
            raise ValueError("last_weekday_of_month rule requires 'weekday'")
        return _resolve_last_weekday_of_month(
            calendar,
            year,
            month,
            expiration_rule.weekday,
        )
    if rule_type == "second_business_day_prior_to_month":
        return _resolve_second_business_day_prior_to_month(
            calendar,
            year,
            month,
        )
    if rule_type == "business_day_prior_to_day_of_preceding_month":
        if expiration_rule.day is None:
            raise ValueError(
                "business_day_prior_to_day_of_preceding_month rule requires 'day'"
            )
        return _resolve_business_day_prior_to_day_of_preceding_month(
            calendar,
            year,
            month,
            expiration_rule.day,
        )
    if rule_type == "nth_business_day_from_end":
        if expiration_rule.n is None:
            raise ValueError("nth_business_day_from_end rule requires 'n'")
        return _resolve_nth_business_day_from_end(
            calendar,
            year,
            month,
            expiration_rule.n,
        )
    if rule_type == "schedule":
        raise NotImplementedError(
            "schedule expiration rules need external schedule data"
        )

    raise ValueError(f"Unsupported expiration rule type: {rule_type}")
