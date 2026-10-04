"""Isolated public-data Quant Lab acceptance experiment. Never tune for profits."""
import argparse,json,os,time
from datetime import datetime,date,timezone
from pathlib import Path
from uuid import UUID
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))

from psycopg.conninfo import conninfo_to_dict

from market_cortex.database import connect,migrate
from market_cortex.identity import IdentityRegistry
from market_cortex.providers import BinanceDaily,ProviderFailure
from market_cortex.quant import QuantService
from market_cortex.quant_contracts import (BacktestDefinition,CompareRequest,GridRequest,MonteCarloRequest,WalkForwardDefinition)
from market_cortex.storage import ArtifactStore,PostgresCatalog


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--backfill',action='store_true');args=parser.parse_args()
    dsn=os.environ['MARKET_CORTEX_PHASE8_PILOT_DSN']
    if not conninfo_to_dict(dsn).get('dbname','').endswith('_test'):
        raise ValueError('ISOLATED_TEST_DB_REQUIRED')
    root=Path(os.environ['MARKET_CORTEX_PHASE8_PILOT_DATA_ROOT']).resolve()
    project=Path(__file__).resolve().parents[1];migrate(dsn,project)
    catalog=PostgresCatalog(dsn,ArtifactStore(root))
    head_at_start=catalog.head();now=datetime.now(timezone.utc)
    # Preserved Phase 7 pin: the public backfill may already have completed in a
    # previous acceptance attempt. Never invent another ingestion in a rerun.
    before=UUID('f87c2a62-7cdf-443d-8eed-0575b6dd8e17')
    with connect(dsn) as c:
        if not c.execute('SELECT 1 FROM dataset_manifests WHERE manifest_id=%s',(before,)).fetchone():
            before=head_at_start
    service=QuantService(catalog,'PILOT_TEST',progress=lambda message:print(message,flush=True))
    old_definition=BacktestDefinition(strategy_id='equal_weight',manifest_id=before,source_as_of=now,
        start=date(2025,9,1),end=date(2026,10,3),replay_policy='HISTORICAL_RECONSTRUCTION')
    old_run=service.run(old_definition)
    backfill=[]
    if args.backfill:
        registry=IdentityRegistry(*catalog.load_identity())
        provider=BinanceDaily()
        for symbol in ('BTCUSDT','ETHUSDT','SOLUSDT','BNBUSDT','XRPUSDT'):
            start=datetime(2024,1,1,tzinfo=timezone.utc);end=datetime(2025,9,1,tzinfo=timezone.utc)
            instrument=registry.resolve(provider_id='binance',identifier_type='exchange_pair',identifier_value=symbol,at=start,known_at=now)
            mapping=next(m for m in registry.mappings if m.instrument_id==instrument.instrument_id and m.identifier_value==symbol)
            cal=catalog.load_calendar(instrument.primary_venue_id,start,end)
            try:
                batch=provider.fetch_daily(instrument,mapping,cal,start,end)
                result=catalog.ingest(list(batch.bars),cal,source_batch_id=batch.batch_id,provider_id='binance',raw_hash=batch.raw_hash,fetched_at=batch.fetched_at)
                backfill.append({'symbol':symbol,'stored':result.stored,'duplicates':result.duplicates,'manifest_id':str(result.manifest_id)})
                print('Public immutable backfill',backfill[-1],flush=True)
            except ProviderFailure as exc:
                backfill.append({'symbol':symbol,'status':exc.code})
                print('Public backfill unavailable',symbol,exc.code,flush=True)
    now=datetime.now(timezone.utc);manifest=catalog.head()
    service=QuantService(catalog,'PILOT_TEST',progress=lambda message:print(message,flush=True))
    source,_=service.source(old_definition.model_copy(update={'manifest_id':manifest,'source_as_of':now}))
    firsts={}
    for b in source['bars']:
        firsts.setdefault(b['envelope']['instrument_id'],[]).append(b['session_date'])
    start=date.fromisoformat(max(min(v) for v in firsts.values()))
    d=old_definition.model_copy(update={'manifest_id':manifest,'source_as_of':now,'start':start,'strategy_id':'momentum'})
    results=[];timer=time.perf_counter()
    strict=service.run(d.model_copy(update={'replay_policy':'AS_RECORDED'}))
    print('Strict recorded result',strict.metrics,flush=True)
    for name in ('momentum','breakout','trend_continuation','pullback','equal_weight'):
        run=service.run(d.model_copy(update={'strategy_id':name}))
        results.append({'strategy':name,'run_id':str(run.run_id),'metrics':run.metrics,'elapsed_ms':run.elapsed_ms,'warnings':run.warnings})
        print('Research result',name,run.metrics,flush=True)
    wf=service.walk_forward(WalkForwardDefinition(definition=d,holding_sessions=[5,10,15],stop_fraction=[.06,.08],
        train_sessions=180,validation_sessions=90,step_sessions=90,max_folds=6))
    print('Walk-forward',wf['study_id'],wf['result']['oos_N'],flush=True)
    sensitivity=service.sensitivity(GridRequest(definition=d,holding_sessions=[5,10,15],stop_fraction=[.06,.08,.10]))
    robust=service.robustness(d)
    first=UUID(results[0]['run_id']);mc=None
    if results[0]['metrics']['N']>=2:
        mc=service.monte_carlo(MonteCarloRequest(run_id=first,simulations=1000,seed=20261004))
    comparison=service.compare(CompareRequest(run_ids=[UUID(r['run_id']) for r in results]))
    replay=service.replay(old_run.run_id)
    with connect(dsn) as c:
        backfill_evidence=c.execute('''SELECT o.manifest_id,m.created_at,count(*),min(o.session_date),max(o.session_date)
            FROM observations o JOIN dataset_manifests m USING(manifest_id)
            WHERE o.provider_id='binance' AND o.session_date BETWEEN '2024-01-01' AND '2025-08-31'
            GROUP BY o.manifest_id,m.created_at ORDER BY m.created_at''').fetchall()
    report={'generated_at':datetime.now(timezone.utc).isoformat(),'manifest_before':str(before),'manifest_after':str(manifest),
        'head_at_script_start':str(head_at_start),'backfill_this_invocation':backfill,
        'recorded_backfill_evidence':[{'manifest_id':str(k),'created_at':at.isoformat(),'stored':n,'first_session':str(a),'last_session':str(b)} for k,at,n,a,b in backfill_evidence],
        'start':str(start),'end':str(d.end),'sessions_per_asset':(d.end-start).days+1,
        'source_as_of':now.isoformat(),'strict_recorded':{'run_id':str(strict.run_id),'metrics':strict.metrics},
        'strategies':results,'walk_forward':wf,'sensitivity':sensitivity,'robustness':robust,'monte_carlo':mc,
        'comparison':comparison,'old_pinned_replay_after_backfill':replay,'storage':catalog.scan_storage(),
        'performance_seconds':time.perf_counter()-timer,'search_counts':service.store.search_counts()}
    output=project/'docs'/'quant'/'PHASE_8_PILOT_RESULTS.json';output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(report,indent=2,default=str),encoding='utf-8')
    print('SAVED',output,flush=True)


if __name__=='__main__':main()
