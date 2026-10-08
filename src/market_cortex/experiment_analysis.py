"""Descriptive research diagnostics. No significance or edge promotion shortcuts."""
from collections import defaultdict
from datetime import datetime, timedelta
import numpy as np
from .experiment_models import matrix, targets, score, predict, fit, complete, purge


def metric_groups(predictions, key, task):
    groups = defaultdict(list)
    for r in predictions: groups[key(r)].append(r)
    return [{'group': k, **score(np.array([r['target'] for r in values]),
        np.array([r['prediction'] for r in values]), task)} for k, values in sorted(groups.items())]


def reliability(predictions):
    rows = []
    for lower in np.linspace(0, .8, 5):
        cell = [r for r in predictions if lower <= r['prediction'] <= 1 and
                (r['prediction'] < lower+.2 or lower == .8)]
        rows.append({'lower': float(lower), 'upper': float(lower+.2), 'N': len(cell),
            'forecast_mean': float(np.mean([r['prediction'] for r in cell])) if cell else None,
            'event_rate': float(np.mean([r['target'] for r in cell])) if cell else None})
    return rows


def block_bootstrap(predictions, horizon, paths, seed, task, check=lambda: None):
    # Aggregate cross-sectional dependence first; retain serial dependence via
    # moving contiguous daily blocks. This CI is conditional on the frozen search.
    per_day = defaultdict(list)
    for r in predictions:
        delta = (r['prediction']-r['target'])**2-(r['baseline']-r['target'])**2
        per_day[r['session']].append(delta)
    sessions = sorted(per_day); values = np.array([np.mean(per_day[d]) for d in sessions]); n = len(values)
    if n < max(30, 4*horizon): return {'status': 'INSUFFICIENT_EVIDENCE', 'session_N': n}
    # Do not wrap blocks across fold/calendar gaps.
    starts = [i for i in range(n-horizon+1) if (datetime.fromisoformat(sessions[i+horizon-1])-datetime.fromisoformat(sessions[i])).days == horizon-1]
    if not starts: return {'status': 'INSUFFICIENT_EVIDENCE', 'session_N': n}
    rng = np.random.default_rng(seed); means = []
    for _ in range(paths):
        check(); sample = np.concatenate([values[i:i+horizon] for i in rng.choice(starts, size=int(np.ceil(n/horizon)), replace=True)])[:n]
        means.append(float(sample.mean()))
    return {'status': 'EMPIRICAL_CONDITIONAL_UNCERTAINTY', 'method': 'MOVING_DAILY_BLOCKS_AFTER_CROSS_ASSET_AGGREGATION',
        'block_sessions': horizon, 'session_N': n, 'paths': paths, 'seed': seed,
        'mean_model_minus_baseline_squared_loss': float(values.mean()),
        'conditional_95pct_interval': [float(np.percentile(means, 2.5)), float(np.percentile(means, 97.5))],
        'warning': 'NOT_PRICE_FORECAST_PROBABILITY; CONDITIONAL_ON_SEARCH; NO_SELECTION_CORRECTION; BLOCK_CHOICE_ASSUMPTION'}


def diagnostics(dataset, evaluation, definition, hypothesis, check=lambda: None):
    rows = dataset['rows']; p = evaluation['predictions']; task = 'classification' if hypothesis.target == 'direction' else 'regression'
    y = np.array([r['target'] for r in p]); forecast = np.array([r['prediction'] for r in p]); baseline = np.array([r['baseline'] for r in p])
    metrics = score(y, forecast, task); base = score(y, baseline, task); objective = 'brier' if task == 'classification' else 'rmse'
    metrics['baseline_skill'] = 1-metrics[objective]/base[objective] if base.get(objective) else None
    asset = metric_groups(p, lambda r: r['symbol'], task); regimes = metric_groups(p, lambda r: r['regime'], task)
    periods = metric_groups(p, lambda r: r['session'][:4], task)
    importance = []; ablation = []; factors = []; shifts = []; correlation = []
    for fold in evaluation['folds']:
        check(); model = fold['model']; names = model['features']; fold_n = fold['fold']
        training = complete([r for r in rows if fold['training_window'][0] <= r['session'] <= fold['training_window'][1] and
            datetime.fromisoformat(r['label']['known_at']) <= datetime.fromisoformat(fold['training_label_cutoff'])], names)
        testing = complete([r for r in rows if fold['test_window'][0] <= r['session'] <= fold['test_window'][1]], hypothesis.features)
        if not testing or not training: continue
        x = matrix(training, names); xt = matrix(testing, names); target = targets(testing)
        original = predict(model, testing, calibrated=True)
        original_loss = float(np.mean((target-original)**2))
        zshift = (xt.mean(axis=0)-x.mean(axis=0))/np.maximum(x.std(axis=0), 1e-12)
        maxshift = float(np.max(np.abs(zshift)))
        shifts.append({'fold': fold_n, 'train_N': len(training), 'test_N': len(testing),
            'standardized_mean_shift': {f: float(v) for f, v in zip(names, zshift)},
            'max_absolute_shift': maxshift, 'status': 'INSUFFICIENT_EVIDENCE' if len(testing) < 100 else
                'DEGRADED' if maxshift > 2 else 'WATCH' if maxshift > 1 else 'STABLE',
            'residual_rmse': float(np.sqrt(original_loss)), 'thresholds': 'Research heuristic: >1 WATCH, >2 DEGRADED; not calibrated alarms'})
        for j, f in enumerate(names):
            # Rotate contiguous temporal blocks within each asset; no per-row iid shuffle.
            altered = [{**r, 'features': dict(r['features'])} for r in testing]
            by_symbol = defaultdict(list)
            for i, r in enumerate(testing): by_symbol[r['symbol']].append(i)
            for indices in by_symbol.values():
                values = [testing[i]['features'][f] for i in indices]
                offset = min(len(values)-1, definition.dataset.horizon_sessions*2)
                rotated = values[offset:]+values[:offset]
                for i, value in zip(indices, rotated): altered[i]['features'][f] = value
            changed = float(np.mean((target-predict(model, altered, calibrated=True))**2))-original_loss
            importance.append({'fold': fold_n, 'feature': f, 'coefficient_standardized': model['coefficients'][j],
                'block_rotation_loss_increase': changed, 'test_N': len(testing), 'interpretation': 'DIAGNOSTIC_NOT_CAUSAL; OOS_NOW_EXAMINED'})
            if len(names) > 1 and model['registry_id'] not in ('mean', 'momentum'):
                reduced = [k for k in names if k != f]
                refit = fit(training, reduced, model['registry_id'], model['alpha'], task, len(reduced), definition.model.max_iterations, check)
                ablation.append({'fold': fold_n, 'removed': f, 'rmse': score(target, predict(refit, testing), task)['rmse'],
                    'N': len(testing), 'stage': 'EXPLORATORY_FIXED_OUTER_TRAIN_REFIT; CALIBRATION_NOT_REFIT'})
            yy = targets(training)
            corr = float(np.corrcoef(x[:, j], yy)[0, 1]) if np.std(x[:, j]) > 1e-12 and np.std(yy) > 1e-12 else None
            trimmed = (x[:, j] >= np.quantile(x[:, j], .05)) & (x[:, j] <= np.quantile(x[:, j], .95))
            trimmed_corr = float(np.corrcoef(x[trimmed, j], yy[trimmed])[0, 1]) if np.std(x[trimmed, j]) > 1e-12 and np.std(yy[trimmed]) > 1e-12 else None
            factors.append({'fold': fold_n, 'feature': f, 'train_N': len(training), 'pearson': corr,
                'trimmed_pearson': trimmed_corr, 'coefficient': model['coefficients'][j], 'claim': 'ASSOCIATION_NOT_CAUSATION'})
        for i, a in enumerate(names):
            for j in range(i+1, len(names)):
                b = names[j]; value = float(np.corrcoef(x[:, i], x[:, j])[0, 1]) if np.std(x[:, i]) > 1e-12 and np.std(x[:, j]) > 1e-12 else None
                correlation.append({'fold': fold_n, 'features': [a, b], 'correlation': value,
                    'redundant_heuristic': value is not None and abs(value) > .9})
    transitions = defaultdict(int); duration = defaultdict(list)
    for symbol in hypothesis.symbols:
        sequence = sorted([r for r in rows if r['symbol'] == symbol], key=lambda r: r['session'])
        length = 0; previous = None; last_day = None
        for r in sequence:
            if last_day and (datetime.fromisoformat(r['session'])-datetime.fromisoformat(last_day)).days != 1:
                if previous: duration[previous].append(length)
                previous = None; length = 0
            if previous is not None: transitions[previous+'->'+r['regime']] += 1
            if previous is not None and r['regime'] != previous: duration[previous].append(length); length = 0
            previous = r['regime']; length += 1; last_day = r['session']
        # Last run is censored, deliberately not counted as completed duration.
    minimum = min([r['N'] for r in asset+regimes+periods] or [0])
    positive = [f['metrics']['baseline_skill'] for f in evaluation['folds'] if f['metrics']['baseline_skill'] is not None]
    robust_status = 'INSUFFICIENT_EVIDENCE' if minimum < 30 else 'MIXED' if positive and sum(x > 0 for x in positive) >= len(positive)/2 else 'FRAGILE'
    costs = definition.configuration.costs
    total_bps = costs.entry_fee_bps+costs.exit_fee_bps+2*costs.slippage_bps+costs.spread_bps
    cost_rows = []
    if hypothesis.target in ('return', 'excess_return'):
        # A diagnostic decision-rule proxy, not a second fill/backtest engine.
        # Nonoverlapping anchors per fold; equal asset weights; no compounded overlapping labels.
        anchor = defaultdict(list)
        for r in p: anchor[(r['fold'], r['session'])].append(r)
        for multiplier in (0., 1., 2., 4.):
            values = []; count = 0
            for fold in sorted({r['fold'] for r in p}):
                cells = sorted((d, v) for (f, d), v in anchor.items() if f == fold)
                for _, cell in cells[::definition.dataset.horizon_sessions]:
                    values.append(float(np.mean([r['target']-multiplier*total_bps/10000 if r['prediction'] > 0 else 0. for r in cell])))
                    count += sum(r['prediction'] > 0 for r in cell)
            cost_rows.append({'cost_multiplier': multiplier, 'anchor_N': len(values), 'active_asset_N': count,
                'mean_proxy_net_return': float(np.mean(values)) if values else None})
    return {'metrics': metrics, 'mean_baseline': base, 'asset_research': asset, 'regime_research': regimes, 'period_research': periods,
        'feature_importance': importance, 'feature_redundancy': correlation, 'factor_research': factors,
        'feature_ablation': ablation, 'drift': shifts,
        'regime_transitions': {'counts': dict(transitions), 'completed_durations': {k: {'N': len(v), 'mean_sessions': float(np.mean(v))} for k, v in duration.items()},
            'probability_status': 'PROBABILITY_UNAVAILABLE; DESCRIPTIVE_COUNTS_ONLY'},
        'robustness': {'classification': robust_status, 'minimum_cell_N': minimum, 'cost_sensitivity': cost_rows,
            'warning': 'FORECAST_RULE_COST_PROXY; NO_BAR_FILL_CLAIM; USE_CANONICAL_QUANT_BACKTEST_FOR_TRADE_SIMULATION',
            'missingness': dataset['missingness'], 'sample_fraction': evaluation['complete_case_N']/max(1, len(rows)),
            'delay_slippage_stress': 'REGISTERED_QUANT_ROBUSTNESS_TOOL', 'fixed_fee': costs.fixed_fee,
            'fixed_fee_status': 'NOT_APPLIED_TO_RETURN_PROXY_WITHOUT_NOTIONAL'},
        'calibration': {'status': 'EXPERIMENTAL_CALIBRATED' if task == 'classification' and evaluation['folds'] and
            all(f['probability_status'] == 'EXPERIMENTAL_CALIBRATED' for f in evaluation['folds']) else 'PROBABILITY_UNAVAILABLE',
            'event': 'Positive raw forward close return' if task == 'classification' else None,
            'horizon_sessions': definition.dataset.horizon_sessions, 'bins': reliability(p) if task == 'classification' else [],
            'warning': 'Temporal experimental diagnostics; dependent observations; no calibrated live market forecast'},
        'uncertainty': block_bootstrap(p, definition.dataset.horizon_sessions, definition.configuration.bootstrap_paths,
            definition.configuration.seed, task, check),
        'multiple_testing': {'parameter_variants': len(evaluation['search']), 'ablation_variants': len(ablation),
            'objective': objective, 'fdr': 'STATISTICAL_METHOD_UNAVAILABLE: NO_VALID_P_VALUES',
            'deflated_sharpe': 'STATISTICAL_METHOD_UNAVAILABLE: NO_INDEPENDENT_NET_RETURN_TRIALS',
            'pbo': 'STATISTICAL_METHOD_UNAVAILABLE: TEMPORAL_SEARCH_NOT_COMBINATORIAL_CV',
            'warning': 'ALL_SEARCH_ROWS_RETAINED; DEPENDENT_SAMPLE; NO_SIGNIFICANCE_CLAIM'},
        'meta_labeling': {'status': 'INSUFFICIENT_EVIDENCE', 'reason': 'Requires PIT candidates, rejected coverage and representative outcome ledger; not inferred from selected experiments'}}


def analogues(dataset, request):
    ref = next((r for r in dataset['rows']+dataset.get('reference_rows', []) if r['session'] == str(request.reference_date) and r['symbol'] == request.symbol), None)
    if ref is None: raise LookupError('ANALOGUE_REFERENCE_UNAVAILABLE')
    features = [k for k, v in ref['features'].items() if v is not None]
    if not features: raise ValueError('ANALOGUE_FEATURES_UNAVAILABLE')
    cutoff = datetime.fromisoformat(ref['feature_at'])
    candidates = complete([r for r in dataset['rows'] if r['symbol'] == request.symbol and
        r['session'] < str(request.reference_date-timedelta(days=request.minimum_separation_sessions)) and
        datetime.fromisoformat(r['label']['known_at']) < cutoff], features)
    if len(candidates) < 30: raise ValueError('INSUFFICIENT_ANALOGUE_HISTORY')
    x = matrix(candidates, features); means = x.mean(axis=0); scales = x.std(axis=0); scales[scales < 1e-12] = 1.
    reference = matrix([ref], features)[0]; distances = np.sqrt(np.mean(((x-reference)/scales)**2, axis=1))
    ordered = sorted(zip(distances, candidates), key=lambda pair: (pair[0], pair[1]['session']))
    matches = []
    for distance, r in ordered:
        if any(abs((datetime.fromisoformat(r['session'])-datetime.fromisoformat(m['session'])).days) < request.minimum_separation_sessions for m in matches): continue
        matches.append({'session': r['session'], 'symbol': r['symbol'], 'distance': float(distance),
            'differences': {k: float(r['features'][k]-ref['features'][k]) for k in features},
            'historical_outcome': r['label'], 'observation_id': r['observation_id']})
        if len(matches) == request.limit: break
    return {'reference': {k: v for k, v in ref.items() if k != 'label'}, 'matches': matches, 'candidate_N': len(candidates),
        'features': features, 'scaler': {'means': means.tolist(), 'scales': scales.tolist()},
        'selection': 'PAST_FEATURE_DISTANCE_ONLY; OUTCOMES_READ_AFTER_SELECTION; PAST_TRAIN_SCALING',
        'warning': 'HISTORICAL_ANALOGUES_ARE_NOT_FORECAST_PROBABILITIES; PRICE_RECONSTRUCTION_ASSUMPTIONS_IN_DATASET'}
