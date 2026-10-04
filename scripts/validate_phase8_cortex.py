"""Explain the stored acceptance studies locally, without rerunning a search."""
import json
import os
import sys
import time
from datetime import datetime,timezone
from pathlib import Path
from uuid import UUID

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from psycopg.conninfo import conninfo_to_dict
from market_cortex.config import Settings
from market_cortex.cortex import CortexService
from market_cortex.cortex_contracts import ResearchRequest
from market_cortex.cortex_gateway import NoModelGateway
from market_cortex.storage import ArtifactStore,PostgresCatalog


def main():
    project=Path(__file__).resolve().parents[1]
    path=project/'docs/quant/PHASE_8_PILOT_RESULTS.json'
    report=json.loads(path.read_text(encoding='utf-8'))
    dsn=os.environ['MARKET_CORTEX_PHASE8_PILOT_DSN']
    if not conninfo_to_dict(dsn).get('dbname','').endswith('_test'):
        raise ValueError('ISOLATED_TEST_DB_REQUIRED')
    root=Path(os.environ['MARKET_CORTEX_PHASE8_PILOT_DATA_ROOT']).resolve()
    catalog=PostgresCatalog(dsn,ArtifactStore(root))
    service=CortexService(catalog,Settings(dsn,root,'Asia/Kolkata','INR',True,True,'PILOT_TEST'),gateway=NoModelGateway())
    cases=[('strategy_and_walk_forward',{'backtest_run_id':UUID(report['strategies'][0]['run_id']),
        'quant_study_id':UUID(report['walk_forward']['study_id'])},
        'How did momentum perform after costs and out of sample? Explain the drawdown and overfitting limits.')]
    if report['monte_carlo']:
        cases.append(('monte_carlo',{'quant_study_id':UUID(report['monte_carlo']['study_id'])},
            'Explain this Monte Carlo study, its sample size, period, costs and limitations.'))
    results=[]
    for name,arguments,question in cases:
        timer=time.perf_counter()
        run=service.research(ResearchRequest(question=question,mode='pinned',manifest_id=UUID(report['manifest_after']),
            as_of=datetime.now(timezone.utc),**arguments))
        replay=service.replay(run.run_id)
        if run.failure_state is not None or not replay['evidence_reproducible']:
            raise ValueError('CORTEX_QUANT_EVIDENCE_ACCEPTANCE_FAILED')
        if 'costs' not in run.answer or 'OOS' not in run.answer or '2024-01-01' not in run.answer:
            raise ValueError('CORTEX_QUANT_DISCLOSURE_MISSING')
        results.append({'case':name,'research_run_id':str(run.run_id),'tool_ids':[tool.tool_id for tool in run.tools],
            'model_provider':run.model_provider,'failure_state':run.failure_state,'evidence_hash':run.evidence_hash,
            'replay':replay,'elapsed_seconds':time.perf_counter()-timer})
        print(name,results[-1],flush=True)
    report['cortex_quant']=results
    path.write_text(json.dumps(report,indent=2,default=str)+'\n',encoding='utf-8')


if __name__=='__main__':main()
