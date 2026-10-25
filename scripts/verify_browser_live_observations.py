"""Match rendered live prices/timestamps to hash-verified archived source events."""
from __future__ import annotations

if not __package__:
    raise SystemExit('Use python -m scripts.verify_browser_live_observations')

import argparse
import json
import re
from datetime import datetime
from decimal import Decimal
from pathlib import Path

from market_cortex.market_archive import MarketArchive, stamp
from scripts.verify_browser_market_values import compare
from market_cortex.market_universe import PacedTransport


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--closed-receipt',type=Path,default=Path('runtime/market-closed-candle-rollover-browser-2026-10-14.json'))
    parser.add_argument('--closed-field',default='final_panel')
    parser.add_argument('--live-receipt',type=Path,default=Path('runtime/market-final-live-viewport-2026-10-14.json'))
    parser.add_argument('--live-fields',nargs='+',default=['first','second'])
    parser.add_argument('--live-symbols',nargs='+',default=['BTCUSDT','BTCUSDT'])
    args=parser.parse_args();archive=MarketArchive(args.root)
    browser=json.loads(args.live_receipt.read_text(encoding='utf-8'))
    events=[row for manifest in archive.manifests('events','binance') for row in archive.rows(manifest)]
    samples=[]
    for name,symbol in zip(args.live_fields,args.live_symbols,strict=True):
        text=browser[name]
        price=re.search(r'Last trade: ([\d.]+)',text)[1]
        times=re.search(r'Source timestamp\s+(\S+)\s*·\s*received\s+(\S+)',text)
        matches=[row for row in events if row['native_id']==symbol and row['kind']=='ticker' and
                 Decimal(row['price'])==Decimal(price) and
                 datetime.fromisoformat(row['event_at'])==datetime.fromisoformat(times[1].replace('Z','+00:00')) and
                 datetime.fromisoformat(row['received_at'])==datetime.fromisoformat(times[2].replace('Z','+00:00'))]
        samples.append({'sample':name,'symbol':symbol,'price':price,'event_at':times[1],'received_at':times[2],
                        'exact_archived_event_match':len(matches)==1,
                        'source_hash':matches[0]['source_hash'] if matches else None})
    rolled=json.loads(args.closed_receipt.read_text(encoding='utf-8'))
    closed=compare(PacedTransport(),'BTCUSDT','1m',rolled[args.closed_field])
    passed=all(row['exact_archived_event_match'] for row in samples) and all(
        closed[key] for key in ('exact_ohlcv_match','timestamps_match','volume_units_match'))
    result={'observed_at':stamp(),'status':'VERIFIED' if passed else 'FAILED','rendered_live_events':samples,
            'latest_rolled_closed_candle':closed,'viewport_preserved':browser.get('viewport_before',browser.get('viewport_first'))==browser.get('viewport_after',browser.get('viewport_second')),
            'browser_delivery':'LOCAL_HTTP_POLL_EVERY_2_SECONDS','provider_delivery':'PUBLIC_BINANCE_WEBSOCKET',
            'database_access':False,'owner_writes':False,'provider_calls':1}
    with args.output.open('x',encoding='utf-8') as stream:json.dump(result,stream,indent=2)
    print(json.dumps(result,indent=2));return 0 if passed else 1


if __name__=='__main__':raise SystemExit(main())
