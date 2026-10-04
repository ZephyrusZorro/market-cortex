"""Isolated *_test journal→prediction→outcome→learning integration, never owner data."""
import copy
import os
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from psycopg.conninfo import conninfo_to_dict

from market_cortex.api import create_app
from market_cortex.config import Settings
from market_cortex.cortex import CortexService
from market_cortex.cortex_contracts import ResearchRequest
from market_cortex.database import connect, migrate
from market_cortex.learning import LearningService
from market_cortex.learning_contracts import (EdgeDraft,EvaluationRequest,JournalDraft,JournalRevision,
    LearningLinks,PredictionDefinition)
from market_cortex.learning_store import LearningStore
from market_cortex.portfolio_store import PortfolioStore
from market_cortex.risk import RiskService
from market_cortex.risk_contracts import PortfolioCreate,RiskRequest
from market_cortex.storage import ArtifactStore,PostgresCatalog
from market_cortex.workstation import build_context

DSN=os.environ.get("MARKET_CORTEX_PHASE7_PILOT_DSN")
ROOT=os.environ.get("MARKET_CORTEX_PHASE7_PILOT_DATA_ROOT")
SAFE=bool(DSN and ROOT and conninfo_to_dict(DSN).get("dbname","").endswith("_test") and Path(ROOT).is_dir())


@pytest.fixture
def pilot():
    if not SAFE:
        pytest.skip("dedicated Phase 7 *_test catalog and matching Parquet root required")
    migrate(DSN,Path(__file__).resolve().parents[1])
    catalog=PostgresCatalog(DSN,ArtifactStore(Path(ROOT)))
    return LearningService(catalog,"PILOT_TEST"),TestClient(create_app(
        settings=Settings(DSN,Path(ROOT),"Asia/Kolkata","INR",False,True,"PILOT_TEST"),catalog=catalog))


def test_learning_risk_link_requires_actual_recording_visibility(pilot):
    service,_=pilot
    store=PortfolioStore(DSN,"PILOT_TEST")
    portfolio=store.create(PortfolioCreate(name="SYNTHETIC_TEST_PORTFOLIO_PHASE7_RECORDING_GUARD",
        base_currency="USDT",capital="1000",classification="SYNTHETIC_TEST_PORTFOLIO"))
    try:
        snapshot=RiskService(service.catalog,"PILOT_TEST").snapshot(portfolio.portfolio_id,
            RiskRequest(manifest_id=service.catalog.head(),persist=True))
        with connect(DSN) as connection:
            recorded=connection.execute("SELECT recorded_at FROM portfolio_risk_snapshots WHERE snapshot_id=%s",
                                        (snapshot.snapshot_id,)).fetchone()[0]
        assert snapshot.as_of<recorded
        before=recorded-timedelta(microseconds=1)
        assert store.risk_snapshot(snapshot.snapshot_id,known_at=before) is None
        assert store.risk_snapshot(snapshot.snapshot_id,known_at=recorded) is not None
        with pytest.raises(LookupError,match="LINK_RISK_SNAPSHOT_NOT_VISIBLE"):
            service.freeze_links(LearningLinks(risk_snapshot_id=snapshot.snapshot_id),service.catalog.head(),before,"SYNTHETIC_TEST")
        with pytest.raises(ValueError,match="SYNTHETIC_LINK_REQUIRES_SYNTHETIC_RECORD"):
            service.freeze_links(LearningLinks(risk_snapshot_id=snapshot.snapshot_id),service.catalog.head(),
                                 datetime.now(timezone.utc),"OWNER_RESEARCH")
    finally:
        with connect(DSN) as connection:
            connection.execute("DELETE FROM portfolio_risk_snapshots WHERE portfolio_id=%s",(portfolio.portfolio_id,))
            connection.execute("DELETE FROM portfolio_versions WHERE portfolio_id=%s",(portfolio.portfolio_id,))
            connection.execute("DELETE FROM portfolios WHERE portfolio_id=%s",(portfolio.portfolio_id,))


def test_learning_chain_context_history_evaluation_repeat_statistics_privacy_and_cortex(pilot):
    service,client=pilot
    context=build_context(service.catalog,as_of=datetime.now(timezone.utc))
    manifest=UUID(context["source_manifest_id"])
    latest=date.fromisoformat(context["evaluation_date"])
    prediction_ids,journal_ids,edge_ids,run_ids=[],[],[],[]
    try:
        request=PredictionDefinition(title="SYNTHETIC_TEST: BTC versus ETH over five sessions",
            prediction_type="relative_performance",symbol="BTCUSDT",benchmark_symbol="ETHUSDT",
            horizon_sessions=5,comparator="gt",threshold="0",manifest_id=manifest,
            as_of=datetime.now(timezone.utc),baseline_session=latest-timedelta(days=10),
            registration="RETROSPECTIVE_EVALUATION",classification="SYNTHETIC_TEST")
        prediction=service.create_prediction(request)
        prediction_ids.append(prediction.prediction_id)
        original=copy.deepcopy(prediction.original_context)
        assert len(prediction.horizon_dates)==5 and prediction.due_session==prediction.baseline_session+timedelta(days=5)
        assert prediction.created_at>prediction.due_at and prediction.registration=="RETROSPECTIVE_EVALUATION"
        evaluation_request=EvaluationRequest(manifest_id=manifest,as_of=datetime.now(timezone.utc))
        evaluation=service.evaluate(prediction.prediction_id,evaluation_request)
        assert evaluation.status in ("CONFIRMED","INVALIDATED","INCONCLUSIVE")
        assert evaluation.observed_sessions==5 and len(evaluation.observation_ids)==10
        assert evaluation.evaluated_at>=prediction.created_at
        assert service.evaluate(prediction.prediction_id,evaluation_request).model_dump()==evaluation.model_dump()
        assert len(service.store.evaluations(prediction.prediction_id))==1
        with pytest.raises(ValueError,match="EVALUATION_CUTOFF_CANNOT_MOVE_BACKWARD"):
            service.evaluate(prediction.prediction_id,EvaluationRequest(
                manifest_id=manifest,as_of=evaluation_request.as_of-timedelta(microseconds=1)))
        assert service.store.prediction(prediction.prediction_id).evaluation_id==evaluation.evaluation_id
        assert service.store.prediction(prediction.prediction_id).original_context==original
        assert service.store.prediction(prediction.prediction_id).original_context_hash==prediction.original_context_hash
        historical=service.store.prediction(prediction.prediction_id,prediction.created_at+timedelta(milliseconds=100))
        assert historical.status=="OPEN" and historical.evaluation_id is None
        api=client.get(f"/api/v1/learning/predictions/{prediction.prediction_id}",params={"as_of":(prediction.created_at+timedelta(milliseconds=100)).isoformat()})
        assert api.status_code==200 and api.json()["evaluations"]==[]
        journal=service.journal(JournalDraft(category="lesson",title="SYNTHETIC_TEST: preserved expectation",
            notes="Synthetic owner note: stale baseline remains documented, not current evidence.",
            failure_category="stale_data",manifest_id=manifest,as_of=datetime.now(timezone.utc),
            links=LearningLinks(prediction_id=prediction.prediction_id),classification="SYNTHETIC_TEST",tags=["fixture"]))
        journal_ids.append(journal.entry_id)
        revised=service.store.revise_journal(journal.entry_id,JournalRevision(expected_revision=1,
            reason="Add a clearly later research lesson",draft=JournalDraft(category="lesson",
                title=journal.title,notes="Later note does not replace original belief.",manifest_id=manifest,
                as_of=datetime.now(timezone.utc),classification="SYNTHETIC_TEST")),{})
        assert revised.revision==2 and service.store.journal(journal.entry_id,1).notes==journal.notes
        just_before=service.store.journals(as_of=revised.recorded_at-timedelta(microseconds=1))
        assert next(e for e in just_before if e.entry_id==journal.entry_id).revision==1
        at_revision=service.store.journals(as_of=revised.recorded_at)
        assert next(e for e in at_revision if e.entry_id==journal.entry_id).revision==2
        assert len(service.store.journal_history(journal.entry_id))==2
        with pytest.raises(ValueError,match="JOURNAL_REVISION_CONFLICT"):
            service.store.revise_journal(journal.entry_id,JournalRevision(expected_revision=1,
                reason="Reject concurrent stale revision",draft=JournalDraft(category="review",title="Stale correction",
                    manifest_id=manifest,as_of=datetime.now(timezone.utc),classification="SYNTHETIC_TEST")),{})
        postmortem=service.postmortem(prediction.prediction_id)
        assert postmortem.author=="cortex_template" and postmortem.links.prediction_id==prediction.prediction_id
        assert "no trade" in postmortem.structured_content["execution"]
        report=service.performance(as_of=datetime.now(timezone.utc),classification="SYNTHETIC_TEST")
        cohort=next(g for g in report["groups"] if str(prediction.prediction_id) in g["prediction_ids"])
        assert cohort["registration"]=="RETROSPECTIVE_EVALUATION" and cohort["detector_version"]==prediction.detector_version
        assert sum(cohort["outcomes"].values())==cohort["N"]
        assert cohort["N"]==cohort["usable_N"]+cohort["missing_inconclusive_N"]+cohort["excluded_quality_N"]
        assert "SMALL_SAMPLE_NO_EDGE_CLAIM" in cohort["warnings"]
        assert report["candidate_ledger_N"]==sum(row["N"] for row in report["candidate_ledger"])
        assert any(row["outcome"]=="rejected" for row in report["candidate_ledger"])
        edge=service.edge(EdgeDraft(title="SYNTHETIC_TEST: relative return hypothesis",hypothesis="Test-only hypothesis with insufficient sample size",
            detector_id=prediction.detector_id,detector_version=prediction.detector_version,
            registration="RETROSPECTIVE_EVALUATION",classification="SYNTHETIC_TEST"))
        edge_ids.append(edge["edge_id"])
        assert edge["status"]=="HYPOTHESIS" and "NOT_A_PROVEN_EDGE" in edge["warnings"]
        research=client.post("/api/v1/cortex/research",json={"question":"What actually happened to this prediction and what can we learn?",
            "mode":"pinned","manifest_id":str(manifest),"as_of":datetime.now(timezone.utc).isoformat(),
            "prediction_id":str(prediction.prediction_id),"depth":"quick"})
        assert research.status_code==200,research.text
        run=research.json();run_ids.append(run["run_id"])
        assert any(t["tool_id"]=="learning.prediction" and t["status"]=="ok" for t in run["tools"])
        assert any("Observed evaluation metric" in claim["text"] for claim in run["claims"])
        assert all(claim["evidence_ids"] for claim in run["claims"])
        assert client.get(f"/api/v1/cortex/runs/{run['run_id']}/replay").json()["evidence_reproducible"] is True
        class CloudGateway:
            locality="cloud"
            called=False
            def select_claims(self,*args):
                self.called=True
                raise AssertionError("Private journal must never reach cloud model")
        cloud=CloudGateway()
        private=CortexService(service.catalog,Settings(DSN,Path(ROOT),"Asia/Kolkata","INR",True,True,"PILOT_TEST"),gateway=cloud).research(
            ResearchRequest(question="Show my private journal lesson and prediction outcome",mode="pinned",manifest_id=manifest,
                as_of=datetime.now(timezone.utc),journal_entry_id=journal.entry_id,prediction_id=prediction.prediction_id,depth="quick"),persist=False)
        assert cloud.called is False and "MODEL_BLOCKED_BY_PRIVACY_POLICY" in private.warnings
        future=service.create_prediction(request.model_copy(update={"baseline_session":latest,"horizon_sessions":20,
            "title":"SYNTHETIC_TEST: future outcome is not invented"}))
        prediction_ids.append(future.prediction_id)
        pending=service.evaluate(future.prediction_id,EvaluationRequest(manifest_id=manifest,as_of=datetime.now(timezone.utc)))
        assert pending.status=="PENDING_EVALUATION" and pending.metric_value is None
        cancelled=service.store.cancel(future.prediction_id,"Owner cancels the synthetic pending example")
        assert cancelled.status=="CANCELLED"
        with pytest.raises(ValueError,match="CANCELLED_PREDICTION_CANNOT_EVALUATE"):
            service.evaluate(future.prediction_id,evaluation_request)
        with pytest.raises((ValueError,LookupError),match="LINK_CONTEXT_NOT_VISIBLE_AT_CUTOFF|LINK_PREDICTION_NOT_VISIBLE"):
            service.freeze_links(LearningLinks(prediction_id=prediction.prediction_id),manifest,
                prediction.created_at-timedelta(seconds=1),"SYNTHETIC_TEST")
    finally:
        with connect(DSN) as connection:
            for run_id in run_ids:
                connection.execute("DELETE FROM cortex_research_runs WHERE run_id=%s",(run_id,))
            for entry_id in journal_ids:
                connection.execute("DELETE FROM journal_revisions WHERE entry_id=%s",(entry_id,))
                connection.execute("DELETE FROM journal_entries WHERE entry_id=%s",(entry_id,))
            for prediction_id in prediction_ids:
                connection.execute("DELETE FROM prediction_revisions WHERE prediction_id=%s",(prediction_id,))
                connection.execute("DELETE FROM prediction_evaluations WHERE prediction_id=%s",(prediction_id,))
                connection.execute("DELETE FROM prediction_records WHERE prediction_id=%s",(prediction_id,))
            for edge_id in edge_ids:
                connection.execute("DELETE FROM edge_library WHERE edge_id=%s",(edge_id,))


def test_synthetic_records_refuse_owner_environment(pilot):
    with pytest.raises(ValueError,match="SYNTHETIC_LEARNING_REQUIRES_TEST_DATABASE"):
        LearningStore(DSN,"OWNER_MAIN").guard("SYNTHETIC_TEST")


def test_prior_horizon_cannot_be_claimed_as_pre_registered(pilot):
    service,_=pilot
    context=build_context(service.catalog,as_of=datetime.now(timezone.utc))
    with pytest.raises(ValueError,match="HORIZON_ALREADY_STARTED_USE_RETROSPECTIVE"):
        service.create_prediction(PredictionDefinition(title="Reject hindsight registration",prediction_type="forward_return",
            symbol="BTCUSDT",horizon_sessions=5,comparator="gt",threshold="0",manifest_id=context["source_manifest_id"],
            as_of=datetime.now(timezone.utc),baseline_session=date.fromisoformat(context["evaluation_date"])-timedelta(days=10),
            classification="SYNTHETIC_TEST"))
