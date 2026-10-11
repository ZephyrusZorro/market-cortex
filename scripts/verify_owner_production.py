"""Read-only owner acceptance inventory after the single approved research save.

Requires the private owner connection in the invoking terminal. No migrations,
ingestion, job enqueue, record changes, backups, restores or application launch.

Run from the repository root: python -m scripts.verify_owner_production
Direct file invocation puts scripts/market_cortex.py ahead of the real package.
"""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re
from uuid import uuid4

if __name__ == '__main__' and not __package__:
    raise SystemExit('Run from the repository root: python -m scripts.verify_owner_production')

from market_cortex.database import connect
from market_cortex.operations import load_profile, preflight
from market_cortex.owner_migration import digest, file_hash
from market_cortex.owner_onboarding import migration_inventory, require, schema_fingerprint


ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / 'runtime/owner-onboarding-20473f58dfda42659c60bcf6668b12bb'


def main():
    result = {'status': 'FAILED_READ_ONLY_OWNER_ACCEPTANCE', 'owner_database_writes': False,
              'observed_at': datetime.now(timezone.utc).isoformat()}
    try:
        baseline = json.loads((RUN / 'verification-7c13d8d2c4534941a72e39e258d6249d.json').read_text(encoding='utf-8-sig'))
        source = json.loads((RUN / 'report.json').read_text(encoding='utf-8-sig'))
        saved = json.loads((ROOT / 'runtime/owner-authorized-cortex-run.json').read_text(encoding='utf-8'))
        require(baseline['status'] == 'VALIDATED_OWNER_MARKET_DATA_READ_ONLY_RECOVERY', 'BASELINE_NOT_VALIDATED')
        require(file_hash(RUN / 'report.json') == baseline['original_report_sha256'], 'ORIGINAL_REPORT_CHANGED')
        _, settings = load_profile(ROOT / 'config/operations-owner.example.json')
        require(settings.environment == 'OWNER_MAIN' and settings.data_root.resolve() == Path('C:/MarketCortexData').resolve(), 'WRONG_OWNER_PROFILE')
        current = preflight(settings, integrity=True)
        result['preflight'] = current
        require(current['status'] == 'VALIDATED', 'OWNER_PREFLIGHT_FAILED')
        require(current['checks']['database_identity'] == baseline['preflight']['checks']['database_identity'], 'OWNER_IDENTITY_CHANGED')
        expected = dict(baseline['preflight']['checks']['table_counts'])
        expected['cortex_research_runs'] += 1
        require(current['checks']['table_counts'] == expected, 'UNEXPECTED_OWNER_RECORD_COUNTS')
        require(current['checks']['storage'] == baseline['preflight']['checks']['storage'], 'OWNER_STORAGE_CHANGED')
        with connect(settings.database_url) as connection:
            connection.execute('SET TRANSACTION READ ONLY')
            history = migration_inventory(connection)
            require(history['count'] == 13 and history['ledger'] == baseline['migration_history']['ledger']
                    and history['utc_hash'] == baseline['migration_history']['utc_hash'], 'MIGRATION_HISTORY_CHANGED')
            schema = schema_fingerprint(connection)
            require(schema == baseline['schema_hash'], 'OWNER_SCHEMA_CHANGED')
            head = connection.execute('SELECT manifest_id FROM dataset_head').fetchone()[0]
            require(str(head) == source['pinned_manifest'], 'OWNER_HEAD_CHANGED')
            row = connection.execute('SELECT payload FROM cortex_research_runs WHERE run_id=%s', (saved['run_id'],)).fetchone()
            require(row is not None and digest(row[0]) == digest(saved), 'AUTHORIZED_RESEARCH_CHANGED')
        require(file_hash(Path(source['retained_backup'])) == source['backup_sha256'], 'RETAINED_BACKUP_CHANGED')
        result.update(status='VALIDATED_READ_ONLY_OWNER_ACCEPTANCE_INVENTORY', migration_history=history,
                      schema_hash=schema, manifest_id=str(head), run_id=saved['run_id'],
                      research_payload_hash=digest(saved), evidence_hash=saved['evidence_hash'],
                      only_record_count_change={'cortex_research_runs': 1}, retained_backup_hash_verified=True)
    except Exception as error:
        candidate = str(error) if isinstance(error, ValueError) else ''
        result['error_code'] = candidate if re.fullmatch('[A-Z0-9_]{1,100}', candidate) else type(error).__name__
    path = ROOT / 'runtime' / ('owner-production-verification-' + uuid4().hex + '.json')
    path.write_text(json.dumps(result, indent=2, default=str) + '\n', encoding='utf-8')
    print(json.dumps({'status': result['status'], 'report': str(path), 'owner_database_writes': False,
                      'error_code': result.get('error_code')}))
    return 0 if result['status'] == 'VALIDATED_READ_ONLY_OWNER_ACCEPTANCE_INVENTORY' else 1


if __name__ == '__main__':
    argparse.ArgumentParser(description=__doc__).parse_args()
    raise SystemExit(main())
