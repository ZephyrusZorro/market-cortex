"""Synthetic API scope tests, never owner approval or live broker evidence."""
from datetime import datetime,timezone,timedelta
from unittest.mock import Mock,patch

import pytest
from fastapi.testclient import TestClient

from market_cortex.market_archive import MarketArchive
from market_cortex.market_data_app import create_market_app
from market_cortex.market_fetch_scope import FetchScope,FetchWindow
from market_cortex.providers import ProviderFailure


START=datetime(2026,10,1,4,tzinfo=timezone.utc)
END=datetime(2026,10,14,4,tzinfo=timezone.utc)


@pytest.mark.parametrize('provider,native,interval,start,end',[
    ('alpaca','not-approved','1d',START,END),
    ('upstox','asset-aapl','1d',START,END),
    ('alpaca','asset-aapl','1m',START,END),
    ('alpaca','asset-aapl','1d',START-timedelta(days=1),END),
    ('alpaca','asset-aapl','1d',START,END+timedelta(seconds=1)),
])
def test_approval_does_not_expand_identity_provider_interval_or_dates(provider,native,interval,start,end):
    scope=FetchScope((FetchWindow('alpaca','asset-aapl','1d',START,END),))
    with pytest.raises(ProviderFailure,match='SOURCE_FETCH_NOT_APPROVED'):
        scope.require(provider,native,interval,start,end)


def test_scoped_api_refuses_fetch_before_lookup_network_or_archive_writes(tmp_path):
    archive=MarketArchive(tmp_path/'source',initialize=True)
    before=archive.integrity();service=Mock()
    scope=FetchScope((FetchWindow('alpaca','asset-aapl','1d',START,END),))
    with patch('market_cortex.market_data_app.search_catalog') as lookup:
        with TestClient(create_market_app(archive,history=service,fetch_scope=scope)) as client:
            response=client.post('/api/v1/market-data/history/fetch',json={
                'provider':'alpaca','native_id':'unapproved','interval':'1d',
                'start':START.isoformat(),'end':END.isoformat()})
    assert response.status_code==422 and response.json()['code']=='SOURCE_FETCH_NOT_APPROVED'
    lookup.assert_not_called();service.fetch.assert_not_called()
    assert archive.integrity()==before


def test_scope_accepts_only_contained_window_and_default_closed_scope_denies():
    scope=FetchScope((FetchWindow('alpaca','asset-aapl','1d',START,END),))
    scope.require('alpaca','asset-aapl','1d',START,END)
    scope.require('alpaca','asset-aapl','1d',START+timedelta(days=1),END)
    with pytest.raises(ProviderFailure,match='SOURCE_FETCH_NOT_APPROVED'):
        FetchScope(()).require('alpaca','asset-aapl','1d',START,END)
