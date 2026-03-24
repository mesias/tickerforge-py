from __future__ import annotations

import csv
import lzma
from datetime import date
from pathlib import Path

import pytest

from tickerforge import TickerForge
from tickerforge.calendars import get_calendar

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
