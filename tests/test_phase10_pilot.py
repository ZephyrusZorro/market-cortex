"""All six genuine Phase 10 dossiers remain inspectable and replayable."""
import json
import os
from pathlib import Path
from uuid import UUID
import pytest
from psycopg.conninfo import conninfo_to_dict
from market_cortex.config import Settings
from market_cortex.missions import MissionService,implementation_hash
from market_cortex.mission_evaluator import evidence
from market_cortex.storage import ArtifactStore,PostgresCatalog

DSN=os.environ.get('MARKET_CORTEX_PHASE10_PILOT_DSN')
ROOT=os.environ.get('MARKET_CORTEX_PHASE10_PILOT_DATA_ROOT')
SAFE=bool(DSN and ROOT and conninfo_to_dict(DSN).get('dbname','').endswith('_test') and Path(ROOT).is_dir())

@pytest.mark.parametrize('label',list('ABCDEF'))
def test_real_pilot_dossier_negative_quant_no_leakage_and_replay(label):
    if not SAFE: pytest.skip('explicit Phase 10 *_test pilot catalog required')
    report=json.loads((Path(__file__).resolve().parents[1]/'docs/cortex/PHASE_10_PILOT_RESULTS.json').read_text(encoding='utf-8'))
    item=next(m for m in report['missions'] if m['label']==label)
    root=Path(ROOT); catalog=PostgresCatalog(DSN,ArtifactStore(root))
    s=MissionService(catalog,Settings(DSN,root,'Asia/Kolkata','INR',False,True,'PILOT_TEST'))
    m=s.store.get(UUID(item['mission_id']))
    assert m.code_hash==implementation_hash()==report['implementation_hash']
    assert m.status in ('COMPLETED','INCONCLUSIVE')
    assert m.usage.api_cost_inr==0 and m.evaluator['budgets_respected']
    assert not m.evaluator['rejected_claims']
    rows=evidence(m)
    assert next(e.value for e in rows if e.label=='Momentum temporal OOS return')==-.07817165407921722
    assert next(e.value for e in rows if e.label=='Momentum temporal OOS N')==82
    assert '-7.82%' in m.report and 'NO SUPPORTED EDGE' in m.report
    replay = s.replay(m.mission_id)
    assert replay['matched'], replay
    if label=='B': assert m.context.symbol=='ETHUSDT' and m.context.compare_symbol=='BTCUSDT'
    if label=='C': assert any(e.kind=='contradiction' and e.tool_id=='mission.challenge_candidate' for e in rows)
    if label=='D': assert any(h.hypothesis_id=='historical_momentum_support' and h.status=='CONTRADICTED' for h in m.hypotheses)
    if label=='E': assert any(e.label.startswith('derivatives.') for e in rows) and any(e.label.startswith('macro.') for e in rows)
    if label=='F':
        assert m.previous_context and m.previous_context.as_of<m.context.as_of
        assert m.previous_context.context_manifest_id is None
        older=[e for e in rows if e.as_of==m.previous_context.as_of]
        assert not any(e.kind=='context_fact' for e in older)
        assert m.usage.historical_comparisons==3
    assert report['canonical_counts_before']==report['canonical_counts_after']
