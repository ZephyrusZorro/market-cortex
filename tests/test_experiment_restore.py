"""Repeatable restore of new JSON model/result and Edge Library references."""
from pathlib import Path
import tempfile
from uuid import UUID
import pytest
from psycopg import sql
from psycopg.conninfo import make_conninfo, conninfo_to_dict
from market_cortex.backup import backup, restore
from market_cortex.database import connect
from market_cortex.storage import PostgresCatalog, ArtifactStore
from market_cortex.experiments import ExperimentService
from market_cortex.experiment_contracts import ExperimentEdgeInput, PromotionDecision
from market_cortex.learning import LearningService
from market_cortex.learning_contracts import EdgeDraft
from test_backup_restore_integration import TARGET, _safe_pair
from test_experiment_catalog import catalog, registered
from test_phase9_catalog import settings


@pytest.mark.skipif(not _safe_pair(), reason='two distinct disposable *_test catalogs required')
def test_experiment_json_models_governance_and_edge_survive_restore(catalog):
    s, r = registered(catalog, model='mean'); k = UUID(r['experiment_id']); result = s.run(k)['result']
    edge = LearningService(catalog, 'PILOT_TEST').edge(EdgeDraft(title='Synthetic restore research edge',
        hypothesis='A synthetic hypothesis for checking immutable experimental links only.', detector_id='momentum',
        detector_version='1.0.0', registration='RETROSPECTIVE_EVALUATION', classification='SYNTHETIC_TEST'))
    s.attach_edge(ExperimentEdgeInput(experiment_id=k, edge_id=UUID(edge['edge_id']), stance='COUNTER', reason='Synthetic evidence does not support a profitable edge.'))
    s.store.govern(PromotionDecision(experiment_id=k, decision='EXPERIMENTAL', reason='Retain the synthetic experiment as research only.'), 'PILOT_TEST')
    schema = conninfo_to_dict(catalog.dsn)['options'].removeprefix('-csearch_path=')
    target_dsn = make_conninfo(TARGET, options='-csearch_path='+schema)
    with connect(TARGET) as c:
        assert c.execute("SELECT count(*) FROM pg_tables WHERE schemaname NOT IN ('pg_catalog','information_schema')").fetchone()[0] == 0
    try:
        with tempfile.TemporaryDirectory(prefix='market-cortex-experiment-restore-') as work:
            root = Path(work); source = root/'archive.mcbackup'; target_root = root/'restored'
            backup(settings(catalog), source, 'synthetic-restore-drill-only')
            restore(source, target_root, target_dsn, catalog.dsn, 'synthetic-restore-drill-only')
            restored = PostgresCatalog(target_dsn, ArtifactStore(target_root)); target = ExperimentService(restored, settings(restored))
            assert restored.head() == catalog.head()
            assert target.store.result(k)['result']['result_hash'] == result['result_hash']
            assert target.replay(k)['status'] == 'MATCH'
            assert target.edge_links(UUID(edge['edge_id'])) and target.store.governance(k)
            for ref in result['model_refs']: assert target.store.quant.get(UUID(ref['artifact_id']), 'experiment_model')
    finally:
        with connect(TARGET) as c: c.execute(sql.SQL('DROP SCHEMA IF EXISTS {} CASCADE').format(sql.Identifier(schema)))
