from datetime import date
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

    today = date.today().isoformat()
    assert dol.trading_symbol_today(spec=spec) == forge.generate("DOL", today)
    assert dol.trading_symbol_today() == TickerForge().generate("DOL", today)
