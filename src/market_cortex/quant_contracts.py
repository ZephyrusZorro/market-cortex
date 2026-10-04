"""Reviewed daily crypto research contracts. No arbitrary code or order routing."""
from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .contracts import utc
from .market_state import PILOT_SYMBOLS


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False, frozen=True,validate_default=True)


class ExecutionPolicy(Strict):
    version: Literal["daily_execution_v1"] = "daily_execution_v1"
    timing: Literal["next_open", "next_close"] = "next_open"
    delay_sessions: int = Field(default=0, ge=0, le=5)
    ambiguity: Literal["stop_first", "target_first"] = "stop_first"


class CostModel(Strict):
    version: Literal["bps_proxy_v1"] = "bps_proxy_v1"
    entry_fee_bps: float = Field(default=10, ge=0, le=500)
    exit_fee_bps: float = Field(default=10, ge=0, le=500)
    slippage_bps: float = Field(default=5, ge=0, le=500)
    spread_bps: float = Field(default=0, ge=0, le=500)
    fixed_fee: float = Field(default=0, ge=0, le=100)


class StrategyParameters(Strict):
    holding_sessions: int = Field(default=10, ge=1, le=60)
    stop_fraction: float = Field(default=.08, gt=0, le=.5)
    target_r: float = Field(default=2, gt=0, le=10)


class SizingPolicy(Strict):
    version: Literal["cash_capped_v1"] = "cash_capped_v1"
    mode: Literal["equal_weight", "fixed_notional", "fixed_quantity", "fractional_risk"] = "equal_weight"
    value: float = Field(default=.01, gt=0)
    @model_validator(mode="after")
    def bounded(self):
        if self.mode == "fractional_risk" and self.value > .1:
            raise ValueError("RISK_FRACTION_MAX_10_PERCENT")
        return self


class StrategyDefinition(Strict):
    strategy_id: str
    version: str = "1.0.0"
    detector_id: str | None
    detector_version: str | None = "1.0.0"
    description: str
    entry_policy: str = "valid_only_v1"
    exit_policy: str = "fixed_stop_target_time_v1"
    required_features: list[str] = Field(default_factory=list)
    minimum_history: int = 55
    universe: str = "binance_pilot_5_selected_survivors"
    interval: str = "P1D"
    parameter_schema: dict = Field(default_factory=lambda: StrategyParameters.model_json_schema())


class BacktestDefinition(Strict):
    schema_version: Literal["backtest_v1"] = "backtest_v1"
    strategy_id: Literal["momentum", "breakout", "trend_continuation", "pullback", "buy_hold", "equal_weight"]
    strategy_version: Literal["1.0.0"] = "1.0.0"
    manifest_id: UUID
    source_as_of: datetime
    start: date
    end: date
    symbols: list[str] = Field(default_factory=lambda: list(PILOT_SYMBOLS), min_length=1, max_length=5)
    replay_policy: Literal["AS_RECORDED", "HISTORICAL_RECONSTRUCTION"] = "AS_RECORDED"
    publication_lag_seconds: int = Field(default=60, ge=1, le=86400)
    interval: Literal["P1D"] = "P1D"
    adjustment_basis: Literal["raw"] = "raw"
    universe: Literal["binance_pilot_5_selected_survivors"] = "binance_pilot_5_selected_survivors"
    capital: float = Field(default=10000, gt=0, le=1e12)
    max_positions: int = Field(default=5, ge=1, le=5)
    parameters: StrategyParameters = Field(default_factory=StrategyParameters)
    execution: ExecutionPolicy = Field(default_factory=ExecutionPolicy)
    costs: CostModel = Field(default_factory=CostModel)
    sizing: SizingPolicy = Field(default_factory=SizingPolicy)
    benchmark: Literal["BTCUSDT", "same_universe_equal_weight", "cash"] = "same_universe_equal_weight"
    annualization: Literal[365] = 365
    risk_free_rate: float = Field(default=0, ge=-.1, le=.5)
    classification: Literal["OWNER_RESEARCH", "SYNTHETIC_TEST"] = "OWNER_RESEARCH"
    @field_validator("source_as_of")
    @classmethod
    def aware(cls, value):
        return utc(value)
    @model_validator(mode="after")
    def valid(self):
        if self.start >= self.end or (self.end-self.start).days > 3000:
            raise ValueError("INVALID_BACKTEST_RANGE")
        if self.end >= self.source_as_of.date():
            raise ValueError("BACKTEST_REQUIRES_COMPLETED_DAILY_SESSIONS")
        if len(set(self.symbols)) != len(self.symbols) or any(s not in PILOT_SYMBOLS for s in self.symbols):
            raise ValueError("INVALID_PILOT_UNIVERSE")
        if self.strategy_id == "buy_hold" and len(self.symbols) != 1:
            raise ValueError("BUY_HOLD_REQUIRES_ONE_SYMBOL")
        if self.strategy_id in ("buy_hold","equal_weight"):
            if self.sizing.mode=="fractional_risk":
                raise ValueError("BASELINE_HAS_NO_STOP_FOR_FRACTIONAL_RISK")
            if self.max_positions<len(self.symbols):
                raise ValueError("BASELINE_REQUIRES_SLOTS_FOR_SELECTED_UNIVERSE")
        return self


class Decision(Strict):
    symbol: str
    session: date
    cutoff: datetime
    candidate: dict | None = None
    state: dict | None = None
    outcome: str
    status: str
    enter: bool
    reason: str
    observation_ids: list[str]
    evidence_hash: str


class SimulatedTrade(Strict):
    trade_id: UUID
    symbol: str
    signal_session: date
    signal_at: datetime
    decision_hash: str
    entry_session: date
    entry_at: datetime
    exit_session: date
    exit_at: datetime
    exit_time_basis: str = "DAILY_BOUNDARY_PROXY; STOP_TARGET_TIME_IS_SESSION_UPPER_BOUND"
    excursion_basis: str = "WHOLE_DAILY_BAR_BOUNDS; MAY_INCLUDE_POST_EXIT_EXTREMA"
    quantity: float
    entry_reference: float
    exit_reference: float
    entry_price: float
    exit_price: float
    entry_fee: float
    exit_fee: float
    friction: float
    gross_pnl: float
    net_pnl: float
    return_fraction: float
    r_multiple: float | None
    holding_sessions: int
    exit_reason: str
    ambiguous: bool
    mae: float
    mfe: float
    regime: str
    source_observation_ids: list[str]


class EquityPoint(Strict):
    session: date
    cash: float
    position_value: float
    net: float
    gross: float
    benchmark: float
    realized_pnl: float
    unrealized_pnl: float
    exposure: float
    heat: float | None
    concurrent_positions: int
    turnover_notional: float
    drawdown: float = 0


class BacktestManifest(Strict):
    schema_version: str = "backtest_manifest_v1"
    source_hash: str
    manifest_id: UUID
    source_as_of: datetime
    engine_version: str
    code_hash: str
    detector_code_hash: str
    feature_code_hash: str
    calendar_versions: dict[str, str]
    environment: dict[str, str]
    definition_hash: str
    input_hash: str


class BacktestRun(Strict):
    run_id: UUID
    status: Literal["completed"] = "completed"
    created_at: datetime
    definition: BacktestDefinition
    manifest: BacktestManifest
    decisions: list[Decision]
    trades: list[SimulatedTrade]
    equity: list[EquityPoint]
    metrics: dict[str, float | int | str | None]
    drawdown: dict
    regime_performance: list[dict]
    controls: dict
    warnings: list[str]
    result_hash: str
    elapsed_ms: float


class GridRequest(Strict):
    definition: BacktestDefinition
    holding_sessions: list[int] = Field(default_factory=lambda: [5,10,15], min_length=1, max_length=6)
    stop_fraction: list[float] = Field(default_factory=lambda: [.06,.08,.10], min_length=1, max_length=6)
    @model_validator(mode="after")
    def grid(self):
        if len(self.holding_sessions)*len(self.stop_fraction)>24:
            raise ValueError("GRID_LIMIT_24_COMBINATIONS")
        if len(set(self.holding_sessions))!=len(self.holding_sessions) or len(set(self.stop_fraction))!=len(self.stop_fraction):
            raise ValueError("DUPLICATE_GRID_VALUE")
        for hold in self.holding_sessions:
            for stop in self.stop_fraction:
                StrategyParameters(holding_sessions=hold,stop_fraction=stop)
        return self


class WalkForwardDefinition(GridRequest):
    mode: Literal["rolling", "expanding"] = "rolling"
    train_sessions: int = Field(default=120, ge=60, le=1000)
    validation_sessions: int = Field(default=60, ge=10, le=365)
    step_sessions: int = Field(default=60, ge=10, le=365)
    max_folds: int = Field(default=6, ge=1, le=12)
    objective: Literal["net_total_return"] = "net_total_return"
    @model_validator(mode="after")
    def nonoverlap(self):
        if self.step_sessions < self.validation_sessions:
            raise ValueError("OVERLAPPING_OOS_FOLDS_FORBIDDEN")
        if len(self.holding_sessions)*len(self.stop_fraction)*self.max_folds>144:
            raise ValueError("WALK_FORWARD_SEARCH_LIMIT")
        return self


class MonteCarloRequest(Strict):
    run_id: UUID
    seed: int = Field(default=42, ge=0, le=2**32-1)
    simulations: int = Field(default=500, ge=10, le=10000)
    method: Literal["bootstrap", "permutation"] = "bootstrap"


class CompareRequest(Strict):
    run_ids: list[UUID] = Field(min_length=2, max_length=12)
    @field_validator("run_ids")
    @classmethod
    def distinct(cls,values):
        if len(set(values))!=len(values):
            raise ValueError("DUPLICATE_RUN_IDS")
        return values


class EdgeEvidenceRequest(Strict):
    edge_id: UUID
    run_ids: list[UUID] = Field(min_length=1, max_length=12)
    study_ids: list[UUID] = Field(default_factory=list, max_length=12)
    status: Literal["HYPOTHESIS", "EARLY_EVIDENCE", "SUPPORTED", "WEAKENED", "REJECTED"] = "HYPOTHESIS"
    expected_revision: int = Field(default=0, ge=0)
    reason: str = Field(min_length=12, max_length=1000)
    @field_validator("run_ids","study_ids")
    @classmethod
    def distinct(cls,values):
        if len(set(values))!=len(values):
            raise ValueError("DUPLICATE_EVIDENCE_IDS")
        return values
