"""Bounded, cache-first source OHLCV. Calendar authority is never invented.

Native samples remain separate from canonical Bar ingestion until mappings and
exchange sessions are verified. Existing daily adapters provide that strict gate.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from urllib.parse import quote
from zoneinfo import ZoneInfo

from pydantic import BaseModel, ConfigDict, model_validator

from .contracts import utc
from .market_archive import digest, stamp
from .market_universe import PacedTransport, headers
from .providers import ProviderFailure

INTERVALS = {
    '1m': ('PT1M', 60, 'minutes', 1, '1Min'),
    '5m': ('PT5M', 300, 'minutes', 5, '5Min'),
    '15m': ('PT15M', 900, 'minutes', 15, '15Min'),
    '1h': ('PT1H', 3600, 'hours', 1, '1Hour'),
    '4h': ('PT4H', 14400, 'hours', 4, '4Hour'),
    '1d': ('P1D', 86400, 'days', 1, '1Day'),
    '1w': ('P1W', 604800, 'weeks', 1, '1Week'),
    '1M': ('P1M', None, 'months', 1, '1Month'),
}

# The public REST mirror can still return provisional close/volume immediately
# after its declared boundary. Keep those observations out of closed history.
BINANCE_FINALIZATION_GRACE = timedelta(seconds=10)


class SourceCandle(BaseModel):
    model_config = ConfigDict(extra='forbid')
    provider: str
    native_id: str
    symbol: str
    interval: str
    start_at: datetime
    end_at: datetime
    available_at: datetime
    provider_timestamp: str
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal
    feed: str
    adjustment_basis: str
    source_hash: str
    currency: str
    volume_unit: str
    timezone: str
    canonical_status: str = 'REQUIRES_VERIFIED_MAPPING_AND_CALENDAR'

    @model_validator(mode='after')
    def values(self):
        self.start_at, self.end_at, self.available_at = map(utc, (self.start_at, self.end_at, self.available_at))
        if (self.start_at >= self.end_at or self.end_at > self.available_at or
            any(not p.is_finite() or p < 0 for p in (self.open, self.high, self.low, self.close, self.volume)) or
            self.low > min(self.open, self.close) or self.high < max(self.open, self.close) or self.high < self.low):
            raise ValueError('invalid closed source candle')
        return self


def next_boundary(start, interval, timezone_name):
    local = start.astimezone(ZoneInfo(timezone_name))
    seconds = INTERVALS[interval][1]
    if interval == '1M':
        result = local.replace(year=local.year + (local.month == 12), month=local.month % 12 + 1)
    elif interval in {'1d', '1w'}:
        result = local + timedelta(seconds=seconds)
    else:
        return start + timedelta(seconds=seconds)
    return result.astimezone(timezone.utc)


def candle_key(row):
    return (row['native_id'], row['interval'], row['feed'], row['adjustment_basis'], row['start_at'])


def candle_fingerprint(row):
    return digest({k: row[k] for k in ('native_id', 'interval', 'feed', 'adjustment_basis', 'start_at',
                                    'end_at', 'open', 'high', 'low', 'close', 'volume')})


def cached_candles(archive, provider, native_id, interval, start, end, *, feed=None, as_of=None):
    heads = {}
    for manifest in archive.manifests('candles', provider, as_of):
        # Verified manifests partition new captures by identity and interval.
        # Legacy/mixed captures without these hints still require a full read.
        metadata = manifest.get('metadata', {})
        if (metadata.get('native_id') is not None and metadata['native_id'] != native_id or
            metadata.get('interval') is not None and metadata['interval'] != interval):
            continue
        for row in archive.rows(manifest):
            if (row['native_id'] == native_id and row['interval'] == INTERVALS[interval][0] and
                (feed is None or row['feed'] == feed) and
                (as_of is None or datetime.fromisoformat(row['available_at']) <= as_of) and
                start <= datetime.fromisoformat(row['start_at']) < end):
                heads[candle_key(row)] = row
    return sorted(heads.values(), key=lambda r: r['start_at'])


def subtract_ranges(start, end, covered):
    gaps = [(start, end)]
    for left, right in sorted(covered):
        remaining = []
        for a, b in gaps:
            if left >= b or right <= a:
                remaining.append((a, b))
            else:
                if a < left:
                    remaining.append((a, left))
                if right < b:
                    remaining.append((right, b))
        gaps = remaining
    return gaps


class HistoryService:
    def __init__(self, archive, transport=None, *, now=None, max_pages=20, max_rows=20_000):
        self.archive, self.transport = archive, transport or PacedTransport()
        self.now, self.max_pages, self.max_rows = now, max_pages, max_rows

    def fetch(self, instrument, interval, start, end, *, refresh=False, feed=None):
        now = self.now or datetime.now(timezone.utc)
        start, end = utc(start), utc(end)
        provider, native = instrument['provider'], instrument['native_id']
        if interval not in INTERVALS or start >= end or end > now or end-start > timedelta(days=3660):
            raise ProviderFailure('INVALID_HISTORY_RANGE_OR_INTERVAL')
        if not instrument['present'] or instrument['status'] in {'SUSPENDED', 'CONFLICTING_LISTED_AND_SUSPENDED', 'ABSENT_FROM_CURRENT_SOURCE'}:
            raise ProviderFailure('INSTRUMENT_NOT_CURRENTLY_AVAILABLE')
        feed = feed or {'binance': 'spot_public', 'upstox': 'historical_v3', 'alpaca': 'iex'}[provider]
        if feed != {'binance': 'spot_public', 'upstox': 'historical_v3', 'alpaca': 'iex'}[provider]:
            raise ProviderFailure('UNAPPROVED_HISTORY_FEED')
        covered, matured_coverage = [], []
        if not refresh:
            for m in self.archive.manifests('requests', provider):
                meta = m['metadata']
                if meta.get('native_id') == native and meta.get('interval') == interval and meta.get('feed') == feed:
                    # Empty responses are retryable after one hour, never considered complete history.
                    if meta.get('returned_rows'):
                        left, right = datetime.fromisoformat(meta['start']), datetime.fromisoformat(meta['end'])
                        closed = meta.get('closed_coverage_end')
                        if closed is None:
                            # Old independent receipts must not hide their last in-progress candle.
                            observed_rows = cached_candles(self.archive,provider,native,interval,left,right,
                                feed=feed,as_of=datetime.fromisoformat(m['observed_at']))
                            closed = max((r['end_at'] for r in observed_rows),default=meta['start'])
                        covered.append((left,min(right,datetime.fromisoformat(closed))))
                        matured_coverage.append((left,min(right,datetime.fromisoformat(closed),
                            datetime.fromisoformat(m['observed_at'])-BINANCE_FINALIZATION_GRACE)))
                    elif (now-datetime.fromisoformat(m['observed_at']) < timedelta(seconds=min(3600,INTERVALS[interval][1] or 3600)) and
                          not (provider=='binance' and meta.get('finalization_pending') and
                               now >= datetime.fromisoformat(meta['end'])+BINANCE_FINALIZATION_GRACE)):
                        covered.append((datetime.fromisoformat(meta['start']), datetime.fromisoformat(meta['end'])))
        gaps = subtract_ranges(start, end, covered)
        if provider == 'binance' and not refresh:
            # Reconcile only old captures taken too close to their boundary.
            # A mature request receipt prevents repeated downloads even if the
            # provider values were unchanged. Corrections append new revisions.
            for row in cached_candles(self.archive,provider,native,interval,start,end,feed=feed):
                opened,closed,received=map(datetime.fromisoformat,
                    (row['start_at'],row['end_at'],row['available_at']))
                if (received < closed+BINANCE_FINALIZATION_GRACE and closed+BINANCE_FINALIZATION_GRACE <= now and
                    not any(a <= opened and closed <= b for a,b in matured_coverage)):
                    gaps.append((opened,closed))
            merged=[]
            for a,b in sorted(gaps):
                if merged and a <= merged[-1][1]:merged[-1]=(merged[-1][0],max(merged[-1][1],b))
                else:merged.append((a,b))
            gaps=merged
        call_budget, fetched_rows, writes = self.max_pages, 0, 0
        for a, b in gaps:
            rows, sources, calls = self._fetch(instrument, interval, a, b, now, call_budget)
            observed = self.now or datetime.now(timezone.utc)
            call_budget -= calls
            fetched_rows += len(rows)
            if fetched_rows > self.max_rows:
                raise ProviderFailure('HISTORY_ROW_BUDGET')
            old = cached_candles(self.archive, provider, native, interval, a, b, feed=feed)
            old = {candle_key(r): candle_fingerprint(r) for r in old}
            changed = [r for r in rows if old.get(candle_key(r)) != candle_fingerprint(r)]
            if changed:
                self.archive.append('candles', provider, changed, sources=sources,
                                    metadata={'interval': interval, 'native_id': native}, observed_at=observed.isoformat())
                writes += len(changed)
            self.archive.append('requests', provider, [], sources=sources, metadata={
                'native_id': native, 'interval': interval, 'feed': feed, 'start': a.isoformat(), 'end': b.isoformat(),
                'closed_coverage_end':min(b,max((datetime.fromisoformat(r['end_at']) for r in rows),default=a)).isoformat(),
                'finalization_pending':provider=='binance' and b > observed-BINANCE_FINALIZATION_GRACE,
                'returned_rows': len(rows), 'coverage': 'PROVIDER_RETURNED_ONLY', 'calendar_verified': provider == 'binance'},
                observed_at=observed.isoformat())
        result = cached_candles(self.archive, provider, native, interval, start, end, feed=feed)
        return {'items': result, 'cache_hit': not gaps, 'provider_calls': self.max_pages-call_budget,
                'new_revisions': writes, 'state': 'HISTORICAL' if result else 'UNAVAILABLE',
                'feed': feed, 'calendar': 'UTC_24X7' if provider == 'binance' else 'UNVERIFIED_SOURCE_WINDOWS',
                'coverage': 'PROVIDER_RETURNED_ONLY', 'complete_market_history': False,
                'volume_coverage': 'IEX_ONLY' if provider == 'alpaca' else 'PROVIDER_NATIVE',
                'adjustment_basis': 'provider_unspecified' if provider == 'upstox' else 'raw'}

    def _fetch(self, instrument, interval, start, end, now, budget):
        provider, native, symbol = instrument['provider'], instrument['native_id'], instrument['symbol']
        rows, sources, calls = [], [], 0
        zone = {'binance': 'UTC', 'upstox': 'Asia/Kolkata', 'alpaca': 'America/New_York'}[provider]
        iso_interval, seconds, unit, number, alpaca_interval = INTERVALS[interval]
        auth = {} if provider == 'binance' else headers(provider)
        cursor, token, seen_tokens = start, None, set()
        while cursor < end:
            if calls >= budget:
                raise ProviderFailure('HISTORY_CALL_BUDGET')
            if provider == 'binance':
                if instrument['segment'] != 'SPOT':
                    raise ProviderFailure('WRONG_MARKET_SEGMENT')
                page = self.transport.get('data-api.binance.vision', '/api/v3/klines', params={
                    'symbol': symbol, 'interval': interval, 'timeZone': '0', 'startTime': int(cursor.timestamp()*1000),
                    'endTime': int(end.timestamp()*1000)-1, 'limit': 1000})
                data = page.data
            elif provider == 'upstox':
                if instrument['segment'] not in {'NSE_EQ', 'BSE_EQ'} or not native.startswith(instrument['segment']+'|'):
                    raise ProviderFailure('WRONG_MARKET_SEGMENT')
                days = 28 if unit == 'minutes' and number <= 15 else 80 if unit in {'minutes', 'hours'} else 366
                chunk_end = min(cursor+timedelta(days=days), end)
                first = cursor.astimezone(ZoneInfo(zone)).date()
                last = (chunk_end-timedelta(microseconds=1)).astimezone(ZoneInfo(zone)).date()
                page = self.transport.get('api.upstox.com', f'/v3/historical-candle/{quote(native, safe="")}/{unit}/{number}/{last}/{first}', headers=auth)
                data = page.data.get('data', {}).get('candles') if isinstance(page.data, dict) else None
            else:
                params = {'timeframe': alpaca_interval, 'start': start.isoformat(), 'end': end.isoformat(),
                          'feed': 'iex', 'adjustment': 'raw', 'asof': '-', 'limit': 1000, 'sort': 'asc'}
                if token:
                    params['page_token'] = token
                page = self.transport.get('data.alpaca.markets', f'/v2/stocks/{symbol}/bars', params=params, headers=auth)
                data = page.data.get('bars') if isinstance(page.data, dict) else None
            calls += 1
            arrived = self.now or datetime.now(timezone.utc)
            sources.append({'endpoint': provider+':history:'+interval, 'sha256': page.content_hash})
            if not isinstance(data, list):
                raise ProviderFailure('MALFORMED_CANDLE_RESPONSE')
            page_starts = []
            for raw in data:
                try:
                    if provider == 'binance':
                        opened = datetime.fromtimestamp(raw[0]/1000, timezone.utc)
                        closed = datetime.fromtimestamp((raw[6]+1)/1000, timezone.utc)
                        source_time, values = str(raw[0]), raw[1:6]
                        if closed != next_boundary(opened, interval, zone):
                            raise ProviderFailure('UNEXPECTED_CANDLE_WINDOW')
                    elif provider == 'upstox':
                        source_time, values = raw[0], raw[1:6]
                        opened = utc(datetime.fromisoformat(source_time.replace('Z', '+00:00')))
                        closed = next_boundary(opened, interval, zone)
                    else:
                        source_time, values = raw['t'], [raw[k] for k in ('o', 'h', 'l', 'c', 'v')]
                        opened = utc(datetime.fromisoformat(source_time.replace('Z', '+00:00')))
                        closed = next_boundary(opened, interval, zone)
                    page_starts.append(opened)
                    maturity = arrived-BINANCE_FINALIZATION_GRACE if provider=='binance' else arrived
                    if not start <= opened < end or closed > maturity:
                        continue
                    item = SourceCandle(provider=provider, native_id=native, symbol=symbol, interval=iso_interval,
                        start_at=opened, end_at=closed, available_at=arrived, provider_timestamp=source_time,
                        open=values[0], high=values[1], low=values[2], close=values[3], volume=values[4],
                        feed={'binance':'spot_public', 'upstox':'historical_v3', 'alpaca':'iex'}[provider],
                        adjustment_basis='provider_unspecified' if provider == 'upstox' else 'raw',
                        source_hash=page.content_hash, currency=instrument['currency'],
                        volume_unit=instrument.get('base') or 'shares', timezone=zone)
                    rows.append(item.model_dump(mode='json'))
                    if len(rows) > self.max_rows:
                        raise ProviderFailure('HISTORY_ROW_BUDGET')
                except ProviderFailure:
                    raise
                except Exception:
                    raise ProviderFailure('INVALID_PROVIDER_CANDLE') from None
            if provider == 'binance':
                if page_starts != sorted(set(page_starts)):
                    raise ProviderFailure('NONMONOTONIC_PROVIDER_PAGE')
                if len(data) < 1000:
                    break
                next_cursor = next_boundary(max(page_starts), interval, zone)
                if next_cursor <= cursor:
                    raise ProviderFailure('PAGINATION_STALLED')
                cursor = next_cursor
            elif provider == 'upstox':
                cursor = chunk_end
            else:
                token = page.data.get('next_page_token')
                if token is None:
                    break
                if not isinstance(token, str) or token in seen_tokens:
                    raise ProviderFailure('PAGINATION_STALLED')
                seen_tokens.add(token)
        heads = {}
        for row in rows:
            key = candle_key(row)
            if key in heads and candle_fingerprint(heads[key]) != candle_fingerprint(row):
                raise ProviderFailure('CONFLICTING_PROVIDER_CANDLES')
            heads[key] = row
        return sorted(heads.values(), key=lambda r: r['start_at']), sources, calls
