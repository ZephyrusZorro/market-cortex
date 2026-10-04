"""Measure Phase 6 with disposable, unmistakably synthetic Pilot 5 positions."""

from __future__ import annotations

import json
import sys
import time
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from uuid import UUID

from psycopg.conninfo import conninfo_to_dict

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from market_cortex.config import Settings
from market_cortex.database import connect
from market_cortex.features import FeatureEngine
from market_cortex.opportunity_store import OpportunityStore
from market_cortex.portfolio_store import PortfolioStore
from market_cortex.risk import RiskService, run_scenario
from market_cortex.risk_contracts import (OverlayRequest, PortfolioCreate, PositionChange,
                                          PositionInput, RiskRequest, ScenarioDefinition)
from market_cortex.storage import ArtifactStore, PostgresCatalog
from market_cortex.workstation import build_context


def main() -> None:
    settings = Settings.load()
    if (settings.environment != "PILOT_TEST" or not settings.database_url or
            not conninfo_to_dict(settings.database_url).get("dbname", "").lower().endswith("_test") or
            not settings.data_root.is_dir()):
        raise SystemExit("DEDICATED_PILOT_TEST_DATABASE_AND_DATA_ROOT_REQUIRED")
    catalog = PostgresCatalog(settings.database_url, ArtifactStore(settings.data_root))
    service = RiskService(catalog, settings.environment)
    store = PortfolioStore(settings.database_url, settings.environment)
    cutoff = datetime.now(timezone.utc)
    context = build_context(catalog, as_of=cutoff)
    manifest = UUID(context["source_manifest_id"])
    members = {item["symbol"]: item for item in context["members"]}
    if not {"BTCUSDT", "ETHUSDT", "SOLUSDT"} <= set(members):
        raise SystemExit("PILOT_3_MAPPING_UNAVAILABLE")
    thesis = next((item for item in OpportunityStore(settings.database_url).recent_theses(
        symbol="BTCUSDT", limit=50) if item.updated_at <= cutoff and
        item.as_of <= cutoff and item.source_manifest_id in service._manifest_ancestors(manifest)), None)
    if thesis is None:
        raise SystemExit("VISIBLE_PILOT_BTC_THESIS_REQUIRED")
    portfolio = store.create(PortfolioCreate(name="SYNTHETIC_TEST_PORTFOLIO_PHASE6_MEASUREMENT",
        base_currency="USDT", capital=Decimal("100000"),
        classification="SYNTHETIC_TEST_PORTFOLIO"))
    started = time.perf_counter()
    try:
        prices: dict[str, Decimal] = {}
        for symbol, quantity in (("BTCUSDT", "0.1"), ("ETHUSDT", "2"), ("SOLUSDT", "10")):
            member = members[symbol]
            session = datetime.fromisoformat(member["last_session"]).date()
            loaded = FeatureEngine(catalog).load(instrument_id=UUID(member["instrument_id"]),
                start_date=session, end_date=session, as_of=cutoff, manifest_id=manifest,
                provider_id="binance")
            prices[symbol] = Decimal(str(loaded.bars[-1].close))
            position = PositionInput(instrument_id=UUID(member["instrument_id"]),
                quantity=Decimal(quantity), average_cost=prices[symbol]*Decimal("0.95"),
                invalidation_price=prices[symbol]*Decimal("0.90"), native_currency="USDT",
                opened_at=cutoff, source_type="synthetic_fixture")
            portfolio = store.change(portfolio.portfolio_id, PositionChange(action="add",
                position=position, reason=f"Disposable Phase 6 {symbol} measurement"))
        risk = service.snapshot(portfolio.portfolio_id, RiskRequest(
            manifest_id=manifest, persist=True))
        scenario = ScenarioDefinition(name="Pilot 5 minus ten percent",
            kind="broad_crypto_shock", shocks={symbol:Decimal("-0.1")
                for symbol in ("BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT")})
        shock = run_scenario(risk, scenario)
        extra = PositionInput(instrument_id=thesis.instrument_id,
            quantity=Decimal("0.02"), average_cost=prices["BTCUSDT"]*Decimal("0.95"),
            invalidation_price=prices["BTCUSDT"]*Decimal("0.90"),
            native_currency="USDT", opened_at=cutoff, thesis_id=thesis.thesis_id,
            source_type="synthetic_fixture")
        overlay = service.overlay(portfolio.portfolio_id, OverlayRequest(
            risk=RiskRequest(manifest_id=manifest, as_of=risk.as_of,
                portfolio_version=portfolio.version), hypothetical_position=extra,
            scenario=scenario))
        result = {
            "classification":"SYNTHETIC_TEST_PORTFOLIO", "manifest_id":str(manifest),
            "parent_manifest_id":context["manifest"]["parent_manifest_id"],
            "as_of":risk.as_of.isoformat(), "portfolio_version":portfolio.version,
            "position_sessions":{item.symbol:item.price_session for item in risk.positions},
            "price_freshness":risk.price_freshness,
            "market_state_freshness":risk.market_state_freshness,
            "gross_exposure_usdt":str(risk.exposure.gross),
            "unrealized_pnl_usdt":str(risk.unrealized_pnl),
            "heat_usdt":str(risk.heat_amount), "heat_fraction":str(risk.heat_percent),
            "concentration_flags":risk.exposure.concentration_flags,
            "correlation_cluster_flags":risk.correlation_cluster_flags,
            "correlations":[{"pair":f"{item['left']}/{item['right']}",
                             "coefficient":item["correlation"],
                             "sample_count":item["sample_count"]} for item in risk.correlations],
            "scenario_pnl_usdt":str(shock.portfolio_pnl),
            "scenario_change_fraction":str(shock.portfolio_change_percent),
            "thesis_overlay_label":overlay["label"],
            "thesis_overlay_delta_exposure_usdt":str(overlay["delta_gross_exposure"]),
            "thesis_overlay_delta_heat_usdt":str(overlay["delta_heat"]),
            "thesis_overlay_scenario_before_usdt":overlay["before_scenario"]["portfolio_pnl"],
            "thesis_overlay_scenario_after_usdt":overlay["after_scenario"]["portfolio_pnl"],
            "risk_snapshot_saved":store.risk_snapshot(risk.snapshot_id) is not None,
            "calculation_seconds":round(time.perf_counter()-started, 3),
            "warnings":risk.warnings,
        }
        print(json.dumps(result, indent=2))
    finally:
        with connect(settings.database_url) as connection:
            connection.execute("DELETE FROM portfolio_risk_snapshots WHERE portfolio_id=%s",
                               (portfolio.portfolio_id,))
            connection.execute("DELETE FROM portfolio_versions WHERE portfolio_id=%s",
                               (portfolio.portfolio_id,))
            connection.execute("DELETE FROM portfolios WHERE portfolio_id=%s",
                               (portfolio.portfolio_id,))


if __name__ == "__main__":
    main()
