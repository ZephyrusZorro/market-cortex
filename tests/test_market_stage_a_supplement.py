"""Hermetic supplemental admission checks; no credentials or provider calls."""
import asyncio
from datetime import datetime, timezone
from unittest.mock import Mock, patch

import pytest

from market_cortex.market_stage_a_supplement import require_capture_window, supplement
from market_cortex.market_archive import MarketArchive
from market_cortex.providers import ProviderFailure


@pytest.mark.parametrize('instant', ['2026-10-14T20:03:00', '2026-10-17T15:00:00',
                                   '2026-12-14T14:00:00'])
def test_closed_weekend_or_winter_preopen_rejected(instant):
    with pytest.raises(ProviderFailure, match='ACTIVE_SESSION_WINDOW_REQUIRED'):
        require_capture_window(datetime.fromisoformat(instant).replace(tzinfo=timezone.utc))


@pytest.mark.parametrize('instant', ['2026-10-15T14:00:00', '2026-12-14T15:00:00'])
def test_dst_and_winter_session_admitted(instant):
    require_capture_window(datetime.fromisoformat(instant).replace(tzinfo=timezone.utc))


def test_closed_window_performs_no_archive_or_feed_operations():
    archive = Mock(spec=MarketArchive)
    with patch('market_cortex.market_stage_a_supplement.require_capture_window',
               side_effect=ProviderFailure('SUPPLEMENTAL_IEX_ACTIVE_SESSION_WINDOW_REQUIRED')), \
         patch('market_cortex.market_stage_a_supplement.FeedWorker') as worker:
        with pytest.raises(ProviderFailure):
            asyncio.run(supplement(archive))
    assert not archive.mock_calls and not worker.mock_calls


@pytest.mark.parametrize('rows,code', [([], 'ORIGINAL_IEX_CAPTURE_REQUIRED'), ([
    {'metadata': {'operation': 'stage_a_capture_complete'}},
    {'metadata': {'operation': 'stage_a_supplemental_iex_90_started'}}],
    'SUPPLEMENTAL_IEX_ALREADY_STARTED_REVIEW_REQUIRED')])
def test_missing_original_or_repeat_refused_before_writes(rows, code):
    archive = Mock(spec=MarketArchive)
    archive.manifests.return_value = rows
    with patch('market_cortex.market_stage_a_supplement.require_capture_window'), \
         patch('market_cortex.market_stage_a_supplement.FeedWorker') as worker:
        with pytest.raises(ProviderFailure, match=code):
            asyncio.run(supplement(archive))
    archive.append.assert_not_called()
    archive.assert_capacity.assert_not_called()
    worker.assert_not_called()
import asyncio
from unittest.mock import AsyncMock

def test_supplement_never_reconnects():
    archive = Mock(spec=MarketArchive)
    archive.manifests.side_effect = [[{'metadata': {'operation': 'stage_a_capture_complete'}}], []]
    with patch('market_cortex.market_stage_a_supplement.require_capture_window'), \
         patch('market_cortex.market_stage_a_supplement.identities', return_value=[{'native_id': 'fixture'}]), \
         patch('market_cortex.market_stage_a_supplement.StageATransport'), \
         patch('market_cortex.market_stage_a_supplement.FeedWorker') as worker:
        worker.return_value.run = AsyncMock(side_effect=ProviderFailure('TEST_STOP'))
        with pytest.raises(ProviderFailure, match='TEST_STOP'):
            asyncio.run(supplement(archive))
        worker.assert_called_once_with(archive, 'alpaca', [{'native_id': 'fixture'}], feed='iex', interval='1m', max_retries=0)
        worker.return_value.run.assert_awaited_once_with(90)
        assert archive.append.call_args.kwargs['metadata']['maximum_connections'] == 1
        assert archive.append.call_args.kwargs['metadata']['maximum_reconnects'] == 0
