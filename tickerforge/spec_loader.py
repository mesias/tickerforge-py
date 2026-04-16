from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

from tickerforge.models import (
    Asset,
    ContractCycle,
    ContractSpec,
    Exchange,
    ExpirationRule,
    OptionSpec,
)
from tickerforge.schedule import ExchangeSchedule, load_schedules


@dataclass
class SpecRepository:
    exchanges: dict[str, Exchange]
    contracts: dict[str, ContractSpec]
    options: list[OptionSpec]
    contract_cycles: dict[str, ContractCycle]
    expiration_rules: dict[str, ExpirationRule]
    schedules: dict[str, ExchangeSchedule]

    def get_exchange(self, code: str) -> Exchange:
        key = code.upper()
        try:
            return self.exchanges[key]
        except KeyError as exc:
            raise KeyError(f"Unknown exchange: {code}") from exc

    def get_contract(self, symbol: str) -> ContractSpec:
        key = symbol.upper()
        try:
            return self.contracts[key]
        except KeyError as exc:
            raise KeyError(f"Unknown contract: {symbol}") from exc


def _read_yaml(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
        if not isinstance(data, dict):
            raise ValueError(f"Expected YAML mapping in {path}")
        return data


def _load_exchanges(spec_root: Path) -> dict[str, Exchange]:
    exchanges: dict[str, Exchange] = {}
    exchanges_dir = spec_root / "exchanges"
    for yaml_path in sorted(exchanges_dir.glob("*.yaml")):
        raw = _read_yaml(yaml_path)
        code = str(raw.get("exchange", "")).upper()
        if not code:
            raise ValueError(f"Missing 'exchange' in {yaml_path}")

        assets_data = raw.get("assets", {})
        assets: dict[str, Asset] = {}
        if isinstance(assets_data, dict):
            for symbol, payload in assets_data.items():
                payload = payload or {}
                if not isinstance(payload, dict):
                    raise ValueError(f"Invalid asset '{symbol}' in {yaml_path}")
                assets[symbol.upper()] = Asset(symbol=symbol.upper(), **payload)

        exchanges[code] = Exchange(
            code=code,
            mic=raw.get("mic"),
            full_name=raw.get("full_name"),
            country=raw.get("country"),
            timezone=raw.get("timezone"),
            assets=assets,
        )
    return exchanges


def _load_cycles_and_rules(
    spec_root: Path,
) -> tuple[dict[str, ContractCycle], dict[str, ExpirationRule]]:
    source_path = spec_root / "schemas" / "contract_cycles.yaml"
    raw = _read_yaml(source_path)

    cycles: dict[str, ContractCycle] = {}
    for name, payload in (raw.get("contract_cycles") or {}).items():
        payload = payload or {}
        cycles[name] = ContractCycle(name=name, **payload)

    rules: dict[str, ExpirationRule] = {}
    for name, payload in (raw.get("expiration_rules") or {}).items():
        payload = payload or {}
        rules[name] = ExpirationRule(name=name, **payload)

    return cycles, rules


def _load_contracts(spec_root: Path) -> list[ContractSpec]:
    contracts: list[ContractSpec] = []
    contracts_dir = spec_root / "contracts"
    for yaml_path in sorted(contracts_dir.glob("**/*.yaml")):
        raw = _read_yaml(yaml_path)
        items = raw.get("contracts")
        if items is None:
            continue
        if not isinstance(items, list):
            raise ValueError(f"Expected list under 'contracts' in {yaml_path}")
        for item in items:
            if not isinstance(item, dict):
                raise ValueError(f"Invalid contract item in {yaml_path}")
            contracts.append(ContractSpec(**item))
    return contracts


def _load_options(spec_root: Path) -> list[OptionSpec]:
    options: list[OptionSpec] = []
    contracts_dir = spec_root / "contracts"
    for yaml_path in sorted(contracts_dir.glob("**/*.yaml")):
        raw = _read_yaml(yaml_path)
        items = raw.get("options")
        if items is None:
            continue
        if not isinstance(items, list):
            raise ValueError(f"Expected list under 'options' in {yaml_path}")
        for item in items:
            if not isinstance(item, dict):
                raise ValueError(f"Invalid option item in {yaml_path}")
            options.append(OptionSpec(**item))
    return options


def _default_spec_path() -> Path:
    try:
        from tickerforge_spec_data import get_spec_root
    except ImportError as exc:
        raise RuntimeError(
            "No spec path provided and tickerforge-spec-data is not installed. "
            "Install dependency or pass spec_path explicitly."
        ) from exc

    return Path(get_spec_root()).expanduser().resolve()


def load_spec(path: str | Path | None = None) -> SpecRepository:
    spec_root = (
        _default_spec_path() if path is None else Path(path).expanduser().resolve()
    )
    if not spec_root.exists():
        raise FileNotFoundError(f"Spec path does not exist: {spec_root}")

    exchanges = _load_exchanges(spec_root)
    contract_cycles, expiration_rules = _load_cycles_and_rules(spec_root)

    contracts: dict[str, ContractSpec] = {}
    for contract in _load_contracts(spec_root):
        if contract.contract_cycle not in contract_cycles:
            raise ValueError(
                f"Contract {contract.symbol} references unknown cycle "
                f"'{contract.contract_cycle}'"
            )
        if contract.expiration_rule not in expiration_rules:
            raise ValueError(
                f"Contract {contract.symbol} references unknown rule "
                f"'{contract.expiration_rule}'"
            )
        contracts[contract.symbol.upper()] = contract

    for sym, contract in list(contracts.items()):
        ex = exchanges.get(contract.exchange.upper())
        if not ex:
            continue
        asset = ex.assets.get(sym)
        sessions = list(asset.sessions) if asset else []
        contracts[sym] = contract.model_copy(
            update={
                "sessions": sessions,
                "exchange_timezone": ex.timezone,
            }
        )

    options = _load_options(spec_root)

    schedules = load_schedules(spec_root)

    from tickerforge.calendars import register_schedules

    register_schedules(schedules)

    return SpecRepository(
        exchanges=exchanges,
        contracts=contracts,
        options=options,
        contract_cycles=contract_cycles,
        expiration_rules=expiration_rules,
        schedules=schedules,
    )
