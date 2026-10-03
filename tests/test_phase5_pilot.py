"""Opt-in Phase 5 validation against the isolated pilot *_test PostgreSQL catalog."""

from __future__ import annotations

import os
from datetime import datetime, timedelta
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from psycopg.conninfo import conninfo_to_dict

from market_cortex.api import create_app
from market_cortex.config import Settings
from market_cortex.database import connect
from market_cortex.opportunity import OpportunityService
from market_cortex.opportunity_contracts import ScanRequest
from market_cortex.opportunity_store import OpportunityStore
from market_cortex.storage import ArtifactStore, PostgresCatalog


DSN = os.environ.get("MARKET_CORTEX_PHASE5_PILOT_DSN")
ROOT = os.environ.get("MARKET_CORTEX_PHASE5_PILOT_DATA_ROOT")
SAFE = bool(DSN and ROOT and
            conninfo_to_dict(DSN).get("dbname", "").lower().endswith("_test") and Path(ROOT).is_dir())


@pytest.fixture
def pilot():
    if not SAFE:
        pytest.skip("dedicated Phase 5 pilot *_test catalog and matching Parquet root required")
    root = Path(ROOT)
    catalog = PostgresCatalog(DSN, ArtifactStore(root))
    settings = Settings(DSN, root, "Asia/Kolkata", "INR", False, True, "PILOT_TEST")
    return catalog, TestClient(create_app(settings=settings, catalog=catalog))


def test_live_pilot_scan_dedup_historical_and_candidate_review(pilot):
    catalog, client = pilot
    context = client.get("/api/v1/workstation/context").json()
    request = {"mode": "latest", "manifest_id": context["source_manifest_id"],
               "as_of": context["as_of"], "record": True}
    first = client.post("/api/v1/opportunities/scan", json=request)
    assert first.status_code == 200, first.text
    result = first.json()
    assert len(result["candidates"]) == 40
    assert result["counts"]["candidate"] > 0
    assert result["counts"]["rejected"] > 0
    assert result["counts"]["unsupported"] == 1  # BTC versus itself
    assert result["unavailable_members"] == []
    second = client.post("/api/v1/opportunities/scan", json=request).json()
    assert second["scan_id"] == result["scan_id"]
    assert second["recorded_events"] == 0
    assert [item["candidate_id"] for item in second["candidates"]] == [
        item["candidate_id"] for item in result["candidates"]]
    assert [item["evidence_hash"] for item in second["candidates"]] == [
        item["evidence_hash"] for item in result["candidates"]]
    candidate = next(item for item in result["candidates"] if
                     item["outcome"] == "candidate" and item["symbol"] == "BTCUSDT")
    stored = client.get(f"/api/v1/opportunities/candidates/{candidate['candidate_id']}")
    assert stored.status_code == 200
    assert stored.json()["candidate_id"] == candidate["candidate_id"]
    assert stored.json()["source_manifest_id"] == candidate["source_manifest_id"]
    assert datetime.fromisoformat(stored.json()["as_of"]) <= datetime.fromisoformat(candidate["as_of"])
    created = client.post("/api/v1/opportunities/theses", json={"candidate_id": candidate["candidate_id"]})
    assert created.status_code == 200
    thesis_id = created.json()["thesis_id"]
    review = client.post(f"/api/v1/opportunities/theses/{thesis_id}/review")
    assert review.status_code == 200, review.text
    reviewed = review.json()
    assert reviewed["review_status"] == "GROUNDED_RESEARCH_ATTACHED"
    assert candidate["candidate_id"] in reviewed["run"]["answer"]
    assert any(tool["tool_id"] == "opportunity.candidate" and tool["status"] == "ok"
               for tool in reviewed["run"]["tools"])
    candidate_tool = next(tool for tool in reviewed["run"]["tools"]
                          if tool["tool_id"] == "opportunity.candidate")
    assert candidate_tool["evidence"][0]["source_as_of"] == stored.json()["as_of"]
    assert reviewed["thesis"]["status"] == created.json()["status"]
    replay = client.get(f"/api/v1/cortex/runs/{reviewed['run']['run_id']}/replay")
    assert replay.status_code == 200 and replay.json()["evidence_reproducible"] is True

    with connect(DSN) as connection:
        old_manifest, created_at = connection.execute("""SELECT manifest_id, created_at
            FROM dataset_manifests ORDER BY created_at LIMIT 1""").fetchone()
    historical = client.post("/api/v1/opportunities/scan", json={"mode": "historical",
        "manifest_id": str(old_manifest), "as_of": (created_at + timedelta(seconds=5)).isoformat(),
        "symbol": "BTCUSDT", "detector_id": "momentum"})
    assert historical.status_code == 200, historical.text
    past = historical.json()["candidates"][0]
    assert past["event_date"] < candidate["event_date"]
    assert past["outcome"] == "insufficient_data"
    assert all(item["session_date"] <= past["event_date"]
               for item in past["evidence"] if item["session_date"])
    future_manifest = client.post("/api/v1/opportunities/scan", json={"mode": "historical",
        "manifest_id": context["source_manifest_id"],
        "as_of": (created_at - timedelta(seconds=1)).isoformat(),
        "symbol": "BTCUSDT", "detector_id": "momentum"})
    assert future_manifest.status_code == 422
    assert future_manifest.json()["detail"]["code"] == "MANIFEST_NOT_YET_KNOWN_AT_CUTOFF"

    comparison = client.post("/api/v1/cortex/research", json={
        "question": "Compare BTC opportunities with the earlier manifest",
        "mode": "pinned", "manifest_id": context["source_manifest_id"],
        "older_manifest_id": str(old_manifest), "as_of": context["as_of"],
        "symbol": "BTCUSDT", "depth": "quick"})
    assert comparison.status_code == 200, comparison.text
    compared = comparison.json()
    opportunity_tools = [tool for tool in compared["tools"] if tool["tool_id"] == "opportunity.scan"]
    assert len(opportunity_tools) == 2 and all(tool["status"] == "ok" for tool in opportunity_tools)
    paired_claims = [claim for claim in compared["claims"] if "opportunity changed" in claim["text"]]
    assert paired_claims and all(len(claim["evidence_ids"]) == 2 for claim in paired_claims)
    assert str(old_manifest) in compared["answer"]

    parent_id = context["manifest"]["parent_manifest_id"]
    assert parent_id
    previous = client.post("/api/v1/cortex/research", json={
        "question": "Compare BTC opportunities with the previous manifest",
        "mode": "pinned", "manifest_id": context["source_manifest_id"],
        "as_of": context["as_of"], "symbol": "BTCUSDT", "depth": "quick"})
    assert previous.status_code == 200, previous.text
    previous_tools = [tool for tool in previous.json()["tools"] if tool["tool_id"] == "opportunity.scan"]
    assert {tool["inputs"]["manifest_id"] for tool in previous_tools} == {
        context["source_manifest_id"], parent_id}


def test_synthetic_thesis_invalidation_version_history_and_owner_guard(pilot):
    catalog, client = pilot
    service, store = OpportunityService(catalog), OpportunityStore(DSN)
    scan = service.scan(ScanRequest(symbol="BTCUSDT", detector_id="momentum"))
    real = scan.candidates[0]
    # Lifecycle fixture: statuses are deliberately set to exercise state transitions,
    # and are never described as live detector output.
    first = real.model_copy(update={"candidate_id": uuid4(), "status": "VALID",
                                    "evidence_hash": uuid4().hex})
    later = real.model_copy(update={"candidate_id": uuid4(), "status": "AVOID",
        "outcome": "rejected", "as_of": real.as_of + timedelta(seconds=1),
        "evidence_hash": uuid4().hex, "rejection_reasons": ["SYNTHETIC_INVALIDATION"]})
    thesis_id = None
    try:
        fixture_scan = scan.model_copy(update={"scan_id": uuid4(), "candidates": [first, later]})
        assert store.record_scan(fixture_scan) == 2
        thesis = store.create_thesis(first.candidate_id)
        thesis_id = thesis.thesis_id
        assert thesis.status == "VALID" and thesis.version == 1
        invalidated = store.advance(thesis_id, later)
        assert invalidated.status == "INVALIDATED" and invalidated.version == 2
        assert invalidated.transitions[-1].actor == "detector"
        assert store.advance(thesis_id, later).version == 2
        assert store.thesis(thesis_id, 1).status == "VALID"
        assert [item.version for item in store.versions(thesis_id)] == [1, 2]
        response = client.post(f"/api/v1/opportunities/theses/{thesis_id}/decision",
                               json={"status": "VALID", "reason": "Owner may not declare VALID"})
        assert response.status_code == 422
        reopened = client.post(f"/api/v1/opportunities/theses/{thesis_id}/decision",
                               json={"status": "WATCHING", "reason": "New evidence warrants renewed observation"})
        assert reopened.status_code == 200
        assert reopened.json()["version"] == 3
        assert reopened.json()["transitions"][-1]["actor"] == "owner"
        comparison = client.get(f"/api/v1/opportunities/theses/{thesis_id}/comparison",
                                params={"from_version": 1, "to_version": 2})
        assert comparison.status_code == 200
        assert comparison.json()["from_status"] == "VALID"
        assert comparison.json()["to_status"] == "INVALIDATED"
    finally:
        with connect(DSN) as connection:
            if thesis_id:
                connection.execute("DELETE FROM research_thesis_versions WHERE thesis_id=%s", (thesis_id,))
                connection.execute("DELETE FROM research_theses WHERE thesis_id=%s", (thesis_id,))
            connection.execute("DELETE FROM opportunity_candidates WHERE candidate_id IN (%s,%s)",
                               (first.candidate_id, later.candidate_id))
