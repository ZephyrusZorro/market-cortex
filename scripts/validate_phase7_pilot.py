"""Persist one explicitly synthetic Phase 7 demonstration in a guarded test catalog."""
from __future__ import annotations

import json
import sys
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"src"))

from market_cortex.config import Settings
from market_cortex.cortex import CortexService
from market_cortex.cortex_contracts import ResearchRequest
from market_cortex.learning import LearningService
from market_cortex.learning_contracts import (EdgeDraft,EvaluationRequest,JournalDraft,
    LearningLinks,PredictionDefinition)
from market_cortex.opportunity_store import OpportunityStore
from market_cortex.risk import RiskService
from market_cortex.storage import ArtifactStore,PostgresCatalog
from market_cortex.workstation import build_context


def main():
    started=time.perf_counter()
    settings=Settings.load()
    catalog=PostgresCatalog(settings.database_url,ArtifactStore(settings.data_root))
    service=LearningService(catalog,settings.environment)
    service.store.guard("SYNTHETIC_TEST")
    context=build_context(catalog,as_of=datetime.now(timezone.utc))
    latest=date.fromisoformat(context["evaluation_date"])
    thesis=next((t for t in OpportunityStore(catalog.dsn).recent_theses(symbol="BTCUSDT")
                 if t.source_manifest_id in RiskService(catalog,settings.environment)._manifest_ancestors(catalog.head())),None)
    if thesis is None:
        raise ValueError("VISIBLE_PHASE5_BTC_THESIS_REQUIRED")
    # No automatic daemon or detector-wide prediction creation. These are three explicit fixtures.
    definitions=[("forward_return",None,latest-timedelta(days=10),"RETROSPECTIVE_EVALUATION"),
                 ("relative_performance","ETHUSDT",latest-timedelta(days=10),"RETROSPECTIVE_EVALUATION"),
                 ("forward_return",None,latest,"PRE_REGISTERED")]
    measurements=[]
    first=None
    for kind,benchmark,baseline,registration in definitions:
        record=service.create_prediction(PredictionDefinition(
            title=f"SYNTHETIC_TEST_PHASE7: BTC {kind} five-session {registration}",
            symbol="BTCUSDT",benchmark_symbol=benchmark,prediction_type=kind,
            horizon_sessions=5,comparator="gt",threshold="0",baseline_session=baseline,
            registration=registration,classification="SYNTHETIC_TEST",
            manifest_id=context["source_manifest_id"],as_of=datetime.now(timezone.utc),
            links=LearningLinks(thesis_id=thesis.thesis_id,candidate_id=thesis.candidate.candidate_id)))
        outcome=service.evaluate(record.prediction_id,EvaluationRequest(
            manifest_id=context["source_manifest_id"],as_of=datetime.now(timezone.utc)))
        measurements.append({"prediction_id":str(record.prediction_id),"registration":record.registration,
            "baseline_session":str(record.baseline_session),"due_session":str(record.due_session),
            "status":outcome.status,"metric_value":str(outcome.metric_value) if outcome.metric_value is not None else None,
            "observed_sessions":outcome.observed_sessions,"expected_sessions":outcome.expected_sessions,
            "source_freshness":outcome.prediction_freshness,"warnings":outcome.warnings})
        first=first or record
    template=service.postmortem(first.prediction_id)
    journal=service.journal(template)
    lesson=service.journal(JournalDraft(category="lesson",title="SYNTHETIC_TEST_PHASE7: retrospective evidence boundary",
        notes="Synthetic demonstration note: this historical outcome was already observable at registration and cannot establish forecasting accuracy.",
        classification="SYNTHETIC_TEST",failure_category="other_owner_observation",
        manifest_id=context["source_manifest_id"],as_of=datetime.now(timezone.utc),
        links=LearningLinks(prediction_id=first.prediction_id,thesis_id=thesis.thesis_id),tags=["synthetic-fixture","phase7"]))
    report_start=time.perf_counter()
    report=service.performance(as_of=datetime.now(timezone.utc),classification="SYNTHETIC_TEST")
    report_seconds=time.perf_counter()-report_start
    edge=service.edge(EdgeDraft(title="SYNTHETIC_TEST_PHASE7: momentum research hypothesis",
        hypothesis="A small retrospective sample is a hypothesis requiring pre-registered independent validation.",
        detector_id=first.detector_id,detector_version=first.detector_version,
        registration="RETROSPECTIVE_EVALUATION",classification="SYNTHETIC_TEST"))
    cortex=CortexService(catalog,settings)
    run=cortex.research(ResearchRequest(question="What actually happened to this BTC prediction and what can honestly be learned?",
        mode="pinned",manifest_id=context["source_manifest_id"],as_of=datetime.now(timezone.utc),
        prediction_id=first.prediction_id,depth="quick"))
    replay=cortex.replay(run.run_id)
    print(json.dumps({"classification":"SYNTHETIC_TEST","source_manifest":context["source_manifest_id"],
        "latest_stored_session":str(latest),"measurements":measurements,
        "journal_id":str(journal.entry_id),"lesson_id":str(lesson.entry_id),"thesis_id":str(thesis.thesis_id),
        "prediction_N":report["prediction_N"],"usable_N":report["usable_N"],
        "candidate_rejection_ledger_N":report["candidate_ledger_N"],
        "groups":[{k:v for k,v in g.items() if k in ("detector_id","detector_version","registration",
            "prediction_type","N","usable_N","outcomes","forward_return","warnings")} for g in report["groups"]],
        "edge_id":edge["edge_id"],"edge_status":edge["status"],"cortex_run_id":str(run.run_id),
        "cortex_evidence_reproducible":replay["evidence_reproducible"],
        "performance_report_seconds":round(report_seconds,3),"pipeline_seconds":round(time.perf_counter()-started,3)},indent=2))


if __name__=="__main__":
    main()
