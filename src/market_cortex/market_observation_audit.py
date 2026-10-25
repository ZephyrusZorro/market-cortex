"""Offline source-evidence audit. No credentials, provider calls or database access."""
from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from statistics import median

from .market_archive import MarketArchive, digest, stamp
from .providers import ProviderFailure


def event_evidence(events, *, stale_seconds=30, clock_tolerance_seconds=5):
    """Measure freshness at arrival, separately from capture/connection status.

    A minute-bar timestamp is its window start, not network latency. An initial
    last-trade snapshot may be genuine but old, even on a healthy connection.
    """
    states = Counter()
    lags, fresh_prices, fresh_times, bids, asks = [], set(), set(), set(), set()
    price_events = []
    for row in events:
        if row['kind'] not in {'trade', 'quote', 'ticker', 'last_trade_snapshot'}:
            continue
        event = datetime.fromisoformat(row['event_at'])
        received = datetime.fromisoformat(row['received_at'])
        if event.tzinfo is None or received.tzinfo is None:
            raise ProviderFailure('AUDIT_AWARE_TIMESTAMPS_REQUIRED')
        lag = (received-event).total_seconds()
        delay = row.get('delay_seconds', 0)
        if delay < 0:
            raise ProviderFailure('INVALID_FEED_DELAY')
        state = ('CLOCK_SKEW' if lag < -clock_tolerance_seconds else
                 'STALE' if lag-delay > stale_seconds else 'DELAYED' if delay else 'FRESH')
        states[state] += 1
        lags.append(lag)
        price_events.append(row)
        if state == 'FRESH':
            fresh_times.add(event.isoformat())
            for field, target in [('price',fresh_prices),('bid',bids),('ask',asks)]:
                if row.get(field) is not None:
                    value = Decimal(str(row[field]))
                    if not value.is_finite() or value < 0:
                        raise ProviderFailure('INVALID_AUDIT_PRICE')
                    target.add(value)
    return {
        'observations_received':len(events), 'kinds':dict(Counter(r['kind'] for r in events)),
        'price_observations':len(price_events), 'arrival_states':dict(states),
        'price_event_age_at_arrival_seconds':{
            'min':min(lags), 'median':median(lags), 'max':max(lags)} if lags else None,
        'fresh_price_observations_received':states['FRESH'] > 0,
        'fresh_distinct_event_timestamps':len(fresh_times),
        'fresh_distinct_trade_prices':len(fresh_prices),
        'fresh_distinct_bids':len(bids), 'fresh_distinct_asks':len(asks),
        'fresh_price_range':[str(min(fresh_prices)),str(max(fresh_prices))] if fresh_prices else None,
        'fresh_price_changes_observed':len(fresh_times)>1 and
            any(len(values)>1 for values in (fresh_prices,bids,asks)),
        'freshness_threshold_seconds':stale_seconds,
        'current_connection_inferred':False,
        'bar_start_timestamps_excluded_from_price_latency':True,
    }


def audit_probe(report_path: Path):
    raw = report_path.read_bytes()
    report = json.loads(raw)
    provider = report['provider']
    if provider not in {'upstox','alpaca'} or report.get('database_access') is not False or report.get('owner_ingestion') is not False:
        raise ProviderFailure('INDEPENDENT_PROBE_RECEIPT_REQUIRED')
    archive = MarketArchive(report_path.with_suffix(''))
    integrity = archive.integrity()
    catalog, rows = archive.latest('catalog',provider)
    if not catalog or catalog['manifest_hash'] != report['catalog']['manifest_hash'] or len(rows)!=report['catalog']['records']:
        raise ProviderFailure('PROBE_CATALOG_RECEIPT_MISMATCH')
    if any(r['provider']!=provider for r in rows):
        raise ProviderFailure('PROBE_CATALOG_PROVIDER_MISMATCH')
    candles = []
    for manifest in archive.manifests('candles',provider):
        source_hashes = {s.get('sha256') for s in manifest['sources']}
        for row in archive.rows(manifest):
            if row['source_hash'] not in source_hashes:
                raise ProviderFailure('PROBE_HISTORY_SOURCE_LINEAGE_MISMATCH')
            candles.append(row)
    events = [r for m in archive.manifests('events',provider) for r in archive.rows(m)]
    stats = report['stream']['stats']
    if len(candles)!=report['history']['rows'] or len(events)!=stats['events']:
        raise ProviderFailure('PROBE_OBSERVATION_RECEIPT_MISMATCH')
    comparison = report['history_accuracy']
    if (comparison['status']!='EXACT_OHLCV_MATCH' or comparison['compared_rows']!=len(candles) or
            any(comparison.get(k) for k in ('missing_timestamps','unexpected_timestamps','changed_timestamps'))):
        raise ProviderFailure('PROBE_COMPARISON_NOT_EXACT')
    if any(r['provider']!=provider or r['feed']!=comparison['feed'] or
           r['adjustment_basis']!=comparison['adjustment_basis'] for r in candles):
        raise ProviderFailure('PROBE_HISTORY_IDENTITY_MISMATCH')
    native_ids = {r['native_id'] for r in candles}
    if len(native_ids)!=1 or any(r['provider']!=provider or r['native_id'] not in native_ids for r in events):
        raise ProviderFailure('PROBE_STREAM_IDENTITY_MISMATCH')
    if len({(r['native_id'],r['start_at']) for r in candles})!=len(candles):
        raise ProviderFailure('PROBE_DUPLICATE_HISTORY')
    for row in candles:
        values = [Decimal(str(row[k])) for k in ('open','high','low','close','volume')]
        o,h,l,c,v = values
        if any(not x.is_finite() or x<0 for x in values) or l>min(o,c) or h<max(o,c) or h<l:
            raise ProviderFailure('PROBE_INVALID_OHLCV')
    for row in events:
        if len(row['source_hash'])!=64 or any(c not in '0123456789abcdef' for c in row['source_hash']):
            raise ProviderFailure('PROBE_INVALID_EVENT_SOURCE_HASH')
    # Sources are hash-only. The fresh GET comparison was performed by the
    # credentialed probe; this audit cannot reconstruct an unretained raw body.
    history_sources = sorted({r['source_hash'] for r in candles})
    sizes = {}
    for kind in ('catalog','candles','events','requests'):
        manifests = archive.manifests(kind,provider)
        artifacts = {str(archive.artifact_path(m)):archive.artifact_path(m).stat().st_size for m in manifests}
        count = sum(m['rows'] for m in manifests)
        sizes[kind] = {'rows':count,'unique_parquet_bytes':sum(artifacts.values()),
                       'bytes_per_row':sum(artifacts.values())/count if count else None}
    return {
        'provider':provider, 'receipt_sha256':hashlib.sha256(raw).hexdigest(),
        'receipt_path':str(report_path.resolve()), 'archive_root':str(archive.root),
        'integrity':integrity, 'catalog':{'manifest_hash':catalog['manifest_hash'], 'records':len(rows),
            'by_status':dict(Counter(r['status'] for r in rows)),
            'by_exchange':dict(Counter(r['exchange'] for r in rows)),
            'by_exchange_and_status':dict(Counter(r['exchange']+':'+r['status'] for r in rows)),
            'active_tradable_metadata_records':sum(r['status']=='active' and bool(r['attributes'].get('tradable')) for r in rows)
                if provider=='alpaca' else None,
            'equity_etf_classification_verified':False,
            'history_coverage_established_by_catalog':False},
        'history':{'rows':len(candles),'native_ids':sorted(native_ids),
            'start_at':min(r['start_at'] for r in candles),'last_start_at':max(r['start_at'] for r in candles),
            'stored_rows_sha256':digest(sorted(candles,key=lambda r:r['start_at'])),
            'credentialed_comparison':comparison, 'original_response_hashes':history_sources,
            'comparison_response_equals_original_hash':comparison['source_response_hash'] in history_sources,
            'offline_raw_provider_comparison_reproduced':False, 'raw_response_retention':'HASH_ONLY'},
        'feed':{'authentication_confirmed':stats.get('authentication_confirmed',False),
            'subscription_confirmed':stats.get('subscription_confirmed',False),
            'connected_at_capture_end':stats.get('connected',False), 'last_error':stats.get('last_error'),
            'feed_entitlements_observed':sorted({r['feed'] for r in events}),
            **event_evidence(events)},
        'observed_rate_headers':report['read_only_sample'].get('rate_limit_headers',{}),
        'size_measurements':sizes,
        'gates':{'canonical_identity':'REQUIRES_VERIFICATION','exchange_calendar':'REQUIRES_VERIFICATION',
                 'corporate_actions':'REQUIRES_VERIFICATION','owner_deployment':'REQUIRES_APPROVAL'},
        'database_access':False, 'owner_writes':False, 'provider_calls':0,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report',type=Path,action='append',required=True)
    parser.add_argument('--output',type=Path,required=True)
    args = parser.parse_args(argv)
    result = {'observed_at':stamp(),'status':'OFFLINE_SOURCE_EVIDENCE_AUDITED',
              'probes':[audit_probe(p) for p in args.report], 'owner_writes':False,'database_access':False}
    with args.output.open('x',encoding='utf-8') as stream:
        json.dump(result,stream,indent=2)
    print(json.dumps({'status':result['status'],'report':str(args.output.resolve()),'owner_writes':False}))
    return 0


if __name__=='__main__':
    raise SystemExit(main())
