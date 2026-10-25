"""Read-only loopback response timings; no source fetch or database connection."""
from __future__ import annotations

if not __package__:
    raise SystemExit('Use python -m scripts.benchmark_market_http')

import argparse
import json
import statistics
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port',type=int,required=True,choices=(8677,3017,3018))
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    prefix='/api/v1/market-data/' if args.port==8677 else '/api/market-data/'
    day=datetime.now(timezone.utc).replace(hour=0,minute=0,second=0,microsecond=0)
    requests={
        'catalog':('catalog',{'provider':'binance','query':'BTCUSDT','status':'TRADING'}),
        'btc_daily':('history',{'provider':'binance','native_id':'BTCUSDT','interval':'1d',
                              'start':(day-timedelta(days=30)).isoformat(),'end':day.isoformat()}),
        'prices':('prices',{'provider':'binance','native_id':'BTCUSDT'}),
    }
    result={'observed_at':datetime.now(timezone.utc).isoformat(),'port':args.port,
            'measurement':'FULL_LOOPBACK_HTTP_RESPONSE','queries':{},'owner_writes':False,'provider_calls':0}
    with httpx.Client(base_url=f'http://127.0.0.1:{args.port}',timeout=15) as client:
        for name,(route,params) in requests.items():
            elapsed=[]
            for _ in range(5):
                start=time.perf_counter();response=client.get(prefix+route,params=params)
                elapsed.append(round((time.perf_counter()-start)*1000,2));response.raise_for_status()
            result['queries'][name]={'elapsed_ms':elapsed,'median_ms':statistics.median(elapsed),
                                    'response_bytes':len(response.content),'rows':len(response.json().get('items',[]))}
        if args.port!=8677:
            elapsed=[]
            for _ in range(5):
                start=time.perf_counter();response=client.get('/markets');response.raise_for_status()
                elapsed.append(round((time.perf_counter()-start)*1000,2))
            result['page_document']={'elapsed_ms':elapsed,'median_ms':statistics.median(elapsed),
                                     'response_bytes':len(response.content),'is_browser_render_measurement':False}
    with args.output.open('x',encoding='utf-8') as stream:json.dump(result,stream,indent=2)
    print(json.dumps(result,indent=2))


if __name__=='__main__':main()
