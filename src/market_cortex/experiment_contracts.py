"""Frozen, bounded research contracts. Models and code are registry names only."""
from datetime import date, datetime, timezone
from typing import Literal
from uuid import UUID

from pydantic import Field, field_validator, model_validator
from .quant_contracts import Strict, CostModel
from .market_state import PILOT_SYMBOLS

FEATURES = ('momentum_5', 'momentum_20', 'trend_persistence', 'volatility_20',
            'relative_strength', 'volume_ratio', 'drawdown_60', 'dispersion',
            'correlation_btc', 'funding', 'open_interest_change', 'macro_rate')
MODELS = ('mean', 'momentum', 'ridge', 'logistic', 'ensemble')


class ResearchHypothesis(Strict):
    schema_version: Literal['research_hypothesis_v1'] = 'research_hypothesis_v1'
    question: str = Field(min_length=10, max_length=600)
    rationale: str = Field(min_length=10, max_length=1200)
    relationship: str = Field(min_length=10, max_length=600)
    falsification: str = Field(min_length=10, max_length=600)
    concerns: list[str] = Field(default_factory=lambda: ['Selected survivors', 'Dependent overlapping returns'], max_length=12)
    target: Literal['return', 'excess_return', 'volatility', 'mae', 'mfe', 'direction'] = 'return'
    features: list[str] = Field(default_factory=lambda: list(FEATURES[:6]), min_length=1, max_length=12)
    symbols: list[str] = Field(default_factory=lambda: list(PILOT_SYMBOLS), min_length=1, max_length=5)
    benchmark: Literal['BTCUSDT'] = Field(default='BTCUSDT', description='Registered cross-asset reference; forecast-error baseline is the training mean')
    registration: Literal['EXPLORATORY', 'PREREGISTERED'] = 'EXPLORATORY'
    minimum_oos_rows: int = Field(default=100, ge=30, le=10000)
    minimum_improvement: float = Field(default=0.02, ge=0, le=1)
    version: Literal['1.0.0'] = '1.0.0'

    @field_validator('features', 'symbols')
    @classmethod
    def registry(cls, values, info):
        allowed = FEATURES if info.field_name == 'features' else PILOT_SYMBOLS
        if len(set(values)) != len(values) or any(v not in allowed for v in values):
            raise ValueError('UNREGISTERED_OR_DUPLICATE_INPUT')
        return values


class ExperimentDataset(Strict):
    manifest_id: UUID
    source_as_of: datetime
    start: date
    end: date
    horizon_sessions: int = Field(default=5, ge=1, le=30)
    replay_policy: Literal['AS_RECORDED', 'HISTORICAL_RECONSTRUCTION'] = 'HISTORICAL_RECONSTRUCTION'
    adjustment_basis: Literal['raw'] = 'raw'
    interval: Literal['P1D'] = 'P1D'
    source_classification: Literal['LIVE_SOURCE', 'SYNTHETIC_TEST'] = 'LIVE_SOURCE'
    universe: Literal['BINANCE_PILOT_5_SELECTED_SURVIVORS'] = 'BINANCE_PILOT_5_SELECTED_SURVIVORS'
    publication_lag_seconds: int = Field(default=60, ge=1, le=86400)

    @field_validator('source_as_of')
    @classmethod
    def aware(cls, at):
        if at.tzinfo is None: raise ValueError('AWARE_CUTOFF_REQUIRED')
        return at.astimezone(timezone.utc)

    @model_validator(mode='after')
    def bounded(self):
        if self.end < self.start or (self.end-self.start).days > 1500 or self.end >= self.source_as_of.date():
            raise ValueError('INVALID_EXPERIMENT_WINDOW')
        return self


class FeatureSelectionDefinition(Strict):
    version: Literal['train_only_rank_v1'] = 'train_only_rank_v1'
    top_k: int = Field(default=12, ge=1, le=12)


class ValidationProtocol(Strict):
    version: Literal['purged_temporal_v1'] = 'purged_temporal_v1'
    mode: Literal['rolling', 'expanding'] = 'expanding'
    train_sessions: int = Field(default=240, ge=60, le=1000)
    test_sessions: int = Field(default=90, ge=10, le=180)
    max_folds: int = Field(default=4, ge=1, le=6)
    embargo_sessions: int = Field(default=5, ge=0, le=30)
    inner_validation_sessions: int = Field(default=30, ge=10, le=90)
    calibration_sessions: int = Field(default=30, ge=10, le=90)
    minimum_train_rows: int = Field(default=80, ge=20, le=10000)
    feature_selection: FeatureSelectionDefinition = Field(default_factory=FeatureSelectionDefinition)


class ModelDefinition(Strict):
    registry_id: Literal['mean', 'momentum', 'ridge', 'logistic', 'ensemble'] = 'ridge'
    version: Literal['numpy_cpu_v1'] = 'numpy_cpu_v1'
    alphas: list[float] = Field(default_factory=lambda: [0.1, 10.0], min_length=1, max_length=4)
    max_iterations: int = Field(default=60, ge=10, le=100)
    @field_validator('alphas')
    @classmethod
    def alphas_safe(cls, values):
        if len(set(values)) != len(values) or any(not 0.0001 <= x <= 10000 for x in values):
            raise ValueError('INVALID_REGULARIZATION_GRID')
        return sorted(values)


class ExperimentConfiguration(Strict):
    seed: int = Field(default=1208, ge=0, le=2**31-1)
    timeout_seconds: int = Field(default=180, ge=10, le=300)
    max_rows: int = Field(default=10000, ge=100, le=15000)
    max_artifact_bytes: int = Field(default=12_000_000, ge=100_000, le=16_000_000)
    bootstrap_paths: int = Field(default=200, ge=20, le=1000)
    costs: CostModel = Field(default_factory=CostModel)


class ExperimentDefinition(Strict):
    schema_version: Literal['experiment_definition_v1'] = 'experiment_definition_v1'
    hypothesis_id: UUID
    dataset: ExperimentDataset
    validation: ValidationProtocol = Field(default_factory=ValidationProtocol)
    model: ModelDefinition = Field(default_factory=ModelDefinition)
    configuration: ExperimentConfiguration = Field(default_factory=ExperimentConfiguration)
    experiment_version: Literal['1.0.0'] = '1.0.0'
    quant_run_ids: list[UUID] = Field(default_factory=list, max_length=4)
    quant_study_ids: list[UUID] = Field(default_factory=list, max_length=4)
    metrics: tuple[str, ...] = ('mae', 'rmse', 'directional_accuracy', 'baseline_skill')
    @model_validator(mode='after')
    def fixed_metrics(self):
        if self.metrics != ('mae', 'rmse', 'directional_accuracy', 'baseline_skill'):
            raise ValueError('FIXED_METRICS_REQUIRED')
        if self.validation.train_sessions < self.validation.inner_validation_sessions + self.validation.calibration_sessions + 20:
            raise ValueError('TRAINING_WINDOW_TOO_SHORT')
        return self


class ModelArtifact(Strict):
    format: Literal['restricted_json_v1'] = 'restricted_json_v1'
    registry_id: Literal['mean', 'momentum', 'ridge', 'logistic', 'ensemble']
    version: Literal['numpy_cpu_v1'] = 'numpy_cpu_v1'
    features: list[str] = Field(max_length=12)
    means: list[float] = Field(max_length=12)
    scales: list[float] = Field(max_length=12)
    coefficients: list[float] = Field(max_length=12)
    intercept: float
    alpha: float
    training_cutoff: datetime
    training_rows: int = Field(ge=1)
    task: Literal['regression', 'classification']
    calibration: tuple[float, float] | None = None
    calibration_rows: int = Field(default=0, ge=0)
    @model_validator(mode='after')
    def shapes(self):
        if not len(self.features) == len(self.means) == len(self.scales) == len(self.coefficients):
            raise ValueError('MODEL_SHAPE_MISMATCH')
        if any(x <= 0 for x in self.scales) or any(x not in FEATURES for x in self.features):
            raise ValueError('UNSAFE_MODEL_ARTIFACT')
        if self.training_cutoff.tzinfo is None: raise ValueError('AWARE_CUTOFF_REQUIRED')
        return self


class ExperimentComparison(Strict):
    experiment_ids: list[UUID] = Field(min_length=2, max_length=8)
    @field_validator('experiment_ids')
    @classmethod
    def unique(cls, values):
        if len(set(values)) != len(values): raise ValueError('DISTINCT_EXPERIMENTS_REQUIRED')
        return values


class AnalogueRequest(Strict):
    experiment_id: UUID
    reference_date: date
    symbol: str = Field(default='BTCUSDT', pattern='^(BTCUSDT|ETHUSDT|SOLUSDT|BNBUSDT|XRPUSDT)$')
    limit: int = Field(default=5, ge=1, le=20)
    minimum_separation_sessions: int = Field(default=10, ge=1, le=90)


class ExperimentProposal(Strict):
    parent_experiment_id: UUID
    definition: ExperimentDefinition
    reason: str = Field(min_length=10, max_length=1000)


class PromotionDecision(Strict):
    experiment_id: UUID
    expected_revision: int = Field(default=0, ge=0)
    decision: Literal['EXPERIMENTAL', 'CANDIDATE_FOR_REVIEW', 'REJECTED', 'HUMAN_APPROVED_RESEARCH_BASELINE', 'ARCHIVED']
    reason: str = Field(min_length=10, max_length=1000)
    owner_confirmed: bool = False


class ExperimentEdgeInput(Strict):
    experiment_id: UUID
    edge_id: UUID
    stance: Literal['SUPPORTING', 'COUNTER', 'INCONCLUSIVE']
    reason: str = Field(min_length=10, max_length=1000)


class ExperimentMissionInput(Strict):
    experiment_id: UUID
    authorize_run: bool = False
    max_tool_calls: int = Field(default=8, ge=4, le=12)
    personalization_snapshot_id: UUID | None = None


class ExperimentQuestion(Strict):
    experiment_id: UUID
    question: str = Field(min_length=5, max_length=1000)


class ExperimentManifest(Strict):
    definition_hash: str
    hypothesis_hash: str
    source_hash: str
    dataset_hash: str
    code_hash: str
    dependencies: dict[str, str]
    holdout_status: Literal['PREVIOUSLY_EXAMINED', 'EXPLORATORY_FIRST_EXPOSURE']
    context_policy: Literal['AS_RECORDED_ONLY'] = 'AS_RECORDED_ONLY'


class ExperimentResult(Strict):
    status: Literal['COMPLETED', 'INCONCLUSIVE']
    conclusion: Literal['HYPOTHESIS_FALSIFIED', 'INSUFFICIENT_EVIDENCE', 'EXPLORATORY_IMPROVEMENT']
    reports: dict
    warnings: list[str]


class ExperimentRun(Strict):
    experiment_id: UUID
    manifest: ExperimentManifest
    result: ExperimentResult
    result_hash: str


class RobustnessAssessment(Strict):
    classification: Literal['FRAGILE', 'MIXED', 'INSUFFICIENT_EVIDENCE']
    rows: list[dict]
    minimum_cell_N: int
