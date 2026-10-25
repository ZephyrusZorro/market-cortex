"""Read-only independent archive benchmark; never fetches provider data or opens a DB."""
from __future__ import annotations

if not __package__:
    raise SystemExit('Use python -m scripts.benchmark_market_reads')

import argparse
import cProfile
import json
import pstats
import statistics
import time
from datetime import datetime, timezone
from pathlib import Path

from fastapi.testclient import TestClient
from market_cortex.market_archive import MarketArchive, digest, stamp
from market_cortex.market_data_app import create_market_app


def run(root, repetitions=5):
    archive = MarketArchive(Path(root))
    now = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    from datetime import timedelta
    queries = {
        'catalog_btc': ('catalog', {'provider': 'binance', 'query': 'BTCUSDT', 'status': 'TRADING'}),
        'btc_daily': ('history', {'provider':'binance','native_id':'BTCUSDT','interval':'1d',
                                'start':(now-timedelta(days=30)).isoformat(),'end':now.isoformat()}),
        'btc_minute': ('history', {'provider':'binance','native_id':'BTCUSDT','interval':'1m',
                                 'start':(now-timedelta(days=1)).isoformat(),'end':now.isoformat()}),
        'eth_daily': ('history', {'provider':'binance','native_id':'ETHUSDT','interval':'1d',
                                'start':(now-timedelta(days=30)).isoformat(),'end':now.isoformat()}),
    }
    result = {'observed_at':stamp(),'mode':'READ_ONLY_IN_PROCESS_HTTP','database_access':False,
              'provider_requests':0,'owner_writes':False,'repetitions':repetitions,'queries':{}}
    profile = cProfile.Profile()
    with TestClient(create_market_app(archive)) as client:
        for name,(route,params) in queries.items():
            elapsed=[];cpu=[];fingerprints=[]
            for _ in range(repetitions):
                started=time.perf_counter();processor=time.process_time()
                response=client.get('/api/v1/market-data/'+route,params=params)
                elapsed.append(round((time.perf_counter()-started)*1000,2))
                cpu.append(round((time.process_time()-processor)*1000,2))
                response.raise_for_status(); payload=response.json()
                fingerprints.append(digest(payload))
            result['queries'][name]={'elapsed_ms':elapsed,'median_ms':statistics.median(elapsed),
                                    'cpu_ms':cpu,'rows':len(payload['items']),
                                    'response_hash':fingerprints[0],'stable_responses':len(set(fingerprints))==1}
        # Profile the actual synchronous endpoint implementation in this thread.
        endpoint=next(route.endpoint for route in client.app.routes if getattr(route,'path',None)=='/api/v1/market-data/history')
        params=queries['btc_minute'][1]
        profile.enable()
        endpoint(provider='binance',native_id='BTCUSDT',interval='1m',
                 start=datetime.fromisoformat(params['start']),end=datetime.fromisoformat(params['end']),
                 as_of=None,offset=0,limit=2000)
        profile.disable()
    stats=pstats.Stats(profile)
    functions=sorted(stats.stats.items(),key=lambda item:item[1][3],reverse=True)[:15]
    result['profile']=[{'function':f'{Path(key[0]).name}:{key[1]}:{key[2]}','calls':value[1],
                        'self_ms':round(value[2]*1000,2),'cumulative_ms':round(value[3]*1000,2)} for key,value in functions]
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',required=True);parser.add_argument('--output',required=True)
    args=parser.parse_args();result=run(args.root)
    with Path(args.output).open('x',encoding='utf-8') as stream:json.dump(result,stream,indent=2)
    print(json.dumps(result,indent=2))


if __name__=='__main__':main()
