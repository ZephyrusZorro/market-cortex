"""Hermetic credential, feed, native identity and GET-only access diagnostics."""
import json
from datetime import datetime,timezone

import httpx
import pytest

from market_cortex.provider_readiness import probe
from market_cortex.providers import ReadTransport,ProviderFailure


@pytest.mark.parametrize('provider',['upstox','alpaca'])
def test_absent_credentials_are_deferred_without_network(monkeypatch,provider):
    for name in ('UPSTOX_ACCESS_TOKEN','APCA_API_KEY_ID','APCA_API_SECRET_KEY'):monkeypatch.delenv(name,raising=False)
    class NoNetwork:
        def get(self,*args,**kwargs):pytest.fail('missing credentials must not call provider')
    assert probe(provider,transport=NoNetwork())['status']=='DEFERRED_NOT_CONFIGURED'


def test_alpaca_probe_iex_headers_and_no_implicit_ticker_remapping(monkeypatch):
    monkeypatch.setenv('APCA_API_KEY_ID','private-test-key')
    monkeypatch.setenv('APCA_API_SECRET_KEY','private-test-secret')
    calls=[]
    def respond(request):
        calls.append(request)
        assert request.method=='GET' and request.url.host=='data.alpaca.markets'
        assert request.url.params['feed']=='iex' and request.url.params['adjustment']=='raw' and request.url.params['asof']=='-'
        assert request.headers['APCA-API-SECRET-KEY']=='private-test-secret'
        return httpx.Response(200,json={'bars':[{'t':'2026-10-09T04:00:00Z','o':1,'h':2,'l':1,'c':2,'v':1}]})
    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        result=probe('alpaca',transport=ReadTransport(client),now=datetime(2026,10,11,tzinfo=timezone.utc))
    assert result['status']=='AUTHENTICATED_SAMPLE_OBSERVED'
    assert result['canonical_identity']=='REQUIRES_VERIFIED_MAPPING' and not result['owner_ingestion']
    assert 'private-test' not in json.dumps(result) and len(calls)==1


def test_upstox_probe_native_key_and_safe_auth_failure(monkeypatch):
    monkeypatch.setenv('UPSTOX_ACCESS_TOKEN','private-test-token')
    calls=[]
    def respond(request):
        calls.append(request)
        assert request.method=='GET' and request.headers['Authorization']=='Bearer private-test-token'
        if request.url.path.endswith('search'):
            return httpx.Response(200,json={'data':[{'trading_symbol':'RELIANCE','segment':'NSE_EQ','exchange':'NSE','instrument_key':'NSE_EQ|INE002A01018'}]})
        return httpx.Response(403,text='private-test-token sensitive provider diagnostic')
    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        result=probe('upstox',transport=ReadTransport(client))
    assert result['code']=='ACCESS_DENIED' and len(calls)==2
    assert 'private-test-token' not in json.dumps(result)


@pytest.mark.parametrize('host,path',[
    ('api.upstox.com','/v2/order/place'),('api.alpaca.markets','/v2/orders'),
    ('paper-api.alpaca.markets','/v2/orders'),('api.upstox.com','/v2/login/authorization/token'),
    ('data.alpaca.markets','/v2/account'),('evil.example','/v2/stocks/AAPL/bars')])
def test_transport_rejects_broker_and_auth_write_surfaces(host,path):
    with pytest.raises(ProviderFailure,match='ENDPOINT_NOT_ALLOWED'):
        ReadTransport().get(host,path)


def test_upstox_ambiguous_mapping_never_requests_bars(monkeypatch):
    monkeypatch.setenv('UPSTOX_ACCESS_TOKEN','synthetic-token')
    calls=[]
    def respond(request):
        calls.append(request)
        item={'trading_symbol':'RELIANCE','segment':'NSE_EQ','exchange':'NSE','instrument_key':'NSE_EQ|INE002A01018'}
        return httpx.Response(200,json={'data':[item,item]})
    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        result=probe('upstox',transport=ReadTransport(client))
    assert result['code']=='NO_UNIQUE_NATIVE_INSTRUMENT' and len(calls)==1


@pytest.mark.parametrize('complete',[True,False])
def test_typed_adapter_probe_normalizes_only_declared_calendar(monkeypatch,complete):
    from datetime import date
    from test_foundation import identity,calendar,instant
    from market_cortex.provider_readiness import AdapterProbeBundle
    monkeypatch.setenv('APCA_API_KEY_ID','synthetic-key')
    monkeypatch.setenv('APCA_API_SECRET_KEY','synthetic-secret')
    i,m=identity('XNYS','alpaca','AAPL','ticker')
    cal=calendar('XNYS')
    bundle=AdapterProbeBundle(instrument=i,mapping=m,venue=cal.venue,calendar_id=cal.calendar_id,
        calendar_version=cal.version,sessions=[cal.session(date(2025,1,2))] if complete else [],
        identity_evidence='synthetic fixture identity',calendar_evidence='synthetic fixture sessions',
        start=instant('2025-01-02T05:00:00Z'),end=instant('2025-01-03T05:00:00Z'))
    def respond(request):
        return httpx.Response(200,json={'bars':[{'t':'2025-01-02T05:00:00Z','o':100,'h':110,'l':90,'c':105,'v':20}],'next_page_token':None})
    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        result=probe('alpaca',transport=ReadTransport(client),bundle=bundle)
    if complete:
        assert result['adapter']['accepted_daily_bars']==1 and result['adapter']['missing_declared_sessions']==[]
        assert not result['adapter']['authority_independently_verified']
    else:
        assert result['code']=='CALENDAR_UNKNOWN'
