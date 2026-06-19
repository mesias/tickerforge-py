from pathlib import Path

import pytest

from tickerforge.contract_cycle import resolve_contract_months
from tickerforge.month_codes import code_to_month, month_to_code
from tickerforge.spec_loader import load_spec


def test_month_code_round_trip():
    assert month_to_code(1) == "F"
    assert month_to_code(12) == "Z"
    assert code_to_month("F") == 1
    assert code_to_month("z") == 12


def test_month_code_errors():
    with pytest.raises(ValueError, match="Invalid month: 13"):
        month_to_code(13)
    with pytest.raises(ValueError, match="Invalid month code: A"):
        code_to_month("A")


def test_resolve_contract_months_for_common_cycles():
    spec_path = Path(__file__).resolve().parents[1] / "spec"
    spec = load_spec(spec_path)

    monthly = spec.contract_cycles["monthly"]
    quarterly = spec.contract_cycles["quarterly"]
    bimonthly_even = spec.contract_cycles["bimonthly_even"]

    assert resolve_contract_months(monthly, 2026) == [
        1,
        2,
        3,
        4,
        5,
        6,
        7,
        8,
        9,
        10,
        11,
        12,
    ]
    assert resolve_contract_months(quarterly, 2026) == [3, 6, 9, 12]
    assert resolve_contract_months(bimonthly_even, 2026) == [2, 4, 6, 8, 10, 12]


def test_resolve_contract_months_string_and_errors():
    # Test valid string cycles
    assert resolve_contract_months("monthly", 2026) == list(range(1, 13))
    assert resolve_contract_months("quarterly", 2026) == [3, 6, 9, 12]

    # Test invalid string cycle
    with pytest.raises(ValueError, match="Unknown contract cycle"):
        resolve_contract_months("invalid_cycle", 2026)

    # Test invalid type
    with pytest.raises(TypeError, match="contract_cycle must be ContractCycle or str"):
        resolve_contract_months(123, 2026)
