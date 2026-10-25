"""Credential-probe acceptance guards; synthetic responses, no broker account."""
import json
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import pytest

from market_cortex.multi_market_probe import main, verify_history_accuracy, feed_validation_code
from market_cortex.providers import Page, ProviderFailure


@pytest.fixture
def credentials(monkeypatch):
    for name in ('UPSTOX_ACCESS_TOKEN','APCA_API_KEY_ID','APCA_API_SECRET_KEY'):
        monkeypatch.setenv(name,'synthetic-private-probe-value')


def evidence(provider):
    at=datetime(2026,10,5,18,30,tzinfo=timezone.utc) if provider=='upstox' else datetime(2026,10,6,4,tzinfo=timezone.utc)
    native='NSE_EQ|INE000A01010' if provider=='upstox' else 'asset-native-id'
    item={'provider':provider,'native_id':native,'symbol':'SAMPLE'}
    observation={'provider':provider,'native_id':native,'interval':'P1D','start_at':at.isoformat(),
        'end_at':(at+timedelta(days=1)).isoformat(),'open':'100.00','high':'102','low':'99',
        'close':'101.00','volume':'123','feed':'historical_v3' if provider=='upstox' else 'iex',
        'adjustment_basis':'provider_unspecified' if provider=='upstox' else 'raw'}
    raw=['2026-10-06T00:00:00+05:30',100,102,99,101,123] if provider=='upstox' else {
        't':at.isoformat().replace('+00:00','Z'),'o':100,'h':102,'l':99,'c':101,'v':123}
    return item,observation,raw


class Transport:
    def __init__(self,provider,rows):
        self.calls=[]
        self.body={'data':{'candles':rows}} if provider=='upstox' else {'bars':rows,'next_page_token':None}

    def get(self,*args,**kwargs):
        self.calls.append((args,kwargs))
        return Page(self.body,'b'*64,200)


@pytest.mark.parametrize('provider',['upstox','alpaca'])
def test_comparison_uses_fresh_provider_values_and_timezone_equivalence(provider,credentials):
    item,observation,raw=evidence(provider)
    transport=Transport(provider,[raw])
    result=verify_history_accuracy(item,[observation],transport=transport)
    assert result['status']=='EXACT_OHLCV_MATCH' and result['compared_rows']==1
    assert result['provider_calls']==len(transport.calls)==1
    assert result['source_response_hash']=='b'*64
    assert not result['calendar_authority_verified']
    if provider=='alpaca':
        assert transport.calls[0][1]['params']['feed']=='iex'
        assert transport.calls[0][1]['params']['asof']=='-'
    assert 'synthetic-private-probe-value' not in json.dumps(result)


@pytest.mark.parametrize('provider',['upstox','alpaca'])
def test_value_changes_fail_accuracy_without_overwriting_evidence(provider,credentials):
    item,observation,raw=evidence(provider)
    if provider=='upstox':
        raw[4]=100.5
    else:
        raw['v']=124
    result=verify_history_accuracy(item,[observation],transport=Transport(provider,[raw]))
    assert result['status']=='MISMATCH' and result['changed_timestamps']==[observation['start_at']]
    assert observation['close']=='101.00' and observation['volume']=='123'


def test_missing_and_extra_rows_are_not_treated_as_accuracy(credentials):
    item,observation,raw=evidence('alpaca')
    missing=verify_history_accuracy(item,[observation],transport=Transport('alpaca',[]))
    assert missing['status']=='MISMATCH' and missing['missing_timestamps']==[observation['start_at']]
    extra={**raw,'t':'2026-10-06T05:00:00Z'}
    result=verify_history_accuracy(item,[observation],transport=Transport('alpaca',[raw,extra]))
    assert result['status']=='MISMATCH' and result['unexpected_timestamps']==['2026-10-06T05:00:00+00:00']


def test_empty_history_and_wrong_feed_do_not_issue_comparison_requests(credentials):
    item,observation,raw=evidence('alpaca')
    transport=Transport('alpaca',[raw])
    assert verify_history_accuracy(item,[],transport=transport)['status']=='UNAVAILABLE'
    with pytest.raises(ProviderFailure,match='ACCURACY_SOURCE_IDENTITY_MISMATCH'):
        verify_history_accuracy(item,[{**observation,'feed':'sip'}],transport=transport)
    assert transport.calls==[]


def test_probe_stops_before_feed_when_accuracy_fails(tmp_path):
    item,observation,_=evidence('alpaca')
    report=tmp_path/'report.json'
    with (patch('market_cortex.multi_market_probe.probe',return_value={'status':'AUTHENTICATED_SAMPLE_OBSERVED'}),
          patch('market_cortex.multi_market_probe.sync_catalog',return_value={'rows':1,'manifest_hash':'a'*64}),
          patch('market_cortex.multi_market_probe.select',return_value=[item]),
          patch('market_cortex.multi_market_probe.HistoryService') as service,
          patch('market_cortex.multi_market_probe.verify_history_accuracy',return_value={'status':'MISMATCH'}),
          patch('market_cortex.multi_market_probe.collect',new_callable=AsyncMock) as collector):
        service.return_value.fetch.return_value={'items':[observation],'provider_calls':1}
        assert main(['--provider','alpaca','--root',str(tmp_path/'source'),'--output',str(report)])==1
        collector.assert_not_called()
    receipt=json.loads(report.read_text())
    assert receipt['code']=='HISTORY_ACCURACY_MISMATCH' and not receipt['owner_ingestion']


def test_missing_credentials_leave_source_archive_uninitialized(tmp_path,monkeypatch):
    for name in ('UPSTOX_ACCESS_TOKEN','APCA_API_KEY_ID','APCA_API_SECRET_KEY'):
        monkeypatch.delenv(name,raising=False)
    source=tmp_path/'source'
    report=tmp_path/'report.json'
    assert main(['--provider','upstox','--root',str(source),'--output',str(report)])==1
    assert json.loads(report.read_text())['status']=='DEFERRED_NOT_CONFIGURED'
    assert not source.exists()


def test_optional_delayed_sip_authentication_failure_cannot_pass_primary_feed(tmp_path):
    item,observation,_=evidence('alpaca')
    report=tmp_path/'report.json'
    captures=[{'stats':{'authentication_confirmed':True,'events':0}},
              {'stats':{'authentication_confirmed':False,'events':0}}]
    with (patch('market_cortex.multi_market_probe.probe',return_value={'status':'AUTHENTICATED_SAMPLE_OBSERVED'}),
          patch('market_cortex.multi_market_probe.sync_catalog',return_value={'rows':1,'manifest_hash':'a'*64}),
          patch('market_cortex.multi_market_probe.select',return_value=[item]),
          patch('market_cortex.multi_market_probe.HistoryService') as service,
          patch('market_cortex.multi_market_probe.verify_history_accuracy',return_value={'status':'EXACT_OHLCV_MATCH'}),
          patch('market_cortex.multi_market_probe.collect',new_callable=AsyncMock,side_effect=captures)):
        service.return_value.fetch.return_value={'items':[observation],'provider_calls':1}
        assert main(['--provider','alpaca','--root',str(tmp_path/'source'),'--output',str(report),'--delayed-sip'])==1
    receipt=json.loads(report.read_text())
    assert receipt['status']=='FEED_NOT_VALIDATED'
    assert receipt['code']=='DELAYED_SIP_NOT_ENTITLED_OR_NOT_AUTHENTICATED'
    assert not receipt['market_updates_observed']


@pytest.mark.parametrize('stats,code',[
    ({'authentication_confirmed':False,'subscription_confirmed':False},'STREAM_AUTH_NOT_CONFIRMED'),
    ({'authentication_confirmed':True,'subscription_confirmed':False},'STREAM_SUBSCRIPTION_NOT_CONFIRMED'),
    ({'authentication_confirmed':True,'subscription_confirmed':True,'last_error':'STREAM_RETRY_BUDGET_EXHAUSTED'},'STREAM_CAPTURE_ERROR_REQUIRES_REVIEW'),
    ({'authentication_confirmed':True,'subscription_confirmed':True,'events':0},None),
])
def test_feed_acceptance_requires_auth_subscription_and_error_free_capture(stats,code):
    assert feed_validation_code(stats)==code


@pytest.mark.parametrize('failed_feed',['primary','delayed'])
def test_authenticated_but_unsubscribed_feed_cannot_pass_probe(tmp_path,failed_feed):
    item,observation,_=evidence('alpaca');report=tmp_path/'report.json'
    good={'stats':{'authentication_confirmed':True,'subscription_confirmed':True,'events':0}}
    failed={'stats':{'authentication_confirmed':True,'subscription_confirmed':False,'events':0}}
    captures=[failed] if failed_feed=='primary' else [good,failed]
    with (patch('market_cortex.multi_market_probe.probe',return_value={'status':'AUTHENTICATED_SAMPLE_OBSERVED'}),
          patch('market_cortex.multi_market_probe.sync_catalog',return_value={'rows':1,'manifest_hash':'a'*64}),
          patch('market_cortex.multi_market_probe.select',return_value=[item]),
          patch('market_cortex.multi_market_probe.HistoryService') as service,
          patch('market_cortex.multi_market_probe.verify_history_accuracy',return_value={'status':'EXACT_OHLCV_MATCH'}),
          patch('market_cortex.multi_market_probe.collect',new_callable=AsyncMock,side_effect=captures)):
        service.return_value.fetch.return_value={'items':[observation],'provider_calls':1}
        args=['--provider','alpaca','--root',str(tmp_path/'source'),'--output',str(report)]
        if failed_feed=='delayed':args.append('--delayed-sip')
        assert main(args)==1
    receipt=json.loads(report.read_text())
    assert receipt['status']=='FEED_NOT_VALIDATED' and not receipt['market_updates_observed']
    if failed_feed=='primary':assert receipt['code']=='STREAM_SUBSCRIPTION_NOT_CONFIRMED'
    else:assert receipt['delayed_sip_validation_code']=='STREAM_SUBSCRIPTION_NOT_CONFIRMED'
