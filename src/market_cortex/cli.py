"""Windows-compatible local CLI. Never prints connection strings or tokens."""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from uuid import UUID

from .config import Settings
from .database import migrate


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="market-cortex")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("doctor", help="Show safe configuration status")
    sub.add_parser("migrate", help="Apply PostgreSQL migrations")
    backup = sub.add_parser("backup", help="Create encrypted PostgreSQL + Parquet backup")
    backup.add_argument("--output", type=Path, required=True)
    restore = sub.add_parser("restore", help="Restore to an empty separate database and data directory")
    restore.add_argument("--input", type=Path, required=True)
    restore.add_argument("--data-root", type=Path, required=True)
    crypto = sub.add_parser("bootstrap-crypto", help="Resolve public Binance native spot identities")
    crypto.add_argument("--symbols", nargs="+", default=None)
    sync = sub.add_parser("sync-daily", help="Fetch and ingest a bounded daily history interval")
    sync.add_argument("--provider", choices=["binance", "alpaca", "upstox"], required=True)
    sync.add_argument("--instrument-id", type=UUID, required=True)
    sync.add_argument("--start", type=datetime.fromisoformat, required=True)
    sync.add_argument("--end", type=datetime.fromisoformat, required=True)
    sync.add_argument("--calendar-id")
    sync.add_argument("--calendar-version")
    inspect = sub.add_parser("inspect-manifest", help="Verify and summarize a pinned Parquet manifest")
    inspect.add_argument("--manifest-id", type=UUID, required=True)
    sub.add_parser("scan-storage", help="Read-only orphan, missing-file and checksum inventory")
    serve = sub.add_parser("serve", help="Start the loopback read API")
    serve.add_argument("--port", type=int, default=8765)
    feature = sub.add_parser("compute-feature", help="Compute a manifest-pinned deterministic daily feature")
    feature.add_argument("--name", required=True)
    feature.add_argument("--instrument-id", type=UUID, required=True)
    feature.add_argument("--from", dest="from_date", type=date.fromisoformat, required=True)
    feature.add_argument("--to", dest="to_date", type=date.fromisoformat, required=True)
    feature.add_argument("--as-of", type=datetime.fromisoformat)
    feature.add_argument("--manifest-id", type=UUID)
    feature.add_argument("--provider-id")
    feature.add_argument("--adjustment-basis", default="raw")
    feature.add_argument("--parameters", default="{}", help="JSON object of approved numeric parameters")
    feature.add_argument("--series", action="store_true", help="Include every daily point")
    state = sub.add_parser("compute-market-state", help="Inspect the Binance pilot state vector")
    state.add_argument("--history-from", type=date.fromisoformat, required=True)
    state.add_argument("--evaluation-date", type=date.fromisoformat, required=True)
    state.add_argument("--as-of", type=datetime.fromisoformat)
    state.add_argument("--manifest-id", type=UUID)
    research = sub.add_parser("research", help="Create an evidence-grounded local CORTEX research run")
    research.add_argument("question")
    research.add_argument("--mode", choices=["latest", "pinned", "historical"], default="latest")
    research.add_argument("--manifest-id", type=UUID)
    research.add_argument("--as-of", type=datetime.fromisoformat)
    research.add_argument("--symbol")
    research.add_argument("--compare-symbol")
    research.add_argument("--older-manifest-id", type=UUID)
    research.add_argument("--candidate-id", type=UUID, help="Review a recorded opportunity candidate")
    research.add_argument("--thesis-id", type=UUID, help="Review a recorded structured thesis")
    research.add_argument("--prediction-id", type=UUID, help="Explain a frozen prediction and its outcome")
    research.add_argument("--journal-entry-id", type=UUID, help="Inspect a private journal revision")
    research.add_argument("--backtest-run-id", type=UUID)
    research.add_argument("--quant-study-id", type=UUID)
    research.add_argument("--portfolio-id", type=UUID, help="Ground a local portfolio risk question")
    research.add_argument("--scenario-shocks", type=json.loads, help="JSON object of explicit symbol: fractional shock")
    research.add_argument("--overlay-quantity", type=str, help="Hypothetical thesis units for research overlay")
    research.add_argument("--overlay-reference-price", type=str, help="Explicit hypothetical entry price")
    research.add_argument("--overlay-invalidation-price", type=str, help="Optional explicit invalidation price")
    research.add_argument("--depth", choices=["quick", "deep"], default="deep")
    runs = sub.add_parser("research-runs", help="List recent local CORTEX research runs")
    runs.add_argument("--symbol")
    inspect_run = sub.add_parser("inspect-research-run", help="Inspect a saved research manifest")
    inspect_run.add_argument("run_id", type=UUID)
    replay_run = sub.add_parser("replay-research-run", help="Verify saved deterministic evidence")
    replay_run.add_argument("run_id", type=UUID)
    opportunity = sub.add_parser("scan-opportunities", help="Scan versioned Pilot 5 daily detectors")
    opportunity.add_argument("--mode", choices=["latest", "pinned", "historical"], default="latest")
    opportunity.add_argument("--manifest-id", type=UUID)
    opportunity.add_argument("--as-of", type=datetime.fromisoformat)
    opportunity.add_argument("--symbol")
    opportunity.add_argument("--detector-id")
    opportunity.add_argument("--record", action="store_true", help="Append deduplicated candidate/rejection events")
    inspect_candidate = sub.add_parser("inspect-candidate", help="Inspect a recorded opportunity candidate")
    inspect_candidate.add_argument("candidate_id", type=UUID)
    make_thesis = sub.add_parser("create-thesis", help="Create a structured research thesis from a recorded candidate")
    make_thesis.add_argument("candidate_id", type=UUID)
    inspect_thesis = sub.add_parser("inspect-thesis", help="Inspect a structured thesis")
    inspect_thesis.add_argument("thesis_id", type=UUID)
    inspect_thesis.add_argument("--version", type=int)
    monitor_thesis = sub.add_parser("monitor-thesis", help="Re-evaluate a thesis under a chosen context")
    monitor_thesis.add_argument("thesis_id", type=UUID)
    monitor_thesis.add_argument("--mode", choices=["latest", "pinned", "historical"], default="latest")
    monitor_thesis.add_argument("--manifest-id", type=UUID)
    monitor_thesis.add_argument("--as-of", type=datetime.fromisoformat)
    sub.add_parser("portfolios", help="List local research portfolios")
    risk = sub.add_parser("portfolio-risk", help="Calculate pinned portfolio risk")
    risk.add_argument("portfolio_id", type=UUID)
    risk.add_argument("--manifest-id", type=UUID)
    risk.add_argument("--as-of", type=datetime.fromisoformat)
    risk.add_argument("--version", type=int)
    risk.add_argument("--persist", action="store_true")
    scenario = sub.add_parser("portfolio-scenario", help="Run explicit what-if shocks over a portfolio")
    scenario.add_argument("portfolio_id", type=UUID)
    scenario.add_argument("--manifest-id", type=UUID)
    scenario.add_argument("--as-of", type=datetime.fromisoformat)
    scenario.add_argument("--shocks", type=json.loads, required=True)
    sizing = sub.add_parser("risk-sizing", help="Hypothetical research sizing without any order path")
    sizing.add_argument("--capital", required=True)
    sizing.add_argument("--entry", required=True)
    sizing.add_argument("--invalidation", required=True)
    budget = sizing.add_mutually_exclusive_group(required=True)
    budget.add_argument("--risk-percent")
    budget.add_argument("--risk-amount")
    sizing.add_argument("--target")
    prediction = sub.add_parser("create-prediction", help="Register an explicit machine-evaluable expectation")
    prediction.add_argument("--definition", type=Path, required=True, help="Local JSON PredictionDefinition")
    evaluate = sub.add_parser("evaluate-prediction", help="Evaluate a prediction using an explicit immutable manifest")
    evaluate.add_argument("prediction_id", type=UUID)
    evaluate.add_argument("--manifest-id", type=UUID, required=True)
    evaluate.add_argument("--as-of", type=datetime.fromisoformat, required=True)
    due = sub.add_parser("evaluate-due-predictions", help="Idempotent, explicitly invoked evaluation queue")
    due.add_argument("--manifest-id", type=UUID, required=True)
    due.add_argument("--as-of", type=datetime.fromisoformat, required=True)
    inspect_prediction = sub.add_parser("inspect-prediction", help="Inspect frozen expectation and outcome revisions")
    inspect_prediction.add_argument("prediction_id", type=UUID)
    learning = sub.add_parser("learning-performance", help="Descriptive detector/version/registration statistics")
    learning.add_argument("--eligible-only", action="store_true")
    sub.add_parser("review-queue", help="List local predictions requiring human review")
    sub.add_parser("quant-strategies", help="List reviewed deterministic strategy definitions")
    for name in ("quant-backtest","quant-walk-forward","quant-sensitivity","quant-robustness","quant-monte-carlo","quant-compare"):
        command=sub.add_parser(name,help="Run bounded deterministic quant research from a strict JSON definition")
        command.add_argument("--input",type=Path,required=True)
    for name in ("quant-inspect","quant-replay"):
        command=sub.add_parser(name)
        command.add_argument("artifact_id",type=UUID)
    for name in ('intelligence-coverage', 'intelligence-context', 'intelligence-events', 'intelligence-inspect'):
        command = sub.add_parser(name, help='Read immutable contextual intelligence')
        command.add_argument('--as-of', type=datetime.fromisoformat)
        command.add_argument('--context-manifest-id', type=UUID)
        command.add_argument('--instrument-id', type=UUID)
        if name == 'intelligence-inspect':
            command.add_argument('fact_id', type=UUID)
    for name in ('intelligence-probe', 'intelligence-sync'):
        command = sub.add_parser(name, help='Bounded public advanced-data GET; sync appends source facts')
        command.add_argument('--source', choices=('binance_usdm', 'us_treasury'), required=True)
        command.add_argument('--symbols', nargs='+', default=['BTCUSDT'])
        command.add_argument('--funding-limit', type=int, default=90)
    mission_create=sub.add_parser('mission-create',help='Create a policy-validated bounded research plan from typed JSON')
    mission_create.add_argument('--input',type=Path,required=True)
    for name in ('mission-run','mission-inspect','mission-replay','mission-cancel','mission-resume'):
        command=sub.add_parser(name,help='Inspect or operate one pinned local research mission')
        command.add_argument('mission_id',type=UUID)
    comparison=sub.add_parser('mission-compare',help='Compare structured evidence from two missions')
    comparison.add_argument('older',type=UUID); comparison.add_argument('newer',type=UUID)
    sub.add_parser('mission-history',help='List recent local missions')
    sub.add_parser('mission-worker',help='Process one durable research job')
    args = parser.parse_args(argv)
    try:
        settings = Settings.load()
        if args.command.startswith('mission-'):
            from .missions import MissionService
            from .mission_contracts import MissionRequest
            from .storage import ArtifactStore,PostgresCatalog
            if not settings.database_url:
                print('DATABASE_NOT_CONFIGURED',file=sys.stderr); return 2
            service=MissionService(PostgresCatalog(settings.database_url,ArtifactStore(settings.data_root)),settings)
            if args.command=='mission-create': result=service.create(MissionRequest.model_validate_json(args.input.read_text(encoding='utf-8-sig')))
            elif args.command=='mission-compare': result=service.diff(args.older,args.newer)
            elif args.command=='mission-history': result={'items':[m.model_dump(mode='json') for m in service.store.recent()]}
            elif args.command=='mission-worker': result=service.worker()
            elif args.command=='mission-inspect': result=service.store.get(args.mission_id)
            elif args.command=='mission-replay': result=service.replay(args.mission_id)
            elif args.command=='mission-cancel': result=service.store.cancel(args.mission_id)
            else: result=service.run(args.mission_id)
            print(json.dumps(result.model_dump(mode='json') if hasattr(result,'model_dump') else result,default=str))
            return 0
        if args.command.startswith('intelligence-'):
            from .intelligence import IntelligenceService
            from .intelligence_contracts import ContextRequest
            from .intelligence_sources import BinanceDerivatives, TreasuryMacro, coverage
            from .storage import ArtifactStore, PostgresCatalog
            service = IntelligenceService(PostgresCatalog(settings.database_url, ArtifactStore(settings.data_root)))
            if args.command in ('intelligence-probe', 'intelligence-sync'):
                provider = BinanceDerivatives() if args.source == 'binance_usdm' else TreasuryMacro()
                facts = provider.fetch(service.catalog, symbols=args.symbols, funding_limit=args.funding_limit) if args.source == 'binance_usdm' else provider.fetch()
                result = service.store.append(facts) if args.command == 'intelligence-sync' else {'source': args.source, 'normalized_records': len(facts), 'persisted_facts': False}
            else:
                cutoff = args.as_of or datetime.now(timezone.utc)
                if args.command == 'intelligence-coverage':
                    result = {'items': [s.model_dump(mode='json') for s in coverage(service.store, cutoff)]}
                elif args.command == 'intelligence-inspect':
                    result = service.store.inspect(args.fact_id, cutoff)
                else:
                    snap = service.snapshot(ContextRequest(as_of=cutoff, context_manifest_id=args.context_manifest_id, instrument_id=args.instrument_id))
                    result = snap.model_dump(mode='json') if args.command == 'intelligence-context' else {'event_risk': snap.event_risk, 'items': [f.model_dump(mode='json') for f in snap.facts if f.domain == 'events']}
            print(json.dumps(result))
            return 0
        if args.command.startswith("quant-"):
            from .quant import QuantService,strategies
            from .quant_api import MODELS
            from .storage import ArtifactStore,PostgresCatalog
            if args.command=="quant-strategies":
                result={"items":[s.model_dump(mode="json") for s in strategies()]}
            else:
                service=QuantService(PostgresCatalog(settings.database_url,ArtifactStore(settings.data_root)),settings.environment)
                if args.command=="quant-inspect":
                    result=service.store.get(args.artifact_id)
                elif args.command=="quant-replay":
                    result=service.replay(args.artifact_id)
                else:
                    operation=args.command.removeprefix("quant-").replace("-","_")
                    operation="comparison" if operation=="compare" else operation
                    request=MODELS[operation].model_validate_json(args.input.read_text(encoding="utf-8"))
                    result=getattr(service,"run" if operation=="backtest" else "compare" if operation=="comparison" else operation)(request)
            print(json.dumps(result.model_dump(mode="json") if hasattr(result,"model_dump") else result,default=str))
            return 0
        if args.command == "doctor":
            print(json.dumps(settings.safe_summary(), indent=2))
            return 0
        if args.command == "migrate":
            if not settings.database_url:
                print("DATABASE_NOT_CONFIGURED", file=sys.stderr)
                return 2
            root = Path(__file__).resolve().parents[2]
            print(json.dumps({"applied_migrations": migrate(settings.database_url, root)}))
            return 0
        if args.command == "risk-sizing":
            from decimal import Decimal
            from .risk import research_sizing
            from .risk_contracts import SizingRequest
            result = research_sizing(SizingRequest(capital=Decimal(args.capital),
                entry_price=Decimal(args.entry), invalidation_price=Decimal(args.invalidation),
                risk_percent=Decimal(args.risk_percent) if args.risk_percent else None,
                risk_amount=Decimal(args.risk_amount) if args.risk_amount else None,
                target_price=Decimal(args.target) if args.target else None))
            print(json.dumps(result, default=str))
            return 0
        if args.command in ("bootstrap-crypto", "sync-daily", "inspect-manifest", "scan-storage",
                            "compute-feature", "compute-market-state", "research", "research-runs",
                            "inspect-research-run", "replay-research-run", "scan-opportunities",
                            "inspect-candidate", "create-thesis", "inspect-thesis", "monitor-thesis",
                            "portfolios", "portfolio-risk", "portfolio-scenario", "create-prediction",
                            "evaluate-prediction", "evaluate-due-predictions", "inspect-prediction",
                            "learning-performance", "review-queue"):
            if not settings.database_url:
                print("DATABASE_NOT_CONFIGURED", file=sys.stderr)
                return 2
            from .storage import ArtifactStore, PostgresCatalog
            catalog = PostgresCatalog(settings.database_url, ArtifactStore(settings.data_root))
            if args.command in ("create-prediction", "evaluate-prediction", "evaluate-due-predictions",
                                "inspect-prediction", "learning-performance", "review-queue"):
                from .learning import LearningService
                from .learning_contracts import PredictionDefinition, EvaluationRequest
                service = LearningService(catalog,settings.environment)
                if args.command == "create-prediction":
                    result = service.create_prediction(PredictionDefinition.model_validate_json(args.definition.read_text(encoding="utf-8-sig")))
                elif args.command in ("evaluate-prediction", "evaluate-due-predictions"):
                    request = EvaluationRequest(manifest_id=args.manifest_id,as_of=args.as_of)
                    result = service.evaluate(args.prediction_id,request) if args.command=="evaluate-prediction" else service.evaluate_due(request)
                elif args.command == "inspect-prediction":
                    item = service.store.prediction(args.prediction_id)
                    if item is None:
                        raise LookupError("PREDICTION_NOT_FOUND")
                    result = {"prediction":item.model_dump(mode="json"),"revisions":service.store.prediction_history(args.prediction_id)}
                elif args.command == "learning-performance":
                    result = service.performance(as_of=datetime.now(timezone.utc),eligible_only=args.eligible_only)
                else:
                    result = service.review_queue(datetime.now(timezone.utc))
                print(json.dumps(result.model_dump(mode="json") if hasattr(result,"model_dump") else result,default=str))
                return 0
            if args.command in ("portfolios", "portfolio-risk", "portfolio-scenario"):
                from .risk import RiskService, run_scenario
                from .risk_contracts import RiskRequest, ScenarioDefinition
                service = RiskService(catalog, settings.environment)
                if args.command == "portfolios":
                    result = {"items": [item.model_dump(mode="json") for item in service.store.list()]}
                else:
                    snapshot = service.snapshot(args.portfolio_id, RiskRequest(
                        manifest_id=args.manifest_id, as_of=args.as_of,
                        portfolio_version=args.version if args.command == "portfolio-risk" else None,
                        persist=args.persist if args.command == "portfolio-risk" else False))
                    result = snapshot.model_dump(mode="json") if args.command == "portfolio-risk" else \
                        run_scenario(snapshot, ScenarioDefinition(name="CLI explicit what-if",
                            shocks=args.shocks)).model_dump(mode="json")
                print(json.dumps(result))
                return 0
            if args.command in ("scan-opportunities", "inspect-candidate", "create-thesis",
                                "inspect-thesis", "monitor-thesis"):
                from .opportunity import OpportunityService
                from .opportunity_contracts import ScanRequest
                from .opportunity_store import OpportunityStore
                store = OpportunityStore(catalog.dsn)
                if args.command == "scan-opportunities":
                    result = OpportunityService(catalog).scan(ScanRequest(mode=args.mode,
                        manifest_id=args.manifest_id, as_of=args.as_of, symbol=args.symbol,
                        detector_id=args.detector_id, record=args.record))
                elif args.command == "inspect-candidate":
                    result = store.candidate(args.candidate_id)
                elif args.command == "create-thesis":
                    result = store.create_thesis(args.candidate_id)
                elif args.command == "inspect-thesis":
                    result = store.thesis(args.thesis_id, args.version)
                else:
                    prior = store.thesis(args.thesis_id)
                    if prior is None:
                        raise LookupError("THESIS_NOT_FOUND")
                    scan = OpportunityService(catalog).scan(ScanRequest(mode=args.mode,
                        manifest_id=args.manifest_id, as_of=args.as_of, symbol=prior.symbol,
                        detector_id=prior.detector_id, record=True))
                    result = store.advance(args.thesis_id, scan.candidates[0])
                if result is None:
                    print(json.dumps({"code": "RECORD_NOT_FOUND"}))
                    return 2
                print(result.model_dump_json())
                return 0
            if args.command in ("research", "research-runs", "inspect-research-run", "replay-research-run"):
                from .cortex import CortexService
                from .cortex_contracts import ResearchRequest
                service = CortexService(catalog, settings)
                if args.command == "research":
                    request = ResearchRequest(question=args.question, mode=args.mode,
                        manifest_id=args.manifest_id, as_of=args.as_of, symbol=args.symbol,
                        compare_symbol=args.compare_symbol, older_manifest_id=args.older_manifest_id,
                        candidate_id=args.candidate_id, thesis_id=args.thesis_id,
                        prediction_id=args.prediction_id, journal_entry_id=args.journal_entry_id,
                        backtest_run_id=args.backtest_run_id, quant_study_id=args.quant_study_id,
                        portfolio_id=args.portfolio_id, scenario_shocks=args.scenario_shocks,
                        overlay_quantity=args.overlay_quantity,
                        overlay_reference_price=args.overlay_reference_price,
                        overlay_invalidation_price=args.overlay_invalidation_price,
                        depth=args.depth)
                    result = service.research(request)
                    print(json.dumps({"run_id": str(result.run_id), "answer": result.answer,
                        "evidence_strength": result.evidence_strength,
                        "model_status": result.model_status}))
                elif args.command == "research-runs":
                    print(json.dumps({"items": service.store.recent(symbol=args.symbol)}))
                elif args.command == "inspect-research-run":
                    result = service.store.get(args.run_id)
                    print(result.model_dump_json() if result else json.dumps({"code": "RESEARCH_RUN_NOT_FOUND"}))
                    if result is None:
                        return 2
                else:
                    print(json.dumps(service.replay(args.run_id)))
                return 0
            if args.command == "scan-storage":
                print(json.dumps(catalog.scan_storage()))
                return 0
            if args.command == "compute-feature":
                from .features import FeatureEngine, FeatureRequest
                parameters = json.loads(args.parameters)
                if not isinstance(parameters, dict):
                    raise ValueError("parameters must be a JSON object")
                request = FeatureRequest(instrument_id=args.instrument_id, feature=args.name,
                    start_date=args.from_date, end_date=args.to_date,
                    as_of=args.as_of or datetime.now(timezone.utc), manifest_id=args.manifest_id,
                    provider_id=args.provider_id, adjustment_basis=args.adjustment_basis,
                    parameters=parameters)
                payload = FeatureEngine(catalog).calculate(request).model_dump(mode="json")
                if not args.series:
                    payload["latest"] = payload["points"][-1] if payload["points"] else None
                    del payload["points"]
                    payload["source_observation_count"] = len(payload.pop("source_observation_ids"))
                print(json.dumps(payload))
                return 0
            if args.command == "compute-market-state":
                from .market_state import MarketStateEngine, MarketStateRequest
                request = MarketStateRequest(history_start=args.history_from,
                    evaluation_date=args.evaluation_date, as_of=args.as_of or datetime.now(timezone.utc),
                    manifest_id=args.manifest_id)
                print(MarketStateEngine(catalog).compute(request).model_dump_json())
                return 0
            if args.command == "inspect-manifest":
                from .analytics import manifest_coverage
                print(json.dumps({"manifest_id": str(args.manifest_id),
                                  "coverage": manifest_coverage(catalog, args.manifest_id)}))
                return 0
            if args.command == "bootstrap-crypto":
                from .bootstrap import DEFAULT_CRYPTO_CANDIDATES, discover_crypto
                print(json.dumps(discover_crypto(catalog, args.symbols or DEFAULT_CRYPTO_CANDIDATES)))
                return 0
            from .calendar import SessionCalendar
            from .contracts import utc
            from .identity import IdentityRegistry
            from .providers import AlpacaDaily, BinanceDaily, UpstoxDaily
            start, end = utc(args.start), utc(args.end)
            if start >= end:
                print("INVALID_INTERVAL", file=sys.stderr)
                return 2
            instruments, mappings = catalog.load_identity()
            instrument = next((i for i in instruments if i.instrument_id == args.instrument_id), None)
            if instrument is None:
                print("INSTRUMENT_NOT_FOUND", file=sys.stderr)
                return 2
            kind = {"binance": "exchange_pair", "alpaca": "ticker", "upstox": "provider_token"}[args.provider]
            mapping = IdentityRegistry(instruments, mappings).mapping_for(args.instrument_id, args.provider, kind, start)
            calendar = catalog.load_calendar(instrument.primary_venue_id, start, end,
                                             args.calendar_id, args.calendar_version)
            adapter = {"binance": BinanceDaily, "alpaca": AlpacaDaily, "upstox": UpstoxDaily}[args.provider]()
            fetched = adapter.fetch_daily(instrument, mapping, calendar, start, end)
            result = catalog.ingest(list(fetched.bars), calendar, source_batch_id=fetched.batch_id,
                                    provider_id=fetched.provider_id, raw_hash=fetched.raw_hash,
                                    fetched_at=fetched.fetched_at)
            print(json.dumps({"manifest_id": str(result.manifest_id) if result.manifest_id else None,
                              "stored": result.stored, "duplicates": result.duplicates,
                              "quarantined": result.quarantined, "pages": fetched.pages,
                              "feed_class": fetched.feed_class, "adjustment_basis": fetched.adjustment_basis}))
            return 0
        if args.command in ("backup", "restore"):
            from .backup import backup as create_backup, restore as restore_backup
            passphrase = os.environ.get("MARKET_CORTEX_BACKUP_PASSPHRASE")
            if not passphrase:
                print("BACKUP_PASSPHRASE_NOT_CONFIGURED", file=sys.stderr)
                return 2
            if args.command == "backup":
                result = create_backup(settings, args.output, passphrase)
            else:
                target = os.environ.get("MARKET_CORTEX_RESTORE_DATABASE_URL")
                if not target:
                    print("RESTORE_DATABASE_NOT_CONFIGURED", file=sys.stderr)
                    return 2
                result = restore_backup(args.input, args.data_root.resolve(), target, settings.database_url, passphrase)
            print(json.dumps(result))
            return 0
        if args.command == "serve":
            import uvicorn
            uvicorn.run("market_cortex.api:app", host="127.0.0.1", port=args.port, access_log=False)
            return 0
    except Exception as exc:
        # Exception messages from drivers can contain credentials or URLs.
        print(f"OPERATION_FAILED: {type(exc).__name__}", file=sys.stderr)
        return 1
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
