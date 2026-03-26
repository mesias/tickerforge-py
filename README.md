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

```python
from tickerforge import TickerForge, TickerParser

forge = TickerForge()
ticker = forge.generate("IND", date="2025-04-01")
print(ticker)  # e.g. INDM25

parser = TickerParser()
parsed = parser.parse(ticker, reference_date="2025-04-01")
print(parsed.symbol, parsed.year, parsed.month)
```

Custom spec directory:

```python
forge = TickerForge(spec_path="/path/to/tickerforge-spec/spec")
```

### Contract-centric (tick, session, trading symbol)

`load_spec()` returns a repository of contracts. Each `ContractSpec` includes tick size and (after load) regular session times and exchange timezone, plus helpers that use the **bundled default spec** unless you pass `spec=…`:

```python
from tickerforge import load_spec

spec = load_spec()
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

- Loading exchanges, contract cycles, expiration rules, and futures contracts from YAML
- Validating loaded structures with Pydantic models
- Resolving contract months by cycle
- Resolving expiration dates with spec-driven exchange calendars
- Rule-based holiday definitions (fixed dates, Easter offsets, nth-weekday) loaded from `spec/schedules/`
- Fallback to `exchange_calendars` when no spec schedule exists
- Generating futures tickers from `{symbol}{month_code}{yy}`-style templates
- Parsing tickers back to structured contract information
- Golden calendar validation for B3 WIN/IND/DOL (2023--2026)

## Run tests

Tests load YAML and fixtures from a `spec/` directory at the project root—the same tree bundled into the [`tickerforge-spec-data`](https://github.com/mesias/tickerforge-spec) wheel from that repo’s root. Clone the spec repo once:

```bash
git clone --depth 1 https://github.com/mesias/tickerforge-spec.git /tmp/tickerforge-spec
cp -r /tmp/tickerforge-spec/spec .
pytest
```
