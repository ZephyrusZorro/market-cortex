"""Deterministic descriptive context; no direction guarantees or learned edge."""
import math
import re
from pathlib import Path
from datetime import timedelta
from difflib import SequenceMatcher
from uuid import NAMESPACE_URL, uuid5

import numpy as np

from .intelligence_contracts import ContextDimension, ContextRequest, ContextSnapshot, EventFact, NewsEvent
from .intelligence_store import ContextStore, digest, visible

DOMAINS = ('macro', 'fundamentals', 'events', 'news', 'derivatives', 'options', 'onchain')
CALCULATION_CODE_HASH = digest({name: Path(__file__).with_name(name).read_bytes().replace(b'\r\n', b'\n').decode()
                               for name in ('intelligence.py', 'intelligence_contracts.py', 'intelligence_store.py')})


def deduplicate_news(facts):
    """Conservative groups, not a claim that similar headlines are independent evidence."""
    groups = []
    for f in sorted(facts, key=lambda f: (f.envelope.event_at, str(f.envelope.observation_id))):
        title = ' '.join(re.findall(r'\w+', f.title.lower()))
        target = None
        for group in groups:
            prior = group[0]
            same_scope = (f.entity.kind, f.entity.key) == (prior.entity.kind, prior.entity.key) and f.category == prior.category
            same_time = abs((f.envelope.event_at-prior.envelope.event_at).total_seconds()) <= 86400
            related = f.syndication_id and f.syndication_id == prior.syndication_id
            similar = SequenceMatcher(None, title, ' '.join(re.findall(r'\w+', prior.title.lower()))).ratio() >= .85
            if same_scope and same_time and (related or similar):
                target = group
                break
        if target is None:
            groups.append([f])
        else:
            target.append(f)
    return [{'group_id': digest(sorted(str(f.envelope.observation_id) for f in g)),
             'article_ids': [str(f.envelope.observation_id) for f in g],
             'independent_event_count': 1, 'rule': 'entity_category_24h_syndication_or_title85_v1'} for g in groups]


def conflicts(facts):
    groups = {}
    for f in facts:
        if isinstance(f, NewsEvent) and f.assertion_key and f.assertion_value:
            key = (f.domain, f.entity.kind, f.entity.key, f.assertion_key, f.envelope.event_at.date())
            groups.setdefault(key, []).append(f)
        elif hasattr(f, 'metric') and hasattr(f, 'value'):
            key = (f.domain, f.entity.kind, f.entity.key, f.metric, f.period_start, f.period_end,
                   f.envelope.event_at if not f.period_end else None, f.envelope.unit, f.envelope.currency)
            groups.setdefault(key, []).append(f)
    value = lambda f: f.assertion_value if isinstance(f, NewsEvent) else str(f.value)
    return [{'metric': g[0].assertion_key if isinstance(g[0], NewsEvent) else g[0].metric, 'fact_ids': [str(f.envelope.observation_id) for f in g],
             'sources': [f.envelope.provider_id for f in g], 'values': [value(f) for f in g],
             'available_at': [f.envelope.available_at.isoformat() for f in g],
             'resolution': 'UNRESOLVED', 'preferred_source': None, 'policy': 'preserve_both_v1'}
            for g in groups.values() if len({value(f) for f in g}) > 1 and len({f.envelope.provider_id for f in g}) > 1]


def event_risk(facts, cutoff, instrument_id=None, horizon_days=10):
    end = cutoff+timedelta(days=horizon_days)
    relevant = [f for f in facts if isinstance(f, EventFact) and f.validation_state == 'validated' and
                f.envelope.quality_state in ('valid', 'corrected') and
                f.classification == 'SOURCE_FACT' and (instrument_id is None or f.entity.key == str(instrument_id) or
                instrument_id in f.related_instrument_ids)]
    upcoming = [f for f in relevant if cutoff <= f.scheduled_at <= end]
    high = [f for f in upcoming if f.importance == 'high' and f.importance_source]
    recent = [f for f in relevant if cutoff-timedelta(days=1) <= f.scheduled_at < cutoff]
    complete = any(f.calendar_complete_until and f.calendar_complete_until >= end for f in relevant)
    if upcoming:
        state = 'EVENT_IMMINENT' if min(f.scheduled_at for f in upcoming)-cutoff <= timedelta(days=1) else 'EVENT_UPCOMING'
    elif recent:
        state = 'EVENT_RECENT'
    else:
        state = 'NO_KNOWN_EVENT' if complete else 'EVENT_DATA_UNAVAILABLE'
    return {'version': 'event_proximity_v1', 'state': state, 'horizon_days': horizon_days,
            'horizon_end': end.isoformat(), 'high_impact_in_horizon': bool(high),
            'fact_ids': [str(f.envelope.observation_id) for f in upcoming or recent],
            'transition_fact_ids': [str(f.envelope.observation_id) for f in high],
            'calendar_coverage_complete': complete,
            'reason': 'SOURCED_RELEVANT_EVENT' if upcoming or recent else 'VERIFIED_COMPLETE_CALENDAR' if complete else 'NO_VERIFIED_CALENDAR_COVERAGE'}


def derivatives(facts):
    facts = [f for f in facts if f.classification == 'SOURCE_FACT' and f.validation_state == 'validated' and f.envelope.quality_state in ('valid', 'corrected')]
    contracts = {f.contract.instrument_id for f in facts}
    if len(contracts) != 1:
        return {'reason': 'SELECT_ONE_EXACT_DERIVATIVE_CONTRACT', 'contract_count': len(contracts)}
    funding = sorted((f for f in facts if f.kind == 'funding'), key=lambda f: f.envelope.event_at)
    oi = sorted((f for f in facts if f.kind == 'open_interest'), key=lambda f: f.envelope.event_at)
    mark = sorted((f for f in facts if f.kind == 'mark_index'), key=lambda f: f.envelope.event_at)
    output = {'funding_N': len(funding), 'oi_N': len(oi), 'directional_implication': 'NONE_DESCRIPTIVE_ONLY',
              'contextual_backtest_status': 'INSUFFICIENT_AS_RECORDED_HISTORY'}
    if funding:
        values = [float(f.value) for f in funding]
        output.update(funding_latest=values[-1], funding_percentile=sum(v <= values[-1] for v in values)/len(values),
                      funding_positive_fraction=sum(v > 0 for v in values)/len(values),
                      funding_unit='fraction_per_funding_event', funding_event_at=funding[-1].envelope.event_at.isoformat())
        sign = 1 if values[-1] > 0 else -1 if values[-1] < 0 else 0
        n = 0
        for v in reversed(values):
            if (1 if v > 0 else -1 if v < 0 else 0) != sign:
                break
            n += 1
        output['funding_same_sign_events'] = n
    if oi:
        output.update(oi_latest=float(oi[-1].value), oi_unit=oi[-1].envelope.unit,
                      oi_event_at=oi[-1].envelope.event_at.isoformat())
        if len(oi) > 1 and oi[-2].value > 0:
            output['oi_change_fraction'] = float(oi[-1].value/oi[-2].value-1)
            # Funding charges can carry subsecond offsets; allow <=1s clock distance, no interpolation.
            prices = []
            for observation in oi[-2:]:
                matches = [f for f in funding if abs((f.envelope.event_at-observation.envelope.event_at).total_seconds()) <= 1 and f.mark_price is not None]
                prices.append(min(matches, key=lambda f: abs((f.envelope.event_at-observation.envelope.event_at).total_seconds())).mark_price if matches else None)
            output['price_oi_alignment'] = 'funding_event_mark_within_1_second_v1; actual_timestamps_preserved; no_interpolation'
            if all(p is not None and p > 0 for p in prices):
                change = float(prices[1]/prices[0]-1)
                output['aligned_price_change_fraction'] = change
                output['price_oi_state'] = ('PRICE_UP' if change > 0 else 'PRICE_DOWN' if change < 0 else 'PRICE_FLAT') + '_' + (
                    'OI_UP' if output['oi_change_fraction'] > 0 else 'OI_DOWN' if output['oi_change_fraction'] < 0 else 'OI_FLAT')
            else:
                output['price_oi_state'] = 'UNAVAILABLE_NO_ALIGNED_MARKS_WITHIN_1_SECOND'
    if mark and mark[-1].companion_value and mark[-1].companion_value > 0:
        output['mark_index_premium_fraction'] = float(mark[-1].value/mark[-1].companion_value-1)
        output['premium_time'] = mark[-1].envelope.event_at.isoformat()
    return output


def macro_dimensions(facts):
    groups = {}
    for f in facts:
        if f.classification != 'SOURCE_FACT' or f.validation_state != 'validated' or f.envelope.quality_state not in ('valid', 'corrected'):
            continue
        groups.setdefault((f.series_id, f.envelope.provider_id, f.envelope.unit), []).append(f)
    result = {}
    for (series, provider, unit), group in groups.items():
        group.sort(key=lambda f: f.period_end)
        result[f'{provider}:{series}:latest'] = float(group[-1].value)
        result[f'{provider}:{series}:unit'] = unit
        result[f'{provider}:{series}:direction'] = ('UP' if group[-1].value > group[-2].value else 'DOWN' if group[-1].value < group[-2].value else 'FLAT') if len(group) > 1 else 'INSUFFICIENT_HISTORY'
    return result


def fundamental_ratio(numerator, denominator, operation='margin'):
    a, b = numerator, denominator
    if any(f.classification != 'SOURCE_FACT' or f.validation_state != 'validated' or f.envelope.quality_state not in ('valid', 'corrected') for f in (a,b)):
        return {'value': None, 'reason': 'TRUSTED_SOURCE_FACTS_REQUIRED', 'version': 'fundamental_ratio_v1'}
    if (a.issuer_id, a.period_start, a.period_end, a.currency, a.envelope.unit) != (
        b.issuer_id, b.period_start, b.period_end, b.currency, b.envelope.unit):
        return {'value': None, 'reason': 'INCOMPATIBLE_PERIOD_CURRENCY_UNIT', 'version': 'fundamental_ratio_v1'}
    if operation not in ('margin', 'leverage') or b.value == 0:
        return {'value': None, 'reason': 'UNSUPPORTED_RATIO_OR_ZERO_DENOMINATOR', 'version': 'fundamental_ratio_v1'}
    allowed = {'margin': ({'net_income', 'operating_income'}, {'revenue'}),
               'leverage': ({'liabilities'}, {'equity'})}
    if a.metric not in allowed[operation][0] or b.metric not in allowed[operation][1]:
        return {'value': None, 'reason': 'INCOMPATIBLE_METRIC_CONCEPTS', 'version': 'fundamental_ratio_v1'}
    return {'value': str(a.value/b.value), 'unit': 'fraction', 'version': 'fundamental_ratio_v1',
            'source_fact_ids': [str(a.envelope.observation_id), str(b.envelope.observation_id)]}


def build_snapshot(request, manifest_id, facts):
    facts = visible(facts, request.as_of, request.instrument_id)
    dimensions = {}
    for domain in DOMAINS:
        rows = [f for f in facts if f.domain == domain]
        limits = {'macro': 'Only ingested series; no policy/inflation/curve coverage inferred',
                  'fundamentals': 'No verified live equity source', 'events': 'No complete calendar inferred',
                  'news': 'Metadata; syndicated articles do not imply independent events',
                  'derivatives': 'Funding/OI/mark only; liquidation unavailable',
                  'options': 'No verified live chain; no exposure analytics', 'onchain': 'No verified live on-chain source'}
        status = 'PARTIAL' if rows else 'UNKNOWN'
        max_age = timedelta(days=45 if domain == 'macro' else 2 if domain == 'derivatives' else 7)
        if rows and request.as_of-max(f.envelope.ingested_at for f in rows) > max_age:
            status = 'STALE'
        metrics = derivatives(rows) if rows and domain == 'derivatives' else macro_dimensions(rows) if rows and domain == 'macro' else {}
        if domain == 'news' and rows:
            metrics = {'article_count': len(rows), 'event_groups': len(deduplicate_news(rows)), 'independent_confirmation': 'NOT_ESTABLISHED'}
        dimensions[domain] = ContextDimension(status=status, reason=limits[domain] if rows else 'NO_VISIBLE_VERIFIED_FACTS_AT_CUTOFF',
            fact_ids=[f.envelope.observation_id for f in rows], metrics=metrics)
    dimensions['cross_asset'] = ContextDimension(status='UNKNOWN', reason='NO_SYNCHRONIZED_CONTEXTUAL_MARKET_SERIES; USE_PHASE2_ALIGNMENT_FOR_PRICE_PAIRS', fact_ids=[])
    dimensions['market_state'] = ContextDimension(status='PARTIAL' if request.market_manifest_id else 'UNKNOWN',
        reason='CANONICAL_PHASE2_ENGINE_VIA_MARKET_MANIFEST; CONTEXT_DOES_NOT_RECALCULATE_DETECTORS', fact_ids=[],
        metrics={'market_manifest_id': str(request.market_manifest_id) if request.market_manifest_id else None})
    risk = event_risk(facts, request.as_of, request.instrument_id, request.horizon_days)
    warnings = ['PARTIAL_DOMAIN_COVERAGE', 'NO_SUPPORTED_EDGE_FROM_CONTEXT', 'SOURCE_FACT_EXTRACTED_INTERPRETATION_DISTINCT',
                'AS_RECORDED_CONTEXT_ONLY; NO_RETROACTIVE_PUBLICATION_ASSUMPTION']
    if any(f.classification_scope == 'SYNTHETIC_TEST' for f in facts):
        warnings.append('CONTAINS_SYNTHETIC_TEST_FACTS')
    core = dict(schema_version='context_snapshot_v1', calculation_version='context_dimensions_v1', calculation_code_hash=CALCULATION_CODE_HASH,
                context_manifest_id=str(manifest_id) if manifest_id else None,
                market_manifest_id=str(request.market_manifest_id) if request.market_manifest_id else None,
                as_of=request.as_of.isoformat().replace('+00:00', 'Z'), instrument_id=str(request.instrument_id) if request.instrument_id else None,
                dimensions={k: v.model_dump(mode='json') for k, v in dimensions.items()},
                facts=[f.model_dump(mode='json') for f in facts], conflicts=conflicts(facts), event_risk=risk, warnings=warnings)
    h = digest(core)
    return ContextSnapshot(snapshot_id=uuid5(NAMESPACE_URL, 'context-snapshot:'+h), content_hash=h, **core)


class IntelligenceService:
    def __init__(self, catalog):
        self.catalog = catalog
        self.store = ContextStore(catalog)
    def snapshot(self, request, persist=False):
        key = self.store.resolve(request.as_of, request.context_manifest_id)
        result = build_snapshot(request, key, self.store.facts(key, request.as_of, request.instrument_id))
        return self.store.save_snapshot(result) if persist else result
    def compare(self, left, right):
        a, b = self.store.snapshot(left), self.store.snapshot(right)
        if a.instrument_id != b.instrument_id:
            raise ValueError('CONTEXT_COMPARISON_SCOPE_MISMATCH')
        return {'left': str(left), 'right': str(right), 'added_fact_ids': sorted(set(str(f.envelope.observation_id) for f in b.facts)-set(str(f.envelope.observation_id) for f in a.facts)),
                'removed_or_revised_fact_ids': sorted(set(str(f.envelope.observation_id) for f in a.facts)-set(str(f.envelope.observation_id) for f in b.facts)),
                'left_dimensions': {k: v.model_dump(mode='json') for k, v in a.dimensions.items()},
                'right_dimensions': {k: v.model_dump(mode='json') for k, v in b.dimensions.items()}}


def option_analytics(*, price, underlying, strike, years, rate, carry=0., right='call', exercise='european'):
    """European Black-Scholes, supplied price (no automatic mid), bisection [1e-8,5]."""
    details = {'version': 'bs_european_v1', 'price_convention': 'explicit_input_price', 'annual_rate': rate,
               'annual_dividend_carry': carry, 'years': years, 'vol_bracket': [1e-8, 5.], 'max_iterations': 100,
               'tolerance': 1e-8, 'theta_unit': 'price_per_calendar_day', 'vega_rho_unit': 'price_per_unit_fraction'}
    if exercise != 'european' or right not in ('call', 'put') or any(not math.isfinite(v) for v in (price, underlying, strike, years, rate, carry)) or min(underlying, strike, years) <= 0 or not -1 <= rate <= 1 or not -1 <= carry <= 1 or years > 100 or max(price, underlying, strike) > 1e12 or min(underlying, strike) < 1e-8:
        return {**details, 'status': 'INVALID_INPUT', 'iv': None, 'greeks': None}
    s, k, t, r, q = underlying, strike, years, rate, carry
    sd, kd = s*math.exp(-q*t), k*math.exp(-r*t)
    low_bound, high_bound = (max(0., sd-kd), sd) if right == 'call' else (max(0., kd-sd), kd)
    if not low_bound < price < high_bound:
        return {**details, 'status': 'NO_ARBITRAGE_OR_BOUNDARY', 'iv': None, 'greeks': None}
    cdf = lambda x: .5*(1+math.erf(x/math.sqrt(2)))
    def calc(v):
        d1 = (math.log(s/k)+(r-q+.5*v*v)*t)/(v*math.sqrt(t))
        d2 = d1-v*math.sqrt(t)
        return (sd*cdf(d1)-kd*cdf(d2) if right == 'call' else kd*cdf(-d2)-sd*cdf(-d1)), d1, d2
    lo, hi = 1e-8, 5.
    if not calc(lo)[0] <= price <= calc(hi)[0]:
        return {**details, 'status': 'OUTSIDE_SOLVER_BRACKET', 'iv': None, 'greeks': None}
    for iteration in range(100):
        v = (lo+hi)/2
        estimated, d1, d2 = calc(v)
        if abs(estimated-price) < 1e-8:
            break
        if estimated < price:
            lo = v
        else:
            hi = v
    else:
        return {**details, 'status': 'NONCONVERGENCE', 'iv': None, 'greeks': None}
    pdf = math.exp(-.5*d1*d1)/math.sqrt(2*math.pi)
    sign = 1 if right == 'call' else -1
    delta = math.exp(-q*t)*(cdf(d1) if sign == 1 else cdf(d1)-1)
    theta = -sd*pdf*v/(2*math.sqrt(t))-sign*r*kd*cdf(sign*d2)+sign*q*sd*cdf(sign*d1)
    return {**details, 'status': 'CONVERGED', 'iterations': iteration+1, 'iv': v, 'price': estimated,
            'greeks': {'delta': delta, 'gamma': math.exp(-q*t)*pdf/(s*v*math.sqrt(t)),
                       'theta': theta/365, 'vega': sd*pdf*math.sqrt(t), 'rho': sign*kd*t*cdf(sign*d2)}}


def event_study(bars, calendar, event_at, *, before=5, after=5, classification='SYNTHETIC_TEST'):
    if not 0 <= before <= 60 or not 1 <= after <= 60:
        raise ValueError('EVENT_WINDOW_BOUND')
    ordered = sorted(bars, key=lambda b: b.session_date)
    index = next((i for i, b in enumerate(ordered) if calendar.session(b.session_date).open_at >= event_at), None)
    if index is None or index-before < 1 or index+after >= len(ordered):
        return {'status': 'INSUFFICIENT_SESSION_WINDOW', 'causality': 'NOT_ESTABLISHED'}
    window = ordered[index-before-1:index+after+1]
    expected = calendar.expected_dates(window[0].session_date, window[-1].session_date)
    if [b.session_date for b in window] != expected:
        return {'status': 'MISSING_CALENDAR_SESSIONS', 'causality': 'NOT_ESTABLISHED'}
    anchor = float(ordered[index-1].close)
    prices = np.array([float(b.close) for b in window])
    returns = prices[1:]/prices[:-1]-1
    volumes = [float(b.volume) for b in window if b.volume is not None]
    pre = [float(b.volume) for b in ordered[index-before:index] if b.volume is not None]
    post = [float(b.volume) for b in ordered[index:index+after+1] if b.volume is not None]
    dd = prices/np.maximum.accumulate(prices)-1
    return {'schema_version': 'event_study_v1', 'status': 'AVAILABLE', 'classification': classification,
            'event_at': event_at.isoformat(), 'anchor_policy': 'first_session_open_at_or_after_event; base_prior_close',
            'calendar_id': calendar.calendar_id, 'calendar_version': calendar.version, 'window': [-before, after],
            'pre_return': anchor/float(ordered[index-before-1].close)-1 if before else None,
            'post_return': float(ordered[index+after].close)/anchor-1,
            'pre_daily_volatility': float(np.std(returns[:before], ddof=1)) if before > 1 else None,
            'post_daily_volatility': float(np.std(returns[before:], ddof=1)),
            'volume_response_ratio': float(np.mean(post)/np.mean(pre)) if pre and post and np.mean(pre) > 0 and len(pre) == before and len(post) == after+1 else None,
            'window_max_drawdown': float(np.min(dd)), 'sample_N': 1, 'causality': 'NOT_ESTABLISHED',
            'fact_classification': 'CALCULATION', 'source_observation_ids': [str(b.envelope.observation_id) for b in window]}
