"""Synthetic validation in an isolated schema; zero owner behavior is fabricated."""
from datetime import timedelta
from uuid import UUID,uuid4
import pytest
from fastapi.testclient import TestClient
from market_cortex.api import create_app
from market_cortex.database import connect
from market_cortex.learning_contracts import JournalDraft
from market_cortex.learning_store import LearningStore
from market_cortex.personal_contracts import (ProfileQuery,PreferenceInput,MemoryAction,ProposalAction,FeedbackInput,
    PersonalQuestion,PersonalizedMissionInput,AttestationInput)
from market_cortex.personalization import PersonalizationService
from market_cortex.personal_missions import PersonalizedMissionService
from market_cortex.personal_store import now
from market_cortex.mission_contracts import MissionRequest
from test_phase10_catalog import catalog,settings,quick

A='SYNTHETIC_VALIDATION'
Q=ProfileQuery(audience=A)

def service(c): return PersonalizationService(c,settings(c))
def journal(c,category='insufficient_history'):
    return LearningStore(c.dsn,'PILOT_TEST').create_journal(JournalDraft(category='lesson',title='Synthetic validation research lesson',notes='never owner data',
        failure_category=category,manifest_id=c.head(),as_of=now(),classification='SYNTHETIC_TEST'),{})

def test_zero_owner_profile_even_after_synthetic_journal_and_missions(catalog):
    journal(catalog); p=service(catalog).refresh(ProfileQuery())
    assert p.observed_behavior['genuine_owner_record_N']==0 and not p.patterns and not p.memories

def test_refresh_provenance_inspector_dedup_and_snapshot_hash(catalog):
    s=service(catalog)
    for _ in range(3): journal(catalog)
    p=s.refresh(Q); failure=next(m for m in p.memories if m.key=='failure:insufficient_history')
    assert failure.sample_N>=3 and failure.evidence_ids
    assert s.store.get(failure.memory_id)['kind']=='MEMORY'
    assert s.store.snapshot(p.snapshot_id).content_hash==p.content_hash
    p2=s.refresh(Q); same=next(m for m in p2.memories if m.key==failure.key)
    assert same.memory_id==failure.memory_id and same.version==failure.version

def test_explicit_preferences_corrections_and_historical_versions(catalog):
    s=service(catalog); m=s.preference(PreferenceInput(audience=A,key='default_horizon',value=7)); cutoff=now()
    fixed=s.memory_action(m.memory_id,MemoryAction(expected_version=m.version,action='correct',correction=PreferenceInput(audience=A,key='default_horizon',value=12)))
    assert fixed.version==m.version+1 and fixed.value==12
    assert s.store.memory(s.store.get(m.memory_id,as_of=cutoff)).value==7
    assert len(s.store.history(m.memory_id))==2
    with pytest.raises(ValueError,match='VERSION_CONFLICT'): s.memory_action(m.memory_id,MemoryAction(expected_version=m.version,action='disable'))

def test_proposal_does_not_activate_until_explicit_acceptance_and_can_retire(catalog):
    s=service(catalog); p=s.refresh(Q)
    proposal=next(x for x in p.proposals if x.value=='quant')
    assert proposal.status=='PROPOSED' and not any(m.key=='review_emphasis' and m.source_type=='EXPLICIT' for m in p.memories)
    accepted=s.proposal_action(proposal.proposal_id,ProposalAction(expected_version=proposal.version,action='accept'))
    current=s.profile(Q); assert accepted.status=='ACTIVE'
    assert next(m for m in current.memories if m.key=='review_emphasis').value=='quant'
    s.proposal_action(accepted.proposal_id,ProposalAction(expected_version=accepted.version,action='retire'))
    assert next(m for m in s.profile(Q).memories if m.key=='review_emphasis').status=='DISABLED'

def test_personalized_planner_uses_accepted_preference_without_canonical_changes(catalog):
    s=service(catalog); s.preference(PreferenceInput(audience=A,key='review_emphasis',value='quant'))
    snapshot=s.refresh(Q); head=catalog.head()
    inputs=PersonalizedMissionInput(snapshot_id=snapshot.snapshot_id,request=MissionRequest(goal='Investigate BTC momentum and historical support.',symbol='BTCUSDT'))
    mission_service=PersonalizedMissionService(catalog,settings(catalog),snapshot)
    m=mission_service.create_personalized(inputs)
    assert [step.step_id for step in m.plan.steps][:2]==['availability','quant']
    assert m.frozen_references['personalization']['content_hash']==snapshot.content_hash
    result=mission_service.run(m.mission_id)
    assert result.status=='INCONCLUSIVE' and catalog.head()==head
    assert mission_service.replay_personalized(m.mission_id)['personalization_verified']
    assert mission_service.replay_personalized(m.mission_id)['matched']

def test_disabled_emphasis_cannot_influence_planner_and_explicit_request_is_respected(catalog):
    s=service(catalog); m=s.preference(PreferenceInput(audience=A,key='review_emphasis',value='quant'))
    s.memory_action(m.memory_id,MemoryAction(expected_version=m.version,action='disable'))
    s.preference(PreferenceInput(audience=A,key='default_mode',value='DEEP_RESEARCH'))
    p=s.refresh(Q); planner=PersonalizedMissionService(catalog,settings(catalog),p)
    result=planner.create_personalized(PersonalizedMissionInput(request=quick(),snapshot_id=p.snapshot_id,use_explicit_preferences=True))
    assert result.request.mode=='QUICK_RESEARCH' and result.plan.steps[1].step_id=='features'

def test_future_profile_cannot_influence_historical_mission(catalog):
    s=service(catalog); p=s.refresh(Q); planner=PersonalizedMissionService(catalog,settings(catalog),p)
    with pytest.raises(ValueError,match='FUTURE_PERSONALIZATION'):
        planner.create_personalized(PersonalizedMissionInput(request=quick(as_of=p.as_of-timedelta(seconds=1))))

def test_rejection_and_feedback_are_local_versioned_evidence(catalog):
    s=service(catalog); p=s.refresh(Q); m=next(m for m in p.memories if m.key=='failure:insufficient_history')
    row=s.feedback(FeedbackInput(audience=A,target_kind='MEMORY',target_id=m.memory_id,rating='IRRELEVANT'))
    assert row['rating']=='IRRELEVANT'
    result=s.memory_action(m.memory_id,MemoryAction(expected_version=m.version,action='reject'))
    assert result.status=='REJECTED' and not any(c['key']==m.key for c in s.profile(Q).coaching)

def test_external_model_fact_creation_and_owner_write_in_test_are_blocked(catalog):
    client=TestClient(create_app(settings(catalog),catalog))
    assert client.post('/api/v1/personalization/preferences',json={'key':'default_horizon','value':7}).status_code==409
    assert client.post('/api/v1/personalization/preferences',json={'audience':A,'key':'default_horizon','value':7,'model_fact':'opaque trait'}).status_code==422
    assert client.post('/api/v1/personalization/attestations',json={'audience':A,'source_kind':'news','source_id':str(uuid4()),'source_version':1}).status_code==422
    assert client.get('/api/v1/personalization/tools/execute_shell').status_code==409

def test_typed_api_memory_search_history_export_and_questions(catalog):
    client=TestClient(create_app(settings(catalog),catalog)); params={'audience':A}
    p=client.get('/api/v1/personalization/profile',params=params).json()
    assert p['privacy']=='LOCAL_ONLY'
    listing=client.get('/api/v1/personalization/memories',params={**params,'search':'horizon'}).json()['items']
    assert listing
    history=client.get('/api/v1/personalization/memories/'+listing[0]['memory_id']+'/history').json()['items']
    assert all(x['effective_status']=='SUPERSEDED' for x in history[:-1])
    exported=client.get('/api/v1/personalization/export',params=params).json()
    assert 'never owner data' not in str(exported) and all('facts' not in e for e in exported['source_metadata'])
    answer=client.post('/api/v1/personalization/query',json={'audience':A,'question':'What mistakes do I repeat?'}).json()
    assert answer['privacy']=='LOCAL_ONLY' and answer['owner_sample_N']==0

def test_historical_profile_does_not_learn_future_corrections_or_feedback(catalog):
    s=service(catalog); cutoff=now(); before=s.profile(ProfileQuery(audience=A,as_of=cutoff))
    s.preference(PreferenceInput(audience=A,key='preferred_instrument',value='ETHUSDT'))
    after=s.profile(ProfileQuery(audience=A,as_of=cutoff))
    assert before.model_dump()==after.model_dump()
    with pytest.raises(ValueError,match='HISTORICAL'): s.refresh(ProfileQuery(audience=A,as_of=cutoff))

def test_attestation_requires_canonical_record_and_known_revision(catalog):
    s=service(catalog)
    with pytest.raises(LookupError): s.attest(AttestationInput(audience=A,source_kind='mission',source_id=uuid4(),source_version=1))

def test_source_attestation_follows_only_then_known_mission_checkpoints(catalog):
    s=service(catalog); p=s.refresh(Q); planner=PersonalizedMissionService(catalog,settings(catalog),p)
    m=planner.create_personalized(PersonalizedMissionInput(request=quick(),snapshot_id=p.snapshot_id))
    before=now(); result=planner.run(m.mission_id)
    old=s.profile(ProfileQuery(audience=A,as_of=before)); current=s.profile(Q)
    old_e=next(e for e in old.evidence if e.source_id==m.mission_id)
    new_e=next(e for e in current.evidence if e.source_id==m.mission_id)
    assert old_e.facts['status']=='READY' and new_e.facts['status']==result.status
    assert new_e.source_version>old_e.source_version

def test_historical_snapshot_remains_frozen_after_correction_and_store_detects_tamper(catalog):
    s=service(catalog); p=s.refresh(Q); m=s.preference(PreferenceInput(audience=A,key='preferred_view',value='my-research'))
    frozen=s.refresh(Q)
    s.memory_action(m.memory_id,MemoryAction(expected_version=m.version,action='disable'))
    assert s.store.snapshot(frozen.snapshot_id).content_hash==frozen.content_hash
    with connect(catalog.dsn) as c:
        c.execute("UPDATE personal_record_versions SET payload=payload||'{\"poisoned\":true}'::jsonb WHERE record_id=%s AND version=%s",(m.memory_id,m.version))
    with pytest.raises(ValueError,match='HASH_MISMATCH'): s.store.get(m.memory_id,version=m.version)
