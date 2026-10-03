"""Opt-in read-only workstation acceptance against the existing Binance pilot.

Both variables must target the isolated *_test pilot catalog and its Parquet root.
This test does not ingest data or mutate the catalog.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from psycopg.conninfo import conninfo_to_dict

from market_cortex.api import create_app
from market_cortex.database import connect
from market_cortex.storage import ArtifactStore, PostgresCatalog


DSN = os.environ.get("MARKET_CORTEX_PHASE3_PILOT_DSN")
ROOT = os.environ.get("MARKET_CORTEX_PHASE3_PILOT_DATA_ROOT")
SAFE = bool(DSN and ROOT and
            conninfo_to_dict(DSN).get("dbname", "").lower().endswith("_test") and
            Path(ROOT).is_dir())


@pytest.mark.skipif(not SAFE, reason="isolated Phase 3 pilot DB and Parquet root required")
def test_workstation_read_models_are_pinned_and_historical():
    catalog = PostgresCatalog(DSN, ArtifactStore(Path(ROOT)))
    client = TestClient(create_app(catalog=catalog))
    cutoff = datetime.now(timezone.utc).isoformat()

    health = client.get("/api/v1/health").json()
    assert health["status"] == "ready"
    context_response = client.get("/api/v1/workstation/context", params={"as_of": cutoff})
    assert context_response.status_code == 200
    ctx = context_response.json()
    assert ctx["universe_label"] == "Binance Pilot 5"
    assert [member["symbol"] for member in ctx["members"]] == [
        "BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT"]
    assert all(member["observed_sessions"] >= 390 for member in ctx["members"])
    assert [provider["status"] for provider in ctx["providers"]] == [
        "VALIDATED_PUBLIC", "DEFERRED_NOT_CONFIGURED", "DEFERRED_NOT_CONFIGURED"]

    pinned = {"manifest_id": ctx["source_manifest_id"], "as_of": ctx["as_of"]}
    overview = client.get("/api/v1/workstation/overview", params=pinned)
    assert overview.status_code == 200
    result = overview.json()
    assert len(result["items"]) == 5
    assert result["state"]["source_manifest_id"] == ctx["source_manifest_id"]
    assert result["items"][0]["features"]["rsi"]["value"] is not None

    btc = ctx["members"][0]
    period = {**pinned, "from": ctx["history_start"], "to": ctx["evaluation_date"]}
    chart = client.get(f"/api/v1/workstation/instrument/{btc['instrument_id']}", params=period)
    assert chart.status_code == 200
    chart_data = chart.json()
    assert len(chart_data["bars"]) == btc["observed_sessions"]
    assert chart_data["features"]["rsi_14"]["points"][-1]["value"] is not None
    assert chart_data["features"]["sma_20"]["points"][-1]["value"] is not None
    assert chart_data["bars"][-1]["observation_id"]

    compare = client.get("/api/v1/workstation/comparison", params={
        **period, "window": 60,
        "instrument_ids": [ctx["members"][0]["instrument_id"], ctx["members"][1]["instrument_id"]]})
    assert compare.status_code == 200
    assert compare.json()["matrix"][0][1]["count"] == 60
    assert compare.json()["alignment_policy"] == "same_session"

    manifest = client.get(f"/api/v1/workstation/manifest/{ctx['source_manifest_id']}")
    assert manifest.status_code == 200
    assert manifest.json()["rows_in_files"] >= 1950
    assert manifest.json()["storage"]["corrupt"] == []

    with connect(DSN) as connection:
        oldest = connection.execute("SELECT manifest_id FROM dataset_manifests ORDER BY created_at ASC LIMIT 1").fetchone()[0]
        earliest_arrival = connection.execute("SELECT min(available_at) FROM observations").fetchone()[0]
    old_ctx = client.get("/api/v1/workstation/context", params={
        "manifest_id": str(oldest), "as_of": cutoff})
    assert old_ctx.status_code == 200
    assert old_ctx.json()["source_manifest_id"] == str(oldest)
    assert sum(member["observed_sessions"] for member in old_ctx.json()["members"]) < 1950

    early_ctx = client.get("/api/v1/workstation/context", params={
        "manifest_id": ctx["source_manifest_id"], "as_of": earliest_arrival.isoformat()})
    assert early_ctx.status_code == 200
    assert sum(member["observed_sessions"] for member in early_ctx.json()["members"]) < 1950

    assert client.get("/api/v1/workstation/context", params={"as_of": "2026-10-01T00:00:00"}).status_code == 422
    assert client.get("/api/v1/workstation/manifest/00000000-0000-0000-0000-000000000001").status_code == 404
    assert client.post("/api/v1/workstation/context").status_code == 405
