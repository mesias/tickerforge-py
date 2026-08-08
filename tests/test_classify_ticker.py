from pathlib import Path
from unittest.mock import patch

import pytest

from tickerforge import (
    AmbiguousClassifyError,
    TickerClass,
    classify_ticker,
    clear_load_spec_cache,
    load_spec,
    parse_ticker,
)
from tickerforge import ticker_parser as tp
from tickerforge.ticker_parser import (
    _classify_options,
    _match_options,
    _NonequityOptionPattern,
    _PatternIndex,
    _pick_unique_class,
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


def test_classify_nonequity_option(spec):
    classified = classify_ticker("DOLK26C5000", spec)
    assert classified.asset_type == "option"
    assert classified.root == "DOL"
    assert classified.option_type == "call"
    assert classified.year == 2026
    assert classified.month == 5
    assert classified.strike == "5000"


def test_classify_nonequity_put_option(spec):
    classified = classify_ticker("DOLK26P5000", spec)
    assert classified.asset_type == "option"
    assert classified.option_type == "put"


def test_classify_cash_equity(spec):
    classified = classify_ticker("PETR4", spec)
    assert classified.asset_type == "equity"
    assert classified.root == "PETR4"
    assert classified.exchange == "B3"


def test_classify_with_default_spec_loads():
    clear_load_spec_cache()
    classified = classify_ticker("INDM26")
    assert classified.asset_type == "future"
    assert classified.root == "IND"


def test_classify_filters_by_exchange(spec):
    classified = classify_ticker("INDM26", spec, exchange="B3")
    assert classified.exchange == "B3"
    with pytest.raises(ValueError, match="Unable to classify"):
        classify_ticker("INDM26", spec, exchange="CME")


def test_classify_unknown_tag_raises(spec):
    with pytest.raises(ValueError, match="Unable to classify"):
        classify_ticker("NOSUCH[0]", spec)


def test_classify_tag_wrong_exchange_raises(spec):
    with pytest.raises(ValueError, match="Unable to classify"):
        classify_ticker("DOL[1]", spec, exchange="CME")


def test_classify_matches_parse_asset_type(spec):
    for ticker in ("INDM26", "PETRA30", "IND", "DOL[0]", "DOLK26C5000", "PETR4"):
        assert (
            classify_ticker(ticker, spec).asset_type
            == parse_ticker(ticker, spec).asset_type
        )


def test_classify_unknown_raises(spec):
    with pytest.raises(ValueError, match="Unable to classify"):
        classify_ticker("NOTAREALTICKER999", spec)


def test_pick_unique_class_ambiguous():
    matches = [
        TickerClass(asset_type="future", root="A", exchange="B3"),
        TickerClass(asset_type="option", root="B", exchange="B3"),
    ]
    with pytest.raises(AmbiguousClassifyError, match="Ambiguous ticker") as exc_info:
        _pick_unique_class("FOO", matches)
    err = exc_info.value
    assert err.ticker == "FOO"
    assert err.matches == matches


def test_pick_unique_class_empty_raises():
    with pytest.raises(ValueError, match="Unable to classify"):
        _pick_unique_class("FOO", [])


def test_match_options_skips_unmapped_equity_month_code(monkeypatch, spec):
    monkeypatch.setattr(tp, "_equity_code_to_month_and_type", lambda *a, **k: None)
    assert _match_options("PETRA30", spec) == []


def test_classify_options_skips_unmapped_equity_month_code(monkeypatch, spec):
    monkeypatch.setattr(tp, "_equity_code_to_month_and_type", lambda *a, **k: None)
    assert _classify_options("PETRA30", spec) == []


def test_classify_options_skips_non_call_put_type(monkeypatch, spec):
    monkeypatch.setattr(
        tp, "_equity_code_to_month_and_type", lambda *a, **k: (1, "other")
    )
    assert _classify_options("PETRA30", spec) == []


def test_option_helpers_skip_nonequity_without_type_codes(spec):
    index = tp._pattern_index(spec)
    ne = index.nonequity_options[0]
    broken = ne.option.model_copy(update={"option_type_codes": None})
    fake = _PatternIndex(
        futures=index.futures,
        equity_options=[],
        nonequity_options=[_NonequityOptionPattern(pattern=ne.pattern, option=broken)],
    )
    ticker = f"{broken.symbol or ne.option.symbol}K26C5000"
    with patch.object(tp, "_pattern_index", return_value=fake):
        assert _match_options(ticker, spec) == []
        assert _classify_options(ticker, spec) == []


def test_load_spec_missing_path_raises():
    clear_load_spec_cache()
    missing = Path(__file__).resolve().parent / "does-not-exist-spec-root"
    with pytest.raises(FileNotFoundError, match="Spec path does not exist"):
        load_spec(missing)
    clear_load_spec_cache()


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
