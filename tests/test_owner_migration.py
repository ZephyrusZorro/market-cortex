"""Exact empty-owner baseline replicated only in fresh, disposable *_test DBs."""
import json
import os
from pathlib import Path
import tempfile
from uuid import uuid4

import pytest
import psycopg
from psycopg import sql
from psycopg.conninfo import make_conninfo

from market_cortex.config import Settings
from market_cortex.database import connect, migrate
from market_cortex import owner_migration as procedure
from test_phase9_catalog import DSN, SAFE


@pytest.fixture
def baseline(monkeypatch):
    if not SAFE:
        pytest.skip('explicit dedicated *_test PostgreSQL required')
    plan=procedure.approved_plan()
    name='owner_guard_'+uuid4().hex+'_test'
    dsn=make_conninfo(DSN,dbname=name,options='')
    admin=make_conninfo(DSN,dbname='postgres',options='')
    with connect(admin) as c:
        c.autocommit=True
        c.execute(sql.SQL("CREATE DATABASE {} TEMPLATE template0 ENCODING 'UTF8'").format(sql.Identifier(name)))
    try:
        with tempfile.TemporaryDirectory(prefix='market-cortex-owner-guard-') as directory:
            work=Path(directory)
            old=work/'old/infra/migrations'; old.mkdir(parents=True)
            for path in sorted((procedure.ROOT/'infra/migrations').glob('000[12]_*.sql')):
                (old/path.name).write_text(path.read_text(encoding='utf-8'),encoding='utf-8')
            assert len(migrate(dsn,work/'old'))==2
            data=work/'data'; data.mkdir()
            settings=Settings(dsn,data,'Asia/Kolkata','INR',False,True,'DEVELOPMENT_TEST')
            before=procedure.read_snapshot(dsn)
            monkeypatch.setenv('MARKET_CORTEX_BACKUP_PASSPHRASE','test-only-not-an-owner-key-2026')
            yield settings,plan,before,admin,work
            for path in work.rglob('report.json'):
                r=json.loads(path.read_text())
                if r.get('isolated_database_created'):
                    target=r['isolated_database']
                    assert target.startswith('mc_owner_restore_') and target.endswith('_test')
                    with connect(admin) as c:
                        c.autocommit=True
                        c.execute(sql.SQL('DROP DATABASE {}').format(sql.Identifier(target)))
    finally:
        with connect(admin) as c:
            c.autocommit=True
            c.execute(sql.SQL('DROP DATABASE {}').format(sql.Identifier(name)))


def run(baseline):
    settings,plan,before,admin,work=baseline
    return procedure.execute(settings,plan,before['identity'],admin,
        work/'backups',work/'recovery',work/'report.json')


def test_actual_empty_baseline_backup_restore_rehearse_guarded_upgrade(baseline):
    result=run(baseline)
    assert result['status']=='VALIDATED_ISOLATED_ENGINE_TEST',result
    assert result['backup']['artifact_count']==0
    assert result['restored_baseline_verified'] and result['rehearsal_verified']
    assert result['owner_migration_committed']
    assert len(result['final_state']['ledger'])==13 and len(result['final_state']['counts'])==51
    assert result['existing_records_preserved'] and result['new_tables_empty']
    bundle=Path(result['retained_backup'])
    assert bundle.is_file() and procedure.file_hash(bundle)==result['backup_sha256']
    assert Path(result['restore_data_root']).is_dir()
    assert len(result['isolated_database'].encode('utf-8')) <= 63
    assert result['rehearsal']['identity']['database'] == result['isolated_database']
    assert result['isolated_database'].endswith('_test')
    serialized=json.dumps(result)
    assert 'test-only-not-an-owner-key' not in serialized
    assert 'password=' not in serialized and 'postgresql://' not in serialized


def test_failed_restore_preserves_backup_and_prevents_live_migration(baseline,monkeypatch):
    real=procedure.restore
    monkeypatch.setattr(procedure,'restore',lambda bundle,root,target,source,phrase:
                        real(bundle,root,target,source,'different-wrong-test-only-phrase'))
    result=run(baseline)
    assert result['status']=='FAILED_STOPPED' and not result['owner_migration_attempted']
    assert Path(result['retained_backup']).is_file()
    procedure.unchanged(procedure.read_snapshot(baseline[0].database_url),baseline[2])


def test_record_change_before_backup_stops_without_creating_backup(baseline):
    with connect(baseline[0].database_url) as c:
        c.execute("UPDATE schema_migrations SET applied_at=applied_at+interval '1 second'")
        c.execute("INSERT INTO venues VALUES ('TEST_ONLY','UTC','24x7','{}')")
    result=run(baseline)
    assert result['error_code']=='MATERIAL_LIVE_RECORD_COUNT_CHANGE'
    assert not result['owner_migration_attempted'] and 'retained_backup' not in result


def test_record_change_after_rehearsal_is_caught_inside_transaction(baseline,monkeypatch):
    real=procedure.migrate
    def changed(dsn,root,**kwargs):
        if kwargs.get('verify_before'):
            with connect(dsn) as c:
                c.execute("UPDATE schema_migrations SET applied_at=applied_at+interval '1 second'")
        return real(dsn,root,**kwargs)
    monkeypatch.setattr(procedure,'migrate',changed)
    result=run(baseline)
    assert result['error_code']=='MATERIAL_LIVE_STATE_CHANGE'
    assert not result['owner_migration_committed']
    assert Path(result['retained_backup']).is_file()
    assert len(procedure.read_snapshot(baseline[0].database_url)['ledger'])==2


def test_post_sql_guard_failure_rolls_back_the_whole_transaction(baseline):
    def reject(c,applied):
        assert len(applied)==11
        c.execute("UPDATE schema_migrations SET applied_at=applied_at+interval '1 second' WHERE name='0001_market_foundation.sql'")
        raise ValueError('TEST_ONLY_POSTCHECK_REJECTION')
    with pytest.raises(ValueError,match='TEST_ONLY_POSTCHECK_REJECTION'):
        migrate(baseline[0].database_url,procedure.ROOT,verify_after=reject)
    procedure.unchanged(procedure.read_snapshot(baseline[0].database_url),baseline[2])


def test_reviewed_sql_change_is_rejected_before_backup(baseline,monkeypatch):
    settings,plan,before,admin,work=baseline
    altered=work/'altered-project'
    target=altered/'infra/migrations'; target.mkdir(parents=True)
    for path in (procedure.ROOT/'infra/migrations').glob('*.sql'):
        text=path.read_text(encoding='utf-8')
        if path.name=='0003_cortex_research.sql': text+='\n-- unreviewed edit\n'
        (target/path.name).write_text(text,encoding='utf-8')
    monkeypatch.setattr(procedure,'ROOT',altered)
    result=run(baseline)
    assert result['error_code']=='REVIEWED_MIGRATION_SET_CHANGED'
    assert not result['owner_migration_attempted']
    assert not Path(result['retained_backup']).exists()


def test_competing_migration_lock_stops_without_schema_changes(baseline):
    with connect(baseline[0].database_url) as holder:
        holder.execute('SELECT pg_advisory_xact_lock(%s)',(837_241_903,))
        with pytest.raises(psycopg.errors.LockNotAvailable):
            migrate(baseline[0].database_url,procedure.ROOT,lock_timeout_ms=100)
    procedure.unchanged(procedure.read_snapshot(baseline[0].database_url),baseline[2])


def test_interruption_writes_safe_stop_report(baseline,monkeypatch):
    def interrupted(*args): raise KeyboardInterrupt()
    monkeypatch.setattr(procedure,'backup',interrupted)
    result=run(baseline)
    assert result['status']=='FAILED_STOPPED' and result['error_code']=='KeyboardInterrupt'
    assert not result['owner_migration_attempted']
    assert json.loads((baseline[4]/'report.json').read_text())['error_code']=='KeyboardInterrupt'
    procedure.unchanged(procedure.read_snapshot(baseline[0].database_url),baseline[2])
