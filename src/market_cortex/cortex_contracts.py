"""Strict public contracts for a manifest-pinned CORTEX research run."""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .contracts import utc
from .market_state import PILOT_SYMBOLS


class ResearchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    question: str = Field(min_length=3, max_length=600)
    mode: Literal["latest", "pinned", "historical"] = "latest"
    manifest_id: UUID | None = None
    as_of: datetime | None = None
    symbol: str | None = None
    compare_symbol: str | None = None
    older_manifest_id: UUID | None = None
    candidate_id: UUID | None = None
    thesis_id: UUID | None = None
    depth: Literal["quick", "deep"] = "deep"

    @field_validator("as_of")
    @classmethod
    def aware(cls, value: datetime | None) -> datetime | None:
        return utc(value) if value is not None else None

    @field_validator("symbol", "compare_symbol")
    @classmethod
    def supported_symbol(cls, value: str | None) -> str | None:
        if value is not None and value.upper() not in PILOT_SYMBOLS:
            raise ValueError("UNSUPPORTED_PILOT_SYMBOL")
        return value.upper() if value else None

    @model_validator(mode="after")
    def compatible_mode(self) -> "ResearchRequest":
        if self.mode == "pinned" and self.manifest_id is None:
            raise ValueError("PINNED_MANIFEST_REQUIRED")
        if self.mode == "historical" and self.as_of is None:
            raise ValueError("HISTORICAL_CUTOFF_REQUIRED")
        if self.mode == "latest" and (self.manifest_id is None) != (self.as_of is None):
            raise ValueError("LATEST_CONTEXT_NEEDS_MANIFEST_AND_CUTOFF")
        return self


class ResearchContext(BaseModel):
    model_config = ConfigDict(extra="forbid")
    mode: str
    manifest_id: UUID
    as_of: datetime
    universe_id: str = "binance_pilot_5"
    evaluation_date: date | None
    history_start: date | None
    members: dict[str, UUID]
    member_last_sessions: dict[str, date] = Field(default_factory=dict)
    symbol: str | None
    compare_symbol: str | None
    environment: str
    base_currency: str
    secondary_currency: str = "USD"


class Evidence(BaseModel):
    model_config = ConfigDict(extra="forbid")
    evidence_id: str
    tool_id: str
    kind: str
    label: str
    symbol: str | None = None
    instrument_id: UUID | None = None
    value: float | int | str | None = None
    unit: str | None = None
    session_date: date | None = None
    manifest_id: UUID
    as_of: datetime
    source_id: str | None = None
    provider_id: str | None = None
    source_manifest_id: UUID | None = None
    source_as_of: datetime | None = None
    source_recorded_at: datetime | None = None
    version: str | None = None
    parameters: dict[str, int | float] = Field(default_factory=dict)
    observation_id: UUID | None = None
    quality: str | None = None
    freshness: str | None = None
    coverage: float | None = None
    reason: str | None = None


class ToolRun(BaseModel):
    model_config = ConfigDict(extra="forbid")
    tool_id: str
    version: str
    description: str
    inputs: dict
    status: Literal["ok", "insufficient", "unavailable"]
    evidence: list[Evidence]
    output_hash: str
    elapsed_ms: float


class Claim(BaseModel):
    model_config = ConfigDict(extra="forbid")
    claim_id: str
    type: Literal["OBSERVATION", "CALCULATION", "CLASSIFICATION", "INTERPRETATION", "LIMITATION", "HYPOTHESIS"]
    text: str
    evidence_ids: list[str]
    stance: Literal["support", "counter", "neutral", "limitation"] = "neutral"


class ResearchRun(BaseModel):
    model_config = ConfigDict(extra="forbid")
    run_id: UUID
    created_at: datetime
    request: ResearchRequest
    context: ResearchContext
    tools: list[ToolRun]
    claims: list[Claim]
    evidence_strength: Literal["weak", "moderate", "strong"]
    answer: str
    warnings: list[str]
    failure_state: str | None = None
    evidence_hash: str
    orchestration_version: str = "cortex_orchestrator_v1"
    model_prompt_version: str = "cortex_claim_selection_v1"
    model_configuration: dict[str, str | int | float | bool] = Field(default_factory=dict)
    model_provider: str = "deterministic"
    model_id: str | None = None
    model_status: str = "no_model_configured"
    model_latency_ms: float = 0
    deterministic_latency_ms: float = 0
    total_latency_ms: float = 0
    model_input_tokens: int | None = None
    model_output_tokens: int | None = None
    model_cost: str = "local / ₹0 API spend"
