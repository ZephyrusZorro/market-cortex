"""Synthetic Stage A limits and viewer isolation; no live acceptance claims."""
from unittest.mock import Mock, patch

import httpx
import pytest
from fastapi.testclient import TestClient

from market_cortex.market_archive import MarketArchive
from market_cortex.market_stage_a import StageATransport, approved_scope, viewer, category, LISTINGS, WINDOWS
from market_cortex.providers import ProviderFailure


def test_seven_exact_native_windows():
    assert len(approved_scope().windows) == 7
    for provider, native, _, _ in LISTINGS:
        approved_scope().require(provider, native, '1d', *WINDOWS[provider])
    assert WINDOWS['upstox'][0].isoformat() == '2026-09-30T18:30:00+00:00'
    assert WINDOWS['alpaca'][0].isoformat() == '2026-10-01T04:00:00+00:00'


@pytest.mark.parametrize('host,path', [
    ('api.upstox.com', '/v3/historical-candle/NSE_EQ%7CINE002A01018/days/1/2026-10-14/2026-10-01'),
    ('api.upstox.com', '/v3/historical-candle/unknown/days/1/2026-10-13/2026-10-01'),
    ('data.alpaca.markets', '/v2/stocks/MSFT/bars'),
    ('data-api.binance.vision', '/api/v3/klines'),
    ('api.alpaca.markets', '/v2/orders'),
])
def test_other_endpoints_dates_and_identities_denied(host, path):
    with pytest.raises(ProviderFailure, match='STAGE_A_ENDPOINT_NOT_APPROVED'):
        category(host, path)


def test_durable_attempt_limits_survive_transport_recreation(tmp_path):
    archive = MarketArchive(tmp_path / 'source', initialize=True)
    with patch('market_cortex.market_universe.PacedTransport.before_attempt'):
        transport = StageATransport(archive)
        for _ in range(18):
            transport.before_attempt('api.upstox.com', '/v3/feed/market-data-feed/authorize')
        assert transport.usage()['stream_authorization'] == 18
        restarted = StageATransport(MarketArchive(archive.root))
        with pytest.raises(ProviderFailure, match='STAGE_A_REQUEST_BUDGET_EXHAUSTED'):
            restarted.before_attempt('api.upstox.com', '/v3/feed/market-data-feed/authorize')
        assert restarted.usage() == transport.usage()


def test_http_retries_count_as_separate_attempts(tmp_path):
    archive = MarketArchive(tmp_path / 'source', initialize=True)
    statuses = iter([500, 502, 200])
    client = httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(next(statuses), json={})))
    with patch('market_cortex.market_universe.PacedTransport.before_attempt'), patch('market_cortex.providers.time.sleep'):
        transport = StageATransport(archive, client)
        transport.get('api.alpaca.markets', '/v2/assets')
    assert transport.usage()['metadata'] == 3


def test_viewer_denies_even_approved_downloads_without_network(tmp_path):
    archive = MarketArchive(tmp_path / 'source', initialize=True)
    before = archive.integrity()
    with patch('market_cortex.market_data_app.search_catalog') as lookup:
        with TestClient(viewer(archive)) as client:
            response = client.post('/api/v1/market-data/history/fetch', json={
                'provider': 'upstox', 'native_id': LISTINGS[0][1], 'interval': '1d',
                'start': WINDOWS['upstox'][0].isoformat(), 'end': WINDOWS['upstox'][1].isoformat()})
            policy = client.get('/api/v1/market-data/stage-a-policy').json()
    assert response.status_code == 422 and response.json()['code'] == 'SOURCE_FETCH_NOT_APPROVED'
    assert not policy['history_fetch_enabled'] and not policy['owner_writes']
    assert not policy['scheduled_jobs'] and not policy['continuous_collection']
    lookup.assert_not_called()
    assert archive.integrity() == before


@pytest.mark.parametrize('change', [{'feed': 'sip'}, {'timeframe': '1Min'},
                                  {'start': '2026-09-30T04:00:00Z'}, {'end': '2026-10-15T04:00:00Z'}])
def test_alpaca_unapproved_parameters_fail_before_admission(tmp_path, change):
    archive = MarketArchive(tmp_path / 'source', initialize=True)
    client = Mock()
    transport = StageATransport(archive, client)
    params = {'start': WINDOWS['alpaca'][0].isoformat(), 'end': WINDOWS['alpaca'][1].isoformat(),
              'timeframe': '1Day', 'feed': 'iex', 'adjustment': 'raw', 'asof': '-', 'limit': 1000}
    params.update(change)
    with pytest.raises(ProviderFailure):
        transport.get('data.alpaca.markets', '/v2/stocks/AAPL/bars', params=params)
    client.stream.assert_not_called()
    assert sum(transport.usage().values()) == 0
