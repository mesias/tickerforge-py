from pathlib import Path

from tickerforge import TickerForge, load_spec
from tickerforge.models import ContractSpec, SessionSegment


def test_load_spec_reads_b3_exchange_and_contracts():
    spec_path = Path(__file__).resolve().parents[1] / "spec"
    spec = load_spec(spec_path)

    exchange = spec.get_exchange("B3")
    contract = spec.get_contract("IND")

    assert exchange.code == "B3"
    assert "IND" in exchange.assets
    assert contract.symbol == "IND"
    assert contract.ticker_format == "{symbol}{month_code}{yy}"

    dol = spec.get_contract("DOL")
    assert dol.tick_size == 0.5
    assert dol.regular_session_start_end() == ("09:00", "18:30")
    assert dol.exchange_timezone == "America/Sao_Paulo"
    assert dol.sessions[0].name == "regular"
    assert dol.sessions[0].start == "09:00"
    assert dol.sessions[0].end == "18:30"
    assert dol.is_unique_session()
    assert dol.default_session() is not None
    assert dol.default_session().name == "regular"


def test_default_session_only_when_single_segment():
    one = ContractSpec(
        symbol="Y",
        exchange="B3",
        contract_cycle="m",
        expiration_rule="r",
        sessions=[SessionSegment(name="regular", start="09:00", end="18:00")],
    )
    assert one.is_unique_session()
    assert one.default_session() is not None
    assert one.default_session().name == "regular"

    multi = ContractSpec(
        symbol="Z",
        exchange="B3",
        contract_cycle="m",
        expiration_rule="r",
        sessions=[
            SessionSegment(name="regular", start="09:00", end="12:00"),
            SessionSegment(name="afternoon", start="13:00", end="18:00"),
        ],
    )
    assert not multi.is_unique_session()
    assert multi.default_session() is None


def test_contract_trading_symbol_matches_forge():
    spec_path = Path(__file__).resolve().parents[1] / "spec"
    spec = load_spec(spec_path)
    dol = spec.get_contract("DOL")
    forge = TickerForge(spec_path=spec_path)

    assert dol.trading_symbol_for("2026-03-15", spec=spec) == forge.generate(
        "DOL", "2026-03-15"
    )
    assert dol.trading_symbol_for("2026-03-15") == TickerForge().generate(
        "DOL", "2026-03-15"
    )

    assert dol.trading_symbol_today(spec=spec) == forge.gen("DOL")
    assert dol.trading_symbol_today() == TickerForge().gen("DOL")


def test_models_additional_coverage():
    import pytest

    from tickerforge.models import Asset, EquitySpec, _sessions_mapping_to_list

    # Line 27: sess item not a dict
    with pytest.raises(ValueError, match="must be an object with start and end"):
        _sessions_mapping_to_list({"bad": "not_dict"})

    # Line 30: missing start or end
    with pytest.raises(ValueError, match="requires start and end"):
        _sessions_mapping_to_list({"bad": {"start": "09:00"}})

    # Line 48: Asset model validator with non-dict
    with pytest.raises(ValueError):
        Asset.model_validate("not_dict")

    # Line 57: Asset sessions empty
    with pytest.raises(
        ValueError, match="Asset sessions must include at least one segment"
    ):
        Asset(symbol="A", sessions=[])

    # Line 59: Asset first session segment not 'regular'
    with pytest.raises(
        ValueError, match="First session segment must be named 'regular'"
    ):
        Asset(
            symbol="A",
            sessions=[SessionSegment(name="afternoon", start="13:00", end="17:00")],
        )

    # Line 64 & 68: Asset is_unique_session and default_session
    asset_single = Asset(
        symbol="A",
        sessions=[SessionSegment(name="regular", start="09:00", end="17:00")],
    )
    assert asset_single.is_unique_session() is True
    assert asset_single.default_session() is not None

    asset_multi = Asset(
        symbol="A",
        sessions=[
            SessionSegment(name="regular", start="09:00", end="12:00"),
            SessionSegment(name="afternoon", start="13:00", end="17:00"),
        ],
    )
    assert asset_multi.is_unique_session() is False
    assert asset_multi.default_session() is None

    # Line 192: EquitySpec regular_session_start_end when no regular session
    eq_no_reg = EquitySpec(
        symbol="EQ",
        exchange="B3",
        type="equity",
        sessions=[],
    )
    assert eq_no_reg.regular_session_start_end() is None

    # Line 218: ContractSpec model validator with non-dict
    with pytest.raises(ValueError):
        ContractSpec.model_validate("not_dict")

    # Line 221: ContractSpec sessions passed as dict in kwargs
    cs_dict_sessions = ContractSpec(
        symbol="C",
        exchange="B3",
        contract_cycle="m",
        expiration_rule="r",
        sessions={"regular": {"start": "09:00", "end": "18:00"}},
    )
    assert cs_dict_sessions.sessions[0].name == "regular"

    # Line 227: ContractSpec first session not regular
    with pytest.raises(
        ValueError, match="First session segment must be named 'regular'"
    ):
        ContractSpec(
            symbol="C",
            exchange="B3",
            contract_cycle="m",
            expiration_rule="r",
            sessions=[SessionSegment(name="morning", start="08:00", end="12:00")],
        )

    # Line 246: ContractSpec regular_session_start_end when empty sessions
    cs_no_sessions = ContractSpec(
        symbol="C",
        exchange="B3",
        contract_cycle="m",
        expiration_rule="r",
        sessions=[],
    )
    assert cs_no_sessions.regular_session_start_end() is None
