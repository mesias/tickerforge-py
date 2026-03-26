from __future__ import annotations

import csv
import lzma
from datetime import date
from pathlib import Path

import pytest

from tickerforge import TickerForge
from tickerforge.calendars import get_calendar
from tickerforge.schedule import load_schedule

_DATE_MIN = date(2023, 1, 1)
# BVMF in exchange_calendars ends ~Mar 2027 and omits sessions past that horizon, so
# generate() cannot match 2027–2028 golden rows yet. Raise when a newer calendar ships.
_DATE_MAX = date(2026, 12, 31)


def _spec_root() -> Path:
    py_root = Path(__file__).resolve().parents[1]
    for candidate in (py_root / "spec", py_root.parent / "tickerforge-spec" / "spec"):
        if candidate.is_dir() and (candidate / "contracts").is_dir():
            return candidate
    raise FileNotFoundError(
        "Spec not found. Copy tickerforge-spec/spec into tickerforge-py/spec, or place "
        "tickerforge-spec alongside tickerforge-py in the same parent directory."
    )


def _calendar_xz_path() -> Path:
    p = _spec_root() / "tests" / "b3" / "B3_2023_2028_WIN_IND_DOL_calendar_FIXED.csv.xz"
    if not p.is_file():
        pytest.skip(f"Missing golden calendar fixture: {p}")
    return p


@pytest.fixture(scope="module")
def forge() -> TickerForge:
    return TickerForge(spec_path=str(_spec_root()))


def test_b3_win_ind_dol_calendar_matches_generator(forge: TickerForge) -> None:
    """Golden WIN/IND/DOL names vs generate(); rows with empty names are non-trading days.

    BVMF data in exchange_calendars often disagrees with the official golden calendar
    (missing or extra holidays), so we do not assert is_session here.
    """
    cal = get_calendar("B3")
    cal_first = cal.first_session.date()
    cal_last = cal.last_session.date()
    path = _calendar_xz_path()
    with lzma.open(path, "rt", encoding="utf-8") as handle:
        reader = csv.DictReader(handle, delimiter=";")
        for row in reader:
            row_date = date.fromisoformat(row["date"])
            if not (_DATE_MIN <= row_date <= _DATE_MAX):
                continue
            if not (cal_first <= row_date <= cal_last):
                continue

            win = row["WIN_name"].strip()
            ind = row["IND_name"].strip()
            dol = row["DOL_name"].strip()
            has_contracts = bool(win)
            assert bool(ind) == has_contracts, row
            assert bool(dol) == has_contracts, row

            if has_contracts:
                assert forge.generate("WIN", date=row_date) == win
                assert forge.generate("IND", date=row_date) == ind
                assert forge.generate("DOL", date=row_date) == dol


# Ash Wednesday = Easter - 46 days
_ASH_WEDNESDAY = {
    2023: date(2023, 2, 22),
    2024: date(2024, 2, 14),
    2025: date(2025, 3, 5),
    2026: date(2026, 2, 18),
}


@pytest.fixture(scope="module")
def b3_schedule():
    schedule_path = _spec_root() / "schedules" / "b3.yaml"
    if not schedule_path.is_file():
        pytest.skip(f"Missing schedule fixture: {schedule_path}")
    return load_schedule(schedule_path)


def test_b3_ash_wednesday_is_early_close(b3_schedule) -> None:
    """Ash Wednesday should be an early close with open at 13:00 for every year."""
    for year, ash_wed in _ASH_WEDNESDAY.items():
        assert b3_schedule.is_early_close(
            ash_wed
        ), f"Ash Wednesday {ash_wed} should be early close"
        assert (
            b3_schedule.early_close_time(ash_wed) == "13:00"
        ), f"Ash Wednesday {ash_wed} open time should be 13:00"


def test_b3_ash_wednesday_is_still_trading_session(b3_schedule) -> None:
    """Early-close days are trading sessions, not holidays."""
    for year, ash_wed in _ASH_WEDNESDAY.items():
        assert b3_schedule.is_session(
            ash_wed
        ), f"Ash Wednesday {ash_wed} should be a trading session"
        assert ash_wed not in b3_schedule.holidays_for_year(
            year
        ), f"Ash Wednesday {ash_wed} must not appear in holidays"


def test_b3_regular_day_not_early_close(b3_schedule) -> None:
    """A normal trading day should not be flagged as early close."""
    normal_day = date(2025, 6, 2)  # Monday
    assert b3_schedule.is_session(normal_day)
    assert not b3_schedule.is_early_close(normal_day)
    assert b3_schedule.early_close_time(normal_day) is None


def test_b3_holiday_not_early_close(b3_schedule) -> None:
    """A holiday is not a session and not an early close."""
    christmas = date(2025, 12, 25)  # Thursday
    assert not b3_schedule.is_session(christmas)
    assert not b3_schedule.is_early_close(christmas)


def test_b3_spec_calendar_early_close_passthrough(forge: TickerForge) -> None:
    """SpecCalendar pass-through mirrors ExchangeSchedule early-close methods."""
    cal = get_calendar("B3")
    ash_wed_2025 = date(2025, 3, 5)
    assert cal.is_early_close(ash_wed_2025)
    assert cal.early_close_time(ash_wed_2025) == "13:00"
    assert not cal.is_early_close(date(2025, 6, 2))
