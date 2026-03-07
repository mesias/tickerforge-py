from pathlib import Path

import pytest

from tickerforge import TickerForge, TickerParser


def test_parse_ind_ticker():
    spec_path = Path(__file__).resolve().parents[1] / "spec"
    parser = TickerParser(spec_path=str(spec_path))

    parsed = parser.parse("INDM26", reference_date="2026-01-01")
    assert parsed.symbol == "IND"
    assert parsed.month == 6
    assert parsed.year == 2026
    assert parsed.contract.exchange == "B3"


def test_generate_and_parse_round_trip():
    spec_path = Path(__file__).resolve().parents[1] / "spec"
    forge = TickerForge(spec_path=str(spec_path))
    parser = TickerParser(spec_path=str(spec_path))

    generated = forge.generate("IND", date="2026-06-01")
    parsed = parser.parse(generated, reference_date="2026-06-01")

    assert generated == "INDM26"
    assert parsed.symbol == "IND"
    assert parsed.year == 2026
    assert parsed.month == 6


def test_parse_invalid_ticker_raises_error():
    spec_path = Path(__file__).resolve().parents[1] / "spec"
    parser = TickerParser(spec_path=str(spec_path))

    with pytest.raises(ValueError):
        parser.parse("INVALID")
