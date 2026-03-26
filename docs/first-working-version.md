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
  - Loads YAML from `exchanges/`, `contracts/`, `schemas/contract_cycles.yaml`, and `schedules/*.yaml`
  - Validates data using Pydantic models
  - Exposes a `SpecRepository` with `get_exchange()`, `get_contract()`, and `schedules`
  - Registers loaded schedules with the calendar system via `register_schedules()`
- `tickerforge/models.py`
  - Core models: `Exchange`, `Asset`, `ContractSpec`, `ExpirationRule`, `ContractCycle`
- `tickerforge/schedule.py`
  - Rule-based schedule engine: loads holiday rules from `spec/schedules/<exchange>.yaml`
  - `ExchangeSchedule` evaluates fixed-date, Easter-offset, nth-weekday, last-weekday, and override rules for any year
  - Easter computation via `dateutil.easter`
  - `SpecCalendar` wraps the schedule to match the `exchange_calendars` interface (`sessions_in_range`, `first_session`, `last_session`)
- `tickerforge/calendars.py`
  - `get_calendar()` returns a `SpecCalendar` when a spec schedule exists for the exchange
  - Falls back to `exchange_calendars` when no spec schedule is available
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
- `schedule` expiration rules (per-contract maturity calendars) are explicitly marked as not implemented yet.
- Trading calendars are now spec-driven via rule-based YAML definitions in `spec/schedules/`. See `tickerforge-spec/docs/rule-based-exchange-schedule.md` for the full design.
- The design keeps parsing/generation logic separate from calendar and loading concerns for easier evolution.
