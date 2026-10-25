"""Bounded read-only feed workers, shared by backend consumers.

No broker SDK, order API, simulated prices or silently filled tick gaps.
Credentials and one-use Upstox websocket URLs stay inside connection scope.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import random
import re
import time
from collections import deque
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from urllib.parse import urlsplit
from urllib.parse import quote

from pydantic import BaseModel, ConfigDict, model_validator
from websockets.asyncio.client import connect

from .contracts import utc
from .market_archive import digest, encoded, stamp, publish, link_path
from .market_history import SourceCandle, next_boundary
from .market_universe import PacedTransport, headers
from .providers import ProviderFailure


class FeedEvent(BaseModel):
    model_config = ConfigDict(extra='forbid')
    provider: str
    native_id: str
    symbol: str
    kind: str
    feed: str
    event_at: datetime
    received_at: datetime
    source_timestamp: str
    source_hash: str
    provider_record_id: str | None = None
    source_exchange: str | None = None
    bid_exchange: str | None = None
    ask_exchange: str | None = None
    price: Decimal | None = None
    bid: Decimal | None = None
    ask: Decimal | None = None
    candle: dict | None = None
    is_final: bool = False
    delay_seconds: int = 0

    @model_validator(mode='after')
    def validate_event(self):
        self.event_at, self.received_at = utc(self.event_at), utc(self.received_at)
        if self.event_at > self.received_at + timedelta(seconds=5):
            raise ValueError('future event')
        if any(v is not None and (not v.is_finite() or v < 0) for v in (self.price, self.bid, self.ask)):
            raise ValueError('invalid price')
        if self.price is None and self.bid is None and self.ask is None and self.candle is None:
            raise ValueError('no market observation')
        if self.candle:
            c = self.candle
            opened, closed = (utc(datetime.fromisoformat(c[k])) for k in ('start_at','end_at'))
            values = [Decimal(c[k]) for k in ('open','high','low','close','volume')]
            if (opened >= closed or (self.is_final and closed > self.received_at+timedelta(seconds=5)) or
                any(not v.is_finite() or v<0 for v in values) or values[2]>min(values[0],values[3]) or
                values[1]<max(values[0],values[3]) or values[1]<values[2]):
                raise ValueError('invalid source candle')
        return self


def milliseconds(value):
    return datetime.fromtimestamp(int(value)/1000, timezone.utc)


def decode_events(provider, payload, instruments, *, received_at=None, feed=None):
    received = received_at or datetime.now(timezone.utc)
    wire = payload if isinstance(payload, bytes) else payload.encode()
    sha = hashlib.sha256(wire).hexdigest()
    result = []
    if provider == 'upstox':
        if not isinstance(payload, bytes):
            raise ProviderFailure('UPSTOX_BINARY_FEED_REQUIRED')
        from google.protobuf.json_format import MessageToDict
        from .feed_proto.MarketDataFeed_pb2 import FeedResponse
        message = FeedResponse()
        message.ParseFromString(payload)
        obj = MessageToDict(message)
        entries = obj.get('feeds', {}).items()
    else:
        obj = json.loads(payload)
        entries = [(None, obj.get('data', obj))] if provider == 'binance' else [(None, r) for r in obj]
    by_symbol = {r['symbol']: r for r in instruments}
    by_native = {r['native_id']: r for r in instruments}
    for native, row in entries:
        common = {'provider': provider, 'received_at': received, 'source_hash': sha}
        if provider == 'binance':
            if row.get('e') == 'serverShutdown':
                raise ProviderFailure('SERVER_SHUTDOWN', retryable=True)
            instrument = by_symbol.get(row.get('s'))
            if not instrument:
                continue
            event = milliseconds(row['E'])
            common.update(native_id=instrument['native_id'], symbol=instrument['symbol'],
                          feed='spot_public', event_at=event, source_timestamp=str(row['E']))
            if row['e'] in {'24hrMiniTicker', '24hrTicker'}:
                common.update(kind='ticker', price=row['c'])
            elif row['e'] == 'kline':
                k = row['k']
                opened, closed = milliseconds(k['t']), milliseconds(int(k['T'])+1)
                if closed != next_boundary(opened, k['i'], 'UTC'):
                    raise ProviderFailure('UNEXPECTED_STREAM_CANDLE_WINDOW')
                common.update(kind='candle', price=k['c'], is_final=k['x'], candle={
                    'interval': k['i'], 'start_at': opened.isoformat(), 'end_at': closed.isoformat(),
                    'open': k['o'], 'high': k['h'], 'low': k['l'], 'close': k['c'], 'volume': k['v']})
            else:
                continue
        elif provider == 'alpaca':
            if row.get('T') == 'error':
                # Never serialize provider messages, which may echo credentials.
                code = row.get('code')
                raise ProviderFailure('STREAM_ACCESS_DENIED' if code in (402, 403, 405, 406, 409) else 'STREAM_PROVIDER_ERROR')
            instrument = by_symbol.get(row.get('S'))
            if not instrument or row.get('T') not in {'t', 'q', 'b', 'u'}:
                continue
            event = utc(datetime.fromisoformat(row['t'].replace('Z', '+00:00')))
            common.update(native_id=instrument['native_id'], symbol=instrument['symbol'], event_at=event,
                          source_timestamp=row['t'], feed=feed or 'iex', delay_seconds=900 if feed == 'delayed_sip' else 0)
            if row['T'] == 't':
                common.update(kind='trade', price=row['p'],source_exchange=row.get('x'),
                              provider_record_id=str(row.get('i')) if row.get('i') is not None else None)
            elif row['T'] == 'q':
                common.update(kind='quote', bid=row['bp'], ask=row['ap'],
                              bid_exchange=row.get('bx'),ask_exchange=row.get('ax'))
            else:
                common.update(kind='candle_revision' if row['T'] == 'u' else 'candle', price=row['c'], is_final=True,
                              candle={'interval': '1m', 'start_at': event.isoformat(),
                              'end_at': (event+timedelta(minutes=1)).isoformat(),
                              **{k: str(row[v]) for k, v in [('open','o'),('high','h'),('low','l'),('close','c'),('volume','v')]}})
        else:
            instrument = by_native.get(native)
            if not instrument:
                continue
            ltpc = row.get('ltpc') or row.get('fullFeed', {}).get('marketFF', {}).get('ltpc')
            if not ltpc or not ltpc.get('ltt'):
                continue
            common.update(native_id=native, symbol=instrument['symbol'], kind='last_trade_snapshot', feed='v3_ltpc',
                          price=ltpc['ltp'], event_at=milliseconds(ltpc['ltt']), source_timestamp=str(ltpc['ltt']))
        value = FeedEvent.model_validate(common)
        if value.candle:
            c = value.candle
            prices = [Decimal(c[k]) for k in ('open', 'high', 'low', 'close', 'volume')]
            if (any(not v.is_finite() or v < 0 for v in prices) or prices[2] > min(prices[0], prices[3])
                    or prices[1] < max(prices[0], prices[3]) or prices[1] < prices[2]):
                raise ProviderFailure('INVALID_STREAM_OHLCV')
        result.append(value.model_dump(mode='json'))
        if provider == 'upstox':
            ohlc = row.get('fullFeed', {}).get('marketFF', {}).get('marketOHLC', {}).get('ohlc', [])
            for c in ohlc:
                interval = {'I1':'1m','1d':'1d'}.get(c.get('interval'))
                if not interval or not c.get('ts') or not all(k in c for k in ('open','high','low','close','vol')):
                    continue
                opened = milliseconds(c['ts'])
                result.append(FeedEvent.model_validate({**common,'kind':'candle','feed':'v3_full',
                    'price':c['close'],'is_final':False,'candle':{'interval':interval,
                        'start_at':opened.isoformat(),'end_at':next_boundary(opened,interval,'Asia/Kolkata').isoformat(),
                        **{k:str(c[k]) for k in ('open','high','low','close')},'volume':str(c['vol'])}}).model_dump(mode='json'))
    return result


class SubscriptionPool:
    """Consumer references share one bounded provider subscription union."""
    def __init__(self, provider, limit=None):
        self.provider = provider
        self.limit = limit or {'binance': 50, 'upstox': 50, 'alpaca': 30}[provider]
        self.clients = {}

    def set(self, client_id, native_ids):
        if len(self.clients) >= 100 and client_id not in self.clients:
            raise ProviderFailure('CONSUMER_LIMIT')
        proposed = {**self.clients, client_id: set(native_ids)}
        union = set().union(*proposed.values())
        if len(union) > self.limit:
            raise ProviderFailure('SUBSCRIPTION_LIMIT')
        self.clients = proposed
        return sorted(union)

    def remove(self, client_id):
        self.clients.pop(client_id, None)
        return sorted(set().union(*self.clients.values()))


def approved_socket(provider, instruments, interval='1m', feed='iex', transport=None):
    if not instruments or len({r['native_id'] for r in instruments}) != len(instruments):
        raise ProviderFailure('INVALID_STREAM_SELECTION')
    pool = SubscriptionPool(provider)
    pool.set('collector', [r['native_id'] for r in instruments])
    if any(r['provider'] != provider or not r['present'] for r in instruments):
        raise ProviderFailure('INVALID_STREAM_SELECTION')
    statuses = {'binance':{'TRADING'},'upstox':{'LISTED'},'alpaca':{'active'}}[provider]
    if any(r['status'] not in statuses for r in instruments):
        raise ProviderFailure('STREAM_INSTRUMENT_NOT_ACTIVE')
    if provider == 'binance':
        if interval not in {'1m','5m','15m','1h','4h','1d','1w','1M'}:
            raise ProviderFailure('UNSUPPORTED_STREAM_INTERVAL')
        symbols = [r['symbol'].lower() for r in instruments]
        if any(not 3<=len(s)<=40 or not all(c.isalnum() for c in s) for s in symbols):
            raise ProviderFailure('UNSUPPORTED_STREAM_SYMBOL_ENCODING')
        streams = '/'.join(quote(s,safe='')+suffix for s in symbols for suffix in ('@miniTicker', '@kline_'+interval))
        return 'wss://data-stream.binance.vision/stream?streams='+streams, None
    if provider == 'alpaca':
        if feed not in {'iex', 'delayed_sip'}:
            raise ProviderFailure('UNAPPROVED_STREAM_FEED')
        # Delayed SIP is explicit and may fail entitlement; never substitute IEX.
        return 'wss://stream.data.alpaca.markets/v2/'+feed, headers(provider)
    transport = transport or PacedTransport()
    page = transport.get('api.upstox.com', '/v3/feed/market-data-feed/authorize', headers=headers(provider))
    url = page.data.get('data', {}).get('authorized_redirect_uri')
    if not isinstance(url, str):
        raise ProviderFailure('INVALID_AUTHORIZED_FEED_URL')
    parsed = urlsplit(url)
    if (parsed.scheme != 'wss' or not parsed.hostname or not parsed.hostname.endswith('.upstox.com') or
        parsed.username or parsed.password or parsed.port not in (None, 443) or
        not parsed.path.startswith('/market-data-feeder/v3/')):
        raise ProviderFailure('FEED_DESTINATION_NOT_ALLOWED')
    return url, None


def display_state(event, *, now=None, connected=True, stale_seconds=30):
    if event is None:
        return 'UNAVAILABLE'
    now = now or datetime.now(timezone.utc)
    lag = (now-datetime.fromisoformat(event['event_at'])).total_seconds()-event['delay_seconds']
    receipt_lag = (now-datetime.fromisoformat(event['received_at'])).total_seconds()
    if not connected or min(lag, receipt_lag) < -5 or max(lag, receipt_lag) > stale_seconds:
        return 'STALE'
    return 'DELAYED' if event['delay_seconds'] else 'LIVE'


def collector_state(archive, provider):
    directory = archive.root / 'collector' / provider
    snapshots = list(directory.glob('????????T*Z-*.json'))
    if snapshots:
        path = max(snapshots)
        raw = path.read_bytes()
        if hashlib.sha256(raw).hexdigest() != path.stem.rsplit('-',1)[-1]:
            raise ProviderFailure('COLLECTOR_STATE_HASH_MISMATCH')
        return json.loads(raw)
    legacy = archive.root / 'collector' / (provider+'.json')
    return json.loads(legacy.read_bytes()) if legacy.exists() else None


class FeedWorker:
    def __init__(self, archive, provider, instruments, *, interval='1m', feed='iex', upstox_mode='ltpc',
                 mode='bounded_capture',connector=None, max_retries=5, transport=None, payload_observer=None):
        self.archive, self.provider, self.instruments = archive, provider, instruments
        self.interval, self.feed, self.connector = interval, feed, connector or connect
        self.max_retries = max_retries
        self.transport, self.payload_observer = transport, payload_observer
        if upstox_mode not in {'ltpc','full'}:
            raise ProviderFailure('UNAPPROVED_UPSTOX_STREAM_MODE')
        self.upstox_mode = upstox_mode
        if mode not in {'bounded_capture','continuous_independent_test'}:
            raise ProviderFailure('INVALID_COLLECTION_MODE')
        self.mode = mode
        self.seen, self.order = set(), deque(maxlen=4096)
        self.latest, self.pending = {}, []
        self.stats = {'messages':0, 'events':0, 'duplicates':0, 'reconnections':0, 'out_of_order':0, 'connected':False,
                      'ever_connected':False, 'authentication_confirmed':False, 'subscription_confirmed':False}
        self.last_received = None
        self.last_flush = time.monotonic()
        self.max_capture_events = 200_000

    def accept(self, events):
        for event in events:
            key = digest({k:v for k,v in event.items() if k not in {'received_at','source_hash'}})
            if key in self.seen:
                self.stats['duplicates'] += 1
                continue
            if self.stats['events'] >= self.max_capture_events:
                raise ProviderFailure('CAPTURE_EVENT_BUDGET_EXHAUSTED')
            if len(self.order) == self.order.maxlen:
                self.seen.discard(self.order[0])
            self.order.append(key)
            self.seen.add(key)
            key_kind = event['native_id']+'|'+event['kind']
            current = self.latest.get(key_kind)
            if not current or event['event_at'] >= current['event_at']:
                self.latest[key_kind] = event
            else:
                self.stats['out_of_order'] += 1
            self.pending.append(event)
            self.stats['events'] += 1
            self.last_received = event['received_at']

    def flush(self):
        if self.pending:
            self.archive.append('events', self.provider, self.pending, sources=[],
                                metadata={'feed':self.feed if self.provider == 'alpaca' else self.provider,
                                          'tick_gap_recovery':'UNAVAILABLE_FROM_OHLCV'})
            self.pending = []
        state = {'provider':self.provider, 'updated_at':stamp(), 'stats':self.stats, 'items':list(self.latest.values()),
                 'latest_received_at':self.last_received, 'mode':self.mode, 'owner_writes':False}
        # OneDrive/Windows may hold the previous file open without delete sharing.
        # Publish immutable checkpoints instead of replacing an open checkpoint.
        directory = self.archive.root / 'collector' / self.provider
        self.archive.assert_capacity(3*len(encoded(state)))
        target = publish(directory,encoded(state),'.json')
        token = datetime.fromisoformat(state['updated_at']).strftime('%Y%m%dT%H%M%S%fZ')
        alias = directory / (token+'-'+target.stem+'.json')
        try:
            os.link(link_path(target),link_path(alias))
        except FileExistsError:
            pass
        self.last_flush = time.monotonic()

    def gap(self, start, end, reason):
        self.archive.append('gaps', self.provider, [{'from':start, 'to':end, 'reason':reason,
            'native_ids':[r['native_id'] for r in self.instruments], 'tick_recovery':'UNRECOVERABLE',
            'ohlcv_recovery':'REQUIRES_BOUNDED_HISTORY_REFRESH'}], sources=[])

    async def run(self, seconds=60):
        lock = self.archive.root / ('.collector-'+self.provider+'.lock')
        try:
            stream = lock.open('x')
        except FileExistsError:
            raise ProviderFailure('COLLECTOR_ALREADY_RUNNING') from None
        try:
            with stream:
                stream.write(str(os.getpid()))
            return await self._run(seconds)
        finally:
            lock.unlink(missing_ok=True)

    async def _run(self, seconds=60):
        if not 1 <= seconds <= 86400:
            raise ProviderFailure('INVALID_COLLECTOR_DURATION')
        deadline, retries = time.monotonic()+seconds, 0
        prior = collector_state(self.archive,self.provider)
        if prior:
            if prior.get('latest_received_at'):
                self.gap(prior['latest_received_at'], stamp(), 'COLLECTOR_OFFLINE')
        while time.monotonic() < deadline:
            disconnected_at = stamp()
            try:
                url, auth = await asyncio.to_thread(approved_socket, self.provider, self.instruments,
                                                    self.interval, self.feed, self.transport)
                # Suppress connection debug logs, especially signed one-use URLs.
                logger = logging.getLogger('market_cortex.private_feed')
                logger.disabled = True
                async with self.connector(url, open_timeout=10, ping_interval=20, ping_timeout=20,
                                          max_size=2_000_000, max_queue=16, logger=logger) as socket:
                    if self.provider == 'alpaca':
                        await socket.send(json.dumps({'action':'auth','key':auth['APCA-API-KEY-ID'], 'secret':auth['APCA-API-SECRET-KEY']}))
                        authenticated = False
                        for _ in range(3):
                            reply = json.loads(await asyncio.wait_for(socket.recv(), timeout=10))
                            if any(r.get('T') == 'error' for r in reply):
                                raise ProviderFailure('STREAM_ACCESS_DENIED')
                            if any(r.get('T') == 'success' and r.get('msg') == 'authenticated' for r in reply):
                                authenticated = True
                                break
                        if not authenticated:
                            raise ProviderFailure('STREAM_AUTH_NOT_CONFIRMED')
                        self.stats['authentication_confirmed'] = True
                        symbols = [r['symbol'] for r in self.instruments]
                        await socket.send(json.dumps({'action':'subscribe','trades':symbols,'quotes':symbols,'bars':symbols,'updatedBars':symbols}))
                    elif self.provider == 'upstox':
                        await socket.send(encoded({'guid':'market-cortex-read-only','method':'sub','data':{
                            'mode':self.upstox_mode,'instrumentKeys':[r['native_id'] for r in self.instruments]}}))
                    self.stats['connected'] = True
                    self.stats['ever_connected'] = True
                    if self.provider == 'binance':
                        self.stats['authentication_confirmed'] = True  # Public feed, no credential exchange.
                        self.stats['subscription_confirmed'] = True
                    self.flush()
                    rotate_at = time.monotonic()+23*3600+50*60
                    while time.monotonic() < min(deadline, rotate_at):
                        try:
                            payload = await asyncio.wait_for(socket.recv(), timeout=min(5, deadline-time.monotonic()))
                        except asyncio.TimeoutError:
                            # Websocket ping/pong proves transport health; no fake data when idle.
                            self.flush()
                            continue
                        self.stats['messages'] += 1
                        if self.provider == 'alpaca':
                            response = json.loads(payload)
                            for entry in response:
                                if entry.get('T') == 'subscription':
                                    expected = {r['symbol'] for r in self.instruments}
                                    self.stats['subscription_confirmed'] = all(expected <= set(entry.get(k, [])) for k in ('trades','quotes','bars'))
                        if self.payload_observer is not None:
                            self.payload_observer(payload)
                        events = decode_events(self.provider, payload, self.instruments, feed=self.feed)
                        if self.provider == 'upstox' and isinstance(payload, bytes):
                            self.stats['authentication_confirmed'] = True
                            self.stats['subscription_confirmed'] = bool(events) or self.stats['subscription_confirmed']
                        self.accept(events)
                        if self.stats['events'] >= self.max_capture_events:
                            raise ProviderFailure('CAPTURE_EVENT_BUDGET_EXHAUSTED')
                        if len(self.pending) >= 100 or time.monotonic()-self.last_flush >= 5:
                            self.flush()
                    self.flush()
                    if time.monotonic() >= deadline:
                        break
            except ProviderFailure as error:
                self.stats['last_error'] = error.code
                if not error.retryable:
                    break
            except Exception:
                self.stats['last_error'] = 'STREAM_NETWORK_OR_DECODE_FAILURE'
            finally:
                self.stats['connected'] = False
                self.flush()
            retries += 1
            self.stats['reconnections'] += 1
            self.gap(self.last_received or disconnected_at, stamp(), 'CONNECTION_INTERRUPTION')
            if retries > self.max_retries:
                self.stats['last_error'] = 'STREAM_RETRY_BUDGET_EXHAUSTED'
                break
            await asyncio.sleep(min(30, 2**(retries-1)+random.random(), max(0, deadline-time.monotonic())))
        self.stats['connected'] = False
        self.flush()
        return self.stats
