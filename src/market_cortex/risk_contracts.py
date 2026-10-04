"""Strict local portfolio and deterministic research-risk contracts."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .contracts import utc
from .market_state import PILOT_SYMBOLS


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class PortfolioCreate(Strict):
    name: str = Field(min_length=1, max_length=100)
    base_currency: str = Field(pattern=r"^[A-Z]{3,5}$")
    capital: Decimal = Field(gt=0)
    classification: Literal["OWNER_RESEARCH", "SYNTHETIC_TEST_PORTFOLIO"] = "OWNER_RESEARCH"


class PositionInput(Strict):
    position_id: UUID = Field(default_factory=uuid4)
    instrument_id: UUID
    quantity: Decimal = Field(gt=0)
    average_cost: Decimal = Field(gt=0)
    native_currency: str = Field(pattern=r"^[A-Z]{3,5}$")
    opened_at: datetime
    thesis_id: UUID | None = None
    invalidation_price: Decimal | None = Field(default=None, gt=0)
    target_price: Decimal | None = Field(default=None, gt=0)
    note: str = Field(default="", max_length=500)
    source_type: Literal["manual", "synthetic_fixture"] = "manual"
    closed_at: datetime | None = None

    @field_validator("opened_at", "closed_at")
    @classmethod
    def aware(cls, value: datetime | None) -> datetime | None:
        return utc(value) if value is not None else None

    @model_validator(mode="after")
    def chronology(self) -> "PositionInput":
        if self.closed_at is not None and self.closed_at < self.opened_at:
            raise ValueError("POSITION_CLOSED_BEFORE_OPENED")
        if self.invalidation_price is not None and self.invalidation_price >= self.average_cost:
            raise ValueError("LONG_INVALIDATION_MUST_BE_BELOW_ENTRY")
        if self.target_price is not None and self.target_price <= self.average_cost:
            raise ValueError("LONG_TARGET_MUST_BE_ABOVE_ENTRY")
        return self


class PositionChange(Strict):
    action: Literal["add", "update", "close"]
    position: PositionInput
    reason: str = Field(min_length=8, max_length=500)


class Portfolio(Strict):
    schema_version: str = "portfolio_v1"
    portfolio_id: UUID
    name: str
    base_currency: str
    capital: Decimal
    classification: str
    version: int
    created_at: datetime
    updated_at: datetime
    positions: list[PositionInput]


class RiskRequest(Strict):
    manifest_id: UUID | None = None
    as_of: datetime | None = None
    portfolio_version: int | None = Field(default=None, ge=1)
    persist: bool = False

    @field_validator("as_of")
    @classmethod
    def aware(cls, value: datetime | None) -> datetime | None:
        return utc(value) if value is not None else None


class ScenarioDefinition(Strict):
    name: str = Field(min_length=1, max_length=100)
    shocks: dict[str, Decimal] = Field(min_length=1, max_length=5)
    kind: Literal["instrument_shock", "broad_crypto_shock", "custom"] = "custom"

    @model_validator(mode="after")
    def valid_shocks(self) -> "ScenarioDefinition":
        if any(symbol not in PILOT_SYMBOLS for symbol in self.shocks):
            raise ValueError("UNSUPPORTED_SCENARIO_SYMBOL")
        if any(shock < -1 or shock > 10 for shock in self.shocks.values()):
            raise ValueError("SCENARIO_SHOCK_OUT_OF_RANGE")
        if self.kind == "broad_crypto_shock" and set(self.shocks) != set(PILOT_SYMBOLS):
            raise ValueError("BROAD_SHOCK_REQUIRES_PILOT_FIVE")
        return self


class SizingRequest(Strict):
    capital: Decimal = Field(gt=0)
    entry_price: Decimal = Field(gt=0)
    invalidation_price: Decimal = Field(gt=0)
    risk_percent: Decimal | None = Field(default=None, gt=0, le=1)
    risk_amount: Decimal | None = Field(default=None, gt=0)
    target_price: Decimal | None = Field(default=None, gt=0)

    @model_validator(mode="after")
    def one_risk_budget(self) -> "SizingRequest":
        if (self.risk_percent is None) == (self.risk_amount is None):
            raise ValueError("EXACTLY_ONE_RISK_BUDGET_REQUIRED")
        if self.invalidation_price >= self.entry_price:
            raise ValueError("LONG_INVALIDATION_MUST_BE_BELOW_ENTRY")
        if self.target_price is not None and self.target_price <= self.entry_price:
            raise ValueError("LONG_TARGET_MUST_BE_ABOVE_ENTRY")
        return self


class OverlayRequest(Strict):
    risk: RiskRequest = Field(default_factory=RiskRequest)
    hypothetical_position: PositionInput
    scenario: ScenarioDefinition | None = None


class PositionRisk(Strict):
    position_id: UUID
    instrument_id: UUID
    symbol: str
    native_currency: str
    quantity: Decimal
    reference_price: Decimal | None
    price_session: str | None
    price_observation_id: UUID | None
    market_value: Decimal | None
    cost_basis: Decimal
    unrealized_pnl: Decimal | None
    pnl_percent: Decimal | None
    annualized_volatility: float | None
    atr14: float | None
    volatility_rank90: float | None
    drawdown: float | None
    maximum_drawdown: float | None
    drawdown_duration: float | None
    recovery_state: float | None
    invalidation_price: Decimal | None
    invalidation_source: str | None
    distance_to_invalidation: Decimal | None
    risk_to_invalidation: Decimal | None
    risk_percent_of_value: Decimal | None
    one_r: Decimal | None
    current_r: Decimal | None
    target_r: Decimal | None
    reward_to_risk: Decimal | None
    freshness: str
    data_quality: str
    coverage: float
    feature_ids: dict[str, str]
    warnings: list[str]
    thesis_id: UUID | None


class PortfolioExposure(Strict):
    by_instrument: dict[str, Decimal]
    by_asset_class: dict[str, Decimal]
    by_currency: dict[str, Decimal]
    by_strategy: dict[str, Decimal]
    by_provider: dict[str, Decimal]
    gross: Decimal | None
    net: Decimal | None
    currency: str | None
    concentration_weights: dict[str, Decimal]
    concentration_threshold: Decimal
    concentration_flags: list[str]


class RiskSnapshot(Strict):
    schema_version: str = "risk_snapshot_v1"
    calculation_version: str = "portfolio_risk_daily_v1"
    calculation_code_hash: str
    snapshot_id: UUID
    portfolio_id: UUID
    portfolio_version: int
    portfolio_classification: str
    portfolio_updated_at: datetime
    source_manifest_id: UUID
    as_of: datetime
    evaluation_date: str | None
    market_regime: str | None
    capital: Decimal
    base_currency: str
    positions: list[PositionRisk]
    exposure: PortfolioExposure
    portfolio_market_value: Decimal | None
    unrealized_pnl: Decimal | None
    heat_amount: Decimal | None
    heat_percent: Decimal | None
    heat_by_position: dict[str, Decimal | None]
    heat_by_strategy: dict[str, Decimal | None]
    heat_by_asset_class: dict[str, Decimal | None]
    unknown_risk_position_ids: list[UUID]
    correlation_window: int
    correlations: list[dict]
    correlation_cluster_flags: list[str]
    btc_sensitivity_proxy: Decimal | None
    portfolio_drawdown: Decimal | None = None
    coverage: float
    price_freshness: str
    feature_freshness: str
    market_state_freshness: str
    warnings: list[str]


class ScenarioResult(Strict):
    schema_version: str = "what_if_scenario_v1"
    snapshot_id: UUID
    scenario: ScenarioDefinition
    position_pnl: dict[str, Decimal | None]
    currency_pnl: dict[str, Decimal]
    portfolio_pnl: Decimal | None
    portfolio_change_percent: Decimal | None
    coverage: float
    warnings: list[str]
