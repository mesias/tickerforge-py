# Smart Ticker Parsing

## Summary

`parse_ticker` accepts both **full tickers** (`INDM26`, `DOLK26`, `WINZ25`, `PETRA30`, `IBOVK26C120000`) and **root symbols** (`IND`, `DOL`, `WIN`). It parses **futures and options** from all supported markets and returns a single unified `ParsedTicker`.

Previously, a `reference_date` was always required to interpret the 2-digit year. The new behaviour removes this requirement for full tickers and only uses the date when resolving root symbols to their front-month contract.

## Behaviour

### Full futures ticker (e.g. `INDM26`)

Year and month are extracted directly from the ticker string:

- **Month** is decoded from the standard futures month code (`M` = June).
- **Year** is `2000 + yy` (`26` = 2026).

`reference_date` is **ignored** when a full ticker is provided.

### Option ticker (e.g. `PETRA30`, `IBOVK26C120000`)

Matched against option rules loaded from all `spec/contracts/**/*.yaml` files:

- **Equity** — pattern `{equity_root}{month_code}{strike}` using `call_month_codes`/`put_month_codes`. `equity_root("PETR4")` = `"PETR"`, so PETR4 January call with strike 30 → `PETRA30`.
- **Non-equity** — pattern `{symbol}{month_code}{yy}{C|P}{strike}`.

`year` is `None` for equity options (no year in the ticker).

### Root symbol (e.g. `IND`)

When the input does not match any `ticker_format` pattern but matches a known contract symbol, the parser resolves the front-month contract:

1. If `reference_date` is provided, it is used as the as-of date.
2. If omitted, **today** is used.

### Unknown input

If the input matches nothing, a `ValueError` is raised containing `"Unable to parse ticker"`.

### Ambiguous ticker

When a ticker matches instruments on multiple markets/types, `AmbiguousTickerError` is raised. Pass `exchange=` to disambiguate.

## `ParsedTicker` fields

| Field | Type | Description |
|---|---|---|
| `symbol` | `str` | Root symbol (e.g. `IND`, `PETR4` for equity options) |
| `year` | `int \| None` | Contract year; `None` for equity options |
| `month` | `int` | Contract month (1–12) |
| `tick_size` | `float` | Minimum price increment |
| `lot_size` | `float` | Contract multiplier |
| `asset_type` | `"future" \| "option"` | Instrument type |
| `exchange` | `str \| None` | Exchange code (e.g. `"B3"`, `"CME"`) |
| `contract` | `ContractSpec \| None` | Full contract spec; `None` for options |
| `option` | `OptionSpec \| None` | Option rule spec; `None` for futures |
| `option_type` | `"call" \| "put" \| None` | Option direction; `None` for futures |
| `strike` | `str \| None` | Raw strike string from the ticker; `None` for futures |
| `underlying` | `str \| None` | Full underlying symbol for equity options (e.g. `"PETR4"`); `None` for futures/non-equity options |
| `reference_date` | `date \| None` | Date used for root-symbol resolution; `None` for full tickers |
| `is_trading_session` | `bool \| None` | Whether `reference_date` is an exchange trading session; `None` for full tickers |

## `AmbiguousTickerError`

Raised when `parse_ticker` finds multiple instruments matching the same ticker string (e.g. a symbol defined on both B3 and CME). Inherits from `ValueError`.

```python
from tickerforge import AmbiguousTickerError, parse_ticker

try:
    parsed = parse_ticker("AMBIGUOUS")
except AmbiguousTickerError as e:
    print(e)  # lists each matching instrument and hints to pass exchange=
```

## API

```python
from tickerforge import parse_ticker

# Futures
parsed = parse_ticker("INDM26")
assert parsed.asset_type == "future"
assert parsed.year == 2026

# CME futures
parsed = parse_ticker("ESM26")
assert parsed.exchange == "CME"

# B3 equity option (equity_root("PETR4") = "PETR")
parsed = parse_ticker("PETRA30")
assert parsed.asset_type == "option"
assert parsed.option_type == "call"
assert parsed.underlying == "PETR4"
assert parsed.month == 1          # A = January
assert parsed.strike == "30"
assert parsed.year is None        # no year in equity option ticker
assert parsed.exchange == "B3"

# B3 index option
parsed = parse_ticker("IBOVK26C120000")
assert parsed.underlying is None  # non-equity options use symbol, not underlying
assert parsed.symbol == "IBOV"
assert parsed.month == 5          # K = May
assert parsed.year == 2026

# Exchange filter
parsed = parse_ticker("ESM26", exchange="CME")
parsed = parse_ticker("PETRA30", exchange="B3")

# Root symbol
parsed = parse_ticker("IND")
parsed = parse_ticker("DOL", reference_date="2026-04-15")
```

### `is_trading_session` resolution flow

![is_trading_session resolution flow](is_trading_session_flow.svg)

When a **full ticker** is parsed, both `reference_date` and `is_trading_session` are `None` — no date context exists.

When a **root symbol** is parsed, the date (explicit or today) is used to resolve the front-month contract. The parser checks the exchange calendar:

- **Weekday with exchange open** → `is_trading_session = True`
- **Weekend or exchange holiday** → `is_trading_session = False`

## Builder pattern

`TickerParser.builder()` returns a fluent builder. The builder enforces a typestate-like contract: `parse()` is only available after `ticker()` has been called.

| Terminal method | Returns | When to use |
|---|---|---|
| `.build()` | `TickerParser` | Build a reusable parser |
| `.parse()` | `ParsedTicker` | One-shot: load spec + parse in one call |

Builder methods: `spec_path(path)`, `spec(path)` (alias), `ticker(t)`, `reference_date(d)`, `exchange(e)`.

```python
from tickerforge import TickerParser

# Build a reusable parser
parser = TickerParser.builder().build()

# One-shot futures parse
parsed = TickerParser.builder().ticker("INDM26").parse()

# One-shot option parse with exchange filter
parsed = TickerParser.builder().ticker("PETRA30").exchange("B3").parse()

# One-shot with custom spec and date
parsed = (
    TickerParser.builder()
    .spec("/path/to/spec")
    .ticker("IND")
    .reference_date("2026-06-01")
    .parse()
)
```

## Test coverage

`tests/test_ticker_parsing.py` — existing futures parsing tests.

`tests/test_option_parsing.py` — 29 option parsing tests:

- `test_spec_loads_options`, `test_spec_options_include_equity_type`, `test_spec_options_include_index_type`
- Equity options: `PETRA30`, `PETRM30`, `VALEF50`, `ITUBX25`
- Index options: `IBOVK26C120000`, `IBOVK26P100000`
- Dollar options: `DOLK26C5000`, `DOLK26P4800`
- Interest-rate options: `IDIF26C100000`, `IDIF26P95000`
- Futures backward compat: `INDM26`, `ESM26`, `WINM26`
- DOL disambiguation: `DOLK26` vs `DOLK26C5000`
- Exchange filter: 5 tests
- Unknown tickers: 2 tests
- `test_all_equity_underlyings_parseable`
