"""Independent read-only checks of the new owner restore and source recovery.

No owner connection, record writes, migrations, database creation or restore.
"""
import argparse
import json
from pathlib import Path
from uuid import UUID

from psycopg.conninfo import make_conninfo

from market_cortex.config import Settings
from market_cortex.cortex import CortexService
from market_cortex.database import connect
from market_cortex.market_archive import MarketArchive, stamp
from market_cortex.market_source_backup import file_hash, inventory, require
from market_cortex.market_stage_a_acceptance import recovery_gates
from market_cortex.operations import preflight, catalog_for
from market_cortex.owner_migration import CLUSTER, DEFAULT_ADMIN
from market_cortex.owner_onboarding import START, END
from market_cortex.protection_inventory import read_inventory
from market_cortex.market_archive import digest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--owner-report', type=Path, required=True)
    parser.add_argument('--source-report', type=Path, required=True)
    parser.add_argument('--source-root', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    require(not args.output.exists(), 'NEW_RECOVERY_AUDIT_REQUIRED')
    archive = MarketArchive(args.source_root)
    gates = recovery_gates(args.owner_report, args.source_report, archive)
    report = json.loads(args.owner_report.read_text(encoding='utf-8-sig'))
    name = report['isolated_database']
    require(name.startswith('mc_protection_') and name.endswith('_test'), 'ISOLATED_RECOVERY_IDENTITY_REQUIRED')
    root = Path(report['restore_data_root']).resolve()
    require(root.parent == Path('C:/MarketCortexRestoreDrills').resolve(), 'ISOLATED_RECOVERY_ROOT_REQUIRED')
    with connect(DEFAULT_ADMIN) as connection:
        connection.execute('SET TRANSACTION READ ONLY')
        port, directory, version = connection.execute(
            "SELECT inet_server_port(),current_setting('data_directory'),current_setting('server_version_num')").fetchone()
        require(port == 55432 and Path(directory).resolve() == CLUSTER.resolve() and int(version) // 10000 == 17,
                'ISOLATED_CLUSTER_IDENTITY_CHANGED')
    target = make_conninfo(DEFAULT_ADMIN, dbname=name)
    current = read_inventory(target)
    require(current == report['source_inventory'], 'RESTORED_FULL_INVENTORY_CHANGED')
    settings = Settings(target, root, 'Asia/Kolkata', 'INR', False, True, 'DEVELOPMENT_TEST')
    checked = preflight(settings, integrity=True)
    require(checked['status'] == 'VALIDATED', 'RESTORED_PREFLIGHT_FAILED')
    catalog = catalog_for(settings)
    replay = CortexService(catalog, settings).replay(UUID(report['research_replay']['run_id']))
    require(replay['evidence_reproducible'] and len(replay['checks']) == 6
            and all(c['matched'] for c in replay['checks']), 'RESTORED_SAVED_RESEARCH_CHANGED')
    base = Path(__file__).resolve().parents[1]
    onboarding = json.loads((base / 'runtime/owner-onboarding-20473f58dfda42659c60bcf6668b12bb/report.json').read_text())
    from datetime import datetime
    pinned = []
    for item in onboarding['identities']:
        bars = catalog.bars(instrument_id=UUID(item['instrument_id']), start=START, end=END,
            as_of=datetime.fromisoformat(onboarding['pinned_as_of']),
            manifest_id=UUID(onboarding['pinned_manifest']), provider_id='binance')[1]
        require(digest([b.model_dump(mode='json') for b in bars]) == onboarding['frozen_bar_hashes'][item['symbol']],
                'RESTORED_PINNED_BAR_HASH_CHANGED')
        pinned.append({'symbol': item['symbol'], 'sessions': len(bars), 'hash_matched': True})
    cache = json.loads(args.source_report.read_text())
    recovered = MarketArchive(Path(cache['restore']['restore_root']))
    require(inventory(recovered) == inventory(archive), 'CURRENT_SOURCE_DIFFERS_FROM_PROTECTED_SNAPSHOT')
    result = {'status': 'VALIDATED_STAGE_A_BOTH_RECOVERY_GATES', 'observed_at': stamp(), 'gates': gates,
        'owner_connected': False, 'owner_database_writes': False, 'isolated_database_read_only': True,
        'owner_restore_inventory_matches_all_tables': True, 'table_count': len(current['counts']),
        'verified_migrations': len(current['ledger']), 'observations': current['counts']['observations'],
        'research_records': current['counts']['cortex_research_runs'], 'restored_storage': checked['checks']['storage'],
        'pinned_replay': pinned, 'research_replay': replay, 'source_restore': recovered.integrity(),
        'source_equals_authenticated_restore': True, 'backups_retained': True}
    with args.output.open('x', encoding='utf-8') as stream:
        json.dump(result, stream, indent=2)
    print(json.dumps({'status': result['status'], 'report': str(args.output.resolve()),
        'tables': result['table_count'], 'migrations': result['verified_migrations'],
        'observations': result['observations'], 'research_hashes_matched': len(replay['checks'])}))


if __name__ == '__main__':
    main()
