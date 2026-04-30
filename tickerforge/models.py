from __future__ import annotations

from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

if TYPE_CHECKING:
    from datetime import date, datetime

    from tickerforge.spec_loader import SpecRepository


class SessionSegment(BaseModel):
    """One clock-time trading window; YAML uses the key as ``name`` (not repeated in the value)."""

    model_config = ConfigDict(extra="forbid")

    name: str
    start: str
    end: str


def _sessions_mapping_to_list(sess: dict[str, Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for k, v in sess.items():
        if not isinstance(v, dict):
            raise ValueError(f"session '{k}' must be an object with start and end")
        start, end = v.get("start"), v.get("end")
        if start is None or end is None:
            raise ValueError(f"session '{k}' requires start and end")
        out.append({"name": str(k), "start": str(start), "end": str(end)})
    return out


class Asset(BaseModel):
    model_config = ConfigDict(extra="allow")

    symbol: str
    type: str | None = None
    category: str | None = None
    description: str | None = None
    sessions: list[SessionSegment] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def _sessions_map_to_segments(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        sess = data.get("sessions")
        if isinstance(sess, dict):
            data = {**data, "sessions": _sessions_mapping_to_list(sess)}
        return data

    @model_validator(mode="after")
    def _validate_sessions(self) -> Asset:
        if not self.sessions:
            raise ValueError("Asset sessions must include at least one segment")
        if self.sessions[0].name.lower() != "regular":
            raise ValueError("First session segment must be named 'regular'")
        return self

    def is_unique_session(self) -> bool:
        """True if there is exactly one trading band (no implicit pauses between segments)."""
        return len(self.sessions) == 1

    def default_session(self) -> SessionSegment | None:
        """The sole session when ``is_unique_session``; otherwise ``None`` (multiple bands)."""
        return self.sessions[0] if len(self.sessions) == 1 else None


class Exchange(BaseModel):
    model_config = ConfigDict(extra="allow")

    code: str
    mic: str | None = None
    full_name: str | None = None
    country: str | None = None
    timezone: str | None = None
    assets: dict[str, Asset] = Field(default_factory=dict)


class ContractCycle(BaseModel):
    model_config = ConfigDict(extra="allow")

    name: str
    description: str | None = None
    months: list[str] = Field(default_factory=list)


class ExpirationRule(BaseModel):
    model_config = ConfigDict(extra="allow")

    name: str
    type: str
    description: str | None = None
    weekday: str | None = None
    day: int | None = None
    n: int | None = None
    tags: list[str] = Field(default_factory=list)


class OptionSpec(BaseModel):
    """Specification for an option contract loaded from ``options:`` blocks in spec YAML."""

    model_config = ConfigDict(extra="allow")

    type: str
    symbol: str | None = None
    exchange: str
    option_style: str
    ticker_format: str
    contract_multiplier: float | None = None
    tick_size: float | None = None
    currency: str | None = None
    aliases: list[str] = Field(default_factory=list)
    call_month_codes: list[str] | None = None
    put_month_codes: list[str] | None = None
    option_type_codes: dict[str, str] | None = None
    contract_cycle: str | None = None
    expiration_rule: str
    underlyings: list[str] | None = None
    description: str | None = None


class EquitySpec(BaseModel):
    model_config = ConfigDict(extra="allow")

    symbol: str
    exchange: str
    type: str
    description: str | None = None
    currency: str | None = None
    tick_size: float | None = None
    contract_multiplier: float | None = None
    aliases: list[str] = Field(default_factory=list)
    sessions: list[SessionSegment] = Field(default_factory=list)
    exchange_timezone: str | None = None

    @model_validator(mode="before")
    @classmethod
    def _sessions_map_to_segments(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        sess = data.get("sessions")
        if isinstance(sess, dict):
            data = {**data, "sessions": _sessions_mapping_to_list(sess)}
        return data

    @model_validator(mode="after")
    def _validate_sessions(self) -> EquitySpec:
        if self.sessions and self.sessions[0].name.lower() != "regular":
            raise ValueError("First session segment must be named 'regular'")
        return self

    def regular_session(self) -> SessionSegment | None:
        """The regular band (first segment; clock times in ``exchange_timezone``)."""
        return self.sessions[0] if self.sessions else None

    def is_unique_session(self) -> bool:
        """True if there is exactly one trading band (no implicit pauses between segments)."""
        return len(self.sessions) == 1

    def default_session(self) -> SessionSegment | None:
        """The sole session when there is only one band; ``None`` if zero or multiple segments."""
        return self.sessions[0] if len(self.sessions) == 1 else None

    def regular_session_start_end(self) -> tuple[str, str] | None:
        """Start and end clock times for the regular session, e.g. ``('09:00', '18:30')``."""
        reg = self.regular_session()
        if not reg:
            return None
        return (reg.start, reg.end)


class ContractSpec(BaseModel):
    model_config = ConfigDict(extra="allow")

    symbol: str
    exchange: str
    description: str | None = None
    ticker_format: str = "{symbol}{month_code}{yy}"
    contract_cycle: str
    expiration_rule: str
    contract_multiplier: float | None = None
    tick_size: float | None = None
    currency: str | None = None
    aliases: list[str] = Field(default_factory=list)
    # Filled at load time from `exchanges/<mic>.yaml` for this symbol (not in contract YAML).
    sessions: list[SessionSegment] = Field(default_factory=list)
    exchange_timezone: str | None = None

    @model_validator(mode="before")
    @classmethod
    def _sessions_map_to_segments(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        sess = data.get("sessions")
        if isinstance(sess, dict):
            data = {**data, "sessions": _sessions_mapping_to_list(sess)}
        return data

    @model_validator(mode="after")
    def _validate_sessions(self) -> ContractSpec:
        if self.sessions and self.sessions[0].name.lower() != "regular":
            raise ValueError("First session segment must be named 'regular'")
        return self

    def regular_session(self) -> SessionSegment | None:
        """The regular band (first segment; clock times in ``exchange_timezone``)."""
        return self.sessions[0] if self.sessions else None

    def is_unique_session(self) -> bool:
        """True if there is exactly one trading band (no implicit pauses between segments)."""
        return len(self.sessions) == 1

    def default_session(self) -> SessionSegment | None:
        """The sole session when there is only one band; ``None`` if zero or multiple segments."""
        return self.sessions[0] if len(self.sessions) == 1 else None

    def regular_session_start_end(self) -> tuple[str, str] | None:
        """Start and end clock times for the regular session, e.g. ``('09:00', '18:30')``."""
        reg = self.regular_session()
        if not reg:
            return None
        return (reg.start, reg.end)

    def trading_symbol_today(
        self,
        spec: SpecRepository | None = None,
        *,
        offset: int = 0,
    ) -> str:
        """Front-month ticker using bundled spec unless ``spec`` is passed."""
        from datetime import date

        from tickerforge.spec_loader import load_spec
        from tickerforge.ticker_generator import generate_ticker_for_contract

        repo = spec if spec is not None else load_spec()
        return generate_ticker_for_contract(self, date.today(), repo, offset=offset)

    def trading_symbol_for(
        self,
        as_of: str | date | datetime,
        spec: SpecRepository | None = None,
        *,
        offset: int = 0,
    ) -> str:
        """Front-month ticker for ``as_of``; bundled spec unless ``spec`` is passed."""
        from tickerforge.spec_loader import load_spec
        from tickerforge.ticker_generator import generate_ticker_for_contract

        repo = spec if spec is not None else load_spec()
        return generate_ticker_for_contract(self, as_of, repo, offset=offset)
