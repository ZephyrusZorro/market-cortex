"""Approved Binance-only owner onboarding; retained recovery precedes writes.

No migrations, resets, rollback, synthetic records, scheduling or app launch.
Secrets are environment-only; every failure retains backup and recovery evidence.
"""
from __future__ import annotations

import argparse
import json
import os
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import UUID, uuid4

from psycopg import sql
from psycopg.conninfo import make_conninfo

from .backup import backup, restore
from .bootstrap import discover_crypto
from .config import Settings
from .database import connect
from .identity import IdentityRegistry
from .operations import ROOT, catalog_for, enqueue_refresh, load_profile, preflight, status, worker
from .owner_migration import CLUSTER, DEFAULT_ADMIN, digest, file_hash, read_snapshot, require, unchanged
from .providers import BinanceDaily, ProviderFailure

SYMBOLS = ('BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'BNBUSDT', 'XRPUSDT')
START = datetime(2025, 10, 11, tzinfo=timezone.utc)
END = datetime(2026, 10, 11, tzinfo=timezone.utc)
MARKET_TABLES = {'venues', 'instruments', 'identifier_mappings', 'source_batches',
                 'observations', 'dataset_files', 'dataset_manifests', 'manifest_members',
                 'dataset_head', 'outbox', 'quarantine', 'jobs'}


def baseline_guard(before: dict):
    require(len(before['counts']) == 51 and len(before['ledger']) == 13, 'OWNER_SCHEMA_DIFFERS')
    require(before['counts']['schema_migrations'] == 13 and before['counts']['dataset_head'] == 1
            and before['head'] == [None], 'OWNER_METADATA_DIFFERS')
    require(all(n == 0 for t, n in before['counts'].items()
                if t not in {'schema_migrations', 'dataset_head'}), 'OWNER_ALREADY_CONTAINS_RECORDS')


def owner_guard(settings: Settings, before: dict, now: datetime):
    require(settings.environment == 'OWNER_MAIN' and
            settings.data_root.resolve() == Path('C:/MarketCortexData').resolve(), 'OWNER_PROFILE_REQUIRED')
    identity = before['identity']
    require(identity['database'] == 'market_cortex' and identity['port'] == 5432
            and identity['database_oid'] == 16388 and identity['version'] == '17.11', 'OWNER_IDENTITY_DIFFERS')
    require(now.astimezone(timezone.utc).date() == END.date(), 'APPROVED_CLOSED_SESSION_DATE_CHANGED')
    baseline_guard(before)
    require(settings.data_root.is_dir() and not any(settings.data_root.iterdir()), 'OWNER_DATA_ROOT_DIFFERS')


def recovery_baseline(settings, before, result, publish, backup_parent, restore_parent):
    """Also exercised against an empty, disposable test catalog by integration tests."""
    baseline_guard(before)
    phrase = os.environ.get('MARKET_CORTEX_BACKUP_PASSPHRASE', '')
    require(len(phrase) >= 16, 'RETAINED_BACKUP_PASSPHRASE_REQUIRED')
    with connect(DEFAULT_ADMIN) as c:
        c.execute('SET TRANSACTION READ ONLY')
        port, version, directory = c.execute(
            "SELECT inet_server_port(),current_setting('server_version_num'),current_setting('data_directory')").fetchone()
        require(port == 55432 and int(version) // 10000 == 17
                and Path(directory).resolve() == CLUSTER.resolve(), 'ISOLATED_RECOVERY_CLUSTER_DIFFERS')
    nonce = uuid4().hex
    bundle = backup_parent / ('owner-before-market-' + nonce + '.mcbackup')
    recovered_root = restore_parent / ('owner-market-' + nonce)
    dbname = 'mc_owner_market_' + nonce + '_test'
    require(len(dbname.encode()) <= 63 and not recovered_root.exists() and not bundle.exists(), 'RECOVERY_TARGET_COLLISION')
    result.update(phase='RETAINED_ENCRYPTED_BACKUP', retained_backup=str(bundle), restore_data_root=str(recovered_root),
                  isolated_database=dbname)
    publish()
    result['backup'] = backup(settings, bundle, phrase)
    result['backup_sha256'] = file_hash(bundle)
    require(result['backup']['artifact_count'] == 0 and result['backup']['head_manifest_id'] is None, 'BACKUP_BASELINE_DIFFERS')
    unchanged(read_snapshot(settings.database_url), before)
    target = make_conninfo(DEFAULT_ADMIN, dbname=dbname)
    with connect(DEFAULT_ADMIN) as c:
        c.autocommit = True
        c.execute(sql.SQL("CREATE DATABASE {} TEMPLATE template0 ENCODING 'UTF8'").format(sql.Identifier(dbname)))
    result.update(phase='ISOLATED_RECOVERY', isolated_database_created=True)
    publish()
    recovered_root.mkdir(parents=True)
    result['restore'] = restore(bundle, recovered_root, target, settings.database_url, phrase)
    recovered = read_snapshot(target)
    require(recovered['identity']['database'] == dbname and recovered['identity']['port'] == 55432, 'RECOVERY_IDENTITY_DIFFERS')
    unchanged(recovered, before, compare_identity=False)
    restored_settings = Settings(target, recovered_root, settings.owner_timezone, settings.base_currency,
                                 False, settings.owner_configured, 'DEVELOPMENT_TEST')
    require(preflight(restored_settings, integrity=True)['status'] == 'VALIDATED', 'RECOVERY_INTEGRITY_FAILED')
    require(file_hash(bundle) == result['backup_sha256'], 'RETAINED_BACKUP_CHANGED')
    unchanged(read_snapshot(settings.database_url), before)
    result.update(recovery_verified=True, recovered_baseline=recovered)
    publish()


def sync(catalog, instrument_id):
    instruments, mappings = catalog.load_identity()
    instrument = next(i for i in instruments if i.instrument_id == UUID(instrument_id))
    mapping = IdentityRegistry(instruments, mappings).mapping_for(instrument.instrument_id, 'binance', 'exchange_pair', START)
    calendar = catalog.load_calendar('BINANCE_SPOT', START, END)
    fetched = BinanceDaily().fetch_daily(instrument, mapping, calendar, START, END)
    ingested = catalog.ingest(list(fetched.bars), calendar, source_batch_id=fetched.batch_id,
                              provider_id=fetched.provider_id, raw_hash=fetched.raw_hash, fetched_at=fetched.fetched_at)
    return {'stored': ingested.stored, 'duplicates': ingested.duplicates, 'quarantined': ingested.quarantined,
            'manifest_id': str(ingested.manifest_id) if ingested.manifest_id else None,
            'source_batch_id': str(fetched.batch_id), 'provider_response_hash': fetched.raw_hash, 'pages': fetched.pages}


def migration_inventory(connection):
    """Canonicalize timestamptz JSON exactly as the original snapshot does."""
    zone = connection.execute('SHOW TimeZone').fetchone()[0]
    raw = connection.execute('SELECT to_jsonb(m) FROM schema_migrations m').fetchall()
    connection.execute("SET LOCAL timezone='UTC'")
    canonical = connection.execute('SELECT to_jsonb(m) FROM schema_migrations m').fetchall()
    ledger = dict(connection.execute('SELECT name,checksum FROM schema_migrations ORDER BY name'))
    return {'session_timezone': zone, 'count': len(canonical), 'ledger': ledger,
            'session_hash': digest(sorted(digest(r[0]) for r in raw)),
            'utc_hash': digest(sorted(digest(r[0]) for r in canonical))}


def schema_fingerprint(connection):
    schema = connection.execute('SELECT current_schema()').fetchone()[0]
    columns = connection.execute("""SELECT table_name,column_name,ordinal_position,udt_schema,udt_name,
        is_nullable,column_default FROM information_schema.columns WHERE table_schema=%s
        ORDER BY table_name,ordinal_position""", (schema,)).fetchall()
    constraints = connection.execute("""SELECT r.relname,k.conname,pg_get_constraintdef(k.oid)
        FROM pg_constraint k JOIN pg_class r ON r.oid=k.conrelid JOIN pg_namespace n ON n.oid=r.relnamespace
        WHERE n.nspname=%s ORDER BY 1,2""", (schema,)).fetchall()
    indexes = connection.execute('SELECT tablename,indexname,indexdef FROM pg_indexes WHERE schemaname=%s ORDER BY 1,2',
                                 (schema,)).fetchall()
    return digest([columns, constraints, indexes])


def migration_history_unchanged(history, before):
    require(history['count'] == 13 and history['ledger'] == before['ledger']
            and history['utc_hash'] == before['row_hashes']['schema_migrations'], 'MIGRATION_HISTORY_CHANGED')


def verify_existing(settings, original_path):
    """Resume postchecks only. Every owner transaction is READ ONLY."""
    original_path = original_path.resolve()
    require(original_path.name == 'report.json' and original_path.parent.parent == ROOT / 'runtime'
            and re.fullmatch('owner-onboarding-[0-9a-f]{32}', original_path.parent.name), 'INVALID_ONBOARDING_REPORT_PATH')
    source = json.loads(original_path.read_text(encoding='utf-8-sig'))
    require(source['status'] == 'FAILED_STOPPED' and source['error_code'] == 'MIGRATION_HISTORY_CHANGED'
            and source['recovery_verified'], 'REPORT_NOT_ELIGIBLE_FOR_READ_ONLY_RECOVERY')
    result = {'status': 'IN_PROGRESS', 'mode': 'READ_ONLY_POST_INGESTION_RECOVERY', 'original_report': str(original_path),
              'original_report_sha256': file_hash(original_path), 'owner_database_writes': False, 'owner_ready': False}
    output = original_path.parent / ('verification-' + uuid4().hex + '.json')
    try:
        require(settings.environment == 'OWNER_MAIN' and settings.data_root.resolve() == Path('C:/MarketCortexData').resolve(), 'OWNER_PROFILE_REQUIRED')
        before = source['baseline']
        with connect(settings.database_url) as c:
            c.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY')
            identity = c.execute("""SELECT current_database(),host(inet_server_addr()),inet_server_port(),
                current_setting('server_version'),(SELECT oid FROM pg_database WHERE datname=current_database())""").fetchone()
            require(dict(zip(('database','address','port','version','database_oid'), identity)) == before['identity'], 'OWNER_IDENTITY_DIFFERS')
            result['migration_history'] = migration_inventory(c)
            result['schema_hash'] = schema_fingerprint(c)
        result['expected_migration_hash'] = before['row_hashes']['schema_migrations']
        migration_history_unchanged(result['migration_history'], before)
        require(result['schema_hash'] == before['schema_hash'], 'OWNER_SCHEMA_FINGERPRINT_CHANGED')
        result['preflight'] = preflight(settings, integrity=True)
        require(result['preflight']['status'] == 'VALIDATED', 'OWNER_FINAL_INTEGRITY_FAILED')
        counts = result['preflight']['checks']['table_counts']
        require(set(counts) == set(before['counts']) and all(counts[t] == n for t,n in before['counts'].items()
                if t not in MARKET_TABLES), 'UNRELATED_OWNER_COUNTS_CHANGED')
        require(counts['observations'] == 1825 and counts['instruments'] == counts['identifier_mappings'] == 5
                and counts['quarantine'] == 0, 'OWNER_MARKET_COUNTS_DIFFER')
        catalog = catalog_for(settings)
        require(str(catalog.head()) == source['pinned_manifest'], 'OWNER_HEAD_CHANGED')
        _, mappings = catalog.load_identity()
        knowledge_before = min(m.available_at for m in mappings if m.available_at) - timedelta(microseconds=1)
        result['coverage'] = []
        for identity in source['identities']:
            args = dict(instrument_id=UUID(identity['instrument_id']), start=START, end=END,
                        manifest_id=UUID(source['pinned_manifest']), provider_id='binance')
            bars = catalog.bars(**args, as_of=datetime.fromisoformat(source['pinned_as_of']))[1]
            require(len(bars) == 365 and digest([b.model_dump(mode='json') for b in bars]) == source['frozen_bar_hashes'][identity['symbol']], 'PINNED_REPLAY_DIFFERS')
            require(not catalog.bars(**args, as_of=knowledge_before)[1], 'AS_OF_KNOWLEDGE_BACKDATED')
            result['coverage'].append({'symbol':identity['symbol'],'visible_sessions':len(bars),'hash_matched':True})
        result['freshness'] = status(settings, datetime.now(timezone.utc))
        jobs = {j['job_id']:j for j in result['freshness']['jobs']}
        require(set(source['refresh_jobs']) <= set(jobs)
                and all(jobs[key]['state'] == 'done' for key in source['refresh_jobs']), 'RECORDED_REFRESH_NOT_COMPLETE')
        result['retained_backup_hash_verified'] = file_hash(Path(source['retained_backup'])) == source['backup_sha256']
        require(result['retained_backup_hash_verified'], 'RETAINED_BACKUP_CHANGED')
        result.update(status='VALIDATED_OWNER_MARKET_DATA_READ_ONLY_RECOVERY',
                      root_cause='TIMESTAMPTZ_JSON_HASH_USED_DIFFERENT_SESSION_TIMEZONE',
                      application_acceptance='PENDING_OWNER_PRODUCTION_LAUNCH')
    except Exception as error:
        candidate = str(error) if isinstance(error, ValueError) else ''
        result.update(status='FAILED_READ_ONLY_VERIFICATION', error_code=candidate if re.fullmatch('[A-Z0-9_]{1,100}',candidate) else type(error).__name__)
    output.write_text(json.dumps(result,indent=2,default=str)+'\n',encoding='utf-8')
    return result, output


def execute(profile, settings, report_path):
    result = {'status': 'IN_PROGRESS', 'phase': 'READ_ONLY_BASELINE', 'owner_ready': False,
              'symbols': SYMBOLS, 'start': START.isoformat(), 'end': END.isoformat(), 'migration_executed': False}
    report_path.parent.mkdir(parents=True, exist_ok=False)
    def publish():
        report_path.write_text(json.dumps(result, indent=2, default=str) + '\n', encoding='utf-8')
    publish()
    try:
        require(tuple(profile.symbols) == SYMBOLS and profile.database_env == 'MARKET_CORTEX_DATABASE_URL', 'APPROVED_PROFILE_DIFFERS')
        before = read_snapshot(settings.database_url)
        owner_guard(settings, before, datetime.now(timezone.utc))
        inspected = json.loads((ROOT / 'runtime/owner-migration-99c3aca053254bc1a956496a431e5569/report.json').read_text(encoding='utf-8-sig'))
        require(inspected['status'] == 'VALIDATED_OWNER_SCHEMA_MIGRATION' and inspected['owner_migration_committed'], 'INSPECTED_OWNER_RECEIPT_UNAVAILABLE')
        unchanged(read_snapshot(settings.database_url, original=inspected['baseline']), inspected['final_state'])
        require(preflight(settings, integrity=True)['status'] == 'VALIDATED', 'OWNER_PREFLIGHT_FAILED')
        result['baseline'] = before
        recovery_baseline(settings, before, result, publish, Path('C:/MarketCortexBackups'), Path('C:/MarketCortexRestoreDrills'))
        owner_guard(settings, read_snapshot(settings.database_url), datetime.now(timezone.utc))
        unchanged(read_snapshot(settings.database_url), before)
        catalog = catalog_for(settings)
        knowledge_before = datetime.now(timezone.utc)
        result['phase'] = 'OWNER_PUBLIC_IDENTITY_BOOTSTRAP'
        publish()
        result['identities'] = discover_crypto(catalog, SYMBOLS)
        result['initial_ingestion'] = []
        for identity in result['identities']:
            result['phase'] = 'INGEST_' + identity['symbol']
            publish()
            outcome = sync(catalog, identity['instrument_id'])
            result['initial_ingestion'].append({'symbol': identity['symbol'], **outcome})
            publish()
            require(outcome['stored'] == 365 and outcome['quarantined'] == 0, 'INITIAL_COVERAGE_OR_QUALITY_DIFFERS')
        pinned = catalog.head()
        cutoff = datetime.now(timezone.utc)
        frozen = {}
        for identity in result['identities']:
            args = dict(instrument_id=UUID(identity['instrument_id']), start=START, end=END,
                        manifest_id=pinned, provider_id='binance')
            bars = catalog.bars(**args, as_of=cutoff)[1]
            require(len(bars) == 365 and len({b.session_date for b in bars}) == 365, 'VISIBLE_COVERAGE_DIFFERS')
            require(not catalog.bars(**args, as_of=knowledge_before)[1], 'AS_OF_KNOWLEDGE_BACKDATED')
            frozen[identity['symbol']] = digest([b.model_dump(mode='json') for b in bars])
        result.update(phase='IDEMPOTENCE_CHECK', pinned_manifest=str(pinned), pinned_as_of=cutoff.isoformat(), frozen_bar_hashes=frozen)
        publish()
        result['duplicate_repeat'] = [dict(symbol=i['symbol'], **sync(catalog, i['instrument_id'])) for i in result['identities']]
        require(all(r['stored'] == 0 and r['duplicates'] == 365 and r['quarantined'] == 0 for r in result['duplicate_repeat'])
                and catalog.head() == pinned, 'SOURCE_CORRECTION_OR_REPEAT_DIFFERS_STOPPED')
        result['phase'] = 'EXPLICIT_INCREMENTAL_REFRESH'
        publish()
        refresh_now = datetime.now(timezone.utc)
        require(refresh_now.date() == END.date(), 'APPROVED_CLOSED_SESSION_DATE_CHANGED')
        result['refresh_jobs'] = enqueue_refresh(profile, settings, refresh_now)
        result['refresh'] = [worker(profile, settings) for _ in SYMBOLS]
        require(all(r['status'] == 'DONE' and r['stored'] == 0 and r['quarantined'] == 0 for r in result['refresh']), 'REFRESH_FAILED_OR_SOURCE_REVISED')
        for identity in result['identities']:
            bars = catalog.bars(instrument_id=UUID(identity['instrument_id']), start=START, end=END,
                                as_of=cutoff, manifest_id=pinned, provider_id='binance')[1]
            require(digest([b.model_dump(mode='json') for b in bars]) == frozen[identity['symbol']], 'PINNED_REPLAY_DIFFERS')
        final = preflight(settings, integrity=True)
        result.update(phase='POST_INGESTION_VERIFICATION', preflight=final)
        publish()
        require(final['status'] == 'VALIDATED', 'OWNER_FINAL_INTEGRITY_FAILED')
        require(all(final['checks']['table_counts'][t] == n for t, n in before['counts'].items() if t not in MARKET_TABLES), 'UNRELATED_OWNER_COUNTS_CHANGED')
        with connect(settings.database_url) as c:
            c.execute('SET TRANSACTION READ ONLY')
            history = migration_inventory(c)
        migration_history_unchanged(history, before)
        result.update(status='VALIDATED_OWNER_MARKET_DATA', phase='COMPLETE', preflight=final,
                      freshness=status(settings, datetime.now(timezone.utc)), scheduling_enabled=False,
                      owner_ready=False, application_acceptance='PENDING_OWNER_PRODUCTION_LAUNCH')
    except (Exception, KeyboardInterrupt) as error:
        candidate = error.code if isinstance(error, ProviderFailure) else str(error) if isinstance(error, ValueError) else ''
        code = candidate if re.fullmatch('[A-Z0-9_]{1,100}', candidate) else type(error).__name__
        result.update(status='FAILED_STOPPED', error_code=code, recovery_action='Preserve all evidence; inspect partial state. No reset, restore-over-owner or blind rerun.')
    publish()
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument('--approved-owner-onboarding', action='store_true')
    modes.add_argument('--verify-existing', type=Path, help='Read-only verification of a stopped run; no bootstrap, ingestion, jobs or migration')
    args = parser.parse_args()
    try:
        profile, settings = load_profile(ROOT / 'config/operations-owner.example.json')
    except Exception as error:
        print(json.dumps({'status': 'FAILED_BEFORE_EXECUTION', 'error_code': type(error).__name__}))
        return 1
    if args.verify_existing:
        try:
            outcome, report = verify_existing(settings, args.verify_existing)
        except Exception as error:
            print(json.dumps({'status':'FAILED_BEFORE_VERIFICATION','error_code':type(error).__name__}))
            return 1
        print(json.dumps({'status':outcome['status'],'report':str(report),'owner_database_writes':False,'error_code':outcome.get('error_code')}))
        return 0 if outcome['status'] == 'VALIDATED_OWNER_MARKET_DATA_READ_ONLY_RECOVERY' else 1
    report = ROOT / 'runtime' / ('owner-onboarding-' + uuid4().hex) / 'report.json'
    print(json.dumps({'report': str(report), 'phase': 'READ_ONLY_BASELINE'}), flush=True)
    outcome = execute(profile, settings, report)
    print(json.dumps({'status': outcome['status'], 'phase': outcome['phase'], 'report': str(report),
                      'error_code': outcome.get('error_code')}))
    return 0 if outcome['status'] == 'VALIDATED_OWNER_MARKET_DATA' else 1


if __name__ == '__main__':
    raise SystemExit(main())
