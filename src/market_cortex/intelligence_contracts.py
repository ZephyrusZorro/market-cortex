"""Phase 9 source facts; source text is data and never an executable instruction."""
from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, model_validator, field_validator

from .contracts import ObservationEnvelope, utc

Domain = Literal['macro', 'fundamentals', 'events', 'news', 'derivatives', 'options', 'onchain']
Number = Annotated[Decimal, Field(allow_inf_nan=False)]


class Strict(BaseModel):
    model_config = ConfigDict(extra='forbid', frozen=True, allow_inf_nan=False)


class EntityRef(Strict):
    kind: Literal['instrument', 'issuer', 'region', 'series']
    key: str = Field(min_length=1, max_length=160)
    mapping_version: str = Field(min_length=1, max_length=100)
    @model_validator(mode='after')
    def identity(self):
        if self.kind == 'instrument':
            UUID(self.key)
        return self


class Fact(Strict):
    schema_version: Literal['context_fact_v1'] = 'context_fact_v1'
    envelope: ObservationEnvelope
    entity: EntityRef
    related_instrument_ids: list[UUID] = Field(default_factory=list, max_length=50)
    logical_key: str = Field(min_length=1, max_length=240)
    classification: Literal['SOURCE_FACT', 'EXTRACTED'] = 'SOURCE_FACT'
    extraction_model: str | None = None
    extraction_version: str | None = None
    validation_state: Literal['validated', 'unvalidated'] = 'validated'
    classification_scope: Literal['LIVE_SOURCE', 'SYNTHETIC_TEST'] = 'LIVE_SOURCE'
    revision_number: int = Field(default=1, ge=1)
    period_start: date | None = None
    period_end: date | None = None
    effective_at: datetime | None = None
    revised_at: datetime | None = None
    @field_validator('effective_at', 'revised_at')
    @classmethod
    def aware(cls, value):
        return utc(value) if value else None
    @model_validator(mode='after')
    def semantics(self):
        e = self.envelope
        import re
        if not re.fullmatch(r'[0-9a-f]{64}', e.raw_content_hash):
            raise ValueError('RAW_SOURCE_SHA256_REQUIRED')
        from urllib.parse import urlsplit
        ref = urlsplit(e.source_ref)
        if ref.scheme and ref.scheme not in ('https', 'urn'):
            raise ValueError('UNSAFE_SOURCE_REFERENCE')
        if ref.scheme == 'https':
            import ipaddress
            if not ref.hostname or ref.username or ref.password or ref.port not in (None, 443):
                raise ValueError('UNSAFE_SOURCE_REFERENCE')
            try:
                ipaddress.ip_address(ref.hostname)
            except ValueError:
                if ref.hostname.lower() == 'localhost' or '.' not in ref.hostname:
                    raise ValueError('UNSAFE_SOURCE_REFERENCE')
            else:
                raise ValueError('IP_SOURCE_REFERENCE_FORBIDDEN')
        if self.period_start and self.period_end and self.period_start > self.period_end:
            raise ValueError('INVALID_REPORTING_PERIOD')
        if e.published_at and e.available_at and e.available_at < e.published_at:
            raise ValueError('AVAILABILITY_BEFORE_PUBLICATION')
        if self.classification == 'EXTRACTED' and not (self.extraction_model and self.extraction_version):
            raise ValueError('EXTRACTION_PROVENANCE_REQUIRED')
        if self.entity.kind == 'instrument' and str(e.instrument_id) != self.entity.key:
            raise ValueError('ENTITY_ENVELOPE_MISMATCH')
        if self.revision_number > 1 and not e.supersedes_observation_id:
            raise ValueError('REVISION_PARENT_REQUIRED')
        return self


class EconomicObservation(Fact):
    domain: Literal['macro'] = 'macro'
    kind: Literal['economic_observation'] = 'economic_observation'
    series_id: str
    metric: str
    value: Number
    region: str
    frequency: Literal['daily', 'monthly', 'quarterly', 'annual', 'irregular']
    seasonal_adjustment: Literal['adjusted', 'unadjusted', 'not_applicable', 'unknown']
    initial_published_at: datetime | None = None
    @field_validator('initial_published_at')
    @classmethod
    def aware(cls, value):
        return utc(value) if value else None
    @model_validator(mode='after')
    def period(self):
        if not self.period_start or not self.period_end:
            raise ValueError('MACRO_PERIOD_REQUIRED')
        if self.envelope.available_at and self.period_end > self.envelope.available_at.date():
            raise ValueError('UNRELEASED_MACRO_PERIOD')
        if self.initial_published_at:
            utc(self.initial_published_at)
        return self


class FundamentalFact(Fact):
    domain: Literal['fundamentals'] = 'fundamentals'
    kind: Literal['fundamental_fact'] = 'fundamental_fact'
    issuer_id: str
    metric: str
    value: Number
    fiscal_period: str
    currency: str
    @model_validator(mode='after')
    def period(self):
        if not self.period_start or not self.period_end or self.entity.kind != 'issuer' or self.entity.key != self.issuer_id:
            raise ValueError('FUNDAMENTAL_PERIOD_ISSUER_REQUIRED')
        if self.envelope.currency != self.currency:
            raise ValueError('FUNDAMENTAL_CURRENCY_MISMATCH')
        if self.envelope.available_at and self.period_end > self.envelope.available_at.date():
            raise ValueError('UNRELEASED_FUNDAMENTAL_PERIOD')
        return self


class FundamentalStatement(Strict):
    schema_version: Literal['fundamental_statement_v1'] = 'fundamental_statement_v1'
    issuer_id: str
    facts: list[FundamentalFact]
    @model_validator(mode='after')
    def issuer(self):
        if any(f.issuer_id != self.issuer_id for f in self.facts):
            raise ValueError('MIXED_ISSUER_STATEMENT')
        return self


class EventFact(Fact):
    domain: Literal['events'] = 'events'
    kind: Literal['economic_event', 'corporate_event']
    category: Literal['central_bank', 'inflation', 'employment', 'gdp', 'earnings', 'dividend', 'split', 'symbol_change', 'announcement']
    scheduled_at: datetime
    actual_release_at: datetime | None = None
    region: str | None = None
    importance: Literal['high', 'medium', 'low', 'unknown'] = 'unknown'
    importance_source: str | None = None
    calendar_complete_until: datetime | None = None
    actual: Number | None = None
    prior: Number | None = None
    revised_prior: Number | None = None
    consensus: Number | None = None
    consensus_source: str | None = None
    corporate_action_ref: str | None = None
    @field_validator('scheduled_at', 'actual_release_at', 'calendar_complete_until')
    @classmethod
    def aware(cls, value):
        return utc(value) if value else None
    @model_validator(mode='after')
    def sourced(self):
        if self.importance != 'unknown' and not self.importance_source:
            raise ValueError('IMPORTANCE_SOURCE_REQUIRED')
        if self.consensus is not None and not self.consensus_source:
            raise ValueError('CONSENSUS_SOURCE_REQUIRED')
        if self.actual is not None and (not self.actual_release_at or not self.envelope.available_at or self.actual_release_at > self.envelope.available_at):
            raise ValueError('UNRELEASED_ACTUAL')
        return self


class NewsEvent(Fact):
    domain: Literal['news'] = 'news'
    kind: Literal['news_event'] = 'news_event'
    title: str = Field(min_length=1, max_length=500)
    category: str = Field(max_length=60)
    language: str = Field(default='en', max_length=12)
    duplicate_group_id: str | None = None
    syndication_id: str | None = None
    assertion_key: str | None = Field(default=None, max_length=120)
    assertion_value: str | None = Field(default=None, max_length=300)
    confidence_category: Literal['source_reported', 'unverified_extraction', 'validated_extraction', 'unknown'] = 'unknown'
    # No article body and no executable URLs in tool arguments.


class DerivativeContract(Strict):
    schema_version: Literal['derivative_contract_v1'] = 'derivative_contract_v1'
    instrument_id: UUID
    underlying_instrument_id: UUID
    provider: str
    venue: str
    native_id: str
    contract_type: Literal['PERPETUAL', 'DELIVERY']
    base_asset: str
    quote_currency: str
    margin_currency: str
    quantity_unit: str
    identity_version: str
    known_at: datetime
    metadata_source_ref: str | None = None
    metadata_raw_hash: str | None = Field(default=None, pattern=r'^[0-9a-f]{64}$')
    metadata_observed_at: datetime | None = None
    @field_validator('known_at', 'metadata_observed_at')
    @classmethod
    def aware(cls, value):
        return utc(value) if value else None


class DerivativeObservation(Fact):
    domain: Literal['derivatives'] = 'derivatives'
    kind: Literal['funding', 'open_interest', 'mark_index', 'liquidation']
    contract: DerivativeContract
    metric: str
    value: Number
    companion_value: Number | None = None
    companion_unit: str | None = None
    mark_price: Number | None = None
    interval: str | None = None
    @model_validator(mode='after')
    def units(self):
        if self.envelope.instrument_id != self.contract.instrument_id or self.entity.key != str(self.contract.instrument_id):
            raise ValueError('DERIVATIVE_IDENTITY_MISMATCH')
        if self.contract.known_at > self.envelope.ingested_at:
            raise ValueError('UNKNOWN_CONTRACT_AT_INGESTION')
        if self.kind == 'funding' and (abs(self.value) > 1 or self.envelope.unit != 'fraction_per_funding_event'):
            raise ValueError('INVALID_FUNDING_UNIT_RANGE')
        if self.kind == 'open_interest' and (self.value < 0 or self.envelope.unit != self.contract.quantity_unit):
            raise ValueError('INVALID_OI_UNIT_RANGE')
        if self.companion_value is not None and not self.companion_unit:
            raise ValueError('COMPANION_UNIT_REQUIRED')
        if self.kind in ('mark_index', 'liquidation') and self.value <= 0:
            raise ValueError('NONPOSITIVE_PRICE_OR_LIQUIDATION')
        return self


class OptionContract(Strict):
    schema_version: Literal['option_contract_v1'] = 'option_contract_v1'
    instrument_id: UUID
    underlying_instrument_id: UUID
    provider: str
    venue: str
    native_id: str = Field(min_length=1)
    expiry: datetime
    strike: Number = Field(gt=0)
    right: Literal['call', 'put']
    multiplier: Number = Field(gt=0)
    settlement: Literal['cash', 'physical']
    exercise: Literal['european', 'american']
    quote_currency: str
    identity_version: str
    @field_validator('expiry')
    @classmethod
    def aware(cls, value):
        return utc(value)


class OptionQuote(Strict):
    contract: OptionContract
    bid: Number | None = Field(default=None, ge=0)
    ask: Number | None = Field(default=None, ge=0)
    last: Number | None = Field(default=None, ge=0)
    volume: Number | None = Field(default=None, ge=0)
    open_interest: Number | None = Field(default=None, ge=0)
    implied_volatility: Number | None = Field(default=None, gt=0)
    greeks: dict[str, Number] = Field(default_factory=dict)
    analytics_origin: Literal['provider', 'calculated', 'unavailable'] = 'unavailable'
    calculation_version: str | None = None
    @model_validator(mode='after')
    def spread(self):
        if self.bid is not None and self.ask is not None and self.bid > self.ask:
            raise ValueError('CROSSED_OPTION_QUOTE')
        if (self.greeks or self.implied_volatility is not None) and self.analytics_origin == 'unavailable':
            raise ValueError('ANALYTICS_ORIGIN_REQUIRED')
        if self.analytics_origin == 'calculated' and not self.calculation_version:
            raise ValueError('CALCULATION_VERSION_REQUIRED')
        return self


class OptionChainSnapshot(Fact):
    domain: Literal['options'] = 'options'
    kind: Literal['option_chain'] = 'option_chain'
    underlying_instrument_id: UUID
    underlying_price: Number = Field(gt=0)
    quotes: list[OptionQuote] = Field(max_length=1000)
    @model_validator(mode='after')
    def identities(self):
        keys = [(q.contract.provider, q.contract.venue, q.contract.native_id) for q in self.quotes]
        economic = [(q.contract.expiry, q.contract.strike, q.contract.right) for q in self.quotes]
        if len(set(keys)) != len(keys) or len(set(economic)) != len(economic):
            raise ValueError('DUPLICATE_OPTION_CONTRACT')
        if any(q.contract.underlying_instrument_id != self.underlying_instrument_id or
               q.contract.expiry <= self.envelope.event_at for q in self.quotes):
            raise ValueError('OPTION_SCOPE_OR_EXPIRY_MISMATCH')
        return self


class OnChainMetric(Fact):
    domain: Literal['onchain'] = 'onchain'
    kind: Literal['onchain_metric'] = 'onchain_metric'
    network: str
    metric: str
    value: Number = Field(ge=0)
    block_height: int | None = Field(default=None, ge=0)
    methodology: str


ContextFact = Annotated[EconomicObservation | FundamentalFact | EventFact | NewsEvent |
                        DerivativeObservation | OptionChainSnapshot | OnChainMetric, Field(discriminator='kind')]
FACTS = TypeAdapter(ContextFact)


class SourceCapability(Strict):
    provider: str
    domain: Domain
    status: Literal['VALIDATED', 'PUBLIC_VALIDATED', 'CONFIGURED_NOT_VALIDATED', 'DEFERRED_NOT_CONFIGURED',
                    'UNSUPPORTED', 'DEGRADED', 'UNAVAILABLE', 'DEFERRED_DATA_SOURCE', 'DEFERRED_PAID_SOURCE']
    authentication: str
    cost: Literal['free', 'paid', 'unknown'] = 'free'
    coverage: list[str]
    frequency: str
    timestamp_semantics: str
    rate_constraints: str
    historical_depth: str
    limitations: list[str]
    live_validated_at: datetime | None = None
    last_ingested_at: datetime | None = None
    fact_count: int = 0


class ContextDimension(Strict):
    status: Literal['AVAILABLE', 'PARTIAL', 'STALE', 'UNKNOWN', 'UNSUPPORTED']
    reason: str
    fact_ids: list[UUID]
    metrics: dict[str, str | float | int | None] = Field(default_factory=dict)


class ContextSnapshot(Strict):
    schema_version: Literal['context_snapshot_v1'] = 'context_snapshot_v1'
    calculation_version: Literal['context_dimensions_v1'] = 'context_dimensions_v1'
    calculation_code_hash: str | None = None
    snapshot_id: UUID
    content_hash: str
    context_manifest_id: UUID | None
    market_manifest_id: UUID | None
    as_of: datetime
    instrument_id: UUID | None
    dimensions: dict[str, ContextDimension]
    facts: list[ContextFact]
    conflicts: list[dict]
    event_risk: dict
    warnings: list[str]


class ContextRequest(Strict):
    as_of: datetime
    context_manifest_id: UUID | None = None
    market_manifest_id: UUID | None = None
    instrument_id: UUID | None = None
    horizon_days: int = Field(default=10, ge=1, le=90)
    @field_validator('as_of')
    @classmethod
    def aware(cls, value):
        return utc(value)
