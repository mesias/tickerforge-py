"""Tests for the ``SYMBOL[n]`` bracket-tag offset syntax.

Semantics (see ``docs/offset-tag.md``):

* ``n >= 0`` — nth still-tradeable contract from the front (``n=0`` = front month).
* ``n < 0`` — nth most-recently-EXPIRED contract (``-1`` = the one that just rolled off).

Concrete expected tickers below were verified by running the generator against
the bundled B3 spec in the GUI venv (the proc free-threading venv segfaults on
import) and then baked into the assertions:

* ``DOL``  front on 2026-06-29 -> ``DOLN26``; ``DOL[1]`` -> ``DOLQ26``;
  ``DOL[-1]`` -> ``DOLM26``.
* ``WIN``  on 2026-06-29: ``WIN[2]`` -> ``WINZ26``.
* ``IND``  front on 2026-06-18 -> ``INDQ26``; ``IND[-1]`` -> ``INDM26``.
* ``CCM``  on 2026-09-01: ``CCM[1]`` -> ``CCMX26``; ``CCM[3]`` -> ``CCMH27`` (Mar next year).
* ``BGI``  on 2026-09-01: ``BGI[6]`` -> ``BGIH27``; on 2026-12-31: ``BGI[6]`` -> ``BGIN27``.

Offset-field convention: plain roots (``DOL``) are routed through the tag path
with ``offset=0``, so ``ParsedTicker.offset`` is ``0`` for plain roots and for
``SYMBOL[0]``; it is the tag int for ``SYMBOL[n]``; and it is ``None`` for full
tickers such as ``DOLN26`` (which never go through the tag path).
"""

from datetime import date
from pathlib import Path

import pytest

from tickerforge import TickerForge, TickerParser, parse_ticker

SPEC_PATH = Path(__file__).resolve().parents[1] / "spec"


def _forge() -> TickerForge:
    return TickerForge(spec_path=str(SPEC_PATH))


# ---------------------------------------------------------------------------
# Forward offsets (n >= 0)
# ---------------------------------------------------------------------------


def test_dol_offset_one_matches_generator_and_concrete_value():
    forge = _forge()
    ref = "2026-06-29"
    parsed = parse_ticker("DOL[1]", spec=forge.spec, reference_date=ref)
    assert parsed.ticker == "DOLQ26"
    assert parsed.ticker == forge.generate("DOL", date=ref, offset=1)


def test_win_offset_two_matches_generator_and_concrete_value():
    forge = _forge()
    ref = "2026-06-29"
    parsed = parse_ticker("WIN[2]", spec=forge.spec, reference_date=ref)
    assert parsed.ticker == "WINZ26"
    assert parsed.ticker == forge.generate("WIN", date=ref, offset=2)


def test_ccm_offset_one_matches_generator_and_concrete_value():
    forge = _forge()
    ref = "2026-09-01"
    parsed = parse_ticker("CCM[1]", spec=forge.spec, reference_date=ref)
    assert parsed.ticker == "CCMX26"
    assert parsed.ticker == forge.generate("CCM", date=ref, offset=1)
    assert parsed.offset == 1


def test_bgi_offset_six_matches_generator_and_concrete_value():
    forge = _forge()
    ref = "2026-09-01"
    parsed = parse_ticker("BGI[6]", spec=forge.spec, reference_date=ref)
    assert parsed.ticker == "BGIH27"
    assert parsed.ticker == forge.generate("BGI", date=ref, offset=6)
    assert parsed.offset == 6


def test_ccm_crosses_year():
    """September reference: CCM[3] lands in March of the next calendar year."""
    forge = _forge()
    ref = "2026-09-01"
    parsed = parse_ticker("CCM[3]", spec=forge.spec, reference_date=ref)
    assert parsed.ticker == "CCMH27"
    assert parsed.ticker == forge.generate("CCM", date=ref, offset=3)
    assert parsed.year == 2027
    assert parsed.month == 3
    assert parsed.offset == 3


def test_bgi_crosses_year():
    """Late-year reference: BGI[6] spans into the next calendar year."""
    forge = _forge()
    ref = "2026-12-31"
    parsed = parse_ticker("BGI[6]", spec=forge.spec, reference_date=ref)
    assert parsed.ticker == "BGIN27"
    assert parsed.ticker == forge.generate("BGI", date=ref, offset=6)
    assert parsed.year == 2027
    assert parsed.month == 7
    assert parsed.offset == 6


def test_dol_offset_zero_equals_plain_root():
    ref = "2026-06-29"
    assert parse_ticker("DOL[0]", reference_date=ref).ticker == "DOLN26"
    assert parse_ticker("DOL[0]", reference_date=ref) == parse_ticker(
        "DOL", reference_date=ref
    )


# ---------------------------------------------------------------------------
# Negative offsets (expired contracts)
# ---------------------------------------------------------------------------


def test_ind_negative_one_matches_generator_and_concrete_value():
    forge = _forge()
    ref = "2026-06-18"
    parsed = parse_ticker("IND[-1]", spec=forge.spec, reference_date=ref)
    # IND front on 2026-06-18 is INDQ26; the most-recently-expired is INDM26.
    assert parsed.ticker == "INDM26"
    assert parsed.ticker == forge.generate("IND", date=ref, offset=-1)


def test_dol_negative_one_generation_concrete_value():
    forge = _forge()
    # DOL front on 2026-06-29 is DOLN26; the previous (expired) ticker is DOLM26.
    assert forge.generate("DOL", date="2026-06-29", offset=-1) == "DOLM26"


# ---------------------------------------------------------------------------
# ParsedTicker.offset / reference_date / is_trading_session
# ---------------------------------------------------------------------------


def test_offset_field_set_for_tag():
    parsed = parse_ticker("DOL[1]", reference_date="2026-06-29")
    assert parsed.offset == 1


def test_offset_field_zero_for_plain_root():
    # Plain roots are routed through the tag path with offset=0.
    parsed = parse_ticker("DOL", reference_date="2026-06-29")
    assert parsed.offset == 0


def test_offset_field_none_for_full_ticker():
    parsed = parse_ticker("DOLN26")
    assert parsed.offset is None


def test_offset_field_negative_for_expired_tag():
    parsed = parse_ticker("IND[-1]", reference_date="2026-06-18")
    assert parsed.offset == -1


def test_reference_date_and_session_populated_for_tag():
    parsed = parse_ticker("DOL[1]", reference_date="2026-06-29")
    assert parsed.reference_date == date(2026, 6, 29)
    # 2026-06-29 is a Monday and a B3 trading session.
    assert parsed.is_trading_session is True


# ---------------------------------------------------------------------------
# Error cases
# ---------------------------------------------------------------------------


def test_forward_out_of_range_raises():
    with pytest.raises(ValueError, match="out of range"):
        parse_ticker("DOL[999]", reference_date="2026-06-29")


def test_negative_out_of_range_raises():
    with pytest.raises(ValueError, match="out of range"):
        parse_ticker("DOL[-999]", reference_date="2026-06-29")


def test_unknown_root_raises():
    with pytest.raises(ValueError, match="Unable to parse ticker"):
        parse_ticker("ZZZ[1]", reference_date="2026-06-29")


def test_full_ticker_unaffected_by_tag_regex():
    # DOLK26C5000 contains no '[' and must parse as an option, not a tag.
    parsed = parse_ticker("DOLK26C5000")
    assert parsed.asset_type == "option"
    assert parsed.offset is None


# ---------------------------------------------------------------------------
# Builder
# ---------------------------------------------------------------------------


def test_builder_tagged_root_matches_direct_parse():
    expected = parse_ticker("DOL[1]", spec=_forge().spec, reference_date="2026-06-29")
    built = (
        TickerParser.builder()
        .spec_path(str(SPEC_PATH))
        .ticker("DOL[1]")
        .reference_date("2026-06-29")
        .parse()
    )
    assert built.ticker == "DOLQ26"
    assert built == expected
    assert built.offset == 1


# ---------------------------------------------------------------------------
# Conditional Roll-Day Exception (@roll)
# ---------------------------------------------------------------------------


def test_dol_roll_tag_valid_on_roll_day():
    forge = _forge()
    # June 30th is the last trading day of DOLN26 (which expires on July 1st)
    ref = "2026-06-30"

    # Shortcut: DOL[@roll] resolves to the rolled front contract (offset=0) -> DOLQ26
    parsed = parse_ticker("DOL[@roll]", spec=forge.spec, reference_date=ref)
    assert parsed.ticker == "DOLQ26"
    assert parsed.offset == 0

    # Expiring contract: DOL[-1@roll] resolves to the expiring contract -> DOLN26
    parsed_expiring = parse_ticker("DOL[-1@roll]", spec=forge.spec, reference_date=ref)
    assert parsed_expiring.ticker == "DOLN26"
    assert parsed_expiring.offset == -1


def test_dol_roll_tag_invalid_on_non_roll_day():
    forge = _forge()
    # June 29th is NOT the roll day (June 30th is)
    ref = "2026-06-29"
    with pytest.raises(ValueError, match="is not valid on 2026-06-29"):
        parse_ticker("DOL[@roll]", spec=forge.spec, reference_date=ref)

    with pytest.raises(ValueError, match="is not valid on 2026-06-29"):
        parse_ticker("DOL[0@roll]", spec=forge.spec, reference_date=ref)


def test_win_roll_tag_index_future():
    forge = _forge()
    # For WINM26 (June 2026), the expiration is June 17th, 2026.
    # WIN remains tradeable on expiration day, so the last trading day is June 17th.
    ref_roll = "2026-06-17"
    ref_other = "2026-06-16"

    # On roll day: WIN[@roll] resolves to the next cycle contract (WINQ26)
    parsed = parse_ticker("WIN[@roll]", spec=forge.spec, reference_date=ref_roll)
    assert parsed.ticker == "WINQ26"
    assert parsed.offset == 1

    # On roll day: WIN[0@roll] resolves to the expiring contract (WINM26)
    parsed_zero = parse_ticker("WIN[0@roll]", spec=forge.spec, reference_date=ref_roll)
    assert parsed_zero.ticker == "WINM26"
    assert parsed_zero.offset == 0

    # On non-roll day: fails to parse
    with pytest.raises(ValueError, match="is not valid on 2026-06-16"):
        parse_ticker("WIN[@roll]", spec=forge.spec, reference_date=ref_other)


# ---------------------------------------------------------------------------
# is_valid Flag Verification
# ---------------------------------------------------------------------------


def test_is_valid_flag_for_roll_day():
    forge = _forge()
    ref = "2026-06-30"
    parsed = parse_ticker("DOL[@roll]", spec=forge.spec, reference_date=ref)
    assert parsed.is_valid is True


def test_is_valid_flag_for_expired_contracts():
    forge = _forge()
    ref = "2026-07-01"
    # DOLQ24 (August 2024 contract) has expired as of July 1st, 2026
    parsed_expired = parse_ticker("DOLQ24", spec=forge.spec, reference_date=ref)
    assert parsed_expired.is_valid is False


def test_is_valid_flag_for_active_contracts():
    forge = _forge()
    ref = "2026-07-01"
    # DOLQ26 (August 2026 contract) is active as of July 1st, 2026
    parsed_active = parse_ticker("DOLQ26", spec=forge.spec, reference_date=ref)
    assert parsed_active.is_valid is True
