"""Explicit finite Stage A operations. Fail closed on recovery/scope/identity.

Never connects to SQL. An authenticated local owner protection receipt gates
provider reads; the viewer has no credentialed download route. No resume/reset
flag, automatic collector, schedule, gap backfill or application deployment.
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from .market_archive import MarketArchive, digest, stamp
from .market_data_cli import select
from .market_history import HistoryService, cached_candles
from .market_observation_audit import event_evidence
from .market_source_backup import file_hash, require, inventory
from .market_stage_a import LISTINGS, WINDOWS, approved_scope, StageATransport, verify_profile
from .market_stream import FeedWorker
from .multi_market_probe import verify_history_accuracy, feed_validation_code


def recovery_gates(owner_receipt, source_receipt, archive):
    owner = json.loads(Path(owner_receipt).read_text(encoding='utf-8-sig'))
    require(owner['status'] == 'VALIDATED_CURRENT_OWNER_BACKUP_AND_ISOLATED_RESTORE'
            and owner['phase'] == 'COMPLETE' and owner['source_unchanged']
            and owner['all_table_row_hashes_matched'] and owner['backup_retained'],
            'STAGE_A_OWNER_RECOVERY_NOT_VALIDATED')
    # Oct11 protection evidence is valid retained evidence, but cannot replace
    # the new backup explicitly required for this authorized Stage A operation.
    require(datetime.fromisoformat(owner['started_at']) >= datetime(2026, 10, 14, tzinfo=timezone.utc),
            'STAGE_A_NEW_OWNER_PROTECTION_REQUIRED')
    require(file_hash(Path(owner['retained_backup'])) == owner['backup_sha256'],
            'STAGE_A_OWNER_BACKUP_CHANGED')
    require(owner['restore']['catalog_inventory_verified'] and
            owner['research_replay']['evidence_reproducible'] and
            len(owner['research_replay']['checks']) == 6,
            'STAGE_A_OWNER_RESTORE_EVIDENCE_INCOMPLETE')
    cache = json.loads(Path(source_receipt).read_text(encoding='utf-8-sig'))
    require(cache['status'] == 'VALIDATED_SOURCE_BACKUP_AND_ISOLATED_RESTORE',
            'STAGE_A_SOURCE_RECOVERY_NOT_VALIDATED')
    require(file_hash(Path(cache['backup']['backup'])) == cache['backup']['sha256'] == cache['restore']['sha256'],
            'STAGE_A_SOURCE_BACKUP_CHANGED')
    recovered = MarketArchive(Path(cache['restore']['restore_root']))
    recovered.integrity()
    require([m['manifest_hash'] for m in recovered.manifests()] == cache['restore']['manifest_hashes'],
            'STAGE_A_SOURCE_RESTORE_CHANGED')
    require(set(cache['restore']['manifest_hashes']) <= {m['manifest_hash'] for m in archive.manifests()},
            'STAGE_A_SOURCE_LINEAGE_CHANGED')
    return {'owner_receipt_sha256': file_hash(Path(owner_receipt)),
            'source_receipt_sha256': file_hash(Path(source_receipt)),
            'owner_backup_sha256': owner['backup_sha256'],
            'source_backup_sha256': cache['backup']['sha256']}


def identities(archive, provider=None):
    values = []
    for p, native, symbol, exchange in LISTINGS:
        if provider and p != provider:
            continue
        selected = select(archive, p, [native])[0]
        require((selected['symbol'], selected['exchange']) == (symbol, exchange),
                'STAGE_A_NATIVE_IDENTITY_CHANGED')
        require(selected['status'] in {'LISTED', 'active'}, 'STAGE_A_LISTING_UNAVAILABLE')
        values.append(selected)
    return values


def history_operation(archive, transport):
    # Exactly one operation per listing. On a partial failure preserve receipts;
    # rerunning this operation needs a separately reviewed recovery scope.
    prior = [m for m in archive.manifests('requests')
             if m['metadata'].get('operation') in {'stage_a_history_started', 'stage_a_history_complete'}]
    require(not prior, 'STAGE_A_HISTORY_ALREADY_STARTED_REVIEW_RECOVERY')
    selected = identities(archive)
    profile = json.loads((archive.root / 'stage-a-profile.json').read_text())
    require(profile['maximum_daily_observations'] == 91 and profile['maximum_source_bytes'] == 512 * 1024 * 1024,
            'STAGE_A_PROFILE_BUDGET_CHANGED')
    archive.append('requests', 'upstox', [], sources=[], metadata={'operation': 'stage_a_history_started'})
    results, accepted = [], 0
    for item in selected:
        provider, native = item['provider'], item['native_id']
        start, end = WINDOWS[provider]
        approved_scope().require(provider, native, '1d', start, end)
        result = HistoryService(archive, transport=transport, max_pages=2, max_rows=13).fetch(
            item, '1d', start, end, refresh=True)
        require(0 < len(result['items']) <= 13, 'STAGE_A_HISTORY_UNAVAILABLE_OR_ROW_CAP')
        accepted += len(result['items'])
        require(accepted <= 91, 'STAGE_A_TOTAL_ROW_CAP')
        accuracy = verify_history_accuracy(item, result['items'], transport=transport)
        require(accuracy['status'] == 'EXACT_OHLCV_MATCH', 'STAGE_A_HISTORY_PROVENANCE_OR_VALUE_MISMATCH')
        # Repeat from the cache only. No additional provider request is made for
        # weekend/holiday gaps: daily broker session authority is still pending.
        pinned = cached_candles(archive, provider, native, '1d', start, end)
        require(digest(pinned) == digest(result['items']), 'STAGE_A_CACHE_REPLAY_MISMATCH')
        results.append({'provider': provider, 'native_id': native, 'symbol': item['symbol'],
            'exchange': item['exchange'], 'rows': len(pinned), 'new_revisions': result['new_revisions'],
            'items_hash': digest(pinned), 'accuracy': accuracy,
            'duplicate_cache_reads_add_rows': False})
        archive.append('requests', provider, [], sources=[], metadata={
            'operation': 'stage_a_listing_history_verified', 'native_id': native,
            'rows': len(pinned), 'items_hash': digest(pinned), 'accuracy': accuracy})
    archive.append('requests', 'upstox', [], sources=[], metadata={
        'operation': 'stage_a_history_complete', 'accepted_rows': accepted})
    return {'status': 'SEVEN_LISTING_HISTORY_VERIFIED', 'rows': accepted, 'listings': results}


class IndianSessionEvidence:
    """Provider-reported exchange segment status, not a fabricated holiday calendar."""
    def __init__(self):
        self.observations = []

    def __call__(self, payload):
        if not isinstance(payload, bytes):
            return
        from .feed_proto import MarketDataFeed_pb2 as protocol
        message = protocol.FeedResponse()
        message.ParseFromString(payload)
        if message.HasField('marketInfo'):
            states = {segment: protocol.MarketStatus.Name(status)
                      for segment, status in message.marketInfo.segmentStatus.items()
                      if segment in {'NSE_EQ', 'BSE_EQ'}}
            if states:
                self.observations.append({'received_at': stamp(), 'states': states,
                    'source_payload_sha256': hashlib.sha256(payload).hexdigest()})

    def require_active(self):
        require(self.observations and all(
            self.observations[-1]['states'].get(segment) == 'NORMAL_OPEN'
            for segment in ('NSE_EQ', 'BSE_EQ')), 'STAGE_A_INDIAN_ACTIVE_SESSION_NOT_CONFIRMED')


async def capture_operation(archive, provider, transport):
    if provider == 'upstox':
        # Admission window is conservative; actual NORMAL_OPEN segment evidence
        # from the official feed is required after capture, including holidays.
        from zoneinfo import ZoneInfo
        local = datetime.now(ZoneInfo('Asia/Kolkata'))
        require(local.weekday() < 5 and (9, 20) <= (local.hour, local.minute) < (15, 25),
                'STAGE_A_INDIAN_SESSION_WINDOW_CLOSED')
    prior = [m for m in archive.manifests('requests', provider)
             if m['metadata'].get('operation') == 'stage_a_capture_started']
    require(not prior, 'STAGE_A_CAPTURE_ALREADY_STARTED_REVIEW_REQUIRED')
    selected = (select(archive, 'binance', ['BTCUSDT', 'ETHUSDT']) if provider == 'binance'
                else identities(archive, provider))
    # Enforce the planned 64MiB capture reserve before any socket authorization.
    archive.assert_capacity(64 * 1024 * 1024)
    before = {m['manifest_hash'] for m in archive.manifests('events', provider)}
    indian = IndianSessionEvidence() if provider == 'upstox' else None
    worker = FeedWorker(archive, provider, selected, interval='1m', feed='iex',
                        transport=transport, payload_observer=indian, max_retries=5)
    archive.append('requests', provider, [], sources=[], metadata={
        'operation': 'stage_a_capture_started', 'seconds': 120,
        'native_ids': [i['native_id'] for i in selected], 'automatic_gap_recovery': False})
    stats = await worker.run(120)
    require(not stats['connected'] and not feed_validation_code(stats), 'STAGE_A_STREAM_AUTH_SUBSCRIPTION_OR_CAPTURE_FAILED')
    events = [r for m in archive.manifests('events', provider) if m['manifest_hash'] not in before
              for r in archive.rows(m)]
    evidence = {i['native_id']: event_evidence([r for r in events if r['native_id'] == i['native_id']])
                for i in selected}
    require(all(e['fresh_price_observations_received'] and e['fresh_distinct_event_timestamps'] >= 2
                for e in evidence.values()), 'STAGE_A_FRESH_LISTING_EVENTS_NOT_CONFIRMED')
    if indian:
        indian.require_active()
    result = {'status': 'BOUNDED_FRESH_FEED_VERIFIED', 'stats': stats, 'listings': evidence,
              'indian_session_evidence': indian.observations if indian else None,
              'delivery': 'EXCHANGE_WEBSOCKET_TO_CACHE_BROWSER_HTTP_POLLING',
              'collector_stopped': True, 'automatic_gap_recovery': False}
    archive.append('requests', provider, [], sources=[], metadata={
        'operation': 'stage_a_capture_complete', 'receipt': result})
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--owner-protection', type=Path, required=True)
    parser.add_argument('--source-protection', type=Path, required=True)
    parser.add_argument('--report', type=Path, required=True)
    parser.add_argument('--operation', choices=['history', 'binance', 'upstox', 'alpaca'], required=True)
    args = parser.parse_args(argv)
    require(not args.report.exists(), 'NEW_STAGE_A_OPERATION_REPORT_REQUIRED')
    result = {'started_at': stamp(), 'operation': args.operation, 'owner_writes': False,
              'database_access': False, 'schedules_enabled': False, 'cutover_performed': False}
    try:
        archive = MarketArchive(args.root, maximum_bytes=512 * 1024 * 1024)
        verify_profile(archive)
        result['recovery_gates'] = recovery_gates(args.owner_protection, args.source_protection, archive)
        transport = StageATransport(archive)
        result['before'] = archive.integrity()
        result['operation_result'] = (history_operation(archive, transport) if args.operation == 'history'
            else asyncio.run(capture_operation(archive, args.operation, transport)))
        result.update(status='VALIDATED_STAGE_A_SCOPED_OPERATION', integrity=archive.integrity(),
                      provider_get_admissions=transport.usage())
    except Exception as error:
        from .providers import ProviderFailure
        result.update(status='STOPPED_PRESERVE_PARTIAL_STATE', error_code=(
            error.code if isinstance(error, ProviderFailure) else 'STAGE_A_OPERATION_FAILED'))
    args.report.parent.mkdir(parents=True, exist_ok=True)
    with args.report.open('x', encoding='utf-8') as stream:
        json.dump(result, stream, indent=2)
    print(json.dumps({'status': result['status'], 'report': str(args.report.resolve()),
                      'error_code': result.get('error_code'), 'owner_writes': False}))
    return 0 if result['status'].startswith('VALIDATED_') else 1


if __name__ == '__main__':
    raise SystemExit(main())
