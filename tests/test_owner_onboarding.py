"""Safety guards and real recovery of an empty migrated disposable catalog."""
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import pytest
from psycopg import sql
from psycopg.conninfo import make_conninfo

from market_cortex import owner_onboarding as procedure
from market_cortex.config import Settings
from market_cortex.database import connect, migrate
from market_cortex.owner_migration import read_snapshot, unchanged
from test_phase9_catalog import DSN, SAFE


@pytest.fixture
def migrated_catalog(tmp_path, monkeypatch):
    if not SAFE:
        pytest.skip('dedicated disposable test database required')
    name = 'owner_data_guard_' + uuid4().hex + '_test'
    admin = make_conninfo(DSN, dbname='postgres', options='')
    dsn = make_conninfo(admin, dbname=name)
    with connect(admin) as c:
        c.autocommit = True
        c.execute(sql.SQL("CREATE DATABASE {} TEMPLATE template0 ENCODING 'UTF8'").format(sql.Identifier(name)))
    targets = []
    try:
        migrate(dsn, procedure.ROOT)
        data = tmp_path / 'source'; data.mkdir()
        settings = Settings(dsn, data, 'Asia/Kolkata', 'INR', False, True, 'DEVELOPMENT_TEST')
        monkeypatch.setenv('MARKET_CORTEX_BACKUP_PASSPHRASE', 'test-only-owner-data-drill-key-2026')
        yield settings, read_snapshot(dsn), tmp_path, targets
    finally:
        for target in [*targets, name]:
            assert target.endswith('_test') and (target.startswith('mc_owner_market_') or target == name)
            with connect(admin) as c:
                c.autocommit = True
                c.execute(sql.SQL('DROP DATABASE {}').format(sql.Identifier(target)))


def test_retained_encrypted_recovery_before_any_market_write(migrated_catalog):
    settings, before, work, targets = migrated_catalog
    result = {}
    def publish():
        if result.get('isolated_database_created') and result['isolated_database'] not in targets:
            targets.append(result['isolated_database'])
    procedure.recovery_baseline(settings, before, result, publish, work/'backups', work/'recovery')
    assert result['recovery_verified']
    assert Path(result['retained_backup']).is_file()
    assert len(result['isolated_database'].encode()) <= 63
    unchanged(read_snapshot(settings.database_url), before)
    assert result['recovered_baseline']['counts'] == before['counts']
    assert result['recovered_baseline']['row_hashes'] == before['row_hashes']
    assert not any(settings.data_root.iterdir())


def test_failed_restore_retains_backup_and_preserves_source(migrated_catalog, monkeypatch):
    settings, before, work, targets = migrated_catalog
    result = {}
    def publish():
        if result.get('isolated_database_created') and result['isolated_database'] not in targets:
            targets.append(result['isolated_database'])
    def fail(*args):
        raise RuntimeError('TEST_ONLY_RECOVERY_FAILURE')
    monkeypatch.setattr(procedure, 'restore', fail)
    with pytest.raises(RuntimeError, match='TEST_ONLY_RECOVERY_FAILURE'):
        procedure.recovery_baseline(settings, before, result, publish, work/'backups', work/'recovery')
    assert Path(result['retained_backup']).is_file() and not result.get('recovery_verified')
    unchanged(read_snapshot(settings.database_url), before)


def test_existing_owner_records_stop_before_recovery(migrated_catalog):
    _, before, _, _ = migrated_catalog
    before['counts']['venues'] = 1
    with pytest.raises(ValueError, match='OWNER_ALREADY_CONTAINS_RECORDS'):
        procedure.baseline_guard(before)


def test_timestamp_hash_is_canonical_across_session_timezones(migrated_catalog):
    settings, before, _, _ = migrated_catalog
    with connect(settings.database_url) as c:
        c.execute('SET TRANSACTION READ ONLY')
        c.execute("SET LOCAL timezone='Asia/Kolkata'")
        result = procedure.migration_inventory(c)
        assert procedure.schema_fingerprint(c) == before['schema_hash']
    assert result['session_hash'] != result['utc_hash']
    assert result['utc_hash'] == before['row_hashes']['schema_migrations']
    procedure.migration_history_unchanged(result, before)


@pytest.mark.parametrize('column', ['checksum', 'applied_at'])
def test_real_migration_row_changes_remain_rejected(migrated_catalog, column):
    settings, before, _, _ = migrated_catalog
    with connect(settings.database_url) as c:
        if column == 'checksum':
            c.execute("UPDATE schema_migrations SET checksum='TEST_ONLY_CHANGED' WHERE name=(SELECT min(name) FROM schema_migrations)")
        else:
            c.execute("UPDATE schema_migrations SET applied_at=applied_at+interval '1 second' WHERE name=(SELECT min(name) FROM schema_migrations)")
    with connect(settings.database_url) as c:
        c.execute('SET TRANSACTION READ ONLY')
        result = procedure.migration_inventory(c)
    with pytest.raises(ValueError, match='MIGRATION_HISTORY_CHANGED'):
        procedure.migration_history_unchanged(result, before)


@pytest.mark.parametrize('environment,identity,when,code', [
    ('PILOT_TEST', {}, procedure.END, 'OWNER_PROFILE_REQUIRED'),
    ('OWNER_MAIN', {'database':'market_cortex_pilot_test','port':55432,'database_oid':1,'version':'17.11'}, procedure.END, 'OWNER_IDENTITY_DIFFERS'),
    ('OWNER_MAIN', {'database':'market_cortex','port':5432,'database_oid':16388,'version':'17.11'}, datetime(2026,10,12,tzinfo=timezone.utc), 'APPROVED_CLOSED_SESSION_DATE_CHANGED'),
])
def test_wrong_environment_identity_or_date_rejected_without_accessing_owner_files(environment, identity, when, code):
    settings = Settings('unused', Path('C:/MarketCortexData'), 'Asia/Kolkata', 'INR', False, True, environment)
    with pytest.raises(ValueError, match=code):
        procedure.owner_guard(settings, {'identity':identity}, when)
