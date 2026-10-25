"""Verify real independent API/proxy reads, as-of evidence and zero-fetch cache hits.

No owner/pilot connection, migration, research submission or market-data backfill.
The cache-hit POST is checked for zero provider calls and zero revisions.
"""
from __future__ import annotations

if not __package__:
    raise SystemExit('Use python -m scripts.verify_production_market_reads')

import argparse
import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx

from market_cortex.market_archive import MarketArchive, digest, stamp
from market_cortex.market_history import cached_candles


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();archive=MarketArchive(args.root)
    manifests=[m for m in archive.manifests('candles','binance') if
               m['metadata'].get('native_id')=='BTCUSDT' and m['metadata'].get('interval')=='1d']
    cutoff=datetime.fromisoformat(manifests[0]['observed_at'])
    end=datetime.now(timezone.utc).replace(hour=0,minute=0,second=0,microsecond=0)
    start=end-timedelta(days=30)
    result={'observed_at':stamp(),'status':'VERIFIED','samples':[],
            'database_access':False,'owner_writes':False,'pilot_writes':False}
    with httpx.Client(timeout=20) as client:
        for point in (cutoff-timedelta(microseconds=1),cutoff,None):
            expected=cached_candles(archive,'binance','BTCUSDT','1d',start,end,as_of=point)
            params={'provider':'binance','native_id':'BTCUSDT','interval':'1d','start':start.isoformat(),'end':end.isoformat()}
            if point:params['as_of']=point.isoformat()
            hashes=[]
            for base in ('http://127.0.0.1:8677/api/v1/market-data/', 'http://127.0.0.1:3018/api/market-data/'):
                response=client.get(base+'history',params=params);response.raise_for_status()
                payload=response.json();hashes.append(digest(payload['items']))
                if payload['items']!=expected or payload['total']!=len(expected):raise ValueError('ASOF_OR_PROXY_EVIDENCE_MISMATCH')
            result['samples'].append({'as_of':point.isoformat() if point else None,'rows':len(expected),
                                     'items_hash':hashes[0],'direct_proxy_and_archive_match':len(set(hashes))==1})
        body={'provider':'binance','native_id':'BTCUSDT','interval':'1d','start':start.isoformat(),'end':end.isoformat()}
        response=client.post('http://127.0.0.1:3018/api/market-data/history/fetch',json=body)
        response.raise_for_status();fetched=response.json()
        if fetched['provider_calls']!=0 or fetched['new_revisions']!=0 or not fetched['cache_hit']:
            raise ValueError('UNEXPECTED_PROVIDER_FETCH_OR_REVISION')
        result['cached_fetch']={key:fetched[key] for key in ('cache_hit','provider_calls','new_revisions','state')}
    sandbox=Path('runtime/multi-market-production-sandbox-path.txt').read_text(encoding='utf-8-sig').strip()
    result['production_build_id']=(Path(sandbox)/'.next/BUILD_ID').read_text().strip()
    result['build_source_matches']={}
    for relative in ('app/markets/page.tsx','lib/market-data.ts','components/charts.tsx','app/api/market-data/[...path]/route.ts'):
        local=Path('apps/workstation')/relative;built=Path(sandbox)/relative
        matches=hashlib.sha256(local.read_bytes()).digest()==hashlib.sha256(built.read_bytes()).digest()
        result['build_source_matches'][relative]=matches
        if not matches:raise ValueError('PRODUCTION_SOURCE_DIFFERS_FROM_VERIFIED_IMPLEMENTATION')
    with args.output.open('x',encoding='utf-8') as stream:json.dump(result,stream,indent=2)
    print(json.dumps(result,indent=2))


if __name__=='__main__':main()
