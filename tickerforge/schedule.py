from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import yaml
from dateutil.easter import easter

WEEKDAY_MAP = {
    "monday": 0,
    "tuesday": 1,
    "wednesday": 2,
    "thursday": 3,
    "friday": 4,
}


def _nth_weekday_of_month(year: int, month: int, weekday: int, nth: int) -> date:
    first = date(year, month, 1)
    diff = (weekday - first.weekday()) % 7
    first_occ = first + timedelta(days=diff)
    return first_occ + timedelta(weeks=nth - 1)


def _last_weekday_of_month(year: int, month: int, weekday: int) -> date:
    if month == 12:
        last_day = date(year + 1, 1, 1) - timedelta(days=1)
    else:
        last_day = date(year, month + 1, 1) - timedelta(days=1)
    diff = (last_day.weekday() - weekday) % 7
    return last_day - timedelta(days=diff)


def _rule_applies(rule: dict, year: int) -> bool:
    if "from_year" in rule and year < rule["from_year"]:
        return False
    if "to_year" in rule and year > rule["to_year"]:
        return False
    return True


class ExchangeSchedule:
    def __init__(self, data: dict) -> None:
        self.exchange: str = data["exchange"]
        self.timezone: str = data["timezone"]
        self._holidays = data.get("holidays", {})
        self._early_closes = data.get("early_closes", {})
        self._holiday_cache: dict[int, set[date]] = {}
        self._early_close_cache: dict[int, dict[date, str]] = {}

    def holidays_for_year(self, year: int) -> set[date]:
        if year in self._holiday_cache:
            return self._holiday_cache[year]

        holidays: set[date] = set()
        easter_sunday = easter(year)

        for rule in self._holidays.get("fixed", []):
            if not _rule_applies(rule, year):
                continue
            holidays.add(date(year, rule["month"], rule["day"]))

        for rule in self._holidays.get("easter_offset", []):
            if not _rule_applies(rule, year):
                continue
            holidays.add(easter_sunday + timedelta(days=rule["offset"]))

        for rule in self._holidays.get("nth_weekday", []):
            if not _rule_applies(rule, year):
                continue
            wd = WEEKDAY_MAP[rule["weekday"]]
            holidays.add(_nth_weekday_of_month(year, rule["month"], wd, rule["nth"]))

        for rule in self._holidays.get("last_weekday", []):
            if not _rule_applies(rule, year):
                continue
            wd = WEEKDAY_MAP[rule["weekday"]]
            holidays.add(_last_weekday_of_month(year, rule["month"], wd))

        for rule in self._holidays.get("overrides", []):
            d = date.fromisoformat(rule["date"])
            if d.year != year:
                continue
            if rule["action"] == "add":
                holidays.add(d)
            elif rule["action"] == "remove":
                holidays.discard(d)

        holidays = {d for d in holidays if d.weekday() < 5}
        self._holiday_cache[year] = holidays
        return holidays

    def early_closes_for_year(self, year: int) -> dict[date, str]:
        if year in self._early_close_cache:
            return self._early_close_cache[year]

        result: dict[date, str] = {}
        easter_sunday = easter(year)

        for rule in self._early_closes.get("fixed", []):
            if not _rule_applies(rule, year):
                continue
            d = date(year, rule["month"], rule["day"])
            if d.weekday() < 5:
                result[d] = rule["open"]

        for rule in self._early_closes.get("easter_offset", []):
            if not _rule_applies(rule, year):
                continue
            d = easter_sunday + timedelta(days=rule["offset"])
            if d.weekday() < 5:
                result[d] = rule["open"]

        self._early_close_cache[year] = result
        return result

    def is_early_close(self, d: date) -> bool:
        return d in self.early_closes_for_year(d.year)

    def early_close_time(self, d: date) -> str | None:
        return self.early_closes_for_year(d.year).get(d)

    def is_session(self, d: date) -> bool:
        if d.weekday() >= 5:
            return False
        return d not in self.holidays_for_year(d.year)

    def sessions_in_range(self, start: date, end: date) -> list[date]:
        result: list[date] = []
        current = start
        one_day = timedelta(days=1)
        while current <= end:
            if self.is_session(current):
                result.append(current)
            current += one_day
        return result


class SpecCalendar:
    """Wraps ExchangeSchedule to expose the interface expected by expiration_rules.py."""

    def __init__(self, schedule: ExchangeSchedule) -> None:
        self._schedule = schedule
        first = date(1990, 1, 1)
        while not schedule.is_session(first):
            first += timedelta(days=1)
        self._first_session = first

        last = date(2035, 12, 31)
        while not schedule.is_session(last):
            last -= timedelta(days=1)
        self._last_session = last

    @property
    def first_session(self) -> _DateWrapper:
        return _DateWrapper(self._first_session)

    @property
    def last_session(self) -> _DateWrapper:
        return _DateWrapper(self._last_session)

    def sessions_in_range(
        self, start: str | date, end: str | date
    ) -> list[_DateWrapper]:
        s = date.fromisoformat(str(start)) if isinstance(start, str) else start
        e = date.fromisoformat(str(end)) if isinstance(end, str) else end
        return [_DateWrapper(d) for d in self._schedule.sessions_in_range(s, e)]

    def is_early_close(self, d: date) -> bool:
        return self._schedule.is_early_close(d)

    def early_close_time(self, d: date) -> str | None:
        return self._schedule.early_close_time(d)


class _DateWrapper:
    """Mimics the pandas.Timestamp interface that exchange_calendars returns."""

    def __init__(self, d: date) -> None:
        self._date = d

    def date(self) -> date:
        return self._date

    def __repr__(self) -> str:
        return f"_DateWrapper({self._date})"


def load_schedule(path: Path) -> ExchangeSchedule:
    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"Expected YAML mapping in {path}")
    return ExchangeSchedule(data)


def load_schedules(spec_root: Path) -> dict[str, ExchangeSchedule]:
    schedules_dir = spec_root / "schedules"
    result: dict[str, ExchangeSchedule] = {}
    if not schedules_dir.is_dir():
        return result
    for yaml_path in sorted(schedules_dir.glob("*.yaml")):
        schedule = load_schedule(yaml_path)
        result[schedule.exchange.upper()] = schedule
    return result
