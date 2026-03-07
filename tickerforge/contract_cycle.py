from __future__ import annotations

from tickerforge.models import ContractCycle
from tickerforge.month_codes import code_to_month


BUILTIN_CYCLES: dict[str, list[str]] = {
    "monthly": ["F", "G", "H", "J", "K", "M", "N", "Q", "U", "V", "X", "Z"],
    "bimonthly_even": ["G", "J", "M", "Q", "V", "Z"],
    "quarterly": ["H", "M", "U", "Z"],
}


def resolve_contract_months(contract_cycle: ContractCycle | str, year: int) -> list[int]:
    del year  # The cycle defines valid months; year is kept for a stable API.

    if isinstance(contract_cycle, ContractCycle):
        month_codes = contract_cycle.months
    elif isinstance(contract_cycle, str):
        try:
            month_codes = BUILTIN_CYCLES[contract_cycle]
        except KeyError as exc:
            raise ValueError(f"Unknown contract cycle: {contract_cycle}") from exc
    else:
        raise TypeError("contract_cycle must be ContractCycle or str")

    return sorted(code_to_month(code) for code in month_codes)
