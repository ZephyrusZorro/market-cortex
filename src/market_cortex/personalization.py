"""Local evidence-based profiles, controlled owner corrections and research guidance."""
from pathlib import Path
from uuid import UUID,uuid4
import hashlib
from .intelligence_store import digest
from .personal_contracts import PersonalMemory,PreferenceInput,AdaptationProposal
from .personal_engine import build_snapshot,usable
from .personal_sources import PersonalSources,timestamp
from .personal_store import PersonalStore,now

def _source_hash():
    root=Path(__file__).parent
    names=('personal_contracts.py','personal_engine.py','personal_sources.py','personal_store.py','personalization.py','personal_missions.py','personal_tools.py')
    return digest({n:hashlib.sha256((root/n).read_text(encoding='utf-8').replace('\r\n','\n').encode()).hexdigest() for n in names})


PERSONAL_IMPLEMENTATION_HASH=_source_hash()
def _code_hash(): return PERSONAL_IMPLEMENTATION_HASH


class PersonalizationService:
    def __init__(self,catalog,settings):
        self.catalog,self.settings=catalog,settings
        self.store=PersonalStore(catalog.dsn,settings.environment); self.sources=PersonalSources(self.store)
    def profile(self,query,*,save=False):
        cutoff=query.as_of or now()
        if cutoff>now(): raise ValueError('FUTURE_PROFILE_UNAVAILABLE')
        records,excluded=self.sources.collect(query.audience,cutoff)
        eligible=self.store.owner_ready or query.audience=='SYNTHETIC_VALIDATION'
        controls=[self.store.memory(r) for r in self.store.list('MEMORY',query.audience,cutoff)] if eligible else []
        proposals=[self.store.proposal(r) for r in self.store.list('PROPOSAL',query.audience,cutoff)] if eligible else []
        result=build_snapshot(records,controls,proposals,query.audience,cutoff,_code_hash(),excluded)
        if query.as_of:
            result=result.model_copy(update={'reconstruction_kind':'RETROSPECTIVE_RECONSTRUCTION','limitations':result.limitations+['RECONSTRUCTED_FROM_THEN_AVAILABLE_EVIDENCE_UNDER_THE_DECLARED_ALGORITHM; STORED_OLDER_SNAPSHOTS_REMAIN_UNCHANGED']})
        if query.audience=='OWNER_RESEARCH' and not self.store.owner_ready:
            result=result.model_copy(update={'limitations':result.limitations+['OWNER_MAIN_NOT_CONFIGURED_OR_TEST_CATALOG; ZERO_GENUINE_OWNER_RECORDS']})
        return self.store.save_snapshot(result) if save else result
    def refresh(self,query):
        result=self.profile(query)
        if query.as_of: raise ValueError('HISTORICAL_PROFILE_IS_READ_ONLY')
        if self.store.owner_ready or query.audience=='SYNTHETIC_VALIDATION':
            for m in result.memories:
                if m.source_type=='EXPLICIT' or m.owner_override: continue
                key='inferred:'+m.key
                existing=next((r for r in self.store.list('MEMORY',m.audience,now()) if r['item']['key']==m.key and r['item']['source_type']!='EXPLICIT'),None)
                if existing and existing['item']['evidence_ids']==m.evidence_ids: continue
                row=self.store.append('MEMORY',m.audience,key,{'item':m.model_dump(mode='json')})
            for p in result.patterns:
                if p['sample_N']<3 or p['change']=='IMPROVING': continue
                key='review_emphasis'; value=None
                if p['key'] in ('cortex:quant_ignored','failure:insufficient_history'): value='quant'
                elif p['key']=='cortex:context_ignored': value='intelligence'
                elif p['key']=='failure:contradiction_ignored': value='contradictions'
                if not value: continue
                proposal=AdaptationProposal(proposal_id=uuid4(),audience=result.audience,key=key,value=value,
                    evidence_ids=p['evidence_ids'],memory_ids=[m.memory_id for m in result.memories if m.key==p['key']],
                    rationale='Repeated eligible canonical research evidence indicates a workflow gap.',expected_benefit='Prioritize review of the recorded evidence gap.',
                    affected_workflow='Personalized mission tool order; calculations and budgets remain canonical.',risk='WORKFLOW_APPROVAL_REQUIRED',created_at=now(),recorded_at=now())
                existing=self.store.list('PROPOSAL',result.audience,now())
                if not any(r['item']['key']==key and r['item']['value']==value for r in existing):
                    self.store.append('PROPOSAL',result.audience,key+':'+value,{'item':proposal.model_dump(mode='json')})
        return self.profile(query,save=True)
    def preference(self,request,*,proposal=None):
        self.store.guard(request.audience,write=True); at=now()
        m=PersonalMemory(memory_id=uuid4(),key=request.key,memory_type='SEMANTIC',source_type='EXPLICIT',audience=request.audience,
            status='OWNER_CONFIRMED',statement='Owner explicitly configured '+request.key.replace('_',' ')+'.',value=request.value,
            sample_N=1,sufficiency='EARLY_PATTERN',subject='OWNER_PROCESS',created_at=at,last_validated=at,owner_override='ACCEPTED_PROPOSAL' if proposal else 'EXPLICIT',
            evidence_ids=['proposal:'+str(proposal.proposal_id)+':'+str(proposal.version)] if proposal else [])
        rows=self.store.list('MEMORY',request.audience,at)
        existing=next((r for r in rows if r['item']['key']==request.key and r['item']['source_type']=='EXPLICIT'),None)
        if existing and existing['item']['value']==request.value and existing['item']['status']=='OWNER_CONFIRMED': return self.store.memory(existing)
        row=self.store.append('MEMORY',request.audience,'explicit:'+request.key,{'item':m.model_dump(mode='json')})
        return self.store.memory(row)
    def memory_action(self,key,request):
        row=self.store.get(key); m=self.store.memory(row); self.store.guard(m.audience,write=True)
        if m.version!=request.expected_version: raise ValueError('PERSONAL_VERSION_CONFLICT')
        changes={'owner_override':{'confirm':'CONFIRMED','reject':'REJECTED','correct':'CORRECTED','disable':'DISABLED','retire':'RETIRED'}[request.action],
            'status':{'confirm':'OWNER_CONFIRMED','reject':'REJECTED','correct':'OWNER_CONFIRMED','disable':'DISABLED','retire':'EXPIRED'}[request.action],'last_validated':now()}
        if request.action=='confirm':
            from datetime import timedelta
            changes['expires_at']=None if m.source_type=='EXPLICIT' else now()+timedelta(days=90)
            if m.key in ('default_horizon','preferred_instrument','default_mode','preferred_view','review_emphasis'):
                PreferenceInput(audience=m.audience,key=m.key,value=m.value)
                changes.update(source_type='EXPLICIT',expires_at=None)
        if request.correction:
            if request.correction.key!=m.key or request.correction.audience!=m.audience: raise ValueError('CORRECTION_SCOPE_MISMATCH')
            changes.update(value=request.correction.value,source_type='EXPLICIT',expires_at=None,statement='Owner corrected the explicit '+m.key+' preference.')
        elif request.statement:
            if m.key in ('default_horizon','preferred_instrument','default_mode','preferred_view','review_emphasis'): raise ValueError('TYPED_PREFERENCE_CORRECTION_REQUIRED')
            changes.update(statement=request.statement,source_type='EXPLICIT',value=None,sample_N=1,sufficiency='EARLY_PATTERN')
        updated=m.model_copy(update=changes)
        with __import__('market_cortex.database',fromlist=['connect']).connect(self.store.dsn) as c:
            dedup=c.execute('SELECT dedup_key FROM personal_records WHERE record_id=%s',(key,)).fetchone()[0]
        result=self.store.append('MEMORY',m.audience,dedup,{'item':updated.model_dump(mode='json'),'supersedes_version':m.version},expected=m.version)
        return self.store.memory(result)
    def proposal_action(self,key,request):
        row=self.store.get(key); p=self.store.proposal(row); self.store.guard(p.audience,write=True)
        if p.version!=request.expected_version: raise ValueError('PERSONAL_VERSION_CONFLICT')
        allowed={'PROPOSED':{'accept','reject'},'ACTIVE':{'accept','retire'},'OWNER_ACCEPTED':{'accept','retire'}}
        if request.action not in allowed.get(p.status,set()): raise ValueError('INVALID_PROPOSAL_TRANSITION')
        status={'accept':'ACTIVE','reject':'OWNER_REJECTED','retire':'RETIRED'}[request.action]
        updated=p.model_copy(update={'status':status,'recorded_at':now()})
        # Acceptance is recorded before the explicit preference. If interrupted, a
        # retry can safely apply the same approved preference without new approval.
        result=self.store.append('PROPOSAL',p.audience,p.key+':'+str(p.value),{'item':updated.model_dump(mode='json'),'owner_action':request.action},expected=p.version)
        if request.action=='accept': self.preference(PreferenceInput(audience=p.audience,key=p.key,value=p.value),proposal=self.store.proposal(result))
        elif request.action=='retire':
            rows=self.store.list('MEMORY',p.audience,now())
            m=next((self.store.memory(r) for r in rows if r['item']['key']==p.key and r['item']['source_type']=='EXPLICIT' and r['item']['value']==p.value),None)
            if m and any(k.startswith('proposal:'+str(p.proposal_id)+':') for k in m.evidence_ids):
                from .personal_contracts import MemoryAction
                self.memory_action(m.memory_id,MemoryAction(expected_version=m.version,action='disable'))
        return self.store.proposal(result)
    def attest(self,request):
        self.store.guard(request.audience,write=True)
        p,recorded=self.sources.record(request.source_kind,request.source_id,request.source_version,now())
        self.sources.normalize(request.source_kind,request.source_id,request.source_version,p,recorded,request.audience)
        if request.source_kind=='risk' and request.audience=='OWNER_RESEARCH':
            from .portfolio_store import PortfolioStore
            portfolio=PortfolioStore(self.store.dsn,self.settings.environment).get(UUID(p['portfolio_id']),p['portfolio_version'])
            if not portfolio or portfolio.classification!='OWNER_RESEARCH' or any(x.source_type!='manual' for x in portfolio.positions): raise ValueError('SYNTHETIC_SOURCE_EXCLUDED')
        return self.store.append('ATTESTATION',request.audience,request.source_kind+':'+str(request.source_id),request.model_dump(mode='json'))
    def feedback(self,request):
        self.store.guard(request.audience,write=True)
        if request.target_kind in ('MEMORY','PROPOSAL'):
            target=self.store.get(request.target_id)
            if target['kind']!=request.target_kind or target['audience']!=request.audience: raise ValueError('FEEDBACK_SCOPE_MISMATCH')
        elif request.target_kind=='MISSION':
            self.sources.record('mission',request.target_id,1,now())
        else:
            snapshot=self.store.snapshot(request.target_id)
            if snapshot.audience!=request.audience: raise ValueError('FEEDBACK_SCOPE_MISMATCH')
        return self.store.append('FEEDBACK',request.audience,str(uuid4()),request.model_dump(mode='json'))
    def answer(self,request):
        profile=self.profile(request)
        text=request.question.lower()
        window_start=None
        if 'this month' in text:
            from zoneinfo import ZoneInfo
            window_start=profile.as_of.astimezone(ZoneInfo(self.settings.owner_timezone)).replace(day=1,hour=0,minute=0,second=0,microsecond=0)
            records=[e for e in profile.evidence if e.source_kind in ('quant','preference') or e.recorded_at>=window_start]
            profile=build_snapshot(records,[m for m in profile.memories if m.source_type=='EXPLICIT' or m.owner_override],profile.proposals,
                profile.audience,profile.as_of,_code_hash())
        if any(k in text for k in ('wrong','cortex')): items=[p for p in profile.patterns if p['subject']=='CORTEX_PROCESS']
        elif any(k in text for k in ('mistake','ignore','improve','weaken')): items=[p for p in profile.patterns if p['key'].startswith(('failure:','risk:')) or p['change']=='IMPROVING']
        elif any(k in text for k in ('strateg','edge')): items=profile.strategy_evidence
        else: items=profile.coaching
        if request.symbol or request.strategy:
            by_id={e.evidence_id:e for e in profile.evidence}
            items=[p for p in items if any((not request.symbol or by_id[k].symbol in (None,request.symbol)) and (not request.strategy or by_id[k].strategy==request.strategy) for k in p['evidence_ids'] if k in by_id)]
        return {'question':request.question,'history_state':profile.observed_behavior['history_state'],'owner_sample_N':profile.observed_behavior['genuine_owner_record_N'],
            'scope':{'as_of':profile.as_of.isoformat(),'window_start':window_start.isoformat() if window_start else None,'current_pattern_window_days':90,'duration_measurement':'NOT_RECORDED; USAGE_COUNTS_ONLY'},
            'items':items,'evidence':[e.model_dump(mode='json') for e in profile.evidence if e.evidence_id in {k for i in items for k in i['evidence_ids']}],
            'privacy':'LOCAL_ONLY','limitations':profile.limitations,'model_provider':'deterministic'}
    def verify_snapshot(self,snapshot):
        records,_=self.sources.collect(snapshot.audience,snapshot.as_of)
        by={e.evidence_id:e for e in records}
        checks=[{'evidence_id':e.evidence_id,'matched':e.evidence_id in by and by[e.evidence_id].model_dump()==e.model_dump()} for e in snapshot.evidence]
        return {'matched':all(c['matched'] for c in checks),'checks':checks,'algorithm_available':snapshot.implementation_hash==_code_hash()}
    def export_metadata(self,query):
        p=self.profile(query)
        return {'schema_version':p.schema_version,'snapshot_id':str(p.snapshot_id),'audience':p.audience,'as_of':p.as_of.isoformat(),
            'algorithm_version':p.algorithm_version,'privacy':p.privacy,'observed_behavior':p.observed_behavior,
            'memory_metadata':[m.model_dump(mode='json',exclude={'statement','owner_override'}) for m in p.memories],
            'source_metadata':[e.model_dump(mode='json',exclude={'facts'}) for e in p.evidence],
            'proposal_metadata':[x.model_dump(mode='json',exclude={'rationale','expected_benefit','affected_workflow'}) for x in p.proposals],
            'limitations':p.limitations}
    @staticmethod
    def model_context(profile,gateway):
        if gateway.locality!='local': raise ValueError('PRIVATE_PERSONAL_MEMORY_CLOUD_BLOCKED')
        # No model is used for inference or memory creation. This optional local
        # context consists only of already grounded metadata, never raw notes.
        return {'snapshot_id':str(profile.snapshot_id),'coaching':profile.coaching,'privacy':'LOCAL_ONLY'}
