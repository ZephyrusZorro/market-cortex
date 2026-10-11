"""Import and read-only acceptance guards; no owner database is accessed."""
from copy import deepcopy
import json
import os
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

import pytest

from scripts import verify_owner_production as verifier


def test_module_entrypoint_resolves_real_package_without_running_inventory():
    root = Path(__file__).resolve().parents[1]
    env = {key: value for key, value in os.environ.items()
           if not key.upper().startswith('MARKET_CORTEX_')}
    env.pop('PYTHONPATH', None)
    # Help must not read configuration, connect, or create a diagnostic receipt.
    env['MARKET_CORTEX_DATABASE_URL'] = 'must-not-be-used-by-help'
    receipts_before = set((root / 'runtime').glob('owner-production-verification-*.json'))
    help_result = subprocess.run([sys.executable, '-m', 'scripts.verify_owner_production', '--help'],
                                 cwd=root, env=env, capture_output=True, text=True, timeout=20)
    assert help_result.returncode == 0, help_result.stderr
    assert 'Read-only owner acceptance' in help_result.stdout
    direct_result = subprocess.run([sys.executable, 'scripts/verify_owner_production.py'],
                                   cwd=root, env=env, capture_output=True, text=True, timeout=20)
    assert direct_result.returncode != 0
    assert 'python -m scripts.verify_owner_production' in direct_result.stderr
    assert 'Traceback' not in direct_result.stderr
    assert set((root / 'runtime').glob('owner-production-verification-*.json')) == receipts_before
    probe = subprocess.run([sys.executable, '-c',
                            'import market_cortex; import scripts.verify_owner_production; '
                            'print(market_cortex.__file__); assert hasattr(market_cortex, "__path__")'],
                           cwd=root, env=env, capture_output=True, text=True, timeout=20)
    assert probe.returncode == 0, probe.stderr
    assert Path(probe.stdout.strip()).resolve() == root / 'src/market_cortex/__init__.py'


@pytest.mark.parametrize('extra_record', [False, True])
def test_inventory_requires_read_only_transaction_and_exact_approved_count(tmp_path, monkeypatch, capsys, extra_record):
    """Exercise the complete verifier with a connection that refuses writes."""
    run = tmp_path / 'runtime/onboarding'
    run.mkdir(parents=True)
    monkeypatch.setattr(verifier, 'ROOT', tmp_path)
    monkeypatch.setattr(verifier, 'RUN', run)
    backup = tmp_path / 'retained-backup'
    backup.write_bytes(b'test-only-retained-evidence')
    source = {'pinned_manifest': 'owner-head', 'retained_backup': str(backup),
              'backup_sha256': verifier.file_hash(backup)}
    source_path = run / 'report.json'
    source_path.write_text(json.dumps(source), encoding='utf-8')
    history = {'count': 13, 'ledger': {'unchanged': 'checksum'}, 'utc_hash': 'original-utc-hash'}
    before = {'status': 'VALIDATED', 'checks': {
        'database_identity': {'database': 'market_cortex', 'server_port': 5432},
        'table_counts': {'cortex_research_runs': 0, 'observations': 1825},
        'storage': {'referenced': 65, 'missing': [], 'corrupt': []}}}
    baseline = {'status': 'VALIDATED_OWNER_MARKET_DATA_READ_ONLY_RECOVERY',
                'original_report_sha256': verifier.file_hash(source_path),
                'preflight': before, 'migration_history': history, 'schema_hash': 'unchanged-schema'}
    (run / 'verification-7c13d8d2c4534941a72e39e258d6249d.json').write_text(json.dumps(baseline), encoding='utf-8')
    saved = {'run_id': 'approved-run', 'evidence_hash': 'approved-evidence', 'payload': 'real-authorized-research'}
    (tmp_path / 'runtime/owner-authorized-cortex-run.json').write_text(json.dumps(saved), encoding='utf-8')
    current = deepcopy(before)
    current['checks']['table_counts']['cortex_research_runs'] = 2 if extra_record else 1
    settings = SimpleNamespace(environment='OWNER_MAIN', data_root=Path('C:/MarketCortexData'), database_url='test-double')
    monkeypatch.setattr(verifier, 'load_profile', lambda _: (None, settings))
    def preflight(selected, *, integrity):
        assert selected is settings and integrity is True
        return current
    monkeypatch.setattr(verifier, 'preflight', preflight)
    statements = []
    class ReadOnlyConnection:
        read_only = False
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def execute(self, query, params=None):
            statements.append(query)
            if query == 'SET TRANSACTION READ ONLY':
                self.read_only = True
                return None
            assert self.read_only, 'Owner queries must follow READ ONLY'
            if query == 'SELECT manifest_id FROM dataset_head':
                return SimpleNamespace(fetchone=lambda: ('owner-head',))
            if query == 'SELECT payload FROM cortex_research_runs WHERE run_id=%s':
                assert params == ('approved-run',)
                return SimpleNamespace(fetchone=lambda: (saved,))
            raise AssertionError('Unexpected SQL or mutation attempt')
    connection = ReadOnlyConnection()
    monkeypatch.setattr(verifier, 'connect', lambda _: connection)
    def inventory(c):
        assert c.read_only
        return history
    def schema(c):
        assert c.read_only
        return 'unchanged-schema'
    monkeypatch.setattr(verifier, 'migration_inventory', inventory)
    monkeypatch.setattr(verifier, 'schema_fingerprint', schema)
    assert verifier.main() == (1 if extra_record else 0)
    output = json.loads(capsys.readouterr().out)
    receipt = json.loads(Path(output['report']).read_text(encoding='utf-8'))
    assert receipt['owner_database_writes'] is False
    if extra_record:
        assert receipt['error_code'] == 'UNEXPECTED_OWNER_RECORD_COUNTS'
        assert statements == []
    else:
        assert receipt['status'] == 'VALIDATED_READ_ONLY_OWNER_ACCEPTANCE_INVENTORY'
        assert statements == ['SET TRANSACTION READ ONLY', 'SELECT manifest_id FROM dataset_head',
                              'SELECT payload FROM cortex_research_runs WHERE run_id=%s']
    assert verifier.file_hash(source_path) == baseline['original_report_sha256']
    assert verifier.file_hash(backup) == source['backup_sha256']
