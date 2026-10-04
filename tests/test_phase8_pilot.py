"""Actual stored Binance reads in an explicitly isolated *_test catalog."""
import os
from datetime import date,datetime,timedelta,timezone
from pathlib import Path
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from psycopg.conninfo import conninfo_to_dict

from market_cortex.api import create_app
from market_cortex.config import Settings
from market_cortex.cortex import CortexService
from market_cortex.cortex_contracts import ResearchRequest
from market_cortex.database import connect,migrate
from market_cortex.learning import LearningService
from market_cortex.learning_contracts import EdgeDraft
from market_cortex.opportunity import OpportunityService
from market_cortex.opportunity_contracts import ScanRequest
from market_cortex.quant import QuantService,decision_hash
from market_cortex.quant_contracts import BacktestDefinition,EdgeEvidenceRequest
from market_cortex.quant_replay import ReplayCatalog,ReplayOpportunityService
from market_cortex.storage import ArtifactStore,PostgresCatalog

DSN=os.getenv('MARKET_CORTEX_PHASE8_PILOT_DSN');ROOT=os.getenv('MARKET_CORTEX_PHASE8_PILOT_DATA_ROOT')
SAFE=bool(DSN and ROOT and conninfo_to_dict(DSN).get('dbname','').endswith('_test'))


@pytest.fixture(scope='module')
def pilot():
    if not SAFE:
        pytest.skip('dedicated Phase 8 *_test catalog with matching Parquet required')
    migrate(DSN,Path(__file__).resolve().parents[1])
    catalog=PostgresCatalog(DSN,ArtifactStore(Path(ROOT)))
    settings=Settings(DSN,Path(ROOT),'Asia/Kolkata','INR',False,True,'PILOT_TEST')
    return QuantService(catalog,'PILOT_TEST'),settings,TestClient(create_app(settings=settings,catalog=catalog))


def test_canonical_detector_parity_on_actual_known_manifest(pilot):
    service,_,_=pilot
    d=BacktestDefinition(strategy_id='momentum',manifest_id=service.catalog.head(),source_as_of=datetime.now(timezone.utc),
        start=date(2026,9,30),end=date(2026,10,3),classification='SYNTHETIC_TEST')
    source,_=service.source(d)
    request=ScanRequest(mode='pinned',manifest_id=d.manifest_id,as_of=d.source_as_of)
    live=OpportunityService(service.catalog).scan(request)
    replay=ReplayOpportunityService(ReplayCatalog(source,'AS_RECORDED')).scan(request)
    assert [decision_hash(c) for c in live.candidates]==[decision_hash(c) for c in replay.candidates]


def test_persist_recompute_api_job_cortex_privacy_and_edge_gates(pilot):
    service,settings,client=pilot
    now=datetime.now(timezone.utc)
    d=BacktestDefinition(strategy_id='trend_continuation',manifest_id=service.catalog.head(),source_as_of=now,
        start=date(2026,9,29),end=date(2026,10,3),replay_policy='HISTORICAL_RECONSTRUCTION',classification='SYNTHETIC_TEST')
    run=service.run(d)
    assert service.replay(run.run_id)['status']=='MATCH'
    assert client.get(f'/api/v1/quant/runs/{run.run_id}').json()['result_hash']==run.result_hash
    assert client.post('/api/v1/quant/jobs',json={'operation':'exec_python','payload':{}}).status_code==422
    assert client.post('/api/v1/quant/jobs',json={'operation':'backtest','payload':{**d.model_dump(mode='json'),'code':'print(1)'}}).status_code==422
    queued=client.post('/api/v1/quant/jobs',json={'operation':'backtest','payload':d.model_dump(mode='json')})
    assert queued.status_code==202
    job_id=queued.json()['job_id']
    status=client.get(f'/api/v1/quant/jobs/{job_id}').json()
    assert status['status']=='completed' and status['result_ref']==str(run.run_id)
    cortex=CortexService(service.catalog,settings)
    research=cortex.research(ResearchRequest(question='What was this backtest max drawdown after fees; did it survive OOS?',
        mode='pinned',manifest_id=d.manifest_id,as_of=datetime.now(timezone.utc),backtest_run_id=run.run_id),persist=True)
    assert [tool.tool_id for tool in research.tools]==['dataset.context','quant.run']
    assert f"N={run.metrics['N']}" in research.answer and 'period=' in research.answer and 'costs=' in research.answer
    assert 'OOS=single run in-sample' in research.answer and 'ASSUMED_HISTORICAL_RECONSTRUCTION' in research.answer
    assert research.model_provider=='deterministic' and research.failure_state is None
    assert cortex.replay(research.run_id)['evidence_reproducible'] is True
    class CloudSpy:
        locality='cloud'
        provider='fake_cloud'
        def select_claims(self,*args):
            raise AssertionError('Private quant context must never reach a cloud model')
    from dataclasses import replace
    private=CortexService(service.catalog,replace(settings,cloud_model_allowed=True),gateway=CloudSpy()).research(ResearchRequest(
        question='Explain this backtest, its sample and costs',mode='pinned',manifest_id=d.manifest_id,
        as_of=datetime.now(timezone.utc),backtest_run_id=run.run_id),persist=False)
    assert private.model_provider=='deterministic' and 'costs=' in private.answer
    with pytest.raises(LookupError):
        service.store.get(run.run_id,'run',as_of=run.created_at-timedelta(microseconds=1))
    learning=LearningService(service.catalog,'PILOT_TEST')
    edge=learning.edge(EdgeDraft(title='SYNTHETIC_TEST Phase 8 quant attachment',hypothesis='Explicit evidence should not become a supported edge from one backtest.',
        detector_id='trend_continuation',detector_version='1.0.0',registration='RETROSPECTIVE_EVALUATION',classification='SYNTHETIC_TEST'))
    try:
        request=EdgeEvidenceRequest(edge_id=edge['edge_id'],run_ids=[run.run_id],reason='Synthetic test validates evidence revision boundaries.')
        evidence=service.attach_edge(request)
        assert evidence['revision']==1 and evidence['status']=='HYPOTHESIS'
        with pytest.raises(ValueError,match='SUPPORTED_REQUIRES'):
            service.attach_edge(request.model_copy(update={'status':'SUPPORTED','expected_revision':1}))
        with pytest.raises(ValueError,match='EDGE_REVISION_CONFLICT'):
            service.attach_edge(request)
        before=learning.store.edges(datetime.fromisoformat(evidence['recorded_at'])-timedelta(microseconds=1))
        assert not next(e for e in before if e['edge_id']==edge['edge_id']).get('quant_evidence')
        current=learning.store.edges(datetime.now(timezone.utc))
        assert next(e for e in current if e['edge_id']==edge['edge_id'])['quant_evidence']['revision']==1
    finally:
        with connect(DSN) as c:
            c.execute('DELETE FROM quant_edge_evidence WHERE edge_id=%s',(edge['edge_id'],))
            c.execute('DELETE FROM edge_library WHERE edge_id=%s',(edge['edge_id'],))


def test_failed_job_safe_error_and_explicit_retry(pilot):
    _,_,client=pilot
    from uuid import uuid4
    # A missing immutable source is a domain failure, not an accepted execution.
    missing=uuid4()
    response=client.post('/api/v1/quant/jobs',json={'operation':'monte_carlo','payload':{'run_id':str(missing)}})
    assert response.status_code==202
    job=response.json()['job_id']
    status=client.get(f'/api/v1/quant/jobs/{job}').json()
    assert status['status']=='failed' and status['error_code']=='QUANT_ARTIFACT_NOT_VISIBLE'
    assert client.post(f'/api/v1/quant/jobs/{job}/retry').status_code==202
    retried=client.get(f'/api/v1/quant/jobs/{job}').json()
    assert retried['status']=='failed' and retried['attempts']==status['attempts']+1
