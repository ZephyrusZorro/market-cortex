"""Retain and restore-test the populated owner backup. No owner record writes."""
from __future__ import annotations

import argparse
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID, uuid4

from psycopg import sql
from psycopg.conninfo import make_conninfo

from .backup import backup, restore
from .config import Settings
from .database import connect
from .operations import ROOT, catalog_for, load_profile, preflight
from .owner_migration import CLUSTER, DEFAULT_ADMIN, digest, file_hash, require
from .owner_onboarding import START, END
from .protection_inventory import read_inventory

RECEIPT = ROOT / 'runtime/owner-production-verification-abfa86482c814d57bef0d97223da4a9f.json'
ONBOARDING = ROOT / 'runtime/owner-onboarding-20473f58dfda42659c60bcf6668b12bb/report.json'


def expected_guard(settings, before, accepted):
    require(settings.environment == 'OWNER_MAIN' and settings.data_root.resolve() == Path('C:/MarketCortexData').resolve(), 'OWNER_PROFILE_REQUIRED')
    require(accepted['status'] == 'VALIDATED_READ_ONLY_OWNER_ACCEPTANCE_INVENTORY', 'ACCEPTANCE_RECEIPT_REQUIRED')
    current = preflight(settings, integrity=True)
    require(current['status'] == 'VALIDATED', 'OWNER_PREFLIGHT_FAILED')
    require(current['checks']['database_identity'] == accepted['preflight']['checks']['database_identity'], 'OWNER_IDENTITY_DIFFERS')
    require(before['counts'] == accepted['preflight']['checks']['table_counts']
            and before['schema_hash'] == accepted['schema_hash']
            and before['ledger'] == accepted['migration_history']['ledger']
            and before['row_hashes']['schema_migrations'] == accepted['migration_history']['utc_hash']
            and before['head'] == accepted['manifest_id'], 'OWNER_DIFFERS_FROM_ACCEPTED_STATE')
    require(current['checks']['storage'] == accepted['preflight']['checks']['storage'], 'OWNER_STORAGE_DIFFERS')
    with connect(settings.database_url) as c:
        c.execute('SET TRANSACTION READ ONLY')
        row = c.execute('SELECT payload FROM cortex_research_runs WHERE run_id=%s', (accepted['run_id'],)).fetchone()
        require(row and digest(row[0]) == accepted['research_payload_hash'], 'APPROVED_RESEARCH_DIFFERS')
    return current


def protect(settings, accepted, report_path, *, admin_dsn=DEFAULT_ADMIN,
            backup_parent=Path('C:/MarketCortexBackups'), restore_parent=Path('C:/MarketCortexRestoreDrills'),
            enforce_owner=True):
    result = {'status': 'IN_PROGRESS', 'owner_database_writes': False, 'migration_executed': False,
              'release': 'v1.0.1-operational', 'started_at': datetime.now(timezone.utc).isoformat()}
    report_path.parent.mkdir(parents=True, exist_ok=False)
    def publish():
        report_path.write_text(json.dumps(result, indent=2, default=str)+'\n', encoding='utf-8')
    publish()
    try:
        phrase = os.environ.get('MARKET_CORTEX_BACKUP_PASSPHRASE', '')
        require(len(phrase) >= 16, 'RETAINED_BACKUP_PASSPHRASE_REQUIRED')
        before = read_inventory(settings.database_url)
        result['phase'] = 'READ_ONLY_SOURCE_INVENTORY'
        if enforce_owner:
            result['preflight'] = expected_guard(settings, before, accepted)
        with connect(admin_dsn) as c:
            c.execute('SET TRANSACTION READ ONLY')
            port, directory, version = c.execute("SELECT inet_server_port(),current_setting('data_directory'),current_setting('server_version_num')").fetchone()
            # The admin database can be SQL_ASCII; the NEW restore database is
            # explicitly UTF8. Never alter existing admin/pilot encodings.
            require(port == 55432 and Path(directory).resolve() == CLUSTER.resolve() and int(version)//10000 == 17, 'RECOVERY_CLUSTER_DIFFERS')
        nonce = uuid4().hex
        name = 'mc_protection_' + nonce + '_test'
        bundle = backup_parent / ('owner-current-' + nonce + '.mcbackup')
        recovered_root = restore_parent / ('owner-current-' + nonce)
        require(not bundle.exists() and not recovered_root.exists() and len(name.encode()) <= 63, 'RECOVERY_TARGET_COLLISION')
        result.update(phase='RETAINED_ENCRYPTED_BACKUP', retained_backup=str(bundle),
                      isolated_database=name, restore_data_root=str(recovered_root), source_inventory=before)
        publish()
        metadata = {}
        if enforce_owner:
            import yaml
            owner_file = ROOT/'config/owner.yaml'
            require(owner_file.stat().st_size <= 16384, 'OWNER_METADATA_TOO_LARGE')
            local = yaml.safe_load(owner_file.read_text(encoding='utf-8'))
            keys = ('base_currency','secondary_display_currency','timezone','preferred_market_sessions',
                    'review_times','enabled_markets','ai_privacy','storage_budget','AI_model_budget',
                    'market_data_budget','default_research_horizon','risk_display_preferences')
            require(isinstance(local,dict), 'INVALID_OWNER_METADATA')
            metadata = {'operational_release':'v1.0.1-operational',
                        'release_commit':'cfe696d51b137566c15eebaf734ff7ee0ca95197',
                        'owner_configuration':{k:local[k] for k in keys if k in local},
                        'accepted_research_run':accepted['run_id'],
                        'accepted_research_payload_hash':accepted['research_payload_hash'],
                        'restore_rule':'Isolated restore only; no migration rerun or overwrite of owner'}
        result['backup'] = backup(settings, bundle, phrase, recovery_metadata=metadata)
        result['backup_sha256'] = file_hash(bundle)
        require(result['backup']['catalog_inventory'] == before, 'SOURCE_CHANGED_DURING_BACKUP')
        require(read_inventory(settings.database_url) == before, 'SOURCE_CHANGED_DURING_BACKUP')
        target = make_conninfo(admin_dsn, dbname=name)
        with connect(admin_dsn) as c:
            c.autocommit = True
            c.execute(sql.SQL("CREATE DATABASE {} TEMPLATE template0 ENCODING 'UTF8'").format(sql.Identifier(name)))
        result.update(phase='ISOLATED_RESTORE', isolated_database_created=True)
        publish()
        recovered_root.mkdir(parents=True)
        result['restore'] = restore(bundle, recovered_root, target, settings.database_url, phrase)
        require(read_inventory(target) == before, 'RESTORED_CATALOG_DIFFERS')
        recovered_settings = Settings(target, recovered_root, settings.owner_timezone, settings.base_currency,
                                      False, settings.owner_configured, 'DEVELOPMENT_TEST')
        result['restored_integrity'] = preflight(recovered_settings, integrity=True)
        require(result['restored_integrity']['status'] == 'VALIDATED', 'RESTORED_STORAGE_INTEGRITY_FAILED')
        storage = result['restored_integrity']['checks']['storage']
        require(storage['referenced'] == result['backup']['artifact_count'] and not storage['unreferenced']
                and storage['staged_count'] == 0, 'RESTORED_FILE_INVENTORY_DIFFERS')
        if enforce_owner:
            source = json.loads(ONBOARDING.read_text(encoding='utf-8-sig'))
            restored_catalog = catalog_for(recovered_settings)
            result['pinned_replay'] = []
            for item in source['identities']:
                bars = restored_catalog.bars(instrument_id=UUID(item['instrument_id']), start=START, end=END,
                    as_of=datetime.fromisoformat(source['pinned_as_of']), manifest_id=UUID(source['pinned_manifest']), provider_id='binance')[1]
                require(digest([b.model_dump(mode='json') for b in bars]) == source['frozen_bar_hashes'][item['symbol']], 'RESTORED_PINNED_REPLAY_DIFFERS')
                result['pinned_replay'].append({'symbol':item['symbol'], 'sessions':len(bars), 'hash_matched':True})
            from .cortex import CortexService
            result['research_replay'] = CortexService(restored_catalog, recovered_settings).replay(UUID(accepted['run_id']))
            require(result['research_replay']['evidence_reproducible']
                    and len(result['research_replay']['checks']) == 6, 'RESTORED_RESEARCH_REPLAY_DIFFERS')
        require(read_inventory(settings.database_url) == before, 'SOURCE_CHANGED_DURING_RECOVERY')
        require(file_hash(bundle) == result['backup_sha256'], 'RETAINED_BACKUP_CHANGED')
        result.update(status='VALIDATED_CURRENT_OWNER_BACKUP_AND_ISOLATED_RESTORE', phase='COMPLETE',
                      source_unchanged=True, all_table_row_hashes_matched=True, backup_retained=True)
    except (Exception, KeyboardInterrupt) as error:
        candidate = str(error) if isinstance(error, ValueError) else ''
        result.update(status='FAILED_STOPPED', error_code=candidate if re.fullmatch('[A-Z0-9_]{1,100}',candidate) else type(error).__name__,
                      recovery_action='Preserve backup, isolated database, data directory and receipt. Inspect; do not rerun blindly or restore over owner.')
    publish()
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--profile', type=Path, default=ROOT/'config/operations-owner.example.json')
    args = parser.parse_args()
    path = ROOT/'runtime'/('owner-protection-'+uuid4().hex)/'report.json'
    try:
        _, settings = load_profile(args.profile)
        accepted = json.loads(RECEIPT.read_text(encoding='utf-8-sig'))
        result = protect(settings, accepted, path)
        print(json.dumps({'status':result['status'], 'report':str(path), 'error_code':result.get('error_code'), 'owner_database_writes':False}))
        return 0 if result['status'].startswith('VALIDATED_') else 1
    except Exception as error:
        candidate = str(error) if type(error) is ValueError else ''
        print(json.dumps({'status':'FAILED_BEFORE_BACKUP', 'error_code':candidate if re.fullmatch('[A-Z0-9_]{1,100}', candidate) else type(error).__name__}))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
