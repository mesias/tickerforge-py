from pathlib import Path

from tickerforge import TickerForge


def test_generate_ind_front_contract_before_expiry():
    spec_path = Path(__file__).resolve().parents[1] / "spec"
    forge = TickerForge(spec_path=str(spec_path))

    ticker = forge.generate("IND", date="2026-06-01")
    assert ticker == "INDM26"


def test_generate_ind_rolls_after_expiry():
    spec_path = Path(__file__).resolve().parents[1] / "spec"
    forge = TickerForge(spec_path=str(spec_path))

    ticker = forge.generate("IND", date="2026-06-18")
    assert ticker == "INDQ26"
