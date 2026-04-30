from pathlib import Path

import pytest

from tickerforge.models import EquitySpec
from tickerforge.spec_loader import load_spec


def test_equity_spec_model():
    data = {
        "symbol": "PETR4",
        "exchange": "B3",
        "type": "equity",
        "sessions": {"regular": {"start": "10:00", "end": "17:00"}},
    }
    eq = EquitySpec(**data)
    assert eq.symbol == "PETR4"
    assert eq.is_unique_session()
    assert eq.regular_session().start == "10:00"
    assert eq.default_session().end == "17:00"
    assert eq.regular_session_start_end() == ("10:00", "17:00")


def test_equity_spec_multiple_sessions():
    data = {
        "symbol": "FOO",
        "exchange": "B3",
        "type": "equity",
        "sessions": {
            "regular": {"start": "10:00", "end": "12:00"},
            "afternoon": {"start": "13:00", "end": "17:00"},
        },
    }
    eq = EquitySpec(**data)
    assert not eq.is_unique_session()
    assert eq.default_session() is None
    assert eq.regular_session_start_end() == ("10:00", "12:00")


def test_equity_spec_validation_error():
    data = {
        "symbol": "ERR",
        "exchange": "B3",
        "type": "equity",
        "sessions": {"afternoon": {"start": "13:00", "end": "17:00"}},
    }
    with pytest.raises(
        ValueError, match="First session segment must be named 'regular'"
    ):
        EquitySpec(**data)


def test_load_equities_from_spec():
    # Load using the default bundled spec path, which should now have spec/equities/b3.yaml
    # We need to make sure we point to our local dev directory, but load_spec will use tickerforge_spec_data if installed.
    # We will pass the local path explicitly for testing.
    local_spec = Path(__file__).parent.parent / "spec"
    if not local_spec.exists():
        pytest.skip("Local spec path not found")

    repo = load_spec(local_spec)

    assert "PETR4" in repo.equities
    petr4 = repo.equities["PETR4"]
    assert petr4.exchange == "B3"
    assert petr4.type == "equity"
    assert petr4.regular_session().start == "10:00"
    assert petr4.exchange_timezone == "America/Sao_Paulo"


def test_load_equities_edge_cases(tmp_path):
    import yaml

    from tickerforge.spec_loader import _load_equities

    eq_dir = tmp_path / "equities"
    eq_dir.mkdir()

    # 1. No equities dir
    assert _load_equities(tmp_path / "fake") == []

    # 2. No equities key
    f1 = eq_dir / "1.yaml"
    f1.write_text(yaml.dump({"other": []}))
    assert _load_equities(tmp_path) == []

    # 3. Equities is not a list
    f2 = eq_dir / "2.yaml"
    f2.write_text(yaml.dump({"equities": "not a list"}))
    with pytest.raises(ValueError, match="Expected list under 'equities'"):
        _load_equities(tmp_path)
    f2.unlink()

    # 4. Equity item is not a dict
    f3 = eq_dir / "3.yaml"
    f3.write_text(yaml.dump({"equities": ["not a dict"]}))
    with pytest.raises(ValueError, match="Invalid equity item"):
        _load_equities(tmp_path)


def test_equity_spec_sessions_not_dict():
    # Covers model_validator where data is not a dict
    from tickerforge.models import EquitySpec

    with pytest.raises(ValueError):
        EquitySpec.model_validate("not a dict")
