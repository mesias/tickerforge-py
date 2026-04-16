from __future__ import annotations

import re
import warnings
from datetime import date, datetime
from pathlib import Path
from typing import Literal

from dateutil import parser as date_parser
from pydantic import BaseModel

from tickerforge.contract_cycle import resolve_contract_months
from tickerforge.models import ContractSpec, OptionSpec
from tickerforge.month_codes import code_to_month
from tickerforge.spec_loader import SpecRepository, load_spec


class ParsedTicker(BaseModel):
    symbol: str
    year: int | None = None
    month: int
    tick_size: float
    lot_size: float
    asset_type: Literal["future", "option"] = "future"
    exchange: str | None = None
    contract: ContractSpec | None = None
    option: OptionSpec | None = None
    option_type: Literal["call", "put"] | None = None
    strike: str | None = None
    underlying: str | None = None
    reference_date: date | None = None
    is_trading_session: bool | None = None


class AmbiguousTickerError(ValueError):
    """Raised when a ticker matches multiple contracts or options across markets."""

    def __init__(self, ticker: str, matches: list[ParsedTicker]) -> None:
        self.ticker = ticker
        self.matches = matches
        descriptions = []
        for m in matches:
            source = m.option or m.contract
            desc = getattr(source, "description", None) or m.symbol
            descriptions.append(f"  - {m.asset_type} on {m.exchange}: {desc}")
        detail = "\n".join(descriptions)
        super().__init__(
            f"Ambiguous ticker '{ticker}' matched {len(matches)} instruments:\n{detail}\n"
            f"Pass exchange= to disambiguate."
        )


def _coerce_date(value: str | date | datetime | None) -> date:
    if value is None:
        return date.today()
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return date_parser.parse(value).date()


# ---------------------------------------------------------------------------
# Futures pattern matching
# ---------------------------------------------------------------------------


def _pattern_for_contract(contract: ContractSpec) -> re.Pattern[str]:
    escaped = re.escape(contract.ticker_format)
    pattern = (
        escaped.replace(r"\{symbol\}", re.escape(contract.symbol))
        .replace(r"\{month_code\}", r"(?P<month_code>[FGHJKMNQUVXZ])")
        .replace(r"\{yy\}", r"(?P<yy>\d{2})")
    )
    return re.compile(f"^{pattern}$")


def _match_futures(ticker: str, spec: SpecRepository) -> list[ParsedTicker]:
    results: list[ParsedTicker] = []
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

        results.append(
            ParsedTicker(
                symbol=contract.symbol,
                year=year,
                month=month,
                tick_size=contract.tick_size,
                lot_size=contract.contract_multiplier,
                asset_type="future",
                exchange=contract.exchange,
                contract=contract,
            )
        )
    return results


# ---------------------------------------------------------------------------
# Options pattern matching
# ---------------------------------------------------------------------------

_EQUITY_CALL_CODES = list("ABCDEFGHIJKL")
_EQUITY_PUT_CODES = list("MNOPQRSTUVWX")


def _equity_root(underlying: str) -> str:
    """Strip one trailing digit from an equity underlying symbol.

    Mirrors the Rust ``equity_root`` function: ``PETR4`` → ``PETR``,
    ``BOVA11`` → ``BOVA1``.  This gives the root used in B3 option tickers.
    """
    if underlying and underlying[-1].isdigit():
        return underlying[:-1]
    return underlying


def _equity_code_to_month_and_type(
    code: str, option: OptionSpec
) -> tuple[int, str] | None:
    """Map an equity option month code to (month_number, 'call'|'put')."""
    call_codes = option.call_month_codes or _EQUITY_CALL_CODES
    put_codes = option.put_month_codes or _EQUITY_PUT_CODES
    upper = code.upper()
    if upper in call_codes:
        return (call_codes.index(upper) + 1, "call")
    if upper in put_codes:
        return (put_codes.index(upper) + 1, "put")
    return None


def _patterns_for_equity_option(
    option: OptionSpec,
) -> list[tuple[re.Pattern[str], str]]:
    """Build (pattern, underlying) pairs for an equity option spec.

    The pattern root is ``equity_root(underlying)`` (trailing digit stripped)
    to match the real B3 ticker format: ``PETRA30`` not ``PETR4A30``.
    The second element of each tuple is the full underlying symbol (``PETR4``)
    used as metadata on the parsed result.
    """
    if not option.underlyings:
        return []

    call_codes = option.call_month_codes or _EQUITY_CALL_CODES
    put_codes = option.put_month_codes or _EQUITY_PUT_CODES
    all_codes = "".join(call_codes + put_codes)

    patterns: list[tuple[re.Pattern[str], str]] = []
    for underlying in option.underlyings:
        root = _equity_root(underlying)
        pat = re.compile(
            rf"^{re.escape(root)}(?P<month_code>[{re.escape(all_codes)}])(?P<strike>\d+)$"
        )
        patterns.append((pat, underlying))
    return patterns


def _pattern_for_nonequity_option(option: OptionSpec) -> re.Pattern[str] | None:
    """Build a regex for index / dollar / interest_rate options.

    Format: ``{symbol}{month_code}{yy}{option_type}{strike}``
    """
    if option.symbol is None or option.option_type_codes is None:
        return None

    call_code = re.escape(option.option_type_codes["call"])
    put_code = re.escape(option.option_type_codes["put"])

    return re.compile(
        rf"^{re.escape(option.symbol)}"
        rf"(?P<month_code>[FGHJKMNQUVXZ])"
        rf"(?P<yy>\d{{2}})"
        rf"(?P<option_type>{call_code}|{put_code})"
        rf"(?P<strike>\d+)$"
    )


def _match_options(ticker: str, spec: SpecRepository) -> list[ParsedTicker]:
    results: list[ParsedTicker] = []

    for option in spec.options:
        if option.type == "equity":
            for pat, underlying in _patterns_for_equity_option(option):
                match = pat.match(ticker)
                if not match:
                    continue
                parsed = _equity_code_to_month_and_type(
                    match.group("month_code"), option
                )
                if parsed is None:
                    continue
                month, opt_type = parsed
                results.append(
                    ParsedTicker(
                        symbol=underlying,
                        year=None,
                        month=month,
                        tick_size=option.tick_size,
                        lot_size=option.contract_multiplier,
                        asset_type="option",
                        exchange=option.exchange,
                        option=option,
                        option_type=opt_type,
                        strike=match.group("strike"),
                        underlying=underlying,
                    )
                )
        else:
            nonequity_pat: re.Pattern[str] | None = _pattern_for_nonequity_option(
                option
            )
            if nonequity_pat is None:
                continue
            match = nonequity_pat.match(ticker)
            if not match:
                continue

            month = code_to_month(match.group("month_code"))
            year = 2000 + int(match.group("yy"))
            raw_type = match.group("option_type")

            if option.option_type_codes is None:
                continue
            if raw_type == option.option_type_codes["call"]:
                opt_type = "call"
            else:
                opt_type = "put"

            results.append(
                ParsedTicker(
                    symbol=option.symbol,
                    year=year,
                    month=month,
                    tick_size=option.tick_size,
                    lot_size=option.contract_multiplier,
                    asset_type="option",
                    exchange=option.exchange,
                    option=option,
                    option_type=opt_type,
                    strike=match.group("strike"),
                )
            )

    return results


# ---------------------------------------------------------------------------
# Combined matching
# ---------------------------------------------------------------------------


def _find_all_matches(
    ticker: str,
    spec: SpecRepository,
    exchange: str | None = None,
) -> list[ParsedTicker]:
    candidates = _match_futures(ticker, spec) + _match_options(ticker, spec)
    if exchange is not None:
        candidates = [
            c
            for c in candidates
            if c.exchange and c.exchange.upper() == exchange.upper()
        ]
    return candidates


def _parse_full_ticker(
    ticker: str,
    spec: SpecRepository,
    exchange: str | None = None,
) -> ParsedTicker | None:
    """Try to match *ticker* against every contract and option pattern.

    Returns a single :class:`ParsedTicker`, raises :class:`AmbiguousTickerError`
    when multiple instruments match, or returns ``None`` on zero matches.
    """
    candidates = _find_all_matches(ticker, spec, exchange=exchange)
    if len(candidates) == 1:
        return candidates[0]
    if len(candidates) > 1:
        raise AmbiguousTickerError(ticker, candidates)
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
    exchange: str | None = None,
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

    if exchange is not None and contract.exchange.upper() != exchange.upper():
        return None

    ref_date = _coerce_date(reference_date)
    full_ticker = generate_ticker_for_contract(contract, ref_date, spec)
    result = _parse_full_ticker(full_ticker, spec, exchange=exchange)
    if result is not None:
        result = result.model_copy(
            update={
                "reference_date": ref_date,
                "is_trading_session": _is_trading_session(contract.exchange, ref_date),
            }
        )
    return result


def parse_ticker(
    ticker: str,
    spec: SpecRepository | None = None,
    reference_date: str | date | datetime | None = None,
    exchange: str | None = None,
) -> ParsedTicker:
    if spec is None:
        spec = load_spec()

    result = _parse_full_ticker(ticker, spec, exchange=exchange)
    if result is not None:
        if (
            reference_date is not None
            and result.asset_type == "future"
            and result.year is not None
        ):
            warnings.warn(
                f"reference_date is ignored for full ticker '{ticker}'; "
                f"year and month are derived directly from the ticker string",
                stacklevel=2,
            )
        return result

    result = _resolve_root_symbol(ticker, spec, reference_date, exchange=exchange)
    if result is not None:
        return result

    raise ValueError(f"Unable to parse ticker: {ticker}")


class _TickerParserBuilderBase:
    """Shared builder state -- methods available regardless of whether a ticker
    has been set."""

    def __init__(self) -> None:
        self._spec_path: Path | None = None
        self._ticker: str | None = None
        self._reference_date: str | date | datetime | None = None
        self._exchange: str | None = None

    def spec_path(self, path: str) -> _TickerParserBuilderBase:
        """Set a custom spec directory.  When omitted the bundled default is used."""
        self._spec_path = Path(path)
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

    def exchange(self, exchange: str) -> _TickerParserBuilderBase:
        """Restrict parsing to a single exchange for disambiguation."""
        self._exchange = exchange
        return self

    def build(self) -> TickerParser:
        """Build a **reusable** :class:`TickerParser`."""
        return TickerParser(spec_path=self._spec_path)


class _TickerParserBuilderWithTicker(_TickerParserBuilderBase):
    """Builder state after a ticker has been set -- ``parse()`` is available."""

    def ticker(self, ticker: str) -> _TickerParserBuilderWithTicker:
        """Replace the ticker string (stays in *has-ticker* state)."""
        self._ticker = ticker
        return self

    def spec_path(self, path: str) -> _TickerParserBuilderWithTicker:
        self._spec_path = Path(path)
        return self

    def spec(self, path: str) -> _TickerParserBuilderWithTicker:
        """Set a custom spec directory (alias for :meth:`spec_path`)."""
        return self.spec_path(path)

    def reference_date(
        self, ref_date: str | date | datetime
    ) -> _TickerParserBuilderWithTicker:
        self._reference_date = ref_date
        return self

    def exchange(self, exchange: str) -> _TickerParserBuilderWithTicker:
        """Restrict parsing to a single exchange for disambiguation."""
        self._exchange = exchange
        return self

    def parse(self) -> ParsedTicker:
        """One-shot: load spec, parse the ticker, and return the result."""
        spec = load_spec(self._spec_path)
        return parse_ticker(
            ticker=self._ticker,  # type: ignore[arg-type]
            spec=spec,
            reference_date=self._reference_date,
            exchange=self._exchange,
        )


class _TickerParserBuilderNoTicker(_TickerParserBuilderBase):
    """Builder state before a ticker has been set -- only ``build()`` and
    configuration methods are available."""

    def ticker(self, ticker: str) -> _TickerParserBuilderWithTicker:
        """Set the ticker string, enabling one-shot :meth:`parse`."""
        builder = _TickerParserBuilderWithTicker()
        builder._spec_path = self._spec_path
        builder._reference_date = self._reference_date
        builder._exchange = self._exchange
        builder._ticker = ticker
        return builder

    def spec_path(self, path: str) -> _TickerParserBuilderNoTicker:
        self._spec_path = Path(path)
        return self

    def spec(self, path: str) -> _TickerParserBuilderNoTicker:
        """Set a custom spec directory (alias for :meth:`spec_path`)."""
        return self.spec_path(path)

    def reference_date(
        self, ref_date: str | date | datetime
    ) -> _TickerParserBuilderNoTicker:
        self._reference_date = ref_date
        return self

    def exchange(self, exchange: str) -> _TickerParserBuilderNoTicker:
        """Restrict parsing to a single exchange for disambiguation."""
        self._exchange = exchange
        return self


class TickerParser:
    """Reusable parser that holds a loaded :class:`SpecRepository`.

    Create via :meth:`TickerParser()` (direct), or :meth:`TickerParser.builder`
    for fluent configuration.
    """

    def __init__(self, spec_path: str | Path | None = None) -> None:
        self.spec = load_spec(spec_path)

    @staticmethod
    def builder() -> _TickerParserBuilderNoTicker:
        """Start a :class:`TickerParserBuilder`."""
        return _TickerParserBuilderNoTicker()

    def parse(
        self,
        ticker: str,
        reference_date: str | date | datetime | None = None,
        exchange: str | None = None,
    ) -> ParsedTicker:
        return parse_ticker(
            ticker=ticker,
            spec=self.spec,
            reference_date=reference_date,
            exchange=exchange,
        )
