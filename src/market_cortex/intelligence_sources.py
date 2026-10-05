"""Bounded public GET adapters on the foundation's endpoint allowlist."""
import time
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Protocol
from uuid import UUID, NAMESPACE_URL, uuid4, uuid5

from .contracts import IdentifierMapping, Instrument, ObservationEnvelope, Venue
from .database import connect
from .intelligence_contracts import DerivativeContract, DerivativeObservation, EconomicObservation, EntityRef, SourceCapability
from .intelligence_store import ContextStore
from .providers import ReadTransport, ProviderFailure
from .market_state import PILOT_SYMBOLS


class ContextProvider(Protocol):
    provider_id: str
    def fetch(self, catalog, **kwargs) -> list: ...


class CachedTransport:
    """Process-local TTL and minimum spacing; foundation bounds retries/bytes/redirects."""
    def __init__(self, transport=None):
        self.transport = transport or ReadTransport()
        self.cache = {}
        self.last_request = 0.
    def get(self, host, path, params=None):
        key = (host, path, tuple(sorted((params or {}).items())))
        now = time.monotonic()
        ttl = 3600 if path.endswith('exchangeInfo') else 60
        if key in self.cache and now-self.cache[key][0] < ttl:
            return self.cache[key][1]
        time.sleep(max(0., .3-(now-self.last_request)))
        page = self.transport.get(host, path, params=params)
        self.last_request = time.monotonic()
        self.cache[key] = (self.last_request, page)
        return page


def envelope(provider, event_at, arrived, page, *, instrument_id=None, series_id=None, unit, record, source_ref, currency=None):
    return ObservationEnvelope(observation_id=uuid4(), instrument_id=instrument_id, series_id=series_id,
        venue_id='BINANCE_USDM' if provider == 'binance_usdm' else 'US_TREASURY', provider_id=provider,
        provider_record_id=record, event_at=event_at, published_at=None, available_at=arrived,
        availability_basis='observed_arrival', ingested_at=arrived, timestamp_precision='millisecond' if instrument_id else 'date',
        is_final=True, quality_state='valid', freshness_policy_id='context_v1', validation_codes=[],
        source_ref=source_ref, source_batch_id=uuid4(), raw_content_hash=page.content_hash,
        raw_retention_state='hash_only', normalizer_version='phase9_public_v1', license_policy_id='public_api_metadata_hash_only',
        unit=unit, adjustment_basis='raw', currency=currency)


def ms(value):
    return datetime.fromtimestamp(int(value)/1000, timezone.utc)


class BinanceDerivatives:
    provider_id = 'binance_usdm'
    def __init__(self, transport=None):
        self.transport = transport or CachedTransport()
    def fetch(self, catalog, *, symbols=('BTCUSDT',), funding_limit=90):
        if not symbols or len(symbols) > 5 or len(set(symbols)) != len(symbols) or any(s not in PILOT_SYMBOLS for s in symbols) or not 1 <= funding_limit <= 1000:
            raise ValueError('BOUNDED_PILOT_DERIVATIVES_REQUIRED')
        info = self.transport.get('fapi.binance.com', '/fapi/v1/exchangeInfo')
        metadata = info.data.get('symbols', [])
        instruments, mappings = catalog.load_identity()
        facts = []
        for symbol in symbols:
            rows = [r for r in metadata if r.get('symbol') == symbol and r.get('contractType') == 'PERPETUAL' and
                    r.get('quoteAsset') == 'USDT' and r.get('marginAsset') == 'USDT' and r.get('status') == 'TRADING']
            underlying = [m for m in mappings if m.provider_id == 'binance' and m.venue_id == 'BINANCE_SPOT' and
                          m.identifier_value == symbol and m.available_at and m.available_at <= datetime.now(timezone.utc) and m.valid_to is None]
            if len(rows) != 1 or len({m.instrument_id for m in underlying}) != 1:
                raise ProviderFailure('VERIFIED_NATIVE_CONTRACT_UNDERLYING_REQUIRED')
            row = rows[0]
            native_key = f'binance_usdm:BINANCE_USDM:PERPETUAL:{symbol}:USDT'
            iid = uuid5(NAMESPACE_URL, native_key)
            known = datetime.now(timezone.utc)
            previous = [i for i in instruments if i.instrument_id == iid]
            native = [m for m in mappings if m.instrument_id == iid and m.provider_id == self.provider_id]
            if not previous:
                instrument = Instrument(instrument_id=iid, asset_class='perpetual', instrument_kind='linear_usdt_perpetual',
                    primary_venue_id='BINANCE_USDM', trading_currency='USDT', price_unit='USDT', quantity_unit=row['baseAsset'],
                    listing_status='active', valid_from=ms(row['onboardDate']), underlying_instrument_id=underlying[0].instrument_id)
                mapping = IdentifierMapping(mapping_id=uuid5(NAMESPACE_URL, native_key+':mapping'), instrument_id=iid,
                    provider_id=self.provider_id, venue_id='BINANCE_USDM', identifier_type='contract_code', identifier_value=symbol,
                    valid_from=instrument.valid_from, available_at=known)
                catalog.register_identity([Venue(venue_id='BINANCE_USDM', timezone='UTC', session_kind='24x7')], [instrument], [mapping])
            else:
                if len(native) != 1 or previous[0].underlying_instrument_id != underlying[0].instrument_id or previous[0].quantity_unit != row['baseAsset']:
                    raise ProviderFailure('CONTRACT_METADATA_CONFLICT')
                known = native[0].available_at
            contract = DerivativeContract(instrument_id=iid, underlying_instrument_id=underlying[0].instrument_id,
                provider=self.provider_id, venue='BINANCE_USDM', native_id=symbol, contract_type='PERPETUAL',
                base_asset=row['baseAsset'], quote_currency='USDT', margin_currency='USDT', quantity_unit=row['baseAsset'],
                identity_version='binance_usdm_native_v1', known_at=known,
                metadata_source_ref='https://fapi.binance.com/fapi/v1/exchangeInfo',
                metadata_raw_hash=info.content_hash, metadata_observed_at=datetime.now(timezone.utc))
            entity = EntityRef(kind='instrument', key=str(iid), mapping_version=contract.identity_version)
            for kind, path, params in (
                ('funding', '/fapi/v1/fundingRate', {'symbol': symbol, 'limit': funding_limit}),
                ('open_interest', '/futures/data/openInterestHist', {'symbol': symbol, 'period': '1d', 'limit': 30}),
                ('mark_index', '/fapi/v1/premiumIndex', {'symbol': symbol})):
                page = self.transport.get('fapi.binance.com', path, params)
                arrived = datetime.now(timezone.utc)
                records = page.data if isinstance(page.data, list) else [page.data]
                if not records or len(records) > 1000:
                    raise ProviderFailure('EMPTY_OR_OVERSIZED_DERIVATIVES_RESPONSE')
                for r in records:
                    if r.get('symbol') != symbol:
                        raise ProviderFailure('NATIVE_SYMBOL_MISMATCH')
                    event = ms(r['fundingTime'] if kind == 'funding' else r['timestamp'] if kind == 'open_interest' else r['time'])
                    if event > arrived + timedelta(seconds=5):
                        raise ProviderFailure('FUTURE_PROVIDER_TIMESTAMP')
                    unit = 'fraction_per_funding_event' if kind == 'funding' else contract.quantity_unit if kind == 'open_interest' else 'USDT'
                    value = r['fundingRate'] if kind == 'funding' else r['sumOpenInterest'] if kind == 'open_interest' else r['markPrice']
                    companion = r.get('sumOpenInterestValue') if kind == 'open_interest' else r.get('indexPrice') if kind == 'mark_index' else None
                    facts.append(DerivativeObservation(envelope=envelope(self.provider_id, event, arrived, page,
                        instrument_id=iid, unit=unit, record=f'{symbol}:{kind}:{event.isoformat()}',
                        source_ref=f'https://fapi.binance.com{path}', currency='USDT'), entity=entity,
                        related_instrument_ids=[contract.underlying_instrument_id], logical_key=f'{native_key}:{kind}:{event.isoformat()}',
                        kind=kind, contract=contract, metric=kind, value=Decimal(value),
                        companion_value=Decimal(companion) if companion else None, companion_unit='USDT' if companion else None,
                        mark_price=Decimal(r['markPrice']) if kind == 'funding' and r.get('markPrice') else None,
                        interval='1d' if kind == 'open_interest' else None))
        return facts


class TreasuryMacro:
    provider_id = 'us_treasury'
    def __init__(self, transport=None):
        self.transport = transport or CachedTransport()
    def fetch(self, catalog=None, *, months=24):
        if not 1 <= months <= 60:
            raise ValueError('MACRO_HISTORY_BOUND')
        path = '/services/api/fiscal_service/v2/accounting/od/avg_interest_rates'
        page = self.transport.get('api.fiscaldata.treasury.gov', path,
            {'filter': 'security_desc:eq:Treasury Bills', 'sort': '-record_date', 'page[size]': months})
        arrived = datetime.now(timezone.utc)
        rows = page.data.get('data', [])
        if not rows or len(rows) > months:
            raise ProviderFailure('INVALID_TREASURY_RESPONSE')
        facts = []
        for r in rows:
            if r.get('security_desc') != 'Treasury Bills':
                raise ProviderFailure('TREASURY_SERIES_MISMATCH')
            end = date.fromisoformat(r['record_date'])
            if end > arrived.date():
                raise ProviderFailure('FUTURE_MACRO_PERIOD')
            series = 'US_TREASURY:AVG_INTEREST_RATE:TREASURY_BILLS'
            facts.append(EconomicObservation(envelope=envelope(self.provider_id,
                datetime.combine(end, datetime.min.time(), timezone.utc), arrived, page, series_id=series,
                unit='percent_per_annum', record=f'{series}:{end}', source_ref=f'https://api.fiscaldata.treasury.gov{path}'),
                entity=EntityRef(kind='series', key=series, mapping_version='treasury_avg_rates_v1'),
                logical_key=f'{series}:{end}', series_id=series, metric='average_interest_rate_on_outstanding_treasury_bills',
                value=Decimal(r['avg_interest_rate_amt']), region='US', frequency='monthly',
                seasonal_adjustment='not_applicable', period_start=end.replace(day=1), period_end=end))
        return facts


def coverage(store, cutoff):
    manifest = store.resolve(cutoff)
    facts = store.facts(manifest, cutoff)
    specifications = [
        ('binance_usdm', 'derivatives', 'UNAVAILABLE', 'none', ['BTCUSDT linear USDT perpetual; spot mapping required'], 'funding events / daily OI / current mark', 'funding up to 1000 bounded events; OI latest month',
         ['Arrival-only knowledge; no historical publication vintage', 'LIQUIDATIONS: UNAVAILABLE; no complete historical feed', 'OI quantity in base asset; value in USDT; never compared across contracts']),
        ('us_treasury', 'macro', 'UNAVAILABLE', 'none', ['US Treasury Bills average outstanding interest rate'], 'monthly', 'up to 60 monthly observations',
         ['Not a market yield curve, policy rate, or risk-free spot rate', 'Release and initial-vintage times unavailable: observed arrival only']),
        ('calendar', 'events', 'DEFERRED_DATA_SOURCE', 'not configured', [], 'source dependent', 'none', ['No verified live event calendar; absence is not event safety']),
        ('equity_sources', 'fundamentals', 'DEFERRED_NOT_CONFIGURED', 'environment credentials', [], 'quarterly / annual', 'fixtures only', ['Upstox/Alpaca credentials, verified equity mappings and calendars await configuration']),
        ('news_source', 'news', 'DEFERRED_DATA_SOURCE', 'not configured', [], 'source dependent', 'fixtures only', ['Metadata-only architecture; no licensed live news feed configured']),
        ('options_source', 'options', 'DEFERRED_DATA_SOURCE', 'not configured', [], 'source dependent', 'fixtures only', ['No verified live chain; no GEX, DEX or max-pain claims']),
        ('onchain_source', 'onchain', 'DEFERRED_DATA_SOURCE', 'not configured', [], 'source dependent', 'fixtures only', ['No verified free on-chain source configured'])]
    result = []
    for provider, domain, status, auth, covered, freq, depth, limits in specifications:
        live = [f for f in facts if f.domain == domain and f.envelope.provider_id == provider and f.classification_scope == 'LIVE_SOURCE']
        if live:
            status = 'PUBLIC_VALIDATED'
            if domain == 'derivatives':
                covered = sorted({f.contract.native_id+' linear USDT perpetual' for f in live})
        result.append(SourceCapability(provider=provider, domain=domain, status=status, authentication=auth,
            coverage=covered, frequency=freq, timestamp_semantics='published, available, ingested distinct; strict arrival replay',
            rate_constraints='cached 60s (metadata 1h), spacing 300ms; at most 3 bounded retries; response <=4MB',
            historical_depth=depth, limitations=limits, fact_count=len(live),
            live_validated_at=max((f.envelope.ingested_at for f in live), default=None),
            last_ingested_at=max((f.envelope.ingested_at for f in live), default=None)))
    return result
