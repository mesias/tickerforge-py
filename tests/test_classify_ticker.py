from pathlib import Path

import pytest

from tickerforge import (
    classify_ticker,
    clear_load_spec_cache,
    load_spec,
    parse_ticker,
)


@pytest.fixture
def spec():
    spec_path = Path(__file__).resolve().parents[1] / "spec"
    return load_spec(spec_path)


def test_classify_futures_full_ticker(spec):
    classified = classify_ticker("INDM26", spec)
    assert classified.asset_type == "future"
    assert classified.root == "IND"
    assert classified.year == 2026
    assert classified.month == 6
    assert classified.exchange == "B3"


def test_classify_futures_root(spec):
    classified = classify_ticker("IND", spec)
    assert classified.asset_type == "future"
    assert classified.root == "IND"
    assert classified.year is None
    assert classified.month is None


def test_classify_offset_tag(spec):
    classified = classify_ticker("DOL[1]", spec)
    assert classified.asset_type == "future"
    assert classified.root == "DOL"


def test_classify_equity_option(spec):
    classified = classify_ticker("PETRA30", spec)
    assert classified.asset_type == "option"
    assert classified.root == "PETR4"
    assert classified.option_type == "call"
    assert classified.month == 1
    assert classified.strike == "30"


def test_classify_matches_parse_asset_type(spec):
    for ticker in ("INDM26", "PETRA30", "IND", "DOL[0]"):
        assert (
            classify_ticker(ticker, spec).asset_type
            == parse_ticker(ticker, spec).asset_type
        )


def test_classify_unknown_raises(spec):
    with pytest.raises(ValueError, match="Unable to classify"):
        classify_ticker("NOTAREALTICKER999", spec)


def test_load_spec_is_cached():
    clear_load_spec_cache()
    first = load_spec()
    second = load_spec()
    assert first is second
    clear_load_spec_cache()
    third = load_spec()
    assert third is not first


def test_pattern_index_reused(spec):
    classify_ticker("INDM26", spec)
    first_index = spec._pattern_index
    classify_ticker("DOLN26", spec)
    assert spec._pattern_index is first_index
