"""Real populated disposable restores, never OWNER_MAIN or the live pilot."""
import os
from datetime import date, datetime, timezone
from pathlib import Path
from uuid import uuid4

import pytest
from psycopg import sql
from psycopg.conninfo import make_conninfo
from psycopg.types.json import Jsonb

from market_cortex import backup as procedure
from market_cortex.backup import backup, restore, decrypt_file, encrypt_file
from market_cortex.config import Settings
from market_cortex.database import connect, migrate
from market_cortex.owner_migration import DEFAULT_ADMIN, file_hash
from market_cortex.owner_protection import protect
from market_cortex.protection_inventory import read_inventory
from market_cortex.storage import ArtifactStore, PostgresCatalog
from market_cortex.contracts import Venue
from market_cortex.calendar import SessionCalendar
from test_foundation import identity, bar
from test_operations import task_directory

ROOT = Path(__file__).resolve().parents[1]
KEY = 'test-only-protection-key-not-owner-2026'


@pytest.fixture
def protected_catalog(task_directory):
    # Keep content-addressed Parquet paths below legacy Windows MAX_PATH.
    tmp_path = task_directory
    # Explicit integration opt-in; each case creates its own entire database.
    if not os.getenv('MARKET_CORTEX_PROTECTION_TESTS'):
        pytest.skip('disposable protection integration opt-in required')
    names = ['mc_protection_fixture_'+uuid4().hex+'_test' for _ in range(2)]
    for name in names:
        with connect(DEFAULT_ADMIN) as c:
            c.autocommit=True
            c.execute(sql.SQL("CREATE DATABASE {} TEMPLATE template0 ENCODING 'UTF8'").format(sql.Identifier(name)))
    source,target = [make_conninfo(DEFAULT_ADMIN,dbname=n) for n in names]
    try:
        migrate(source,ROOT)
        data=tmp_path/'source';data.mkdir()
        settings=Settings(source,data,'Asia/Kolkata','INR',False,True,'DEVELOPMENT_TEST')
        catalog=PostgresCatalog(source,ArtifactStore(data))
        venue=Venue(venue_id='BINANCE_SPOT',timezone='UTC',session_kind='24x7')
        instrument,mapping=identity(venue_id='BINANCE_SPOT',native='BTCUSDT')
        catalog.register_identity([venue],[instrument],[mapping])
        cal=SessionCalendar(venue,'BINANCE_SPOT:utc_daily','v1')
        for day in (date(2025,1,2),date(2025,1,3)):
            b=bar(instrument,mapping,cal,day=day,available='2026-01-01T00:00:00Z')
            catalog.ingest([b],cal,source_batch_id=b.envelope.source_batch_id,provider_id='binance',raw_hash='a'*64,fetched_at=datetime(2026,1,1,tzinfo=timezone.utc))
        with connect(source) as c:
            c.execute('INSERT INTO cortex_research_runs (run_id,created_at,manifest_id,as_of,primary_symbol,evidence_hash,payload) VALUES (%s,now(),%s,now(),%s,%s,%s)',
                (uuid4(),catalog.head(),'BTCUSDT','b'*64,Jsonb({'fixture':'Synthetic research Unicode ₹ 日本語','never_owner':True})))
        yield settings,target,tmp_path,catalog,names
    finally:
        for name in names:
            assert name.endswith('_test') and (name.startswith('mc_protection_fixture_') or name.startswith('mc_protection_'))
            with connect(DEFAULT_ADMIN) as c:
                c.autocommit=True
                c.execute(sql.SQL('DROP DATABASE {}').format(sql.Identifier(name)))


def test_populated_protection_retains_bundle_and_source(protected_catalog,monkeypatch):
    settings,_,work,_,names=protected_catalog
    before=read_inventory(settings.database_url)
    monkeypatch.setenv('MARKET_CORTEX_BACKUP_PASSPHRASE',KEY)
    result=protect(settings,{},work/'receipt/report.json',backup_parent=work/'backups',restore_parent=work/'restore',enforce_owner=False)
    if result.get('isolated_database_created'):names.append(result['isolated_database'])
    assert result['status']=='VALIDATED_CURRENT_OWNER_BACKUP_AND_ISOLATED_RESTORE',result.get('error_code')
    assert result['restore']['catalog_inventory_verified']
    assert result['backup']['artifact_count']==2
    assert result['backup']['catalog_inventory']['counts']['cortex_research_runs']==1
    assert file_hash(Path(result['retained_backup']))==result['backup_sha256']
    assert read_inventory(settings.database_url)==before


def test_dump_snapshot_excludes_concurrent_record_but_covers_non_head_files(protected_catalog,monkeypatch):
    settings,target,work,catalog,_=protected_catalog
    # Point head back to first manifest, retaining later evidence in catalog.
    with connect(settings.database_url) as c:
        first=c.execute('SELECT manifest_id FROM dataset_manifests WHERE parent_manifest_id IS NULL').fetchone()[0]
        c.execute('UPDATE dataset_head SET manifest_id=%s',(first,))
    before=read_inventory(settings.database_url)
    run=procedure._run_pg
    def concurrent_write(binary,dsn,args):
        if binary=='pg_dump':
            assert '--snapshot' in args
            with connect(settings.database_url) as c:
                c.execute('INSERT INTO cortex_research_runs (run_id,created_at,manifest_id,as_of,primary_symbol,evidence_hash,payload) VALUES (%s,now(),%s,now(),%s,%s,%s)',
                    (uuid4(),first,'BTCUSDT','c'*64,Jsonb({'fixture':'concurrent record'})))
        return run(binary,dsn,args)
    monkeypatch.setattr(procedure,'_run_pg',concurrent_write)
    result=backup(settings,work/'current.mcbackup',KEY)
    assert result['artifact_count']==2  # old algorithm copied only one
    restore(work/'current.mcbackup',work/'recovered',target,settings.database_url,KEY)
    assert read_inventory(target)==before
    assert read_inventory(settings.database_url)['counts']['cortex_research_runs']==2


def test_corrupt_bundle_never_restores_records(protected_catalog):
    settings,target,work,_,_=protected_catalog
    bundle=work/'bad.mcbackup'
    backup(settings,bundle,KEY)
    original=bundle.read_bytes();bundle.write_bytes(original[:-1]+bytes([original[-1]^1]))
    with pytest.raises(ValueError,match='authentication failed'):
        restore(bundle,work/'bad-restore',target,settings.database_url,KEY)
    with connect(target) as c:
        assert c.execute("SELECT count(*) FROM pg_tables WHERE schemaname='public'").fetchone()[0]==0
    assert bundle.exists()


def test_failed_recovery_preserves_populated_source_and_retained_bundle(protected_catalog,monkeypatch):
    settings,_,work,_,names=protected_catalog
    before=read_inventory(settings.database_url)
    monkeypatch.setenv('MARKET_CORTEX_BACKUP_PASSPHRASE',KEY)
    def fail(*args):raise RuntimeError('synthetic recovery failure')
    monkeypatch.setattr('market_cortex.owner_protection.restore',fail)
    result=protect(settings,{},work/'failed/report.json',backup_parent=work/'backups',restore_parent=work/'restore',enforce_owner=False)
    if result.get('isolated_database_created'):names.append(result['isolated_database'])
    assert result['status']=='FAILED_STOPPED'
    assert Path(result['retained_backup']).exists() and Path(result['restore_data_root']).exists()
    assert read_inventory(settings.database_url)==before


def test_restore_refuses_same_live_database_alias(tmp_path):
    with pytest.raises(ValueError,match='separate database'):
        restore(tmp_path/'nonexistent',tmp_path/'restore',
                'host=localhost port=5432 dbname=market_cortex', 'host=127.0.0.1 port=5432 dbname=market_cortex',KEY)


def test_decrypt_refuses_overwrite_and_cleans_only_owned_plaintext(tmp_path):
    plain=tmp_path/'source';plain.write_bytes(b'fixture')
    cipher=tmp_path/'fixture.mcbackup';encrypt_file(plain,cipher,KEY)
    destination=tmp_path/'existing';destination.write_bytes(b'preserved')
    with pytest.raises(FileExistsError):decrypt_file(cipher,destination,KEY)
    assert destination.read_bytes()==b'preserved'
