# Integrate Early Closes (Half-Day Sessions) into tickerforge-py

## Current state

- `spec/schedules/b3.yaml` defines `early_closes.easter_offset` (Ash Wednesday at `open: "13:00"`), and the schema (`spec/schemas/schedule_schema.yaml`) also allows `early_closes.fixed` rules.
- `schedule.py` reads `self._early_closes` and evaluates both `fixed` and `easter_offset` early-close rules.
- The golden CSV confirms Ash Wednesday dates are **trading sessions** (they have ticker names), so `is_session` is already correct -- they are not marked as holidays.

## Changes

### 1. `ExchangeSchedule` -- `early_closes_for_year()` method

In `tickerforge/schedule.py`, a new method evaluates early-close rules (same pattern as `holidays_for_year`) and returns `dict[date, str]` mapping date to the modified open time:

- Processes `early_closes.fixed` rules (month/day, with `from_year`/`to_year` filtering)
- Processes `early_closes.easter_offset` rules (offset from Easter Sunday, with `from_year`/`to_year` filtering)
- Caches results per year in `self._early_close_cache`
- Skips weekend dates (same as holidays)

### 2. `ExchangeSchedule` -- `is_early_close()` and `early_close_time()` convenience methods

```python
def is_early_close(self, d: date) -> bool:
    return d in self.early_closes_for_year(d.year)

def early_close_time(self, d: date) -> str | None:
    return self.early_closes_for_year(d.year).get(d)
```

### 3. `SpecCalendar` -- early-close queries

Pass-through methods on `SpecCalendar` so that consumers using the calendar interface can query early-close info:

- `is_early_close(d)` -> bool
- `early_close_time(d)` -> str | None

### 4. Tests -- `test_b3_calendar_golden.py`

Validates that:

- Ash Wednesday (Easter - 46) for years 2023--2026 is correctly identified as an early close with `open: "13:00"`
- Ash Wednesday is still a valid trading session (`is_session` returns True)
- Non-early-close trading days return `False` / `None`
- Known B3 holidays return `False` (they are not early closes, they are holidays)
- `SpecCalendar` pass-through mirrors the underlying `ExchangeSchedule` methods
