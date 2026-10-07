"""Actual stored evidence validation; no synthetic records are adopted as owner history."""
import json,os,sys,time
from pathlib import Path
from uuid import UUID
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from psycopg.conninfo import conninfo_to_dict
from market_cortex.config import Settings
from market_cortex.database import connect,migrate
from market_cortex.storage import PostgresCatalog,ArtifactStore
from market_cortex.personalization import PersonalizationService
from market_cortex.personal_missions import PersonalizedMissionService
from market_cortex.personal_contracts import ProfileQuery,PersonalQuestion,PersonalizedMissionInput
from market_cortex.mission_contracts import MissionRequest


def main():
    root=Path(__file__).resolve().parents[1]
    dsn=os.environ['MARKET_CORTEX_PHASE11_PILOT_DSN']; data=Path(os.environ['MARKET_CORTEX_PHASE11_PILOT_DATA_ROOT'])
    if not conninfo_to_dict(dsn).get('dbname','').endswith('_test'): raise ValueError('DEDICATED_TEST_CATALOG_REQUIRED')
    migrate(dsn,root); catalog=PostgresCatalog(dsn,ArtifactStore(data))
    settings=Settings(dsn,data,'Asia/Kolkata','INR',False,True,'PILOT_TEST')
    service=PersonalizationService(catalog,settings); started=time.perf_counter()
    tables=('observations','context_facts','opportunity_candidates','research_thesis_versions','portfolio_versions','prediction_records','journal_revisions','quant_artifacts')
    def counts():
        with connect(dsn) as c: return {t:c.execute('SELECT count(*) FROM '+t).fetchone()[0] for t in tables}
    before=counts(); head=catalog.head(); profile=service.refresh(ProfileQuery())
    assert profile.observed_behavior['genuine_owner_record_N']==0 and profile.observed_behavior['history_state']=='INSUFFICIENT_HISTORY'
    assert not profile.patterns and not profile.proposals
    quant=next(q for q in profile.strategy_evidence if q['strategy']=='momentum')
    assert quant['oos_return']==-.07817165407921722 and quant['N']==82 and quant['owner_usage_N']==0
    assert service.verify_snapshot(profile)['matched']
    answer=service.answer(PersonalQuestion(question='What should I review before analyzing BTC?',symbol='BTCUSDT'))
    assert answer['items'] and all(i['subject']=='STRATEGY_EVIDENCE' for i in answer['items'])
    planner=PersonalizedMissionService(catalog,settings,profile)
    mission=planner.create_personalized(PersonalizedMissionInput(snapshot_id=profile.snapshot_id,request=MissionRequest(goal='Investigate whether BTCUSDT momentum is currently attractive and whether historical evidence supports it.',symbol='BTCUSDT')))
    final=planner.run(mission.mission_id); replay=planner.replay_personalized(mission.mission_id)
    assert replay['matched'] and replay['personalization_verified'] and final.status=='INCONCLUSIVE'
    assert counts()==before and catalog.head()==head
    configured=Settings.load()
    result={'validated_at':__import__('datetime').datetime.now(__import__('datetime').timezone.utc).isoformat(),
        'owner_connection_configured':bool(configured.database_url),'owner_history_status':'UNAVAILABLE_OWNER_CONNECTION; ZERO_ELIGIBLE_OWNER_RECORDS_IN_PILOT',
        'genuine_owner_sample_N':0,'history_state':profile.observed_behavior['history_state'],'implementation_hash':profile.implementation_hash,
        'snapshot_id':str(profile.snapshot_id),'snapshot_hash':profile.content_hash,'profile_source_verification':service.verify_snapshot(profile),
        'actual_patterns':[],'actual_owner_strengths_or_mistakes':[],'strategy_evidence':profile.strategy_evidence,
        'coaching':profile.coaching,'personalized_mission_id':str(final.mission_id),'mission_status':final.status,
        'personalization_activity':[a for a in final.activity if a['action']=='PERSONALIZED_PLAN_REVIEW'],
        'mission_replay':replay,'canonical_counts_before':before,'canonical_counts_after':counts(),
        'paid_api_cost_inr':0,'model_provider':'deterministic','elapsed_s':round(time.perf_counter()-started,2),
        'owner_main_database_and_data':'UNTOUCHED','synthetic_habits_adopted_as_owner':False}
    out=root/'docs'/'personalization'; out.mkdir(parents=True,exist_ok=True)
    (out/'PHASE_11_PILOT_RESULTS.json').write_text(json.dumps(result,indent=2,ensure_ascii=False),encoding='utf-8')
    print('Pilot verified:',final.status,'owner N=0; insufficient history; negative OOS preserved; canonical counts unchanged.')
if __name__=='__main__': main()
