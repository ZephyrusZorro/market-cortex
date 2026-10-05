"""Read actual ingested public facts and prove a disposable encrypted contextual restore."""
import json
import os
import secrets
import shutil
import tempfile
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from uuid import NAMESPACE_URL, UUID, uuid4, uuid5
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'src'))

from fastapi.testclient import TestClient
from psycopg import sql
from psycopg.conninfo import conninfo_to_dict, make_conninfo
from psycopg.types.json import Jsonb

from market_cortex.api import create_app
from market_cortex.backup import backup, restore
from market_cortex.config import Settings
from market_cortex.cortex import CortexService
from market_cortex.cortex_contracts import ResearchRequest
from market_cortex.database import connect, migrate
from market_cortex.intelligence import IntelligenceService, event_study
from market_cortex.intelligence_contracts import ContextRequest
from market_cortex.intelligence_sources import coverage
from market_cortex.intelligence_store import ContextStore, digest
from market_cortex.storage import ArtifactStore, PostgresCatalog
from market_cortex.quant import QuantService
from market_cortex.quant_contracts import BacktestDefinition


def main():
    settings=Settings.load()
    config=conninfo_to_dict(settings.database_url or '')
    if not config.get('dbname','').endswith('_test') or config.get('port')!='55432' or config.get('user')!='cortex_test':
        raise RuntimeError('ISOLATED_PHASE9_TEST_CATALOG_REQUIRED')
    project=Path(__file__).resolve().parents[1]
    catalog=PostgresCatalog(settings.database_url,ArtifactStore(settings.data_root))
    service=IntelligenceService(catalog)
    cutoff=datetime.now(timezone.utc)
    iid=next(m.instrument_id for m in catalog.load_identity()[1] if m.provider_id=='binance' and m.venue_id=='BINANCE_SPOT' and m.identifier_value=='BTCUSDT')
    snap=service.snapshot(ContextRequest(as_of=cutoff,instrument_id=iid,market_manifest_id=catalog.head()),persist=True)
    registry=coverage(service.store,cutoff)
    assert {s.provider for s in registry if s.status=='PUBLIC_VALIDATED'}=={'binance_usdm','us_treasury'}
    assert service.store.snapshot(snap.snapshot_id).content_hash==snap.content_hash
    client=TestClient(create_app(settings,catalog))
    params={'as_of':cutoff.isoformat(),'instrument_id':str(iid),'market_manifest_id':str(catalog.head()),'context_manifest_id':str(snap.context_manifest_id)}
    actual=client.get('/api/v1/intelligence/context',params=params)
    assert actual.status_code==200 and actual.json()['content_hash']==snap.content_hash
    research=CortexService(catalog,settings).research(ResearchRequest(question='What is BTC funding, open interest, macro context and event coverage? Which domains are unavailable?',
        mode='pinned',manifest_id=catalog.head(),as_of=cutoff,symbol='BTCUSDT',context_manifest_id=snap.context_manifest_id))
    assert research.failure_state is None and 'SOURCE_FACT' in research.answer and 'EVENT_DATA_UNAVAILABLE' in research.answer
    assert 'options coverage: UNKNOWN' in research.answer and 'onchain coverage: UNKNOWN' in research.answer
    replay=CortexService(catalog,settings).replay(research.run_id)
    assert replay['evidence_reproducible'] is True
    inventory=catalog.scan_storage()
    assert not inventory['corrupt'] and not inventory['missing']
    import pyarrow.parquet as pq
    files=[]
    for a in service.store.artifacts():
        assert catalog.artifacts.verify(settings.data_root/a.relative_path)==a.content_hash
        table=pq.read_table(settings.data_root/a.relative_path,columns=['fact_json'])
        assert table.num_rows==a.row_count
        files.append({'sha256':a.content_hash,'rows':a.row_count})
    allfacts=service.store.facts(snap.context_manifest_id,cutoff)
    frozen_context=service.store.freeze(cutoff)
    # One predeclared short window verifies the filter path, not profitability.
    quant=QuantService(catalog,'PILOT_TEST')
    definition=BacktestDefinition(strategy_id='momentum',manifest_id=catalog.head(),source_as_of=cutoff,
        start=date(2026,9,29),end=date(2026,10,3),replay_policy='HISTORICAL_RECONSTRUCTION')
    comparison=[]
    for context_filter in ('none','funding_nonpositive'):
        result=quant.run(definition.model_copy(update={'context_filter':context_filter}))
        assert all(not d.contextual_evidence['fact_ids'] for d in result.decisions)
        if context_filter!='none':
            assert not any(d.enter for d in result.decisions)
        quant_replay=quant.replay(result.run_id)
        assert quant_replay['status']=='MATCH'
        comparison.append({'context_filter':context_filter,'run_id':str(result.run_id),'result_hash':result.result_hash,
            'decision_N':len(result.decisions),'known_context_fact_N':0,'metrics':result.metrics,'replay':quant_replay})
    # Source fixture demonstration has no live event claim or catalog writes.
    sys.path.insert(0,str(project/'tests'))
    from test_foundation import identity, bar, calendar
    fixture_i,fixture_m=identity(); fixture_calendar=calendar()
    fixture_bars=[]
    for n in range(20):
        day=date(2025,1,1)+timedelta(days=n)
        value=bar(fixture_i,fixture_m,fixture_calendar,day=day,close=str(100+n))
        fixture_bars.append(value.model_copy(update={'envelope':value.envelope.model_copy(update={
            'observation_id':uuid5(NAMESPACE_URL,'phase9-event-study-fixture:'+str(day))})}))
    event_result=event_study(fixture_bars,fixture_calendar,datetime(2025,1,10,tzinfo=timezone.utc),before=3,after=3,classification='SYNTHETIC_TEST')
    assert event_result['status']=='AVAILABLE' and abs(event_result['post_return']-(112/108-1))<1e-12
    report={'schema_version':'phase9_live_validation_v1','validated_at':cutoff.isoformat(),'environment':'PILOT_TEST',
        'market_manifest_id':str(catalog.head()),'context_manifest_id':str(snap.context_manifest_id),'snapshot_id':str(snap.snapshot_id),
        'snapshot_hash':snap.content_hash,'source_statuses':[s.model_dump(mode='json') for s in registry],
        'history':{domain:{'N':len([f for f in allfacts if f.domain==domain]),
                         'first_event_at':min((f.envelope.event_at.isoformat() for f in allfacts if f.domain==domain),default=None),
                         'last_event_at':max((f.envelope.event_at.isoformat() for f in allfacts if f.domain==domain),default=None)}
                   for domain in ('macro','derivatives')},
        'btc_derivatives':snap.dimensions['derivatives'].model_dump(mode='json'),'event_risk':snap.event_risk,
        'parquet_files':files,'inventory':inventory,'cortex':{'run_id':str(research.run_id),'answer':research.answer,'replay':replay},
        'synthetic_event_study':event_result,
        'quant_comparison':{'status':'INSUFFICIENT_AS_RECORDED_CONTEXT_HISTORY','reason':'Facts arrived after all comparison decision cutoffs; price reconstruction never reconstructs contextual availability',
                           'predeclared_window':['2026-09-29','2026-10-03'],'parameter_search':False,'rows':comparison,
                           'preserved_phase8_momentum_oos_return':-.07817165407921722,'preserved_phase8_momentum_oos_N':82}}
    # Copy the complete pinned context lineage into test-only catalogs, preserving hashes/times.
    admin=make_conninfo(settings.database_url,dbname='postgres')
    suffix=uuid4().hex[:12]
    names=['phase9_backup_'+suffix+'_test','phase9_restore_'+suffix+'_test']
    created=[]
    began=time.perf_counter()
    try:
        with connect(admin) as c:
            c.autocommit=True
            for name in names:
                c.execute(sql.SQL('CREATE DATABASE {}').format(sql.Identifier(name)))
                created.append(name)
        source_dsn=make_conninfo(settings.database_url,dbname=names[0]); restore_dsn=make_conninfo(settings.database_url,dbname=names[1])
        with tempfile.TemporaryDirectory(prefix='market-cortex-phase9-restore-') as work:
            root=Path(work); source_root=root/'source'; restored_root=root/'restored'
            migrate(source_dsn,project)
            copy=PostgresCatalog(source_dsn,ArtifactStore(source_root))
            manifest_ids=[UUID(mid) for mid in frozen_context['manifest_times']]
            with connect(settings.database_url) as original, connect(source_dsn) as target_catalog:
                for table,json_column,query,args in (
                    ('context_facts',11,'SELECT * FROM context_facts WHERE fact_id=ANY(%s)',([UUID(p['envelope']['observation_id']) for p in frozen_context['facts']],)),
                    ('context_files',None,'SELECT * FROM context_files WHERE content_hash=ANY(%s)',([a.content_hash for a in service.store.artifacts()],)),
                    ('context_manifests',4,'SELECT * FROM context_manifests WHERE manifest_id=ANY(%s) ORDER BY created_at',(manifest_ids,)),
                    ('context_manifest_facts',None,'SELECT * FROM context_manifest_facts WHERE manifest_id=ANY(%s)',(manifest_ids,)),
                    ('context_manifest_files',None,'SELECT * FROM context_manifest_files WHERE manifest_id=ANY(%s)',(manifest_ids,)),
                ):
                    for row in original.execute(query,args).fetchall():
                        values=list(row)
                        if json_column is not None: values[json_column]=Jsonb(values[json_column])
                        statement=sql.SQL('INSERT INTO {} VALUES ({})').format(sql.Identifier(table),sql.SQL(',').join(sql.Placeholder() for _ in values))
                        target_catalog.execute(statement,values)
                target_catalog.execute('INSERT INTO context_head VALUES (true,%s)',(snap.context_manifest_id,))
            for artifact in service.store.artifacts():
                destination=source_root/artifact.relative_path
                if not destination.resolve().is_relative_to(source_root.resolve()): raise RuntimeError('UNSAFE_ARTIFACT_PATH')
                destination.parent.mkdir(parents=True,exist_ok=True)
                shutil.copyfile(settings.data_root/artifact.relative_path,destination)
            ContextStore(copy).save_snapshot(snap)
            backup_settings=Settings(source_dsn,source_root,'Asia/Kolkata','INR',False,True,'PILOT_TEST')
            archive=root/'context.mcbackup'; passphrase=secrets.token_urlsafe(32)
            backup(backup_settings,archive,passphrase)
            restored=restore(archive,restored_root,restore_dsn,source_dsn,passphrase)
            result=ContextStore(PostgresCatalog(restore_dsn,ArtifactStore(restored_root)))
            assert result.snapshot(snap.snapshot_id).content_hash==snap.content_hash
            assert sorted(digest(f.model_dump(mode='json')) for f in result.facts(result.resolve(datetime.now(timezone.utc)),datetime.now(timezone.utc)))==sorted(digest(f.model_dump(mode='json')) for f in allfacts)
            restored_frozen=result.freeze(cutoff)
            assert digest(restored_frozen)==digest(frozen_context)
            assert not result.catalog.scan_storage()['corrupt'] and not result.catalog.scan_storage()['missing']
            report['encrypted_restore']={'status':'MATCH','copied_real_fact_N':len(allfacts),'artifact_count':restored['artifact_count'],
                                         'stored_revision_N':len(frozen_context['facts']), 'frozen_lineage_hash':digest(frozen_context),
                                         'scope':'complete pinned contextual lineage, original timestamps/revisions/manifests/files and accepted snapshot; foundation restore separately covered by regression',
                                         'elapsed_seconds':time.perf_counter()-began}
    finally:
        with connect(admin) as c:
            c.autocommit=True
            for name in reversed(created):
                c.execute('SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname=%s AND pid<>pg_backend_pid()', (name,))
                c.execute(sql.SQL('DROP DATABASE {}').format(sql.Identifier(name)))
    target=project/'docs/intelligence/PHASE_9_LIVE_RESULTS.json'
    target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(json.dumps(report,indent=2,default=str)+'\n',encoding='utf-8')
    print(json.dumps({'status':'PASS','facts':len(allfacts),'snapshot_hash':snap.content_hash,'restore':'MATCH','report':target.name}))


if __name__=='__main__': main()
