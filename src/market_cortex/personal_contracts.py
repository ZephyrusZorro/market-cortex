"""Local research behavior only; typed provenance, corrections and workflow proposals."""
from datetime import datetime
from typing import Literal
from uuid import UUID
from pydantic import Field, field_validator, model_validator
from .contracts import utc
from .mission_contracts import Strict, MissionRequest

Audience = Literal['OWNER_RESEARCH','SYNTHETIC_VALIDATION']
MemoryType = Literal['WORKING','EPISODIC','SEMANTIC','PROCEDURAL','MARKET','STRATEGY','FAILURE','PREDICTION']
SourceKind = Literal['journal','prediction','thesis','risk','mission','research','quant','preference','feedback','proposal']
PreferenceKey = Literal['default_horizon','preferred_instrument','default_mode','preferred_view','review_emphasis']


class ProfileQuery(Strict):
    as_of: datetime | None = None
    audience: Audience = 'OWNER_RESEARCH'
    @field_validator('as_of')
    @classmethod
    def aware(cls,v): return utc(v) if v else None


class PersonalEvidence(Strict):
    evidence_id: str
    source_kind: SourceKind
    source_id: UUID
    source_version: int = Field(ge=1)
    recorded_at: datetime
    source_as_of: datetime
    classification: Literal['OWNER_RESEARCH','SYNTHETIC_VALIDATION','STRATEGY_EVIDENCE']
    content_hash: str
    subject: Literal['OWNER_PROCESS','CORTEX_PROCESS','STRATEGY_EVIDENCE']
    symbol: str | None = None
    strategy: str | None = None
    facts: dict = Field(default_factory=dict)
    @field_validator('recorded_at','source_as_of')
    @classmethod
    def aware(cls,v): return utc(v)


class PersonalMemory(Strict):
    memory_id: UUID
    version: int = 1
    key: str
    memory_type: MemoryType
    source_type: Literal['EXPLICIT','OBSERVED','LEARNED_FROM_OUTCOMES','CORTEX_PROPOSED']
    audience: Audience
    status: Literal['ACTIVE','TENTATIVE','SUPERSEDED','REJECTED','EXPIRED','OWNER_CONFIRMED','DISABLED'] = 'TENTATIVE'
    statement: str = Field(max_length=600)
    value: str | int | None = None
    evidence_ids: list[str] = Field(default_factory=list,max_length=500)
    sample_N: int = Field(ge=0)
    sufficiency: Literal['INSUFFICIENT_HISTORY','EARLY_PATTERN','REPEATED_PATTERN','STRONG_PATTERN']
    subject: Literal['OWNER_PROCESS','CORTEX_PROCESS','STRATEGY_EVIDENCE']
    created_at: datetime
    last_validated: datetime
    expires_at: datetime | None = None
    owner_override: str | None = None
    algorithm_version: str = 'personal_patterns_v1'
    persisted: bool = False


class PreferenceInput(Strict):
    audience: Audience = 'OWNER_RESEARCH'
    key: PreferenceKey
    value: str | int
    @model_validator(mode='after')
    def valid_value(self):
        allowed = {'preferred_instrument':{'BTCUSDT','ETHUSDT','SOLUSDT','BNBUSDT','XRPUSDT'},
                   'default_mode':{'QUICK_RESEARCH','DEEP_RESEARCH','STRATEGY_RESEARCH'},
                   'preferred_view':{'research-lab','my-research','quant','intelligence'},
                   'review_emphasis':{'quant','intelligence','contradictions','historical'}}
        if self.key=='default_horizon':
            if type(self.value) is not int or not 1<=self.value<=60: raise ValueError('INVALID_PREFERENCE_VALUE')
        elif self.value not in allowed[self.key]: raise ValueError('INVALID_PREFERENCE_VALUE')
        return self


class MemoryAction(Strict):
    expected_version: int = Field(ge=1)
    action: Literal['confirm','reject','correct','disable','retire']
    correction: PreferenceInput | None = None
    statement: str | None = Field(default=None,min_length=3,max_length=600)
    @model_validator(mode='after')
    def correction_required(self):
        if (self.action=='correct')!=(self.correction is not None or self.statement is not None): raise ValueError('CORRECTION_REQUIRED_ONLY_FOR_CORRECT')
        if self.correction and self.statement: raise ValueError('ONE_CORRECTION_REQUIRED')
        return self


class AdaptationProposal(Strict):
    proposal_id: UUID
    version: int = 1
    audience: Audience
    key: PreferenceKey
    value: str | int
    status: Literal['PROPOSED','OWNER_ACCEPTED','OWNER_REJECTED','ACTIVE','RETIRED'] = 'PROPOSED'
    evidence_ids: list[str]
    memory_ids: list[UUID]
    rationale: str
    expected_benefit: str
    affected_workflow: str
    risk: Literal['LOW_PRESENTATION','WORKFLOW_APPROVAL_REQUIRED']
    created_at: datetime
    recorded_at: datetime


class ProposalAction(Strict):
    expected_version: int = Field(ge=1)
    action: Literal['accept','reject','retire']


class FeedbackInput(Strict):
    audience: Audience = 'OWNER_RESEARCH'
    target_kind: Literal['MEMORY','PROPOSAL','MISSION','COACHING']
    target_id: UUID
    rating: Literal['USEFUL','IRRELEVANT','INCORRECT','NEEDS_EVIDENCE']


class AttestationInput(Strict):
    source_kind: Literal['mission','research','thesis','risk']
    source_id: UUID
    source_version: int = Field(ge=1)
    audience: Audience = 'OWNER_RESEARCH'


class PersonalizationSnapshot(Strict):
    schema_version: str = 'personalization_snapshot_v1'
    snapshot_id: UUID
    audience: Audience
    as_of: datetime
    algorithm_version: str = 'personal_patterns_v1'
    implementation_hash: str
    privacy: Literal['LOCAL_ONLY'] = 'LOCAL_ONLY'
    reconstruction_kind: Literal['CURRENT_PROFILE','RETROSPECTIVE_RECONSTRUCTION'] = 'CURRENT_PROFILE'
    evidence: list[PersonalEvidence]
    memories: list[PersonalMemory]
    proposals: list[AdaptationProposal]
    observed_behavior: dict
    baseline: dict
    patterns: list[dict]
    coaching: list[dict]
    strategy_evidence: list[dict]
    review_queue: list[dict]
    study_items: list[dict]
    limitations: list[str]
    content_hash: str = ''


class PersonalizedMissionInput(Strict):
    request: MissionRequest
    snapshot_id: UUID | None = None
    use_explicit_preferences: bool = False


class PersonalQuestion(ProfileQuery):
    question: str = Field(min_length=3,max_length=300)
    symbol: str | None = None
    strategy: str | None = None
