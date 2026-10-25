"""Full provider-native discovery, separate from verified canonical identity."""
from __future__ import annotations

import gzip
import hashlib
import json
import os
import tempfile
import time
from datetime import datetime, timezone

import httpx
import ijson
import duckdb
import pyarrow.parquet as pq
from pydantic import BaseModel, ConfigDict, Field

from .market_archive import MarketArchive, digest, stamp
from .providers import NotConfigured, ProviderFailure, ReadTransport


class NativeInstrument(BaseModel):
    model_config = ConfigDict(extra='forbid')
    provider: str
    native_id: str = Field(min_length=1, max_length=120)
    symbol: str = Field(min_length=1, max_length=120)
    name: str = Field(max_length=300)
    market: str
    exchange: str
    segment: str
    instrument_type: str
    status: str
    present: bool = True
    isin: str | None = None
    base: str | None = None
    quote: str | None = None
    currency: str
    attributes: dict
    first_observed_at: str
    last_observed_at: str
    canonical_identity: str = 'UNVERIFIED_NATIVE_DISCOVERY'
    live_entitlement: str = 'UNKNOWN_REQUIRES_PROBE'


class PacedTransport(ReadTransport):
    """Provider-specific process-shared limits count every HTTP retry attempt."""
    def __init__(self, client=None):
        super().__init__(client, max_response_bytes=32_000_000)
    def before_attempt(self, host, path):
        from .market_rate_budget import budget_for
        budget_for(host).acquire()

    def observe_response(self, host, status, headers):
        from .market_rate_budget import budget_for
        if status in (418,429):
            value = headers.get('retry-after','')
            seconds = int(value) if value.isdigit() and len(value)<=6 else 60
            budget_for(host).cooldown(max(5,min(seconds,3600)))
        remaining = headers.get('x-ratelimit-remaining','')
        if remaining=='0':
            reset = headers.get('x-ratelimit-reset','')
            seconds = int(reset)-time.time() if reset.isdigit() and len(reset)<=12 else 60
            budget_for(host).cooldown(max(5,min(seconds,3600)))


def headers(provider):
    if provider == 'upstox':
        token = os.environ.get('UPSTOX_ACCESS_TOKEN')
        if not token:
            raise NotConfigured()
        return {'Authorization': 'Bearer ' + token}
    key, secret = os.environ.get('APCA_API_KEY_ID'), os.environ.get('APCA_API_SECRET_KEY')
    if not key or not secret:
        raise NotConfigured()
    return {'APCA-API-KEY-ID': key, 'APCA-API-SECRET-KEY': secret}


def safe_attributes(row):
    # Discovery responses must never persist an echoed authentication secret.
    value = json.loads(json.dumps(row, default=str))
    raw = json.dumps(value, ensure_ascii=False)
    if len(raw) > 20_000 or any(os.environ.get(n) and os.environ[n] in raw for n in (
            'UPSTOX_ACCESS_TOKEN', 'APCA_API_KEY_ID', 'APCA_API_SECRET_KEY', 'MARKET_CORTEX_DATABASE_URL')):
        raise ProviderFailure('UNSAFE_CATALOG_RECORD')
    return value


class LimitedReader:
    def __init__(self, stream, limit=350_000_000):
        self.stream, self.limit, self.count = stream, limit, 0

    def read(self, size=-1):
        value = self.stream.read(min(size, 65536) if size >= 0 else 65536)
        self.count += len(value)
        if self.count > self.limit:
            raise ProviderFailure('CATALOG_DECOMPRESSED_LIMIT')
        return value


def upstox_file(name, client=None):
    if name not in {'NSE', 'BSE', 'suspended-instrument'}:
        raise ProviderFailure('CATALOG_ENDPOINT_NOT_ALLOWED')
    client = client or httpx.Client(timeout=60, follow_redirects=False)
    # Stream the large derivatives-containing file; retain only cash segments.
    with tempfile.TemporaryFile() as stream:
        sha, total = hashlib.sha256(), 0
        try:
            with client.stream('GET', f'https://assets.upstox.com/market-quote/instruments/exchange/{name}.json.gz') as response:
                if response.status_code != 200:
                    raise ProviderFailure('PUBLIC_CATALOG_UNAVAILABLE', retryable=True)
                for chunk in response.iter_bytes():
                    total += len(chunk)
                    if total > 50_000_000:
                        raise ProviderFailure('CATALOG_COMPRESSED_LIMIT')
                    sha.update(chunk)
                    stream.write(chunk)
            stream.seek(0)
            selected, count = [], 0
            with gzip.GzipFile(fileobj=stream) as expanded:
                for row in ijson.items(LimitedReader(expanded), 'item', use_float=True):
                    count += 1
                    if count > 1_000_000:
                        raise ProviderFailure('CATALOG_RECORD_LIMIT')
                    if row.get('segment') in {'NSE_EQ', 'BSE_EQ'}:
                        selected.append(row)
            return selected, {'endpoint': f'upstox:public:{name}', 'sha256': sha.hexdigest(),
                              'compressed_bytes': total, 'source_records': count, 'cash_records': len(selected)}
        except ProviderFailure:
            raise
        except Exception:
            raise ProviderFailure('PUBLIC_CATALOG_FETCH_OR_PARSE_FAILED', retryable=True) from None


def normalize(provider, rows, observed_at, *, suspended=False):
    if provider == 'upstox' and suspended:
        grouped = {}
        for row in rows:
            grouped.setdefault(row['instrument_key'], []).append(row)
        rows = []
        for variants in grouped.values():
            primary = dict(sorted(variants, key=lambda r: (r.get('instrument_type',''),r.get('exchange_token','')))[0])
            primary['suspended_source_variants'] = variants
            rows.append(primary)
    result = []
    for row in rows:
        common = {'provider': provider, 'attributes': safe_attributes(row), 'first_observed_at': observed_at,
                  'last_observed_at': observed_at}
        if provider == 'binance':
            if row.get('isSpotTradingAllowed') is not True:
                continue
            item = dict(common, native_id=row['symbol'], symbol=row['symbol'], name=row['symbol'],
                        market='CRYPTO', exchange='BINANCE_SPOT', segment='SPOT', instrument_type='spot_pair',
                        status=row['status'], base=row['baseAsset'], quote=row['quoteAsset'], currency=row['quoteAsset'],
                        live_entitlement='PUBLIC_SPOT_SUBJECT_TO_AVAILABILITY')
        elif provider == 'upstox':
            if row.get('segment') not in {'NSE_EQ', 'BSE_EQ'}:
                continue
            item = dict(common, native_id=row['instrument_key'], symbol=row['trading_symbol'], name=row.get('name', ''),
                        market='INDIA', exchange=row['exchange'], segment=row['segment'], instrument_type=row['instrument_type'],
                        status='SUSPENDED' if suspended else 'LISTED', isin=row.get('isin'), currency='INR')
        else:
            if row.get('class') != 'us_equity':
                continue
            item = dict(common, native_id=row['id'], symbol=row['symbol'], name=row.get('name', ''), market='US',
                        exchange=row['exchange'], segment='US_EQUITY', instrument_type='equity_or_etf',
                        status=row['status'], currency='USD', live_entitlement='IEX_ONLY_REQUIRES_PROBE')
        result.append(NativeInstrument.model_validate(item).model_dump())
    if len({r['native_id'] for r in result}) != len(result):
        raise ProviderFailure('DUPLICATE_NATIVE_IDENTITY')
    return result


def sync_catalog(archive: MarketArchive, provider, transport=None, public_fetch=None):
    transport = transport or PacedTransport()
    observed, sources = stamp(), []
    if provider == 'binance':
        page = transport.get('data-api.binance.vision', '/api/v3/exchangeInfo')
        records = normalize(provider, page.data['symbols'], observed)
        sources.append({'endpoint': 'binance:spot:exchangeInfo', 'sha256': page.content_hash,
                        'rate_limits': page.data.get('rateLimits', [])})
    elif provider == 'upstox':
        fetch = public_fetch or upstox_file
        by_key = {}
        for name in ('NSE', 'BSE', 'suspended-instrument'):
            rows, source = fetch(name)
            sources.append(source)
            normalized = normalize(provider, rows, observed, suspended=name == 'suspended-instrument')
            for row in normalized:
                key = row['native_id']
                if name == 'suspended-instrument' and key in by_key:
                    listed = by_key[key]
                    variants = row['attributes']['suspended_source_variants']
                    # A suspended BE/BL/etc series must not deactivate a current EQ series.
                    listed['attributes']['suspended_source_variants'] = variants
                    if any(v.get('instrument_type') == listed['instrument_type'] and
                           str(v.get('exchange_token')) == str(listed['attributes'].get('exchange_token')) for v in variants):
                        listed['status'] = 'CONFLICTING_LISTED_AND_SUSPENDED'
                else:
                    by_key[key] = row
        records = list(by_key.values())
    elif provider == 'alpaca':
        auth = headers(provider)
        host = alpaca_asset_host()
        records = []
        for status in ('active', 'inactive'):
            page = transport.get(host, '/v2/assets', params={'status': status, 'asset_class': 'us_equity'}, headers=auth)
            if not isinstance(page.data, list):
                raise ProviderFailure('MALFORMED_ASSET_CATALOG')
            records.extend(normalize(provider, page.data, observed))
            sources.append({'endpoint': 'alpaca:assets:' + status, 'sha256': page.content_hash})
    else:
        raise ProviderFailure('UNKNOWN_PROVIDER')
    if not records:
        raise ProviderFailure('EMPTY_CATALOG_NOT_PUBLISHED')
    if len({r['native_id'] for r in records}) != len(records):
        raise ProviderFailure('DUPLICATE_NATIVE_IDENTITY')
    # Knowledge begins after responses and normalization complete, never at
    # the start of a potentially slow catalog request.
    observed = stamp()
    for row in records:
        row['first_observed_at'] = row['last_observed_at'] = observed
    previous, old = archive.latest('catalog', provider)
    by_id = {r['native_id']: r for r in records}
    changes = {'added': 0, 'changed': 0, 'absent': 0}
    old_by_id = {r['native_id']: r for r in old}
    for key, row in by_id.items():
        if key in old_by_id:
            row['first_observed_at'] = old_by_id[key]['first_observed_at']
            changes['changed'] += row['attributes'] != old_by_id[key]['attributes'] or not old_by_id[key]['present']
        else:
            changes['added'] += 1
    for key, row in old_by_id.items():
        if key not in by_id:
            # Absence is evidence of absence from this snapshot, not proof of delisting.
            by_id[key] = {**row, 'present': False, 'status': 'ABSENT_FROM_CURRENT_SOURCE'}
            changes['absent'] += 1
    def semantic(row):
        return {k:v for k,v in row.items() if k not in {'first_observed_at','last_observed_at'}}
    if previous and {k:semantic(r) for k,r in by_id.items()} == {k:semantic(r) for k,r in old_by_id.items()}:
        # Keep the old point-in-time catalog. A small immutable check receipt
        # records new source hashes/knowledge time without duplicating 70k rows.
        check = archive.append('requests',provider,[],sources=sources,observed_at=observed,
            metadata={'operation':'catalog_check','catalog_snapshot':previous['manifest_hash'],
                      'unchanged':True,'checked_at':observed})
        return {**previous,'catalog_check':{'unchanged':True,'checked_at':observed,
                                          'manifest_hash':check['manifest_hash']}}
    return archive.append('catalog', provider, sorted(by_id.values(), key=lambda r: r['native_id']),
                          sources=sources, metadata={'changes': changes, 'complete_current_provider_catalog': True,
                          'historical_delisting_archive': False, 'canonical_import': False}, observed_at=observed)


def alpaca_asset_host():
    mode = os.environ.get('MARKET_CORTEX_ALPACA_ACCOUNT', 'paper')
    if mode not in {'paper', 'live'}:
        raise ProviderFailure('INVALID_ALPACA_ACCOUNT_MODE')
    return 'paper-api.alpaca.markets' if mode == 'paper' else 'api.alpaca.markets'


def search_catalog(archive, *, provider=None, market=None, query='', exchange=None, status=None,
                   include_absent=False, offset=0, limit=50, snapshot=None, native_id=None):
    if not 1 <= limit <= 200 or offset < 0 or len(query) > 120:
        raise ProviderFailure('INVALID_CATALOG_QUERY')
    if snapshot and provider is None:
        raise ProviderFailure('SNAPSHOT_REQUIRES_PROVIDER')
    paths, hashes = [], {}
    for name in (provider,) if provider else ('binance', 'upstox', 'alpaca'):
        if snapshot:
            manifest = next((m for m in archive.manifests('catalog', name) if m['manifest_hash'] == snapshot), None)
            if not manifest:
                raise ProviderFailure('CATALOG_SNAPSHOT_NOT_FOUND')
        else:
            manifests = archive.manifests('catalog', name)
            manifest = manifests[-1] if manifests else None
        if manifest:
            hashes[name] = manifest['manifest_hash']
            paths.append(str(archive.artifact_path(manifest)))
    if not paths:
        return {'items':[], 'total':0, 'offset':offset, 'next_offset':None, 'snapshots':hashes,
                'history_downloaded_by_discovery':False}
    indexed = all('symbol' in pq.ParquetFile(p).schema.names for p in paths)
    def col(field):
        return field if indexed else f"json_extract_string(record_json, '$.{field}')"
    predicates, params = [], []
    for field, value in [('market',market),('exchange',exchange),('status',status),('native_id',native_id)]:
        if value:
            predicates.append(f"{col(field)} = ?")
            params.append(value)
    if not include_absent:
        predicates.append("present = true" if indexed else "json_extract_string(record_json, '$.present') = 'true'")
    if query:
        text = " || ' ' || ".join(f"coalesce({col(k)},'')" for k in ('symbol','name','native_id','isin'))
        predicates.append(f'contains(lower({text}), lower(?))')
        params.append(query)
    where = ' AND '.join(predicates) or 'true'
    # Scan bounded analytical files; do not inflate every JSON record in Python for each keystroke.
    with duckdb.connect(config={'memory_limit':'128MB' if indexed else '512MB','threads':'1','preserve_insertion_order':'false'}) as db:
        total = db.execute(f'SELECT count(*) FROM read_parquet(?) WHERE {where}',[paths,*params]).fetchone()[0]
        ordered = ','.join(col(k) for k in ('market','symbol','exchange','native_id'))
        found = db.execute(f'SELECT record_json FROM read_parquet(?) WHERE {where} ORDER BY {ordered} LIMIT ? OFFSET ?',
                           [paths,*params,limit,offset]).fetchall()
    items = [json.loads(r[0]) for r in found]
    return {'items': items, 'total': total, 'offset': offset,
            'next_offset': offset+limit if offset+limit < total else None, 'snapshots': hashes,
            'history_downloaded_by_discovery': False}
