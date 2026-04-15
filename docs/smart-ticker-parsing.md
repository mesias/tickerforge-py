# Smart Ticker Parsing

## Summary

`parse_ticker` now accepts both **full tickers** (`INDM26`, `DOLK26`, `WINZ25`) and **root symbols** (`IND`, `DOL`, `WIN`).

Previously, a `reference_date` was always required to interpret the 2-digit year in every ticker string. The new behaviour removes this requirement for full tickers and only uses the date when resolving root symbols to their front-month contract.

## Behaviour

### Full ticker (e.g. `INDM26`)

Year and month are extracted directly from the ticker string:

- **Month** is decoded from the standard futures month code (`M` = June).
- **Year** is `2000 + yy` (`26` = 2026).

`reference_date` is **ignored** when a full ticker is provided, so the same call always returns the same result regardless of when it runs.

### Root symbol (e.g. `IND`)

When the input does not match any `ticker_format` pattern but matches a known contract symbol, the parser resolves the front-month contract:

1. If `reference_date` is provided, it is used as the as-of date for front-month resolution.
2. If `reference_date` is omitted, **today** is used.
3. The generator produces the full ticker for that front-month, which is then parsed with the full-ticker path above.

### Unknown input

If the input matches neither a full ticker pattern nor a known root symbol, a `ValueError` is raised.

## API

```python
from tickerforge import parse_ticker

# Full ticker — no date needed
parsed = parse_ticker("INDM26")

# Full ticker — reference_date is ignored
parsed = parse_ticker("INDM26", reference_date="1990-01-01")

# Root symbol — resolves front-month for today
parsed = parse_ticker("IND")

# Root symbol — resolves front-month for a specific date
parsed = parse_ticker("DOL", reference_date="2026-04-15")
```

`ParsedTicker` fields:

| Field | Type | Description |
|---|---|---|
| `symbol` | `str` | Root symbol (e.g. `IND`) |
| `year` | `int` | Contract year |
| `month` | `int` | Contract month (1–12) |
| `tick_size` | `float` | Minimum price increment from the contract spec |
| `lot_size` | `float` | Contract multiplier from the contract spec |
| `contract` | `ContractSpec` | Full contract specification object |
| `reference_date` | `date \| None` | Date used for root-symbol resolution; `None` for full tickers |
| `is_trading_session` | `bool \| None` | Whether `reference_date` is an exchange trading session; `None` for full tickers |

### `is_trading_session` resolution flow

![is_trading_session resolution flow](is_trading_session_flow.svg)

When a **full ticker** is parsed, both `reference_date` and `is_trading_session` are `None` — no date context exists.

When a **root symbol** is parsed, the date (explicit or today) is used to resolve the front-month contract. The parser then checks the exchange calendar to determine whether that date is an actual trading session:

- **Weekday with exchange open** → `is_trading_session = True`
- **Weekend or exchange holiday** → `is_trading_session = False`

## Builder pattern

`TickerParser.builder()` returns a fluent builder.  The builder enforces a typestate-like
contract: `parse()` is only available after `ticker()` has been called.

| Terminal method | Returns | When to use |
|---|---|---|
| `.build()` | `TickerParser` | Build a reusable parser |
| `.parse()` | `ParsedTicker` | One-shot: load spec + parse in one call |

Builder methods: `spec_path(path)`, `spec(path)` (alias), `ticker(t)`, `reference_date(d)`.

```python
from tickerforge import TickerParser

# Build a reusable parser
parser = TickerParser.builder().build()

# One-shot parse
parsed = TickerParser.builder().ticker("INDM26").parse()

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

New tests in `tests/test_ticker_parsing.py`:

- `test_parse_full_ticker_without_reference_date`
- `test_parse_full_ticker_ignores_wrong_reference_date`
- `test_parse_full_ticker_dol`
- `test_parse_full_ticker_win`
- `test_parse_root_symbol_with_reference_date`
- `test_parse_root_symbol_without_reference_date`
- `test_parse_root_symbol_dol`
- `test_parse_root_symbol_win`
- `test_parse_unknown_symbol_raises`
- `test_builder_build_default_spec`
- `test_builder_build_custom_spec`
- `test_builder_parse_full_ticker`
- `test_builder_parse_root_with_date`
- `test_builder_parse_root_without_date`
- `test_builder_parse_custom_spec_with_date`
- `test_builder_parse_unknown_errors`
- `test_builder_parse_full_ignores_date`
- `test_builder_date_before_ticker`
- `test_builder_no_ticker_has_no_parse`
