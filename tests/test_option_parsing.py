from __future__ import annotations

import pytest

from tickerforge import (
    TickerParser,
    load_spec,
    parse_ticker,
)

# ===========================================================================
# Spec loading: options are present
# ===========================================================================


def test_spec_loads_options():
    spec = load_spec()
    assert len(spec.options) > 0, "Expected at least one option spec loaded"


def test_spec_options_include_equity_type():
    spec = load_spec()
    equity = [o for o in spec.options if o.type == "equity"]
    assert len(equity) >= 1


def test_spec_options_include_index_type():
    spec = load_spec()
    index = [o for o in spec.options if o.type == "index"]
    assert len(index) >= 1


# ===========================================================================
# B3 Equity Options
# ===========================================================================


def test_parse_equity_call_option():
    # Real B3 format: equity_root("PETR4") = "PETR" → ticker "PETRA30"
    parsed = parse_ticker("PETRA30")
    assert parsed.asset_type == "option"
    assert parsed.option_type == "call"
    assert parsed.underlying == "PETR4"
    assert parsed.symbol == "PETR4"
    assert parsed.month == 1
    assert parsed.strike == "30"
    assert parsed.year is None
    assert parsed.exchange == "B3"


def test_parse_equity_put_option():
    # equity_root("PETR4") = "PETR", put code M = January → "PETRM30"
    parsed = parse_ticker("PETRM30")
    assert parsed.asset_type == "option"
    assert parsed.option_type == "put"
    assert parsed.underlying == "PETR4"
    assert parsed.symbol == "PETR4"
    assert parsed.month == 1
    assert parsed.strike == "30"
    assert parsed.exchange == "B3"


def test_parse_equity_call_june():
    # equity_root("VALE3") = "VALE", call code F = June → "VALEF50"
    parsed = parse_ticker("VALEF50")
    assert parsed.asset_type == "option"
    assert parsed.option_type == "call"
    assert parsed.underlying == "VALE3"
    assert parsed.month == 6
    assert parsed.strike == "50"


def test_parse_equity_put_december():
    # equity_root("ITUB4") = "ITUB", put code X = December → "ITUBX25"
    parsed = parse_ticker("ITUBX25")
    assert parsed.asset_type == "option"
    assert parsed.option_type == "put"
    assert parsed.underlying == "ITUB4"
    assert parsed.month == 12
    assert parsed.strike == "25"


def test_parse_equity_option_has_option_spec():
    parsed = parse_ticker("PETRA30")
    assert parsed.option is not None
    assert parsed.option.type == "equity"
    assert parsed.option.option_style == "american"
    assert parsed.contract is None


def test_parse_equity_option_tick_and_lot():
    parsed = parse_ticker("PETRA30")
    assert parsed.tick_size == 0.01
    assert parsed.lot_size == 1.00


# ===========================================================================
# B3 Index Options (IBOV)
# ===========================================================================


def test_parse_ibov_call_option():
    parsed = parse_ticker("IBOVK26C120000")
    assert parsed.asset_type == "option"
    assert parsed.option_type == "call"
    assert parsed.symbol == "IBOV"
    assert parsed.month == 5
    assert parsed.year == 2026
    assert parsed.strike == "120000"
    assert parsed.exchange == "B3"


def test_parse_ibov_put_option():
    parsed = parse_ticker("IBOVK26P100000")
    assert parsed.asset_type == "option"
    assert parsed.option_type == "put"
    assert parsed.symbol == "IBOV"
    assert parsed.month == 5
    assert parsed.year == 2026
    assert parsed.strike == "100000"


def test_parse_ibov_option_has_option_spec():
    parsed = parse_ticker("IBOVK26C120000")
    assert parsed.option is not None
    assert parsed.option.type == "index"
    assert parsed.option.option_style == "european"


# ===========================================================================
# B3 Dollar Options
# ===========================================================================


def test_parse_dol_call_option():
    parsed = parse_ticker("DOLK26C5000")
    assert parsed.asset_type == "option"
    assert parsed.option_type == "call"
    assert parsed.symbol == "DOL"
    assert parsed.month == 5
    assert parsed.year == 2026
    assert parsed.strike == "5000"
    assert parsed.exchange == "B3"


def test_parse_dol_put_option():
    parsed = parse_ticker("DOLK26P4800")
    assert parsed.asset_type == "option"
    assert parsed.option_type == "put"
    assert parsed.symbol == "DOL"
    assert parsed.strike == "4800"


# ===========================================================================
# B3 Interest Rate Options (IDI)
# ===========================================================================


def test_parse_idi_call_option():
    parsed = parse_ticker("IDIF26C100000")
    assert parsed.asset_type == "option"
    assert parsed.option_type == "call"
    assert parsed.symbol == "IDI"
    assert parsed.month == 1
    assert parsed.year == 2026
    assert parsed.strike == "100000"
    assert parsed.exchange == "B3"


def test_parse_idi_put_option():
    parsed = parse_ticker("IDIF26P95000")
    assert parsed.asset_type == "option"
    assert parsed.option_type == "put"
    assert parsed.symbol == "IDI"
    assert parsed.strike == "95000"


# ===========================================================================
# Futures still work (backward compatibility)
# ===========================================================================


def test_futures_still_parse():
    parsed = parse_ticker("INDM26")
    assert parsed.asset_type == "future"
    assert parsed.symbol == "IND"
    assert parsed.year == 2026
    assert parsed.month == 6
    assert parsed.contract is not None
    assert parsed.option is None
    assert parsed.exchange == "B3"


def test_cme_futures_parse():
    parsed = parse_ticker("ESM26")
    assert parsed.asset_type == "future"
    assert parsed.symbol == "ES"
    assert parsed.year == 2026
    assert parsed.month == 6
    assert parsed.exchange == "CME"


def test_futures_have_no_option_fields():
    parsed = parse_ticker("WINM26")
    assert parsed.option_type is None
    assert parsed.strike is None
    assert parsed.underlying is None


# ===========================================================================
# DOL disambiguation: future vs option
# ===========================================================================


def test_dol_future_not_ambiguous_with_option():
    """DOLK26 should match only the future (option format has extra suffix)."""
    parsed = parse_ticker("DOLK26")
    assert parsed.asset_type == "future"
    assert parsed.symbol == "DOL"


def test_dol_option_not_ambiguous_with_future():
    """DOLK26C5000 should match only the option."""
    parsed = parse_ticker("DOLK26C5000")
    assert parsed.asset_type == "option"
    assert parsed.symbol == "DOL"


# ===========================================================================
# Exchange filter for disambiguation
# ===========================================================================


def test_exchange_filter_on_future():
    parsed = parse_ticker("ESM26", exchange="CME")
    assert parsed.exchange == "CME"
    assert parsed.symbol == "ES"


def test_exchange_filter_excludes_wrong_market():
    with pytest.raises(ValueError, match="Unable to parse ticker"):
        parse_ticker("ESM26", exchange="B3")


def test_exchange_filter_on_option():
    parsed = parse_ticker("PETRA30", exchange="B3")
    assert parsed.exchange == "B3"
    assert parsed.asset_type == "option"


def test_exchange_filter_with_builder():
    parsed = TickerParser.builder().ticker("ESM26").exchange("CME").parse()
    assert parsed.symbol == "ES"
    assert parsed.exchange == "CME"


def test_parser_instance_with_exchange():
    parser = TickerParser()
    parsed = parser.parse("DOLK26C5000", exchange="B3")
    assert parsed.asset_type == "option"
    assert parsed.exchange == "B3"


# ===========================================================================
# Unknown tickers
# ===========================================================================


def test_unknown_ticker_still_raises():
    with pytest.raises(ValueError, match="Unable to parse ticker"):
        parse_ticker("ZZZZ")


def test_unknown_option_format_raises():
    with pytest.raises(ValueError, match="Unable to parse ticker"):
        parse_ticker("FAKEA99")


# ===========================================================================
# All equity underlyings can be parsed
# ===========================================================================


def test_all_equity_underlyings_parseable():
    spec = load_spec()
    equity_options = [o for o in spec.options if o.type == "equity"]
    assert len(equity_options) > 0
    for opt in equity_options:
        if not opt.underlyings:
            continue
        for underlying in opt.underlyings:
            # Use equity_root format: strip one trailing digit (PETR4 → PETRA100)
            root = (
                underlying[:-1]
                if underlying and underlying[-1].isdigit()
                else underlying
            )
            ticker = f"{root}A100"
            parsed = parse_ticker(ticker)
            assert parsed.asset_type == "option"
            assert parsed.underlying == underlying
            assert parsed.option_type == "call"
            assert parsed.month == 1
