"""Modest real stored Binance research; explicitly dedicated *_test catalogs."""
import json
import os
import sys
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from uuid import UUID
from collections import Counter
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'src'))
from psycopg.conninfo import conninfo_to_dict
from market_cortex.config import Settings
from market_cortex.database import connect, migrate
from market_cortex.storage import PostgresCatalog, ArtifactStore
from market_cortex.experiments import ExperimentService, IMPLEMENTATION_HASH
from market_cortex.experiment_contracts import (ResearchHypothesis, ExperimentDefinition, ExperimentDataset, ModelDefinition,
    AnalogueRequest, ExperimentComparison, ExperimentEdgeInput, ExperimentMissionInput, PromotionDecision)
from market_cortex.experiment_tools import mission, replay_dossier
from market_cortex.personalization import PersonalizationService
from market_cortex.personal_contracts import ProfileQuery
from market_cortex.quant import QuantService
from market_cortex.quant_contracts import BacktestDefinition


def main():
    root = Path(__file__).resolve().parents[1]; output = root/'docs/quant'; output.mkdir(parents=True, exist_ok=True)
    dsn = os.environ['MARKET_CORTEX_PHASE12_PILOT_DSN']; data = Path(os.environ['MARKET_CORTEX_PHASE12_PILOT_DATA_ROOT'])
    if not conninfo_to_dict(dsn).get('dbname', '').endswith('_test'): raise ValueError('DEDICATED_TEST_CATALOG_REQUIRED')
    migrate(dsn, root); c = PostgresCatalog(dsn, ArtifactStore(data)); settings = Settings(dsn, data, 'Asia/Kolkata', 'INR', False, True, 'PILOT_TEST')
    s = ExperimentService(c, settings); cutoff = datetime.fromisoformat(os.environ['MARKET_CORTEX_PHASE12_SOURCE_AS_OF']) if os.environ.get('MARKET_CORTEX_PHASE12_SOURCE_AS_OF') else datetime.now(timezone.utc)
    started = time.perf_counter(); head = c.head()
    def counts():
        with connect(dsn) as db:
            return {t: db.execute('SELECT count(*) FROM '+t).fetchone()[0] for t in
                ('observations','context_facts','dataset_manifests','context_manifests','portfolio_versions','journal_revisions','prediction_records','research_thesis_versions')}
    before = counts(); profile = PersonalizationService(c, settings).profile(ProfileQuery(), save=True)
    assert profile.observed_behavior['genuine_owner_record_N'] == 0
    quant = QuantService(c, 'PILOT_TEST')
    # Reuse one modest canonical bar engine run for trade interpretation; forecast
    # error metrics below are never presented as simulated trade returns.
    base = BacktestDefinition(manifest_id=head, source_as_of=cutoff, start=date(2026,8,1), end=date(2026,9,30),
        strategy_id='momentum', replay_policy='HISTORICAL_RECONSTRUCTION')
    backtest = quant.run(base)
    print('Canonical momentum bar simulation:', backtest.metrics['N'], 'trades', flush=True)
    with connect(dsn) as db:
        edge = db.execute("SELECT edge_id,payload FROM edge_library ORDER BY created_at LIMIT 1").fetchone()
        negative = db.execute("SELECT artifact_id,payload FROM quant_artifacts WHERE kind='walk_forward' AND (payload->'result'->>'oos_N')::int=82 ORDER BY created_at LIMIT 1").fetchone()
    assert negative and negative[1]['result']['oos_total_return_compounded_reset_capital'] == -.07817165407921722
    price_features = ['momentum_5','momentum_20','trend_persistence','volatility_20','relative_strength','volume_ratio']
    def hyp(question, features, target='return'):
        return s.store.hypothesis(ResearchHypothesis(question=question,
            rationale='A causal price relationship may persist but should be challenged across temporal folds, assets and market regimes.',
            relationship='Registered features may reduce forward-label error relative to the training-only mean baseline.',
            falsification='Reject improvement below two percent or unstable temporal/asset behavior; no profitability inference.',
            features=features, target=target))
    h1 = hyp('Can multi-horizon momentum and regime features reduce forward return error?', price_features)
    h2 = hyp('Does relative strength persist against Bitcoin in forward excess returns?', ['momentum_5','relative_strength','volatility_20','volume_ratio'], 'excess_return')
    h3 = hyp('Can volatility-conditioned price and volume features discriminate positive subsequent returns?',
        ['momentum_5','momentum_20','volatility_20','volume_ratio','drawdown_60'], 'direction')
    h4 = hyp('Do historically recorded funding and open-interest changes add forecast evidence?',
        ['momentum_5','funding','open_interest_change'])
    specs = [('A_mean',h1,'mean',5),('B_momentum',h1,'momentum',5),('C_ridge',h1,'ridge',5),('D_ensemble',h1,'ensemble',5),
        ('E_relative_strength',h2,'ridge',10),('F_volatility_direction',h3,'logistic',5),('G_funding_oi',h4,'ridge',5)]
    results = []; experiment_ids = []
    for label, h, model, horizon in specs:
        t = time.perf_counter()
        d = ExperimentDefinition(hypothesis_id=UUID(h['hypothesis_id']), dataset=ExperimentDataset(manifest_id=head, source_as_of=cutoff,
            start=date(2024,1,1), end=date(2026,10,3), horizon_sessions=horizon), model=ModelDefinition(registry_id=model),
            quant_run_ids=[backtest.run_id])
        record = s.register(d); k = UUID(record['experiment_id']); experiment_ids.append(k)
        result = s.run(k)['result']; replay = s.replay(k)
        assert replay['status'] == 'MATCH'
        metrics = result['result']['reports']['metrics']
        results.append({'label': label, 'experiment_id': str(k), 'definition_hash': record['content_hash'], 'source_hash': record['source_hash'],
            'hypothesis_id': h['hypothesis_id'], 'model': model, 'target': h['hypothesis']['target'], 'horizon_sessions': horizon,
            'status': result['result']['status'], 'conclusion': result['result']['conclusion'], 'result_hash': result['result_hash'],
            'dataset_ref': result['dataset_ref'], 'model_refs': result['model_refs'], 'metrics': metrics,
            'fold_metrics': [{key: f[key] for key in ('fold','training_window','test_window','train_N','test_N','selected_alpha','metrics','mean_baseline','probability_status')} for f in result['result']['reports']['folds']],
            'holdout_status': result['manifest']['holdout_status'], 'calibration': result['result']['reports']['calibration'],
            'robustness': result['result']['reports']['robustness'], 'uncertainty': result['result']['reports']['uncertainty'],
            'search': result['result']['reports']['multiple_testing'], 'replay': replay, 'elapsed_run_and_replay_s': round(time.perf_counter()-t,2)})
        print(label, result['result']['status'], result['result']['conclusion'], 'N='+str(metrics['N']), 'skill='+str(metrics.get('baseline_skill')), flush=True)
    comparison = s.compare(ExperimentComparison(experiment_ids=experiment_ids[:4]))
    analogue = s.analogue(AnalogueRequest(experiment_id=experiment_ids[2], reference_date=date(2026,9,15), symbol='BTCUSDT'))
    if edge:
        edge_before = edge[1]
        link = s.attach_edge(ExperimentEdgeInput(experiment_id=experiment_ids[2], edge_id=edge[0], stance='INCONCLUSIVE',
            reason='Previously examined retrospective forecasts cannot establish a supported trading edge.'))
        with connect(dsn) as db: assert db.execute('SELECT payload FROM edge_library WHERE edge_id=%s', (edge[0],)).fetchone()[0] == edge_before
    else: link = None
    dossier = mission(s, ExperimentMissionInput(experiment_id=experiment_ids[2], max_tool_calls=8, personalization_snapshot_id=profile.snapshot_id))
    dossier_replay = replay_dossier(s, UUID(dossier['artifact_id'])); assert dossier_replay['status'] == 'MATCH'
    # A poor result can be rejected explicitly without changing the canonical detector.
    rejected = next((UUID(r['experiment_id']) for r in results if r['conclusion'] == 'HYPOTHESIS_FALSIFIED'), None)
    governance = s.store.govern(PromotionDecision(experiment_id=rejected, decision='REJECTED', reason='Forecasts fail the registered error-improvement requirement; retain negative evidence.'), 'PILOT_TEST') if rejected else None
    assert counts() == before and c.head() == head
    report = {'validated_at': datetime.now(timezone.utc).isoformat(), 'source_as_of': cutoff.isoformat(), 'environment': 'PILOT_TEST', 'data_mode': 'REAL_STORED_BINANCE; NO_NEW_LIVE_FETCH',
        'market_head': str(head), 'implementation_hash': IMPLEMENTATION_HASH, 'source_period': ['2024-01-01','2026-10-03'],
        'source_observation_N': before['observations'], 'experiments': results, 'comparison_ref': comparison, 'analogue_ref': analogue,
        'edge_link': link, 'governance': governance, 'dossier_ref': dossier, 'dossier_replay': dossier_replay,
        'canonical_backtest': {'run_id': str(backtest.run_id), 'metrics': backtest.metrics, 'replay': quant.replay(backtest.run_id)},
        'prior_negative': {'artifact_id': str(negative[0]), 'oos_return': -.07817165407921722, 'N': 82, 'holdout': 'PREVIOUSLY_EXAMINED'},
        'owner_history': {'status': profile.observed_behavior['history_state'], 'genuine_owner_N': 0},
        'canonical_counts_before': before, 'canonical_counts_after': counts(), 'owner_main': 'UNTOUCHED',
        'paid_api_cost_inr': 0, 'unseen_validation': 'NOT_ESTABLISHED', 'conclusion': 'NO_SUPPORTED_EDGE_ESTABLISHED',
        'deferred': {'Upstox': 'DEFERRED_NOT_CONFIGURED', 'Alpaca': 'DEFERRED_NOT_CONFIGURED'},
        'elapsed_total_s': round(time.perf_counter()-started,2)}
    (output/'PHASE_12_PILOT_RESULTS.json').write_text(json.dumps(report, indent=2, default=str), encoding='utf-8')
    print('All stored experiments and dossier replayed; owner history remains insufficient; canonical market data unchanged.', flush=True)


if __name__ == '__main__': main()
