"""Encrypted recovery drill into a newly-created disposable local *_test DB."""
import json
import os
import secrets
import sys
import tempfile
from pathlib import Path
from uuid import UUID, uuid4
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'src'))
from psycopg import sql
from psycopg.conninfo import conninfo_to_dict, make_conninfo
from market_cortex.backup import backup, restore
from market_cortex.config import Settings
from market_cortex.database import connect
from market_cortex.storage import PostgresCatalog, ArtifactStore
from market_cortex.experiments import ExperimentService
from market_cortex.experiment_tools import replay_dossier
from market_cortex.quant_store import digest


def main():
    root = Path(__file__).resolve().parents[1]
    dsn = os.environ['MARKET_CORTEX_PHASE12_PILOT_DSN']; data = Path(os.environ['MARKET_CORTEX_PHASE12_PILOT_DATA_ROOT'])
    info = conninfo_to_dict(dsn)
    if not info.get('dbname', '').endswith('_test') or info.get('host') not in ('127.0.0.1', 'localhost'):
        raise ValueError('DEDICATED_LOCAL_TEST_CATALOG_REQUIRED')
    report = json.loads((root/'docs/quant/PHASE_12_PILOT_RESULTS.json').read_text(encoding='utf-8'))
    dbname = 'phase12_restore_'+uuid4().hex+'_test'; target_dsn = make_conninfo(dsn, dbname=dbname)
    # Only this fresh, exact, random database is later dropped; no existing DB reset.
    with connect(dsn) as c:
        c.autocommit = True; c.execute(sql.SQL("CREATE DATABASE {} TEMPLATE template0 ENCODING 'UTF8'").format(sql.Identifier(dbname)))
    try:
        with tempfile.TemporaryDirectory(prefix='market-cortex-phase12-restore-') as work:
            work = Path(work); restored = work/'restored'; encrypted = work/'phase12.mcbackup'
            settings = Settings(dsn, data, 'Asia/Kolkata', 'INR', False, True, 'PILOT_TEST')
            passphrase = secrets.token_urlsafe(40)
            created = backup(settings, encrypted, passphrase)
            recovered = restore(encrypted, restored, target_dsn, dsn, passphrase)
            target = PostgresCatalog(target_dsn, ArtifactStore(restored)); s = ExperimentService(target,
                Settings(target_dsn, restored, 'Asia/Kolkata', 'INR', False, True, 'PILOT_TEST'))
            assert str(target.head()) == report['market_head']
            checks = []
            for r in report['experiments']:
                k = UUID(r['experiment_id']); saved = s.store.result(k)['result']
                assert saved['result_hash'] == r['result_hash']
                s.store.quant.get(UUID(saved['dataset_ref']['artifact_id']), 'experiment_dataset')
                for ref in saved['model_refs']: s.store.quant.get(UUID(ref['artifact_id']), 'experiment_model')
                assert s.store.get_hypothesis(UUID(r['hypothesis_id']))
                checks.append({'experiment_id': str(k), 'result_hash': saved['result_hash'], 'dataset': 'CHECKSUM_VERIFIED',
                    'models': len(saved['model_refs']), 'definition': 'CHECKSUM_VERIFIED'})
            replay = s.replay(UUID(report['experiments'][2]['experiment_id'])); assert replay['status'] == 'MATCH'
            dossier = replay_dossier(s, UUID(report['dossier_ref']['artifact_id'])); assert dossier['status'] == 'MATCH'
            links = s.edge_links(); assert not report['edge_link'] or any(x['experiment_id'] == report['edge_link']['experiment_id'] for x in links)
            with connect(target_dsn) as c:
                counts = {t: c.execute('SELECT count(*) FROM '+t).fetchone()[0] for t in
                    ('research_hypotheses','experiment_definitions','experiment_events','experiment_exposures','experiment_edge_links','experiment_governance','experiment_proposals')}
                proposals = c.execute('SELECT experiment_id,payload,content_hash FROM experiment_proposals').fetchall()
            for child, payload, checksum in proposals:
                assert digest(payload) == checksum and s.store.get(child)
            output = {'status': 'VERIFIED', 'drill': 'REAL_PILOT_ENCRYPTED_BACKUP_TO_NEW_DISPOSABLE_TEST_DATABASE',
                'market_head': str(target.head()), 'parquet_artifact_N': recovered['artifact_count'],
                'encrypted_bytes': encrypted.stat().st_size, 'experiment_checks': checks, 'restored_counts': counts,
                'recomputed_experiment_replay': replay, 'dossier_replay': dossier, 'edge_links': 'CHECKSUM_VERIFIED',
                'proposals_verified': len(proposals), 'owner_main': 'UNTOUCHED', 'temporary_restore_database_and_files': 'CLEANED_AFTER_DRILL'}
            (root/'docs/quant/PHASE_12_RESTORE_RESULTS.json').write_text(json.dumps(output, indent=2, default=str), encoding='utf-8')
            print('Restored definitions, datasets, models, results, manifests, edge links and dossier; replay MATCH.', flush=True)
    finally:
        with connect(dsn) as c:
            c.autocommit = True; c.execute(sql.SQL('DROP DATABASE {}').format(sql.Identifier(dbname)))


if __name__ == '__main__': main()
