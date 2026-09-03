from __future__ import annotations

import re
import warnings
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Literal

from dateutil import parser as date_parser
from pydantic import BaseModel

from tickerforge.contract_cycle import resolve_contract_months
from tickerforge.models import ContractSpec, EquitySpec, OptionSpec
from tickerforge.month_codes import code_to_month, month_to_code
from tickerforge.spec_loader import SpecRepository, load_spec
from tickerforge.ticker_generator import format_contract_ticker


class ParsedTicker(BaseModel):
    symbol: str
    year: int | None = None
    month: int | None = None
    tick_size: float
    ctr_std: int
    ctr_size: float | None = None
    asset_type: Literal["future", "option", "equity"] = "future"
    exchange: str | None = None
    contract: ContractSpec | None = None
    option: OptionSpec | None = None
    equity: EquitySpec | None = None
    option_type: Literal["call", "put"] | None = None
    strike: str | None = None
    underlying: str | None = None
    reference_date: date | None = None
    is_trading_session: bool | None = None
    # Bracket-tag offset (e.g. ``DOL[1]`` -> 1, ``IND[-1]`` -> -1) used to resolve a
    # root symbol to a specific contract in the tradeable/expired list. ``None`` for
    # full tickers (``DOLN26``) and plain roots not routed through the tag path.
    offset: int | None = None
    # Whether the contract is tradeable/valid on the reference date.
    is_valid: bool | None = None

    @property
    def ticker(self) -> str:
        """Full trading symbol string (e.g. ``DOLN26``, ``PETRA30``, ``DOLK26C5000``)."""
        return self.format_ticker()

    def format_ticker(self) -> str:
        """Rebuild the exchange ticker string from this parsed result."""
        if self.asset_type == "equity":
            return self.symbol

        if self.asset_type == "future":
            if self.contract is None or self.year is None or self.month is None:
                raise ValueError(
                    "Cannot format futures ticker without contract, year, and month"
                )
            return format_contract_ticker(self.contract, self.year, self.month)

        if (
            self.option is None
            or self.option_type is None
            or self.strike is None
            or self.month is None
        ):
            raise ValueError(
                "Cannot format option ticker without option, option_type, strike, and month"
            )

        if self.option.type == "equity":
            underlying = self.underlying or self.symbol
            root = _equity_root(underlying)
            codes = (
                (self.option.call_month_codes or _EQUITY_CALL_CODES)
                if self.option_type == "call"
                else (self.option.put_month_codes or _EQUITY_PUT_CODES)
            )
            month_code = codes[self.month - 1]
            return f"{root}{month_code}{self.strike}"

        if self.year is None or self.option.option_type_codes is None:
            raise ValueError(
                "Cannot format non-equity option ticker without year and option_type_codes"
            )
        type_code = self.option.option_type_codes[self.option_type]
        return (
            f"{self.symbol}"
            f"{month_to_code(self.month)}"
            f"{self.year % 100:02d}"
            f"{type_code}"
            f"{self.strike}"
        )


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
# Futures / options pattern matching (precompiled per SpecRepository)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class _EquityOptionPattern:
    pattern: re.Pattern[str]
    underlying: str
    option: OptionSpec


@dataclass(frozen=True)
class _NonequityOptionPattern:
    pattern: re.Pattern[str]
    option: OptionSpec


@dataclass
class _PatternIndex:
    """Precompiled futures/options regexes for one :class:`SpecRepository`."""

    futures: list[tuple[re.Pattern[str], ContractSpec]]
    equity_options: list[_EquityOptionPattern]
    nonequity_options: list[_NonequityOptionPattern]


def _pattern_for_contract(contract: ContractSpec) -> re.Pattern[str]:
    escaped = re.escape(contract.ticker_format)
    pattern = (
        escaped.replace(r"\{symbol\}", re.escape(contract.symbol))
        .replace(r"\{month_code\}", r"(?P<month_code>[FGHJKMNQUVXZ])")
        .replace(r"\{yy\}", r"(?P<yy>\d{2})")
    )
    return re.compile(f"^{pattern}$")


def _build_pattern_index(spec: SpecRepository) -> _PatternIndex:
    futures = [
        (_pattern_for_contract(contract), contract)
        for contract in spec.contracts.values()
    ]
    equity_options: list[_EquityOptionPattern] = []
    nonequity_options: list[_NonequityOptionPattern] = []
    for option in spec.options:
        if option.type == "equity":
            for pat, underlying in _patterns_for_equity_option(option):
                equity_options.append(
                    _EquityOptionPattern(
                        pattern=pat, underlying=underlying, option=option
                    )
                )
        else:
            nonequity_pat = _pattern_for_nonequity_option(option)
            if nonequity_pat is not None:
                nonequity_options.append(
                    _NonequityOptionPattern(pattern=nonequity_pat, option=option)
                )
    return _PatternIndex(
        futures=futures,
        equity_options=equity_options,
        nonequity_options=nonequity_options,
    )


def _pattern_index(spec: SpecRepository) -> _PatternIndex:
    cached = spec._pattern_index
    if isinstance(cached, _PatternIndex):
        return cached
    built = _build_pattern_index(spec)
    spec._pattern_index = built
    return built


def _match_futures(ticker: str, spec: SpecRepository) -> list[ParsedTicker]:
    results: list[ParsedTicker] = []
    for pattern, contract in _pattern_index(spec).futures:
        match = pattern.match(ticker)
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
                ctr_std=contract.ctr_std,
                ctr_size=contract.ctr_size,
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
    index = _pattern_index(spec)

    for eq_entry in index.equity_options:
        match = eq_entry.pattern.match(ticker)
        if not match:
            continue
        parsed = _equity_code_to_month_and_type(
            match.group("month_code"), eq_entry.option
        )
        if parsed is None:
            continue
        month, opt_type = parsed
        option = eq_entry.option
        underlying = eq_entry.underlying
        results.append(
            ParsedTicker(
                symbol=underlying,
                year=None,
                month=month,
                tick_size=option.tick_size,
                ctr_std=option.ctr_std,
                ctr_size=option.ctr_size,
                asset_type="option",
                exchange=option.exchange,
                option=option,
                option_type=opt_type,
                strike=match.group("strike"),
                underlying=underlying,
            )
        )

    for ne_entry in index.nonequity_options:
        match = ne_entry.pattern.match(ticker)
        if not match:
            continue

        option = ne_entry.option
        month = code_to_month(match.group("month_code"))
        year = 2000 + int(match.group("yy"))
        raw_type = match.group("option_type")

        if option.option_type_codes is None:
            continue
        if raw_type == option.option_type_codes["call"]:
            ne_opt_type: Literal["call", "put"] = "call"
        else:
            ne_opt_type = "put"

        results.append(
            ParsedTicker(
                symbol=option.symbol,
                year=year,
                month=month,
                tick_size=option.tick_size,
                ctr_std=option.ctr_std,
                ctr_size=option.ctr_size,
                asset_type="option",
                exchange=option.exchange,
                option=option,
                option_type=ne_opt_type,
                strike=match.group("strike"),
            )
        )

    return results


# ---------------------------------------------------------------------------
# Lightweight classification (no calendars / validity / generator)
# ---------------------------------------------------------------------------


class TickerClass(BaseModel):
    """Lightweight ticker identity: type and root without calendars or validity."""

    asset_type: Literal["future", "option", "equity"]
    root: str
    exchange: str | None = None
    year: int | None = None
    month: int | None = None
    option_type: Literal["call", "put"] | None = None
    strike: str | None = None
    underlying: str | None = None


class AmbiguousClassifyError(ValueError):
    """Raised when :func:`classify_ticker` matches multiple instruments."""

    def __init__(self, ticker: str, matches: list[TickerClass]) -> None:
        self.ticker = ticker
        self.matches = matches
        detail = "\n".join(
            f"  - {m.asset_type} on {m.exchange}: {m.root}" for m in matches
        )
        super().__init__(
            f"Ambiguous ticker '{ticker}' matched {len(matches)} instruments:\n{detail}\n"
            f"Pass exchange= to disambiguate."
        )


def _classify_futures(ticker: str, spec: SpecRepository) -> list[TickerClass]:
    results: list[TickerClass] = []
    for pattern, contract in _pattern_index(spec).futures:
        match = pattern.match(ticker)
        if not match:
            continue
        results.append(
            TickerClass(
                asset_type="future",
                root=contract.symbol,
                exchange=contract.exchange,
                year=2000 + int(match.group("yy")),
                month=code_to_month(match.group("month_code")),
            )
        )
    return results


def _classify_options(ticker: str, spec: SpecRepository) -> list[TickerClass]:
    results: list[TickerClass] = []
    index = _pattern_index(spec)

    for eq_entry in index.equity_options:
        match = eq_entry.pattern.match(ticker)
        if not match:
            continue
        parsed = _equity_code_to_month_and_type(
            match.group("month_code"), eq_entry.option
        )
        if parsed is None:
            continue
        month, eq_opt_type = parsed
        if eq_opt_type not in ("call", "put"):
            continue
        results.append(
            TickerClass(
                asset_type="option",
                root=eq_entry.underlying,
                exchange=eq_entry.option.exchange,
                month=month,
                option_type=eq_opt_type,
                strike=match.group("strike"),
                underlying=eq_entry.underlying,
            )
        )

    for ne_entry in index.nonequity_options:
        match = ne_entry.pattern.match(ticker)
        if not match:
            continue
        option = ne_entry.option
        if option.option_type_codes is None:
            continue
        raw_type = match.group("option_type")
        ne_opt_type: Literal["call", "put"] = (
            "call" if raw_type == option.option_type_codes["call"] else "put"
        )
        results.append(
            TickerClass(
                asset_type="option",
                root=option.symbol or "",
                exchange=option.exchange,
                year=2000 + int(match.group("yy")),
                month=code_to_month(match.group("month_code")),
                option_type=ne_opt_type,
                strike=match.group("strike"),
            )
        )

    return results


def _pick_unique_class(ticker: str, candidates: list[TickerClass]) -> TickerClass:
    if len(candidates) == 1:
        return candidates[0]
    if len(candidates) > 1:
        raise AmbiguousClassifyError(ticker, candidates)
    raise ValueError(f"Unable to classify ticker: {ticker}")


def classify_ticker(
    ticker: str,
    spec: SpecRepository | None = None,
    exchange: str | None = None,
) -> TickerClass:
    """Classify a ticker into asset type and root without calendars or validity.

    Faster than :func:`parse_ticker` for UI filters and routing: skips expiration
    rules, trading calendars, front-month generation, and cycle-month checks.
    Full tickers, cash equities, futures roots, and ``SYMBOL[n]`` tags are supported.
    """
    if spec is None:
        spec = load_spec()

    key = ticker.upper()
    if key in spec.equities:
        eq = spec.equities[key]
        if exchange is None or eq.exchange.upper() == exchange.upper():
            return TickerClass(
                asset_type="equity",
                root=eq.symbol,
                exchange=eq.exchange,
            )

    candidates = _classify_futures(ticker, spec) + _classify_options(ticker, spec)
    if exchange is not None:
        candidates = [
            c
            for c in candidates
            if c.exchange and c.exchange.upper() == exchange.upper()
        ]
    if candidates:
        return _pick_unique_class(ticker, candidates)

    tag_match = _TAG_RE.match(ticker)
    if tag_match is not None:
        root = tag_match.group("root").upper()
        contract = spec.contracts.get(root)
        if contract is not None and (
            exchange is None or contract.exchange.upper() == exchange.upper()
        ):
            return TickerClass(
                asset_type="future",
                root=contract.symbol,
                exchange=contract.exchange,
            )
        raise ValueError(f"Unable to classify ticker: {ticker}")

    contract = spec.contracts.get(key)
    if contract is not None and (
        exchange is None or contract.exchange.upper() == exchange.upper()
    ):
        return TickerClass(
            asset_type="future",
            root=contract.symbol,
            exchange=contract.exchange,
        )

    raise ValueError(f"Unable to classify ticker: {ticker}")


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
    return _resolve_tagged_root(
        ticker, spec, reference_date, exchange=exchange, offset=0
    )


# ``SYMBOL[n]`` bracket tag: ``DOL[1]``, ``WIN[2]``, ``IND[-1]``. Full tickers
# such as ``DOLN26`` or ``DOLK26C5000`` contain no ``[`` and so do not match.
_TAG_RE = re.compile(
    r"^(?P<root>[A-Za-z][A-Za-z0-9]*)\[(?:(?P<offset>-?\d+)?@(?P<cond>roll)|(?P<offset_val>-?\d+))\]$"
)


def _is_roll_day(contract: ContractSpec, ref_date: date, spec: SpecRepository) -> bool:
    from tickerforge.calendars import get_calendar
    from tickerforge.contract_cycle import resolve_contract_months
    from tickerforge.expiration_rules import resolve_expiration
    from tickerforge.ticker_generator import _resolve_last_trading_day

    rule = spec.expiration_rules[contract.expiration_rule]
    calendar = get_calendar(contract.exchange)
    cycle = spec.contract_cycles[contract.contract_cycle]

    for year in (ref_date.year - 1, ref_date.year, ref_date.year + 1):
        for month in resolve_contract_months(cycle, year):
            expiration_date = resolve_expiration(contract, year, month, rule, calendar)
            ltd = _resolve_last_trading_day(expiration_date, rule, calendar)
            if ref_date == ltd:
                return True
    return False


def _resolve_tagged_root(
    ticker: str,
    spec: SpecRepository,
    reference_date: str | date | datetime | None,
    exchange: str | None = None,
    offset: int = 0,
    condition: str | None = None,
) -> ParsedTicker | None:
    """Resolve a root symbol (with optional bracket offset) to a :class:`ParsedTicker`.

    ``offset`` defaults to 0 (front month) so plain roots and ``SYMBOL[0]`` behave
    identically. Stamps ``reference_date``, ``is_trading_session`` and ``offset``
    on the result. Returns ``None`` when the root is unknown or the exchange filter
    rejects it; out-of-range offsets raise :class:`ValueError` from the generator.
    """
    from tickerforge.ticker_generator import generate_ticker_for_contract

    contract = spec.contracts.get(ticker.upper())
    if contract is None:
        return None

    if exchange is not None and contract.exchange.upper() != exchange.upper():
        return None

    ref_date = _coerce_date(reference_date)

    if condition == "roll":
        if not _is_roll_day(contract, ref_date, spec):
            raise ValueError(
                f"Ticker '{contract.symbol}[{offset}@roll]' is not valid on {ref_date.isoformat()} "
                f"because it is not the last trading day of the expiring contract."
            )

    full_ticker = generate_ticker_for_contract(contract, ref_date, spec, offset=offset)
    result = _parse_full_ticker(full_ticker, spec, exchange=exchange)
    if result is not None:
        from tickerforge.calendars import get_calendar
        from tickerforge.expiration_rules import resolve_expiration
        from tickerforge.ticker_generator import _is_contract_tradeable

        rule = spec.expiration_rules[contract.expiration_rule]
        calendar = get_calendar(contract.exchange)
        assert result.year is not None
        assert result.month is not None
        expiration_date = resolve_expiration(
            contract, result.year, result.month, rule, calendar
        )
        is_valid = _is_contract_tradeable(ref_date, expiration_date, rule, calendar)

        result = result.model_copy(
            update={
                "reference_date": ref_date,
                "is_trading_session": _is_trading_session(contract.exchange, ref_date),
                "offset": offset,
                "is_valid": is_valid,
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

    # Check equities first.
    key = ticker.upper()
    if key in spec.equities:
        eq = spec.equities[key]
        matches_exchange = True
        if exchange is not None:
            if eq.exchange.upper() != exchange.upper():
                matches_exchange = False
        if matches_exchange:
            ref_date = (
                _coerce_date(reference_date) if reference_date is not None else None
            )
            is_trading_session = None
            if ref_date is not None:
                is_trading_session = _is_trading_session(eq.exchange, ref_date)
            return ParsedTicker(
                symbol=eq.symbol,
                tick_size=eq.tick_size or 0.01,
                ctr_std=eq.ctr_std or 100,
                ctr_size=eq.ctr_size or 1.0,
                asset_type="equity",
                exchange=eq.exchange,
                equity=eq,
                reference_date=ref_date,
                is_trading_session=is_trading_session,
                is_valid=True if ref_date is not None else None,
            )

    result = _parse_full_ticker(ticker, spec, exchange=exchange)
    if result is not None:
        if (
            reference_date is not None
            and result.asset_type == "future"
            and result.year is not None
        ):
            ref_date = _coerce_date(reference_date)
            contract = result.contract
            assert contract is not None
            assert result.month is not None
            from tickerforge.calendars import get_calendar
            from tickerforge.expiration_rules import resolve_expiration
            from tickerforge.ticker_generator import _is_contract_tradeable

            rule = spec.expiration_rules[contract.expiration_rule]
            calendar = get_calendar(contract.exchange)
            expiration_date = resolve_expiration(
                contract, result.year, result.month, rule, calendar
            )
            is_valid = _is_contract_tradeable(ref_date, expiration_date, rule, calendar)

            result = result.model_copy(
                update={
                    "reference_date": ref_date,
                    "is_trading_session": _is_trading_session(
                        contract.exchange, ref_date
                    ),
                    "is_valid": is_valid,
                }
            )

            warnings.warn(
                f"reference_date is ignored for full ticker '{ticker}'; "
                f"year and month are derived directly from the ticker string",
                stacklevel=2,
            )
        return result

    tag_match = _TAG_RE.match(ticker)
    if tag_match is not None:
        root = tag_match.group("root")
        contract = spec.contracts.get(root.upper())
        if contract is None:
            raise ValueError(f"Unable to parse ticker: {ticker}")
        if exchange is not None and contract.exchange.upper() != exchange.upper():
            raise ValueError(f"Unable to parse ticker: {ticker}")

        cond = tag_match.group("cond")
        if cond is not None:
            offset_str = tag_match.group("offset")
            if offset_str is not None:
                offset = int(offset_str)
            else:
                rule = spec.expiration_rules[contract.expiration_rule]
                offset = 0 if rule.should_roll_on_last_trading_day() else 1
        else:
            offset = int(tag_match.group("offset_val"))

        result = _resolve_tagged_root(
            root,
            spec,
            reference_date,
            exchange=exchange,
            offset=offset,
            condition=cond,
        )
        if result is not None:
            return result
        raise ValueError(f"Unable to parse ticker: {ticker}")

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
