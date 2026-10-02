"""Bounded read-only Phase 2 validation against an existing five-pair Binance catalog."""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from datetime import date, datetime
from pathlib import Path
from uuid import UUID

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from fastapi.testclient import TestClient

from market_cortex.api import create_app
from market_cortex.config import Settings
from market_cortex.contracts import utc
from market_cortex.features import FeatureEngine, FeatureRequest, REGISTRY
from market_cortex.market_state import MarketStateEngine, MarketStateRequest, PILOT_SYMBOLS
from market_cortex.storage import ArtifactStore, PostgresCatalog


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--history-from", type=date.fromisoformat, required=True)
    parser.add_argument("--evaluation-date", type=date.fromisoformat, required=True)
    parser.add_argument("--as-of", type=datetime.fromisoformat, required=True)
    parser.add_argument("--manifest-id", type=UUID, required=True)
    parser.add_argument("--baseline-manifest-id", type=UUID)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    settings = Settings.load()
    if not settings.database_url:
        raise SystemExit("DATABASE_NOT_CONFIGURED")
    catalog = PostgresCatalog(settings.database_url, ArtifactStore(settings.data_root))
    as_of = utc(args.as_of)
    state_request = MarketStateRequest(history_start=args.history_from,
                                       evaluation_date=args.evaluation_date,
                                       as_of=as_of, manifest_id=args.manifest_id)
    engine = MarketStateEngine(catalog)
    times = []
    snapshots = []
    for _ in range(5):
        started = time.perf_counter()
        snapshots.append(engine.compute(state_request))
        times.append((time.perf_counter() - started) * 1000)
    if len({item.snapshot_id for item in snapshots}) != 1:
        raise SystemExit("NONREPRODUCIBLE_SNAPSHOT")
    snapshot = snapshots[-1]
    features = FeatureEngine(catalog)
    checks = {}
    for symbol in PILOT_SYMBOLS:
        instrument_id = snapshot.universe_members.get(symbol)
        if instrument_id is None:
            raise SystemExit("PILOT_IDENTITY_MISSING")
        entries = {}
        for name, params in (("sma", {"period": 200}), ("rsi", {"period": 14}),
                             ("macd_histogram", {}), ("atr", {"period": 14}),
                             ("annualized_volatility", {"period": 20}),
                             ("relative_volume", {"period": 20})):
            request = FeatureRequest(instrument_id=instrument_id, feature=name,
                start_date=args.history_from, end_date=args.evaluation_date, as_of=as_of,
                manifest_id=args.manifest_id, provider_id="binance", parameters=params)
            result = features.calculate(request)
            if result.points[-1].value is None:
                raise SystemExit(f"PILOT_FEATURE_UNAVAILABLE:{symbol}:{name}")
            entries[name] = {"feature_id": result.feature_id, "value": result.points[-1].value,
                             "unit": result.definition.unit, "observed_sessions": result.observed_sessions,
                             "expected_sessions": result.expected_sessions,
                             "freshness": result.freshness}
        checks[symbol] = entries
    baseline = None
    if args.baseline_manifest_id:
        btc_id = snapshot.universe_members["BTCUSDT"]
        request = FeatureRequest(instrument_id=btc_id, feature="sma", parameters={"period": 200},
            start_date=args.history_from, end_date=args.evaluation_date, as_of=as_of,
            manifest_id=args.baseline_manifest_id, provider_id="binance")
        old = features.calculate(request)
        if old.points[-1].value is not None:
            raise SystemExit("OLD_MANIFEST_LEAKED_NEW_HISTORY")
        baseline = {"manifest_id": str(args.baseline_manifest_id),
                    "observed_sessions": old.observed_sessions,
                    "sma200_latest": None}
    client = TestClient(create_app(settings, catalog))
    btc_id = snapshot.universe_members["BTCUSDT"]
    eth_id = snapshot.universe_members["ETHUSDT"]
    common = {"from": args.history_from.isoformat(), "to": args.evaluation_date.isoformat(),
              "as_of": as_of.isoformat(), "manifest_id": str(args.manifest_id)}
    calls = {
        "feature_definitions": client.get("/api/v1/features"),
        "feature_compute": client.get("/api/v1/features/compute", params={**common, "name": "sma",
            "period": 200, "instrument_id": str(btc_id), "provider_id": "binance"}),
        "comparison": client.get("/api/v1/comparisons", params={**common, "kind": "correlation",
            "window": 60, "instrument_id": str(eth_id),
            "reference_instrument_id": str(btc_id), "provider_id": "binance",
            "reference_provider_id": "binance"}),
        "market_state": client.get("/api/v1/market-state", params={
            "history_from": args.history_from.isoformat(),
            "evaluation_date": args.evaluation_date.isoformat(), "as_of": as_of.isoformat(),
            "manifest_id": str(args.manifest_id)}),
        "regime": client.get("/api/v1/regime", params={
            "history_from": args.history_from.isoformat(),
            "evaluation_date": args.evaluation_date.isoformat(), "as_of": as_of.isoformat(),
            "manifest_id": str(args.manifest_id)}),
    }
    statuses = {name: response.status_code for name, response in calls.items()}
    if any(code != 200 for code in statuses.values()):
        raise SystemExit(f"READ_API_VALIDATION_FAILED:{statuses}")
    if calls["market_state"].json()["snapshot_id"] != snapshot.snapshot_id:
        raise SystemExit("API_SNAPSHOT_MISMATCH")
    report = {
        "status": "PASS", "as_of": as_of.isoformat(), "manifest_id": str(args.manifest_id),
        "history_from": str(args.history_from), "evaluation_date": str(args.evaluation_date),
        "universe_id": snapshot.request.universe_id,
        "members": {symbol: str(instrument_id) for symbol, instrument_id in snapshot.universe_members.items()},
        "feature_definitions": len(REGISTRY), "feature_checks": checks,
        "snapshot_id": snapshot.snapshot_id, "regime": snapshot.regime.model_dump(mode="json"),
        "dimension_categories": {item.name: item.category for item in snapshot.dimensions},
        "breadth": snapshot.breadth.model_dump(mode="json") if snapshot.breadth else None,
        "baseline_manifest": baseline, "api_statuses": statuses,
        "market_state_elapsed_ms": {"samples": [round(value, 3) for value in times],
                                    "median": round(statistics.median(times), 3),
                                    "p95_nearest_rank": round(sorted(times)[-1], 3)},
        "storage_inventory": catalog.scan_storage(),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": report["status"], "snapshot_id": snapshot.snapshot_id,
                      "manifest_id": report["manifest_id"], "api_statuses": statuses,
                      "market_state_p95_ms": report["market_state_elapsed_ms"]["p95_nearest_rank"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
