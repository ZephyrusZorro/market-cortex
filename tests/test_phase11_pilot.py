import json,os
from pathlib import Path
from uuid import UUID
import pytest
from psycopg.conninfo import conninfo_to_dict
from market_cortex.config import Settings
from market_cortex.storage import PostgresCatalog,ArtifactStore
from market_cortex.personalization import PersonalizationService
from market_cortex.personal_missions import PersonalizedMissionService
from market_cortex.personal_contracts import ProfileQuery

DSN=os.environ.get('MARKET_CORTEX_PHASE11_PILOT_DSN')
DATA=os.environ.get('MARKET_CORTEX_PHASE11_PILOT_DATA_ROOT')
pytestmark=pytest.mark.skipif(not(DSN and DATA and conninfo_to_dict(DSN).get('dbname','').endswith('_test')),reason='dedicated stored-data pilot catalog required')

def services():
    c=PostgresCatalog(DSN,ArtifactStore(Path(DATA)))
    s=PersonalizationService(c,Settings(DSN,Path(DATA),'Asia/Kolkata','INR',False,True,'PILOT_TEST'))
    report=json.loads((Path(__file__).resolve().parents[1]/'docs/personalization/PHASE_11_PILOT_RESULTS.json').read_text())
    return c,s,report

def test_actual_pilot_is_not_owner_history_and_negative_quant_remains_visible():
    c,s,r=services(); p=s.profile(ProfileQuery())
    assert p.observed_behavior['genuine_owner_record_N']==0 and not p.patterns
    q=next(x for x in p.strategy_evidence if x['strategy']=='momentum')
    assert q['oos_return']==-.07817165407921722 and q['N']==82 and q['owner_usage_N']==0

def test_actual_frozen_profile_sources_reproduce_and_no_synthetic_habits_adopted():
    c,s,r=services(); p=s.store.snapshot(UUID(r['snapshot_id']))
    assert s.verify_snapshot(p)['matched'] and p.implementation_hash==r['implementation_hash']
    assert r['canonical_counts_before']==r['canonical_counts_after'] and r['synthetic_habits_adopted_as_owner'] is False

def test_actual_personalized_mission_replays_frozen_personal_and_market_evidence():
    c,s,r=services(); p=s.store.snapshot(UUID(r['snapshot_id']))
    replay=PersonalizedMissionService(c,s.settings,p).replay_personalized(UUID(r['personalized_mission_id']))
    assert replay['matched'] and replay['personalization_verified'] and replay['personal_implementation_available']
