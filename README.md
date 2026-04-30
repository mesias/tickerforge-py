# tickerforge

[![codecov](https://codecov.io/gh/mesias/tickerforge-py/branch/main/graph/badge.svg)](https://codecov.io/gh/mesias/tickerforge-py)
[![CI](https://github.com/mesias/tickerforge-py/actions/workflows/ci.yml/badge.svg)](https://github.com/mesias/tickerforge-py/actions/workflows/ci.yml)
[![Python versions](https://img.shields.io/badge/python-3.10%20|%203.12%20|%203.14-3776ab?labelColor=434343&logo=python&logoColor=ffd43b)](https://github.com/mesias/tickerforge-py/blob/main/.github/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://github.com/mesias/tickerforge-py/blob/main/LICENSE)

[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
[![Imports: isort](https://img.shields.io/badge/%20imports-isort-%231674b2?style=flat&labelColor=ef8336)](https://pycqa.github.io/isort/)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![Checked with mypy](https://www.mypy-lang.org/static/mypy_badge.svg)](https://www.mypy-lang.org/)

[![Repo Stats](https://github-readme-stats.vercel.app/api/pin/?username=mesias&repo=tickerforge-py&theme=dark)](https://github.com/mesias/tickerforge-py)

Python library that loads [`tickerforge-spec`](https://github.com/mesias/tickerforge-spec) and
generates/parses derivatives tickers.

## Install

```bash
pip install "git+https://github.com/mesias/tickerforge-py.git"
```

`tickerforge` depends on `tickerforge-spec-data` from the same repository root (`pyproject.toml` in [`tickerforge-spec`](https://github.com/mesias/tickerforge-spec)).

## Usage

By default, `TickerForge` / `TickerParser` use the spec bundled in the `tickerforge-spec-data` package (installed from [`tickerforge-spec`](https://github.com/mesias/tickerforge-spec) via `pip`). Pass `spec_path` only to override.

### Generating tickers

```python
from tickerforge import TickerForge

forge = TickerForge()
ticker = forge.generate("IND", date="2025-04-01")
print(ticker)  # e.g. INDM25
```

Custom spec directory:

```python
forge = TickerForge(spec_path="/path/to/tickerforge-spec/spec")
```

### Parsing tickers — futures and options (smart parsing)

`parse_ticker` accepts **full tickers** (`INDM26`, `PETRA30`, `IBOVK26C120000`) or **root symbols** (`IND`). It parses **both futures and options** and returns a unified `ParsedTicker`.

Full tickers derive year/month directly from the string — no `reference_date` required.
Root symbols resolve the front-month contract via the generator; `reference_date` defaults to today when omitted.

```python
from tickerforge import TickerParser, parse_ticker

# Futures — full ticker
parsed = parse_ticker("INDM26")
print(parsed.symbol, parsed.year, parsed.month)  # IND 2026 6
print(parsed.tick_size, parsed.lot_size)          # 5.0 1.0
print(parsed.asset_type)                          # "future"

# Futures — root symbol
parsed = parse_ticker("IND")
parsed = parse_ticker("IND", reference_date="2026-06-01")

# CME futures
parsed = parse_ticker("ESM26")
print(parsed.symbol, parsed.exchange)  # ES CME

# B3 equity option: equity_root("PETR4") = "PETR" → "PETRA30"
parsed = parse_ticker("PETRA30")
print(parsed.asset_type)      # "option"
print(parsed.option_type)     # "call"
print(parsed.underlying)      # "PETR4"
print(parsed.month)           # 1  (A = January)
print(parsed.strike)          # "30"
print(parsed.year)            # None (equity options have no year)
print(parsed.exchange)        # "B3"

# B3 index option
parsed = parse_ticker("IBOVK26C120000")
print(parsed.underlying, parsed.month, parsed.year, parsed.strike)  # IBOV 5 2026 120000

# B3 dollar option
parsed = parse_ticker("DOLK26C5000")
print(parsed.option_type, parsed.strike)  # call 5000

# DOL future vs DOL option — no ambiguity
parse_ticker("DOLK26")      # → future
parse_ticker("DOLK26C5000") # → option

# Exchange filter
parsed = parse_ticker("ESM26", exchange="CME")
# AmbiguousTickerError raised if a ticker matches multiple markets;
# pass exchange= to disambiguate

# Using TickerParser (reuses a loaded spec)
parser = TickerParser()
parsed = parser.parse("DOLK26")
parsed = parser.parse("DOLK26C5000", exchange="B3")
```

### Builder pattern

`TickerParser.builder()` provides a fluent API for configuration and one-shot parsing:

```python
from tickerforge import TickerParser

# Build a reusable parser (default spec)
parser = TickerParser.builder().build()
parsed = parser.parse("INDM26")

# Build a reusable parser (custom spec)
parser = TickerParser.builder().spec_path("/path/to/spec").build()

# One-shot parse — full ticker
parsed = TickerParser.builder().ticker("INDM26").parse()

# One-shot parse — option with exchange filter
parsed = TickerParser.builder().ticker("PETRA30").exchange("B3").parse()

# One-shot parse — root symbol with date
parsed = (
    TickerParser.builder()
    .ticker("IND")
    .reference_date("2026-06-01")
    .parse()
)

# One-shot parse — custom spec + date
parsed = (
    TickerParser.builder()
    .spec_path("/path/to/spec")
    .ticker("IND")
    .reference_date("2026-06-01")
    .parse()
)
```

The builder enforces that `parse()` is only available after `ticker()` has been called.

### Contract-centric (tick, session, trading symbol)

`load_spec()` returns a repository of contracts and equities. Each `ContractSpec` includes tick size and (after load) regular session times and exchange timezone, plus helpers that use the **bundled default spec** unless you pass `spec=…`:

```python
from tickerforge import load_spec

spec = load_spec()

# Loading a cash equity
petr4 = spec.equities["PETR4"]
petr4.contract_multiplier        # 1.0
petr4.regular_session().start    # "10:00"

# Loading a future
dol = spec.get_contract("DOL")

dol.tick_size
dol.regular_session_start_end()  # e.g. ("09:00", "18:30")
dol.exchange_timezone
# `dol.sessions` is an ordered list of `SessionSegment`; in YAML, sessions are a map keyed by
# band name (`regular`, …) and each key is copied into `SessionSegment.name` at load time.

# Front-month ticker — default bundled spec (omit `spec`)
dol.trading_symbol_today()
dol.trading_symbol_for("2026-03-15")

# Same helpers with an explicit `SpecRepository` (e.g. custom `load_spec(path)`)
dol.trading_symbol_today(spec=spec)
dol.trading_symbol_for("2026-03-15", spec=spec)
```

Repeated calls with the default path reload the spec each time; for hot paths, pass `spec=` once.

## What this version supports

- Loading exchanges, contract cycles, expiration rules, futures, **options**, and **equities** from all `contracts/**/*.yaml` and `equities/**/*.yaml` (B3, CME, …)
- Validating loaded structures with Pydantic models
- Resolving contract months by cycle
- Resolving expiration dates with spec-driven exchange calendars
- Rule-based holiday definitions (fixed dates, Easter offsets, nth-weekday) loaded from `spec/schedules/`
- Fallback to `exchange_calendars` when no spec schedule exists
- Generating futures tickers from `{symbol}{month_code}{yy}`-style templates
- **Multi-asset parsing**: futures and options (B3 equity, index, dollar, interest-rate; CME futures) via a single `parse_ticker` call
- `AmbiguousTickerError` when a ticker matches multiple markets; `exchange=` parameter to disambiguate
- `ParsedTicker.asset_type`, `option_type`, `strike`, `underlying`, `exchange` fields for options
- Golden calendar validation for B3 WIN/IND/DOL (2023--2026)

## Run tests

Tests load YAML and fixtures from a `spec/` directory at the project root—the same tree bundled into the [`tickerforge-spec-data`](https://github.com/mesias/tickerforge-spec) wheel from that repo’s root. Clone the spec repo once:

```bash
git clone --depth 1 https://github.com/mesias/tickerforge-spec.git /tmp/tickerforge-spec
cp -r /tmp/tickerforge-spec/spec .
pytest
```
