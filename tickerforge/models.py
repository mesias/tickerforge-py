from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class Asset(BaseModel):
    model_config = ConfigDict(extra="allow")

    symbol: str
    type: str | None = None
    category: str | None = None
    description: str | None = None
    sessions: dict[str, dict[str, str]] = Field(default_factory=dict)


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
