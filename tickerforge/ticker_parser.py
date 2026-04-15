from __future__ import annotations

import re
import warnings
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
    tick_size: float
    lot_size: float
    contract: ContractSpec
    reference_date: date | None = None
    is_trading_session: bool | None = None


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


def _parse_full_ticker(
    ticker: str, spec: SpecRepository
) -> ParsedTicker | None:
    """Try to match *ticker* against every contract pattern.

    Year is derived directly from the 2-digit code (``2000 + yy``);
    no ``reference_date`` is needed.
    """
    for contract in spec.contracts.values():
        match = _pattern_for_contract(contract).match(ticker)
        if not match:
            continue

        month = code_to_month(match.group("month_code"))
        year = 2000 + int(match.group("yy"))

        valid_months = resolve_contract_months(
            spec.contract_cycles[contract.contract_cycle], year
        )
        if month not in valid_months:
            continue

        return ParsedTicker(
            symbol=contract.symbol,
            year=year,
            month=month,
            tick_size=contract.tick_size,
            lot_size=contract.contract_multiplier,
            contract=contract,
        )

    return None


def _is_trading_session(exchange: str, ref_date: date) -> bool:
    """Check whether *ref_date* is an actual trading session on *exchange*."""
    from tickerforge.calendars import get_calendar

    calendar = get_calendar(exchange)
    sessions = calendar.sessions_in_range(ref_date.isoformat(), ref_date.isoformat())
    return len(sessions) > 0


def _resolve_root_symbol(
    ticker: str,
    spec: SpecRepository,
    reference_date: str | date | datetime | None,
) -> ParsedTicker | None:
    """Resolve a bare root symbol (e.g. ``IND``) to a :class:`ParsedTicker`.

    Uses the ticker generator to find the front-month contract for the given
    (or today's) ``reference_date``, then parses the resulting full ticker.
    Sets ``reference_date`` and ``is_trading_session`` on the result.
    """
    from tickerforge.ticker_generator import generate_ticker_for_contract

    contract = spec.contracts.get(ticker.upper())
    if contract is None:
        return None

    ref_date = _coerce_date(reference_date)
    full_ticker = generate_ticker_for_contract(contract, ref_date, spec)
    result = _parse_full_ticker(full_ticker, spec)
    if result is not None:
        result = result.model_copy(update={
            "reference_date": ref_date,
            "is_trading_session": _is_trading_session(contract.exchange, ref_date),
        })
    return result


def parse_ticker(
    ticker: str,
    spec: SpecRepository | None = None,
    reference_date: str | date | datetime | None = None,
) -> ParsedTicker:
    if spec is None:
        spec = load_spec()

    result = _parse_full_ticker(ticker, spec)
    if result is not None:
        if reference_date is not None:
            warnings.warn(
                f"reference_date is ignored for full ticker '{ticker}'; "
                f"year and month are derived directly from the ticker string",
                stacklevel=2,
            )
        return result

    result = _resolve_root_symbol(ticker, spec, reference_date)
    if result is not None:
        return result

    raise ValueError(f"Unable to parse ticker: {ticker}")


class _TickerParserBuilderBase:
    """Shared builder state — methods available regardless of whether a ticker
    has been set."""

    def __init__(self) -> None:
        self._spec_path: str | None = None
        self._ticker: str | None = None
        self._reference_date: str | date | datetime | None = None

    def spec_path(self, path: str) -> _TickerParserBuilderBase:
        """Set a custom spec directory.  When omitted the bundled default is used."""
        self._spec_path = path
        return self

    def spec(self, path: str) -> _TickerParserBuilderBase:
        """Set a custom spec directory (alias for :meth:`spec_path`)."""
        return self.spec_path(path)

    def reference_date(
        self, ref_date: str | date | datetime
    ) -> _TickerParserBuilderBase:
        """Set a ``reference_date`` for root-symbol resolution."""
        self._reference_date = ref_date
        return self

    def build(self) -> TickerParser:
        """Build a **reusable** :class:`TickerParser`."""
        return TickerParser(spec_path=self._spec_path)


class _TickerParserBuilderWithTicker(_TickerParserBuilderBase):
    """Builder state after a ticker has been set — ``parse()`` is available."""

    def ticker(self, ticker: str) -> _TickerParserBuilderWithTicker:
        """Replace the ticker string (stays in *has-ticker* state)."""
        self._ticker = ticker
        return self

    def spec_path(self, path: str) -> _TickerParserBuilderWithTicker:
        self._spec_path = path
        return self  # type: ignore[return-value]

    def spec(self, path: str) -> _TickerParserBuilderWithTicker:
        """Set a custom spec directory (alias for :meth:`spec_path`)."""
        return self.spec_path(path)  # type: ignore[return-value]

    def reference_date(
        self, ref_date: str | date | datetime
    ) -> _TickerParserBuilderWithTicker:
        self._reference_date = ref_date
        return self  # type: ignore[return-value]

    def parse(self) -> ParsedTicker:
        """One-shot: load spec, parse the ticker, and return the result."""
        spec = load_spec(self._spec_path)
        return parse_ticker(
            ticker=self._ticker,  # type: ignore[arg-type]
            spec=spec,
            reference_date=self._reference_date,
        )


class _TickerParserBuilderNoTicker(_TickerParserBuilderBase):
    """Builder state before a ticker has been set — only ``build()`` and
    configuration methods are available."""

    def ticker(self, ticker: str) -> _TickerParserBuilderWithTicker:
        """Set the ticker string, enabling one-shot :meth:`parse`."""
        builder = _TickerParserBuilderWithTicker()
        builder._spec_path = self._spec_path
        builder._reference_date = self._reference_date
        builder._ticker = ticker
        return builder

    def spec_path(self, path: str) -> _TickerParserBuilderNoTicker:
        self._spec_path = path
        return self  # type: ignore[return-value]

    def spec(self, path: str) -> _TickerParserBuilderNoTicker:
        """Set a custom spec directory (alias for :meth:`spec_path`)."""
        return self.spec_path(path)  # type: ignore[return-value]

    def reference_date(
        self, ref_date: str | date | datetime
    ) -> _TickerParserBuilderNoTicker:
        self._reference_date = ref_date
        return self  # type: ignore[return-value]


class TickerParser:
    """Reusable parser that holds a loaded :class:`SpecRepository`.

    Create via :meth:`TickerParser()` (direct), or :meth:`TickerParser.builder`
    for fluent configuration.
    """

    def __init__(self, spec_path: str | None = None) -> None:
        self.spec = load_spec(spec_path)

    @staticmethod
    def builder() -> _TickerParserBuilderNoTicker:
        """Start a :class:`TickerParserBuilder`."""
        return _TickerParserBuilderNoTicker()

    def parse(
        self,
        ticker: str,
        reference_date: str | date | datetime | None = None,
    ) -> ParsedTicker:
        return parse_ticker(
            ticker=ticker, spec=self.spec, reference_date=reference_date
        )
