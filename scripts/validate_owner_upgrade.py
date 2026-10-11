"""Rehearse the owner's pending upgrade using synthetic, disposable test data.

Never connects to the owner catalog. Requires MARKET_CORTEX_TEST_DATABASE_URL
for a loopback *_test database and PostgreSQL client tools on PATH.
"""
import json
import os
from pathlib import Path
import secrets
import shutil
import sys
import tempfile
from datetime import datetime, timezone
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
sys.path.insert(0, str(ROOT / 'tests'))
from psycopg import sql
from psycopg.conninfo import conninfo_to_dict, make_conninfo
from market_cortex.backup import backup, restore
from market_cortex.config import Settings
from market_cortex.database import connect, migrate
from market_cortex.operations import preflight
from market_cortex.storage import ArtifactStore, PostgresCatalog
from test_foundation import identity, calendar, bar


def main():
    base = os.environ.get('MARKET_CORTEX_TEST_DATABASE_URL', '')
    parts = conninfo_to_dict(base)
    if (parts.get('host') not in {'127.0.0.1', 'localhost', '::1'}
            or not parts.get('dbname', '').endswith('_test')
            or parts.get('hostaddr') not in {None, '127.0.0.1', '::1'}
            or parts.get('service') or parts.get('options')):
        raise ValueError('ISOLATED_TEST_CONNECTION_REQUIRED')
    names = ['onboarding_' + uuid4().hex + '_test' for _ in range(2)]
    created = []
    result = None
    try:
        for name in names:
            with connect(base) as c:
                c.autocommit = True
                c.execute(sql.SQL("CREATE DATABASE {} TEMPLATE template0 ENCODING 'UTF8'").format(sql.Identifier(name)))
            created.append(name)
        source_dsn, target_dsn = [make_conninfo(base, dbname=name) for name in names]
        with tempfile.TemporaryDirectory(prefix='market-cortex-upgrade-') as directory:
            work = Path(directory)
            old_project = work / 'old-project'
            migrations = old_project / 'infra' / 'migrations'
            migrations.mkdir(parents=True)
            for name in ('0001_market_foundation.sql', '0002_job_delivery.sql'):
                shutil.copyfile(ROOT / 'infra' / 'migrations' / name, migrations / name)
            assert len(migrate(source_dsn, old_project)) == 2
            data = work / 'source'
            data.mkdir()
            catalog = PostgresCatalog(source_dsn, ArtifactStore(data))
            instrument, mapping = identity()
            cal = calendar()
            catalog.register_identity([cal.venue], [instrument], [mapping])
            item = bar(instrument, mapping, cal)
            inserted = catalog.ingest([item], cal, source_batch_id=item.envelope.source_batch_id,
                                      provider_id=mapping.provider_id, raw_hash='a' * 64,
                                      fetched_at=item.envelope.ingested_at)
            assert inserted.stored == 1
            settings = Settings(source_dsn, data, 'Asia/Kolkata', 'INR', False, True, 'PILOT_TEST')
            before = preflight(settings, integrity=True)
            assert before['status'] == 'FAILED' and len(before['checks']['pending_migrations']) == 11
            assert before['checks']['storage']['referenced'] == 1 and not before['checks']['storage']['missing']
            phrase = secrets.token_urlsafe(40)
            encrypted = work / 'before-upgrade.mcbackup'
            saved = backup(settings, encrypted, phrase)
            recovered = restore(encrypted, work / 'restored', target_dsn, source_dsn, phrase)
            assert recovered['head_manifest_id'] == saved['head_manifest_id']
            restored = PostgresCatalog(target_dsn, ArtifactStore(work / 'restored'))
            request = dict(instrument_id=instrument.instrument_id, start=item.start_at, end=item.end_at,
                           as_of=datetime.now(timezone.utc), manifest_id=catalog.head())
            original = [b.model_dump(mode='json') for b in catalog.bars(**request)[1]]
            assert len(original) == 1
            assert original == [b.model_dump(mode='json') for b in restored.bars(**request)[1]]
            applied = migrate(target_dsn, ROOT)
            assert applied == before['checks']['pending_migrations']
            upgraded = Settings(target_dsn, work / 'restored', 'Asia/Kolkata', 'INR', False, True, 'PILOT_TEST')
            after = preflight(upgraded, integrity=True)
            assert after['status'] == 'VALIDATED'
            assert original == [b.model_dump(mode='json') for b in restored.bars(**request)[1]]
            assert restored.head() == catalog.head()
            for name, count in before['checks']['table_counts'].items():
                expected = count + 11 if name == 'schema_migrations' else count
                assert after['checks']['table_counts'][name] == expected
            added = set(after['checks']['table_counts']) - set(before['checks']['table_counts'])
            assert len(added) == 34 and all(after['checks']['table_counts'][name] == 0 for name in added)
            assert migrate(target_dsn, ROOT) == []
            assert len(preflight(settings)['checks']['pending_migrations']) == 11
            result = {'status': 'VALIDATED_SYNTHETIC_REHEARSAL', 'validated_at': datetime.now(timezone.utc).isoformat(),
                      'owner_main': 'NEVER_CONNECTED_OR_MODIFIED', 'pending_migrations_applied_to_restored_test_only': applied,
                      'before': before, 'after': after, 'new_tables': sorted(added),
                      'existing_rows_preserved': True, 'bar_payload_exact_match': True,
                      'manifest_unchanged': True, 'second_migration_run': 'NO_CHANGES',
                      'source_kept_at_original_schema': True,
                      'encrypted_bytes': encrypted.stat().st_size, 'owner_backup': 'NOT_CREATED'}
    finally:
        for name in reversed(created):
            with connect(base) as c:
                c.autocommit = True
                c.execute(sql.SQL('DROP DATABASE {}').format(sql.Identifier(name)))
    # Publish evidence only after owned databases and temporary files are cleaned.
    result['disposable_databases_and_files'] = 'CLEANED'
    (ROOT / 'docs/operations/DEPLOYMENT_UPGRADE_REHEARSAL_RESULTS.json').write_text(
        json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps({'status': result['status'], 'migrations': len(applied), 'new_empty_tables': len(added)}))


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        print(json.dumps({'status': 'FAILED', 'error_type': type(error).__name__}))
        raise SystemExit(1)
