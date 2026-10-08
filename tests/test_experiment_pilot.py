"""Real stored Phase 12 evidence plus preserved Phase 8/10/11 release records."""
import json
import os
from pathlib import Path
from uuid import UUID
import pytest
from psycopg.conninfo import conninfo_to_dict
from market_cortex.config import Settings
from market_cortex.storage import PostgresCatalog, ArtifactStore
from market_cortex.experiments import ExperimentService, IMPLEMENTATION_HASH
from market_cortex.experiment_tools import replay_dossier

DSN = os.environ.get('MARKET_CORTEX_PHASE12_PILOT_DSN')
DATA = os.environ.get('MARKET_CORTEX_PHASE12_PILOT_DATA_ROOT')
SAFE = bool(DSN and DATA and conninfo_to_dict(DSN).get('dbname', '').endswith('_test'))
pytestmark = pytest.mark.skipif(not SAFE, reason='dedicated Phase 12 stored-data pilot required')


def services():
    root = Path(__file__).resolve().parents[1]
    report = json.loads((root/'docs/quant/PHASE_12_PILOT_RESULTS.json').read_text(encoding='utf-8'))
    c = PostgresCatalog(DSN, ArtifactStore(Path(DATA)))
    s = ExperimentService(c, Settings(DSN, Path(DATA), 'Asia/Kolkata', 'INR', False, True, 'PILOT_TEST'))
    return s, report


@pytest.mark.parametrize('index', range(7))
def test_real_dataset_models_and_replay_remain_reproducible(index):
    s, report = services(); r = report['experiments'][index]; k = UUID(r['experiment_id'])
    assert report['implementation_hash'] == IMPLEMENTATION_HASH
    result = s.store.result(k)['result']
    assert result['result_hash'] == r['result_hash'] and s.replay(k)['status'] == 'MATCH'
    assert result['manifest']['holdout_status'] == 'PREVIOUSLY_EXAMINED'
    assert result['result']['reports']['canonical_quant_evidence']
    dataset = s.store.quant.get(UUID(result['dataset_ref']['artifact_id']), 'experiment_dataset')['result']
    assert dataset['source_classification'] == 'LIVE_SOURCE' and dataset['provider'] == 'binance'
    if index == 6:
        assert r['status'] == 'INCONCLUSIVE' and r['metrics']['N'] == 0
        assert dataset['missingness']['funding'] > 0
    else:
        assert r['metrics']['N'] == 1800 and r['conclusion'] == 'HYPOTHESIS_FALSIFIED'


def test_negative_history_owner_separation_and_edge_never_promoted():
    s, report = services()
    assert report['canonical_counts_before'] == report['canonical_counts_after']
    assert report['prior_negative']['oos_return'] == -.07817165407921722 and report['prior_negative']['N'] == 82
    assert report['owner_history'] == {'status': 'INSUFFICIENT_HISTORY', 'genuine_owner_N': 0}
    assert report['unseen_validation'] == 'NOT_ESTABLISHED'
    assert any(x['effect'].endswith('EDGE_STATUS_UNCHANGED') for x in s.edge_links())
    assert replay_dossier(s, UUID(report['dossier_ref']['artifact_id']))['status'] == 'MATCH'


def test_real_encrypted_restore_evidence_is_complete():
    _, report = services(); root = Path(__file__).resolve().parents[1]
    restore = json.loads((root/'docs/quant/PHASE_12_RESTORE_RESULTS.json').read_text(encoding='utf-8'))
    assert restore['status'] == 'VERIFIED' and len(restore['experiment_checks']) == 7
    assert restore['recomputed_experiment_replay']['status'] == 'MATCH'
    assert restore['dossier_replay']['status'] == 'MATCH' and restore['market_head'] == report['market_head']
