"""Actual pilot recovery drill. Creates/drops only its fresh random *_test DB."""
import argparse
import json
import secrets
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID, uuid4
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from psycopg import sql
from psycopg.conninfo import make_conninfo
from market_cortex.operations import load_profile, catalog_for
from market_cortex.config import Settings
from market_cortex.database import connect
from market_cortex.backup import backup, restore
from market_cortex.storage import ArtifactStore,PostgresCatalog
from market_cortex.cortex import CortexService
from market_cortex.experiments import ExperimentService
from market_cortex.experiment_tools import replay_dossier
from market_cortex.personalization import PersonalizationService
from market_cortex.quant_store import digest


def main():
    p=argparse.ArgumentParser(); p.add_argument('--profile',type=Path,required=True)
    p.add_argument('--pilot-results',type=Path,default=Path('docs/operations/OPERATIONAL_PILOT_RESULTS.json'))
    p.add_argument('--output',type=Path,default=Path('docs/operations/OPERATIONAL_RESTORE_RESULTS.json'))
    args=p.parse_args()
    _,settings=load_profile(args.profile)
    if settings.environment=='OWNER_MAIN': raise ValueError('ISOLATED_PILOT_REQUIRED')
    root=Path(__file__).resolve().parents[1]; source=catalog_for(settings); dsn=settings.database_url
    with connect(dsn) as c:
        tables=[r[0] for r in c.execute("SELECT tablename FROM pg_tables WHERE schemaname=current_schema() ORDER BY tablename")]
        before={name:c.execute(sql.SQL('SELECT count(*) FROM {}').format(sql.Identifier(name))).fetchone()[0] for name in tables}
        context_head=str(c.execute('SELECT manifest_id FROM context_head WHERE singleton=true').fetchone()[0])
    pilot=json.loads(args.pilot_results.read_text(encoding='utf-8'))
    phase12=json.loads((root/'docs/quant/PHASE_12_PILOT_RESULTS.json').read_text(encoding='utf-8'))
    personal=json.loads((root/'docs/personalization/PHASE_11_PILOT_RESULTS.json').read_text(encoding='utf-8'))
    target_name='operational_restore_'+uuid4().hex+'_test'; target_dsn=make_conninfo(dsn,dbname=target_name)
    with connect(dsn) as c:
        c.autocommit=True; c.execute(sql.SQL("CREATE DATABASE {} TEMPLATE template0 ENCODING 'UTF8'").format(sql.Identifier(target_name)))
    try:
        with tempfile.TemporaryDirectory(prefix='market-cortex-operational-restore-') as directory:
            work=Path(directory); restored=work/'restored'; encrypted=work/'pilot.mcbackup'
            passphrase=secrets.token_urlsafe(40)
            t=time.perf_counter(); created=backup(settings,encrypted,passphrase); backup_ms=round((time.perf_counter()-t)*1000,2)
            t=time.perf_counter(); recovered=restore(encrypted,restored,target_dsn,dsn,passphrase); restore_ms=round((time.perf_counter()-t)*1000,2)
            target=PostgresCatalog(target_dsn,ArtifactStore(restored))
            target_settings=Settings(target_dsn,restored,'Asia/Kolkata','INR',False,True,'PILOT_TEST')
            assert str(target.head())==created['head_manifest_id']==pilot['market_head']
            inventory=target.scan_storage(); assert not inventory['missing'] and not inventory['corrupt'] and not inventory['unreferenced']
            with connect(target_dsn) as c:
                after={name:c.execute(sql.SQL('SELECT count(*) FROM {}').format(sql.Identifier(name))).fetchone()[0] for name in tables}
                assert str(c.execute('SELECT manifest_id FROM context_head WHERE singleton=true').fetchone()[0])==context_head
                assert c.execute('SHOW server_encoding').fetchone()[0]=='UTF8'
            # Other pilot tests can append while pg_dump acquires its snapshot.
            # Immutable source counts are lower bounds, not a fabricated simultaneous snapshot.
            assert all(after[name]>=before[name] for name in tables)
            cutoff=datetime.fromisoformat(pilot['as_of'])
            with connect(dsn) as c:
                instrument_id=c.execute("SELECT instrument_id FROM identifier_mappings WHERE provider_id='binance' AND identifier_value='BTCUSDT'").fetchone()[0]
            start=datetime(2024,1,1,tzinfo=timezone.utc); end=datetime.fromisoformat(pilot['evaluation_date']).replace(tzinfo=timezone.utc)
            from datetime import timedelta
            kwargs=dict(instrument_id=instrument_id,start=start,end=end+timedelta(days=1),as_of=cutoff,manifest_id=source.head(),provider_id='binance')
            original=source.bars(**kwargs)[1]; recovered_bars=target.bars(**kwargs)[1]
            original_hash=digest([x.model_dump(mode='json') for x in original]); recovered_hash=digest([x.model_dump(mode='json') for x in recovered_bars])
            assert original_hash==recovered_hash and len(original)==pilot['chart_bar_N']
            cortex=CortexService(target,target_settings); run=cortex.store.get(UUID(pilot['research_run_id']))
            assert run and run.evidence_hash==pilot['research_evidence_hash']
            cortex_replay=cortex.replay(run.run_id); assert cortex_replay['evidence_reproducible']
            experiment=ExperimentService(target,target_settings); studies=[]
            for row in phase12['experiments']:
                result=experiment.store.result(UUID(row['experiment_id']))['result']
                assert result['result_hash']==row['result_hash']
                experiment.store.quant.get(UUID(result['dataset_ref']['artifact_id']),'experiment_dataset')
                for ref in result['model_refs']: experiment.store.quant.get(UUID(ref['artifact_id']),'experiment_model')
                studies.append({'experiment_id':row['experiment_id'],'result_hash':row['result_hash'],'models':len(result['model_refs'])})
            t=time.perf_counter(); model_replay=experiment.replay(UUID(phase12['experiments'][2]['experiment_id']))
            replay_ms=round((time.perf_counter()-t)*1000,2); assert model_replay['status']=='MATCH'
            dossier=replay_dossier(experiment,UUID(phase12['dossier_ref']['artifact_id'])); assert dossier['status']=='MATCH'
            ps=PersonalizationService(target,target_settings); snapshot=ps.store.snapshot(UUID(personal['snapshot_id']))
            personal_replay=ps.verify_snapshot(snapshot); assert personal_replay['matched']
            with connect(target_dsn) as c:
                jobs=c.execute("SELECT count(*) FROM jobs WHERE kind='operational_daily_refresh_v1' AND state='done' AND payload ? 'operational_result'").fetchone()[0]
                assert jobs>=10
            result={'status':'VALIDATED','validated_at':datetime.now(timezone.utc).isoformat(),'environment':'PILOT_TEST',
                'owner_main':'UNTOUCHED','market_head':str(target.head()),'context_head':context_head,
                'table_counts_before_backup':before,'restored_table_counts':after,'count_comparison':'SOURCE_LOWER_BOUNDS; PG_DUMP_CONSISTENT_SNAPSHOT',
                'parquet_artifact_N':recovered['artifact_count'],'storage':inventory,'encrypted_bytes':encrypted.stat().st_size,
                'market_query':{'N':len(original),'source_hash':original_hash,'restored_hash':recovered_hash},
                'research_run_id':str(run.run_id),'research_replay':cortex_replay,'experiment_checks':studies,
                'model_replay':model_replay,'dossier_replay':dossier,'personal_snapshot_replay':personal_replay,
                'refresh_jobs_restored':jobs,'timings_ms':{'backup':backup_ms,'restore':restore_ms,'ridge_recompute_replay':replay_ms},
                'retained_owner_backup':'NOT_ESTABLISHED','disposable_database_and_files':'CLEANED_AFTER_DRILL'}
            args.output.write_text(json.dumps(result,indent=2,default=str),encoding='utf-8')
            print(json.dumps({'status':'VALIDATED','artifact_N':result['parquet_artifact_N'],'encrypted_bytes':result['encrypted_bytes'],'timings_ms':result['timings_ms']}))
    finally:
        with connect(dsn) as c:
            c.autocommit=True; c.execute(sql.SQL('DROP DATABASE {}').format(sql.Identifier(target_name)))


if __name__=='__main__':
    try: main()
    except Exception as error:
        print(json.dumps({'status':'FAILED','error_type':type(error).__name__})); raise SystemExit(1)
