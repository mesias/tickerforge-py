from datetime import date
from pathlib import Path
from unittest.mock import patch

import pytest

from tickerforge import TickerForge, TickerParser, load_spec, parse_ticker


def test_parse_ind_ticker():
    spec_path = Path(__file__).resolve().parents[1] / "spec"
    parser = TickerParser(spec_path=spec_path)

    parsed = parser.parse("INDM26", reference_date="2026-01-01")
    assert parsed.symbol == "IND"
    assert parsed.month == 6
    assert parsed.year == 2026
    assert parsed.contract.exchange == "B3"


def test_generate_and_parse_round_trip():
    spec_path = Path(__file__).resolve().parents[1] / "spec"
    forge = TickerForge(spec_path=str(spec_path))
    parser = TickerParser(spec_path=spec_path)

    generated = forge.generate("IND", date="2026-06-01")
    parsed = parser.parse(generated, reference_date="2026-06-01")

    assert generated == "INDM26"
    assert parsed.ticker == "INDM26"
    assert parsed.symbol == "IND"
    assert parsed.year == 2026
    assert parsed.month == 6


def test_parse_invalid_ticker_raises_error():
    spec_path = Path(__file__).resolve().parents[1] / "spec"
    parser = TickerParser(spec_path=spec_path)

    with pytest.raises(ValueError):
        parser.parse("INVALID")


def test_parse_ticker_with_explicit_spec_repository():
    spec = load_spec()
    parsed = parse_ticker("INDM26", spec, reference_date="2026-01-01")
    assert parsed.symbol == "IND"
    assert parsed.month == 6
    assert parsed.year == 2026
    assert parsed.contract.exchange == "B3"


def test_parse_ticker_includes_tick_size_and_lot_size():
    spec = load_spec()
    contract = spec.get_contract("IND")
    parsed = parse_ticker("INDM26", spec, reference_date="2026-01-01")
    assert parsed.tick_size == contract.tick_size
    assert parsed.ctr_std == contract.ctr_std
    assert parsed.ctr_size == contract.ctr_size


def test_parse_ticker_without_spec_matches_explicit_spec():
    spec = load_spec()
    expected = parse_ticker("INDM26", spec, reference_date="2026-01-01")
    got = parse_ticker("INDM26", None, reference_date="2026-01-01")
    assert got == expected


def test_parse_ticker_omitted_spec_kwarg_matches_explicit():
    spec = load_spec()
    expected = parse_ticker("INDM26", spec, reference_date="2026-01-01")
    got = parse_ticker("INDM26", reference_date="2026-01-01")
    assert got == expected


def test_parse_ticker_load_spec_called_when_spec_is_none():
    real_spec = load_spec()
    with patch(
        "tickerforge.ticker_parser.load_spec", return_value=real_spec
    ) as mock_load:
        parsed = parse_ticker("INDM26", reference_date="2026-01-01")
        mock_load.assert_called_once_with()
    assert parsed.symbol == "IND"
    assert parsed.month == 6
    assert parsed.year == 2026


def test_parse_ticker_explicit_spec_does_not_call_load_spec():
    real_spec = load_spec()
    with patch("tickerforge.ticker_parser.load_spec") as mock_load:
        parse_ticker("INDM26", real_spec, reference_date="2026-01-01")
        mock_load.assert_not_called()


# ---------------------------------------------------------------------------
# Smart parsing: full ticker (year/month derived from ticker, no date needed)
# ---------------------------------------------------------------------------


def test_parse_full_ticker_without_reference_date():
    parsed = parse_ticker("INDM26")
    assert parsed.symbol == "IND"
    assert parsed.year == 2026
    assert parsed.month == 6


def test_parse_full_ticker_ignores_wrong_reference_date():
    parsed = parse_ticker("INDM26", reference_date="1990-01-01")
    assert parsed.symbol == "IND"
    assert parsed.year == 2026
    assert parsed.month == 6


def test_parse_full_ticker_dol():
    parsed = parse_ticker("DOLK26")
    assert parsed.symbol == "DOL"
    assert parsed.year == 2026
    assert parsed.month == 5


def test_parse_full_ticker_win():
    parsed = parse_ticker("WINM26")
    assert parsed.symbol == "WIN"
    assert parsed.year == 2026
    assert parsed.month == 6


# ---------------------------------------------------------------------------
# Smart parsing: root symbol (resolves front-month via generator)
# ---------------------------------------------------------------------------


def test_parse_root_symbol_with_reference_date():
    spec = load_spec()
    parsed = parse_ticker("IND", spec, reference_date="2026-06-01")
    assert parsed.symbol == "IND"
    assert parsed.year == 2026
    assert parsed.month in (6, 8)


def test_parse_root_symbol_without_reference_date():
    parsed = parse_ticker("IND")
    assert parsed.symbol == "IND"
    assert isinstance(parsed.year, int)
    assert 1 <= parsed.month <= 12


def test_parse_root_symbol_dol():
    parsed = parse_ticker("DOL", reference_date="2026-04-15")
    assert parsed.symbol == "DOL"
    assert parsed.year == 2026
    assert 1 <= parsed.month <= 12


def test_parse_root_symbol_win():
    parsed = parse_ticker("WIN", reference_date="2026-04-15")
    assert parsed.symbol == "WIN"
    assert parsed.year == 2026
    assert 1 <= parsed.month <= 12


# ---------------------------------------------------------------------------
# Unknown symbol
# ---------------------------------------------------------------------------


def test_parse_unknown_symbol_raises():
    with pytest.raises(ValueError, match="Unable to parse ticker"):
        parse_ticker("ZZZZ")


# ===========================================================================
# Builder → build() → reusable TickerParser
# ===========================================================================


def test_builder_build_default_spec():
    parser = TickerParser.builder().build()
    parsed = parser.parse("INDM26")
    assert parsed.symbol == "IND"
    assert parsed.year == 2026
    assert parsed.month == 6


def test_builder_build_custom_spec():
    parser = TickerParser.builder().build()
    parsed = parser.parse("DOLK26")
    assert parsed.symbol == "DOL"
    assert parsed.year == 2026
    assert parsed.month == 5


# ===========================================================================
# Builder → parse() — one-shot
# ===========================================================================


def test_builder_parse_full_ticker():
    parsed = TickerParser.builder().ticker("INDM26").parse()
    assert parsed.symbol == "IND"
    assert parsed.year == 2026
    assert parsed.month == 6


def test_builder_parse_root_with_date():
    parsed = TickerParser.builder().ticker("IND").reference_date("2026-06-01").parse()
    assert parsed.symbol == "IND"
    assert parsed.year == 2026
    assert 1 <= parsed.month <= 12


def test_builder_parse_root_without_date():
    parsed = TickerParser.builder().ticker("DOL").parse()
    assert parsed.symbol == "DOL"
    assert 1 <= parsed.month <= 12


def test_builder_parse_custom_spec_with_date():
    parsed = TickerParser.builder().ticker("IND").reference_date("2026-06-01").parse()
    assert parsed.symbol == "IND"
    assert parsed.year == 2026


def test_builder_parse_unknown_errors():
    with pytest.raises(ValueError, match="Unable to parse ticker"):
        TickerParser.builder().ticker("ZZZZ").parse()


def test_builder_parse_full_ignores_date():
    parsed = (
        TickerParser.builder().ticker("INDM26").reference_date("1990-01-01").parse()
    )
    assert parsed.symbol == "IND"
    assert parsed.year == 2026
    assert parsed.month == 6


def test_builder_date_before_ticker():
    parsed = TickerParser.builder().reference_date("2026-06-01").ticker("IND").parse()
    assert parsed.symbol == "IND"
    assert parsed.year == 2026


# ===========================================================================
# Builder — spec() convenience alias
# ===========================================================================


def _default_spec_dir() -> str:
    from tickerforge_spec_data import get_spec_root

    return str(get_spec_root())


def test_builder_build_with_spec():
    parser = TickerParser.builder().spec(_default_spec_dir()).build()
    parsed = parser.parse("DOLK26")
    assert parsed.symbol == "DOL"
    assert parsed.year == 2026
    assert parsed.month == 5


def test_builder_parse_with_spec():
    parsed = TickerParser.builder().spec(_default_spec_dir()).ticker("WINM26").parse()
    assert parsed.symbol == "WIN"
    assert parsed.year == 2026
    assert parsed.month == 6


def test_builder_spec_before_ticker():
    parsed = (
        TickerParser.builder()
        .spec(_default_spec_dir())
        .ticker("IND")
        .reference_date("2026-06-01")
        .parse()
    )
    assert parsed.symbol == "IND"
    assert parsed.year == 2026


# ===========================================================================
# Builder — typestate: parse() not available without ticker
# ===========================================================================


def test_builder_no_ticker_has_no_parse():
    builder = TickerParser.builder()
    assert not hasattr(builder, "parse")


# ===========================================================================
# Warnings: full ticker + reference_date
# ===========================================================================


def test_parse_full_ticker_with_date_warns():
    with pytest.warns(UserWarning, match="reference_date is ignored"):
        parsed = parse_ticker("WINQ25", reference_date="2030-01-01")
    assert parsed.symbol == "WIN"
    assert parsed.year == 2025
    assert parsed.month == 8


def test_builder_parse_full_ticker_with_date_warns():
    with pytest.warns(UserWarning, match="reference_date is ignored"):
        parsed = (
            TickerParser.builder().ticker("WINQ25").reference_date("2030-01-01").parse()
        )
    assert parsed.symbol == "WIN"
    assert parsed.year == 2025
    assert parsed.month == 8


# ===========================================================================
# is_trading_session / reference_date
# ===========================================================================


def test_full_ticker_has_no_session_info():
    parsed = parse_ticker("INDM26")
    assert parsed.reference_date is None
    assert parsed.is_trading_session is None


def test_root_symbol_on_weekday_is_trading_session():
    parsed = parse_ticker("IND", reference_date="2026-04-15")
    assert parsed.reference_date == date(2026, 4, 15)
    assert parsed.is_trading_session is True


def test_root_symbol_on_weekend_is_not_trading_session():
    parsed = parse_ticker("IND", reference_date="2026-04-18")
    assert parsed.reference_date == date(2026, 4, 18)
    assert parsed.is_trading_session is False


def test_root_symbol_on_holiday_is_not_trading_session():
    # 2026-04-21 is Tiradentes (B3 holiday, a Tuesday)
    parsed = parse_ticker("IND", reference_date="2026-04-21")
    assert parsed.reference_date == date(2026, 4, 21)
    assert parsed.is_trading_session is False


def test_root_symbol_without_date_has_session_info():
    parsed = parse_ticker("IND")
    assert parsed.reference_date is not None
    assert parsed.is_trading_session is not None


def test_builder_root_symbol_session_info():
    parsed = TickerParser.builder().ticker("DOL").reference_date("2026-04-15").parse()
    assert parsed.reference_date == date(2026, 4, 15)
    assert parsed.is_trading_session is True


def test_builder_full_ticker_no_session_info():
    parsed = TickerParser.builder().ticker("DOLK26").parse()
    assert parsed.reference_date is None
    assert parsed.is_trading_session is None
    assert parsed.ticker == "DOLK26"


def test_parsed_ticker_from_root_symbol_formats_ticker():
    parsed = parse_ticker("DOL", reference_date="2026-06-29")
    assert parsed.ticker == "DOLN26"


def test_parsed_ticker_formats_equity_option():
    parsed = parse_ticker("PETRA30")
    assert parsed.ticker == "PETRA30"


def test_parsed_ticker_formats_dollar_option():
    parsed = parse_ticker("DOLK26C5000")
    assert parsed.ticker == "DOLK26C5000"


def test_parse_new_b3_futures():
    spec_path = Path(__file__).resolve().parents[1] / "spec"
    parser = TickerParser(spec_path=spec_path)

    # 1. ETR (Ethereum, last Friday of Jan 2026 -> 2026-01-30)
    parsed_etr = parser.parse("ETRF26")
    assert parsed_etr.symbol == "ETR"
    assert parsed_etr.year == 2026
    assert parsed_etr.month == 1
    assert parsed_etr.ctr_std == 1
    assert parsed_etr.ctr_size == 0.1

    # 2. SOL (Solana, last Friday of Jan 2026 -> 2026-01-30)
    parsed_sol = parser.parse("SOLF26")
    assert parsed_sol.symbol == "SOL"
    assert parsed_sol.ctr_std == 5
    assert parsed_sol.ctr_size == 5.0

    # 3. SJC (Soybean CBOT, 2nd business day prior to March 2026 -> 2026-02-26)
    parsed_sjc = parser.parse("SJCH26")
    assert parsed_sjc.symbol == "SJC"
    assert parsed_sjc.ctr_std == 1
    assert parsed_sjc.ctr_size == 450.0

    # 4. SOY (Soybean FOB Santos, business day prior to 16th of Feb 2026 -> 2026-02-13)
    parsed_soy = parser.parse("SOYH26")
    assert parsed_soy.symbol == "SOY"
    assert parsed_soy.ctr_std == 1
    assert parsed_soy.ctr_size == 34.0

    # 5. GLD (Gold, 3rd to last business day of Jan 2026 -> 2026-01-28)
    parsed_gld = parser.parse("GLDF26")
    assert parsed_gld.symbol == "GLD"
    assert parsed_gld.ctr_std == 1
    assert parsed_gld.ctr_size == 1.0

    # 6. BIT (Bitcoin, last Friday of Jan 2026 -> 2026-01-30)
    parsed_bit = parser.parse("BITF26")
    assert parsed_bit.symbol == "BIT"
    assert parsed_bit.ctr_std == 1
    assert parsed_bit.ctr_size == 0.01
    assert parsed_bit.tick_size == 20.0

    # 7. ISP (S&P 500, third Friday of March 2026 -> 2026-03-20)
    parsed_isp = parser.parse("ISPH26")
    assert parsed_isp.symbol == "ISP"
    assert parsed_isp.ctr_std == 1
    assert parsed_isp.ctr_size == 50.0
    assert parsed_isp.tick_size == 0.25

    # 8. WSP (Micro S&P 500, third Friday of March 2026 -> 2026-03-20)
    parsed_wsp = parser.parse("WSPH26")
    assert parsed_wsp.symbol == "WSP"
    assert parsed_wsp.ctr_std == 1
    assert parsed_wsp.ctr_size == 2.5
    assert parsed_wsp.tick_size == 0.25

    # 9. ETH (Hydrous Ethanol, last business day of Jan 2026 -> 2026-01-30)
    parsed_eth = parser.parse("ETHF26")
    assert parsed_eth.symbol == "ETH"
    assert parsed_eth.ctr_std == 1
    assert parsed_eth.ctr_size == 10.0
    assert parsed_eth.tick_size == 0.50

    # Let's also resolve expiration dates to verify they work
    from tickerforge.calendars import get_calendar
    from tickerforge.expiration_rules import resolve_expiration

    cal = get_calendar("B3")

    # ETR: last Friday of Jan 2026
    etr_rule = parser.spec.expiration_rules["last_friday"]
    assert resolve_expiration(parsed_etr.contract, 2026, 1, etr_rule, cal) == date(
        2026, 1, 30
    )

    # SJC: second business day prior to March 2026 (Feb 2026 has 20 business days; 2nd to last is Feb 26)
    sjc_rule = parser.spec.expiration_rules["second_business_day_prior_to_month"]
    assert resolve_expiration(parsed_sjc.contract, 2026, 3, sjc_rule, cal) == date(
        2026, 2, 26
    )

    # SOY: business day prior to 16th of Feb 2026
    soy_rule = parser.spec.expiration_rules[
        "business_day_prior_to_16th_of_preceding_month"
    ]
    assert resolve_expiration(parsed_soy.contract, 2026, 3, soy_rule, cal) == date(
        2026, 2, 13
    )

    # GLD: 3rd to last business day of Jan 2026
    gld_rule = parser.spec.expiration_rules["third_to_last_business_day"]
    assert resolve_expiration(parsed_gld.contract, 2026, 1, gld_rule, cal) == date(
        2026, 1, 28
    )

    # BIT: last Friday of Jan 2026
    assert resolve_expiration(parsed_bit.contract, 2026, 1, etr_rule, cal) == date(
        2026, 1, 30
    )

    # ISP: third Friday of March 2026
    isp_rule = parser.spec.expiration_rules["third_friday"]
    assert resolve_expiration(parsed_isp.contract, 2026, 3, isp_rule, cal) == date(
        2026, 3, 20
    )

    # WSP: third Friday of March 2026
    assert resolve_expiration(parsed_wsp.contract, 2026, 3, isp_rule, cal) == date(
        2026, 3, 20
    )

    # ETH: last business day of Jan 2026
    eth_rule = parser.spec.expiration_rules["last_business_day"]
    assert resolve_expiration(parsed_eth.contract, 2026, 1, eth_rule, cal) == date(
        2026, 1, 30
    )


def test_parse_cash_equities():
    spec_path = Path(__file__).resolve().parents[1] / "spec"
    parser = TickerParser(spec_path=spec_path)

    # 1. Parse PETR4 (known cash equity)
    parsed_petr4 = parser.parse("PETR4")
    assert parsed_petr4.symbol == "PETR4"
    assert parsed_petr4.asset_type == "equity"
    assert parsed_petr4.exchange == "B3"
    assert parsed_petr4.tick_size == 0.01
    assert parsed_petr4.ctr_std == 100
    assert parsed_petr4.ctr_size == 1.0
    assert parsed_petr4.equity is not None
    assert parsed_petr4.ticker == "PETR4"

    # 2. Parse PETR4 with reference date
    parsed_date = parser.parse("PETR4", reference_date="2026-04-15")
    assert parsed_date.reference_date == date(2026, 4, 15)
    assert parsed_date.is_trading_session is True
    assert parsed_date.is_valid is True

    # 3. Parse ALOS3 with exchange filter
    parsed_alos3 = parser.parse("ALOS3", exchange="B3")
    assert parsed_alos3.symbol == "ALOS3"
    assert parsed_alos3.exchange == "B3"

    # 4. Unknown equity on incorrect exchange should raise error
    with pytest.raises(ValueError, match="Unable to parse ticker"):
        parser.parse("PETR4", exchange="CME")
