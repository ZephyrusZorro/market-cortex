"""Opt-in Phase 6 validation against an isolated *_test Binance pilot catalog."""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from psycopg.conninfo import conninfo_to_dict

from market_cortex.api import create_app
from market_cortex.config import Settings
from market_cortex.database import connect
from market_cortex.features import FeatureEngine
from market_cortex.opportunity_store import OpportunityStore
from market_cortex.portfolio_store import PortfolioStore
from market_cortex.risk import RiskService, money, run_scenario, snapshot_identity
from market_cortex.risk_contracts import (OverlayRequest, PortfolioCreate, PositionChange,
    PositionInput, RiskRequest, ScenarioDefinition)
from market_cortex.storage import ArtifactStore, PostgresCatalog
from market_cortex.workstation import build_context


DSN = os.environ.get("MARKET_CORTEX_PHASE6_PILOT_DSN")
ROOT = os.environ.get("MARKET_CORTEX_PHASE6_PILOT_DATA_ROOT")
SAFE = bool(DSN and ROOT and
            conninfo_to_dict(DSN).get("dbname", "").lower().endswith("_test") and Path(ROOT).is_dir())


@pytest.fixture
def pilot():
    if not SAFE:
        pytest.skip("dedicated Phase 6 *_test catalog and matching Parquet root required")
    catalog = PostgresCatalog(DSN, ArtifactStore(Path(ROOT)))
    settings = Settings(DSN, Path(ROOT), "Asia/Kolkata", "INR", False, True, "PILOT_TEST")
    return RiskService(catalog, "PILOT_TEST"), TestClient(create_app(settings=settings, catalog=catalog))


def test_synthetic_pilot_exposure_heat_correlation_scenario_overlay_and_history(pilot, monkeypatch):
    service, client = pilot
    context = build_context(service.catalog, as_of=datetime.now(timezone.utc))
    portfolio = service.store.create(PortfolioCreate(name="SYNTHETIC_TEST_PORTFOLIO_PHASE6",
        base_currency="USDT", capital=Decimal("100000"),
        classification="SYNTHETIC_TEST_PORTFOLIO"))
    run_ids = []
    try:
        for symbol, quantity in (("BTCUSDT", "0.1"), ("ETHUSDT", "2"), ("SOLUSDT", "10")):
            member = next(item for item in context["members"] if item["symbol"] == symbol)
            session = datetime.fromisoformat(member["last_session"]).date()
            series = FeatureEngine(service.catalog).load(instrument_id=UUID(member["instrument_id"]),
                start_date=session, end_date=session, as_of=datetime.now(timezone.utc),
                manifest_id=UUID(context["source_manifest_id"]), provider_id="binance")
            price = Decimal(str(series.bars[-1].close))
            position = PositionInput(instrument_id=UUID(member["instrument_id"]),
                quantity=Decimal(quantity), average_cost=price*Decimal("0.95"),
                invalidation_price=price*Decimal("0.90"), native_currency="USDT",
                opened_at=datetime.now(timezone.utc), source_type="synthetic_fixture")
            service.validate_position(position, portfolio)
            portfolio = service.store.change(portfolio.portfolio_id, PositionChange(action="add",
                position=position, reason=f"Synthetic {symbol} Phase 6 validation"))
        assert portfolio.version == 4
        assert [row["action"] for row in service.store.versions(portfolio.portfolio_id)] == [
            "created", "position_added", "position_added", "position_added"]
        assert service.store.get(portfolio.portfolio_id, 1).positions == []
        snapshot = service.snapshot(portfolio.portfolio_id, RiskRequest(
            manifest_id=UUID(context["source_manifest_id"]), persist=True))
        assert snapshot.portfolio_classification == "SYNTHETIC_TEST_PORTFOLIO"
        assert snapshot.exposure.gross > 0 and snapshot.heat_amount > 0
        assert snapshot.heat_percent == money(snapshot.heat_amount / snapshot.capital)
        assert snapshot_identity(snapshot) == snapshot.snapshot_id
        assert snapshot_identity(snapshot.model_copy(update={
            "correlation_cluster_flags":["CHANGED_EVIDENCE"]})) != snapshot.snapshot_id
        assert len(snapshot.correlations) == 3
        assert all(row["sample_count"] >= 60 for row in snapshot.correlations)
        assert snapshot.price_freshness in {"current", "stale"}
        assert {item.price_session for item in snapshot.positions} == {
            datetime.fromisoformat(next(member for member in context["members"]
                if member["symbol"] == item.symbol)["last_session"]).date().isoformat()
            for item in snapshot.positions}
        assert service.store.risk_snapshot(snapshot.snapshot_id)["snapshot_id"] == str(snapshot.snapshot_id)
        scenario = ScenarioDefinition(name="Pilot crypto -10%", kind="broad_crypto_shock",
            shocks={symbol: Decimal("-.1") for symbol in
                    ("BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT")})
        stressed = run_scenario(snapshot, scenario)
        assert stressed.portfolio_pnl == -(snapshot.exposure.gross*Decimal(".1"))
        assert sum(stressed.position_pnl.values()) == stressed.portfolio_pnl
        source = portfolio.positions[-1]
        extra = source.model_copy(update={"position_id":__import__("uuid").uuid4(),
            "quantity":Decimal("1")})
        overlay = service.overlay(portfolio.portfolio_id, OverlayRequest(
            risk=RiskRequest(manifest_id=snapshot.source_manifest_id, as_of=snapshot.as_of,
                             portfolio_version=portfolio.version),
            hypothetical_position=extra, scenario=scenario))
        assert overlay["label"] == "HYPOTHETICAL_RESEARCH_OVERLAY"
        assert overlay["delta_gross_exposure"] > 0 and overlay["delta_heat"] > 0
        assert Decimal(overlay["after_scenario"]["portfolio_pnl"]) < Decimal(
            overlay["before_scenario"]["portfolio_pnl"])
        api = client.post(f"/api/v1/risk/portfolios/{portfolio.portfolio_id}/calculate",
            json={"manifest_id":str(snapshot.source_manifest_id),"as_of":snapshot.as_of.isoformat(),
                  "portfolio_version":portfolio.version})
        assert api.status_code == 200, api.text
        assert api.json()["snapshot_id"] == str(snapshot.snapshot_id)
        assert client.get(f"/api/v1/risk/snapshots/{snapshot.snapshot_id}").status_code == 200
        research = client.post("/api/v1/cortex/research", json={
            "question":"What happens if BTC drops 10% in my portfolio?",
            "mode":"pinned", "manifest_id":str(snapshot.source_manifest_id),
            "as_of":snapshot.as_of.isoformat(), "portfolio_id":str(portfolio.portfolio_id),
            "depth":"quick"})
        assert research.status_code == 200, research.text
        run = research.json()
        run_ids.append(run["run_id"])
        assert {"risk.portfolio", "risk.scenario"} <= {item["tool_id"] for item in run["tools"]}
        assert "Explicit what-if portfolio P/L" in run["answer"]
        assert all(set(claim["evidence_ids"]) <= {e["evidence_id"] for tool in run["tools"]
                    for e in tool["evidence"]} for claim in run["claims"])
        assert client.get(f"/api/v1/cortex/runs/{run['run_id']}/replay").json()[
            "evidence_reproducible"] is True
        thesis = next((item for item in OpportunityStore(DSN).recent_theses(symbol="BTCUSDT")
            if item.updated_at <= snapshot.as_of and item.source_manifest_id in
                service._manifest_ancestors(snapshot.source_manifest_id)), None)
        assert thesis is not None, "Phase 5 pilot thesis required for linked CORTEX overlay"
        btc_price = next(item.reference_price for item in snapshot.positions
                         if item.symbol == "BTCUSDT")
        thesis_request = {"portfolio_id":str(portfolio.portfolio_id),
            "risk":{"manifest_id":str(snapshot.source_manifest_id),
                    "as_of":snapshot.as_of.isoformat(), "portfolio_version":portfolio.version},
            "quantity":"0.02", "reference_price":str(btc_price*Decimal("0.95")),
            "invalidation_price":str(btc_price*Decimal("0.90"))}
        invalid_levels = client.post(f"/api/v1/risk/theses/{thesis.thesis_id}/risk",
            json={**thesis_request, "invalidation_price":str(btc_price)})
        assert invalid_levels.status_code == 422
        # A later thesis head must not hide an earlier version at a pinned cutoff.
        thesis_versions = OpportunityStore(DSN).versions(thesis.thesis_id)
        future = thesis_versions[-1].model_copy(update={
            "version":thesis_versions[-1].version+1,
            "updated_at":snapshot.as_of+timedelta(days=1),
            "as_of":snapshot.as_of+timedelta(days=1)})
        original_thesis = OpportunityStore.thesis
        original_versions = OpportunityStore.versions
        with monkeypatch.context() as patch:
            patch.setattr(OpportunityStore, "thesis", lambda store, thesis_id, version=None:
                future if thesis_id == thesis.thesis_id and version is None
                else original_thesis(store, thesis_id, version))
            patch.setattr(OpportunityStore, "versions", lambda store, thesis_id:
                thesis_versions+[future] if thesis_id == thesis.thesis_id
                else original_versions(store, thesis_id))
            thesis_risk = client.post(f"/api/v1/risk/theses/{thesis.thesis_id}/risk", json=thesis_request)
            assert thesis_risk.status_code == 200, thesis_risk.text
            repeated = client.post(f"/api/v1/risk/theses/{thesis.thesis_id}/risk", json=thesis_request)
            assert repeated.json()["after"]["snapshot_id"] == thesis_risk.json()["after"]["snapshot_id"]
        stale = service.snapshot(portfolio.portfolio_id, RiskRequest(
            manifest_id=snapshot.source_manifest_id, as_of=snapshot.as_of+timedelta(days=8)))
        assert stale.price_freshness == "stale" and stale.market_state_freshness == "stale"
        assert "MARKET_STATE_NOT_CURRENT:stale" in stale.warnings
        overlay_research = client.post("/api/v1/cortex/research", json={
            "question":"How much risk does adding this BTC thesis create?",
            "mode":"pinned", "manifest_id":str(snapshot.source_manifest_id),
            "as_of":snapshot.as_of.isoformat(), "portfolio_id":str(portfolio.portfolio_id),
            "thesis_id":str(thesis.thesis_id), "overlay_quantity":"0.02",
            "overlay_reference_price":str(btc_price*Decimal("0.95")),
            "overlay_invalidation_price":str(btc_price*Decimal("0.90")),
            "scenario_shocks":{"BTCUSDT":"-0.1"}, "depth":"quick"})
        assert overlay_research.status_code == 200, overlay_research.text
        overlay_run = overlay_research.json()
        run_ids.append(overlay_run["run_id"])
        assert any(item["tool_id"] == "risk.overlay" and item["status"] == "ok"
                   for item in overlay_run["tools"])
        assert "hypothetical incremental portfolio heat" in overlay_run["answer"]
        assert client.get(f"/api/v1/cortex/runs/{overlay_run['run_id']}/replay").json()[
            "evidence_reproducible"] is True
        missing_assumptions = client.post("/api/v1/cortex/research", json={
            "question":"How much risk does adding this BTC thesis create?",
            "mode":"pinned", "manifest_id":str(snapshot.source_manifest_id),
            "as_of":snapshot.as_of.isoformat(), "portfolio_id":str(portfolio.portfolio_id),
            "thesis_id":str(thesis.thesis_id), "depth":"quick"})
        assert missing_assumptions.status_code == 422
        assert missing_assumptions.json()["detail"]["code"] == "HYPOTHETICAL_QUANTITY_AND_ENTRY_REQUIRED"
        historical = service.snapshot(portfolio.portfolio_id, RiskRequest(
            manifest_id=UUID(context["manifest"]["parent_manifest_id"]),
            as_of=datetime.now(timezone.utc), portfolio_version=portfolio.version))
        assert historical.source_manifest_id != snapshot.source_manifest_id
        assert historical.coverage <= snapshot.coverage
        with pytest.raises(ValueError, match="PORTFOLIO_VERSION_NOT_YET_KNOWN"):
            service.snapshot(portfolio.portfolio_id, RiskRequest(
                manifest_id=snapshot.source_manifest_id,
                as_of=portfolio.created_at, portfolio_version=portfolio.version))
        corrected = portfolio.positions[0].model_copy(update={"quantity":Decimal("0.05")})
        portfolio = service.store.change(portfolio.portfolio_id, PositionChange(
            action="update", position=corrected, reason="Correct synthetic BTC quantity"))
        assert portfolio.version == 5 and service.store.get(portfolio.portfolio_id, 4).positions[0].quantity == Decimal("0.1")
        closed = corrected.model_copy(update={"closed_at":datetime.now(timezone.utc)})
        portfolio = service.store.change(portfolio.portfolio_id, PositionChange(
            action="close", position=closed, reason="Close synthetic BTC research position"))
        assert portfolio.version == 6
        assert [row["action"] for row in service.store.versions(portfolio.portfolio_id)][-2:] == [
            "position_updated", "position_closed"]
        remaining = service.snapshot(portfolio.portfolio_id, RiskRequest(
            manifest_id=snapshot.source_manifest_id))
        assert {item.symbol for item in remaining.positions} == {"ETHUSDT", "SOLUSDT"}
        replay = service.snapshot(portfolio.portfolio_id, RiskRequest(
            manifest_id=snapshot.source_manifest_id, as_of=remaining.as_of,
            portfolio_version=4))
        assert replay.exposure.gross == snapshot.exposure.gross
    finally:
        with connect(DSN) as connection:
            for run_id in run_ids:
                connection.execute("DELETE FROM cortex_research_runs WHERE run_id=%s", (run_id,))
            connection.execute("DELETE FROM portfolio_risk_snapshots WHERE portfolio_id=%s",
                               (portfolio.portfolio_id,))
            connection.execute("DELETE FROM portfolio_versions WHERE portfolio_id=%s",
                               (portfolio.portfolio_id,))
            connection.execute("DELETE FROM portfolios WHERE portfolio_id=%s",
                               (portfolio.portfolio_id,))


def test_synthetic_fixture_refused_in_owner_main_even_with_test_dsn(pilot):
    with pytest.raises(ValueError, match="SYNTHETIC_PORTFOLIO_REQUIRES_TEST_DATABASE"):
        PortfolioStore(DSN, "OWNER_MAIN").create(PortfolioCreate(name="Do not create",
            base_currency="USDT", capital=Decimal("100"),
            classification="SYNTHETIC_TEST_PORTFOLIO"))


def test_cortex_requires_explicit_portfolio_when_multiple_exist(pilot):
    service, client = pilot
    created = [service.store.create(PortfolioCreate(name=f"PHASE6_AMBIGUITY_{index}",
        base_currency="USDT", capital=Decimal("1000"),
        classification="SYNTHETIC_TEST_PORTFOLIO")) for index in range(2)]
    try:
        context = build_context(service.catalog, as_of=datetime.now(timezone.utc))
        response = client.post("/api/v1/cortex/research", json={
            "question":"How risky is my portfolio?", "mode":"pinned",
            "manifest_id":context["source_manifest_id"], "as_of":datetime.now(timezone.utc).isoformat(),
            "depth":"quick"})
        assert response.status_code == 422
        assert response.json()["detail"]["code"] == "PORTFOLIO_ID_REQUIRED"
    finally:
        with connect(DSN) as connection:
            for portfolio in created:
                connection.execute("DELETE FROM portfolio_versions WHERE portfolio_id=%s",
                                   (portfolio.portfolio_id,))
                connection.execute("DELETE FROM portfolios WHERE portfolio_id=%s",
                                   (portfolio.portfolio_id,))
