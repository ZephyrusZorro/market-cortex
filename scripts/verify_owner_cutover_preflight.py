"""Private, read-only Stage A cutover guard; never starts applications or writes SQL."""
import argparse
from dataclasses import replace
from datetime import datetime, timezone
import json
from pathlib import Path
from uuid import UUID, uuid4

from psycopg.conninfo import make_conninfo

from market_cortex.cortex import CortexService
from market_cortex.market_source_backup import file_hash, require
from market_cortex.operations import load_profile, preflight, catalog_for
from market_cortex.protection_inventory import read_inventory

ROOT = Path(__file__).resolve().parents[1]
ACCEPTANCE = ROOT / 'runtime/stage-a-final-acceptance-2026-10-15.json'


def validate_owner(settings, baseline):
    require(settings.environment == 'OWNER_MAIN' and
            settings.data_root.resolve() == Path('C:/MarketCortexData').resolve(), 'OWNER_PROFILE_REQUIRED')
    require(bool(settings.database_url), 'PRIVATE_OWNER_CONNECTION_REQUIRED')
    # Enforce read-only defaults on every catalog/replay connection, in addition
    # to the explicit repeatable-read transaction used by read_inventory.
    readonly = replace(settings, database_url=make_conninfo(settings.database_url,
        options='-c default_transaction_read_only=on -c statement_timeout=60000'))
    checked = preflight(readonly, integrity=True)
    require(checked['status'] == 'VALIDATED', 'OWNER_PREFLIGHT_FAILED')
    identity = checked['checks']['database_identity']
    require(identity['database'] == 'market_cortex' and identity['server_port'] == 5432
            and identity['transaction_read_only'] == 'on', 'OWNER_IDENTITY_REQUIRED')
    current = read_inventory(readonly.database_url)
    require(current == baseline['source_inventory'], 'OWNER_FULL_INVENTORY_CHANGED')
    require(len(current['counts']) == 51 and len(current['ledger']) == 13
            and current['counts']['observations'] == 1825
            and current['counts']['dataset_files'] == 65, 'OWNER_EXPECTED_COUNTS_CHANGED')
    replay = CortexService(catalog_for(readonly), readonly).replay(UUID(baseline['research_replay']['run_id']))
    require(replay['evidence_reproducible'] and len(replay['checks']) == 6
            and all(c['matched'] for c in replay['checks']), 'OWNER_RESEARCH_REPLAY_CHANGED')
    require(read_inventory(readonly.database_url) == current, 'OWNER_CHANGED_DURING_PREFLIGHT')
    return {'preflight': checked, 'full_inventory': current, 'research_replay': replay,
            'all_owner_row_fingerprints_match_backup': True}


def validate_snapshot(path):
    snapshot = json.loads(path.read_text(encoding='utf-8-sig'))
    require(snapshot['status'] == 'VERIFIED_APPLICATION_COPY_AND_ISOLATED_EXTRACTION', 'APPLICATION_RECOVERY_NOT_VERIFIED')
    require(Path(snapshot['original_root']).resolve() == ROOT, 'APPLICATION_ORIGINAL_ROOT_CHANGED')
    require(file_hash(Path(snapshot['bundle'])) == snapshot['bundle_sha256'], 'APPLICATION_COPY_CHANGED')
    for relative, expected in snapshot['files'].items():
        member = Path(relative)
        require(not member.is_absolute() and '..' not in member.parts, 'APPLICATION_MEMBER_INVALID')
        require(file_hash(ROOT / member) == expected, 'ORIGINAL_APPLICATION_CHANGED_AFTER_COPY')
        require(file_hash(Path(snapshot['isolated_restore']) / member) == expected, 'APPLICATION_RECOVERY_CHANGED')
    return {'snapshot_receipt': str(path.resolve()), 'snapshot_receipt_sha256': file_hash(path),
            'bundle_sha256': snapshot['bundle_sha256'], 'verified_files': len(snapshot['files'])}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--snapshot-receipt', type=Path, required=True)
    args = parser.parse_args()
    result = {'status': 'STOPPED_BEFORE_CUTOVER', 'owner_database_writes': False,
              'application_started': False, 'observed_at': datetime.now(timezone.utc).isoformat()}
    try:
        accepted = json.loads(ACCEPTANCE.read_text())
        require(accepted['status'] == 'STAGE_A_ALL_PRE_CUTOVER_GATES_PASSED', 'ACCEPTANCE_REQUIRED')
        for item in accepted['receipts'].values():
            require(file_hash(Path(item['path'])) == item['sha256'], 'ACCEPTANCE_EVIDENCE_CHANGED')
        for key, field in [('owner_protection', 'retained_backup'), ('source_protection', None)]:
            report = json.loads(Path(accepted['receipts'][key]['path']).read_text())
            bundle = report[field] if field else report['backup']['backup']
            expected = report['backup_sha256'] if field else report['backup']['sha256']
            require(file_hash(Path(bundle)) == expected, 'RETAINED_BACKUP_CHANGED')
        result['application_recovery'] = validate_snapshot(args.snapshot_receipt)
        owner = json.loads(Path(accepted['receipts']['owner_protection']['path']).read_text())
        _, settings = load_profile(ROOT / 'config/operations-owner.example.json')
        result.update(validate_owner(settings, owner))
        result['status'] = 'VALIDATED_PRIVATE_OWNER_CUTOVER_PREFLIGHT'
    except Exception as error:
        # Never include a driver exception, connection string or raw error text.
        from market_cortex.providers import ProviderFailure
        result['error_code'] = error.code if isinstance(error, ProviderFailure) else type(error).__name__
    output = ROOT / 'runtime' / ('owner-cutover-preflight-' + uuid4().hex + '.json')
    with output.open('x', encoding='utf-8') as stream:
        json.dump(result, stream, indent=2, default=str)
    print(json.dumps({'status': result['status'], 'report': str(output),
                      'owner_database_writes': False, 'error_code': result.get('error_code')}))
    return 0 if result['status'] == 'VALIDATED_PRIVATE_OWNER_CUTOVER_PREFLIGHT' else 1


if __name__ == '__main__':
    raise SystemExit(main())
