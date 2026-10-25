"""Offline integration and latency checks over actual copied source evidence.

Use python -m scripts.verify_three_market_bundle. No sockets or databases start;
all provider GETs are rejected during these in-process API checks.
"""
import argparse
import json
from pathlib import Path
from statistics import median
from time import perf_counter
from unittest.mock import patch

from fastapi.testclient import TestClient

from market_cortex.market_archive import MarketArchive, digest, stamp
from market_cortex.market_data_app import create_market_app
from market_cortex.market_universe import search_catalog


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args(argv)
    archive=MarketArchive(args.root)
    before=archive.integrity()
    cases=[('binance','BTCUSDT'),('binance','ETHUSDT'),('upstox','NSE_EQ|INE002A01018'),
           ('upstox','BSE_EQ|INE002A01018'),('upstox','NSE_EQ|INE009A01021'),
           ('upstox','BSE_EQ|INE009A01021'),('alpaca','AAPL'),('alpaca','SPY'),('alpaca','QQQ')]
    catalogs={}
    for provider in ('binance','upstox','alpaca'):
        manifest,rows=archive.latest('catalog',provider)
        indexed=search_catalog(archive,provider=provider,limit=1)
        assert indexed['total']==sum(bool(r['present']) for r in rows)
        catalogs[provider]={'rows':indexed['total'],'snapshot':manifest['manifest_hash'],
                           'catalog_bytes':archive.artifact_path(manifest).stat().st_size}
    checks=[]
    with patch('market_cortex.providers.ReadTransport.get',side_effect=AssertionError('NO_PROVIDER_NETWORK_PERMITTED')):
        with TestClient(create_market_app(archive)) as client:
            health=client.get('/api/v1/market-data/health').json()
            assert not health['owner_connected'] and not health['database_access']
            assert all(health['snapshots'].values())
            for provider,query in cases:
                times=[]
                for _ in range(5):
                    started=perf_counter()
                    response=client.get('/api/v1/market-data/catalog',params={'provider':provider,'query':query,'limit':200})
                    times.append((perf_counter()-started)*1000)
                    assert response.status_code==200
                data=response.json()
                matching=[r for r in data['items'] if (r['native_id']==query if provider=='upstox' else r['symbol']==query)]
                assert len(matching)==1
                instrument=matching[0]
                history_times=[]
                for _ in range(5):
                    started=perf_counter()
                    response=client.get('/api/v1/market-data/history',params={'provider':provider,
                        'native_id':instrument['native_id'],'interval':'1d',
                        'start':'2026-09-29T00:00:00Z','end':'2026-10-15T00:00:00Z'})
                    history_times.append((perf_counter()-started)*1000)
                    assert response.status_code==200
                history=response.json()
                expected=8 if query=='NSE_EQ|INE002A01018' else 9 if query=='AAPL' else None
                if expected is not None:assert len(history['items'])==expected
                if not history['items']:assert history['state']=='UNAVAILABLE'
                archived=[r for m in archive.manifests('candles',provider) for r in archive.rows(m)
                          if r['native_id']==instrument['native_id'] and r['interval']=='P1D' and
                          '2026-09-29'<=r['start_at']<'2026-10-15']
                # Binance can contain legitimate revisions; broker samples have one vintage.
                if provider!='binance':
                    assert digest(sorted(history['items'],key=lambda r:r['start_at']))==digest(sorted(archived,key=lambda r:r['start_at']))
                checks.append({'provider':provider,'symbol':instrument['symbol'],'native_id':instrument['native_id'],
                    'exchange':instrument['exchange'],'status':instrument['status'],
                    'search_matches':data['total'],'search_median_ms':median(times),
                    'history_median_ms':median(history_times),'history_rows':len(history['items']),
                    'history_state':history['state'],'history_payload_hash':digest(history['items'])})
    after=archive.integrity()
    assert before==after
    result={'status':'THREE_MARKET_OFFLINE_API_VALIDATED','observed_at':stamp(),'catalogs':catalogs,
        'total_discoverable_records':sum(c['rows'] for c in catalogs.values()),'checks':checks,'integrity':after,
        'provider_calls':0,'database_access':False,'owner_writes':False,'archive_unchanged':True,
        'browser_acceptance':'NOT_PERFORMED_FOR_BROKERS','currently_live_subscriptions':0,
        'timing_context':'TestClient in-process API, real immutable evidence, five samples per case; not production HTTP'}
    with args.output.open('x',encoding='utf-8') as stream:json.dump(result,stream,indent=2)
    print(json.dumps({'status':result['status'],'report':str(args.output.resolve()),'owner_writes':False}))
    return 0


if __name__=='__main__':
    raise SystemExit(main())
