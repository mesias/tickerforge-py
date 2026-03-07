from datetime import date
from pathlib import Path

from tickerforge.calendars import get_calendar
from tickerforge.expiration_rules import resolve_expiration
from tickerforge.spec_loader import load_spec


def test_resolve_nearest_weekday_to_day_for_ind():
    spec_path = Path(__file__).resolve().parents[1] / "spec"
    spec = load_spec(spec_path)
    contract = spec.get_contract("IND")
    rule = spec.expiration_rules[contract.expiration_rule]
    calendar = get_calendar(contract.exchange)

    expiration = resolve_expiration(contract=contract, year=2026, month=6, expiration_rule=rule, calendar=calendar)
    assert expiration == date(2026, 6, 17)


def test_resolve_first_business_day_for_dol():
    spec_path = Path(__file__).resolve().parents[1] / "spec"
    spec = load_spec(spec_path)
    contract = spec.get_contract("DOL")
    rule = spec.expiration_rules[contract.expiration_rule]
    calendar = get_calendar(contract.exchange)

    expiration = resolve_expiration(contract=contract, year=2026, month=4, expiration_rule=rule, calendar=calendar)
    assert expiration == date(2026, 4, 1)
