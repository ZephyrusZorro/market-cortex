"""Private credential acceptance in an independent archive, without DB access."""
from __future__ import annotations

import argparse
import asyncio
import json
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from urllib.parse import quote
from zoneinfo import ZoneInfo

from .market_archive import MarketArchive, stamp
from .market_data_cli import collect, select
from .market_history import HistoryService
from .market_universe import PacedTransport, headers, sync_catalog
from .market_observation_audit import event_evidence
from .provider_readiness import probe
from .providers import ProviderFailure


def feed_validation_code(stats):
    """Authentication alone cannot establish that the requested feed was subscribed."""
    if not stats.get('authentication_confirmed'):
        return 'STREAM_AUTH_NOT_CONFIRMED'
    if not stats.get('subscription_confirmed'):
        return 'STREAM_SUBSCRIPTION_NOT_CONFIRMED'
    if stats.get('last_error'):
        return 'STREAM_CAPTURE_ERROR_REQUIRES_REVIEW'
    return None


def verify_history_accuracy(instrument, observations, *, transport=None):
    """Compare stored daily OHLCV with a fresh, bounded raw provider response.

    Deliberately do not use the history normalizer for the comparison. These
    observations are native source evidence, not verified exchange sessions.
    This function performs provider GETs and no archive/database writes.
    """
    provider = instrument['provider']
    if provider not in {'upstox', 'alpaca'}:
        raise ProviderFailure('UNAPPROVED_ACCURACY_PROVIDER')
    if not observations:
        return {'status':'UNAVAILABLE', 'compared_rows':0, 'provider_calls':0}
    native = instrument['native_id']
    feed = 'historical_v3' if provider=='upstox' else 'iex'
    basis = 'provider_unspecified' if provider=='upstox' else 'raw'
    expected = {}
    for row in observations:
        if (row['provider']!=provider or row['native_id']!=native or row['interval']!='P1D' or
                row['feed']!=feed or row['adjustment_basis']!=basis):
            raise ProviderFailure('ACCURACY_SOURCE_IDENTITY_MISMATCH')
        at = datetime.fromisoformat(row['start_at'])
        values = tuple(Decimal(str(row[k])) for k in ('open','high','low','close','volume'))
        if at.tzinfo is None or any(not v.is_finite() or v<0 for v in values):
            raise ProviderFailure('INVALID_ACCURACY_REFERENCE')
        at = at.astimezone(timezone.utc)
        if at in expected:
            raise ProviderFailure('INVALID_ACCURACY_REFERENCE')
        expected[at] = values
    start = min(expected)
    end = max(datetime.fromisoformat(r['end_at']) for r in observations)
    if end-start>timedelta(days=31):
        raise ProviderFailure('ACCURACY_RANGE_BUDGET')
    auth = headers(provider)
    transport = transport or PacedTransport()
    if provider=='upstox':
        zone = ZoneInfo('Asia/Kolkata')
        first = start.astimezone(zone).date()
        last = (end-timedelta(microseconds=1)).astimezone(zone).date()
        page = transport.get('api.upstox.com',
            f'/v3/historical-candle/{quote(native,safe="")}/days/1/{last}/{first}', headers=auth)
        raw = page.data.get('data',{}).get('candles') if isinstance(page.data,dict) else None
    else:
        page = transport.get('data.alpaca.markets',f'/v2/stocks/{instrument["symbol"]}/bars',params={
            'start':start.isoformat(),'end':end.isoformat(),'timeframe':'1Day','feed':'iex',
            'adjustment':'raw','asof':'-','sort':'asc','limit':1000},headers=auth)
        raw = page.data.get('bars') if isinstance(page.data,dict) else None
        if isinstance(page.data,dict) and page.data.get('next_page_token'):
            raise ProviderFailure('ACCURACY_PAGE_BUDGET')
    if not isinstance(raw,list) or len(raw)>1000:
        raise ProviderFailure('INVALID_ACCURACY_RESPONSE')
    actual = {}
    try:
        for row in raw:
            timestamp = row[0] if provider=='upstox' else row['t']
            at = datetime.fromisoformat(timestamp.replace('Z','+00:00'))
            raw_values = row[1:6] if provider=='upstox' else [row[k] for k in ('o','h','l','c','v')]
            values = tuple(Decimal(str(v)) for v in raw_values)
            if at.tzinfo is None or len(values)!=5 or any(not v.is_finite() or v<0 for v in values):
                raise ValueError('invalid raw values')
            at = at.astimezone(timezone.utc)
            if start<=at<end:
                if at in actual and actual[at]!=values:
                    raise ValueError('conflicting raw rows')
                actual[at] = values
    except Exception:
        raise ProviderFailure('INVALID_ACCURACY_RESPONSE') from None
    missing = sorted(at.isoformat() for at in expected.keys()-actual.keys())
    unexpected = sorted(at.isoformat() for at in actual.keys()-expected.keys())
    changed = sorted(at.isoformat() for at in expected.keys()&actual.keys() if expected[at]!=actual[at])
    return {'status':'EXACT_OHLCV_MATCH' if not (missing or unexpected or changed) else 'MISMATCH',
        'compared_rows':len(expected.keys()&actual.keys()), 'provider_calls':1,
        'source_response_hash':page.content_hash, 'feed':feed,'adjustment_basis':basis,
        'missing_timestamps':missing,'unexpected_timestamps':unexpected,'changed_timestamps':changed,
        'calendar_authority_verified':False}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--provider',choices=['upstox','alpaca'],required=True)
    parser.add_argument('--root',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--seconds',type=int,default=30)
    parser.add_argument('--delayed-sip',action='store_true')
    args = parser.parse_args(argv)
    result = {'provider':args.provider,'observed_at':stamp(),'database_access':False,'owner_ingestion':False,
              'calendar_authority':'REQUIRES_VERIFICATION', 'corporate_action_identity':'REQUIRES_VERIFICATION',
              'rate_limit_test':'CONSERVATIVE_REQUESTS_ONLY_NO_STRESS_TEST'}
    try:
        sample = probe(args.provider)
        result['read_only_sample'] = sample
        if sample['status'] not in {'AUTHENTICATED_SAMPLE_OBSERVED','AUTHENTICATED_NO_SAMPLE'}:
            result['status'] = sample['status']
        else:
            archive = MarketArchive(args.root,initialize=True)
            catalog = sync_catalog(archive,args.provider)
            result['catalog'] = {'records':catalog['rows'],'manifest_hash':catalog['manifest_hash']}
            native = sample.get('native_key') if args.provider=='upstox' else 'AAPL'
            instruments = select(archive,args.provider,[native])
            now = datetime.now(timezone.utc)
            history = HistoryService(archive).fetch(instruments[0],'1d',now-timedelta(days=14),now)
            result['history'] = {k:v for k,v in history.items() if k!='items'}
            result['history']['rows'] = len(history['items'])
            result['history_accuracy'] = verify_history_accuracy(instruments[0],history['items'])
            if result['history_accuracy']['status']!='EXACT_OHLCV_MATCH':
                raise ProviderFailure('HISTORY_ACCURACY_'+result['history_accuracy']['status'])
            stream = asyncio.run(collect(archive,args.provider,instruments,'1m',args.seconds,reconnect_recovery=False))
            result['stream'] = stream
            if args.delayed_sip:
                if args.provider!='alpaca':
                    raise ProviderFailure('DELAYED_SIP_REQUIRES_ALPACA')
                result['delayed_sip'] = asyncio.run(collect(archive,args.provider,instruments,'1m',args.seconds,
                    reconnect_recovery=False,feed='delayed_sip'))
            stats = stream['stats']
            failure=feed_validation_code(stats)
            result['status'] = 'FEED_NOT_VALIDATED' if failure else 'AUTH_AND_FEED_PROBED'
            if failure:result['code']=failure
            if result.get('delayed_sip'):
                delayed_failure=feed_validation_code(result['delayed_sip']['stats'])
                if delayed_failure:
                    result.update(status='FEED_NOT_VALIDATED',code='DELAYED_SIP_NOT_ENTITLED_OR_NOT_AUTHENTICATED',
                                  delayed_sip_validation_code=delayed_failure)
            result['market_updates_observed'] = stats['events'] > 0
            # Preserve legacy receipt compatibility; this flag means messages
            # were decoded, not that their last-trade timestamps were fresh.
            result['market_updates_observed_semantics'] = 'DECODED_OBSERVATIONS_NOT_FRESHNESS'
            events = [row for manifest in archive.manifests('events',args.provider)
                      for row in archive.rows(manifest)]
            result['observation_evidence'] = event_evidence(events)
            result['integrity'] = archive.integrity()
    except ProviderFailure as error:
        result.update(status='DEFERRED_NOT_CONFIGURED' if error.code=='NOT_CONFIGURED' else 'PROBE_FAILED',code=error.code)
    except Exception:
        result.update(status='PROBE_FAILED',code='PROVIDER_PROBE_INPUT_OR_OPERATION_FAILED')
    args.output.parent.mkdir(parents=True,exist_ok=True)
    with args.output.open('x',encoding='utf-8') as stream:
        json.dump(result,stream,indent=2)
    print(json.dumps({'status':result['status'],'report':str(args.output.resolve()),'owner_writes':False}))
    return 0 if result['status']=='AUTH_AND_FEED_PROBED' else 1


if __name__=='__main__':
    raise SystemExit(main())
