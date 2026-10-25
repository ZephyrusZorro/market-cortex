"""Hermetic safety/recovery checks; never evidence of authenticated broker access."""
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch
import asyncio
import gzip
import json

import httpx
import pytest
from fastapi.testclient import TestClient

from market_cortex.market_archive import MarketArchive
from market_cortex.market_data_app import create_market_app
from market_cortex.market_data_cli import recovery
from market_cortex.market_history import HistoryService, cached_candles, next_boundary, subtract_ranges
from market_cortex.market_stream import FeedWorker, SubscriptionPool, approved_socket, decode_events, display_state, collector_state
from market_cortex.market_universe import normalize, search_catalog, sync_catalog, upstox_file
from market_cortex.providers import Page, ProviderFailure, ReadTransport

NOW = datetime(2026,10,11,12,tzinfo=timezone.utc)
START = NOW.replace(day=10,hour=0)
END = NOW.replace(hour=0)


def raw_symbol(symbol='ADAUSDT', status='TRADING'):
    return {'symbol':symbol,'status':status,'baseAsset':'ADA','quoteAsset':'USDT','isSpotTradingAllowed':True,
            'baseAssetPrecision':8,'quoteAssetPrecision':8,'filters':[{'filterType':'PRICE_FILTER','tickSize':'0.00001'}]}


def native():
    return normalize('binance',[raw_symbol()],START.isoformat())[0]


def candle(at=START, close='2'):
    return [int(at.timestamp()*1000),'1','3','0.5',close,'100',int((at+timedelta(days=1)).timestamp()*1000)-1]


class FakeTransport:
    def __init__(self, data):
        self.data, self.calls = data, []
    def get(self, host, path, **kwargs):
        self.calls.append((host,path,kwargs))
        data = self.data(host,path,kwargs) if callable(self.data) else self.data
        return Page(data,'a'*64,200)


@pytest.fixture
def archive(tmp_path):
    return MarketArchive(tmp_path/'source',initialize=True)


def test_full_catalog_lifecycle_and_pinned_pagination(archive):
    first = sync_catalog(archive,'binance',FakeTransport({'symbols':[raw_symbol(),raw_symbol('DOTUSDT')]}))
    found = search_catalog(archive,provider='binance',query='dot',limit=1)
    assert found['items'][0]['symbol']=='DOTUSDT' and not found['history_downloaded_by_discovery']
    second = sync_catalog(archive,'binance',FakeTransport({'symbols':[raw_symbol(status='BREAK')]}))
    assert second['metadata']['changes']=={'added':0,'changed':1,'absent':1}
    absent = search_catalog(archive,provider='binance',include_absent=True,query='DOT')['items'][0]
    assert absent['status']=='ABSENT_FROM_CURRENT_SOURCE' and not absent['present']
    pinned = search_catalog(archive,provider='binance',snapshot=first['manifest_hash'],query='DOT')
    assert pinned['items'][0]['present']
    assert archive.integrity()['status']=='VALIDATED'


def test_both_indian_exchanges_and_suspension_are_distinct(archive):
    def fetch(name):
        exchange='BSE' if name=='BSE' else 'NSE'
        row={'instrument_key':exchange+'_EQ|INE000A01010','trading_symbol':'SAME','name':'Same company',
             'isin':'INE000A01010','segment':exchange+'_EQ','instrument_type':'EQ','exchange':exchange,'exchange_token':'123'}
        return [row],{'sha256':'b'*64,'endpoint':name}
    manifest = sync_catalog(archive,'upstox',public_fetch=fetch)
    rows = archive.rows(manifest)
    assert len(rows)==2 and {r['exchange'] for r in rows}=={'NSE','BSE'}
    assert rows[1]['status']=='CONFLICTING_LISTED_AND_SUSPENDED'
    assert all(r['canonical_identity']=='UNVERIFIED_NATIVE_DISCOVERY' for r in rows)


def test_us_assets_all_statuses_and_missing_credentials(archive,monkeypatch):
    monkeypatch.delenv('APCA_API_KEY_ID',raising=False)
    with pytest.raises(ProviderFailure,match='NOT_CONFIGURED'):
        sync_catalog(archive,'alpaca')
    monkeypatch.setenv('APCA_API_KEY_ID','private-key')
    monkeypatch.setenv('APCA_API_SECRET_KEY','private-secret')
    fake=FakeTransport(lambda h,p,k:[{'id':k['params']['status'],'symbol':k['params']['status'].upper(),
        'name':'asset','exchange':'NASDAQ','class':'us_equity','status':k['params']['status'],
        'tradable':True,'attributes':[]}])
    manifest=sync_catalog(archive,'alpaca',fake)
    assert manifest['rows']==2 and all(c[0]=='paper-api.alpaca.markets' for c in fake.calls)
    assert {c[2]['params']['status'] for c in fake.calls}=={'active','inactive'}
    assert 'private-key' not in json.dumps(manifest)


def test_streamed_gzip_catalog_excludes_derivatives():
    body=gzip.compress(json.dumps([{'segment':'NSE_FO'}, {'segment':'NSE_EQ','name':'real'}]).encode())
    client=httpx.Client(transport=httpx.MockTransport(lambda request:httpx.Response(200,content=body)))
    records, source=upstox_file('NSE',client)
    assert len(records)==1 and source['source_records']==2 and source['compressed_bytes']==len(body)
    with pytest.raises(ProviderFailure,match='ENDPOINT_NOT_ALLOWED'):
        upstox_file('../orders',client)


def test_candle_cache_idempotence_correction_and_asof(archive):
    fake=FakeTransport([candle()])
    service=HistoryService(archive,fake,now=NOW)
    first=service.fetch(native(),'1d',START,END)
    second=service.fetch(native(),'1d',START,END)
    assert first['new_revisions']==1 and second['cache_hit'] and len(fake.calls)==1
    repeated=service.fetch(native(),'1d',START,END,refresh=True)
    assert repeated['new_revisions']==0
    fake.data=[candle(close='2.5')]
    service.now=NOW+timedelta(minutes=1)
    changed=service.fetch(native(),'1d',START,END,refresh=True)
    assert changed['new_revisions']==1 and changed['items'][0]['close']=='2.5'
    old=cached_candles(archive,'binance','ADAUSDT','1d',START,END,as_of=NOW)
    assert old[0]['close']=='2'
    assert len(archive.manifests('candles','binance'))==2


def test_partitioned_reads_preserve_legacy_revisions_asof_and_hash_checks(archive):
    service=HistoryService(archive,FakeTransport([candle()]),now=NOW)
    service.fetch(native(),'1d',START,END)
    original=cached_candles(archive,'binance','ADAUSDT','1d',START,END)[0]
    # A metadata-free legacy capture must participate in correction/replay.
    corrected={**original,'close':'2.5','available_at':(NOW+timedelta(minutes=1)).isoformat()}
    archive.append('candles','binance',[corrected],sources=[],observed_at=corrected['available_at'])
    unrelated=archive.append('candles','binance',[{**original,'native_id':'DOTUSDT'}],sources=[],
                             metadata={'native_id':'DOTUSDT','interval':'1d'},
                             observed_at=(NOW+timedelta(minutes=2)).isoformat())
    with patch.object(archive,'rows',wraps=archive.rows) as reads:
        assert cached_candles(archive,'binance','ADAUSDT','1d',START,END)[0]['close']=='2.5'
        assert unrelated['manifest_hash'] not in {call.args[0]['manifest_hash'] for call in reads.call_args_list}
    assert cached_candles(archive,'binance','ADAUSDT','1d',START,END,as_of=NOW)[0]['close']=='2'
    # Relevant files continue to be reverified on every read; no hash cache.
    relevant=archive.manifests('candles','binance')[0]
    (archive.root/relevant['artifact']).write_bytes(b'tampered')
    with pytest.raises(ProviderFailure,match='ARTIFACT_HASH_MISMATCH'):
        cached_candles(archive,'binance','ADAUSDT','1d',START,END)


def test_exact_catalog_lookup_is_not_substring_and_includes_absent_evidence(archive):
    sync_catalog(archive,'binance',FakeTransport({'symbols':[raw_symbol('BTCUSDT'),raw_symbol('WBTCUSDT')]}))
    assert [r['native_id'] for r in search_catalog(archive,provider='binance',native_id='BTCUSDT')['items']]==['BTCUSDT']
    sync_catalog(archive,'binance',FakeTransport({'symbols':[raw_symbol('WBTCUSDT')]}))
    assert not search_catalog(archive,provider='binance',native_id='BTCUSDT')['items']
    assert search_catalog(archive,provider='binance',native_id='BTCUSDT',include_absent=True)['items'][0]['status']=='ABSENT_FROM_CURRENT_SOURCE'


def test_cold_empty_cache_unsafe_candles_and_page_budget(archive):
    service=HistoryService(archive,FakeTransport([]),now=NOW)
    assert service.fetch(native(),'1d',START,END)['state']=='UNAVAILABLE'
    assert service.fetch(native(),'1d',START,END)['cache_hit']
    with pytest.raises(ProviderFailure,match='INVALID_PROVIDER_CANDLE'):
        HistoryService(archive,FakeTransport([candle(close='999')]),now=NOW).fetch(native(),'1d',START,END,refresh=True)
    with pytest.raises(ProviderFailure,match='HISTORY_CALL_BUDGET'):
        HistoryService(archive,FakeTransport([]),now=NOW,max_pages=0).fetch(native(),'1d',START,END,refresh=True)
    assert not archive.manifests('candles','binance')


def test_no_in_progress_daily_bars(archive):
    fake=FakeTransport([candle(NOW.replace(hour=0))])
    result=HistoryService(archive,fake,now=NOW).fetch(native(),'1d',NOW.replace(hour=0),NOW)
    assert result['items']==[]


def test_binance_finalization_grace_and_one_time_legacy_tail_reconciliation(archive):
    early=END+timedelta(seconds=1)
    fake=FakeTransport([candle()])
    service=HistoryService(archive,fake,now=early)
    assert service.fetch(native(),'1d',START,END)['items']==[]
    assert not archive.manifests('candles','binance')
    service.now=END+timedelta(seconds=11)
    assert service.fetch(native(),'1d',START,END)['new_revisions']==1
    # Simulate the earlier implementation's immediate-boundary observation.
    old=cached_candles(archive,'binance','ADAUSDT','1d',START,END)[0]
    legacy_archive=MarketArchive(archive.root.parent/'legacy',initialize=True)
    legacy={**old,'native_id':'LEGACYUSDT','symbol':'LEGACYUSDT','available_at':early.isoformat(),'close':'2.5'}
    legacy_archive.append('candles','binance',[legacy],sources=[],metadata={'native_id':'LEGACYUSDT','interval':'1d'},
                   observed_at=early.isoformat())
    legacy_archive.append('requests','binance',[],sources=[],metadata={'native_id':'LEGACYUSDT','interval':'1d',
        'feed':'spot_public','start':START.isoformat(),'end':END.isoformat(),'closed_coverage_end':END.isoformat(),
        'returned_rows':1},observed_at=early.isoformat())
    service=HistoryService(legacy_archive,fake,now=NOW)
    item={**native(),'native_id':'LEGACYUSDT','symbol':'LEGACYUSDT'}
    fixed=service.fetch(item,'1d',START,END)
    assert fixed['provider_calls']==1 and fixed['new_revisions']==1 and fixed['items'][0]['close']=='2'
    assert service.fetch(item,'1d',START,END)['provider_calls']==0
    assert cached_candles(legacy_archive,'binance','LEGACYUSDT','1d',START,END,as_of=early)[0]['close']=='2.5'


def test_calendar_timezone_dst_and_range_subtraction():
    before=datetime(2026,3,8,5,tzinfo=timezone.utc)
    assert next_boundary(before,'1d','America/New_York')==datetime(2026,3,9,4,tzinfo=timezone.utc)
    assert subtract_ranges(START,END,[(START+timedelta(hours=3),START+timedelta(hours=5))])==[
        (START,START+timedelta(hours=3)),(START+timedelta(hours=5),END)]


def test_owner_lake_isolation_and_tamper(archive,tmp_path):
    protected=tmp_path/'owner'; (protected/'lake').mkdir(parents=True)
    with pytest.raises(ProviderFailure,match='PROTECTED_MARKET_LAKE'):
        MarketArchive(protected/'child',initialize=True)
    manifest=archive.append('events','binance',[{'sample':'test'}],sources=[])
    path=archive.root/manifest['artifact'];path.write_bytes(b'changed')
    with pytest.raises(ProviderFailure,match='ARTIFACT_HASH_MISMATCH'):
        archive.integrity()


def ticker(now=NOW):
    return json.dumps({'e':'24hrMiniTicker','s':'ADAUSDT','E':int(now.timestamp()*1000),'c':'2'})


def test_public_stream_decode_no_fake_fallback_dedup_and_freshness(archive):
    event=decode_events('binance',ticker(),[native()],received_at=NOW)[0]
    assert event['price']=='2' and event['source_timestamp']==str(int(NOW.timestamp()*1000))
    worker=FeedWorker(archive,'binance',[native()]);worker.accept([event,event]);worker.flush()
    assert worker.stats['events']==1 and worker.stats['duplicates']==1
    assert display_state(None,now=NOW)=='UNAVAILABLE'
    assert display_state(event,now=NOW)=='LIVE'
    assert display_state(event,now=NOW+timedelta(minutes=1))=='STALE'
    assert display_state({**event,'event_at':(NOW-timedelta(minutes=15)).isoformat(),'delay_seconds':900},now=NOW)=='DELAYED'
    assert display_state(event,now=NOW,connected=False)=='STALE'


def test_shared_subscriptions_enforce_free_plan_limit():
    pool=SubscriptionPool('alpaca')
    assert pool.set('chart',['AAPL'])==['AAPL']
    assert pool.set('watchlist',['AAPL','MSFT'])==['AAPL','MSFT']
    assert pool.remove('chart')==['AAPL','MSFT']
    with pytest.raises(ProviderFailure,match='SUBSCRIPTION_LIMIT'):
        pool.set('oversize',[str(i) for i in range(31)])


def test_upstox_binary_wire_schema_and_signed_url_boundary(monkeypatch):
    from market_cortex.feed_proto.MarketDataFeed_pb2 import FeedResponse
    message=FeedResponse();message.currentTs=int(NOW.timestamp()*1000)
    message.feeds['NSE_EQ|INE000A01010'].ltpc.ltp=100
    message.feeds['NSE_EQ|INE000A01010'].ltpc.ltt=int(NOW.timestamp()*1000)
    item={**native(),'provider':'upstox','native_id':'NSE_EQ|INE000A01010','symbol':'SAMPLE','status':'LISTED'}
    assert decode_events('upstox',message.SerializeToString(),[item],received_at=NOW)[0]['price']=='100.0'
    monkeypatch.setenv('UPSTOX_ACCESS_TOKEN','secret')
    with pytest.raises(ProviderFailure,match='FEED_DESTINATION_NOT_ALLOWED'):
        approved_socket('upstox',[item],transport=FakeTransport({'data':{'authorized_redirect_uri':'wss://upstox.com.evil.example/market-data-feeder/v3/x?code=secret'}}))


def test_alpaca_quote_is_not_a_fabricated_trade_price():
    item={**native(),'provider':'alpaca','native_id':'asset-id','symbol':'AAPL'}
    payload=json.dumps([{'T':'q','S':'AAPL','t':NOW.isoformat(),'bp':100,'ap':101}])
    event=decode_events('alpaca',payload,[item],received_at=NOW)[0]
    assert event['price'] is None and event['bid']=='100' and event['ask']=='101'


def test_api_cache_is_read_only_and_fetch_bounded(archive):
    sync_catalog(archive,'binance',FakeTransport({'symbols':[raw_symbol()]}))
    service=HistoryService(archive,FakeTransport([candle()]),now=NOW)
    client=TestClient(create_market_app(archive,service))
    params={'provider':'binance','native_id':'ADAUSDT','interval':'1d','start':START.isoformat(),'end':END.isoformat()}
    assert client.get('/api/v1/market-data/history',params=params).json()['state']=='UNAVAILABLE'
    assert service.transport.calls==[]
    assert client.post('/api/v1/market-data/history/fetch',json=params).json()['new_revisions']==1
    assert client.get('/api/v1/market-data/history',params=params).json()['total']==1
    assert client.get('/api/v1/market-data/health').json()['owner_connected'] is False
    assert client.post('/api/v1/market-data/history/fetch',json=params,headers={'Origin':'https://evil.example'}).status_code==403
    assert client.post('/api/v1/orders',json={}).status_code==404


def test_extended_transport_still_get_only():
    requests=[]
    transport=ReadTransport(httpx.Client(transport=httpx.MockTransport(lambda r:requests.append(r) or httpx.Response(200,json=[]))))
    transport.get('paper-api.alpaca.markets','/v2/assets')
    with pytest.raises(ProviderFailure,match='ENDPOINT_NOT_ALLOWED'):
        transport.get('paper-api.alpaca.markets','/v2/orders')
    with pytest.raises(ProviderFailure,match='ENDPOINT_NOT_ALLOWED'):
        transport.get('api.upstox.com','/v2/order/place')
    assert all(r.method=='GET' for r in requests)


def test_stream_failure_retains_gap_and_bounded_retry(archive):
    class Broken:
        def __call__(self,*args,**kwargs):
            raise OSError('private network details must not escape')
    worker=FeedWorker(archive,'binance',[native()],connector=Broken(),max_retries=0)
    stats=asyncio.run(worker.run(1))
    assert stats['last_error']=='STREAM_RETRY_BUDGET_EXHAUSTED' and stats['events']==0
    assert archive.manifests('gaps','binance')
    assert not (archive.root/'.collector-binance.lock').exists()


def test_current_forming_bar_is_never_hidden_by_request_cache(archive):
    minute=NOW.replace(minute=0,second=0)
    rows=lambda h,p,k:[[int(minute.timestamp()*1000),'1','3','0.5','2','100',
        int((minute+timedelta(minutes=1)).timestamp()*1000)-1]]
    transport=FakeTransport(rows)
    service=HistoryService(archive,transport,now=minute+timedelta(seconds=30))
    assert not service.fetch(native(),'1m',minute,minute+timedelta(seconds=30))['items']
    service.now=minute+timedelta(minutes=1,seconds=30)
    result=service.fetch(native(),'1m',minute,minute+timedelta(minutes=1,seconds=30))
    # Empty sample retry expires after one minute, then captures the genuine closed bar.
    assert len(result['items'])==1


def test_checkpoint_does_not_replace_windows_open_file(archive,monkeypatch):
    worker=FeedWorker(archive,'binance',[native()])
    event=decode_events('binance',ticker(),[native()],received_at=NOW)[0]
    monkeypatch.setattr('market_cortex.market_stream.os.replace',lambda *a: (_ for _ in ()).throw(PermissionError('Windows reader denies delete sharing')))
    worker.accept([event]);worker.flush()
    first=collector_state(archive,'binance')
    worker.flush()
    assert collector_state(archive,'binance')['stats']['events']==1
    assert first['items'][0]['price']=='2'


def test_duplicate_observation_across_packet_grouping(archive):
    worker=FeedWorker(archive,'binance',[native()])
    event=decode_events('binance',ticker(),[native()],received_at=NOW)[0]
    worker.accept([event,{**event,'source_hash':'b'*64,'received_at':(NOW+timedelta(seconds=1)).isoformat()}])
    assert worker.stats['events']==1 and worker.stats['duplicates']==1


def test_canonical_bridge_preserves_daily_record_keys_and_requires_identity(archive):
    from market_cortex.market_canonical import canonical_bars
    from test_foundation import identity,calendar
    samples=HistoryService(archive,FakeTransport([candle()]),now=NOW).fetch(native(),'1d',START,END)['items']
    instrument,mapping=identity(native='ADAUSDT')
    result=canonical_bars(samples,instrument,mapping,calendar())
    assert result[0].envelope.provider_record_id==f'ADAUSDT:{int(START.timestamp()*1000)}'
    assert result[0].interval=='P1D' and result[0].close==Decimal('2')
    with pytest.raises(ProviderFailure,match='VERIFIED_MAPPING_MISMATCH'):
        canonical_bars(samples,instrument,mapping.model_copy(update={'identifier_value':'BTCUSDT'}),calendar())
