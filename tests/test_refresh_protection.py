from datetime import datetime,timedelta,timezone

import pytest

from market_cortex.database import connect
from market_cortex.operations import enqueue_refresh,refresh_plan,status,worker
from market_cortex.providers import FetchBatch
from test_operations import operational_catalog,task_directory
from test_foundation import bar
from uuid import uuid4


def test_missing_scope_is_explicit_and_owner_bootstrap_is_forbidden(operational_catalog):
    _,settings,p,*_=operational_catalog
    now=datetime.now(timezone.utc)
    current=status(settings,now)
    assert len(current['items'])==5 and not current['all_fresh']
    assert current['items'][0]['freshness']=='DATA_UNAVAILABLE'
    assert current['items'][1]['freshness']=='IDENTITY_UNAVAILABLE'
    from dataclasses import replace
    with pytest.raises(ValueError,match='OWNER_HISTORY_REQUIRED_NO_IMPLICIT_BOOTSTRAP'):
        refresh_plan(p,replace(settings,environment='OWNER_MAIN'),now)


def test_incremental_plan_uses_utc_three_day_overlap_and_latest_due_key(operational_catalog):
    catalog,settings,p,i,m,cal=operational_catalog
    now=datetime.now(timezone.utc)
    latest=now.date()-timedelta(days=1)
    b=bar(i,m,cal,day=latest,available=now.isoformat())
    catalog.ingest([b],cal,source_batch_id=b.envelope.source_batch_id,provider_id='binance',raw_hash='a'*64,fetched_at=now)
    plan=refresh_plan(p,settings,now)[0]
    assert plan.start.date()==latest-timedelta(days=2)
    assert plan.end.hour==0 and plan.end.date()==now.date()
    assert enqueue_refresh(p,settings,now,scheduled=True)==enqueue_refresh(p,settings,now+timedelta(seconds=1),scheduled=True)


def test_empty_provider_never_marks_refresh_done(operational_catalog):
    catalog,settings,p,*_=operational_catalog
    enqueue_refresh(p,settings,datetime.now(timezone.utc),scheduled=True)
    class Empty:
        def fetch_daily(self,*args):return FetchBatch(uuid4(),'binance',datetime.now(timezone.utc),'a'*64,(),1,'spot_public','raw')
    result=worker(p,settings,adapter=Empty())
    assert result['status']=='READY' and result['code']=='LATEST_CLOSED_SESSION_UNAVAILABLE'
    assert catalog.head() is None


def test_expired_third_lease_is_dead_without_another_provider_call(operational_catalog):
    _,settings,p,*_=operational_catalog
    enqueue_refresh(p,settings,datetime.now(timezone.utc),scheduled=True)
    with connect(settings.database_url) as c:
        c.execute("UPDATE jobs SET state='leased',attempts=3,lease_until=now()-interval '1 second'")
    class NoSource:
        def fetch_daily(self,*args):pytest.fail('retry limit exhausted')
    assert worker(p,settings,adapter=NoSource())['status']=='IDLE'
    item=status(settings,datetime.now(timezone.utc),p)['jobs'][0]
    assert item['state']=='dead' and item['attempts']==3 and item['error_code']=='LEASE_RETRY_LIMIT'
