# tickerforge First Working Version

## Goal

Create a minimal, extensible Python library that reads `tickerforge-spec` and supports:

- spec loading
- contract-cycle resolution
- expiration-rule resolution
- ticker generation
- ticker parsing

## Implemented Architecture

- `tickerforge/spec_loader.py`
  - Loads YAML from `exchanges/`, `contracts/`, and `schemas/contract_cycles.yaml`
  - Validates data using Pydantic models
  - Exposes a `SpecRepository` with `get_exchange()` and `get_contract()`
- `tickerforge/models.py`
  - Core models: `Exchange`, `Asset`, `ContractSpec`, `ExpirationRule`, `ContractCycle`
- `tickerforge/calendars.py`
  - Isolated exchange calendar resolution (`get_calendar`)
- `tickerforge/contract_cycle.py`
  - Cycle-to-month resolver (`resolve_contract_months`)
- `tickerforge/expiration_rules.py`
  - Rule engine for:
    - `first_business_day`
    - `last_business_day`
    - `nth_business_day`
    - `fixed_day`
    - `nearest_weekday_to_day`
    - `nth_weekday_of_month`
- `tickerforge/ticker_generator.py`
  - `TickerForge.generate(symbol, date, offset=0)` for futures ticker creation
- `tickerforge/ticker_parser.py`
  - `TickerParser.parse(ticker)` and low-level `parse_ticker(...)`
- `tickerforge/month_codes.py`
  - Standard futures month code mappings and conversion helpers

## Notes

- This first version intentionally focuses on futures contracts from `contracts/*/futures.yaml`.
- `schedule` expiration rules are explicitly marked as not implemented yet.
- The design keeps parsing/generation logic separate from calendar and loading concerns for easier evolution.
