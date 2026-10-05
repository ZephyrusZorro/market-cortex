"""Golden synthetic facts; historical availability, security and deterministic calculations."""
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from uuid import UUID, uuid4
from types import SimpleNamespace

import httpx
import pytest
from pydantic import ValidationError

from market_cortex.contracts import ObservationEnvelope
from market_cortex.intelligence import (build_snapshot, conflicts, deduplicate_news, derivatives,
    event_risk, event_study, fundamental_ratio, option_analytics)
from market_cortex.intelligence_contracts import (ContextRequest, DerivativeContract, DerivativeObservation,
    EconomicObservation, EntityRef, EventFact, FundamentalFact, NewsEvent, OnChainMetric, OptionContract, OptionQuote, OptionChainSnapshot)
from market_cortex.intelligence_sources import CachedTransport, TreasuryMacro
from market_cortex.intelligence_store import digest, visible
from market_cortex.providers import ProviderFailure, ReadTransport
from market_cortex.quant import QuantService
from test_foundation import identity, bar, calendar
from test_phase8_quant import synthetic_source, definition

Z = timezone.utc
T = datetime(2025, 4, 15, 12, tzinfo=Z)
I = UUID('aaaaaaaa-aaaa-4aaa-aaaa-aaaaaaaaaaaa')


def env(at=T, *, instrument=I, provider='synthetic', unit='USD', published=None, **changes):
    value = dict(observation_id=uuid4(), instrument_id=instrument, series_id=None if instrument else 'series',
        venue_id='SYNTHETIC', provider_id=provider, provider_record_id='fixture', event_at=at,
        published_at=published or at, available_at=at, availability_basis='documented_publication', ingested_at=at,
        timestamp_precision='second', is_final=True, quality_state='valid', freshness_policy_id='synthetic', validation_codes=[],
        source_ref='urn:synthetic:fixture', source_batch_id=uuid4(), raw_content_hash='0'*64,
        raw_retention_state='hash_only', normalizer_version='synthetic_v1', license_policy_id='fixture', unit=unit, adjustment_basis='raw')
    value.update(changes)
    return ObservationEnvelope(**value)


def macro(at=T, value='3.0', **changes):
    p = dict(envelope=env(at, instrument=None, unit='percent'), entity=EntityRef(kind='series', key='CPI', mapping_version='fixture'),
        logical_key='CPI:2025Q1', classification_scope='SYNTHETIC_TEST', series_id='CPI', metric='inflation', value=value, region='US',
        frequency='quarterly', seasonal_adjustment='adjusted', period_start=date(2025,1,1), period_end=date(2025,3,31))
    p.update(changes)
    return EconomicObservation(**p)


def fundamental(at=T, metric='revenue', value='100', **changes):
    p = dict(envelope=env(at, instrument=None, unit='currency', currency='USD'),
        entity=EntityRef(kind='issuer', key='issuer:fixture', mapping_version='fixture'), issuer_id='issuer:fixture',
        logical_key=f'{metric}:2025Q1', classification_scope='SYNTHETIC_TEST', metric=metric, value=value,
        fiscal_period='2025Q1', currency='USD', period_start=date(2025,1,1), period_end=date(2025,3,31), related_instrument_ids=[I])
    p.update(changes)
    return FundamentalFact(**p)


def event(at=T, when=None, **changes):
    p = dict(envelope=env(at), entity=EntityRef(kind='instrument', key=str(I), mapping_version='fixture'),
        logical_key='event:fixture', classification_scope='SYNTHETIC_TEST', kind='corporate_event', category='earnings',
        scheduled_at=when or at+timedelta(days=2), importance='high', importance_source='urn:synthetic:calendar')
    p.update(changes)
    return EventFact(**p)


def news(at=T, title='Fixture issuer publishes quarterly earnings', **changes):
    p = dict(envelope=env(at), entity=EntityRef(kind='instrument', key=str(I), mapping_version='fixture'),
        logical_key='news:'+str(uuid4()), classification_scope='SYNTHETIC_TEST', title=title, category='earnings')
    p.update(changes)
    return NewsEvent(**p)


def derivative(at=T, kind='funding', value='.0001', **changes):
    contract = DerivativeContract(instrument_id=I, underlying_instrument_id=UUID(int=1), provider='synthetic', venue='SYNTHETIC',
        native_id='FIXTUREUSDT', contract_type='PERPETUAL', base_asset='BTC', quote_currency='USDT', margin_currency='USDT',
        quantity_unit='BTC', identity_version='fixture', known_at=T-timedelta(days=100))
    p = dict(envelope=env(at, unit='fraction_per_funding_event' if kind=='funding' else 'BTC'),
        entity=EntityRef(kind='instrument', key=str(I), mapping_version='fixture'), logical_key=f'{kind}:{at}',
        classification_scope='SYNTHETIC_TEST', contract=contract, kind=kind, metric=kind, value=value)
    p.update(changes)
    return DerivativeObservation(**p)


def test_macro_revision_and_period_leakage():
    initial=macro(); correction=macro(T+timedelta(days=20), '2.8', revision_number=2,
        envelope=env(T+timedelta(days=20), instrument=None, unit='percent', supersedes_observation_id=initial.envelope.observation_id))
    assert visible([initial,correction], T-timedelta(seconds=1)) == []
    assert visible([initial,correction], T+timedelta(days=1)) == [initial]
    assert visible([initial,correction], T+timedelta(days=30)) == [correction]
    assert correction.period_end < initial.envelope.available_at.date()


@pytest.mark.parametrize('maker', [fundamental, news, derivative])
def test_future_earnings_news_derivatives_excluded(maker):
    future=maker(T+timedelta(days=1))
    assert visible([future], T, I) == []
    snap=build_snapshot(ContextRequest(as_of=T, instrument_id=I), None, [future])
    assert snap.facts == []


def test_ingestion_does_not_backdate_known_publication():
    f=macro(envelope=env(T, instrument=None, unit='percent', ingested_at=T+timedelta(days=1)))
    assert visible([f], T) == []


def test_conflicting_sources_preserve_both_without_preference():
    a=macro(); b=macro(value='3.4', envelope=env(T, instrument=None, provider='second', unit='percent'))
    result=conflicts([a,b])
    assert result[0]['values']==['3.0','3.4'] and result[0]['preferred_source'] is None


def test_news_dedup_scope_time_and_syndication():
    a=news(syndication_id='fixture-wire'); b=news(title='Unrelated edited title', syndication_id='fixture-wire')
    c=news(T+timedelta(days=3))
    groups=deduplicate_news([a,b,c])
    assert len(groups)==2 and sorted(len(g['article_ids']) for g in groups)==[1,2]
    assert sum(g['independent_event_count'] for g in groups)==2


def test_conflicting_news_assertions_are_unresolved_not_canonical_truth():
    a=news(assertion_key='reported_revenue',assertion_value='100',confidence_category='source_reported')
    b=news(assertion_key='reported_revenue',assertion_value='120',confidence_category='source_reported',envelope=env(provider='second'))
    result=conflicts([a,b])
    assert result[0]['values']==['100','120'] and result[0]['resolution']=='UNRESOLVED'


def test_extracted_numbers_do_not_drive_canonical_macro_derivatives_or_ratios():
    extracted=derivative(classification='EXTRACTED',extraction_model='fixture',extraction_version='v1')
    assert 'funding_latest' not in derivatives([extracted])
    f=fundamental(classification='EXTRACTED',extraction_model='fixture',extraction_version='v1')
    assert fundamental_ratio(f,fundamental())['reason']=='TRUSTED_SOURCE_FACTS_REQUIRED'
    bad=event(envelope=env(quality_state='suspect'))
    assert event_risk([bad],T,I)['state']=='EVENT_DATA_UNAVAILABLE'


def test_fundamental_restatement_and_onchain_availability():
    original=fundamental(); later=fundamental(T+timedelta(days=30),value='95',revision_number=2,
        envelope=env(T+timedelta(days=30),instrument=None,unit='currency',currency='USD',supersedes_observation_id=original.envelope.observation_id))
    assert visible([original,later],T+timedelta(days=1),I)==[original]
    assert visible([original,later],T+timedelta(days=40),I)==[later]
    chain=OnChainMetric(envelope=env(unit='addresses'),entity=EntityRef(kind='instrument',key=str(I),mapping_version='fixture'),
        logical_key='onchain_fixture',classification_scope='SYNTHETIC_TEST',network='fixture_network',metric='active_addresses',
        value='123',block_height=12,methodology='SYNTHETIC_DISTINCT_ADDRESS_COUNT')
    assert visible([chain],T-timedelta(seconds=1))==[] and visible([chain],T)==[chain]


def test_economic_calendar_consensus_and_release_provenance():
    with pytest.raises(ValidationError): event(consensus='1')
    with pytest.raises(ValidationError): event(actual='1')
    f=event(kind='economic_event',category='central_bank',scheduled_at=T+timedelta(hours=1),region='US',
        calendar_complete_until=T+timedelta(days=90))
    assert event_risk([f],T+timedelta(days=3),I)['state']=='NO_KNOWN_EVENT'


def test_synthetic_equity_event_window_respects_explicit_closed_sessions():
    from market_cortex.calendar import SessionCalendar
    from market_cortex.contracts import CalendarSession, Venue
    from datetime import time
    start=date(2025,1,1)
    venue=Venue(venue_id='SYNTHETIC_EQUITY',timezone='America/New_York',session_kind='regular')
    sessions=[]
    for n in range(15):
        day=start+timedelta(days=n)
        opened=datetime.combine(day,time(14,30),Z);closed=datetime.combine(day,time(21),Z)
        sessions.append(CalendarSession(calendar_id='fixture_equity',venue_id=venue.venue_id,session_date=day,
            open_at=opened,close_at=closed,status='holiday' if day.weekday()>=5 else 'open',version='fixture'))
    cal=SessionCalendar(venue,'fixture_equity','fixture',sessions)
    i,m=identity(venue_id=venue.venue_id)
    bars=[bar(i,m,cal,day=s.session_date,close=str(100+n)) for n,s in enumerate(sessions) if s.status=='open']
    result=event_study(bars,cal,datetime(2025,1,4,12,tzinfo=Z),before=1,after=2)
    assert result['status']=='AVAILABLE' and result['calendar_version']=='fixture'
    # Saturday event anchors Monday Jan 6, not a fabricated Saturday session.
    assert len(result['source_observation_ids'])==5


def test_event_risk_requires_sourced_relevant_in_horizon_fact():
    assert event_risk([], T, I)['state']=='EVENT_DATA_UNAVAILABLE'
    assert event_risk([event()], T, UUID(int=42))['state']=='EVENT_DATA_UNAVAILABLE'
    assert event_risk([event(when=T+timedelta(days=30))], T, I)['high_impact_in_horizon'] is False
    risk=event_risk([event()], T, I)
    assert risk['state']=='EVENT_UPCOMING' and risk['high_impact_in_horizon'] is True
    assert event_risk([event(when=T+timedelta(hours=3))], T, I)['state']=='EVENT_IMMINENT'
    assert event_risk([event(when=T-timedelta(hours=3))], T, I)['state']=='EVENT_RECENT'
    assert event_risk([event(classification='EXTRACTED', extraction_model='fixture', extraction_version='v1')], T, I)['high_impact_in_horizon'] is False


def test_partial_snapshot_is_reproducible_and_changes_only_with_visible_facts():
    req=ContextRequest(as_of=T, instrument_id=I)
    fact=macro()
    a=build_snapshot(req,None,[fact]); b=build_snapshot(req,None,[fact,news(T+timedelta(seconds=1))])
    assert a.content_hash==b.content_hash and a.snapshot_id==b.snapshot_id
    assert a.dimensions['macro'].status=='PARTIAL' and a.dimensions['options'].status=='UNKNOWN'
    assert a.event_risk['state']=='EVENT_DATA_UNAVAILABLE'
    assert digest(a.model_dump(mode='json', exclude={'snapshot_id','content_hash'}))==a.content_hash
    stale=build_snapshot(ContextRequest(as_of=T+timedelta(days=60)),None,[macro()])
    assert stale.dimensions['macro'].status=='STALE'


def test_fundamental_ratios_reject_incompatible_period_currency_and_concepts():
    a=fundamental(metric='net_income', value='20'); b=fundamental()
    assert Decimal(fundamental_ratio(a,b)['value'])==Decimal('.2')
    assert fundamental_ratio(a,b.model_copy(update={'period_end':date(2024,12,31)}))['value'] is None
    assert fundamental_ratio(a,b.model_copy(update={'currency':'INR'}))['value'] is None
    assert fundamental_ratio(b,b)['value'] is None
    assert fundamental_ratio(a,b.model_copy(update={'value':Decimal(0)}))['value'] is None


def test_funding_and_exact_aligned_price_oi_matrix():
    old=T-timedelta(days=1)
    rows=[derivative(old, value='-.0001', mark_price='100'), derivative(value='.0001', mark_price='110'),
          derivative(old, 'open_interest', '100'), derivative(T, 'open_interest', '120')]
    metrics=derivatives(rows)
    assert metrics['oi_change_fraction']==pytest.approx(.2)
    assert metrics['aligned_price_change_fraction']==pytest.approx(.1)
    assert metrics['price_oi_state']=='PRICE_UP_OI_UP' and metrics['directional_implication']=='NONE_DESCRIPTIVE_ONLY'
    assert metrics['funding_percentile']==1 and metrics['funding_same_sign_events']==1
    assert derivatives(rows[2:])['price_oi_state']=='UNAVAILABLE_NO_ALIGNED_MARKS_WITHIN_1_SECOND'
    offset=rows[1].model_copy(update={'envelope':rows[1].envelope.model_copy(update={'event_at':T+timedelta(milliseconds=2)})})
    assert derivatives([rows[0],offset,*rows[2:]])['price_oi_state']=='PRICE_UP_OI_UP'
    too_late=rows[1].model_copy(update={'envelope':rows[1].envelope.model_copy(update={'event_at':T+timedelta(seconds=2)})})
    assert derivatives([rows[0],too_late,*rows[2:]])['price_oi_state']=='UNAVAILABLE_NO_ALIGNED_MARKS_WITHIN_1_SECOND'


@pytest.mark.parametrize('kind,value,unit', [('funding','2','fraction_per_funding_event'), ('funding','.1','percent'), ('open_interest','-1','BTC'), ('open_interest','2','contracts')])
def test_derivative_quality_rejects_invalid_values_units(kind,value,unit):
    with pytest.raises(ValidationError):
        derivative(kind=kind,value=value,envelope=env(unit=unit))


def test_option_black_scholes_golden_and_invalid_quotes():
    # Independent textbook S=K=100, r=5%, sigma=20%, T=1.
    call=option_analytics(price=10.450583572185565,underlying=100,strike=100,years=1,rate=.05)
    assert call['status']=='CONVERGED' and call['iv']==pytest.approx(.2,abs=1e-8)
    assert call['greeks']['delta']==pytest.approx(.6368306512,abs=1e-8)
    assert call['greeks']['gamma']==pytest.approx(.01876201735,abs=1e-8)
    put=option_analytics(price=5.573526022256971,underlying=100,strike=100,years=1,rate=.05,right='put')
    assert put['iv']==pytest.approx(.2,abs=1e-8) and put['greeks']['delta']<0
    for price in (-1,0,110):
        assert option_analytics(price=price,underlying=100,strike=100,years=1,rate=.05)['iv'] is None
    assert option_analytics(price=10,underlying=100,strike=100,years=1,rate=.05,exercise='american')['status']=='INVALID_INPUT'


def test_option_identity_chain_missing_fields_and_crossed_market():
    contract=OptionContract(instrument_id=uuid4(),underlying_instrument_id=I,provider='synthetic',venue='fixture',native_id='option-fixture',
        expiry=T+timedelta(days=30),strike='100',right='call',multiplier='1',settlement='cash',exercise='european',quote_currency='USD',identity_version='fixture')
    quote=OptionQuote(contract=contract)
    assert quote.implied_volatility is None and quote.bid is None
    with pytest.raises(ValidationError): OptionQuote(contract=contract,bid='11',ask='10')
    with pytest.raises(ValidationError): OptionQuote(contract=contract,greeks={'delta':'.5'})
    p=dict(envelope=env(),entity=EntityRef(kind='instrument',key=str(I),mapping_version='fixture'),logical_key='chain-fixture',
        classification_scope='SYNTHETIC_TEST',underlying_instrument_id=I,underlying_price='100')
    assert OptionChainSnapshot(**p,quotes=[quote]).quotes[0].last is None
    with pytest.raises(ValidationError): OptionChainSnapshot(**p,quotes=[quote,quote])


@pytest.mark.parametrize('url', ['javascript:alert(1)','http://localhost/private','https://127.0.0.1/private','https://user:secret@example.com/a','file:///C:/secret','https://example.com:8080/a'])
def test_unsafe_source_references_rejected(url):
    with pytest.raises(ValidationError): news(envelope=env(source_ref=url))


@pytest.mark.parametrize('host,path', [('127.0.0.1','/secret'),('fapi.binance.com','/fapi/v1/order'),('api.fiscaldata.treasury.gov','/arbitrary'),('example.com','/fapi/v1/fundingRate')])
def test_ssrf_and_trading_paths_rejected_before_network(host,path):
    requests=[]
    with httpx.Client(transport=httpx.MockTransport(lambda request: requests.append(request))) as client:
        with pytest.raises(ProviderFailure): ReadTransport(client).get(host,path)
    assert requests==[]


def test_redirects_parser_and_credentials_are_safe():
    for response in [httpx.Response(302,headers={'Location':'http://127.0.0.1/secret'}),httpx.Response(200,text='not JSON'),httpx.Response(200,headers={'Content-Length':'9000000'})]:
        calls=[]
        def serve(req): calls.append(req); return response
        with httpx.Client(transport=httpx.MockTransport(serve)) as client:
            with pytest.raises(ProviderFailure): ReadTransport(client).get('fapi.binance.com','/fapi/v1/fundingRate')
        assert len(calls)==1
    with pytest.raises(ProviderFailure): ReadTransport().get('fapi.binance.com','/fapi/v1/fundingRate',params={'api_key':'fixture-secret'})


def test_treasury_normalization_cache_no_invented_publication():
    calls=[]
    def serve(req):
        calls.append(req)
        return httpx.Response(200,json={'data':[{'security_desc':'Treasury Bills','record_date':'2025-03-31','avg_interest_rate_amt':'4.1'}]})
    with httpx.Client(transport=httpx.MockTransport(serve)) as client:
        source=TreasuryMacro(CachedTransport(ReadTransport(client)))
        a=source.fetch(); b=source.fetch()
    assert len(calls)==1 and a[0].value==Decimal('4.1') and a[0].envelope.published_at is None
    assert a[0].envelope.available_at>a[0].envelope.event_at and a[0].period_start==date(2025,3,1)


def test_event_study_calendar_and_synthetic_label():
    i,m=identity(); cal=calendar()
    start=date(2025,1,1)
    bars=[bar(i,m,cal,day=start+timedelta(days=n),close=str(100+n)) for n in range(20)]
    result=event_study(bars,cal,datetime(2025,1,10,tzinfo=Z),before=3,after=3)
    assert result['classification']=='SYNTHETIC_TEST' and result['causality']=='NOT_ESTABLISHED'
    assert result['post_return']==pytest.approx(112/108-1)
    assert event_study(bars[:10],cal,datetime(2025,1,10,tzinfo=Z))['status']=='INSUFFICIENT_SESSION_WINDOW'
    assert event_study(bars[:9]+bars[10:],cal,datetime(2025,1,10,tzinfo=Z),before=3,after=3)['status']=='MISSING_CALENDAR_SESSIONS'


def test_quant_reconstruction_cannot_bypass_context_arrival():
    source=synthetic_source(90)
    source['contextual']={'manifest_id':str(uuid4()),'created_at':(T+timedelta(days=100)).isoformat(),
        'facts':[macro(T+timedelta(days=100)).model_dump(mode='json')], 'policy':'AS_RECORDED_ONLY'}
    service=QuantService(SimpleNamespace(dsn=''),'PILOT_TEST')
    d=definition(manifest_id=UUID(source['manifest_id']),replay_policy='HISTORICAL_RECONSTRUCTION',start=date(2025,2,25),end=date(2025,3,1),
        source_as_of=datetime(2025,8,1,tzinfo=Z),classification='SYNTHETIC_TEST')
    decisions=service.decisions(d,source,digest(source))
    assert decisions and all(not x.contextual_evidence['fact_ids'] for x in decisions)
    assert all(x.contextual_evidence['policy']=='AS_RECORDED_ONLY' for x in decisions)
    filtered=service.decisions(d.model_copy(update={'context_filter':'funding_nonpositive'}),source,digest(source))
    assert all(not x.enter for x in filtered)


def test_quant_frozen_revision_keeps_value_known_before_later_manifest():
    source=synthetic_source(90)
    first_at=datetime(2025,2,25,tzinfo=Z); revised_at=datetime(2025,2,28,tzinfo=Z)
    original=macro(first_at,period_start=date(2025,1,1),period_end=date(2025,1,31))
    revision=macro(revised_at,'2.8',period_start=date(2025,1,1),period_end=date(2025,1,31),revision_number=2,
        envelope=env(revised_at,instrument=None,unit='percent',supersedes_observation_id=original.envelope.observation_id))
    earlier,latest=str(uuid4()),str(uuid4())
    source['contextual']={'manifest_id':latest,'created_at':revised_at.isoformat(),'policy':'AS_RECORDED_ONLY',
        'facts':[original.model_dump(mode='json'),revision.model_dump(mode='json')],
        'manifest_times':{earlier:first_at.isoformat(),latest:revised_at.isoformat()},
        'recorded_at':{str(original.envelope.observation_id):first_at.isoformat(),str(revision.envelope.observation_id):revised_at.isoformat()}}
    d=definition(manifest_id=UUID(source['manifest_id']),replay_policy='HISTORICAL_RECONSTRUCTION',start=date(2025,2,25),end=date(2025,3,1),
        source_as_of=datetime(2025,8,1,tzinfo=Z),classification='SYNTHETIC_TEST')
    rows=QuantService(SimpleNamespace(dsn=''),'PILOT_TEST').decisions(d,source,digest(source))
    for row in rows:
        expected=original if row.cutoff<revised_at else revision
        assert row.contextual_evidence['fact_ids']==[str(expected.envelope.observation_id)]
        assert row.contextual_evidence['manifest_id']==(earlier if row.cutoff<revised_at else latest)


def test_future_derivative_event_rejected_even_with_early_arrival():
    later=derivative(T+timedelta(seconds=2),envelope=env(T,event_at=T+timedelta(seconds=2),unit='fraction_per_funding_event'))
    assert visible([later],T)==[]
