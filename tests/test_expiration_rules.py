from datetime import date
from pathlib import Path
from unittest.mock import patch

import pytest

from tickerforge.calendars import _resolve_calendar_name, get_calendar
from tickerforge.expiration_rules import (
    _month_sessions,
    _resolve_business_day_prior_to_day_of_preceding_month,
    _resolve_fixed_day,
    _resolve_last_weekday_of_month,
    _resolve_nearest_weekday_to_day,
    _resolve_nth_business_day,
    _resolve_nth_business_day_from_end,
    _resolve_nth_weekday_of_month,
    _resolve_second_business_day_prior_to_month,
    resolve_expiration,
)
from tickerforge.models import ContractSpec, ExpirationRule
from tickerforge.schedule import ExchangeSchedule, SpecCalendar
from tickerforge.spec_loader import load_spec


class DummyWrapper:
    def __init__(self, d: date):
        self._d = d

    def date(self) -> date:
        return self._d


class DummyCalendar:
    def __init__(self, first: date, last: date, sessions: list[date] | None = None):
        self._first = first
        self._last = last
        self._sessions = sessions or []

    @property
    def first_session(self):
        return DummyWrapper(self._first)

    @property
    def last_session(self):
        return DummyWrapper(self._last)

    def sessions_in_range(self, start, end):
        return [DummyWrapper(s) for s in self._sessions]


def test_resolve_nearest_weekday_to_day_for_ind():
    spec_path = Path(__file__).resolve().parents[1] / "spec"
    spec = load_spec(spec_path)
    contract = spec.get_contract("IND")
    rule = spec.expiration_rules[contract.expiration_rule]
    calendar = get_calendar(contract.exchange)

    expiration = resolve_expiration(
        contract=contract, year=2026, month=6, expiration_rule=rule, calendar=calendar
    )
    assert expiration == date(2026, 6, 17)


def test_resolve_first_business_day_for_dol():
    spec_path = Path(__file__).resolve().parents[1] / "spec"
    spec = load_spec(spec_path)
    contract = spec.get_contract("DOL")
    rule = spec.expiration_rules[contract.expiration_rule]
    calendar = get_calendar(contract.exchange)

    expiration = resolve_expiration(
        contract=contract, year=2026, month=4, expiration_rule=rule, calendar=calendar
    )
    assert expiration == date(2026, 4, 1)


# --- Coverage Boost Tests ---


def test_resolve_calendar_name_no_xcals():
    with patch("tickerforge.calendars.xcals", None):
        with pytest.raises(RuntimeError, match="exchange_calendars is not installed"):
            get_calendar("NYSE")


def test_resolve_calendar_name_fallback():
    # Test valid exchange from exchange_calendars
    cal = get_calendar("XNYS")
    assert cal is not None

    # Test invalid exchange name
    with pytest.raises(ValueError, match="No calendar found for exchange"):
        get_calendar("invalid_exchange_abc")


def test_resolve_calendar_name_case_insensitive_fallback():
    with patch("tickerforge.calendars.xcals") as mock_xcals:
        # Mock get_calendar to fail for uppercase, but get_calendar_names to return mixed case
        mock_xcals.get_calendar.side_effect = Exception("Failed")
        mock_xcals.get_calendar_names.return_value = ["test_exch"]

        assert _resolve_calendar_name("TEST_EXCH") == "test_exch"


def test_month_sessions_boundaries():
    schedule = ExchangeSchedule({"exchange": "TEST", "timezone": "UTC"})
    calendar = SpecCalendar(schedule)

    # 1. Month range completely before first session or after last session
    assert _month_sessions(calendar, 1980, 1) == []
    assert _month_sessions(calendar, 2040, 1) == []

    # 2. clip_start > clip_end (Safety boundary check)
    dummy = DummyCalendar(date(2026, 6, 30), date(2026, 6, 1))
    assert _month_sessions(dummy, 2026, 6) == []


def test_resolve_expiration_missing_properties():
    schedule = ExchangeSchedule({"exchange": "TEST", "timezone": "UTC"})
    calendar = SpecCalendar(schedule)
    dummy_contract = ContractSpec(
        symbol="TEST", exchange="TEST", contract_cycle="monthly", expiration_rule="test"
    )

    # Validate missing n/day/weekday parameters for different rule types
    with pytest.raises(ValueError, match="nth_business_day rule requires 'n'"):
        resolve_expiration(
            dummy_contract,
            2026,
            6,
            ExpirationRule(name="t", type="nth_business_day"),
            calendar,
        )

    with pytest.raises(ValueError, match="fixed_day rule requires 'day'"):
        resolve_expiration(
            dummy_contract,
            2026,
            6,
            ExpirationRule(name="t", type="fixed_day"),
            calendar,
        )

    with pytest.raises(ValueError, match="nearest_weekday_to_day rule requires"):
        resolve_expiration(
            dummy_contract,
            2026,
            6,
            ExpirationRule(name="t", type="nearest_weekday_to_day"),
            calendar,
        )

    with pytest.raises(ValueError, match="nth_weekday_of_month rule requires"):
        resolve_expiration(
            dummy_contract,
            2026,
            6,
            ExpirationRule(name="t", type="nth_weekday_of_month"),
            calendar,
        )

    with pytest.raises(
        ValueError, match="last_weekday_of_month rule requires 'weekday'"
    ):
        resolve_expiration(
            dummy_contract,
            2026,
            6,
            ExpirationRule(name="t", type="last_weekday_of_month"),
            calendar,
        )

    with pytest.raises(
        ValueError,
        match="business_day_prior_to_day_of_preceding_month rule requires 'day'",
    ):
        resolve_expiration(
            dummy_contract,
            2026,
            6,
            ExpirationRule(
                name="t", type="business_day_prior_to_day_of_preceding_month"
            ),
            calendar,
        )

    with pytest.raises(ValueError, match="nth_business_day_from_end rule requires 'n'"):
        resolve_expiration(
            dummy_contract,
            2026,
            6,
            ExpirationRule(name="t", type="nth_business_day_from_end"),
            calendar,
        )

    with pytest.raises(
        NotImplementedError,
        match="schedule expiration rules need external schedule data",
    ):
        resolve_expiration(
            dummy_contract, 2026, 6, ExpirationRule(name="t", type="schedule"), calendar
        )

    with pytest.raises(ValueError, match="Unsupported expiration rule type: invalid"):
        resolve_expiration(
            dummy_contract, 2026, 6, ExpirationRule(name="t", type="invalid"), calendar
        )


def test_rule_type_executions_and_edge_cases():
    # Setup schedule with specific holidays to test boundary checks
    schedule = ExchangeSchedule(
        {
            "exchange": "TEST",
            "timezone": "UTC",
            "holidays": {
                "overrides": [
                    {"date": "2026-06-01", "action": "add"},  # Monday
                    {"date": "2026-06-02", "action": "add"},  # Tuesday
                    {"date": "2026-06-03", "action": "add"},  # Wednesday
                    {"date": "2026-06-04", "action": "add"},  # Thursday
                    {
                        "date": "2026-06-05",
                        "action": "add",
                    },  # Friday (No sessions in 1st week of June)
                    {"date": "2026-06-29", "action": "add"},  # Monday holiday
                    {"date": "2026-06-30", "action": "add"},  # Tuesday holiday
                ]
            },
        }
    )
    calendar = SpecCalendar(schedule)
    dummy_contract = ContractSpec(
        symbol="TEST", exchange="TEST", contract_cycle="monthly", expiration_rule="test"
    )

    # 1. nth_business_day out of bounds
    with pytest.raises(ValueError, match="Invalid nth business day"):
        _resolve_nth_business_day(calendar, 2026, 6, 0)
    with pytest.raises(ValueError, match="Invalid nth business day"):
        _resolve_nth_business_day(calendar, 2026, 6, 100)

    # Valid execution of nth_business_day (Line 52)
    # 2nd business day of June 2026: June 1-5 are holidays. 1st is June 8, 2nd is June 9.
    assert _resolve_nth_business_day(calendar, 2026, 6, 2) == date(2026, 6, 9)

    # 2. fixed_day resolution
    # Target date = June 3, but Monday-Friday of 1st week are holidays. The next available is June 8 (Monday).
    assert _resolve_fixed_day(calendar, 2026, 6, 3) == date(2026, 6, 8)
    # Target date = June 29 (which is holiday, next is June 30 which is holiday, so it falls back to last session of month)
    # The last session of June 2026 is Friday, June 26.
    assert _resolve_fixed_day(calendar, 2026, 6, 29) == date(2026, 6, 26)

    # 3. nearest_weekday_to_day no sessions
    with patch("tickerforge.expiration_rules._month_sessions", return_value=[]):
        with pytest.raises(ValueError, match="No sessions on weekday 'friday'"):
            _resolve_nearest_weekday_to_day(calendar, 2026, 6, "friday", 15)

    # 4. nth_weekday_of_month out of bounds
    with pytest.raises(ValueError, match="Invalid nth weekday '10'"):
        _resolve_nth_weekday_of_month(calendar, 2026, 6, "friday", 10)

    # 5. last_weekday_of_month no sessions on weekday
    with patch("tickerforge.expiration_rules._month_sessions", return_value=[]):
        with pytest.raises(ValueError, match="No sessions on weekday 'friday'"):
            _resolve_last_weekday_of_month(calendar, 2026, 6, "friday")

    # 6. second_business_day_prior_to_month preceding month wrapping (January -> December)
    # January 2026 -> Preceding month is December 2025
    dec_schedule = ExchangeSchedule({"exchange": "TEST", "timezone": "UTC"})
    dec_calendar = SpecCalendar(dec_schedule)
    # Preceding month has 22 sessions, second to last is Dec 30, 2025
    assert _resolve_second_business_day_prior_to_month(dec_calendar, 2026, 1) == date(
        2025, 12, 30
    )

    # Not enough sessions in preceding month
    with patch(
        "tickerforge.expiration_rules._month_sessions", return_value=[date(2025, 12, 1)]
    ):
        with pytest.raises(ValueError, match="Not enough sessions in preceding month"):
            _resolve_second_business_day_prior_to_month(dec_calendar, 2026, 1)

    # 7. business_day_prior_to_day_of_preceding_month preceding month wrapping (January -> December)
    assert _resolve_business_day_prior_to_day_of_preceding_month(
        dec_calendar, 2026, 1, 10
    ) == date(2025, 12, 9)

    # No sessions found before target day
    # Target = December 1, but no sessions are before it
    with patch(
        "tickerforge.expiration_rules._month_sessions",
        return_value=[date(2025, 12, 15)],
    ):
        with pytest.raises(ValueError, match="No sessions found before target day"):
            _resolve_business_day_prior_to_day_of_preceding_month(
                dec_calendar, 2026, 1, 10
            )

    # 8. nth_business_day_from_end out of bounds
    with pytest.raises(ValueError, match="Invalid nth business day from end '100'"):
        _resolve_nth_business_day_from_end(calendar, 2026, 6, 100)

    # 9. resolve_expiration valid branch coverage (Lines 204, 208)
    assert resolve_expiration(
        dummy_contract,
        2026,
        6,
        ExpirationRule(name="t", type="nth_business_day", n=2),
        calendar,
    ) == date(2026, 6, 9)
    assert resolve_expiration(
        dummy_contract,
        2026,
        6,
        ExpirationRule(name="t", type="fixed_day", day=3),
        calendar,
    ) == date(2026, 6, 8)


def test_expiration_rule_last_trading_day_offset_and_roll():
    # 1. explicit last_trading_day_offset (covers line 106)
    rule_offset = ExpirationRule(
        name="custom_offset",
        type="first_business_day",
        last_trading_day="prior_business_day",
        last_trading_day_offset=-3,
    )
    assert rule_offset.effective_last_trading_day_offset() == -3

    rule_offset_zero = ExpirationRule(
        name="zero_offset",
        type="custom",
        last_trading_day_offset=0,
    )
    assert rule_offset_zero.effective_last_trading_day_offset() == 0

    # 2. prior_business_day / previous_business_day
    rule_prior = ExpirationRule(
        name="prior",
        type="custom",
        last_trading_day="prior_business_day",
    )
    assert rule_prior.effective_last_trading_day_offset() == -1

    rule_prev = ExpirationRule(
        name="prev",
        type="custom",
        last_trading_day="previous_business_day",
    )
    assert rule_prev.effective_last_trading_day_offset() == -1

    # 3. same_day
    rule_same = ExpirationRule(
        name="same",
        type="custom",
        last_trading_day="same_day",
    )
    assert rule_same.effective_last_trading_day_offset() == 0

    # 4. type == "first_business_day" with no last_trading_day (covers line 112)
    rule_fbd = ExpirationRule(
        name="fbd",
        type="first_business_day",
    )
    assert rule_fbd.effective_last_trading_day_offset() == -1

    # 5. default fallback
    rule_default = ExpirationRule(
        name="other",
        type="third_friday",
    )
    assert rule_default.effective_last_trading_day_offset() == 0

    # 6. should_roll_on_last_trading_day explicit override
    assert (
        ExpirationRule(
            name="r",
            type="custom",
            roll_on_last_trading_day=True,
        ).should_roll_on_last_trading_day()
        is True
    )
    assert (
        ExpirationRule(
            name="r",
            type="first_business_day",
            roll_on_last_trading_day=False,
        ).should_roll_on_last_trading_day()
        is False
    )

    # 7. should_roll_on_last_trading_day derived from offset < 0
    assert rule_offset.should_roll_on_last_trading_day() is True
    assert rule_offset_zero.should_roll_on_last_trading_day() is False
    assert rule_fbd.should_roll_on_last_trading_day() is True
    assert rule_default.should_roll_on_last_trading_day() is False
