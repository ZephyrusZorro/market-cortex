"""Trace the complete research workflow with real stored bars and pilot records."""
import json
import os
import sys
from collections import Counter
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path
from uuid import UUID
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'src'))
from psycopg.conninfo import conninfo_to_dict
from market_cortex.config import Settings
from market_cortex.database import connect
from market_cortex.storage import PostgresCatalog, ArtifactStore
from market_cortex.identity import IdentityRegistry
from market_cortex.features import FeatureEngine, FeatureRequest
from market_cortex.market_state import MarketStateEngine, MarketStateRequest, PILOT_SYMBOLS
from market_cortex.intelligence import IntelligenceService
from market_cortex.intelligence_contracts import ContextRequest
from market_cortex.opportunity import OpportunityService
from market_cortex.opportunity_contracts import ScanRequest
from market_cortex.risk import RiskService, run_scenario
from market_cortex.risk_contracts import RiskRequest, ScenarioDefinition
from market_cortex.missions import MissionService
from market_cortex.mission_contracts import MissionRequest, MissionBudget
from market_cortex.quant import QuantService
from market_cortex.quant_contracts import BacktestDefinition
from market_cortex.experiments import ExperimentService


def main():
    root = Path(__file__).resolve().parents[1]; report = json.loads((root/'docs/quant/PHASE_12_PILOT_RESULTS.json').read_text(encoding='utf-8'))
    dsn = os.environ['MARKET_CORTEX_PHASE12_PILOT_DSN']; data = Path(os.environ['MARKET_CORTEX_PHASE12_PILOT_DATA_ROOT'])
    if not conninfo_to_dict(dsn).get('dbname', '').endswith('_test'): raise ValueError('DEDICATED_TEST_CATALOG_REQUIRED')
    c = PostgresCatalog(dsn, ArtifactStore(data)); settings = Settings(dsn, data, 'Asia/Kolkata', 'INR', False, True, 'PILOT_TEST')
    s = ExperimentService(c, settings); head = c.head(); cutoff = datetime.fromisoformat(report['source_as_of'])
    instrument = IdentityRegistry(*c.load_identity()).resolve(provider_id='binance', identifier_type='exchange_pair', identifier_value='BTCUSDT', at=cutoff, known_at=cutoff)
    features = FeatureEngine(c).calculate(FeatureRequest(instrument_id=instrument.instrument_id, feature='rolling_return',
        start_date=date(2024,1,1), end_date=date(2026,10,3), as_of=cutoff, manifest_id=head, provider_id='binance'))
    state = MarketStateEngine(c).compute(MarketStateRequest(history_start=date(2024,1,1), evaluation_date=date(2026,10,3), as_of=cutoff, manifest_id=head))
    context = IntelligenceService(c).snapshot(ContextRequest(as_of=cutoff, market_manifest_id=head, instrument_id=instrument.instrument_id))
    scan = OpportunityService(c).scan(ScanRequest(mode='pinned', manifest_id=head, as_of=cutoff, symbol='BTCUSDT', record=False))
    with connect(dsn) as db:
        thesis = db.execute('SELECT thesis_id,version,payload FROM research_thesis_versions WHERE recorded_at<=%s ORDER BY recorded_at DESC LIMIT 1', (cutoff,)).fetchone()
        portfolio = db.execute("SELECT portfolio_id,version FROM portfolio_versions WHERE recorded_at<=%s AND payload->>'classification'='SYNTHETIC_TEST_PORTFOLIO' ORDER BY recorded_at DESC LIMIT 1", (cutoff,)).fetchone()
        before = {t: db.execute('SELECT count(*) FROM '+t).fetchone()[0] for t in ('observations','context_facts','portfolio_versions','research_thesis_versions','prediction_records','journal_revisions')}
    assert portfolio and thesis
    risk = RiskService(c, 'PILOT_TEST').snapshot(portfolio[0], RiskRequest(manifest_id=head, as_of=cutoff, portfolio_version=portfolio[1], persist=False))
    stress = run_scenario(risk, ScenarioDefinition(name='Supplied hypothetical broad crypto -20% shock', kind='broad_crypto_shock', shocks={symbol: Decimal('-.20') for symbol in PILOT_SYMBOLS}))
    quant = QuantService(c, 'PILOT_TEST')
    breakout = quant.run(BacktestDefinition(manifest_id=head, source_as_of=cutoff, start=date(2026,8,1), end=date(2026,9,30),
        strategy_id='breakout', replay_policy='HISTORICAL_RECONSTRUCTION'))
    robustness = quant.robustness(breakout.definition)
    ms = MissionService(c, settings)
    request = MissionRequest(goal='Challenge the recorded thesis, current stale market evidence, contextual gaps and negative historical strategy results.',
        mode='THESIS_REVIEW', template='thesis_challenge', thesis_id=thesis[0], thesis_version=thesis[1], manifest_id=head, as_of=cutoff,
        symbol=thesis[2]['symbol'], portfolio_id=portfolio[0], approved_domains=['market','intelligence','opportunities','quant','learning','portfolio'],
        required_domains=['market'], excluded_domains=['journal'], budgets=MissionBudget(max_tool_calls=16, timeout_seconds=300))
    mission = ms.run(ms.create(request).mission_id); mission_replay = ms.replay(mission.mission_id)
    assert mission_replay['matched'] and not mission.evaluator.get('rejected_claims')
    experiment = s.store.result(UUID(report['experiments'][2]['experiment_id']))['result']
    rows = [{'step': 'Trusted data', 'reference': str(head), 'instrument_id': str(instrument.instrument_id)},
        {'step': 'Canonical deterministic features', 'reference': features.feature_id, 'computed_N': features.computed_points, 'freshness': features.freshness},
        {'step': 'Market state', 'reference': state.snapshot_id, 'regime': state.regime.model_dump(mode='json')},
        {'step': 'Context', 'reference': str(context.snapshot_id), 'dimensions': {k: d.status for k,d in context.dimensions.items()}},
        {'step': 'Opportunity scanner', 'reference': str(scan.scan_id), 'status_counts': dict(Counter(x.status for x in scan.candidates)), 'recorded': False},
        {'step': 'Frozen hypothesis', 'reference': report['experiments'][2]['hypothesis_id']},
        {'step': 'Versioned recorded thesis', 'reference': str(thesis[0]), 'version': thesis[1], 'status': thesis[2]['status']},
        {'step': 'Risk', 'reference': str(risk.snapshot_id), 'coverage': risk.coverage, 'warnings': risk.warnings, 'portfolio_scope': 'SYNTHETIC_TEST_PORTFOLIO; NOT_OWNER_HABITS'},
        {'step': 'Stress', 'assumption': 'SUPPLIED_MINUS_20_PERCENT_SHOCK; NO_FORECAST_PROBABILITY', 'result': stress.model_dump(mode='json')},
        {'step': 'Versioned experiment', 'reference': report['experiments'][2]['experiment_id'], 'result_hash': experiment['result_hash']},
        {'step': 'Purged temporal model validation', 'reference': experiment['dataset_ref'], 'metrics': experiment['result']['reports']['metrics']},
        {'step': 'Canonical breakout backtest', 'reference': str(breakout.run_id), 'metrics': breakout.metrics, 'regime_performance': breakout.regime_performance},
        {'step': 'Canonical fill/cost/delay/asset/period robustness', 'reference': robustness['study_id'], 'classification': robustness['result']['classification']},
        {'step': 'CORTEX skeptic review', 'reference': str(mission.mission_id), 'status': mission.status, 'usage': mission.usage.model_dump(mode='json')},
        {'step': 'Statistical evidence', 'reference': experiment['result']['reports']['multiple_testing'], 'uncertainty': experiment['result']['reports']['uncertainty']},
        {'step': 'Edge Library', 'reference': report['edge_link']['link_id'], 'effect': 'EVIDENCE_LINK_ONLY; STATUS_UNCHANGED'},
        {'step': 'Experimental ResearchDossier', 'reference': report['dossier_ref']},
        {'step': 'Historical replay', 'experiment': report['experiments'][2]['replay'], 'canonical_mission': mission_replay, 'canonical_breakout': quant.replay(breakout.run_id)}]
    with connect(dsn) as db: after = {t: db.execute('SELECT count(*) FROM '+t).fetchone()[0] for t in before}
    assert before == after and c.head() == head
    artifact = s.store.artifact('experiment_dossier', {'workflow': 'PHASES_1_12_READ_ONLY_CANONICAL_FLOW', 'source_as_of': cutoff.isoformat()},
        {'steps': rows, 'mission_hash': mission.content_hash, 'environment': 'PILOT_TEST', 'owner_main': 'UNTOUCHED'})
    result = {'status': 'VERIFIED', 'validated_at': datetime.now(timezone.utc).isoformat(), 'steps': rows, 'workflow_dossier_ref': artifact,
        'canonical_counts_before': before, 'canonical_counts_after': after, 'conclusion': 'NO_SUPPORTED_EDGE_ESTABLISHED', 'owner_main': 'UNTOUCHED'}
    (root/'docs/quant/PHASE_12_SYSTEM_WORKFLOW.json').write_text(json.dumps(result, indent=2, default=str), encoding='utf-8')
    print('Phases 1-12 research workflow verified; market, portfolio, journal, prediction and thesis records unchanged.', flush=True)


if __name__ == '__main__': main()
