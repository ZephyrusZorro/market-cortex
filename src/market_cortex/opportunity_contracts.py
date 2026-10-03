"""Versioned, typed research opportunity and thesis contracts."""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .contracts import utc
from .market_state import PILOT_SYMBOLS


Outcome = Literal["candidate", "rejected", "insufficient_data", "unsupported"]
Status = Literal["WATCHING", "DEVELOPING", "AWAITING_CONFIRMATION", "VALID",
                 "NO_EDGE", "EVENT_RISK", "AVOID", "INVALIDATED"]
Strength = Literal["weak", "moderate", "strong"]
Mode = Literal["latest", "pinned", "historical"]


class ScanRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    mode: Mode = "latest"
    manifest_id: UUID | None = None
    as_of: datetime | None = None
    symbol: str | None = None
    detector_id: str | None = None
    record: bool = False

    @field_validator("as_of")
    @classmethod
    def aware(cls, value: datetime | None) -> datetime | None:
        return utc(value) if value is not None else None

    @field_validator("symbol")
    @classmethod
    def pilot_symbol(cls, value: str | None) -> str | None:
        if value is not None and value.upper() not in PILOT_SYMBOLS:
            raise ValueError("UNSUPPORTED_PILOT_SYMBOL")
        return value.upper() if value else None

    @model_validator(mode="after")
    def valid_context(self) -> "ScanRequest":
        if self.mode == "pinned" and self.manifest_id is None:
            raise ValueError("PINNED_MANIFEST_REQUIRED")
        if self.mode == "historical" and self.as_of is None:
            raise ValueError("HISTORICAL_CUTOFF_REQUIRED")
        if self.mode == "latest" and (self.manifest_id is None) != (self.as_of is None):
            raise ValueError("LATEST_CONTEXT_NEEDS_MANIFEST_AND_CUTOFF")
        return self


class DetectorDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid")
    detector_id: str
    version: str
    description: str
    required_features: list[str]
    optional_features: list[str] = Field(default_factory=list)
    minimum_history: int
    asset_classes: list[str] = Field(default_factory=lambda: ["crypto_spot"])
    timeframe: str = "P1D"
    universe_id: str = "binance_pilot_5"
    market_state_policy: str
    trigger_rules: list[str]
    confirmation_rules: list[str]
    invalidation_rules: list[str]
    rejection_rules: list[str]
    freshness_policy: str = "stale evidence cannot be VALID"
    minimum_coverage: float = 0.9
    enabled: bool = True
    unsupported_reason: str | None = None


class OpportunityEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid")
    evidence_id: str
    metric: str
    value: float | str | None
    unit: str | None = None
    symbol: str
    instrument_id: UUID
    session_date: date | None
    source_manifest_id: UUID
    as_of: datetime
    source_id: str | None = None
    feature_version: str | None = None
    parameters: dict[str, int | float] = Field(default_factory=dict)
    quality: str | None = None
    freshness: str | None = None
    coverage: float | None = None
    reason: str | None = None


class Condition(BaseModel):
    model_config = ConfigDict(extra="forbid")
    condition_id: str
    kind: Literal["trigger", "confirmation", "invalidation", "rejection"]
    metric: str
    operator: Literal["gt", "gte", "lt", "lte", "eq", "between"]
    threshold: float | str | list[float]
    observed: float | str | None
    met: bool | None
    evidence_ids: list[str]
    description: str


class Candidate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: str = "candidate_v1"
    candidate_id: UUID
    created_at: datetime
    instrument_id: UUID
    symbol: str
    detector_id: str
    detector_version: str
    outcome: Outcome
    status: Status
    detector_strength: Strength
    event_date: date | None
    as_of: datetime
    source_manifest_id: UUID
    timeframe: str = "P1D"
    horizon: str = "swing_days_2_to_20"
    bias: Literal["bullish", "bearish", "neutral"]
    universe_id: str = "binance_pilot_5"
    reference_symbol: str | None = None
    market_regime: str | None = None
    market_state_id: str | None = None
    evidence: list[OpportunityEvidence]
    trigger_conditions: list[Condition]
    confirmation_conditions: list[Condition]
    invalidation_conditions: list[Condition]
    rejection_conditions: list[Condition]
    supporting_evidence_ids: list[str]
    opposing_evidence_ids: list[str]
    contradictions: list[str]
    rejection_reasons: list[str]
    coverage: float
    freshness: str
    data_quality: str
    evidence_hash: str
    elapsed_ms: float


class ScanResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    scan_id: UUID
    created_at: datetime
    request: ScanRequest
    source_manifest_id: UUID
    as_of: datetime
    universe_id: str = "binance_pilot_5"
    evaluation_date: date | None
    market_regime: str | None
    candidates: list[Candidate]
    counts: dict[str, int]
    elapsed_ms: float
    recorded_events: int = 0
    unavailable_members: list[str] = Field(default_factory=list)


class ThesisTransition(BaseModel):
    model_config = ConfigDict(extra="forbid")
    from_status: Status | None
    to_status: Status
    at: datetime
    actor: Literal["detector", "owner"]
    reason: str
    source_manifest_id: UUID
    as_of: datetime
    changed_evidence_ids: list[str] = Field(default_factory=list)


class Thesis(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: str = "research_thesis_v1"
    thesis_id: UUID
    version: int
    candidate_ids: list[UUID]
    instrument_id: UUID
    symbol: str
    detector_id: str
    detector_version: str
    status: Status
    horizon: str
    market_regime: str | None
    statement: str
    supporting_evidence_ids: list[str]
    opposing_evidence_ids: list[str]
    confirmation_conditions: list[Condition]
    invalidation_conditions: list[Condition]
    assumptions: list[str]
    risk_factors: list[str]
    data_limitations: list[str]
    source_manifest_id: UUID
    as_of: datetime
    feature_versions: dict[str, str]
    cortex_run_ids: list[UUID] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime
    transitions: list[ThesisTransition]
    candidate: Candidate


class ThesisCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    candidate_id: UUID
    cortex_run_id: UUID | None = None


class ThesisDecisionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: Literal["WATCHING", "NO_EDGE", "EVENT_RISK", "AVOID"]
    reason: str = Field(min_length=8, max_length=500)


class ThesisMonitorRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    mode: Mode = "latest"
    manifest_id: UUID | None = None
    as_of: datetime | None = None

    @field_validator("as_of")
    @classmethod
    def aware(cls, value: datetime | None) -> datetime | None:
        return utc(value) if value is not None else None

    @model_validator(mode="after")
    def valid_context(self) -> "ThesisMonitorRequest":
        ScanRequest(mode=self.mode, manifest_id=self.manifest_id, as_of=self.as_of)
        return self
