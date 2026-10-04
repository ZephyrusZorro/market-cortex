"""Private journal, falsifiable expectations and immutable learning evidence."""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import Field, field_validator, model_validator

from .contracts import utc
from .market_state import PILOT_SYMBOLS
from .risk_contracts import Strict

Classification = Literal["OWNER_RESEARCH", "SYNTHETIC_TEST"]
Registration = Literal["PRE_REGISTERED", "RETROSPECTIVE_EVALUATION"]
PredictionStatus = Literal["OPEN", "PENDING_EVALUATION", "CONFIRMED", "INVALIDATED",
                           "INCONCLUSIVE", "UNMEASURABLE", "CANCELLED"]
PredictionType = Literal["forward_return", "relative_performance", "thesis_survival",
                         "breakout_hold", "invalidation", "relative_strength_persistence",
                         "volatility_state"]
FailureCategory = Literal["stale_data", "insufficient_history", "contradiction_ignored",
    "invalidation_undefined", "overconcentration", "late_thesis", "participation_missing",
    "correlation_overlooked", "other_owner_observation"]


class LearningLinks(Strict):
    instrument_ids: list[UUID] = Field(default_factory=list, max_length=5)
    candidate_id: UUID | None = None
    thesis_id: UUID | None = None
    research_run_id: UUID | None = None
    risk_snapshot_id: UUID | None = None
    prediction_id: UUID | None = None
    portfolio_id: UUID | None = None
    position_id: UUID | None = None


class JournalDraft(Strict):
    category: Literal["observation", "research_note", "thesis_note", "decision", "review",
                      "mistake", "lesson", "hypothesis", "outcome_review"]
    title: str = Field(min_length=3, max_length=180)
    notes: str = Field(default="", max_length=12000)
    structured_content: dict[str, str] = Field(default_factory=dict, max_length=20)
    tags: list[str] = Field(default_factory=list, max_length=20)
    links: LearningLinks = Field(default_factory=LearningLinks)
    manifest_id: UUID
    as_of: datetime
    classification: Classification = "OWNER_RESEARCH"
    author: Literal["owner", "cortex_template"] = "owner"
    failure_category: FailureCategory | None = None

    @field_validator("as_of")
    @classmethod
    def aware(cls, value: datetime) -> datetime:
        return utc(value)

    @field_validator("structured_content", "tags")
    @classmethod
    def bounded_text(cls, value):
        items = list(value.keys()) + list(value.values()) if isinstance(value, dict) else value
        if any(len(item) > 2000 for item in items):
            raise ValueError("JOURNAL_METADATA_TOO_LONG")
        return value

    @model_validator(mode="after")
    def failure_evidence(self):
        if self.failure_category and self.category not in ("mistake", "lesson", "outcome_review"):
            raise ValueError("FAILURE_CATEGORY_REQUIRES_LESSON_OR_REVIEW")
        return self


class JournalEntry(JournalDraft):
    schema_version: str = "journal_entry_v1"
    entry_id: UUID
    revision: int
    created_at: datetime
    recorded_at: datetime
    frozen_links: dict


class JournalRevision(Strict):
    expected_revision: int = Field(ge=1)
    reason: str = Field(min_length=8, max_length=500)
    draft: JournalDraft


class PredictionDefinition(Strict):
    title: str = Field(min_length=5, max_length=180)
    prediction_type: PredictionType
    symbol: str
    benchmark_symbol: str | None = None
    horizon_sessions: int = Field(ge=2, le=20)
    comparator: Literal["gt", "gte", "lt", "lte"]
    threshold: Decimal
    invalidation_price: Decimal | None = Field(default=None, gt=0)
    notes: str = Field(default="", max_length=4000)
    links: LearningLinks = Field(default_factory=LearningLinks)
    manifest_id: UUID
    as_of: datetime
    baseline_session: date | None = None
    registration: Registration = "PRE_REGISTERED"
    classification: Classification = "OWNER_RESEARCH"
    creation_source: Literal["owner_action", "accepted_cortex_suggestion", "thesis_milestone"] = "owner_action"

    @field_validator("as_of")
    @classmethod
    def aware(cls, value: datetime) -> datetime:
        return utc(value)

    @field_validator("symbol", "benchmark_symbol")
    @classmethod
    def symbol_supported(cls, value: str | None):
        if value is not None and value.upper() not in PILOT_SYMBOLS:
            raise ValueError("UNSUPPORTED_PILOT_SYMBOL")
        return value.upper() if value else None

    @model_validator(mode="after")
    def falsifiable(self):
        relative = self.prediction_type in ("relative_performance", "relative_strength_persistence")
        if relative != (self.benchmark_symbol is not None):
            raise ValueError("BENCHMARK_REQUIRED_ONLY_FOR_RELATIVE_METRIC")
        if self.benchmark_symbol == self.symbol:
            raise ValueError("BENCHMARK_MUST_DIFFER")
        if self.prediction_type in ("thesis_survival", "breakout_hold"):
            if self.threshold <= 0 or self.comparator not in ("gt", "gte"):
                raise ValueError("SURVIVAL_REQUIRES_POSITIVE_CLOSE_ABOVE_RULE")
        if self.prediction_type == "invalidation" and (self.threshold <= 0 or self.comparator not in ("lt", "lte")):
            raise ValueError("INVALIDATION_REQUIRES_POSITIVE_CLOSE_BELOW_RULE")
        if self.prediction_type == "volatility_state" and self.threshold < 0:
            raise ValueError("VOLATILITY_CANNOT_BE_NEGATIVE")
        if self.links.prediction_id:
            raise ValueError("PREDICTION_CANNOT_LINK_ANOTHER_PREDICTION")
        if (self.links.portfolio_id is None) != (self.links.position_id is None):
            raise ValueError("PORTFOLIO_AND_POSITION_REQUIRED_TOGETHER")
        return self


class PredictionRecord(PredictionDefinition):
    schema_version: str = "prediction_record_v1"
    prediction_id: UUID
    created_at: datetime
    baseline_session: date
    due_session: date
    due_at: datetime
    horizon_dates: list[date]
    original_context: dict
    original_context_hash: str
    evidence_strength: Literal["weak", "moderate", "strong"]
    detector_id: str
    detector_version: str
    revision: int = 1
    status: PredictionStatus = "OPEN"
    evaluation_id: UUID | None = None


class EvaluationRequest(Strict):
    manifest_id: UUID
    as_of: datetime

    @field_validator("as_of")
    @classmethod
    def aware(cls, value: datetime) -> datetime:
        return utc(value)


class PredictionEvaluation(Strict):
    schema_version: str = "prediction_evaluation_v1"
    calculation_version: str = "daily_expectation_v1"
    calculation_code_hash: str
    evaluation_id: UUID
    prediction_id: UUID
    original_context_hash: str
    source_manifest_id: UUID
    evaluation_manifest_id: UUID
    as_of: datetime
    evaluated_at: datetime
    registration: Registration
    status: PredictionStatus
    metric_value: Decimal | None
    forward_return: Decimal | None
    benchmark_return: Decimal | None
    mae_close: Decimal | None
    mfe_close: Decimal | None
    hypothetical_forward_r: Decimal | None
    expected_sessions: int
    observed_sessions: int
    observation_ids: list[UUID]
    feature_ids: list[str]
    source_quality: str
    evaluation_quality: str
    prediction_freshness: str
    warnings: list[str]


class CancelPrediction(Strict):
    reason: str = Field(min_length=8, max_length=500)


class EdgeDraft(Strict):
    title: str = Field(min_length=5, max_length=180)
    hypothesis: str = Field(min_length=10, max_length=4000)
    detector_id: str = Field(min_length=1, max_length=100)
    detector_version: str = Field(min_length=1, max_length=40)
    registration: Registration
    classification: Classification = "OWNER_RESEARCH"
    regime: str | None = None
