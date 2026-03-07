from __future__ import annotations

import re
from datetime import date, datetime

from dateutil import parser as date_parser
from pydantic import BaseModel

from tickerforge.contract_cycle import resolve_contract_months
from tickerforge.models import ContractSpec
from tickerforge.month_codes import code_to_month
from tickerforge.spec_loader import SpecRepository, load_spec


class ParsedTicker(BaseModel):
    symbol: str
    year: int
    month: int
    contract: ContractSpec


def _coerce_date(value: str | date | datetime | None) -> date:
    if value is None:
        return date.today()
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return date_parser.parse(value).date()


def _pattern_for_contract(contract: ContractSpec) -> re.Pattern[str]:
    escaped = re.escape(contract.ticker_format)
    pattern = (
        escaped.replace(r"\{symbol\}", re.escape(contract.symbol))
        .replace(r"\{month_code\}", r"(?P<month_code>[FGHJKMNQUVXZ])")
        .replace(r"\{yy\}", r"(?P<yy>\d{2})")
    )
    return re.compile(f"^{pattern}$")


def parse_ticker(
    ticker: str,
    spec: SpecRepository,
    reference_date: str | date | datetime | None = None,
) -> ParsedTicker:
    ref_date = _coerce_date(reference_date)
    reference_century = (ref_date.year // 100) * 100

    for contract in spec.contracts.values():
        match = _pattern_for_contract(contract).match(ticker)
        if not match:
            continue

        month = code_to_month(match.group("month_code"))
        year = reference_century + int(match.group("yy"))
        if year < ref_date.year - 50:
            year += 100
        elif year > ref_date.year + 50:
            year -= 100

        valid_months = resolve_contract_months(spec.contract_cycles[contract.contract_cycle], year)
        if month not in valid_months:
            continue

        return ParsedTicker(symbol=contract.symbol, year=year, month=month, contract=contract)

    raise ValueError(f"Unable to parse ticker: {ticker}")


class TickerParser:
    def __init__(self, spec_path: str | None = None) -> None:
        self.spec = load_spec(spec_path)

    def parse(
        self,
        ticker: str,
        reference_date: str | date | datetime | None = None,
    ) -> ParsedTicker:
        return parse_ticker(ticker=ticker, spec=self.spec, reference_date=reference_date)
