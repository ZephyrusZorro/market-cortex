"""Compare rendered Binance OHLCV readouts against fresh public raw responses."""
from __future__ import annotations

if not __package__:
    raise SystemExit('Use python -m scripts.verify_browser_market_values from the repository root')

import argparse
import hashlib
import json
import re
from datetime import datetime
from decimal import Decimal
from pathlib import Path

from market_cortex.market_archive import stamp
from market_cortex.market_universe import PacedTransport


def compare(transport,symbol,interval,text):
    prices=re.search(r'Open ([\d.]+) · high ([\d.]+) · low ([\d.]+) · close ([\d.]+)',text)
    volume=re.search(r'Volume ([\d.]+) (BTC|ETH) · candle start (\S+) · close boundary (\S+)',text)
    if not prices or not volume:
        raise ValueError('RENDERED_SOURCE_VALUES_MISSING')
    start=datetime.fromisoformat(volume[3].replace('Z','+00:00'))
    end=datetime.fromisoformat(volume[4].replace('Z','+00:00'))
    expected=[Decimal(v) for v in (*prices.groups(),volume[1])]
    page=transport.get('data-api.binance.vision','/api/v3/klines',params={'symbol':symbol,
        'interval':interval,'timeZone':'0','startTime':int(start.timestamp()*1000),
        'endTime':int(end.timestamp()*1000)-1,'limit':1})
    if not isinstance(page.data,list) or len(page.data)!=1:
        raise ValueError('PROVIDER_COMPARISON_UNAVAILABLE')
    row=page.data[0]
    actual=[Decimal(str(v)) for v in row[1:6]]
    timestamps_match=int(row[0])==int(start.timestamp()*1000) and int(row[6])+1==int(end.timestamp()*1000)
    units_match=volume[2]==symbol.removesuffix('USDT')
    return {'symbol':symbol,'interval':interval,'start_at':start.isoformat(),'end_at':end.isoformat(),
        'exact_ohlcv_match':expected==actual,'timestamps_match':timestamps_match,'volume_units_match':units_match,
        'provider_ohlcv':[str(v) for v in actual],'comparison_response_hash':page.content_hash,'provider_calls':1}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--browser-receipt',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    raw=args.browser_receipt.read_bytes();browser=json.loads(raw)
    transport=PacedTransport()
    samples=[compare(transport,browser['timeframe_symbol'],item['frame'],item['ohlcv']) for item in browser['timeframes']]
    samples.extend([compare(transport,'BTCUSDT','1d',browser['btc_daily']),
        compare(transport,'ETHUSDT','1d',browser['eth_daily_final'])])
    if 'eth_minute' in browser:
        samples.append(compare(transport,'ETHUSDT','1m',browser['eth_minute']))
    verified=all(item['exact_ohlcv_match'] and item['timestamps_match'] and item['volume_units_match'] for item in samples)
    result={'observed_at':stamp(),'status':'VERIFIED_RENDERED_VALUES_AGAINST_PUBLIC_PROVIDER' if verified else 'COMPARISON_FAILED',
        'browser_receipt_sha256':hashlib.sha256(raw).hexdigest(),'samples':samples,
        'database_access':False,'owner_writes':False,'provider_calls':len(samples)}
    with args.output.open('x',encoding='utf-8') as stream:
        json.dump(result,stream,indent=2)
    print(json.dumps({'status':result['status'],'samples':len(samples),'report':str(args.output.resolve()),'owner_writes':False}))
    return 0 if verified else 1


if __name__=='__main__':
    raise SystemExit(main())
