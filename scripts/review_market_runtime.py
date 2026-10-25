"""Read-only source inventory and optional raw Binance OHLCV comparison.

No owner/pilot database connection, ingestion, stream startup or schema operation.
"""
from __future__ import annotations

if not __package__:
    raise SystemExit('Use python -m scripts.review_market_runtime from the repository root')

import argparse
import json
import socket
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

from market_cortex.market_archive import MarketArchive, stamp
from market_cortex.market_history import candle_key
from market_cortex.market_stream import collector_state
from market_cortex.market_universe import PacedTransport, search_catalog
from market_cortex.providers import ProviderFailure


def inventory(archive):
    now=datetime.now(timezone.utc)
    result={'observed_at':stamp(),'database_access':False,'owner_writes':False,'catalogs':{},
            'history':[],'collectors':{},'loopback_ports':{}}
    for provider in ('binance','upstox','alpaca'):
        manifest,rows=archive.latest('catalog',provider)
        result['catalogs'][provider]={'identities':len(rows),'statuses':dict(Counter(r['status'] for r in rows)),
            'exchanges':dict(Counter(r['exchange'] for r in rows)),
            'current_present_identities':sum(r['present'] for r in rows),
            'current_present_exchanges':dict(Counter(r['exchange'] for r in rows if r['present'])),
            'current_present_statuses':dict(Counter(r['status'] for r in rows if r['present'])),
            'snapshot_observed_at':manifest['observed_at'] if manifest else None,
            'manifest_hash':manifest['manifest_hash'] if manifest else None,
            'authentication':'PUBLIC_METADATA' if provider!='alpaca' else 'DEFERRED_NOT_CONFIGURED'}
        current=collector_state(archive,provider)
        fresh=bool(current and (now-datetime.fromisoformat(current['updated_at'])).total_seconds()<30)
        connected=bool(current and fresh and current['stats']['connected'])
        result['collectors'][provider]={'connected_now':connected,
            'active_observed_instruments':len({r['native_id'] for r in current['items']}) if connected else 0,
            'last_checkpoint_at':current['updated_at'] if current else None,
            'last_capture_stats':current['stats'] if current else None}
    heads={};revisions=Counter()
    for manifest in archive.manifests('candles'):
        for row in archive.rows(manifest):
            key=(row['provider'],*candle_key(row))
            heads[key]=row
            revisions[(row['provider'],row['native_id'],row['interval'])]+=1
    grouped=defaultdict(list)
    for row in heads.values():
        grouped[(row['provider'],row['native_id'],row['interval'])].append(row)
    for key,rows in sorted(grouped.items()):
        rows.sort(key=lambda r:r['start_at'])
        result['history'].append({'provider':key[0],'native_id':key[1],'interval':key[2],
            'logical_closed_rows':len(rows),'stored_revisions':revisions[key],
            'first_start_at':rows[0]['start_at'],'last_end_at':rows[-1]['end_at'],
            'latest_received_at':max(r['available_at'] for r in rows),
            'source_response_hashes':len({r['source_hash'] for r in rows})})
    result['instruments_with_history']=dict(Counter(k[0] for k in {(r['provider'],r['native_id']) for r in heads.values()}))
    result['integrity']=archive.integrity()
    for port in (3017,8677,3000,8765,3002,8001):
        try:
            with socket.create_connection(('127.0.0.1',port),timeout=1):
                result['loopback_ports'][str(port)]='LISTENING'
        except OSError:
            result['loopback_ports'][str(port)]='OFFLINE'
    timings=[]
    for _ in range(3):
        started=time.perf_counter()
        found=search_catalog(archive,provider='binance',query='BTCUSDT',status='TRADING',limit=10)
        timings.append(round((time.perf_counter()-started)*1000,2))
    result['indexed_binance_search']={'milliseconds':timings,'matches':found['total']}
    return result,heads


def compare_binance(heads, symbols=('BTCUSDT','ETHUSDT')):
    transport=PacedTransport();results=[]
    for symbol in symbols:
        rows=sorted((r for r in heads.values() if r['provider']=='binance' and r['native_id']==symbol and r['interval']=='P1D'),key=lambda r:r['start_at'])
        if not rows:
            results.append({'symbol':symbol,'status':'UNAVAILABLE','compared_rows':0})
            continue
        if len(rows)>1000:
            raise ProviderFailure('REVIEW_COMPARISON_ROW_BUDGET')
        start=datetime.fromisoformat(rows[0]['start_at']);end=datetime.fromisoformat(rows[-1]['end_at'])
        page=transport.get('data-api.binance.vision','/api/v3/klines',params={'symbol':symbol,'interval':'1d',
            'timeZone':'0','startTime':int(start.timestamp()*1000),'endTime':int(end.timestamp()*1000)-1,'limit':1000})
        source={int(r[0]):r for r in page.data}
        changed=[];missing=[]
        for row in rows:
            key=int(datetime.fromisoformat(row['start_at']).timestamp()*1000)
            if key not in source:
                missing.append(row['start_at'])
            elif tuple(Decimal(str(row[k])) for k in ('open','high','low','close','volume')) != tuple(Decimal(str(v)) for v in source[key][1:6]):
                changed.append(row['start_at'])
        results.append({'symbol':symbol,'status':'EXACT_OHLCV_MATCH' if not missing and not changed else 'MISMATCH',
            'compared_rows':len(rows)-len(missing),'missing_timestamps':missing,'changed_timestamps':changed,
            'provider_calls':1,'comparison_response_hash':page.content_hash})
    return results


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--compare-binance',action='store_true')
    args=parser.parse_args()
    result,heads=inventory(MarketArchive(args.root))
    if args.compare_binance:
        result['fresh_provider_daily_comparison']=compare_binance(heads)
    result['status']='INVENTORY_RECORDED'
    args.output.parent.mkdir(parents=True,exist_ok=True)
    with args.output.open('x',encoding='utf-8') as stream:
        json.dump(result,stream,indent=2)
    print(json.dumps({'status':result['status'],'report':str(args.output.resolve()),
        'instruments_with_history':result['instruments_with_history'],'active_stream_instruments':
        sum(r['active_observed_instruments'] for r in result['collectors'].values()),'database_access':False}))


if __name__=='__main__':
    main()
