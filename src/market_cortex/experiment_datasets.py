"""Derived research rows over the canonical replay catalog and indicator engine.

Targets live in a separate row field. Context is always actually recorded; price
reconstruction assumptions never propagate to contextual availability.
"""
from datetime import datetime, time, timedelta, timezone
from collections import defaultdict
from uuid import UUID
import math
import numpy as np
from .identity import IdentityRegistry, IdentityError
from .indicators import calculate
from .quant_replay import ReplayCatalog, days
from .quant_store import digest

FEATURE_VERSION = 'experimental_causal_daily_v1'
WARMUP = 61


def stamp(day, lag=60):
    return datetime.combine(day, time.min, timezone.utc) + timedelta(days=1, seconds=lag)


def feature_values(columns):
    """Canonical Phase 2 calculations; all windows are causal and finite."""
    values = {
        'momentum_5': calculate('rolling_return', columns, {'period': 5}),
        'momentum_20': calculate('rolling_return', columns, {'period': 20}),
        'trend_persistence': calculate('trend_persistence', columns, {'period': 20}),
        'volatility_20': calculate('rolling_std', columns, {'period': 20}),
        'volume_ratio': calculate('relative_volume', columns, {'period': 20}),
    }
    # Deliberately finite 60-session drawdown, distinct from canonical running drawdown.
    close = columns['close']
    values['drawdown_60'] = np.array([close[i]/np.max(close[i-59:i+1])-1 if i >= 59 and
        np.isfinite(close[i-59:i+1]).all() else np.nan for i in range(len(close))])
    return values


def label_value(target, current, future, benchmark_current=None, benchmark_future=None):
    if not future or any(b is None for b in future): return None
    closing = np.array([float(b.close) for b in future]); base = float(current.close)
    r = float(closing[-1]/base-1)
    if target == 'return': return r
    if target == 'direction': return float(r > 0)
    if target == 'excess_return':
        if benchmark_current is None or not benchmark_future or any(b is None for b in benchmark_future): return None
        return r - float(benchmark_future[-1].close/benchmark_current.close-1)
    if target == 'volatility':
        if len(closing) < 2: return None
        return float(np.std(np.diff(np.log(np.r_[base, closing])), ddof=1))
    if target == 'mae': return min(0., min(float(b.low)/base-1 for b in future))
    if target == 'mfe': return max(0., max(float(b.high)/base-1 for b in future))
    raise ValueError('UNREGISTERED_TARGET')


def eligible_context(frozen, cutoff, symbol, classification='LIVE_SOURCE'):
    result = {}; latest = {}
    head_time = frozen.get('created_at')
    if not head_time: return result
    for f in frozen.get('facts', []):
        e = f['envelope']; oid = e['observation_id']
        manifest_at = frozen.get('fact_manifest_times', {}).get(oid, head_time)
        times = [e.get('available_at'), e.get('ingested_at'), frozen.get('recorded_at', {}).get(oid), manifest_at]
        if any(not t or datetime.fromisoformat(t) > cutoff for t in times): continue
        if f.get('validation_state') != 'validated' or f.get('classification_scope') != classification: continue
        if e.get('quality_state') != 'valid' or datetime.fromisoformat(e['event_at']) > cutoff: continue
        # TTL is a research safeguard; no indefinitely forward-filled context.
        if cutoff-datetime.fromisoformat(e['event_at']) > timedelta(days=3): continue
        key = f.get('logical_key', oid)
        if key not in latest or f['revision_number'] > latest[key]['revision_number']: latest[key] = f
    interest = defaultdict(list)
    for f in sorted(latest.values(), key=lambda f: (f['envelope']['event_at'], f['revision_number'])):
        contract = f.get('contract', {})
        if f['domain'] == 'derivatives' and contract.get('native_id') == symbol and datetime.fromisoformat(contract['known_at']) <= cutoff:
            if f['kind'] == 'funding': result['funding'] = {'value': float(f['value']), 'observation_id': f['envelope']['observation_id']}
            if f['kind'] == 'open_interest': interest[contract['instrument_id']].append(f)
        # Only a registered Treasury Bills average outstanding interest series;
        # explicitly NOT a risk-free, policy, or market yield.
        if f['domain'] == 'macro' and f.get('series_id') == 'avg_interest_rate_amt':
            value = f.get('value')
            if value is not None: result['macro_rate'] = {'value': float(value), 'observation_id': f['envelope']['observation_id']}
    for facts in interest.values():
        if len(facts) >= 2 and float(facts[-2]['value']) > 0:
            result['open_interest_change'] = {'value': float(facts[-1]['value'])/float(facts[-2]['value'])-1,
                'observation_id': facts[-1]['envelope']['observation_id']}
    return result


def build_dataset(source, definition, hypothesis, check=lambda: None):
    d = definition.dataset; horizon = d.horizon_sessions
    replay = ReplayCatalog(source, d.replay_policy, d.publication_lag_seconds)
    registry = IdentityRegistry(*replay.load_identity())
    timeline = days(d.start-timedelta(days=WARMUP), d.end)
    data = {}; ids = {}; calendars = {}
    for symbol in sorted(set(hypothesis.symbols + ['BTCUSDT'])):
        check()
        try:
            instrument = registry.resolve(provider_id='binance', identifier_type='exchange_pair', identifier_value=symbol,
                                          at=stamp(d.start), known_at=d.source_as_of)
        except IdentityError:
            data[symbol] = {}; continue
        ids[symbol] = str(instrument.instrument_id)
        cal = replay.load_calendar(instrument.primary_venue_id, stamp(timeline[0]), d.source_as_of)
        if cal.venue.session_kind != '24x7': raise ValueError('EXPERIMENT_REQUIRES_VERIFIED_24X7_CALENDAR')
        calendars[symbol] = {'calendar_id': cal.calendar_id, 'version': cal.version, 'timezone': cal.venue.timezone}
        _, bars = replay.bars(instrument_id=instrument.instrument_id,
            start=datetime.combine(timeline[0], time.min, timezone.utc), end=d.source_as_of,
            as_of=d.source_as_of, manifest_id=d.manifest_id)
        data[symbol] = {b.session_date: b for b in bars}
    rows = []; reference_rows = []; missing = defaultdict(int); exclusions = defaultdict(int)
    cached_features = {}
    if d.replay_policy == 'HISTORICAL_RECONSTRUCTION':
        for symbol, by_date in data.items():
            columns = {f: np.array([float(getattr(by_date[day], f)) if day in by_date else np.nan for day in timeline])
                       for f in ('open', 'high', 'low', 'close', 'volume')}
            cached_features[symbol] = feature_values(columns)
    context_source = source.get('contextual', {})
    context_times = context_source.get('fact_manifest_times', {}).values()
    context_start = min((datetime.fromisoformat(t) for t in context_times), default=None)
    for i, day in enumerate(timeline):
        if day < d.start: continue
        if i % 20 == 0: check()
        cutoff = stamp(day, d.publication_lag_seconds)
        if cutoff > d.source_as_of: continue
        window = timeline[max(0, i-WARMUP+1):i+1]
        features = {}; histories = {}
        for symbol in sorted(data):
            history = [data[symbol].get(x) for x in window]
            if d.replay_policy == 'AS_RECORDED' and symbol in ids:
                # Re-select each version at the feature row's actual knowledge time.
                _, known = replay.bars(instrument_id=UUID(ids[symbol]),
                    start=datetime.combine(window[0], time.min, timezone.utc), end=cutoff,
                    as_of=cutoff, manifest_id=d.manifest_id)
                by = {b.session_date: b for b in known}; history = [by.get(x) for x in window]
            histories[symbol] = history
            if symbol in cached_features:
                features[symbol] = {k: float(v[i]) if math.isfinite(float(v[i])) else None for k, v in cached_features[symbol].items()}
            else:
                columns = {f: np.array([float(getattr(b, f)) if b else np.nan for b in history])
                           for f in ('open', 'high', 'low', 'close', 'volume')}
                features[symbol] = {k: float(v[-1]) if len(v) and math.isfinite(float(v[-1])) else None
                                    for k, v in feature_values(columns).items()}
        momenta = [v['momentum_20'] for v in features.values() if v['momentum_20'] is not None]
        btc = histories.get('BTCUSDT', [])
        for symbol in hypothesis.symbols:
            history = histories.get(symbol, [])
            if len(history) < WARMUP or any(b is None for b in history):
                exclusions['MISSING_OR_NOT_KNOWN_PRICE_HISTORY'] += 1; continue
            current = history[-1]; values = features[symbol].copy()
            bm = features.get('BTCUSDT', {}).get('momentum_20')
            values['relative_strength'] = None if bm is None else values['momentum_20']-bm
            values['dispersion'] = float(np.std(momenta, ddof=1)) if len(momenta) == 5 else None
            values['correlation_btc'] = None
            if len(btc) >= 21 and all(b is not None for b in btc[-21:]):
                x = np.diff(np.log([float(b.close) for b in history[-21:]]))
                y = np.diff(np.log([float(b.close) for b in btc[-21:]]))
                if np.std(x) > 0 and np.std(y) > 0: values['correlation_btc'] = float(np.corrcoef(x, y)[0, 1])
            context = eligible_context(context_source, cutoff, symbol, d.source_classification) if context_start is None or cutoff >= context_start else {}
            for name in ('funding', 'open_interest_change', 'macro_rate'): values[name] = context.get(name, {}).get('value')
            selected = {k: values[k] for k in hypothesis.features}
            for k, v in selected.items():
                if v is None: missing[k] += 1
            future_dates = [day+timedelta(days=j) for j in range(1, horizon+1)]
            future = [data[symbol].get(x) for x in future_dates]
            benchmark_future = [data.get('BTCUSDT', {}).get(x) for x in future_dates]
            target = label_value(hypothesis.target, current, future,
                data.get('BTCUSDT', {}).get(day), benchmark_future)
            if target is None or any(x > d.end for x in future_dates):
                reference_rows.append({'session': str(day), 'symbol': symbol, 'instrument_id': ids[symbol],
                    'feature_at': cutoff.isoformat(), 'features': selected,
                    'observation_id': str(current.envelope.observation_id),
                    'input_hash': digest([str(b.envelope.observation_id) for b in history]),
                    'input_sessions': [str(window[0]), str(day)],
                    'actual_input_known_at': max(max(b.envelope.available_at, b.envelope.ingested_at,
                        replay.manifest_times[str(replay._manifest(b))]) for b in history).isoformat(),
                    'context_observation_ids': [f['observation_id'] for f in context.values()],
                    'label_status': 'TARGET_UNAVAILABLE; FEATURE_ONLY_REFERENCE'})
                exclusions['TARGET_UNAVAILABLE'] += 1; continue
            outcome_records = future + (benchmark_future if hypothesis.target == 'excess_return' else [])
            label_actual = max(max(b.envelope.available_at, b.envelope.ingested_at,
                replay.manifest_times[str(replay._manifest(b))]) for b in outcome_records)
            label_known = label_actual if d.replay_policy == 'AS_RECORDED' else stamp(future_dates[-1], d.publication_lag_seconds)
            if label_actual > d.source_as_of: exclusions['TARGET_AFTER_SOURCE_CUTOFF'] += 1; continue
            m = values['momentum_20']; v = values['volatility_20']
            regime = 'volatile' if v is not None and v >= .035 else 'up' if m and m > .02 else 'down' if m and m < -.02 else 'range'
            rows.append({'session': str(day), 'symbol': symbol, 'instrument_id': ids[symbol],
                'feature_at': cutoff.isoformat(), 'features': selected, 'regime': regime,
                'observation_id': str(current.envelope.observation_id),
                'input_hash': digest([str(b.envelope.observation_id) for b in history]),
                'input_sessions': [str(window[0]), str(day)],
                'actual_input_known_at': max(max(b.envelope.available_at, b.envelope.ingested_at,
                    replay.manifest_times[str(replay._manifest(b))]) for b in history).isoformat(),
                'context_observation_ids': [f['observation_id'] for f in context.values()],
                'label': {'value': target, 'start': str(future_dates[0]), 'end': str(future_dates[-1]),
                    'known_at': label_known.isoformat(), 'actual_known_at': label_actual.isoformat(),
                    'observation_ids': [str(b.envelope.observation_id) for b in outcome_records]}})
            if len(rows) > definition.configuration.max_rows: raise ValueError('DATASET_ROW_LIMIT')
    return {'rows': rows, 'reference_rows': reference_rows, 'source_manifest_id': str(d.manifest_id), 'source_as_of': d.source_as_of.isoformat(),
        'feature_version': FEATURE_VERSION, 'feature_versions': {k: FEATURE_VERSION for k in hypothesis.features},
        'feature_parameters': {'momentum': [5, 20], 'volatility': 20, 'drawdown': 60, 'warmup': WARMUP},
        'target': hypothesis.target, 'horizon_sessions': horizon, 'adjustment_basis': 'raw',
        'calendars': calendars, 'provider': 'binance', 'currency': 'USDT', 'identity': ids,
        'source_classification': d.source_classification,
        'missingness': dict(missing), 'exclusions': dict(exclusions), 'row_N': len(rows),
        'context_policy': 'AS_RECORDED_ONLY; MAX_AGE_3_DAYS',
        'regime_definition': 'EXPERIMENTAL_FIXED_PROXY_V1: vol20>=.035 volatile; momentum20 +/- .02; otherwise range. Not canonical Phase 2 state.',
        'warnings': ['SELECTED_SURVIVORS; NOT_HISTORICAL_FULL_UNIVERSE',
            'PRICE_RECONSTRUCTION_IS_NOT_OBSERVED_HISTORICAL_KNOWLEDGE' if d.replay_policy == 'HISTORICAL_RECONSTRUCTION' else 'ACTUAL_RECORDED_KNOWLEDGE',
            'TARGETS_SEPARATE_FROM_FEATURES; OVERLAPPING_LABELS_DEPENDENT',
            'CONTEXT_ABSENCE_IS_NOT_ZERO; NO_BACKFILL_OF_LATER_KNOWLEDGE']}
