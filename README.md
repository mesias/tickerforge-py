# tickerforge

Python library that loads [`tickerforge-spec`](https://github.com/mesias/tickerforge-spec) and
generates/parses derivatives tickers.

## Install

```bash
pip install -e .[dev]
```

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

## What this first version supports

- Loading exchanges, contract cycles, expiration rules, and futures contracts from YAML
- Validating loaded structures with Pydantic models
- Resolving contract months by cycle
- Resolving expiration dates with exchange calendars
- Generating futures tickers from `{symbol}{month_code}{yy}`-style templates
- Parsing tickers back to structured contract information

## Run tests

```bash
pytest
```
