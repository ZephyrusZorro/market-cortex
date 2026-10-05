"""Typed local Research Lab endpoints; no arbitrary plan execution endpoint."""
from datetime import datetime
from uuid import UUID
from fastapi import APIRouter, BackgroundTasks, HTTPException, Query
from .mission_contracts import MissionRequest, ResearchMission
from .mission_evaluator import evidence
from .mission_policy import metadata
from .missions import MissionService


def router_for(catalog,settings):
    router=APIRouter(prefix='/api/v1/cortex/missions',tags=['research missions'])
    service=MissionService(catalog,settings)
    def call(fn):
        try: return fn()
        except LookupError: raise HTTPException(404,detail={'code':'MISSION_OR_PINNED_RECORD_UNAVAILABLE'}) from None
        except ValueError: raise HTTPException(409,detail={'code':'MISSION_POLICY_OR_CHECKPOINT_CONFLICT'}) from None

    @router.get('/status')
    def status():
        return {'orchestration_version':'cortex_mission_v2','model_provider':service.gateway.provider,
            'model_locality':service.gateway.locality,'deterministic_fallback':True,'api_cost_budget_inr':0,
            'autonomy':'BOUNDED_RESEARCH_ONLY','external_fetch':'SOURCE_ADAPTER_WORKFLOW_ONLY'}

    @router.get('/tools')
    def tools(): return {'items':metadata()}

    @router.get('/templates')
    def templates():
        return {'items':[
            {'id':'instrument_deep_dive','mode':'DEEP_RESEARCH','goal':'Investigate BTC momentum and whether historical evidence supports it.'},
            {'id':'market_review','mode':'DEEP_RESEARCH','goal':'Review the narrow Pilot 5 market state and unresolved risks.'},
            {'id':'thesis_challenge','mode':'THESIS_REVIEW','goal':'Challenge the selected recorded thesis and its competing explanations.'},
            {'id':'strategy_review','mode':'STRATEGY_RESEARCH','goal':'Determine whether registered momentum has quantitative historical support.'},
            {'id':'what_changed','mode':'CHANGE_ANALYSIS','goal':'What changed since the previous BTC investigation?'},
            {'id':'historical','mode':'HISTORICAL_RESEARCH','goal':'Investigate BTC under an explicit historical knowledge cutoff.'},
            {'id':'event_context','mode':'DEEP_RESEARCH','goal':'Explain which recorded events and contextual sources are available.'}]}

    @router.get('')
    def recent(as_of:datetime|None=None,limit:int=Query(20,ge=1,le=50)):
        if as_of is not None and as_of.utcoffset() is None: raise HTTPException(422,detail={'code':'OFFSET_REQUIRED'})
        return {'items':[m.model_dump(mode='json') for m in service.store.recent(as_of=as_of,limit=limit)]}

    @router.post('',response_model=ResearchMission,status_code=201)
    def create(request:MissionRequest): return call(lambda:service.create(request))

    @router.get('/{mission_id}',response_model=ResearchMission)
    def get(mission_id:UUID): return call(lambda:service.store.get(mission_id))

    @router.get('/{mission_id}/plan')
    def plan(mission_id:UUID): return call(lambda:service.store.get(mission_id).plan.model_dump(mode='json'))

    @router.get('/{mission_id}/evidence')
    def records(mission_id:UUID): return call(lambda:{'items':[e.model_dump(mode='json') for e in evidence(service.store.get(mission_id))]})

    @router.get('/{mission_id}/hypotheses')
    def hypotheses(mission_id:UUID): return call(lambda:{'items':[h.model_dump(mode='json') for h in service.store.get(mission_id).hypotheses]})

    @router.get('/{mission_id}/report')
    def report(mission_id:UUID):
        m=call(lambda:service.store.get(mission_id))
        return {'mission_id':str(mission_id),'status':m.status,'report':m.report,'claims':[c.model_dump(mode='json') for c in m.claims],
            'evidence_graph':m.evidence_graph,'evaluator':m.evaluator,'content_hash':m.content_hash}

    @router.get('/{mission_id}/history')
    def history(mission_id:UUID): return call(lambda:{'items':service.store.history(mission_id)})

    @router.get('/{mission_id}/diff')
    def diff(mission_id:UUID,older:UUID): return call(lambda:service.diff(older,mission_id))

    @router.post('/{mission_id}/replay')
    def replay(mission_id:UUID): return call(lambda:service.replay(mission_id))

    @router.post('/{mission_id}/cancel',response_model=ResearchMission)
    def cancel(mission_id:UUID): return call(lambda:service.store.cancel(mission_id))

    def enqueue(mission_id,background):
        m=call(lambda:service.store.get(mission_id))
        if m.status in ('CANCELLED','COMPLETED','INCONCLUSIVE'):
            return {'mission_id':str(mission_id),'status':m.status,'job_id':None}
        job_id=call(lambda:service.enqueue(mission_id))
        background.add_task(service.worker,job_id)
        return {'mission_id':str(mission_id),'status':'QUEUED','job_id':str(job_id)}

    @router.post('/{mission_id}/execute',status_code=202)
    def execute(mission_id:UUID,background:BackgroundTasks): return enqueue(mission_id,background)

    @router.post('/{mission_id}/resume',status_code=202)
    def resume(mission_id:UUID,background:BackgroundTasks): return enqueue(mission_id,background)
    return router
