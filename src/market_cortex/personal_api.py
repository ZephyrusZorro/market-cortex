"""Typed owner-controlled local personalization, separate from autonomous writes."""
from uuid import UUID
from datetime import datetime
from fastapi import APIRouter,HTTPException,Query
from .personal_contracts import (ProfileQuery,PreferenceInput,MemoryAction,ProposalAction,FeedbackInput,
    AttestationInput,PersonalQuestion,PersonalizedMissionInput,PersonalizationSnapshot)
from .personalization import PersonalizationService
from .personal_missions import PersonalizedMissionService
from .personal_store import now
from .personal_tools import execute,metadata


def router_for(catalog,settings):
    router=APIRouter(prefix='/api/v1/personalization',tags=['local personal research'])
    service=PersonalizationService(catalog,settings)
    def call(fn):
        try: return fn()
        except LookupError: raise HTTPException(404,detail={'code':'PERSONAL_RECORD_NOT_AVAILABLE'}) from None
        except ValueError as e:
            allowed={'FUTURE_PERSONALIZATION_FORBIDDEN','OWNER_PERSONALIZATION_REQUIRES_OWNER_MAIN','PERSONAL_VERSION_CONFLICT',
                     'SYNTHETIC_PERSONALIZATION_REQUIRES_TEST_DATABASE','HISTORICAL_PROFILE_IS_READ_ONLY'}
            code=str(e) if str(e) in allowed else 'PERSONAL_POLICY_OR_VERSION_CONFLICT'
            raise HTTPException(409,detail={'code':code}) from None
    @router.get('/profile',response_model=PersonalizationSnapshot)
    def profile(as_of:datetime|None=None,audience:str='OWNER_RESEARCH'):
        return call(lambda:service.profile(ProfileQuery(as_of=as_of,audience=audience)))
    @router.post('/refresh',response_model=PersonalizationSnapshot)
    def refresh(query:ProfileQuery): return call(lambda:service.refresh(query))
    @router.get('/snapshots/{snapshot_id}',response_model=PersonalizationSnapshot)
    def snapshot(snapshot_id:UUID): return call(lambda:service.store.snapshot(snapshot_id))
    @router.get('/memories')
    def memories(audience:str='OWNER_RESEARCH',as_of:datetime|None=None,search:str=Query('',max_length=100),
                 memory_type:str|None=None,status:str|None=None,symbol:str|None=None,strategy:str|None=None,source_type:str|None=None):
        q=call(lambda:ProfileQuery(audience=audience,as_of=as_of)); p=call(lambda:service.profile(q)); by={e.evidence_id:e for e in p.evidence}
        rows=[service.store.memory(r) for r in service.store.list('MEMORY',q.audience,q.as_of or now())]
        def match(m):
            return (not memory_type or m.memory_type==memory_type) and (not status or m.status==status) and (not source_type or m.source_type==source_type) and search.lower() in (m.statement+' '+m.key).lower() and (not symbol or any(k in by and by[k].symbol==symbol for k in m.evidence_ids)) and (not strategy or any(k in by and by[k].strategy==strategy for k in m.evidence_ids))
        return {'items':[m for m in rows if match(m)],'as_of':p.as_of,'privacy':'LOCAL_ONLY'}
    @router.get('/memories/{memory_id}')
    def memory(memory_id:UUID): return call(lambda:service.store.memory(service.store.get(memory_id)))
    @router.get('/memories/{memory_id}/history')
    def history(memory_id:UUID):
        rows=call(lambda:service.store.history(memory_id))
        return {'items':[{**r,'effective_status':'SUPERSEDED' if r['version']<rows[-1]['version'] else r['payload']['item']['status']} for r in rows]}
    @router.post('/preferences')
    def preference(request:PreferenceInput): return call(lambda:service.preference(request))
    @router.post('/memories/{memory_id}/action')
    def memory_action(memory_id:UUID,request:MemoryAction): return call(lambda:service.memory_action(memory_id,request))
    @router.get('/proposals')
    def proposals(audience:str='OWNER_RESEARCH',as_of:datetime|None=None):
        q=call(lambda:ProfileQuery(audience=audience,as_of=as_of))
        return {'items':[service.store.proposal(r) for r in service.store.list('PROPOSAL',q.audience,q.as_of or now())]}
    @router.post('/proposals/{proposal_id}/action')
    def proposal_action(proposal_id:UUID,request:ProposalAction): return call(lambda:service.proposal_action(proposal_id,request))
    @router.post('/feedback')
    def feedback(request:FeedbackInput): return call(lambda:service.feedback(request))
    @router.post('/attestations')
    def attest(request:AttestationInput): return call(lambda:service.attest(request))
    @router.post('/query')
    def answer(request:PersonalQuestion): return call(lambda:service.answer(request))
    @router.get('/tools')
    def tools(): return {'items':metadata()}
    @router.get('/tools/{tool_id}')
    def tool(tool_id:str,audience:str='OWNER_RESEARCH',as_of:datetime|None=None):
        return call(lambda:execute(service,tool_id,ProfileQuery(audience=audience,as_of=as_of)))
    @router.get('/export')
    def export(audience:str='OWNER_RESEARCH',as_of:datetime|None=None):
        return call(lambda:service.export_metadata(ProfileQuery(audience=audience,as_of=as_of)))
    @router.post('/missions')
    def mission(request:PersonalizedMissionInput):
        def create():
            p=service.store.snapshot(request.snapshot_id) if request.snapshot_id else service.profile(ProfileQuery(as_of=request.request.as_of),save=True)
            return PersonalizedMissionService(catalog,settings,p).create_personalized(request)
        return call(create)
    @router.post('/missions/{mission_id}/replay')
    def replay(mission_id:UUID):
        from .mission_store import MissionStore
        def run():
            m=MissionStore(catalog.dsn).get(mission_id); ref=m.frozen_references.get('personalization')
            if not ref: raise ValueError('MISSION_HAS_NO_PERSONALIZATION')
            p=service.store.snapshot(UUID(ref['snapshot_id']))
            return PersonalizedMissionService(catalog,settings,p).replay_personalized(mission_id)
        return call(run)
    @router.get('/missions/{mission_id}/review')
    def post_review(mission_id:UUID):
        from .mission_store import MissionStore
        m=call(lambda:MissionStore(catalog.dsn).get(mission_id)); ref=m.frozen_references.get('personalization')
        if not ref: raise HTTPException(409,detail={'code':'MISSION_HAS_NO_PERSONALIZATION'})
        p=call(lambda:service.store.snapshot(UUID(ref['snapshot_id'])))
        done=[s for s in m.plan.steps if s.status=='DONE']
        return {'mission_id':mission_id,'personalization_snapshot_id':p.snapshot_id,'status':m.status,'owner_sample_N':p.observed_behavior['genuine_owner_record_N'],
            'quant_reviewed':any(s.domain=='quant' for s in done),'context_reviewed':any(s.domain=='intelligence' for s in done),
            'contradictions_recorded':bool(m.contradictions),'canonical_claims_rejected':m.evaluator.get('rejected_claims',[]),
            'reminders':p.coaching,'no_outcome_or_improvement_inferred':True}
    return router
