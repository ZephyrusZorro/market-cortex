"""Optional personalized planning over unchanged, replayable Phase 10 orchestration."""
from uuid import UUID
from .missions import MissionService
from .mission_policy import validate_plan
from .personal_contracts import ProfileQuery,AttestationInput
from .personal_engine import usable
from .personalization import PersonalizationService,_code_hash


class PersonalizedMissionService(MissionService):
    def __init__(self,catalog,settings,snapshot):
        super().__init__(catalog,settings); self.personal=PersonalizationService(catalog,settings); self.snapshot=snapshot
    def _references(self,context):
        if self.snapshot.implementation_hash!=_code_hash(): raise ValueError('PERSONALIZATION_VERSION_UNAVAILABLE')
        if self.snapshot.as_of>context.as_of: raise ValueError('FUTURE_PERSONALIZATION_FORBIDDEN')
        self.personal.store.snapshot(self.snapshot.snapshot_id,known_at=context.as_of)
        if self.snapshot.audience=='SYNTHETIC_VALIDATION' and context.environment!='PILOT_TEST': raise ValueError('SYNTHETIC_PERSONALIZATION_FORBIDDEN')
        return {**super()._references(context),'personalization':{'snapshot_id':str(self.snapshot.snapshot_id),
            'content_hash':self.snapshot.content_hash,'algorithm_version':self.snapshot.algorithm_version,'implementation_hash':self.snapshot.implementation_hash,
            'as_of':self.snapshot.as_of.isoformat(),'audience':self.snapshot.audience}}
    def create_personalized(self,input):
        request=input.request
        if request.as_of and self.snapshot.as_of>request.as_of: raise ValueError('FUTURE_PERSONALIZATION_FORBIDDEN')
        preferences={m.key:m for m in self.snapshot.memories if m.source_type=='EXPLICIT' and usable(m,self.snapshot.as_of)}
        changes={}; affected=[]
        if input.use_explicit_preferences:
            for key,field in (('default_horizon','horizon_days'),('default_mode','mode'),('preferred_instrument','symbol')):
                if key in preferences and field not in request.model_fields_set:
                    changes[field]=preferences[key].value; affected.append({'memory_id':str(preferences[key].memory_id),'field':field})
        # Personalization is opt-in and freshness is explicit; it never mutates
        # an old Phase 10 dossier or silently reuses a differently scoped plan.
        request=request.model_copy(update={**changes,'duplicate_policy':'fresh'})
        mission=super().create(request)
        if mission.status!='READY': return mission
        emphasis=preferences.get('review_emphasis')
        order=[s.step_id for s in mission.plan.steps]
        if emphasis:
            priority={'quant':{'quant'},'intelligence':{'context'},'contradictions':{'challenge'},'historical':{'previous_features','previous_context'}}[emphasis.value]
            steps=sorted(mission.plan.steps,key=lambda s:(0 if s.step_id=='availability' else 1 if s.step_id in priority else 2,order.index(s.step_id)))
            try:
                plan=validate_plan(mission.plan.model_copy(update={'steps':steps}),mission.request,mission.budgets,mission.context,mission.previous_context)
                mission=mission.model_copy(update={'plan':plan}); affected.append({'memory_id':str(emphasis.memory_id),'field':'approved_tool_order'})
            except ValueError:
                affected.append({'memory_id':str(emphasis.memory_id),'field':'ORDER_RETAINED_TO_PRESERVE_DEPENDENCIES_AND_BUDGET'})
        mission=self.store.save(mission.model_copy(update={'activity':mission.activity+[{'action':'PERSONALIZED_PLAN_REVIEW','snapshot_id':str(self.snapshot.snapshot_id),
            'affected':affected,'reminders':self.snapshot.coaching,'owner_sample_N':self.snapshot.observed_behavior['genuine_owner_record_N'],
            'canonical_calculations_unchanged':True}]}))
        if self.personal.store.owner_ready or self.snapshot.audience=='SYNTHETIC_VALIDATION':
            self.personal.attest(AttestationInput(audience=self.snapshot.audience,source_kind='mission',source_id=mission.mission_id,source_version=mission.revision))
        return mission
    def replay_personalized(self,key):
        mission=self.store.get(key); ref=mission.frozen_references.get('personalization')
        if not ref: raise ValueError('MISSION_HAS_NO_PERSONALIZATION')
        snapshot=self.personal.store.snapshot(UUID(ref['snapshot_id']),known_at=mission.context.as_of)
        source_checks=self.personal.verify_snapshot(snapshot)
        verified=snapshot.content_hash==ref['content_hash'] and snapshot.as_of<=mission.context.as_of and source_checks['matched']
        # Frozen personal evidence stays inspectable even after current preferences
        # are changed or disabled. Narrative curation is never re-executed.
        return {**super().replay(key),'personalization_verified':verified,'personal_algorithm':ref['algorithm_version'],
            'personal_implementation_available':ref['implementation_hash']==_code_hash(),'personal_source_checks':source_checks}
