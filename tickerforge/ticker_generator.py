from __future__ import annotations

from calendar import monthrange
from datetime import date, datetime, timedelta

from dateutil import parser as date_parser

from tickerforge.calendars import get_calendar
from tickerforge.contract_cycle import resolve_contract_months
from tickerforge.expiration_rules import _month_sessions, resolve_expiration
from tickerforge.models import ContractSpec, ExpirationRule
from tickerforge.month_codes import month_to_code
from tickerforge.spec_loader import SpecRepository, load_spec


def _coerce_date(value: str | date | datetime) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return date_parser.parse(value).date()


def format_contract_ticker(contract: ContractSpec, year: int, month: int) -> str:
    """Build a futures ticker string from contract metadata and expiry month."""
    month_code = month_to_code(month)
    yy = f"{year % 100:02d}"
    return contract.ticker_format.format(
        symbol=contract.symbol,
        month_code=month_code,
        yy=yy,
    )


def _format_ticker(contract: ContractSpec, year: int, month: int) -> str:
    return format_contract_ticker(contract, year, month)


def _resolve_last_trading_day(
    expiration_date: date,
    rule: ExpirationRule,
    calendar,
) -> date:
    """Resolve the final session a contract can be traded on the exchange.

    Based on the ExpirationRule's effective_last_trading_day_offset().
    """
    offset = rule.effective_last_trading_day_offset()
    if offset < 0:
        days_back = abs(offset) * 7 + 10
        sessions = calendar.sessions_in_range(
            (expiration_date - timedelta(days=days_back)).isoformat(),
            expiration_date.isoformat(),
        )
        session_dates = [s.date() if hasattr(s, "date") else s for s in sessions]
        prior_sessions = [d for d in session_dates if d < expiration_date]
        idx = len(prior_sessions) + offset
        if 0 <= idx < len(prior_sessions):
            return prior_sessions[idx]
    return expiration_date


def _is_front_eligible(
    as_of_date: date,
    expiration_date: date,
    rule: ExpirationRule,
    calendar,
) -> bool:
    """Check if a contract is eligible in the forward contract list (front-month at offset=0)."""
    ltd = _resolve_last_trading_day(expiration_date, rule, calendar)
    if rule.should_roll_on_last_trading_day():
        return as_of_date < ltd
    return as_of_date <= ltd


def _is_contract_tradeable(
    as_of_date: date,
    expiration_date: date,
    rule: ExpirationRule,
    calendar,
) -> bool:
    """Check if a specific contract can be traded on as_of_date (up to its last trading day)."""
    ltd = _resolve_last_trading_day(expiration_date, rule, calendar)
    return as_of_date <= ltd


def _is_month_in_calendar_range(calendar, year: int, month: int) -> bool:
    first_session = calendar.first_session.date()
    last_session = calendar.last_session.date()
    month_start = date(year, month, 1)
    month_end = date(year, month, monthrange(year, month)[1])
    return not (month_end < first_session or month_start > last_session)


def _collect_eligible_contracts(
    contract: ContractSpec,
    as_of_date: date,
    spec: SpecRepository,
) -> list[tuple[int, int]]:
    """Forward, still-tradeable ``(year, month)`` pairs from ``as_of.year`` onward."""
    cycle = spec.contract_cycles[contract.contract_cycle]
    rule = spec.expiration_rules[contract.expiration_rule]
    calendar = get_calendar(contract.exchange)

    eligible_contracts: list[tuple[int, int]] = []
    for year in range(as_of_date.year, as_of_date.year + 4):
        for month in resolve_contract_months(cycle, year):
            if not _is_month_in_calendar_range(calendar, year, month):
                continue
            if not _month_sessions(calendar, year, month):
                continue
            expiration_date = resolve_expiration(contract, year, month, rule, calendar)
            if _is_front_eligible(as_of_date, expiration_date, rule, calendar):
                eligible_contracts.append((year, month))
    return eligible_contracts


def _collect_expired_contracts(
    contract: ContractSpec,
    as_of_date: date,
    spec: SpecRepository,
) -> list[tuple[int, int]]:
    """Expired ``(year, month)`` pairs, most-recently-expired first.

    Scans backward from ``as_of.year - 4 .. as_of.year`` (inclusive) over the
    contract cycle, applying the same calendar-range and session filters as the
    forward scan, and keeps pairs that are *no longer* tradeable. The result is
    sorted so the largest ``(year, month)`` (i.e. the most recently expired
    contract) is at index 0, so ``offset = -1`` selects it.
    """
    cycle = spec.contract_cycles[contract.contract_cycle]
    rule = spec.expiration_rules[contract.expiration_rule]
    calendar = get_calendar(contract.exchange)

    expired_contracts: list[tuple[int, int]] = []
    for year in range(as_of_date.year - 4, as_of_date.year + 1):
        for month in resolve_contract_months(cycle, year):
            if not _is_month_in_calendar_range(calendar, year, month):
                continue
            if not _month_sessions(calendar, year, month):
                continue
            expiration_date = resolve_expiration(contract, year, month, rule, calendar)
            if not _is_front_eligible(as_of_date, expiration_date, rule, calendar):
                expired_contracts.append((year, month))

    expired_contracts.sort(reverse=True)
    return expired_contracts


def generate_ticker_for_contract(
    contract: ContractSpec,
    as_of: str | date | datetime,
    spec: SpecRepository,
    offset: int = 0,
) -> str:
    as_of_date = _coerce_date(as_of)

    if offset >= 0:
        eligible_contracts = _collect_eligible_contracts(contract, as_of_date, spec)
        if not eligible_contracts:
            raise ValueError(
                f"No eligible contract found for {contract.symbol} at {as_of_date}"
            )
        if offset >= len(eligible_contracts):
            raise ValueError(f"Offset {offset} is out of range for {contract.symbol}")
        year, month = eligible_contracts[offset]
        return _format_ticker(contract, year, month)

    expired_contracts = _collect_expired_contracts(contract, as_of_date, spec)
    index = (-offset) - 1
    if index >= len(expired_contracts):
        raise ValueError(f"Offset {offset} is out of range for {contract.symbol}")
    year, month = expired_contracts[index]
    return _format_ticker(contract, year, month)


def gen_ticker_ctr(
    contract: ContractSpec,
    spec: SpecRepository,
    offset: int = 0,
) -> str:
    """Front-month ticker for today (``offset`` 0 by default)."""
    return generate_ticker_for_contract(contract, date.today(), spec, offset=offset)


class TickerForge:
    def __init__(self, spec_path: str | None = None) -> None:
        self.spec = load_spec(spec_path)

    def gen(self, symbol: str, offset: int = 0) -> str:
        """Front-month ticker for today (``offset`` 0 by default)."""
        contract = self.spec.get_contract(symbol)
        return gen_ticker_ctr(contract, self.spec, offset=offset)

    def generate(
        self, symbol: str, date: str | date | datetime, offset: int = 0
    ) -> str:
        contract = self.spec.get_contract(symbol)
        return generate_ticker_for_contract(contract, date, self.spec, offset=offset)
