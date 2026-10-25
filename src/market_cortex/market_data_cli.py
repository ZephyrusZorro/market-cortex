"""Independent data tools. No database URL is read and no owner runtime is used."""
from __future__ import annotations

import argparse
import asyncio
import json
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .contracts import utc
from .market_archive import MarketArchive, stamp
from .market_history import HistoryService, INTERVALS
from .market_stream import FeedWorker, collector_state
from .market_universe import search_catalog, sync_catalog
from .providers import ProviderFailure


def select(archive, provider, symbols):
    _, rows = archive.latest('catalog', provider)
    found = []
    for symbol in symbols:
        matches = [r for r in rows if r['present'] and (r['native_id'] == symbol or r['symbol'] == symbol)]
        if len(matches) != 1:
            raise ProviderFailure('NO_UNIQUE_DISCOVERY_MATCH_USE_NATIVE_ID')
        found.append(matches[0])
    return found


def recovery(archive, provider, instruments, interval, *, max_days=3, max_calls=100, service=None):
    """Resume bars, retaining all unrecoverable tick gaps and truncation evidence."""
    now = datetime.now(timezone.utc)
    checkpoint = collector_state(archive,provider)
    if checkpoint is None:
        return {'status':'NO_PRIOR_CHECKPOINT', 'provider_calls':0, 'tick_recovery':'UNAVAILABLE'}
    prior = checkpoint.get('latest_received_at')
    if not prior:
        return {'status':'NO_PRIOR_OBSERVATIONS', 'provider_calls':0, 'tick_recovery':'UNAVAILABLE'}
    left = utc(datetime.fromisoformat(prior))
    bounded = max(left, now-timedelta(days=max_days))
    # Include the interrupted interval; a final candle must be recovered from REST.
    seconds = INTERVALS[interval][1]
    if not seconds:
        raise ProviderFailure('MONTHLY_AUTOMATIC_RECOVERY_REQUIRES_REVIEW')
    a = datetime.fromtimestamp(int(bounded.timestamp())//seconds*seconds, timezone.utc)
    results, used = [], 0
    service = service or HistoryService(archive)
    for item in instruments:
        if used >= max_calls:
            raise ProviderFailure('RECOVERY_CALL_BUDGET_EXHAUSTED')
        service.max_pages = min(20, max_calls-used)
        receipt = service.fetch(item, interval, a, now, refresh=True)
        used += receipt['provider_calls']
        results.append({'native_id':item['native_id'], 'revisions':receipt['new_revisions'],
                        'returned_rows':len(receipt['items']), 'provider_calls':receipt['provider_calls']})
    return {'status':'PROVIDER_AVAILABLE_BARS_RECOVERED', 'from':a.isoformat(), 'to':now.isoformat(),
            'truncated_before':a.isoformat() if a > left else None, 'provider_calls':used,
            'tick_recovery':'UNAVAILABLE', 'calendar_verified':provider=='binance', 'items':results}


async def collect(archive, provider, instruments, interval, seconds, *, reconnect_recovery=True, feed='iex',upstox_mode='ltpc',
                  mode='bounded_capture'):
    recovered = recovery(archive,provider,instruments,interval) if reconnect_recovery and feed=='iex' else {'status':'NOT_REQUESTED'}
    worker = FeedWorker(archive,provider,instruments,interval=interval,feed=feed,upstox_mode=upstox_mode,mode=mode)
    stats = await worker.run(seconds)
    # REST closes the candle gap after interruptions; source ticks remain missing.
    after = recovery(archive,provider,instruments,interval) if reconnect_recovery and stats['reconnections'] and feed=='iex' else None
    return {'status':'OBSERVATIONS_CAPTURED' if stats['events'] else 'NO_OBSERVATIONS', 'stats':stats,
            'recovery_before':recovered, 'recovery_after':after, 'owner_writes':False, 'database_access':False}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', required=True, type=Path)
    parser.add_argument('--output', type=Path)
    subs = parser.add_subparsers(dest='command', required=True)
    subs.add_parser('init')
    sync = subs.add_parser('sync')
    sync.add_argument('--provider',required=True,choices=['binance','upstox','alpaca'])
    query = subs.add_parser('search')
    query.add_argument('--provider',choices=['binance','upstox','alpaca'])
    query.add_argument('--query',default='')
    query.add_argument('--offset',type=int,default=0)
    query.add_argument('--limit',type=int,default=50)
    for name in ('history','stream','collect'):
        sub = subs.add_parser(name)
        sub.add_argument('--provider',required=True,choices=['binance','upstox','alpaca'])
        sub.add_argument('--symbols',nargs='+',required=True)
        sub.add_argument('--interval',choices=list(INTERVALS),default='1d' if name=='history' else '1m')
        if name=='history':
            sub.add_argument('--start',required=True)
            sub.add_argument('--end',required=True)
            sub.add_argument('--refresh',action='store_true')
        else:
            sub.add_argument('--seconds',type=int,default=30)
            sub.add_argument('--feed',choices=['iex','delayed_sip'],default='iex')
            sub.add_argument('--upstox-mode',choices=['ltpc','full'],default='ltpc')
            if name=='collect':
                sub.add_argument('--continuous-independent-test',action='store_true')
    serve = subs.add_parser('serve')
    serve.add_argument('--port',type=int,default=8677)
    subs.add_parser('integrity')
    args = parser.parse_args(argv)
    try:
        archive = MarketArchive(args.root, initialize=args.command=='init')
        if args.command=='init':
            report = {'status':'INITIALIZED_INDEPENDENT_ARCHIVE','root':str(archive.root),'database_access':False}
        elif args.command=='sync':
            manifest = sync_catalog(archive,args.provider)
            report = {'status':'CATALOG_CAPTURED','provider':args.provider,'rows':manifest['rows'],
                      'manifest':manifest['manifest_hash'],'metadata':manifest['metadata']}
        elif args.command=='search':
            report = search_catalog(archive,provider=args.provider,query=args.query,offset=args.offset,limit=args.limit)
        elif args.command in {'history','stream','collect'}:
            items = select(archive,args.provider,args.symbols)
            if args.command=='history':
                if len(items)>20:
                    raise ProviderFailure('BACKFILL_SYMBOL_BUDGET')
                results, used = [], 0
                for item in items:
                    service = HistoryService(archive,max_pages=min(20,100-used))
                    result = service.fetch(item,args.interval,datetime.fromisoformat(args.start.replace('Z','+00:00')),
                                           datetime.fromisoformat(args.end.replace('Z','+00:00')),refresh=args.refresh)
                    used += result['provider_calls']
                    results.append({**{k:v for k,v in result.items() if k!='items'},'native_id':item['native_id'],
                                    'rows':len(result['items'])})
                report = {'status':'BOUNDED_HISTORY_CAPTURED','items':results,'provider_calls':used}
            else:
                while True:
                    report = asyncio.run(collect(archive,args.provider,items,args.interval,args.seconds,
                        reconnect_recovery=args.command=='collect',feed=args.feed,upstox_mode=args.upstox_mode,
                        mode='continuous_independent_test' if args.command=='collect' and args.continuous_independent_test else 'bounded_capture'))
                    if args.command!='collect' or not args.continuous_independent_test or report['stats'].get('last_error'):
                        break
                    time.sleep(2)
        elif args.command=='serve':
            if args.port in {8765,8001,3000,3002,5432,55432} or not 1024<=args.port<=65535:
                raise ProviderFailure('PROTECTED_OR_INVALID_PORT')
            import uvicorn
            from .market_data_app import create_market_app
            uvicorn.run(create_market_app(archive),host='127.0.0.1',port=args.port,log_level='warning')
            return 0
        else:
            report = archive.integrity()
    except ProviderFailure as error:
        report = {'status':'DEFERRED_NOT_CONFIGURED' if error.code=='NOT_CONFIGURED' else 'FAILED', 'code':error.code,
                  'retryable':error.retryable, 'database_access':False, 'owner_writes':False}
    except Exception:
        report = {'status':'FAILED', 'code':'MARKET_DATA_INPUT_OR_OPERATION_FAILED', 'owner_writes':False,'database_access':False}
    if args.output:
        args.output.parent.mkdir(parents=True,exist_ok=True)
        with args.output.open('x',encoding='utf-8') as stream:
            json.dump(report,stream,indent=2)
    print(json.dumps(report,ensure_ascii=False))
    return 1 if report.get('status') in {'FAILED','DEFERRED_NOT_CONFIGURED','NO_OBSERVATIONS'} else 0


if __name__=='__main__':
    raise SystemExit(main())
