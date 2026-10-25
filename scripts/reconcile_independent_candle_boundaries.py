"""Review only independent Binance bars captured within ten seconds of close.

Corrections require the explicit flag; original artifacts/as-of evidence remain.
Never connects to owner/pilot databases or applies migrations.
"""
from __future__ import annotations

if not __package__:
    raise SystemExit('Use python -m scripts.reconcile_independent_candle_boundaries')

import argparse
import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from market_cortex.market_archive import MarketArchive, stamp, digest
from market_cortex.market_history import BINANCE_FINALIZATION_GRACE, HistoryService, INTERVALS, cached_candles, candle_key


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--apply-independent-corrections',action='store_true')
    args=parser.parse_args();archive=MarketArchive(args.root);heads={}
    cutoff=datetime.now(timezone.utc)
    for manifest in archive.manifests('candles','binance'):
        for row in archive.rows(manifest):heads[candle_key(row)]=row
    risky=defaultdict(list)
    for row in heads.values():
        closed=datetime.fromisoformat(row['end_at'])
        if datetime.fromisoformat(row['available_at']) < closed+BINANCE_FINALIZATION_GRACE <= cutoff:
            risky[(row['native_id'],row['interval'])].append(row)
    if len(risky)>20:raise ValueError('RECONCILIATION_SYMBOL_BUDGET')
    _,catalog=archive.latest('catalog','binance');identities={row['native_id']:row for row in catalog}
    reports=[];calls=0
    for (native,iso),rows in sorted(risky.items()):
        interval=next(key for key,value in INTERVALS.items() if value[0]==iso)
        start=min(datetime.fromisoformat(r['start_at']) for r in rows)
        end=max(datetime.fromisoformat(r['end_at']) for r in rows)
        old=cached_candles(archive,'binance',native,interval,start,end,as_of=cutoff)
        report={'native_id':native,'interval':interval,'candidate_rows':len(rows),'start':start.isoformat(),'end':end.isoformat(),
                'before_as_of':cutoff.isoformat(),'before_hash':digest(old)}
        if args.apply_independent_corrections:
            result=HistoryService(archive,max_pages=min(20,20-calls)).fetch(identities[native],interval,start,end)
            calls+=result['provider_calls']
            preserved=cached_candles(archive,'binance',native,interval,start,end,as_of=cutoff)
            repeat=HistoryService(archive).fetch(identities[native],interval,start,end)
            if digest(old)!=digest(preserved) or repeat['provider_calls']!=0:
                raise ValueError('ASOF_OR_IDEMPOTENCE_FAILED')
            report.update(provider_calls=result['provider_calls'],new_revisions=result['new_revisions'],
                          after_hash=digest(result['items']),old_asof_preserved=True,repeat_provider_calls=0)
        reports.append(report)
    result={'observed_at':stamp(),'status':'RECONCILED_INDEPENDENT_SOURCE_REVISIONS' if args.apply_independent_corrections else 'READ_ONLY_CANDIDATES',
            'items':reports,'provider_calls':calls,'integrity':archive.integrity(),'owner_writes':False,'database_access':False}
    with args.output.open('x',encoding='utf-8') as stream:json.dump(result,stream,indent=2)
    print(json.dumps(result,indent=2))


if __name__=='__main__':main()
