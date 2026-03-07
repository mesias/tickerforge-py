from __future__ import annotations

from calendar import monthrange
from datetime import date, datetime

from dateutil import parser as date_parser

from tickerforge.calendars import get_calendar
from tickerforge.contract_cycle import resolve_contract_months
from tickerforge.expiration_rules import resolve_expiration
from tickerforge.models import ContractSpec
from tickerforge.month_codes import month_to_code
from tickerforge.spec_loader import SpecRepository, load_spec


def _coerce_date(value: str | date | datetime) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return date_parser.parse(value).date()


def _format_ticker(contract: ContractSpec, year: int, month: int) -> str:
    return contract.ticker_format.format(
        symbol=contract.symbol,
        month_code=month_to_code(month),
        yy=f"{year % 100:02d}",
        year=year,
        month=month,
    )


def _is_month_in_calendar_range(calendar, year: int, month: int) -> bool:
    first_session = calendar.first_session.date()
    last_session = calendar.last_session.date()
    month_start = date(year, month, 1)
    month_end = date(year, month, monthrange(year, month)[1])
    return not (month_end < first_session or month_start > last_session)


def generate_ticker_for_contract(
    contract: ContractSpec,
    as_of: str | date | datetime,
    spec: SpecRepository,
    offset: int = 0,
) -> str:
    if offset < 0:
        raise ValueError("offset must be >= 0")

    as_of_date = _coerce_date(as_of)
    cycle = spec.contract_cycles[contract.contract_cycle]
    rule = spec.expiration_rules[contract.expiration_rule]
    calendar = get_calendar(contract.exchange)

    eligible_contracts: list[tuple[int, int]] = []
    for year in range(as_of_date.year, as_of_date.year + 4):
        for month in resolve_contract_months(cycle, year):
            if not _is_month_in_calendar_range(calendar, year, month):
                continue
            expiration_date = resolve_expiration(contract, year, month, rule, calendar)
            if as_of_date <= expiration_date:
                eligible_contracts.append((year, month))

    if not eligible_contracts:
        raise ValueError(f"No eligible contract found for {contract.symbol} at {as_of_date}")
    if offset >= len(eligible_contracts):
        raise ValueError(f"Offset {offset} is out of range for {contract.symbol}")

    year, month = eligible_contracts[offset]
    return _format_ticker(contract, year, month)


class TickerForge:
    def __init__(self, spec_path: str | None = None) -> None:
        self.spec = load_spec(spec_path)

    def generate(self, symbol: str, date: str | date | datetime, offset: int = 0) -> str:
        contract = self.spec.get_contract(symbol)
        return generate_ticker_for_contract(contract, date, self.spec, offset=offset)
