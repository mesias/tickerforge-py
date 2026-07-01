# Offset tag syntax `SYMBOL[n]` (tickerforge-py)

`SYMBOL[n]` is a bracket tag that resolves a futures **root symbol** to a specific
contract in the tradeable-contract list, without spelling out the month/year.
It works for every futures contract in the spec — no per-contract YAML, no schema
changes. Options are unaffected.

## Semantics

`n` is an **index into the tradeable-contract list**, not calendar-month arithmetic:

| Tag          | Meaning                                                                |
|--------------|------------------------------------------------------------------------|
| `DOL[0]`     | Front month (still tradeable). Identical to plain `DOL`.               |
| `DOL[1]`     | Next tradeable contract after the front.                               |
| `DOL[2]`     | The one after that.                                                    |
| `IND[-1]`    | The most-recently-**expired** contract (the previous ticker that rolled off). |
| `IND[-2]`    | The expired contract before that.                                      |

This works uniformly across monthly (DOL) and bimonthly (WIN/IND) cycles because
the index is computed from the same still-tradeable / expired lists the generator
already builds. `DOL`/`WDO` roll off on expiry day (`as_of < expiration`); other
contracts stay tradeable through expiry day (`as_of <= expiration`) — the expired
list respects that per-contract rule automatically.

Futures only. `DOLK26C5000[1]` is **not** supported — options already encode the
full month, and the tag regex requires the whole string to be `ROOT[int]`.

## Parsing

`parse_ticker` recognises `SYMBOL[n]` after attempting a full-ticker match and
before the plain-root fallback. On a tag it looks up `root.upper()` in
`spec.contracts`, calls `generate_ticker_for_contract(contract, ref_date, spec,
offset=n)`, and re-parses the resulting full ticker. `ParsedTicker.offset` records
the tag int.

```python
from tickerforge import parse_ticker

# Forward: next DOL contract after the front on 2026-06-29 (front is DOLN26).
parse_ticker("DOL[1]", reference_date="2026-06-29").ticker   # -> 'DOLQ26'

# Negative: most-recently-expired IND on 2026-06-18 (front is INDQ26).
parse_ticker("IND[-1]", reference_date="2026-06-18").ticker  # -> 'INDM26'

# DOL[0] and plain DOL produce identical results.
parse_ticker("DOL[0]", reference_date="2026-06-29") == parse_ticker("DOL", reference_date="2026-06-29")

# Full tickers parse exactly as before; the tag regex does not match them.
parse_ticker("DOLN26").offset       # None  (full ticker)
parse_ticker("DOLK26C5000").offset  # None  (option)
parse_ticker("DOL[1]", reference_date="2026-06-29").offset   # 1
parse_ticker("DOL", reference_date="2026-06-29").offset      # 0  (plain root routed through offset 0)
```

`reference_date` defaults to today. `ParsedTicker.reference_date` and
`is_trading_session` are populated for tag resolution just as for plain roots.

### Errors

* **Out of range** — `parse_ticker("DOL[999]", ...)` and `parse_ticker("DOL[-999]", ...)`
  raise `ValueError` ("Offset ... is out of range for DOL").
* **Unknown root** — `parse_ticker("ZZZ[1]")` raises `ValueError`
  ("Unable to parse ticker: ZZZ[1]").
* **Exchange mismatch** — if `exchange=` is passed and the resolved contract is on
  a different exchange, `ValueError` ("Unable to parse ticker: ...").

### Builder

```python
from tickerforge import TickerParser

TickerParser.builder().ticker("DOL[1]").reference_date("2026-06-29").parse().ticker
# -> 'DOLQ26'
```

## Generation

`TickerForge.generate` / `generate_ticker_for_contract` accept a signed `offset`
(the signature stays `offset: int = 0`, so non-negative callers are unaffected):

```python
from tickerforge import TickerForge

forge = TickerForge()

forge.generate("DOL", date="2026-06-29", offset=1)    # -> 'DOLQ26'   (forward)
forge.generate("DOL", date="2026-06-29", offset=-1)   # -> 'DOLM26'   (previous expired)
forge.generate("IND", date="2026-06-18", offset=-1)   # -> 'INDM26'
```

For `offset >= 0` the generator keeps its existing forward behavior (still-tradeable
contracts from `as_of.year` onward). For `offset < 0` it scans backward over
`as_of.year - 4 .. as_of.year` (inclusive), collects pairs that are no longer
tradeable, sorts them most-recently-expired first, and selects index `(-offset) - 1`.
