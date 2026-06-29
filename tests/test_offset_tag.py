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
