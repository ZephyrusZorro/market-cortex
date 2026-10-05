"""Versioned bounded research contracts; no executable code or arbitrary tool URLs."""
from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .contracts import utc
from .cortex_contracts import ResearchContext, ToolRun
from .market_state import PILOT_SYMBOLS
from .quant_contracts import BacktestDefinition

Mode = Literal['QUICK_RESEARCH','DEEP_RESEARCH','HISTORICAL_RESEARCH','STRATEGY_RESEARCH','THESIS_REVIEW','CHANGE_ANALYSIS']
Domain = Literal['market','intelligence','opportunities','quant','memory','learning','journal','portfolio','options','events','onchain','news','fundamentals']
Status = Literal['CREATED','PLANNING','READY','RUNNING','WAITING_FOR_DATA','PARTIAL','COMPLETED','INCONCLUSIVE','FAILED','CANCELLED']
FINAL = {'COMPLETED','INCONCLUSIVE','FAILED','CANCELLED'}
TRANSITIONS = {
    'CREATED': {'PLANNING','CANCELLED'}, 'PLANNING': {'READY','WAITING_FOR_DATA','FAILED','CANCELLED'},
    'READY': {'RUNNING','FAILED','CANCELLED'}, 'RUNNING': {'PARTIAL','COMPLETED','INCONCLUSIVE','WAITING_FOR_DATA','FAILED','CANCELLED'},
    'PARTIAL': {'RUNNING','CANCELLED'}, 'WAITING_FOR_DATA': {'RUNNING','CANCELLED'},
    'FAILED': {'RUNNING','CANCELLED'}, 'COMPLETED': set(), 'INCONCLUSIVE': set(), 'CANCELLED': set()}


class Strict(BaseModel):
    model_config = ConfigDict(extra='forbid', frozen=True, allow_inf_nan=False)


class MissionBudget(Strict):
    max_tool_calls: int = Field(default=16,ge=1,le=32)
    max_planner_iterations: int = Field(default=2,ge=1,le=4)
    max_replans: int = Field(default=1,ge=0,le=2)
    max_quant_runs: int = Field(default=0,ge=0,le=2)
    max_historical_comparisons: int = Field(default=3,ge=0,le=5)
    max_model_calls: int = Field(default=0,ge=0,le=2)
    timeout_seconds: int = Field(default=300,ge=1,le=900)
    api_cost_budget_inr: Literal[0] = 0


class Usage(Strict):
    tool_calls: int = 0
    planner_iterations: int = 0
    replans: int = 0
    quant_runs: int = 0
    historical_comparisons: int = 0
    model_calls: int = 0
    model_input_tokens: int | None = None
    model_output_tokens: int | None = None
    api_cost_inr: Literal[0] = 0
    elapsed_ms: float = 0
    cache_hits: int = 0


class MissionRequest(Strict):
    schema_version: Literal['mission_request_v1'] = 'mission_request_v1'
    goal: str = Field(min_length=3,max_length=600)
    mode: Mode = 'DEEP_RESEARCH'
    template: Literal['instrument_deep_dive','market_review','thesis_challenge','strategy_review','what_changed','historical','event_context'] = 'instrument_deep_dive'
    symbol: str | None = None
    compare_symbol: str | None = None
    strategy_id: Literal['momentum','breakout','trend_continuation','pullback','buy_hold','equal_weight'] = 'momentum'
    universe: Literal['binance_pilot_5'] = 'binance_pilot_5'
    horizon_days: int = Field(default=20,ge=1,le=60)
    manifest_id: UUID | None = None
    context_manifest_id: UUID | None = None
    as_of: datetime | None = None
    previous_mission_id: UUID | None = None
    older_manifest_id: UUID | None = None
    older_as_of: datetime | None = None
    thesis_id: UUID | None = None
    thesis_version: int | None = Field(default=None,ge=1)
    candidate_id: UUID | None = None
    portfolio_id: UUID | None = None
    approved_domains: list[Domain] = Field(default_factory=lambda:['market','intelligence','opportunities','quant','memory','learning'],max_length=13)
    required_domains: list[Domain] = Field(default_factory=lambda:['market'],max_length=13)
    excluded_domains: list[Domain] = Field(default_factory=lambda:['journal','portfolio'],max_length=13)
    budgets: MissionBudget | None = None
    duplicate_policy: Literal['reuse','fresh'] = 'reuse'
    experiment: BacktestDefinition | None = None
    @field_validator('as_of','older_as_of')
    @classmethod
    def aware(cls,value): return utc(value) if value else None
    @field_validator('symbol','compare_symbol')
    @classmethod
    def pilot(cls,value):
        if value and value.upper() not in PILOT_SYMBOLS: raise ValueError('UNSUPPORTED_PILOT_SYMBOL')
        return value.upper() if value else None
    @model_validator(mode='after')
    def semantics(self):
        if set(self.approved_domains)&set(self.excluded_domains) or not set(self.required_domains)<=set(self.approved_domains):
            raise ValueError('DOMAIN_POLICY_CONFLICT')
        if self.mode=='HISTORICAL_RESEARCH' and self.as_of is None: raise ValueError('HISTORICAL_CUTOFF_REQUIRED')
        if self.mode=='CHANGE_ANALYSIS' and not (self.previous_mission_id or (self.older_manifest_id and self.older_as_of)):
            raise ValueError('CHANGE_BASELINE_REQUIRED')
        if bool(self.older_manifest_id)!=bool(self.older_as_of): raise ValueError('OLDER_CONTEXT_REQUIRES_PIN_AND_CUTOFF')
        if self.mode=='THESIS_REVIEW' and not (self.thesis_id and self.thesis_version): raise ValueError('THESIS_VERSION_REQUIRED')
        if bool(self.thesis_id)!=bool(self.thesis_version): raise ValueError('THESIS_VERSION_REQUIRED')
        if 'market' not in self.approved_domains: raise ValueError('MARKET_SCOPE_REQUIRED')
        for value,domain in ((self.thesis_id,'opportunities'),(self.candidate_id,'opportunities'),(self.portfolio_id,'portfolio'),(self.experiment,'quant')):
            if value and (domain not in self.approved_domains or domain in self.excluded_domains): raise ValueError('REFERENCE_DOMAIN_NOT_APPROVED')
        if self.experiment and self.mode!='STRATEGY_RESEARCH': raise ValueError('EXPERIMENT_REQUIRES_STRATEGY_MODE')
        return self


class PlanStep(Strict):
    step_id: str = Field(pattern=r'^[a-z][a-z0-9_]{0,50}$')
    question: str = Field(max_length=200)
    tool_id: str
    arguments: dict = Field(default_factory=dict,max_length=30)
    expected_evidence: str
    reason: str
    depends_on: list[str] = Field(default_factory=list,max_length=8)
    required: bool = False
    domain: Domain
    scope: Literal['current','previous'] = 'current'
    status: Literal['PENDING','RUNNING','DONE','FAILED','SKIPPED'] = 'PENDING'
    attempts: int = Field(default=0,ge=0,le=3)
    error_code: str | None = None
    output: ToolRun | None = None


class MissionPlan(Strict):
    version: Literal['bounded_plan_v1'] = 'bounded_plan_v1'
    steps: list[PlanStep] = Field(max_length=32)
    passes: list[str] = Field(default_factory=lambda:['observation','hypothesis_tests','skeptic','alternatives','adversarial_review','grounding','synthesis'])
    rationale: str = 'Progressive deterministic scope; unsupported domains remain explicit'


class MissionClaim(Strict):
    claim_id: str
    type: Literal['FACT','CALCULATION','CLASSIFICATION','INTERPRETATION','HYPOTHESIS','LIMITATION','CONTRADICTION']
    text: str = Field(max_length=8000)
    evidence_ids: list[str] = Field(max_length=50)
    stance: Literal['support','counter','neutral','limitation'] = 'neutral'
    observed_value: float | int | str | None = None
    numeric_evidence_id: str | None = None


class Hypothesis(Strict):
    hypothesis_id: str
    statement: str
    originating_evidence: list[str]
    test_requirements: list[str]
    support: list[str] = Field(default_factory=list)
    contradictions: list[str] = Field(default_factory=list)
    status: Literal['PROPOSED','TESTING','SUPPORTED_BY_CURRENT_EVIDENCE','WEAKENED','CONTRADICTED','INCONCLUSIVE'] = 'INCONCLUSIVE'


class ExperimentProposal(Strict):
    proposal_id: str
    hypothesis: str
    definition: BacktestDefinition
    registered_at: datetime
    search_combinations: Literal[1] = 1
    selected_metrics: list[str] = Field(default_factory=lambda:['N','net_total_return','max_drawdown'])
    evaluation_plan: str = 'RETROSPECTIVE_COUNTERFACTUAL; descriptive in-sample; independent OOS remains required'
    overfitting_risks: list[str] = Field(default_factory=lambda:['DEPENDENT_TRADES','SMALL_SAMPLE','SELECTED_PILOT_UNIVERSE','NO_RULE_PROMOTION'])
    status: Literal['PROPOSED','REGISTERED','EXECUTED','UNAVAILABLE'] = 'REGISTERED'
    run_id: UUID | None = None


class ResearchMission(Strict):
    schema_version: Literal['research_mission_v1'] = 'research_mission_v1'
    orchestration_version: Literal['cortex_mission_v2'] = 'cortex_mission_v2'
    mission_id: UUID
    revision: int = 1
    created_at: datetime
    updated_at: datetime
    request: MissionRequest
    context: ResearchContext | None = None
    previous_context: ResearchContext | None = None
    budgets: MissionBudget
    usage: Usage = Field(default_factory=Usage)
    plan: MissionPlan = Field(default_factory=lambda:MissionPlan(steps=[]))
    status: Status = 'CREATED'
    termination_reason: str | None = None
    deadline_at: datetime | None = None
    claims: list[MissionClaim] = Field(default_factory=list)
    hypotheses: list[Hypothesis] = Field(default_factory=list)
    contradictions: list[MissionClaim] = Field(default_factory=list)
    limitations: list[MissionClaim] = Field(default_factory=list)
    experiments: list[ExperimentProposal] = Field(default_factory=list)
    replans: list[dict] = Field(default_factory=list)
    activity: list[dict] = Field(default_factory=list)
    evaluator: dict = Field(default_factory=dict)
    evidence_graph: dict = Field(default_factory=dict)
    report: str = ''
    model_metadata: dict = Field(default_factory=lambda:{'provider':'deterministic','status':'no_model_configured','paid_api_cost_inr':0})
    similar_mission_ids: list[UUID] = Field(default_factory=list)
    frozen_references: dict = Field(default_factory=dict)
    code_hash: str
    content_hash: str = ''
