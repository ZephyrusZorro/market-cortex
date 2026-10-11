"""The explicitly approved owner backup/restore/schema-upgrade procedure.

Credentials and backup passphrase are environment-only. No owner reset, sample
records, rollback/cutover, backup deletion, or production launch is provided.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
from datetime import datetime, timezone
from uuid import uuid4

from psycopg import sql
from psycopg.conninfo import conninfo_to_dict, make_conninfo

from .backup import backup, restore
from .config import Settings
from .database import connect, migrate
from .operations import ROOT, load_profile, preflight

PLAN_DIGEST = '74a1043c1eb0740d50f2e663e3f8995f6119c136292309cb3bf82b5ab94d624b'
DEFAULT_ADMIN = 'host=127.0.0.1 port=55432 dbname=postgres user=cortex_test'
CLUSTER = Path('C:/Users/faris/Downloads/MARKET_CORTEX_Phase_1_Foundation_2026-09-30/market-cortex/runtime/pg_phase1')


def digest(value) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), default=str).encode()).hexdigest()


def file_hash(path: Path) -> str:
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def require(condition: bool, code: str):
    if not condition:
        raise ValueError(code)


def approved_plan() -> dict:
    path = ROOT / 'docs/operations/DEPLOYMENT_OWNER_MIGRATION_PLAN.json'
    require(file_hash(path) == PLAN_DIGEST, 'APPROVED_PLAN_CHANGED')
    plan = json.loads(path.read_text(encoding='utf-8'))
    for item in plan['migrations']:
        path = ROOT / 'infra/migrations' / item['name']
        require(hashlib.sha256(path.read_text(encoding='utf-8').encode()).hexdigest() == item['sha256'],
                'APPROVED_MIGRATION_CHANGED')
    return plan


def snapshot(connection, *, original: dict | None = None) -> dict:
    """Read bounded catalog metadata/row hashes; never return row payloads."""
    connection.execute("SET LOCAL timezone='UTC'")
    connection.execute("SET LOCAL statement_timeout='60s'")
    schema = connection.execute('SELECT current_schema()').fetchone()[0]
    tables = connection.execute("""SELECT schemaname,tablename FROM pg_tables
        WHERE schemaname !~ '^pg_' AND schemaname <> 'information_schema' ORDER BY 1,2""").fetchall()
    require(all(s == schema for s, _ in tables), 'UNINSPECTED_SCHEMA_TABLES_PRESENT')
    columns = connection.execute("""SELECT table_name,column_name,ordinal_position,udt_schema,udt_name,
        is_nullable,column_default FROM information_schema.columns
        WHERE table_schema=%s ORDER BY table_name,ordinal_position""", (schema,)).fetchall()
    constraints = connection.execute("""SELECT r.relname,k.conname,pg_get_constraintdef(k.oid)
        FROM pg_constraint k JOIN pg_class r ON r.oid=k.conrelid JOIN pg_namespace n ON n.oid=r.relnamespace
        WHERE n.nspname=%s ORDER BY 1,2""", (schema,)).fetchall()
    indexes = connection.execute('SELECT tablename,indexname,indexdef FROM pg_indexes WHERE schemaname=%s ORDER BY 1,2',
                                 (schema,)).fetchall()
    column_names = {name: [r[1] for r in columns if r[0] == name] for _, name in tables}
    counts, row_hashes = {}, {}
    for _, name in tables:
        table = sql.Identifier(schema, name)
        count = connection.execute(sql.SQL('SELECT count(*) FROM {}').format(table)).fetchone()[0]
        require(count <= 13, 'MATERIAL_RECORD_COUNT_CHANGE')
        counts[name] = count
        selected = original['columns'][name] if original and name in original['columns'] else column_names[name]
        query = sql.SQL('SELECT to_jsonb(r) FROM (SELECT {} FROM {}').format(
            sql.SQL(',').join(map(sql.Identifier, selected)), table)
        params = ()
        if original and name == 'schema_migrations':
            query += sql.SQL(' WHERE name = ANY(%s)')
            params = (list(original['ledger']),)
        query += sql.SQL(') r')
        records = connection.execute(query, params).fetchall()
        row_hashes[name] = digest(sorted(digest(row[0]) for row in records))
    ledger = dict(connection.execute('SELECT name,checksum FROM schema_migrations ORDER BY name'))
    head = connection.execute('SELECT manifest_id FROM dataset_head WHERE singleton=true').fetchall()
    identity = connection.execute("""SELECT current_database(),host(inet_server_addr()),inet_server_port(),
        current_setting('server_version'),(SELECT oid FROM pg_database WHERE datname=current_database())""").fetchone()
    return {'identity': dict(zip(('database', 'address', 'port', 'version', 'database_oid'), identity)),
            'schema': schema, 'columns': column_names, 'counts': counts, 'row_hashes': row_hashes,
            'ledger': ledger, 'head': [str(row[0]) if row[0] else None for row in head],
            'schema_hash': digest([columns, constraints, indexes])}


def read_snapshot(dsn: str, *, original=None) -> dict:
    with connect(dsn) as connection:
        connection.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY')
        return snapshot(connection, original=original)


def unchanged(actual: dict, before: dict, *, compare_identity=True):
    for key in ('counts', 'row_hashes', 'ledger', 'schema_hash', 'head', 'schema', 'columns'):
        require(actual[key] == before[key], 'MATERIAL_LIVE_STATE_CHANGE')
    if compare_identity:
        require(actual['identity'] == before['identity'], 'LIVE_DATABASE_IDENTITY_CHANGED')


def verified_upgrade(actual: dict, before: dict, rehearsed: dict, pending: list[str]):
    require(actual['schema_hash'] == rehearsed['schema_hash'], 'UPGRADED_SCHEMA_DIFFERS_FROM_REHEARSAL')
    require(actual['counts'] == rehearsed['counts'], 'UPGRADED_RECORD_COUNTS_DIFFER')
    require(actual['ledger'] == rehearsed['ledger'], 'UPGRADED_MIGRATION_CHECKSUMS_DIFFER')
    require(actual['head'] == before['head'], 'EXISTING_HEAD_CHANGED')
    for name, expected in before['row_hashes'].items():
        require(actual['row_hashes'][name] == expected, 'EXISTING_RECORDS_CHANGED')
    require(set(actual['ledger']) - set(before['ledger']) == set(pending), 'UNEXPECTED_MIGRATIONS')


def execute(settings: Settings, plan: dict, expected_identity: dict, admin_dsn: str,
            backup_parent: Path, restore_parent: Path, report_path: Path) -> dict:
    """Trusted CLI engine; integration tests exercise it only on fresh *_test DBs."""
    result = {'status': 'RUNNING', 'environment': settings.environment,
              'authorization': 'USER_EXPLICIT_BACKUP_RESTORE_0003_THROUGH_0013',
              'owner_migration_attempted': False, 'owner_migration_committed': False,
              'production_runtime': 'SEPARATE_POLICY_BLOCKER; NOT_LAUNCHED'}
    def publish():
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(result, indent=2, default=str), encoding='utf-8')
    try:
        result['phase'] = 'LIVE_READ_ONLY_BASELINE'
        before = read_snapshot(settings.database_url)
        require(before['identity']['address'] in {'127.0.0.1', '::1'}, 'LIVE_SERVER_MUST_BE_LOOPBACK')
        require(all(before['identity'][k] == v for k, v in expected_identity.items()), 'LIVE_IDENTITY_DIFFERS_FROM_INSPECTED')
        require(before['counts'] == plan['existing_table_counts'], 'MATERIAL_LIVE_RECORD_COUNT_CHANGE')
        require(before['head'] == [None], 'MATERIAL_LIVE_HEAD_CHANGE')
        old = sorted((ROOT / 'infra/migrations').glob('000[12]_*.sql'))
        expected_ledger = {p.name: hashlib.sha256(p.read_text(encoding='utf-8').encode()).hexdigest() for p in old}
        require(before['ledger'] == expected_ledger, 'LIVE_MIGRATION_HISTORY_DIFFERS')
        require(settings.data_root.is_dir() and not any(settings.data_root.iterdir()), 'MATERIAL_OWNER_DATA_ROOT_CHANGE')
        inventory = preflight(settings, integrity=True)
        pending = [m['name'] for m in plan['migrations']]
        require(inventory['checks'].get('pending_migrations') == pending and
                not inventory['checks'].get('changed_migrations') and
                inventory['checks'].get('storage', {}).get('referenced') == 0 and
                not inventory['checks']['storage']['missing'] and not inventory['checks']['storage']['corrupt'],
                'LIVE_PREFLIGHT_DIFFERS')
        with connect(settings.database_url) as c:
            c.execute('SET TRANSACTION READ ONLY')
            privileged = c.execute("""SELECT has_schema_privilege(current_schema(),'CREATE'),
                has_table_privilege('schema_migrations','INSERT'),
                (SELECT rolsuper FROM pg_roles WHERE rolname=current_user) OR
                (SELECT pg_has_role(relowner,'USAGE') FROM pg_class WHERE oid='jobs'::regclass)""").fetchone()
            require(all(privileged), 'OWNER_DDL_PRIVILEGES_REQUIRED')
        result['baseline'] = before
        result['owner_preflight_before'] = inventory
        # The admin must identify a separate PostgreSQL instance; no owner CREATE DATABASE.
        result['phase'] = 'ISOLATED_RESTORE_CONFIGURATION'
        info = conninfo_to_dict(admin_dsn)
        require(info.get('host') in {'127.0.0.1', 'localhost', '::1'} and
                info.get('hostaddr') in {None, '127.0.0.1', '::1'} and
                not info.get('options') and not info.get('service'), 'RESTORE_ADMIN_MUST_BE_LOOPBACK')
        with connect(admin_dsn) as c:
            c.execute('SET TRANSACTION READ ONLY')
            port, version = c.execute("SELECT inet_server_port(),current_setting('server_version_num')").fetchone()
            require((settings.environment != 'OWNER_MAIN' or port != before['identity']['port']) and
                    int(version) // 10000 == 17, 'RESTORE_CLUSTER_NOT_ISOLATED')
        phrase = os.environ.get('MARKET_CORTEX_BACKUP_PASSPHRASE', '')
        require(len(phrase) >= 16, 'RETAINED_BACKUP_PASSPHRASE_REQUIRED')
        nonce = uuid4().hex
        bundle = backup_parent / ('owner-before-schema-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '-' + nonce + '.mcbackup')
        restored_root = restore_parent / nonce
        require(not restored_root.exists(), 'RESTORE_ROOT_ALREADY_EXISTS')
        result['retained_backup'] = str(bundle)
        result['restore_data_root'] = str(restored_root)
        publish()
        # Freeze reviewed SQL copies for both rehearsed and owner migration calls.
        with tempfile.TemporaryDirectory(prefix='market-cortex-reviewed-migrations-') as directory:
            reviewed = Path(directory)
            destination = reviewed / 'infra/migrations'
            destination.mkdir(parents=True)
            for path in sorted((ROOT / 'infra/migrations').glob('[0-9]*.sql')):
                raw = path.read_text(encoding='utf-8')
                expected = expected_ledger.get(path.name) or next((m['sha256'] for m in plan['migrations'] if m['name'] == path.name), None)
                require(hashlib.sha256(raw.encode()).hexdigest() == expected, 'REVIEWED_MIGRATION_SET_CHANGED')
                (destination / path.name).write_text(raw, encoding='utf-8')
            result['phase'] = 'RETAINED_ENCRYPTED_BACKUP'
            result['backup'] = backup(settings, bundle, phrase)
            result['backup_sha256'] = file_hash(bundle)
            require(result['backup']['artifact_count'] == 0 and result['backup']['head_manifest_id'] is None, 'BACKUP_BASELINE_DIFFERS')
            unchanged(read_snapshot(settings.database_url), before)
            result['phase'] = 'ACTUAL_OWNER_BACKUP_RESTORE'
            dbname = 'mc_owner_restore_' + nonce + '_test'
            require(len(dbname.encode('utf-8')) <= 63, 'RESTORE_DATABASE_NAME_TOO_LONG')
            target_dsn = make_conninfo(admin_dsn, dbname=dbname)
            result['isolated_database'] = dbname
            with connect(admin_dsn) as c:
                c.autocommit = True
                c.execute(sql.SQL("CREATE DATABASE {} TEMPLATE template0 ENCODING 'UTF8'").format(sql.Identifier(dbname)))
            result['isolated_database_created'] = True
            restored_root.mkdir(parents=True)
            result['restore'] = restore(bundle, restored_root, target_dsn, settings.database_url, phrase)
            recovered = read_snapshot(target_dsn)
            require(recovered['identity']['database'] == dbname, 'RESTORE_DATABASE_NAME_CHANGED')
            unchanged(recovered, before, compare_identity=False)
            restored_settings = Settings(target_dsn, restored_root, settings.owner_timezone,
                                         settings.base_currency, False, settings.owner_configured, 'DEVELOPMENT_TEST')
            restored_check = preflight(restored_settings, integrity=True)
            require(restored_check['checks'].get('storage') == inventory['checks']['storage'], 'RESTORED_STORAGE_DIFFERS')
            result['restored_baseline_verified'] = True
            result['phase'] = 'ISOLATED_UPGRADE_REHEARSAL'
            require(migrate(target_dsn, reviewed) == pending, 'REHEARSAL_MIGRATION_SET_DIFFERS')
            rehearsed = read_snapshot(target_dsn, original=before)
            added = set(rehearsed['counts']) - set(before['counts'])
            require(len(added) == 34 and all(rehearsed['counts'][n] == 0 for n in added), 'REHEARSAL_NEW_TABLES_NOT_EMPTY')
            for name, count in before['counts'].items():
                require(rehearsed['counts'][name] == count + (11 if name == 'schema_migrations' else 0), 'REHEARSAL_EXISTING_COUNTS_CHANGED')
            verified_upgrade(rehearsed, before, rehearsed, pending)
            require(migrate(target_dsn, reviewed) == [], 'REHEARSAL_NOT_REPEATABLE')
            require(preflight(restored_settings, integrity=True)['status'] == 'VALIDATED', 'REHEARSAL_PREFLIGHT_FAILED')
            require(file_hash(bundle) == result['backup_sha256'], 'RETAINED_BACKUP_CHANGED')
            result['rehearsal_verified'] = True
            result['rehearsal'] = rehearsed
            publish()

            def before_apply(c):
                c.execute("SET LOCAL lock_timeout='5s'")
                c.execute(sql.SQL('LOCK TABLE {} IN SHARE ROW EXCLUSIVE MODE').format(
                    sql.SQL(',').join(sql.Identifier(before['schema'], name) for name in sorted(before['counts']))))
                unchanged(snapshot(c), before)
                require(not any(settings.data_root.iterdir()), 'MATERIAL_OWNER_DATA_ROOT_CHANGE')

            def after_apply(c, applied):
                require(applied == pending, 'OWNER_MIGRATION_SET_DIFFERS')
                verified_upgrade(snapshot(c, original=before), before, rehearsed, pending)

            result['phase'] = 'OWNER_GUARDED_TRANSACTION'
            result['owner_migration_attempted'] = True
            publish()
            result['applied_migrations'] = migrate(settings.database_url, reviewed,
                verify_before=before_apply, verify_after=after_apply, lock_timeout_ms=5000)
            result['owner_migration_committed'] = True
            publish()
        result['phase'] = 'POST_COMMIT_READ_ONLY_VERIFICATION'
        after = read_snapshot(settings.database_url, original=before)
        require(after['identity'] == before['identity'], 'POST_MIGRATION_DATABASE_IDENTITY_CHANGED')
        verified_upgrade(after, before, rehearsed, pending)
        result['owner_preflight_after'] = preflight(settings, integrity=True)
        require(result['owner_preflight_after']['status'] == 'VALIDATED', 'OWNER_POST_MIGRATION_PREFLIGHT_FAILED')
        require(not any(settings.data_root.iterdir()), 'OWNER_DATA_ROOT_CHANGED')
        require(file_hash(bundle) == result['backup_sha256'], 'RETAINED_BACKUP_CHANGED')
        result.update(status='VALIDATED_OWNER_SCHEMA_MIGRATION' if settings.environment == 'OWNER_MAIN' else 'VALIDATED_ISOLATED_ENGINE_TEST',
                      final_state=after, backup_retained=True, isolated_restore_retained=True,
                      existing_records_preserved=True, new_tables_empty=True, owner_ready=False,
                      completed_at=datetime.now(timezone.utc).isoformat())
    except (Exception, KeyboardInterrupt) as error:
        code = str(error) if type(error) is ValueError and re.fullmatch('[A-Z_0-9]+', str(error)) else type(error).__name__
        result.update(status='FAILED_STOPPED', error_code=code, rollback_or_cutover_attempted=False)
        if result['owner_migration_attempted'] and not result['owner_migration_committed']:
            result['commit_outcome'] = 'UNCONFIRMED_ON_FAILURE; INSPECT_READ_ONLY_BEFORE_ANY_FURTHER_OPERATION'
    publish()
    return result


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--authorized-owner-migration', action='store_true')
    args = p.parse_args()
    try:
        require(args.authorized_owner_migration, 'EXPLICIT_OWNER_AUTHORIZATION_REQUIRED')
        plan = approved_plan()
        _, settings = load_profile(ROOT / 'config/operations-owner.example.json')
        require(settings.environment == 'OWNER_MAIN' and settings.data_root == Path('C:/MarketCortexData').resolve(), 'OWNER_PROFILE_REQUIRED')
        admin = os.environ.get('MARKET_CORTEX_OWNER_RESTORE_ADMIN_URL', DEFAULT_ADMIN)
        parts = conninfo_to_dict(admin)
        require(parts.get('host') in {'127.0.0.1', 'localhost', '::1'} and
                parts.get('hostaddr') in {None, '127.0.0.1', '::1'} and
                parts.get('port') == '55432' and not parts.get('options') and not parts.get('service'),
                'EXPECTED_ISOLATED_ADMIN_CONFIGURATION_REQUIRED')
        with connect(admin) as c:
            c.execute('SET TRANSACTION READ ONLY')
            port = c.execute('SELECT inet_server_port()').fetchone()[0]
            directory = Path(c.execute('SHOW data_directory').fetchone()[0]).resolve()
            require(port == 55432 and directory == CLUSTER.resolve(), 'EXPECTED_ISOLATED_CLUSTER_REQUIRED')
        report = ROOT / 'runtime' / ('owner-migration-' + uuid4().hex) / 'report.json'
        result = execute(settings, plan,
            {'database': 'market_cortex', 'port': 5432, 'version': '17.11'}, admin,
            Path('C:/MarketCortexBackups'), Path('C:/MarketCortexRestoreDrills'), report)
        print(json.dumps({'status': result['status'], 'phase': result.get('phase'),
                          'error_code': result.get('error_code'), 'report': str(report),
                          'backup': result.get('retained_backup'), 'owner_migration_committed': result['owner_migration_committed']}))
        return 0 if result['status'] == 'VALIDATED_OWNER_SCHEMA_MIGRATION' else 1
    except (Exception, KeyboardInterrupt) as error:
        code = str(error) if type(error) is ValueError and re.fullmatch('[A-Z_0-9]+', str(error)) else type(error).__name__
        print(json.dumps({'status': 'FAILED_BEFORE_OWNER_MIGRATION', 'error_code': code}))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
