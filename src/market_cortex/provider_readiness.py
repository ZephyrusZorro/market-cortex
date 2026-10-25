"""Independent GET-only access samples and optional canonical adapter diagnostics.

No database connection, bootstrap, ingestion, authentication exchange or trading.
Sampling does not prove complete history, identity lineage or calendar authority.
"""
from __future__ import annotations

import argparse
import json
import os
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import quote
from zoneinfo import ZoneInfo

from pydantic import BaseModel, ConfigDict, Field

from .calendar import SessionCalendar
from .contracts import CalendarSession, IdentifierMapping, Instrument, Venue
from .providers import AlpacaDaily, UpstoxDaily, ProviderFailure, ReadTransport


class AdapterProbeBundle(BaseModel):
    model_config = ConfigDict(extra='forbid')
    instrument: Instrument
    mapping: IdentifierMapping
    venue: Venue
    calendar_id: str
    calendar_version: str
    sessions: list[CalendarSession]
    identity_evidence: str = Field(min_length=10, max_length=500)
    calendar_evidence: str = Field(min_length=10, max_length=500)
    start: datetime
    end: datetime


def configured(provider):
    names = ('UPSTOX_ACCESS_TOKEN',) if provider == 'upstox' else ('APCA_API_KEY_ID', 'APCA_API_SECRET_KEY')
    return all(os.environ.get(n) for n in names)


def probe(provider, *, symbol=None, transport=None, now=None, bundle=None):
    now = now or datetime.now(timezone.utc)
    report = {'provider':provider, 'observed_at':now.isoformat(), 'owner_ingestion':False,
              'database_access':False, 'rights':'PRIVATE_RESEARCH_ONLY_PENDING_ACCOUNT_TERMS',
              'canonical_identity':'REQUIRES_VERIFIED_MAPPING', 'calendar':'REQUIRES_VERIFIED_EXCHANGE_SESSIONS',
              'full_history_verified':False, 'live_entitlement':'UNKNOWN'}
    if not configured(provider):
        return {**report, 'status':'DEFERRED_NOT_CONFIGURED'}
    transport = transport or ReadTransport()
    try:
        symbol = symbol or ('RELIANCE' if provider == 'upstox' else 'AAPL')
        if not re.fullmatch('[A-Z][A-Z0-9.]{0,14}',symbol):
            raise ProviderFailure('INVALID_NATIVE_SYMBOL')
        if provider == 'upstox':
            headers = {'Authorization':'Bearer '+os.environ['UPSTOX_ACCESS_TOKEN']}
            lookup = transport.get('api.upstox.com', '/v2/instruments/search', params={
                'query':symbol, 'exchanges':'NSE', 'segments':'EQ', 'page_number':1, 'records':30}, headers=headers)
            data = lookup.data.get('data') if isinstance(lookup.data, dict) else None
            if not isinstance(data,list):
                raise ProviderFailure('MALFORMED_INSTRUMENT_RESPONSE')
            matches = [r for r in data if isinstance(r,dict) and r.get('trading_symbol') == symbol
                       and r.get('segment') == 'NSE_EQ' and r.get('exchange') == 'NSE']
            if len(matches) != 1:
                raise ProviderFailure('NO_UNIQUE_NATIVE_INSTRUMENT')
            native = matches[0].get('instrument_key')
            if not isinstance(native,str) or not re.fullmatch(r'NSE_EQ\|[A-Z0-9]{8,30}',native):
                raise ProviderFailure('INVALID_NATIVE_KEY')
            day = now.astimezone(ZoneInfo('Asia/Kolkata')).date()-timedelta(days=1)
            page = transport.get('api.upstox.com', f'/v3/historical-candle/{quote(native,safe="")}/days/1/{day}/{day-timedelta(days=14)}', headers=headers)
            rows = page.data.get('data',{}).get('candles') if isinstance(page.data,dict) and isinstance(page.data.get('data'),dict) else None
            timestamps = [r[0] for r in rows if isinstance(r,list) and len(r)>=6 and isinstance(r[0],str)] if isinstance(rows,list) else []
            report.update(feed='historical_v3', adjustment_basis='provider_unspecified', native_key=native,
                          instrument_search_hash=lookup.content_hash, exact_matches_on_sample_page=1,
                          complete_instrument_search=False)
        else:
            headers = {'APCA-API-KEY-ID':os.environ['APCA_API_KEY_ID'], 'APCA-API-SECRET-KEY':os.environ['APCA_API_SECRET_KEY']}
            day = now.astimezone(ZoneInfo('America/New_York')).date()
            page = transport.get('data.alpaca.markets', f'/v2/stocks/{symbol}/bars', params={
                'timeframe':'1Day', 'feed':'iex', 'adjustment':'raw', 'asof':'-', 'start':(day-timedelta(days=14)).isoformat(),
                'end':day.isoformat(), 'limit':1000}, headers=headers)
            rows = page.data.get('bars') if isinstance(page.data,dict) else None
            timestamps = [r['t'] for r in rows if isinstance(r,dict) and isinstance(r.get('t'),str)] if isinstance(rows,list) else []
            report.update(feed='iex', adjustment_basis='raw', next_page_present=bool(page.data.get('next_page_token')) if isinstance(page.data,dict) else False,
                          volume_coverage='IEX_ONLY_NOT_CONSOLIDATED', ticker_remapping='DISABLED_ASOF_DASH')
        if not isinstance(rows,list) or len(timestamps) != len(rows):
            raise ProviderFailure('MALFORMED_CANDLE_RESPONSE')
        parsed = [datetime.fromisoformat(t.replace('Z','+00:00')) for t in timestamps]
        if any(t.tzinfo is None for t in parsed):
            raise ProviderFailure('UNZONED_PROVIDER_TIMESTAMP')
        report.update(status='AUTHENTICATED_SAMPLE_OBSERVED' if rows else 'AUTHENTICATED_NO_SAMPLE', symbol=symbol,
                      rate_limit_headers=getattr(page,'rate_limit_headers',{}),
                      sample_count=len(rows), source_response_hash=page.content_hash,
                      first_sample=min(parsed).isoformat() if parsed else None,
                      last_sample=max(parsed).isoformat() if parsed else None)
        if bundle is not None:
            if bundle.end.tzinfo is None or bundle.start.tzinfo is None or bundle.start>=bundle.end or bundle.end>now or bundle.end-bundle.start>timedelta(days=31):
                raise ProviderFailure('INVALID_PROBE_BUNDLE_RANGE')
            if len({s.session_date for s in bundle.sessions}) != len(bundle.sessions):
                raise ProviderFailure('DUPLICATE_CALENDAR_SESSION')
            calendar = SessionCalendar(bundle.venue, bundle.calendar_id, bundle.calendar_version, bundle.sessions)
            adapter = UpstoxDaily(transport) if provider=='upstox' else AlpacaDaily(transport, feed='iex')
            batch = adapter.fetch_daily(bundle.instrument,bundle.mapping,calendar,bundle.start,bundle.end)
            expected = {s.session_date for s in bundle.sessions if s.status!='holiday' and bundle.start<=s.open_at<bundle.end}
            observed = {b.session_date for b in batch.bars}
            report['adapter'] = {'status':'VALIDATED_SUPPLIED_CANONICAL_INPUTS', 'accepted_daily_bars':len(batch.bars),
                'provider_response_hash':batch.raw_hash, 'pages':batch.pages,
                'missing_declared_sessions':sorted(d.isoformat() for d in expected-observed),
                'duplicate_sessions':len(batch.bars)-len(observed), 'authority_independently_verified':False}
    except ProviderFailure as error:
        report.update(status='PROBE_FAILED', code=error.code, retryable=error.retryable)
    except Exception:
        report.update(status='PROBE_FAILED', code='INVALID_INPUT_OR_PROVIDER_RESPONSE')
    # Metadata may echo a credential. Never serialize secrets or raw provider bodies.
    secrets = [os.environ.get(n) for n in ('UPSTOX_ACCESS_TOKEN','APCA_API_KEY_ID','APCA_API_SECRET_KEY')]
    def scrub(value):
        if isinstance(value,str):
            for secret in sorted((s for s in secrets if s),key=len,reverse=True):
                value=value.replace(secret,'[REDACTED]')
        elif isinstance(value,dict):
            return {scrub(k):scrub(v) for k,v in value.items()}
        elif isinstance(value,list):
            return [scrub(v) for v in value]
        return value
    return scrub(report)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--provider', choices=('upstox','alpaca'), required=True)
    parser.add_argument('--symbol')
    parser.add_argument('--bundle',type=Path)
    parser.add_argument('--output',type=Path)
    args = parser.parse_args()
    try:
        bundle = AdapterProbeBundle.model_validate_json(args.bundle.read_text(encoding='utf-8')) if args.bundle else None
        result = probe(args.provider,symbol=args.symbol,bundle=bundle)
        if args.output:
            args.output.parent.mkdir(parents=True,exist_ok=True)
            with args.output.open('x',encoding='utf-8') as stream:
                stream.write(json.dumps(result,indent=2)+'\n')
        print(json.dumps(result))
        return 1 if result['status']=='PROBE_FAILED' else 0
    except Exception:
        print(json.dumps({'status':'PROBE_FAILED','code':'INVALID_INPUT_OR_OUTPUT'}))
        return 1


if __name__=='__main__':
    raise SystemExit(main())
