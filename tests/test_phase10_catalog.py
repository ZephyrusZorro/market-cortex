"""Real isolated PostgreSQL checkpoints, recovery, API and model boundary tests."""
from datetime import timedelta
from decimal import Decimal
from pathlib import Path
import tempfile
from uuid import uuid4
import pytest
from fastapi.testclient import TestClient
from market_cortex.api import create_app
from market_cortex.cortex_gateway import ModelResult
from market_cortex.database import connect
from market_cortex.mission_contracts import MissionRequest,MissionBudget
from market_cortex.missions import MissionService,now
from market_cortex.intelligence_store import digest
from psycopg import sql
from psycopg.conninfo import make_conninfo
from market_cortex.database import migrate
from market_cortex.calendar import SessionCalendar
from market_cortex.contracts import Venue
from market_cortex.storage import PostgresCatalog,ArtifactStore
from test_phase9_catalog import DSN,SAFE,settings
from test_foundation import identity,bar

@pytest.fixture(scope='module')
def catalog():
    if not SAFE: pytest.skip('dedicated *_test PostgreSQL required')
    schema='phase10_'+uuid4().hex
    with tempfile.TemporaryDirectory(prefix='market-cortex-phase10-') as directory:
        with connect(DSN) as c: c.execute(sql.SQL('CREATE SCHEMA {}').format(sql.Identifier(schema)))
        dsn=make_conninfo(DSN,options='-csearch_path='+schema)
        try:
            migrate(dsn,Path(__file__).resolve().parents[1])
            result=PostgresCatalog(dsn,ArtifactStore(Path(directory)))
            venue=Venue(venue_id='BINANCE_SPOT',timezone='UTC',session_kind='24x7')
            cal=SessionCalendar(venue,'crypto_daily','v1'); at=now()
            for symbol in ('BTCUSDT','ETHUSDT','SOLUSDT','BNBUSDT','XRPUSDT'):
                i,m=identity(venue_id='BINANCE_SPOT',native=symbol)
                i=i.model_copy(update={'asset_class':'crypto_spot','instrument_kind':'spot_pair','trading_currency':'USDT','quantity_unit':'base_asset'})
                result.register_identity([venue],[i],[m]); batch=uuid4(); rows=[]
                for n in range(120):
                    day=at.date()-timedelta(days=120-n); price=Decimal(100+n)
                    b=bar(i,m,cal,day=day,close=str(price),available=(cal.session(day).close_at+timedelta(seconds=60)).isoformat())
                    rows.append(b.model_copy(update={'open':price,'high':price+1,'low':price-1,
                        'envelope':b.envelope.model_copy(update={'source_batch_id':batch,'ingested_at':at})}))
                result.ingest(rows,cal,source_batch_id=batch,provider_id='binance',raw_hash='0'*64,fetched_at=at)
            yield result
        finally:
            with connect(DSN) as c: c.execute(sql.SQL('DROP SCHEMA {} CASCADE').format(sql.Identifier(schema)))

def service(catalog,gateway=None): return MissionService(catalog,settings(catalog),gateway=gateway)
def quick(**kw): return MissionRequest(goal='Inspect BTCUSDT close.',mode='QUICK_RESEARCH',symbol='BTCUSDT',duplicate_policy='fresh',**kw)

def test_golden_persist_replay_hash_and_no_canonical_writes(catalog):
    s=service(catalog); head=catalog.head()
    m=s.create(MissionRequest(goal='Investigate BTC momentum',symbol='BTCUSDT',duplicate_policy='fresh'))
    assert m.status=='READY' and m.plan.steps
    assert m.context.manifest_id==head  # Several manifests intentionally share a source timestamp.
    final=s.run(m.mission_id)
    assert final.status=='INCONCLUSIVE' and final.report and final.claims and final.hypotheses, [(s.step_id,s.required,s.output.status if s.output else None,[(e.label,e.value) for e in s.output.evidence][:4] if s.output else None) for s in final.plan.steps]
    assert not final.evaluator['rejected_claims']
    assert final.usage.tool_calls==len(final.plan.steps)
    assert s.replay(m.mission_id)['matched']
    assert catalog.head()==head
    with connect(catalog.dsn) as c:
        assert c.execute('select count(*) from opportunity_candidates').fetchone()[0]==0
        assert c.execute('select count(*) from research_theses').fetchone()[0]==0
    assert s.store.get(m.mission_id).content_hash==final.content_hash

def test_missing_options_waits_without_fabrication(catalog):
    s=service(catalog)
    r=quick(approved_domains=['market','options'],required_domains=['market','options'])
    m=s.run(s.create(r).mission_id)
    assert m.status=='WAITING_FOR_DATA'
    assert any('options coverage' in c.text and 'UNKNOWN' in c.text for c in m.limitations)
    assert 'options' in m.evaluator['mandatory_domains_missing']
    assert s.replay(m.mission_id)['matched']

def test_future_manifest_and_unavailable_historical_scope(catalog):
    s=service(catalog)
    m=s.create(quick(as_of=now()-timedelta(days=400),manifest_id=catalog.head()))
    assert m.status=='WAITING_FOR_DATA' and m.context is None
    assert m.termination_reason=='MANIFEST_NOT_KNOWN_AT_CUTOFF'
    assert s.run(m.mission_id).context is None
    m=s.create(quick(as_of=now()+timedelta(days=2)))
    assert m.termination_reason=='FUTURE_CUTOFF_UNAVAILABLE'

def test_retry_and_replan_are_bounded_and_idempotent(catalog,monkeypatch):
    s=service(catalog); m=s.create(quick())
    original=s._execute; calls=[]
    def fail_once(mission,step,**kw):
        calls.append(step.step_id)
        if len(calls)==1: raise TimeoutError('private provider URL must not appear')
        return original(mission,step,**kw)
    monkeypatch.setattr(s,'_execute',fail_once)
    final=s.run(m.mission_id)
    assert final.usage.replans==1 and final.usage.planner_iterations==2
    assert final.plan.steps[0].attempts==2 and final.plan.steps[0].status=='DONE'
    assert 'private provider' not in final.model_dump_json()
    assert s.run(m.mission_id).content_hash==final.content_hash
    assert final.usage.tool_calls==len(final.plan.steps)+1

def test_repeated_tool_failure_terminates(catalog,monkeypatch):
    s=service(catalog); m=s.create(quick())
    monkeypatch.setattr(s,'_execute',lambda *a,**kw: (_ for _ in ()).throw(OSError('secret')))
    result=s.run(m.mission_id)
    assert result.status=='PARTIAL' and result.termination_reason=='REQUIRED_TOOL_FAILED'
    assert result.usage.tool_calls==2 and result.usage.replans==1

def test_tool_budget_not_reset_on_resume(catalog):
    s=service(catalog); m=s.create(quick(budgets=MissionBudget(max_tool_calls=6)))
    m=s.store.save(m.model_copy(update={'usage':m.usage.model_copy(update={'tool_calls':6})}))
    result=s.run(m.mission_id)
    assert result.status=='PARTIAL' and result.termination_reason=='TOOL_BUDGET_EXHAUSTED'
    again=s.run(m.mission_id)
    assert again.usage.tool_calls==6 and again.context==m.context

def test_cancel_active_mission_preserves_checkpoints(catalog,monkeypatch):
    s=service(catalog); m=s.create(quick()); original=s._execute
    def cancel_after(mission,step,**kw):
        result=original(mission,step,**kw)
        if step.step_id=='features': s.store.cancel(mission.mission_id)
        return result
    monkeypatch.setattr(s,'_execute',cancel_after)
    final=s.run(m.mission_id)
    assert final.status=='CANCELLED'
    assert final.plan.steps[0].output and final.usage.tool_calls==2
    assert s.run(m.mission_id).status=='CANCELLED'
    assert len(s.store.history(m.mission_id))>=5

def test_checkpoint_recovery_uses_frozen_scope_and_skips_finished_steps(catalog,monkeypatch):
    s=service(catalog); m=s.create(quick()); original=s._execute
    def crash(mission,step,**kw):
        if step.step_id=='features': raise KeyboardInterrupt()
        return original(mission,step,**kw)
    monkeypatch.setattr(s,'_execute',crash)
    with pytest.raises(KeyboardInterrupt): s.run(m.mission_id)
    checkpoint=s.store.get(m.mission_id)
    assert checkpoint.plan.steps[0].status=='DONE' and checkpoint.plan.steps[1].status=='RUNNING'
    monkeypatch.setattr(s,'_execute',original)
    final=s.run(m.mission_id)
    assert final.context==m.context and final.usage.cache_hits==1
    assert final.plan.steps[0].attempts==1 and final.plan.steps[1].attempts==2
    assert s.replay(m.mission_id)['matched']

def test_deadline_cannot_restart_on_resume(catalog):
    s=service(catalog); m=s.create(quick())
    m=s.store.save(m.model_copy(update={'deadline_at':now()-timedelta(seconds=1)}))
    final=s.run(m.mission_id)
    assert final.termination_reason=='DEADLINE_EXHAUSTED'
    assert final.usage.tool_calls==0 and final.deadline_at==m.deadline_at

def test_append_only_memory_retrieval_uses_earlier_checkpoint(catalog):
    s=service(catalog); m=s.create(quick()); cutoff=now()
    cancelled=s.store.cancel(m.mission_id)
    historical=s.store.get_at(m.mission_id,cutoff)
    assert historical.status=='READY' and cancelled.status=='CANCELLED'
    assert next(x for x in s.store.recent(as_of=cutoff) if x.mission_id==m.mission_id).revision==historical.revision
    with pytest.raises(ValueError,match='CONFLICT'): s.store.save(m)

class MockModel:
    locality='local'; provider='mock_local'; calls=0
    def select_claims(self,question,candidates):
        self.calls+=1; self.candidates=candidates
        return ModelResult((candidates[0]['claim_id'],),self.provider,'mock',2,input_tokens=10,output_tokens=2)

def test_local_mock_model_is_curation_only_and_budgeted(catalog):
    gateway=MockModel(); s=service(catalog,gateway)
    m=s.run(s.create(quick(budgets=MissionBudget(max_tool_calls=6,max_model_calls=1))).mission_id)
    assert gateway.calls==1 and m.usage.model_calls==1
    assert m.usage.api_cost_inr==0 and m.usage.model_input_tokens==10
    assert m.model_metadata['selected_claim_ids'] and m.claims
    assert len(gateway.candidates)<=12

def test_remote_and_malicious_model_cannot_exfiltrate_or_originate(catalog):
    gateway=MockModel(); gateway.locality='cloud'; s=service(catalog,gateway)
    m=s.run(s.create(quick(budgets=MissionBudget(max_tool_calls=6,max_model_calls=1))).mission_id)
    assert gateway.calls==0 and m.model_metadata['status']=='PRIVACY_OR_ZERO_COST_POLICY_BLOCKED'
    gateway=MockModel()
    gateway.select_claims=lambda *a: ModelResult(('invented-claim-profit-100',),'mock_local','malicious',1)
    s=service(catalog,gateway)
    m=s.run(s.create(quick(budgets=MissionBudget(max_tool_calls=6,max_model_calls=1))).mission_id)
    assert m.model_metadata['status']=='MODEL_FAILED_DETERMINISTIC_FALLBACK'
    assert not any('invented-claim' in c.text for c in m.claims)

def test_typed_api_job_queue_reports_and_rejects_arbitrary_execution(catalog):
    app=create_app(settings(catalog),catalog)
    with TestClient(app) as client:
        response=client.post('/api/v1/cortex/missions',json=quick().model_dump(mode='json'))
        assert response.status_code==201
        key=response.json()['mission_id']; prefix='/api/v1/cortex/missions/'+key
        assert client.post(prefix+'/execute').status_code==202
        assert client.get(prefix).json()['status'] in ('INCONCLUSIVE','COMPLETED')
        for endpoint in ('plan','evidence','hypotheses','report','history'):
            assert client.get(prefix+'/'+endpoint).status_code==200
        assert client.post(prefix+'/replay').json()['matched']
        assert client.post('/api/v1/cortex/missions',json={'goal':'Research','tools':['shell']}).status_code==422
        assert client.post(prefix+'/shell',json={}).status_code==404

def test_exact_duplicate_reuse_and_fresh_rerun(catalog):
    s=service(catalog); r=MissionRequest(goal='Duplicate current BTC question',symbol='BTCUSDT',as_of=now())
    first=s.create(r); second=s.create(r)
    assert first.mission_id==second.mission_id
    fresh=s.create(r.model_copy(update={'duplicate_policy':'fresh'}))
    assert fresh.mission_id!=first.mission_id

def test_predeclared_quant_experiment_is_bounded_grounded_and_retry_safe(catalog):
    from market_cortex.quant_contracts import BacktestDefinition
    s=service(catalog); cutoff=now()
    definition=BacktestDefinition(strategy_id='buy_hold',manifest_id=catalog.head(),source_as_of=cutoff,
        start=cutoff.date()-timedelta(days=8),end=cutoff.date()-timedelta(days=5),symbols=['BTCUSDT'],max_positions=1)
    request=MissionRequest(goal='Review a predeclared short baseline counterfactual.',mode='STRATEGY_RESEARCH',symbol='BTCUSDT',as_of=cutoff,
        strategy_id='buy_hold',experiment=definition,budgets=MissionBudget(max_quant_runs=1),duplicate_policy='fresh')
    planned=s.create(request)
    assert planned.experiments[0].status=='REGISTERED' and planned.experiments[0].run_id is None
    result=s.run(planned.mission_id)
    assert result.experiments[0].status=='EXECUTED' and result.usage.quant_runs==1
    assert result.experiments[0].registered_at<=result.updated_at
    assert not result.evaluator['rejected_claims']
    assert any('Retrospective experiment N' in c.text for c in result.claims)
    assert s.replay(result.mission_id)['matched']
    assert s.run(result.mission_id).experiments[0].run_id==result.experiments[0].run_id
    bad=definition.model_copy(update={'start':cutoff.date()-timedelta(days=50)})
    rejected=s.create(request.model_copy(update={'experiment':bad}))
    assert rejected.status=='FAILED' and rejected.termination_reason=='PLAN_POLICY_REJECTED'

def test_selected_candidate_challenge_and_future_record_guard(catalog):
    from market_cortex.opportunity import OpportunityService
    from market_cortex.opportunity_contracts import ScanRequest
    from market_cortex.opportunity_store import OpportunityStore
    scan=OpportunityService(catalog).scan(ScanRequest(symbol='BTCUSDT',record=False))
    candidate=next(c for c in scan.candidates if c.detector_id=='breakout')
    ledger=OpportunityStore(catalog.dsn); ledger.record_scan(scan.model_copy(update={'candidates':[candidate]}))
    s=service(catalog)
    request=MissionRequest(goal='Challenge the recorded breakout setup.',template='thesis_challenge',candidate_id=candidate.candidate_id,duplicate_policy='fresh')
    result=s.run(s.create(request).mission_id)
    assert result.context.symbol=='BTCUSDT'
    assert any(s.tool_id=='mission.challenge_candidate' and s.output for s in result.plan.steps)
    assert result.contradictions
    hidden=s.create(request.model_copy(update={'as_of':candidate.created_at-timedelta(seconds=1)}))
    assert hidden.status=='WAITING_FOR_DATA' and hidden.termination_reason=='RESEARCH_RECORD_NOT_KNOWN_AT_CUTOFF'

def test_change_analysis_has_cited_comparable_deltas(catalog):
    s=service(catalog); prior=s.run(s.create(quick()).mission_id)
    request=MissionRequest(goal='What changed in BTC since the earlier mission?',mode='CHANGE_ANALYSIS',symbol='BTCUSDT',
        previous_mission_id=prior.mission_id,duplicate_policy='fresh')
    result=s.run(s.create(request).mission_id)
    assert result.previous_context==prior.context and result.usage.historical_comparisons==3
    assert any(s.tool_id=='mission.compare_states' and s.output for s in result.plan.steps)
    changes=s.diff(prior.mission_id,result.mission_id)
    assert changes['causal_inference'] is False
    assert s.replay(result.mission_id)['matched']

def test_replay_reports_unavailable_version_and_cannot_change_scope(catalog,monkeypatch):
    s=service(catalog); m=s.create(quick())
    with pytest.raises(ValueError,match='IMMUTABLE'):
        s.store.save(m.model_copy(update={'context':m.context.model_copy(update={'manifest_id':uuid4()})}))
    with pytest.raises(ValueError,match='IMMUTABLE'):
        s.store.save(m.model_copy(update={'frozen_references':{}}))
    monkeypatch.setattr('market_cortex.missions.implementation_hash',lambda:'missing-code-version')
    assert s.replay(m.mission_id)['status']=='ORCHESTRATION_VERSION_UNAVAILABLE'
    assert s.run(m.mission_id).termination_reason=='ORCHESTRATION_VERSION_UNAVAILABLE'

def test_abandoned_process_lease_can_be_reclaimed_before_deadline(catalog):
    from market_cortex.jobs import JobQueue
    s=service(catalog); m=s.create(quick())
    job_id=s.enqueue(m.mission_id); queue=JobQueue(catalog.dsn)
    job=queue.claim(lease_seconds=60,kind='cortex_mission',job_id=job_id)
    assert queue.renew(job_id,job.attempts)
    token=s.store.acquire(m.mission_id,60)
    m=s.store.save(m.model_copy(update={'status':'RUNNING','deadline_at':now()+timedelta(seconds=100)}),token)
    with pytest.raises(ValueError,match='ALREADY_RUNNING'): s.enqueue(m.mission_id)
    output=s._execute(m,m.plan.steps[0]); steps=list(m.plan.steps)
    steps[0]=steps[0].model_copy(update={'status':'DONE','attempts':1,'output':output})
    m=s.store.save(m.model_copy(update={'plan':m.plan.model_copy(update={'steps':steps}),'usage':m.usage.model_copy(update={'tool_calls':1})}),token)
    assert s.store.renew(m.mission_id,token)
    # Emulate OS kill: no Python finally/release ran. The 60-second lease expired,
    # while the original deadline and previously charged budget still survive.
    with connect(catalog.dsn) as c:
        c.execute("UPDATE research_missions SET lease_until=now()-interval '1 second' WHERE mission_id=%s",(m.mission_id,))
        c.execute("UPDATE jobs SET lease_until=now()-interval '1 second' WHERE job_id=%s",(job_id,))
    assert not s.store.renew(m.mission_id,token)
    assert not queue.renew(job_id,job.attempts)
    with pytest.raises(ValueError,match='LEASE_EXPIRED'): s.store.save(m,token)
    assert s.worker(job_id)['status']=='DONE'
    result=s.store.get(m.mission_id)
    assert not queue.renew(job_id,job.attempts)
    assert result.status in ('COMPLETED','INCONCLUSIVE') and result.context==m.context
    assert result.deadline_at==m.deadline_at and result.usage.cache_hits==1
    assert result.usage.tool_calls==len(result.plan.steps) and result.plan.steps[0].attempts==1
