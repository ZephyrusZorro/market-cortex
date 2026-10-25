"""Human-authorized, one-time 90-second IEX browser acceptance addendum.

Original 120-second captures remain untouched. No REST data requests, SQL,
history, recovery backfill, continuous collection, scheduler or cutover.
"""
import argparse
import asyncio
import json
from pathlib import Path
from datetime import datetime, time, timezone
from zoneinfo import ZoneInfo

from .market_archive import MarketArchive, stamp
from .market_observation_audit import event_evidence
from .market_source_backup import require, file_hash
from .market_stage_a import StageATransport, verify_profile
from .market_stage_a_acceptance import recovery_gates, identities
from .market_stream import FeedWorker
from .multi_market_probe import feed_validation_code


def require_capture_window(now=None):
    """Conservative admission only; actual fresh events still prove the feed.

    This does not certify holidays. Refuse closed hours before consuming the
    one-time authorization or creating source records; handle DST in New York.
    """
    current = (now or datetime.now(timezone.utc)).astimezone(ZoneInfo('America/New_York'))
    require(current.weekday() < 5 and time(9, 35) <= current.time() <= time(15, 55),
            'SUPPLEMENTAL_IEX_ACTIVE_SESSION_WINDOW_REQUIRED')


async def supplement(archive):
    require_capture_window()
    requests = archive.manifests('requests', 'alpaca')
    require(any(m['metadata'].get('operation') == 'stage_a_capture_complete' for m in requests),
            'ORIGINAL_IEX_CAPTURE_REQUIRED')
    require(not any(m['metadata'].get('operation') == 'stage_a_supplemental_iex_90_started' for m in requests),
            'SUPPLEMENTAL_IEX_ALREADY_STARTED_REVIEW_REQUIRED')
    archive.assert_capacity(64 * 1024 * 1024)
    selected = identities(archive, 'alpaca')
    before = {m['manifest_hash'] for m in archive.manifests('events', 'alpaca')}
    usage = StageATransport(archive).usage()
    archive.append('requests', 'alpaca', [], sources=[], metadata={
        'operation': 'stage_a_supplemental_iex_90_started', 'seconds': 90,
        'authorization': 'Human owner explicitly authorized supplemental 90-second IEX capture on 2026-10-15',
        'native_ids': [i['native_id'] for i in selected], 'maximum_events': 200_000,
        'additional_rest_requests_allowed': 0, 'automatic_gap_recovery': False,
        'maximum_connections': 1, 'maximum_reconnects': 0,
        'operation_code_sha256': file_hash(Path(__file__))})
    worker = FeedWorker(archive, 'alpaca', selected, feed='iex', interval='1m', max_retries=0)
    stats = await worker.run(90)
    require(not stats['connected'] and not feed_validation_code(stats), 'SUPPLEMENTAL_IEX_FEED_NOT_VERIFIED')
    events = [r for m in archive.manifests('events', 'alpaca') if m['manifest_hash'] not in before
              for r in archive.rows(m)]
    evidence = {i['native_id']: event_evidence([r for r in events if r['native_id'] == i['native_id']])
                for i in selected}
    require(all(e['fresh_price_observations_received'] and e['fresh_distinct_event_timestamps'] >= 2
                for e in evidence.values()), 'SUPPLEMENTAL_FRESH_IEX_OBSERVATIONS_NOT_VERIFIED')
    require(StageATransport(archive).usage() == usage, 'SUPPLEMENTAL_UNEXPECTED_REST_REQUEST')
    result = {'status': 'SUPPLEMENTAL_BOUNDED_IEX_VERIFIED', 'stats': stats, 'listings': evidence,
              'collector_stopped': True, 'additional_rest_requests': 0, 'capture_seconds': 90}
    archive.append('requests', 'alpaca', [], sources=[], metadata={
        'operation': 'stage_a_supplemental_iex_90_complete', 'receipt': result})
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', required=True, type=Path)
    parser.add_argument('--owner-protection', required=True, type=Path)
    parser.add_argument('--source-protection', required=True, type=Path)
    parser.add_argument('--report', required=True, type=Path)
    args = parser.parse_args(argv)
    require(not args.report.exists(), 'NEW_SUPPLEMENTAL_REPORT_REQUIRED')
    result = {'started_at': stamp(), 'owner_writes': False, 'database_access': False,
              'cutover_performed': False, 'continuous_collection': False, 'scheduled_jobs': False}
    try:
        archive = MarketArchive(args.root, maximum_bytes=512 * 1024 * 1024)
        verify_profile(archive)
        result['recovery_gates'] = recovery_gates(args.owner_protection, args.source_protection, archive)
        result['capture'] = asyncio.run(supplement(archive))
        result.update(status='VALIDATED_SUPPLEMENTAL_STAGE_A_IEX', integrity=archive.integrity())
    except Exception as error:
        from .providers import ProviderFailure
        result.update(status='STOPPED_PRESERVE_PARTIAL_STATE', error_code=(
            error.code if isinstance(error, ProviderFailure) else 'SUPPLEMENTAL_CAPTURE_FAILED'))
    with args.report.open('x', encoding='utf-8') as stream:
        json.dump(result, stream, indent=2)
    print(json.dumps({'status': result['status'], 'report': str(args.report.resolve()),
                      'owner_writes': False, 'error_code': result.get('error_code')}))
    return 0 if result['status'].startswith('VALIDATED_') else 1


if __name__ == '__main__':
    raise SystemExit(main())
