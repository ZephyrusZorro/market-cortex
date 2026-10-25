"""Independent loopback API, deliberately not mounted in the owner application."""
from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict

from .contracts import utc
from .operations_security import local_request_allowed
from .market_archive import MarketArchive
from .market_history import HistoryService, INTERVALS, cached_candles
from .market_stream import display_state, collector_state
from .market_universe import search_catalog
from .providers import ProviderFailure


class HistoryRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    provider: str
    native_id: str
    interval: str = '1d'
    start: datetime
    end: datetime


def create_market_app(archive: MarketArchive, history=None, *, fetch_scope=None):
    app = FastAPI(title='MARKET CORTEX Independent Market Data', version='source-v1')
    @app.middleware('http')
    async def boundary(request: Request, call_next):
        test = bool(request.client and request.client.host == 'testclient')
        if ((request.client and request.client.host not in {'127.0.0.1','::1','testclient'}) or
            not local_request_allowed(request.headers.get('host',''), request.headers.get('origin'), test_client=test)):
            return JSONResponse(status_code=403, content={'code':'LOCAL_ONLY'})
        if request.method == 'POST' and len(await request.body()) > 8192:
            return JSONResponse(status_code=413, content={'code':'REQUEST_TOO_LARGE'})
        response = await call_next(request)
        response.headers['Cache-Control'] = 'no-store'
        return response
    service = history or HistoryService(archive)
    history_lock = threading.Lock()

    @app.exception_handler(ProviderFailure)
    async def provider_error(request, error):
        return JSONResponse(status_code=503 if error.retryable else 422, content={'code':error.code})

    @app.exception_handler(Exception)
    async def unexpected(request, error):
        return JSONResponse(status_code=500, content={'code':'MARKET_DATA_INTERNAL_ERROR'})

    def instrument(provider, native_id):
        if provider not in {'binance','upstox','alpaca'}:
            raise ProviderFailure('UNKNOWN_PROVIDER')
        # Use verified Parquet scalar columns to avoid inflating the whole
        # provider catalog for every history request. Match the native ID exactly.
        rows = search_catalog(archive,provider=provider,native_id=native_id,
                              include_absent=True,limit=2)['items']
        value = rows[0] if len(rows)==1 else None
        if value is None:
            raise HTTPException(404, detail={'code':'NATIVE_INSTRUMENT_NOT_FOUND'})
        return value

    @app.get('/api/v1/market-data/health')
    def health():
        current = {p:collector_state(archive,p) for p in ('binance','upstox','alpaca')}
        snapshots,checked_at = {},{}
        for provider in ('binance','upstox','alpaca'):
            manifest = archive.last_manifest('catalog',provider)
            snapshots[provider] = manifest['manifest_hash'] if manifest else None
            checks = [m['observed_at'] for m in archive.manifests('requests',provider)
                      if m['metadata'].get('operation')=='catalog_check' and
                      m['metadata'].get('catalog_snapshot')==snapshots[provider]]
            checked_at[provider] = max([manifest['observed_at'],*checks]) if manifest else None
        return {'status':'INDEPENDENT_TEST', 'owner_connected':False, 'database_access':False,
                'owner_background_collection_enabled':False,
                'collector_modes':{p:r.get('mode','legacy_bounded_capture') if r else 'UNAVAILABLE' for p,r in current.items()},
                'snapshots':snapshots,'catalog_checked_at':checked_at}

    @app.get('/api/v1/market-data/catalog')
    def catalog(provider: str | None = None, market: str | None = None, query: str = '', exchange: str | None = None,
                status: str | None = None, include_absent: bool = False, offset: int = Query(0, ge=0),
                limit: int = Query(50, ge=1, le=200), snapshot: str | None = None):
        if provider and provider not in {'binance','upstox','alpaca'}:
            raise ProviderFailure('UNKNOWN_PROVIDER')
        return search_catalog(archive, provider=provider, market=market, query=query, exchange=exchange,
                              status=status, include_absent=include_absent, offset=offset, limit=limit, snapshot=snapshot)

    @app.get('/api/v1/market-data/history')
    def history_read(provider: str, native_id: str, start: datetime, end: datetime, interval: str = '1d',
                     as_of: datetime | None = None, offset: int = Query(0, ge=0), limit: int = Query(2000, ge=1, le=5000)):
        if interval not in INTERVALS:
            raise ProviderFailure('UNSUPPORTED_INTERVAL')
        try:
            start, end = utc(start), utc(end)
            as_of = utc(as_of) if as_of else None
        except ValueError:
            raise ProviderFailure('AWARE_TIMESTAMPS_REQUIRED') from None
        if start >= end:
            raise ProviderFailure('INVALID_HISTORY_RANGE')
        value = instrument(provider, native_id)
        records = cached_candles(archive, provider, native_id, interval, start, end, as_of=as_of)
        return {'items':records[offset:offset+limit], 'total':len(records),
                'next_offset':offset+limit if offset+limit < len(records) else None,
                'state':'HISTORICAL' if records else 'UNAVAILABLE', 'provider':provider,
                'symbol':value['symbol'], 'interval':interval, 'as_of':as_of.isoformat() if as_of else None,
                'available_intervals':list(INTERVALS), 'canonical_status':'INDEPENDENT_NATIVE_SOURCE_EVIDENCE'}

    @app.post('/api/v1/market-data/history/fetch')
    def history_fetch(body: HistoryRequest):
        if fetch_scope is not None:
            fetch_scope.require(body.provider,body.native_id,body.interval,body.start,body.end)
        if not history_lock.acquire(blocking=False):
            raise ProviderFailure('HISTORY_REQUEST_BUSY', retryable=True)
        try:
            return service.fetch(instrument(body.provider, body.native_id), body.interval, body.start, body.end)
        finally:
            history_lock.release()

    @app.get('/api/v1/market-data/prices')
    def prices(provider: str, native_id: str | None = None):
        if provider not in {'binance','upstox','alpaca'}:
            raise ProviderFailure('UNKNOWN_PROVIDER')
        current = collector_state(archive,provider)
        if current is None:
            return {'items':[], 'state':'UNAVAILABLE', 'reason':'COLLECTOR_NOT_RUNNING_OR_NO_OBSERVATIONS'}
        now = datetime.now(timezone.utc)
        heartbeat_fresh = (now-datetime.fromisoformat(current['updated_at'])).total_seconds() < 30
        connected = current['stats']['connected'] and heartbeat_fresh
        return {'items':[{**r,'state':display_state(r, now=now, connected=connected)} for r in current['items']
                         if native_id is None or r['native_id'] == native_id],
                'connected':connected, 'stats':current['stats'], 'updated_at':current['updated_at']}

    return app
