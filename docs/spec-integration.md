# Spec Integration

## Scope

This document covers Python-specific behavior for consuming the canonical data from `tickerforge-spec`.

For the language-neutral contract, see the spec repo docs on rule-based schedules and session segments. This file only explains how the Python package maps those rules into its own runtime models.

## Rule-Based Schedules

The Python implementation loads schedule definitions from `spec/schedules/*.yaml` during spec loading.

Current integration points:

- `tickerforge/schedule.py`: evaluates schedule rules and exposes session queries
- `tickerforge/calendars.py`: registers loaded schedules with the calendar layer
- `tickerforge/spec_loader.py`: loads schedules alongside exchanges and contracts

The key boundary is that expiration logic works against calendar sessions rather than against raw YAML schedule data.

## Session Segments

The canonical YAML stores `sessions` as a mapping keyed by segment name. Python converts that mapping into an ordered `list[SessionSegment]`.

Current behavior:

- `tickerforge/models.py` defines `SessionSegment`
- model validation converts the YAML mapping into ordered segment objects
- the segment name comes from the YAML key
- validation requires the first segment to be `regular`
- merged `ContractSpec` values inherit session data from the owning asset when needed

This keeps the authored YAML compact while the Python API exposes an ordered session list.

## Why This Lives Here

These details are specific to the Python package's loaders, validators, and model layer. They do not belong in `tickerforge-spec`, because the spec repo should define the canonical format without prescribing Python internals.
