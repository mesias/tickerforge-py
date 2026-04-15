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
    assert parsed.lot_size == contract.contract_multiplier


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
