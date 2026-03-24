from pathlib import Path

from tickerforge.contract_cycle import resolve_contract_months
from tickerforge.month_codes import code_to_month, month_to_code
from tickerforge.spec_loader import load_spec


def test_month_code_round_trip():
    assert month_to_code(1) == "F"
    assert month_to_code(12) == "Z"
    assert code_to_month("F") == 1
    assert code_to_month("z") == 12


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
