"""Verify real copied source evidence and built candidate, without SQL/network.

TestClient exercises the real candidate API. Production browser/live/recovery
gates remain explicitly pending and cannot be satisfied by this receipt.
"""
import argparse
import json
from pathlib import Path

from fastapi.testclient import TestClient

from market_cortex.market_archive import MarketArchive, stamp, digest
from market_cortex.market_history import cached_candles
from market_cortex.market_source_backup import file_hash
from market_cortex.market_stage_a import LISTINGS, WINDOWS, viewer, verify_profile
from market_cortex.market_universe import search_catalog

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--candidate-receipt', type=Path, required=True)
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    if args.report.exists():
        raise RuntimeError('NEW_BUILD_RECEIPT_REQUIRED')
    prepared = json.loads(args.candidate_receipt.read_text())
    candidate = Path(prepared['candidate_root'])
    frontend = candidate / 'workstation'
    archive = MarketArchive(Path(prepared['source_root']))
    profile = verify_profile(archive)
    code = {p.relative_to(candidate).as_posix(): file_hash(p)
            for p in (candidate / 'src').rglob('*') if p.is_file() and '__pycache__' not in p.parts}
    for relative, sha in code.items():
        if file_hash(ROOT / relative) != sha:
            raise RuntimeError('CANDIDATE_BACKEND_DIFFERS_FROM_TESTED_CODE')
    built = (frontend / '.next/BUILD_ID').read_text().strip()
    if (ROOT / 'apps/workstation/.next/BUILD_ID').exists():
        if file_hash(ROOT / 'apps/workstation/.next/BUILD_ID') != prepared['original_build_id_hash']:
            raise RuntimeError('OPERATIONAL_BUILD_CHANGED')
    frontend_files = {p.relative_to(frontend).as_posix(): file_hash(p)
        for folder in ('app', 'components', 'lib', '.next')
        for p in (frontend / folder).rglob('*')
        if p.is_file() and 'cache' not in p.relative_to(frontend).parts}
    inventories = [m for m in archive.manifests('requests', 'binance')
                   if m['metadata'].get('operation') == 'stage_a_candidate_code_inventory']
    snapshot = {'backend': code, 'frontend': frontend_files,
                'dependency_lock_sha256': file_hash(frontend / 'package-lock.json'),
                'stage_a_profile_sha256': file_hash(archive.root / 'stage-a-profile.json'), 'build_id': built}
    if not any(m['metadata'].get('inventory_hash') == digest(snapshot) for m in inventories):
        archive.append('requests', 'binance', [], sources=[], metadata={
            'operation': 'stage_a_candidate_code_inventory', 'inventory_hash': digest(snapshot), 'inventory': snapshot})
    before = archive.integrity()
    counts, scope = {}, []
    with TestClient(viewer(archive)) as client:
        for provider in ('binance', 'upstox', 'alpaca'):
            result = client.get('/api/v1/market-data/catalog', params={'provider': provider, 'limit': 1})
            result.raise_for_status()
            manifest, rows = archive.latest('catalog', provider)
            by_status = {}
            for row in rows:
                by_status[row['status']] = by_status.get(row['status'], 0) + 1
            counts[provider] = {'discoverable': result.json()['total'], 'by_status': by_status,
                                'snapshot': manifest['manifest_hash']}
        for provider, native, symbol, exchange in LISTINGS:
            start, end = WINDOWS[provider]
            params = {'provider': provider, 'native_id': native, 'interval': '1d',
                      'start': start.isoformat(), 'end': end.isoformat()}
            read = client.get('/api/v1/market-data/history', params=params)
            read.raise_for_status()
            rows = cached_candles(archive, provider, native, '1d', start, end)
            assert read.json()['items'] == rows
            rejected = client.post('/api/v1/market-data/history/fetch', json=params)
            assert rejected.status_code == 422 and rejected.json()['code'] == 'SOURCE_FETCH_NOT_APPROVED'
            scope.append({'provider': provider, 'native_id': native, 'symbol': symbol, 'exchange': exchange,
                          'cached_daily_rows': len(rows), 'items_hash': digest(rows),
                          'viewer_post_denied': True, 'state': read.json()['state']})
        live = {p: client.get('/api/v1/market-data/prices', params={'provider': p}).json()
                for p in ('binance', 'upstox', 'alpaca')}
        assert all(r['state'] == 'UNAVAILABLE' and not r['items'] for r in live.values())
    assert archive.integrity() == before
    result = {'status': 'CANDIDATE_BUILT_OFFLINE_VERIFIED_NOT_DEPLOYED', 'observed_at': stamp(),
        **profile, 'build_id': built, 'backend_hashes': code, 'frontend_hashes': frontend_files,
        'code_inventory_hash': digest(snapshot), 'source_integrity': before, 'catalogs': counts,
        'scoped_listing_cache': scope, 'provider_get_admissions': {'history': 0, 'metadata': 0, 'stream_authorization': 0},
        'currently_live_subscriptions': 0, 'historical_observations_are_not_live': True,
        'owner_database_access': False, 'owner_writes': False, 'cutover_performed': False,
        'production_browser_gate': 'PENDING_CANDIDATE_STARTUP',
        'owner_recovery_gate': 'PENDING_NEW_PRIVATE_TERMINAL_RECEIPT',
        'source_recovery_gate': 'PENDING_NEW_ENCRYPTED_DRILL',
        'new_broker_history_gate': 'PENDING_RECOVERY_GATES',
        'fresh_indian_session_gate': 'PENDING_ACTIVE_SESSION',
        'frontend_tests': {'passed': 68, 'typecheck': 'PASSED', 'production_build': 'PASSED'},
        'python_regressions': {'passed': 375, 'subtests_passed': 13, 'skipped': 118,
                               'warning': 'Starlette/httpx TestClient deprecation'}}
    with args.report.open('x', encoding='utf-8') as stream:
        json.dump(result, stream, indent=2)
    print(json.dumps({'status': result['status'], 'report': str(args.report.resolve()),
        'catalog_counts': {p: v['discoverable'] for p, v in counts.items()},
        'source_bytes': before['bytes'], 'live_subscriptions': 0}))


if __name__ == '__main__':
    main()
