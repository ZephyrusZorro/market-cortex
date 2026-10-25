"""Synthetic safety regressions; never broker/owner acceptance evidence."""
import json
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import httpx
import pytest

from market_cortex.market_archive import MarketArchive, publish, link_path
from pathlib import Path
from market_cortex.market_archive_bundle import assemble
from market_cortex.market_observation_audit import event_evidence, audit_probe
from market_cortex.market_rate_budget import RequestBudget, RequestPolicy, budget_for
from market_cortex.market_stream import decode_events, display_state
from market_cortex.market_universe import PacedTransport, sync_catalog
from market_cortex.providers import ProviderFailure


def event(kind='trade', age=1, delay=0, price='100', **values):
    received=datetime(2026,10,14,16,37,tzinfo=timezone.utc)
    return {'kind':kind,'received_at':received.isoformat(),
        'event_at':(received-timedelta(seconds=age)).isoformat(),
        'delay_seconds':delay,'price':price,**values}


def test_authenticated_stale_snapshot_does_not_prove_fresh_live_prices():
    result=event_evidence([event('last_trade_snapshot',age=21030)])
    assert result['observations_received']==1
    assert result['arrival_states']=={'STALE':1}
    assert not result['fresh_price_observations_received']
    assert not result['fresh_price_changes_observed']


def test_fresh_changes_delayed_quotes_and_closed_bar_start_are_distinct():
    rows=[event(age=2,price='100'),event(age=1,price='101'),
          event('quote',age=902,delay=900,price=None,bid='90',ask='91'),
          event('candle',age=62,price='99')]
    result=event_evidence(rows)
    assert result['arrival_states']=={'FRESH':2,'DELAYED':1}
    assert result['kinds']['candle']==1 and result['price_observations']==3
    assert result['fresh_price_changes_observed']
    assert result['fresh_price_range']==['100','101']


def test_fresh_snapshot_alone_does_not_prove_changing_prices():
    result=event_evidence([event('last_trade_snapshot')])
    assert result['fresh_price_observations_received']
    assert not result['fresh_price_changes_observed']


def test_future_clock_or_disconnected_receipt_cannot_be_live():
    row=event(age=-10)
    assert event_evidence([row])['arrival_states']=={'CLOCK_SKEW':1}
    assert display_state(row,now=datetime.fromisoformat(row['received_at']))=='STALE'
    assert display_state(event(),connected=False)=='STALE'


def test_alpaca_execution_and_quote_exchange_codes_are_not_listing_exchange():
    wire=json.dumps([{'T':'t','S':'AAPL','t':'2026-10-14T16:36:59Z','p':100,'x':'V','i':1},
                     {'T':'q','S':'AAPL','t':'2026-10-14T16:36:59Z','bp':99,'ap':101,'bx':'V','ax':'V'}])
    rows=decode_events('alpaca',wire,[{'native_id':'asset-aapl','symbol':'AAPL','exchange':'NASDAQ'}],
                       received_at=datetime(2026,10,14,16,37,tzinfo=timezone.utc))
    assert rows[0]['source_exchange']=='V'
    assert rows[1]['bid_exchange']==rows[1]['ask_exchange']=='V'
    assert rows[0]['source_exchange']!='NASDAQ'


class Clock:
    def __init__(self):self.now=0
    def __call__(self):return self.now
    def sleep(self,seconds):self.now+=seconds


def test_request_windows_shared_instances_and_bounded_wait():
    clock=Clock();budget=RequestBudget(RequestPolicy(((60,2),(1800,3)),1),clock=clock,sleep=clock.sleep)
    budget.acquire();budget.acquire()
    with pytest.raises(ProviderFailure,match='LOCAL_PROVIDER_RATE_BUDGET_EXHAUSTED'):
        budget.acquire()
    assert clock.now==1 and len(budget.attempts)==2
    clock.now=60;budget.acquire()
    clock.now=120
    with pytest.raises(ProviderFailure,match='LOCAL_PROVIDER_RATE_BUDGET_EXHAUSTED'):
        budget.acquire()
    assert budget_for('data.alpaca.markets') is budget_for('paper-api.alpaca.markets')
    assert budget_for('api.upstox.com') is not budget_for('data.alpaca.markets')


def test_every_network_retry_is_charged_and_429_stops_with_cooldown():
    clock=Clock();budget=RequestBudget(RequestPolicy(((60,60),),1),clock=clock,sleep=clock.sleep)
    calls=[]
    def handler(request):
        calls.append(request)
        return httpx.Response(503 if len(calls)==1 else 200,json=[])
    transport=PacedTransport(httpx.Client(transport=httpx.MockTransport(handler)))
    with patch('market_cortex.market_rate_budget.budget_for',return_value=budget),patch('market_cortex.providers.time.sleep'):
        assert transport.get('data.alpaca.markets','/v2/stocks/AAPL/bars').status==200
    assert len(calls)==len(budget.attempts)==2
    def limited(request):return httpx.Response(429,headers={'Retry-After':'60'})
    with patch('market_cortex.market_rate_budget.budget_for',return_value=budget),patch('market_cortex.providers.time.sleep'):
        with pytest.raises(ProviderFailure,match='LOCAL_PROVIDER_RATE_BUDGET_EXHAUSTED'):
            PacedTransport(httpx.Client(transport=httpx.MockTransport(limited))).get('data.alpaca.markets','/v2/stocks/AAPL/bars')
    assert budget.cooldown_until>=60


def test_forbidden_endpoint_never_consumes_budget_or_issues_network():
    with patch('market_cortex.market_rate_budget.budget_for') as gate:
        with pytest.raises(ProviderFailure,match='ENDPOINT_NOT_ALLOWED'):
            PacedTransport().get('api.alpaca.markets','/v2/orders')
        gate.assert_not_called()


def test_bundle_is_new_and_byte_exact_without_collector_state(tmp_path):
    sources={}
    for provider in ('binance','upstox','alpaca'):
        a=MarketArchive(tmp_path/provider,initialize=True)
        a.append('catalog',provider,[{'provider':provider,'native_id':'SAMPLE','symbol':'SAMPLE',
            'name':'Sample','exchange':'NATIVE','market':'NATIVE','status':'LISTED','present':True,'isin':None}],sources=[])
        (a.root/'collector').mkdir();(a.root/'collector'/'not-copied.json').write_text('{}')
        sources[provider]=a.root
    original={p:MarketArchive(root).latest('catalog',p)[0] for p,root in sources.items()}
    target=tmp_path/'new-bundle'
    result=assemble(sources,target)
    assert result['currently_live_subscriptions']==0 and not (target/'collector').exists()
    bundle=MarketArchive(target)
    for provider,old in original.items():
        new=bundle.latest('catalog',provider)[0]
        assert old==new
        assert bundle.artifact_path(new).read_bytes()==MarketArchive(sources[provider]).artifact_path(old).read_bytes()
    with pytest.raises(ProviderFailure,match='NEW_BUNDLE_DIRECTORY_REQUIRED'):
        assemble(sources,target)


def test_bundle_rejects_missing_or_protected_source_before_output(tmp_path):
    with pytest.raises(ProviderFailure,match='THREE_INDEPENDENT_PROVIDER_SOURCES_REQUIRED'):
        assemble({},tmp_path/'new')
    assert not (tmp_path/'new').exists()
    owner=tmp_path/'owner-private';owner.mkdir()
    with pytest.raises(ProviderFailure,match='PROTECTED_DATA_ROOT'):
        assemble({p:owner for p in ('binance','upstox','alpaca')},tmp_path/'new')
    assert not (tmp_path/'new').exists()


def test_content_addressed_publication_under_deep_windows_path(tmp_path):
    directory=tmp_path/('nested-'+'a'*75)/('nested-'+'b'*75)
    first=publish(directory,b'real bytes','.json')
    assert len(str(first.resolve()))>260
    assert Path(link_path(first)).read_bytes()==b'real bytes'
    assert publish(directory,b'real bytes','.json')==first


@pytest.fixture
def probe_receipt(tmp_path):
    archive=MarketArchive(tmp_path/'probe',initialize=True)
    catalog=archive.append('catalog','alpaca',[{'provider':'alpaca','native_id':'asset-aapl',
        'symbol':'AAPL','name':'Apple','market':'US','exchange':'NASDAQ','status':'active','present':True,
        'isin':None,'attributes':{'tradable':True}}],sources=[])
    row={'provider':'alpaca','native_id':'asset-aapl','interval':'P1D','start_at':'2026-10-13T04:00:00Z',
        'feed':'iex','adjustment_basis':'raw','open':'100','high':'102','low':'99','close':'101','volume':'123',
        'source_hash':'a'*64}
    archive.append('candles','alpaca',[row],sources=[{'sha256':'a'*64}])
    report={'provider':'alpaca','database_access':False,'owner_ingestion':False,
        'catalog':{'records':1,'manifest_hash':catalog['manifest_hash']},'history':{'rows':1},
        'history_accuracy':{'status':'EXACT_OHLCV_MATCH','compared_rows':1,'feed':'iex','adjustment_basis':'raw',
                            'source_response_hash':'a'*64},
        'stream':{'stats':{'events':0,'authentication_confirmed':True,'subscription_confirmed':True}},
        'read_only_sample':{}}
    path=tmp_path/'probe.json';path.write_text(json.dumps(report),encoding='utf-8')
    return path,report,archive


def test_offline_audit_reads_real_structure_without_credentials_or_writes(probe_receipt):
    path,report,archive=probe_receipt
    before=archive.integrity();receipt_bytes=path.read_bytes()
    with patch('market_cortex.providers.ReadTransport.get',side_effect=AssertionError('NETWORK_FORBIDDEN')):
        result=audit_probe(path)
    assert not result['owner_writes'] and result['provider_calls']==0
    assert not result['history']['offline_raw_provider_comparison_reproduced']
    assert not result['feed']['fresh_price_observations_received']
    assert archive.integrity()==before and path.read_bytes()==receipt_bytes


@pytest.mark.parametrize('mutation',['owner','counts','artifact'])
def test_offline_audit_rejects_unsafe_or_inconsistent_evidence(probe_receipt,mutation):
    path,report,archive=probe_receipt
    if mutation=='owner':report['owner_ingestion']=True
    if mutation=='counts':report['history']['rows']=2
    if mutation=='artifact':
        manifest=archive.latest('candles','alpaca')[0]
        # Only this synthetic fixture is damaged, never a source archive.
        archive.artifact_path(manifest).write_bytes(b'corrupt fixture')
    path.write_text(json.dumps(report),encoding='utf-8')
    with pytest.raises(ProviderFailure):audit_probe(path)


def test_unchanged_catalog_reuses_snapshot_but_retains_new_source_check(tmp_path):
    from market_cortex.providers import Page
    from fastapi.testclient import TestClient
    from market_cortex.market_data_app import create_market_app
    archive=MarketArchive(tmp_path/'source',initialize=True)
    class Source:
        status='TRADING'
        def get(self,*args,**kwargs):
            return Page({'symbols':[{'symbol':'BTCUSDT','status':self.status,'baseAsset':'BTC',
                'quoteAsset':'USDT','isSpotTradingAllowed':True}]},'a'*64,200)
    source=Source();first=sync_catalog(archive,'binance',source)
    repeated=sync_catalog(archive,'binance',source)
    assert repeated['manifest_hash']==first['manifest_hash']
    assert repeated['catalog_check']['unchanged']
    assert len(archive.manifests('catalog','binance'))==1
    checks=archive.manifests('requests','binance')
    assert len(checks)==1 and checks[0]['metadata']['catalog_snapshot']==first['manifest_hash']
    with TestClient(create_market_app(archive)) as client:
        health=client.get('/api/v1/market-data/health').json()
        assert health['catalog_checked_at']['binance']==checks[0]['observed_at']
    source.status='BREAK';changed=sync_catalog(archive,'binance',source)
    assert changed['manifest_hash']!=first['manifest_hash']
    assert len(archive.manifests('catalog','binance'))==2


def test_catalog_knowledge_is_not_backdated_to_request_start(tmp_path):
    from market_cortex.providers import Page
    archive=MarketArchive(tmp_path/'source',initialize=True)
    clock=Clock()
    class Source:
        def get(self,*args,**kwargs):
            clock.now=5
            return Page({'symbols':[{'symbol':'BTCUSDT','status':'TRADING','baseAsset':'BTC',
                'quoteAsset':'USDT','isSpotTradingAllowed':True}]},'a'*64,200)
    def knowledge():return (datetime(2026,10,14,tzinfo=timezone.utc)+timedelta(seconds=clock.now)).isoformat()
    with patch('market_cortex.market_universe.stamp',side_effect=knowledge):
        manifest=sync_catalog(archive,'binance',Source())
    assert manifest['observed_at']==archive.rows(manifest)[0]['last_observed_at']==knowledge()
    assert datetime.fromisoformat(manifest['observed_at']).second==5


def test_capacity_failure_preserves_previous_evidence_and_publishes_no_partial_operation(tmp_path):
    archive=MarketArchive(tmp_path/'source',initialize=True)
    archive.append('events','alpaca',[{'price':'100'}],sources=[])
    before=archive.integrity()
    capped=MarketArchive(archive.root,maximum_bytes=max(1024,before['bytes']+1))
    with pytest.raises(ProviderFailure,match='ARCHIVE_DISK_BUDGET_EXCEEDED'):
        capped.append('events','alpaca',[{'price':'101'}],sources=[])
    assert archive.integrity()==before
    assert not (archive.root/'.writer.lock').exists()


def test_retained_disk_budget_cannot_be_relaxed_by_reopening(tmp_path):
    archive=MarketArchive(tmp_path/'source',initialize=True,maximum_bytes=2048)
    assert MarketArchive(archive.root).maximum_bytes==2048
    assert MarketArchive(archive.root,maximum_bytes=8192).maximum_bytes==2048
    with pytest.raises(ProviderFailure,match='ARCHIVE_DISK_BUDGET_EXCEEDED'):
        archive.assert_capacity(2048)
    with pytest.raises(ProviderFailure,match='INVALID_ARCHIVE_DISK_BUDGET'):
        MarketArchive(tmp_path/'another',initialize=True,maximum_bytes=True)
