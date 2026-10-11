"""Operational isolation, real PostgreSQL refresh recovery and browser boundaries."""
import json
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

import pytest
import httpx
from fastapi.testclient import TestClient
from psycopg import sql
from psycopg.conninfo import make_conninfo

from market_cortex.api import create_app
from market_cortex.config import Settings
from market_cortex.database import connect, migrate
from market_cortex.operations import (Profile, load_profile, preflight, due_slot, refresh_plan,
                                     enqueue_refresh, worker, status, KIND, profile_key)
from market_cortex.operations_security import local_request_allowed
from market_cortex.providers import FetchBatch, ProviderFailure, ReadTransport
from market_cortex.backup import backup, encrypt_file, decrypt_file
from market_cortex.storage import ArtifactStore, PostgresCatalog
from market_cortex.contracts import Venue
from market_cortex.calendar import SessionCalendar
from test_foundation import identity, bar
from test_phase9_catalog import DSN, SAFE

UTC = timezone.utc


@pytest.mark.parametrize('host,origin,allowed', [
    ('127.0.0.1:8765',None,True), ('[::1]:8765','http://localhost:3000',True),
    ('evil.example:8765',None,False), ('127.0.0.1','https://evil.example',False),
    ('127.0.0.1','null',False), ('127.0.0.1','http://127.0.0.1@evil.example',False),
    ('127.0.0.1','http://localhost:bad',False), ('127.0.0.1/path',None,False),
])
def test_local_boundary(host, origin, allowed):
    assert local_request_allowed(host,origin) is allowed


def test_browser_cross_origin_cannot_write():
    settings = Settings(None,Path('.'), 'Asia/Kolkata','INR',False,False)
    with TestClient(create_app(settings)) as client:
        assert client.post('/api/v1/cortex/research',headers={'Origin':'https://evil.example'},json={}).status_code == 403
        assert client.get('/api/v1/health',headers={'Host':'rebinding.example'}).status_code == 403
        assert client.get('/api/v1/health').json()['status'] == 'not_configured'


@pytest.fixture
def task_directory():
    with tempfile.TemporaryDirectory(prefix='market-cortex-operations-') as directory:
        yield Path(directory)


def test_profile_isolation_and_no_secret_output(task_directory, monkeypatch):
    tmp_path = task_directory
    p = tmp_path/'profile.json'
    def write(environment,root):
        p.write_text(json.dumps({'environment':environment,'database_env':'MARKET_CORTEX_OP_TEST_URL','data_root':str(root)}),encoding='utf-8')
    write('PILOT_TEST',tmp_path)
    monkeypatch.setenv('MARKET_CORTEX_OP_TEST_URL','postgresql://u:private@127.0.0.1/market_cortex')
    with pytest.raises(ValueError,match='TEST_PROFILE_ISOLATION_REQUIRED'): load_profile(p)
    monkeypatch.setenv('MARKET_CORTEX_OP_TEST_URL','postgresql://u:private@127.0.0.1/isolated_test')
    profile, settings=load_profile(p)
    assert 'private' not in json.dumps(settings.safe_summary())
    write('PILOT_TEST','C:/MarketCortexData/child')
    with pytest.raises(ValueError,match='TEST_PROFILE_ISOLATION_REQUIRED'): load_profile(p)
    write('OWNER_MAIN','C:/MarketCortexData')
    with pytest.raises(ValueError,match='OWNER_PROFILE_ISOLATION_REQUIRED'): load_profile(p)
    write('DEVELOPMENT_TEST',tmp_path)
    monkeypatch.setenv('MARKET_CORTEX_OP_TEST_URL','postgresql://u@remote.example/isolated_test')
    with pytest.raises(ValueError,match='DATABASE_MUST_BE_LOOPBACK'): load_profile(p)


def test_missed_schedule_uses_latest_due_slot():
    p=Profile(environment='PILOT_TEST',database_env='MARKET_CORTEX_OP_TEST_URL',data_root='runtime/test')
    assert due_slot(p,datetime(2026,10,8,0,tzinfo=UTC)) == '2026-10-07T07:00:00+05:30'
    assert due_slot(p,datetime(2026,10,8,2,tzinfo=UTC)) == '2026-10-08T07:00:00+05:30'


@pytest.mark.parametrize('recover', [False, True])
def test_rate_limit_is_bounded_and_retryable(monkeypatch, recover):
    """Synthetic transport failures; never generate real provider throttling."""
    requests, delays = [], []
    def respond(request):
        requests.append(request)
        if recover and len(requests) == 2:
            return httpx.Response(200, json=[])
        return httpx.Response(429, headers={'Retry-After': '86400'})
    monkeypatch.setattr('market_cortex.providers.time.sleep', delays.append)
    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        transport=ReadTransport(client)
        if recover:
            assert transport.get('data-api.binance.vision','/api/v3/klines').data == []
            assert len(requests) == 2
        else:
            with pytest.raises(ProviderFailure) as caught:
                transport.get('data-api.binance.vision','/api/v3/klines')
            assert caught.value.code == 'RATE_LIMITED' and caught.value.retryable
            assert len(requests) == 3
    assert sum(delays) <= 2 and all(request.method == 'GET' for request in requests)


def test_backup_never_overwrites_retained_evidence(task_directory):
    destination=task_directory/'retained.mcbackup'; destination.write_bytes(b'original retained evidence')
    settings=Settings('postgresql://u@127.0.0.1/owner',task_directory,'Asia/Kolkata','INR',False,True,'OWNER_MAIN')
    with pytest.raises(FileExistsError): backup(settings,destination,'long-enough-test-passphrase')
    assert destination.read_bytes()==b'original retained evidence'
    source=task_directory/'source'; source.write_bytes(b'new content')
    with pytest.raises(FileExistsError): encrypt_file(source,destination,'long-enough-test-passphrase')
    assert destination.read_bytes()==b'original retained evidence'


def test_atomic_backup_publication_refuses_concurrent_destination(operational_catalog, monkeypatch):
    _,settings,*_=operational_catalog
    final=settings.data_root/'final.mcbackup'
    # Simulate a competing creator after preflight, before atomic publication.
    def competing_creator(source,destination,passphrase):
        encrypt_file(source,destination,passphrase)
        final.write_bytes(b'concurrent retained backup')
    monkeypatch.setattr('market_cortex.backup.encrypt_file',competing_creator)
    with pytest.raises(FileExistsError): backup(settings,final,'long-enough-test-passphrase')
    assert final.read_bytes()==b'concurrent retained backup'
    assert not list(settings.data_root.glob('.staged-backup-*'))


@pytest.fixture
def operational_catalog(task_directory):
    tmp_path = task_directory
    if not SAFE: pytest.skip('dedicated *_test PostgreSQL required')
    schema='operations_'+uuid4().hex
    with connect(DSN) as c: c.execute(sql.SQL('CREATE SCHEMA {}').format(sql.Identifier(schema)))
    dsn=make_conninfo(DSN, options='-csearch_path='+schema)
    try:
        migrate(dsn, Path(__file__).resolve().parents[1])
        catalog=PostgresCatalog(dsn,ArtifactStore(tmp_path))
        settings=Settings(dsn,tmp_path,'Asia/Kolkata','INR',False,True,'PILOT_TEST')
        venue=Venue(venue_id='BINANCE_SPOT',timezone='UTC',session_kind='24x7')
        i,m=identity(venue_id='BINANCE_SPOT',native='BTCUSDT')
        catalog.register_identity([venue],[i],[m])
        cal=SessionCalendar(venue,'BINANCE_SPOT:utc_daily','v1')
        profile=Profile(environment='PILOT_TEST',database_env='MARKET_CORTEX_OP_TEST_URL',data_root=str(tmp_path),symbols=('BTCUSDT',))
        yield catalog,settings,profile,i,m,cal
    finally:
        with connect(DSN) as c: c.execute(sql.SQL('DROP SCHEMA {} CASCADE').format(sql.Identifier(schema)))


def test_refresh_retry_interrupt_idempotence_and_freshness(operational_catalog, monkeypatch):
    catalog,settings,p,i,m,cal=operational_catalog
    now=datetime.now(UTC)
    jobs=enqueue_refresh(p,settings,now,scheduled=True)
    assert enqueue_refresh(p,settings,now,scheduled=True)==jobs
    class Failing:
        def fetch_daily(self,*args): raise ProviderFailure('PROVIDER_UNAVAILABLE',True)
    assert worker(p,settings,adapter=Failing())['status']=='READY'
    assert catalog.head() is None
    with connect(settings.database_url) as c: c.execute("UPDATE jobs SET next_attempt_at=now()-interval '1 second'")
    class Source:
        def fetch_daily(self,*args):
            batch=uuid4()
            b=bar(i,m,cal,day=now.date()-timedelta(days=1),available=now.isoformat())
            b=b.model_copy(update={'envelope':b.envelope.model_copy(update={'source_batch_id':batch})})
            return FetchBatch(batch,'binance',now,'0'*64,(b,),1,'spot_public','raw')
    original=catalog.ingest
    def crash_after_ingest(*args,**kwargs):
        original(*args,**kwargs)
        raise RuntimeError('process interrupted before job completion')
    monkeypatch.setattr(PostgresCatalog,'ingest',lambda self,*a,**k:crash_after_ingest(*a,**k))
    assert worker(p,settings,adapter=Source())['status']=='READY'
    first_head=catalog.head()
    with connect(settings.database_url) as c: c.execute("UPDATE jobs SET next_attempt_at=now()-interval '1 second'")
    monkeypatch.setattr(PostgresCatalog,'ingest',lambda self,*a,**k:original(*a,**k))
    result=worker(p,settings,adapter=Source())
    assert result['status']=='DONE' and result['duplicates']==1 and result['stored']==0
    assert catalog.head()==first_head
    assert status(settings,now)['items'][0]['freshness']=='FRESH'
    assert status(settings,now)['jobs'][0]['result']['completed_at']
    report=preflight(settings,integrity=True)
    assert report['status']=='VALIDATED'
    identity=report['checks']['database_identity']
    assert identity['database'].endswith('_test')
    assert identity['server_address'] in {'127.0.0.1', '::1'}
    assert identity['server_port'] > 0 and identity['server_version']
    assert identity['transaction_read_only']=='on'


def test_permanent_provider_failure_and_job_scope(operational_catalog):
    catalog,settings,p,*_=operational_catalog
    enqueue_refresh(p,settings,datetime.now(UTC),scheduled=True)
    wrong=Settings(settings.database_url,settings.data_root,'Asia/Kolkata','INR',False,True,'DEVELOPMENT_TEST')
    assert worker(p,wrong)['status']=='IDLE'
    class Failing:
        def fetch_daily(self,*args): raise ProviderFailure('ACCESS_DENIED')
    assert worker(p,settings,adapter=Failing())['status']=='DEAD'
    assert catalog.head() is None


def test_preflight_reports_corruption_and_database_failure(operational_catalog):
    catalog,settings,p,i,m,cal=operational_catalog
    now=datetime.now(UTC); batch=uuid4()
    b=bar(i,m,cal,day=now.date()-timedelta(days=1),available=now.isoformat())
    b=b.model_copy(update={'envelope':b.envelope.model_copy(update={'source_batch_id':batch})})
    catalog.ingest([b],cal,source_batch_id=batch,provider_id='binance',raw_hash='0'*64,fetched_at=now)
    path=next(settings.data_root.rglob('*.parquet'))
    path.write_bytes(b'corrupt fixture')
    assert preflight(settings,integrity=True)['checks']['storage']['corrupt']
    missing=Settings('postgresql://u:SECRET@127.0.0.1:1/unavailable_test',settings.data_root,'Asia/Kolkata','INR',False,True,'PILOT_TEST')
    report=preflight(missing)
    assert report['status']=='FAILED' and 'SECRET' not in json.dumps(report)


def test_pending_schema_still_checks_existing_artifacts(operational_catalog):
    catalog,settings,p,i,m,cal=operational_catalog
    now=datetime.now(UTC); batch=uuid4()
    b=bar(i,m,cal,day=now.date()-timedelta(days=1),available=now.isoformat())
    b=b.model_copy(update={'envelope':b.envelope.model_copy(update={'source_batch_id':batch})})
    catalog.ingest([b],cal,source_batch_id=batch,provider_id='binance',raw_hash='0'*64,fetched_at=now)
    # Only this disposable fixture schema loses a migration ledger entry.
    with connect(settings.database_url) as c:
        c.execute("DELETE FROM schema_migrations WHERE name='0013_experimental_research.sql'")
    next(settings.data_root.rglob('*.parquet')).unlink()
    report=preflight(settings,integrity=True)
    assert report['status']=='FAILED'
    assert report['checks']['database']=='CONNECTED_READ_ONLY'
    assert report['checks']['pending_migrations']==['0013_experimental_research.sql']
    assert report['checks']['table_counts']['observations']==1
    assert report['checks']['storage']['referenced']==1 and report['checks']['storage']['missing']
    with connect(settings.database_url) as c:
        assert not c.execute("SELECT 1 FROM schema_migrations WHERE name='0013_experimental_research.sql'").fetchone()


def test_storage_inspection_failure_is_not_authentication_failure(operational_catalog, monkeypatch):
    _,settings,*_=operational_catalog
    def fail(_):
        raise OSError('PRIVATE diagnostic must never appear')
    monkeypatch.setattr(PostgresCatalog,'scan_storage',fail)
    report=preflight(settings,integrity=True)
    assert report['status']=='FAILED'
    assert report['checks']['database']=='CONNECTED_READ_ONLY'
    assert report['checks']['inspection_error']=='OSError'
    assert 'PRIVATE' not in json.dumps(report)
