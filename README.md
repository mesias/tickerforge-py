# tickerforge

[![codecov](https://codecov.io/gh/mesias/tickerforge-py/branch/main/graph/badge.svg)](https://codecov.io/gh/mesias/tickerforge-py)

[![Repo Stats](https://github-readme-stats.vercel.app/api/pin/?username=mesias&repo=tickerforge-py&theme=dark)](https://github.com/mesias/tickerforge-py)

Python library that loads [`tickerforge-spec`](https://github.com/mesias/tickerforge-spec) and
generates/parses derivatives tickers.

## Install

```bash
pip install "git+https://github.com/mesias/tickerforge-py.git"
```

`tickerforge` depends on `tickerforge-spec-data` directly from GitHub:
`https://github.com/mesias/tickerforge-spec` (Python package at `packaging/python`).

## Usage

```python
from tickerforge import TickerForge, TickerParser

forge = TickerForge(spec_path="spec")
ticker = forge.generate("IND", date="2025-04-01")
print(ticker)  # e.g. INDM25

parser = TickerParser(spec_path="spec")
parsed = parser.parse(ticker, reference_date="2025-04-01")
print(parsed.symbol, parsed.year, parsed.month)
```

You can also rely on the packaged spec data and omit `spec_path`:

```python
from tickerforge import TickerForge

forge = TickerForge()
print(forge.generate("IND", date="2025-04-01"))
```

## What this first version supports

- Loading exchanges, contract cycles, expiration rules, and futures contracts from YAML
- Validating loaded structures with Pydantic models
- Resolving contract months by cycle
- Resolving expiration dates with exchange calendars
- Generating futures tickers from `{symbol}{month_code}{yy}`-style templates
- Parsing tickers back to structured contract information

## Run tests

Tests load YAML from a `spec/` directory at the project root (same layout as the [`tickerforge-spec`](https://github.com/mesias/tickerforge-spec) repo). Clone it once:

```bash
git clone --depth 1 https://github.com/mesias/tickerforge-spec.git /tmp/tickerforge-spec
cp -r /tmp/tickerforge-spec/spec .
pytest
```
