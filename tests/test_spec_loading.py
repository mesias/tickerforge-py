from pathlib import Path

from tickerforge import load_spec


def test_load_spec_reads_b3_exchange_and_contracts():
    spec_path = Path(__file__).resolve().parents[1] / "spec"
    spec = load_spec(spec_path)

    exchange = spec.get_exchange("B3")
    contract = spec.get_contract("IND")

    assert exchange.code == "B3"
    assert "IND" in exchange.assets
    assert contract.symbol == "IND"
    assert contract.ticker_format == "{symbol}{month_code}{yy}"
