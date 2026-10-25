"""Public live validation in an independent archive. No owner/pilot DB connection."""
from __future__ import annotations

if not __package__:
    raise SystemExit('Use python -m scripts.validate_market_foundation from the repository root')

import argparse
import asyncio
import ctypes
from ctypes import wintypes
import json
import time
from collections import Counter
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

from market_cortex.market_archive import MarketArchive, stamp
from market_cortex.market_data_cli import collect, select
from market_cortex.market_history import HistoryService, cached_candles
from market_cortex.market_universe import PacedTransport, search_catalog
from market_cortex.provider_readiness import probe


def windows_memory():
    class Counters(ctypes.Structure):
        _fields_=[('cb',ctypes.c_ulong),('faults',ctypes.c_ulong),*[(name,ctypes.c_size_t) for name in
            ('peak_working_set','working_set','peak_paged','paged','peak_nonpaged','nonpaged','pagefile','peak_pagefile')]]
    counters=Counters();counters.cb=ctypes.sizeof(counters)
    current=ctypes.windll.kernel32.GetCurrentProcess
    current.restype=wintypes.HANDLE
    measure=ctypes.windll.psapi.GetProcessMemoryInfo
    measure.argtypes=[wintypes.HANDLE,ctypes.POINTER(Counters),wintypes.DWORD]
    measure.restype=wintypes.BOOL
    if not measure(current(),ctypes.byref(counters),counters.cb) or not counters.working_set:
        raise RuntimeError('WINDOWS_MEMORY_MEASUREMENT_UNAVAILABLE')
    return {'working_set_bytes':counters.working_set,'peak_working_set_bytes':counters.peak_working_set}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    archive=MarketArchive(args.root)
    report={'observed_at':stamp(),'classification':'LIVE_PUBLIC_SOURCE_VALIDATION','owner_writes':False,
            'database_access':False,'archive':str(archive.root),'checks':{}}
    checks=report['checks']
    queries=[]
    for provider,query in [('binance','ADAUSDT'),('binance','DOTUSDT'),('upstox','RELIANCE'),('upstox','INFY')]:
        started=time.perf_counter()
        found=search_catalog(archive,provider=provider,query=query,limit=20)
        queries.append({'provider':provider,'query':query,'total_matches':found['total'],
            'milliseconds':round((time.perf_counter()-started)*1000,2),'snapshot':found['snapshots']})
        assert found['total']>0
    checks['outside_five_discovery']=queries
    checks['catalogs']={}
    for provider in ('binance','upstox'):
        manifest,rows=archive.latest('catalog',provider)
        checks['catalogs'][provider]={'identities':len(rows),'status_counts':dict(Counter(r['status'] for r in rows)),
            'exchange_counts':dict(Counter(r['exchange'] for r in rows)),'manifest_hash':manifest['manifest_hash'],
            'sources':manifest['sources'],'not_a_live_coverage_claim':True}
    items=select(archive,'binance',['ADAUSDT','DOTUSDT'])
    now=datetime.now(timezone.utc)
    end=now.replace(hour=0,minute=0,second=0,microsecond=0);start=end-timedelta(days=30)
    transport=PacedTransport();service=HistoryService(archive,transport)
    comparisons=[]
    for item in items:
        cached=service.fetch(item,'1d',start,end)
        assert cached['cache_hit'] and cached['provider_calls']==0 and len(cached['items'])==30
        direct=transport.get('data-api.binance.vision','/api/v3/klines',params={'symbol':item['symbol'],'interval':'1d',
            'timeZone':'0','startTime':int(start.timestamp()*1000),'endTime':int(end.timestamp()*1000)-1,'limit':1000})
        source={r[0]:r for r in direct.data}
        matches=all([Decimal(r[k]) for k in ('open','high','low','close','volume')]==
            [Decimal(str(v)) for v in source[int(datetime.fromisoformat(r['start_at']).timestamp()*1000)][1:6]] for r in cached['items'])
        assert matches
        observed=min(datetime.fromisoformat(r['available_at']) for r in cached['items'])
        assert not cached_candles(archive,'binance',item['native_id'],'1d',start,end,as_of=observed-timedelta(microseconds=1))
        assert len(cached_candles(archive,'binance',item['native_id'],'1d',start,end,as_of=now))==30
        comparisons.append({'symbol':item['symbol'],'closed_rows':30,'exact_ohlcv_match':matches,
            'comparison_response_hash':direct.content_hash,'repeat_provider_calls':cached['provider_calls'],
            'as_of_before_arrival_empty':True,'as_of_after_arrival_rows':30})
    checks['historical_value_comparison']=comparisons
    minute=service.fetch(items[0],'1m',now-timedelta(minutes=60),now)
    checks['minute_history']={k:v for k,v in minute.items() if k!='items'}
    checks['minute_history']['rows']=len(minute['items'])
    assert minute['items']
    stream=asyncio.run(collect(archive,'binance',[items[0]],'1m',20))
    checks['real_stream_restart_and_bar_recovery']=stream
    assert stream['stats']['ever_connected'] and stream['stats']['events']>0
    assert stream['recovery_before']['tick_recovery']=='UNAVAILABLE'
    checks['tick_gaps']=len(archive.manifests('gaps','binance'))
    assert checks['tick_gaps']>0
    checks['integrity']=archive.integrity()
    checks['credentialed_provider_status']={p:probe(p)['status'] for p in ('upstox','alpaca')}
    checks['resource_measurement']=windows_memory()
    report['status']='VALIDATED_PUBLIC_DISCOVERY_HISTORY_STREAM_RESTART'
    with args.output.open('x',encoding='utf-8') as stream:
        json.dump(report,stream,indent=2)
    print(json.dumps({'status':report['status'],'report':str(args.output.resolve()),'owner_writes':False}))


if __name__=='__main__':
    main()
