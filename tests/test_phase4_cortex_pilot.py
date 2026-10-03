"""Opt-in Phase 4 live pilot gate; writes research runs only to a *_test catalog."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from psycopg.conninfo import conninfo_to_dict

from market_cortex.api import create_app
from market_cortex.config import Settings
from market_cortex.cortex import CortexService
from market_cortex.cortex_contracts import ResearchRequest
from market_cortex.cortex_gateway import ModelResult
from market_cortex.database import connect
from market_cortex.storage import ArtifactStore, PostgresCatalog


DSN = os.environ.get("MARKET_CORTEX_PHASE4_PILOT_DSN")
ROOT = os.environ.get("MARKET_CORTEX_PHASE4_PILOT_DATA_ROOT")
SAFE = bool(DSN and ROOT and
            conninfo_to_dict(DSN).get("dbname", "").lower().endswith("_test") and Path(ROOT).is_dir())


@pytest.mark.skipif(not SAFE, reason="dedicated Phase 4 pilot *_test database and matching Parquet root required")
def test_real_pilot_research_persistence_grounding_and_replay():
    root = Path(ROOT)
    catalog = PostgresCatalog(DSN, ArtifactStore(root))
    settings = Settings(DSN, root, "Asia/Kolkata", "INR", False, True, "PILOT_TEST")
    service = CortexService(catalog, settings)
    with connect(DSN) as connection:
        old_manifest = connection.execute("SELECT manifest_id FROM dataset_manifests ORDER BY created_at ASC LIMIT 1").fetchone()[0]

    btc = service.research(ResearchRequest(question="Analyze BTCUSDT.", symbol="BTCUSDT"))
    assert btc.failure_state is None
    assert btc.model_provider == "deterministic"
    assert btc.context.environment == "PILOT_TEST"
    assert any(item.kind == "observation" and item.symbol == "BTCUSDT"
               for tool in btc.tools for item in tool.evidence)
    assert any(item.stance == "counter" and "momentum" in item.text for item in btc.claims)
    ids = {item.evidence_id for tool in btc.tools for item in tool.evidence}
    assert all(set(claim.evidence_ids) <= ids for claim in btc.claims)
    assert service.store.get(btc.run_id).evidence_hash == btc.evidence_hash
    assert service.replay(btc.run_id)["evidence_reproducible"] is True

    prior = service.research(ResearchRequest(
        question="What did we conclude about BTC previously?", symbol="BTCUSDT"))
    history = [item for tool in prior.tools for item in tool.evidence
               if item.kind == "prior_run" and item.source_id == str(btc.run_id)]
    assert history and history[0].source_manifest_id == btc.context.manifest_id
    assert history[0].source_as_of == btc.context.as_of
    assert "historical context only" in prior.answer
    assert service.replay(prior.run_id)["evidence_reproducible"] is True

    compare = service.research(ResearchRequest(question="Compare ETHUSDT with BTCUSDT.",
                                               symbol="ETHUSDT", compare_symbol="BTCUSDT"))
    assert any(tool.tool_id == "asset.compare" and tool.status == "ok" for tool in compare.tools)
    assert "Pearson correlation" in compare.answer or "relative-strength" in compare.answer
    relative = next(item for tool in compare.tools for item in tool.evidence
                    if tool.tool_id == "asset.compare" and item.label == "relative_strength")
    assert relative.unit == "fractional_outperformance"
    assert ("ETHUSDT led" if relative.value > 0 else "BTCUSDT led") in compare.answer

    earlier = service.research(ResearchRequest(question="What changed in BTC compared with an earlier manifest?",
        symbol="BTCUSDT", older_manifest_id=old_manifest))
    assert any(tool.inputs["manifest_id"] == str(old_manifest) for tool in earlier.tools)
    assert service.replay(earlier.run_id)["evidence_reproducible"] is True

    historical = service.research(ResearchRequest(question="Analyze BTC as of June 1, 2025.", symbol="BTCUSDT"))
    assert historical.context.mode == "historical"
    assert historical.failure_state == "INSUFFICIENT_EVIDENCE"
    assert not any(item.kind == "observation" for tool in historical.tools for item in tool.evidence)
    assert "84,880.05" not in historical.answer

    class InvalidLocalModel:
        provider = "fake_local"
        locality = "local"
        def select_claims(self, question, candidates):
            return ModelResult(("invented-number-claim",), self.provider, "fake", 0)
    mocked = CortexService(catalog, settings, gateway=InvalidLocalModel()).research(
        ResearchRequest(question="Analyze BTCUSDT.", symbol="BTCUSDT"))
    assert "LOCAL_MODEL_UNAVAILABLE_OR_INVALID" in mocked.warnings
    assert mocked.model_provider == "deterministic"
    assert "invented-number-claim" not in mocked.answer

    client = TestClient(create_app(settings=settings, catalog=catalog))
    status = client.get("/api/v1/cortex/status")
    assert status.status_code == 200 and status.json()["environment"] == "PILOT_TEST"
    assert client.get("/api/v1/cortex/tools").status_code == 200
    assert client.get(f"/api/v1/cortex/runs/{btc.run_id}").json()["run_id"] == str(btc.run_id)
    assert client.get(f"/api/v1/cortex/runs/{btc.run_id}/replay").json()["evidence_reproducible"] is True
    assert client.get("/api/v1/cortex/runs", params={"symbol": "BTCUSDT"}).json()["items"]
    assert client.post("/api/v1/cortex/research", json={"question": "x", "mode": "latest"}).status_code == 422
