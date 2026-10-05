"""Six actual stored-data missions. Only research artifacts in an explicit *_test DB."""
import argparse
import json
import os
import sys
from datetime import timedelta
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from psycopg.conninfo import conninfo_to_dict
from market_cortex.config import Settings
from market_cortex.database import connect,migrate
from market_cortex.mission_contracts import MissionRequest
from market_cortex.mission_evaluator import evidence
from market_cortex.missions import MissionService,now,implementation_hash
from market_cortex.storage import ArtifactStore,PostgresCatalog


def main():
    parser=argparse.ArgumentParser(); parser.add_argument('--output',type=Path,required=True); args=parser.parse_args()
    dsn=os.environ.get('MARKET_CORTEX_PHASE10_PILOT_DSN')
    root=Path(os.environ['MARKET_CORTEX_PHASE10_PILOT_DATA_ROOT'])
    if not dsn or not conninfo_to_dict(dsn).get('dbname','').endswith('_test') or not root.is_dir():
        raise SystemExit('EXPLICIT_PILOT_TEST_CONFIGURATION_REQUIRED')
    migrate(dsn,Path(__file__).resolve().parents[1])
    catalog=PostgresCatalog(dsn,ArtifactStore(root)); head=catalog.head()
    settings=Settings(dsn,root,'Asia/Kolkata','INR',False,True,'PILOT_TEST'); service=MissionService(catalog,settings)
    with connect(dsn) as c:
        prior=json.loads((Path(__file__).resolve().parents[1]/'docs/quant/PHASE_8_PILOT_RESULTS.json').read_text(encoding='utf-8'))['manifest_before']
        older=c.execute('SELECT manifest_id,created_at FROM dataset_manifests WHERE manifest_id=%s',(prior,)).fetchone()
        before={table:c.execute('SELECT count(*) FROM '+table).fetchone()[0] for table in ('observations','context_facts','opportunity_candidates','research_thesis_versions','portfolio_versions','prediction_records','journal_revisions','quant_artifacts')}
    cutoff=now()
    requests=[
        ('A',MissionRequest(goal='Analyze BTCUSDT comprehensively, including whether its momentum is attractive.',symbol='BTCUSDT')),
        ('B',MissionRequest(goal='Compare ETHUSDT versus BTCUSDT and challenge relative momentum evidence.',symbol='ETHUSDT',compare_symbol='BTCUSDT')),
        ('C',MissionRequest(goal='Challenge the strongest current opportunity candidate using canonical conditions and counter-evidence.',template='thesis_challenge')),
        ('D',MissionRequest(goal='Determine whether momentum currently has quantitative historical support.',symbol='BTCUSDT',mode='STRATEGY_RESEARCH',template='strategy_review')),
        ('E',MissionRequest(goal='Explain what recorded Binance derivatives and Treasury macro add to BTC context.',symbol='BTCUSDT',template='event_context')),
        ('F',MissionRequest(goal='Compare current BTC context with an older manifest; distinguish data additions from market changes.',symbol='BTCUSDT',mode='CHANGE_ANALYSIS',template='what_changed',older_manifest_id=older[0],older_as_of=older[1]+timedelta(microseconds=1))),
    ]
    results=[]
    for label,request in requests:
        request=request.model_copy(update={'as_of':cutoff,'manifest_id':head,'duplicate_policy':'fresh'})
        planned=service.create(request); result=service.run(planned.mission_id); replay=service.replay(result.mission_id)
        records=evidence(result)
        if result.status not in ('COMPLETED','INCONCLUSIVE'): raise AssertionError('PILOT_MISSION_INCOMPLETE:'+label+':'+str(result.termination_reason))
        if not replay['matched'] or result.evaluator['rejected_claims']: raise AssertionError('PILOT_REPLAY_OR_GROUNDING_FAILED:'+label)
        oos=next((e for e in records if e.label=='Momentum temporal OOS return'),None)
        n=next((e for e in records if e.label=='Momentum temporal OOS N'),None)
        assert oos and oos.value==-.07817165407921722 and n and n.value==82
        assert result.evaluator['quantitative_support']=='NO_SUPPORTED_EDGE_ESTABLISHED'
        summary={'label':label,'mission_id':str(result.mission_id),'revision':result.revision,'goal':request.goal,'status':result.status,
            'termination_reason':result.termination_reason,'context':result.context.model_dump(mode='json'),
            'previous_context':result.previous_context.model_dump(mode='json') if result.previous_context else None,
            'tool_ids':[s.tool_id for s in result.plan.steps],'usage':result.usage.model_dump(mode='json'),
            'evidence_N':len(records),'claim_N':len(result.claims),'contradiction_N':len(result.contradictions),
            'hypotheses':[h.model_dump(mode='json') for h in result.hypotheses],'evaluator':result.evaluator,
            'phase8_oos_return':oos.value,'phase8_oos_N':n.value,'replay':replay,'content_hash':result.content_hash,
            'model_metadata':result.model_metadata,'frozen_references':result.frozen_references}
        results.append(summary)
        args.output.parent.mkdir(parents=True,exist_ok=True)
        (args.output.parent/f'PHASE_10_MISSION_{label}.md').write_text(result.report,encoding='utf-8')
        print(f'{label} {result.status}; tools={result.usage.tool_calls}; evidence={len(records)}; replay={replay["matched"]}',flush=True)
    with connect(dsn) as c:
        after={table:c.execute('SELECT count(*) FROM '+table).fetchone()[0] for table in before}
    assert before==after and head==catalog.head()
    report={'validated_at':now().isoformat(),'environment':'PILOT_TEST','market_head':str(head),'implementation_hash':implementation_hash(),
        'canonical_counts_before':before,'canonical_counts_after':after,'paid_api_cost_inr':0,
        'model_runtime':'NONE_DISCOVERED; DETERMINISTIC_FALLBACK','missions':results,'diff':service.diff(results[0]['mission_id'],results[-1]['mission_id'])}
    args.output.write_text(json.dumps(report,indent=2,default=str),encoding='utf-8')
    return 0


if __name__=='__main__': raise SystemExit(main())
