"""Typed loopback reads; network fetching is an explicit local CLI operation."""
from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query
from pydantic import Field

from .contracts import utc
from .intelligence import IntelligenceService, event_study
from .intelligence_contracts import ContextRequest, ContextSnapshot, Domain, Strict
from .intelligence_sources import coverage
from .intelligence_store import FACTS


class EventStudyRequest(ContextRequest):
    event_fact_id: UUID
    before: int = Field(default=5, ge=0, le=60)
    after: int = Field(default=5, ge=1, le=60)


def router_for(catalog):
    router = APIRouter(prefix='/api/v1/intelligence', tags=['Intelligence'])
    service = IntelligenceService(catalog)
    def request(as_of, context_manifest_id=None, market_manifest_id=None, instrument_id=None, horizon_days=10):
        return ContextRequest(as_of=as_of or datetime.now(timezone.utc), context_manifest_id=context_manifest_id,
                              market_manifest_id=market_manifest_id, instrument_id=instrument_id, horizon_days=horizon_days)
    def call(action):
        try:
            return action()
        except (LookupError, ValueError, KeyError) as exc:
            raise HTTPException(422, detail={'code': str(exc) if isinstance(exc, LookupError) else 'INVALID_CONTEXT_REQUEST'}) from None

    @router.get('/coverage')
    def sources(as_of: datetime | None = None):
        return call(lambda: {'items': [s.model_dump(mode='json') for s in coverage(service.store, utc(as_of or datetime.now(timezone.utc)))]})

    @router.get('/context', response_model=ContextSnapshot)
    def context(as_of: datetime | None = None, context_manifest_id: UUID | None = None,
                market_manifest_id: UUID | None = None, instrument_id: UUID | None = None,
                horizon_days: int = Query(10, ge=1, le=90)):
        return call(lambda: service.snapshot(request(as_of, context_manifest_id, market_manifest_id, instrument_id, horizon_days)))

    @router.get('/facts/{fact_id}')
    def fact(fact_id: UUID, as_of: datetime | None = None):
        return call(lambda: service.store.inspect(fact_id, utc(as_of or datetime.now(timezone.utc))))

    @router.get('/snapshots/{snapshot_id}', response_model=ContextSnapshot)
    def snapshot(snapshot_id: UUID):
        return call(lambda: service.store.snapshot(snapshot_id))

    @router.get('/compare')
    def compare(left: UUID, right: UUID):
        return call(lambda: service.compare(left, right))

    @router.get('/domains/{domain}')
    def domain(domain: Domain, as_of: datetime | None = None, context_manifest_id: UUID | None = None,
               instrument_id: UUID | None = None, limit: int = Query(100, ge=1, le=1000), offset: int = Query(0, ge=0)):
        def read():
            result = service.snapshot(request(as_of, context_manifest_id, instrument_id=instrument_id))
            facts = [f.model_dump(mode='json') for f in result.facts if f.domain == domain]
            return {'context_manifest_id': str(result.context_manifest_id) if result.context_manifest_id else None,
                    'as_of': result.as_of.isoformat(), 'dimension': result.dimensions[domain].model_dump(mode='json'),
                    'items': facts[offset:offset+limit], 'total': len(facts), 'truncated': offset+limit < len(facts)}
        return call(read)

    @router.post('/event-study')
    def study(body: EventStudyRequest):
        def calculate():
            from datetime import timedelta
            if not body.instrument_id or not body.market_manifest_id:
                raise ValueError('EVENT_STUDY_REQUIRES_MARKET_SCOPE')
            fact = FACTS.validate_python(service.store.inspect(body.event_fact_id, body.as_of))
            if fact.domain not in ('events', 'news') or (str(body.instrument_id) != fact.entity.key and body.instrument_id not in fact.related_instrument_ids):
                raise ValueError('EVENT_STUDY_ENTITY_MISMATCH')
            event_at = (fact.actual_release_at or fact.scheduled_at) if fact.domain == 'events' else fact.envelope.event_at
            start, end = event_at-timedelta(days=200), event_at+timedelta(days=200)
            _, bars = catalog.bars(instrument_id=body.instrument_id, start=start, end=end,
                                  as_of=body.as_of, manifest_id=body.market_manifest_id, adjustment_basis='raw')
            if not bars:
                return {'status': 'INSUFFICIENT_SESSION_WINDOW', 'causality': 'NOT_ESTABLISHED'}
            cal = catalog.load_calendar(bars[0].envelope.venue_id, start, end, bars[0].calendar_id)
            return {**event_study(bars, cal, event_at, before=body.before, after=body.after,
                                 classification=fact.classification_scope),
                    'event_fact_id': str(body.event_fact_id), 'market_manifest_id': str(body.market_manifest_id),
                    'as_of': body.as_of.isoformat()}
        return call(calculate)
    return router
