"""Hermetic cutover guards: no databases, provider calls or application startup."""
from copy import deepcopy
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock
import json
import pytest
from psycopg.conninfo import conninfo_to_dict
from market_cortex.config import Settings
from market_cortex.providers import ProviderFailure
from scripts import verify_owner_cutover_preflight as guard

@pytest.mark.parametrize('failure', [None,'rows','replay','during','identity','preflight','missing'])
def test_private_guard_fails_closed_and_enforces_readonly(monkeypatch, failure):
    counts={f'table_{i}':0 for i in range(48)}
    counts.update(observations=1825,dataset_files=65,cortex_research_runs=1)
    inventory={'counts':counts,'ledger':{str(i):'hash' for i in range(13)},'row_hashes':{'research':'original'}}
    baseline={'source_inventory':deepcopy(inventory),'research_replay':{'run_id':'f329f8c9-1274-4be5-8f8d-0e695cdd7e7c'}}
    checked={'status':'VALIDATED','checks':{'database_identity':{'database':'market_cortex','server_port':5432,'transaction_read_only':'on'}}}
    settings=Settings(None if failure=='missing' else 'dbname=not-connected',Path('C:/MarketCortexData'),'Asia/Kolkata','INR',False,True,'OWNER_MAIN')
    if failure=='rows':inventory['row_hashes']['research']='changed'
    if failure=='identity':checked['checks']['database_identity']['database']='pilot'
    if failure=='preflight':checked['status']='FAILED'
    def check(s,**kw):
        assert 'default_transaction_read_only=on' in conninfo_to_dict(s.database_url)['options']
        assert kw=={'integrity':True}
        return checked
    preflight=Mock(side_effect=check); monkeypatch.setattr(guard,'preflight',preflight)
    second=deepcopy(inventory)
    if failure=='during':second['row_hashes']['research']='changed'
    read=Mock(side_effect=[inventory,second]);monkeypatch.setattr(guard,'read_inventory',read)
    monkeypatch.setattr(guard,'catalog_for',lambda s:None)
    service=Mock(); service.replay.return_value={'evidence_reproducible':failure!='replay','checks':[{'matched':True}]*6}
    monkeypatch.setattr(guard,'CortexService',lambda *a:service)
    if failure:
        with pytest.raises(ProviderFailure):guard.validate_owner(settings,baseline)
    else:
        result=guard.validate_owner(settings,baseline)
        assert result['all_owner_row_fingerprints_match_backup'] and read.call_count==2
    if failure in {'missing','rows','identity','preflight'}:service.replay.assert_not_called()
    if failure=='missing':preflight.assert_not_called()

@pytest.mark.parametrize('changed', [False,True])
def test_application_copy_must_match_original_and_extracted_files(tmp_path, monkeypatch, changed):
    original=tmp_path/'app'; restored=tmp_path/'recovery';original.mkdir();restored.mkdir()
    (original/'app.py').write_text('original');(restored/'app.py').write_text('original')
    bundle=tmp_path/'app.zip';bundle.write_bytes(b'test-fixture')
    snapshot={'status':'VERIFIED_APPLICATION_COPY_AND_ISOLATED_EXTRACTION','original_root':str(original),'isolated_restore':str(restored),'bundle':str(bundle),'bundle_sha256':guard.file_hash(bundle),'files':{'app.py':guard.file_hash(original/'app.py')}}
    p=tmp_path/'receipt.json';p.write_text(json.dumps(snapshot));monkeypatch.setattr(guard,'ROOT',original)
    if changed:
        (original/'app.py').write_text('changed')
        with pytest.raises(ProviderFailure):guard.validate_snapshot(p)
    else:assert guard.validate_snapshot(p)['verified_files']==1
