"""Synthetic gated-operation tests; no private owner or real provider writes."""
import asyncio
import json
from unittest.mock import Mock, patch

import pytest

from market_cortex.feed_proto import MarketDataFeed_pb2 as proto
from market_cortex.market_archive import MarketArchive
from market_cortex.market_stage_a import LISTINGS
from market_cortex.market_stage_a_acceptance import (
    recovery_gates, identities, history_operation, IndianSessionEvidence)
from market_cortex.providers import ProviderFailure


def test_old_owner_protection_cannot_satisfy_new_stage_a_gate(tmp_path):
    owner = tmp_path / 'old.json'
    owner.write_text(json.dumps({'status': 'VALIDATED_CURRENT_OWNER_BACKUP_AND_ISOLATED_RESTORE',
        'phase': 'COMPLETE', 'source_unchanged': True, 'all_table_row_hashes_matched': True,
        'backup_retained': True, 'started_at': '2026-10-11T10:00:00Z'}))
    archive = MarketArchive(tmp_path / 'source', initialize=True)
    before = archive.integrity()
    with pytest.raises(ProviderFailure, match='STAGE_A_NEW_OWNER_PROTECTION_REQUIRED'):
        recovery_gates(owner, tmp_path / 'missing.json', archive)
    assert archive.integrity() == before


def test_both_indian_equity_segments_require_current_normal_open():
    observer = IndianSessionEvidence()
    message = proto.FeedResponse()
    message.marketInfo.segmentStatus['NSE_EQ'] = proto.NORMAL_OPEN
    message.marketInfo.segmentStatus['BSE_EQ'] = proto.NORMAL_CLOSE
    observer(message.SerializeToString())
    with pytest.raises(ProviderFailure, match='STAGE_A_INDIAN_ACTIVE_SESSION_NOT_CONFIRMED'):
        observer.require_active()
    message.marketInfo.segmentStatus['BSE_EQ'] = proto.NORMAL_OPEN
    observer(message.SerializeToString())
    observer.require_active()
    assert observer.observations[-1]['states'] == {'NSE_EQ': 'NORMAL_OPEN', 'BSE_EQ': 'NORMAL_OPEN'}
    assert len(observer.observations[-1]['source_payload_sha256']) == 64
    message.marketInfo.segmentStatus['NSE_EQ'] = proto.NORMAL_CLOSE
    observer(message.SerializeToString())
    with pytest.raises(ProviderFailure):
        observer.require_active()


def test_listing_exchange_mismatch_fails_before_fetch():
    with patch('market_cortex.market_stage_a_acceptance.select', return_value=[{
        'symbol': 'RELIANCE', 'exchange': 'BSE', 'status': 'LISTED'}]):
        with pytest.raises(ProviderFailure, match='STAGE_A_NATIVE_IDENTITY_CHANGED'):
            identities(Mock())


def test_seven_scoped_operations_and_repeat_rejected_without_fetch(tmp_path):
    archive = MarketArchive(tmp_path / 'source', initialize=True)
    (archive.root / 'stage-a-profile.json').write_text(json.dumps({
        'maximum_daily_observations': 91, 'maximum_source_bytes': 512 * 1024 * 1024}))
    chosen = [{'provider': p, 'native_id': n, 'symbol': s, 'exchange': e} for p, n, s, e in LISTINGS]
    fake_rows = [{'synthetic': True}]
    service = Mock()
    service.fetch.return_value = {'items': fake_rows, 'new_revisions': 1}
    with patch('market_cortex.market_stage_a_acceptance.identities', return_value=chosen), \
         patch('market_cortex.market_stage_a_acceptance.HistoryService', return_value=service), \
         patch('market_cortex.market_stage_a_acceptance.cached_candles', return_value=fake_rows), \
         patch('market_cortex.market_stage_a_acceptance.verify_history_accuracy', return_value={'status': 'EXACT_OHLCV_MATCH'}):
        result = history_operation(archive, Mock())
        assert result['rows'] == 7 and service.fetch.call_count == 7
        with pytest.raises(ProviderFailure, match='STAGE_A_HISTORY_ALREADY_STARTED_REVIEW_RECOVERY'):
            history_operation(archive, Mock())
        assert service.fetch.call_count == 7


def test_provenance_failure_stops_before_next_listing_preserves_partial(tmp_path):
    archive = MarketArchive(tmp_path / 'source', initialize=True)
    (archive.root / 'stage-a-profile.json').write_text(json.dumps({
        'maximum_daily_observations': 91, 'maximum_source_bytes': 512 * 1024 * 1024}))
    chosen = [{'provider': p, 'native_id': n, 'symbol': s, 'exchange': e} for p, n, s, e in LISTINGS]
    service = Mock()
    service.fetch.return_value = {'items': [{'synthetic': True}], 'new_revisions': 1}
    with patch('market_cortex.market_stage_a_acceptance.identities', return_value=chosen), \
         patch('market_cortex.market_stage_a_acceptance.HistoryService', return_value=service), \
         patch('market_cortex.market_stage_a_acceptance.verify_history_accuracy', return_value={'status': 'MISMATCH'}):
        with pytest.raises(ProviderFailure, match='STAGE_A_HISTORY_PROVENANCE_OR_VALUE_MISMATCH'):
            history_operation(archive, Mock())
        assert service.fetch.call_count == 1
        with pytest.raises(ProviderFailure, match='STAGE_A_HISTORY_ALREADY_STARTED_REVIEW_RECOVERY'):
            history_operation(archive, Mock())
    assert archive.integrity()['manifests'] == 1
