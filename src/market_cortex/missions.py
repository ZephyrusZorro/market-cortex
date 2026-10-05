"""One bounded, checkpointed research orchestrator. No general agent executor."""
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import UUID, uuid4
import hashlib
import re
import time
from contextlib import contextmanager
from threading import Event,Thread

from .cortex import CortexService, _natural_cutoff
from .cortex_contracts import ResearchRequest, ToolRun
from .cortex_gateway import NoModelGateway, gateway_from_environment, may_send_context
from .cortex_tools import ToolRegistry
from .database import connect
from .intelligence_store import digest
from .jobs import JobQueue
from .mission_contracts import ResearchMission, MissionRequest, ExperimentProposal, PlanStep
from .mission_evaluator import evaluate, evidence, render_report, validate_claims
from .mission_policy import CAPABILITIES, build_plan, mode_budget, validate_plan
from .mission_store import MissionStore
from .quant_store import QuantStore


def now(): return datetime.now(timezone.utc)


def _implementation_snapshot():
    root=Path(__file__).parent
    names=('mission_contracts.py','mission_policy.py','mission_store.py','mission_evaluator.py','missions.py',
        'cortex_tools.py','cortex_gateway.py','features.py','market_state.py','intelligence.py','quant.py','jobs.py')
    return digest({n:hashlib.sha256((root/n).read_text(encoding='utf-8').replace('\r\n','\n').encode()).hexdigest() for n in names})


IMPLEMENTATION_HASH=_implementation_snapshot()


def implementation_hash():
    """Identify the implementation loaded by this process, as Quant Lab does."""
    return IMPLEMENTATION_HASH


class MissionStop(Exception):
    pass


@contextmanager
def heartbeat(renew):
    """Local lease renewal stops with the process; no detached research loop."""
    stop=Event()
    def keep_alive():
        while not stop.wait(15):
            try:
                if not renew(): return
            except Exception:
                # No credential/connection exception strings are logged. Expiry
                # fences saves and allows a later worker to reclaim the checkpoint.
                continue
    thread=Thread(target=keep_alive,daemon=True,name='cortex-research-lease')
    thread.start()
    try: yield
    finally:
        stop.set(); thread.join(timeout=2)


class MissionService:
    def __init__(self,catalog,settings,*,gateway=None):
        self.catalog=catalog; self.settings=settings; self.store=MissionStore(catalog.dsn)
        self.resolver=CortexService(catalog,settings,gateway=NoModelGateway())
        try: self.gateway=gateway if gateway is not None else gateway_from_environment()
        except ValueError: self.gateway=NoModelGateway()

    def _scope(self,request,manifest=None,cutoff=None,context_manifest=None):
        cutoff=cutoff or request.as_of or now()
        if cutoff>now(): raise LookupError('FUTURE_CUTOFF_UNAVAILABLE')
        manifest=manifest or request.manifest_id
        with connect(self.catalog.dsn) as c:
            if manifest:
                row=c.execute('SELECT manifest_id,created_at FROM dataset_manifests WHERE manifest_id=%s AND created_at<=%s',(manifest,cutoff)).fetchone()
            else:
                # Tied source timestamps must not select an arbitrary partial manifest.
                row=c.execute('WITH RECURSIVE chain AS (SELECT m.manifest_id,m.parent_manifest_id,m.created_at,0 AS depth FROM dataset_manifests m JOIN dataset_head h USING(manifest_id) UNION ALL SELECT m.manifest_id,m.parent_manifest_id,m.created_at,p.depth+1 FROM dataset_manifests m JOIN chain p ON p.parent_manifest_id=m.manifest_id) SELECT manifest_id,created_at FROM chain WHERE created_at<=%s ORDER BY depth LIMIT 1',(cutoff,)).fetchone()
        if not row: raise LookupError('MANIFEST_NOT_KNOWN_AT_CUTOFF')
        return self.resolver._resolve(ResearchRequest(question=request.goal,mode='pinned',manifest_id=row[0],as_of=cutoff,
            context_manifest_id=context_manifest,symbol=request.symbol,compare_symbol=request.compare_symbol))

    def _references(self,context):
        cutoff=context.as_of
        # Freeze artifact IDs and recorded times, not values from a static report.
        with connect(self.catalog.dsn) as c:
            rows=c.execute("SELECT artifact_id,created_at,content_hash FROM quant_artifacts WHERE kind IN ('walk_forward','robustness','sensitivity','monte_carlo','comparison') AND created_at<=%s ORDER BY created_at DESC LIMIT 20",(cutoff,)).fetchall()
        quant=[]
        for key,at,h in rows:
            item=QuantStore(self.catalog.dsn).get(key,as_of=cutoff)
            quant.append({'id':str(key),'created_at':at.isoformat(),'content_hash':h,'kind':item.get('kind')})
        prior=self.store.recent(as_of=cutoff,limit=20)
        prior=[m for m in prior if m.context and m.context.symbol==context.symbol and m.status in ('COMPLETED','INCONCLUSIVE','FAILED','WAITING_FOR_DATA')][:5]
        return {'quant':quant,'prior':[{'id':str(m.mission_id),'revision':m.revision,'content_hash':m.content_hash} for m in prior]}

    @staticmethod
    def _request_signature(request):
        return request.model_dump(mode='json',exclude={'as_of','duplicate_policy'})

    def create(self,request):
        request=MissionRequest.model_validate(request.model_dump())
        explicit_cutoff=bool(request.as_of)
        natural=_natural_cutoff(request.goal)
        if natural and not request.as_of:
            request=request.model_copy(update={'mode':'HISTORICAL_RESEARCH','as_of':natural})
            explicit_cutoff=True
        created=now(); cutoff=request.as_of or created
        request=request.model_copy(update={'as_of':cutoff})
        context=previous=None; reason=None
        try:
            if (request.thesis_id or request.candidate_id) and not request.symbol:
                from .opportunity_store import OpportunityStore
                records=OpportunityStore(self.catalog.dsn)
                linked=records.thesis(request.thesis_id,request.thesis_version) if request.thesis_id else records.candidate(request.candidate_id)
                if not linked or max(linked.created_at,getattr(linked,'updated_at',linked.created_at))>cutoff: raise LookupError('RESEARCH_RECORD_NOT_KNOWN_AT_CUTOFF')
                request=request.model_copy(update={'symbol':linked.symbol})
            context=self._scope(request,context_manifest=request.context_manifest_id)
            request=request.model_copy(update={'symbol':context.symbol,'compare_symbol':context.compare_symbol})
            if request.previous_mission_id:
                baseline=self.store.get_at(request.previous_mission_id,cutoff)
                if not baseline.context: raise LookupError('BASELINE_CONTEXT_UNAVAILABLE')
                previous=baseline.context
            elif request.older_manifest_id:
                if request.older_as_of>cutoff: raise ValueError('BASELINE_AFTER_CURRENT_CUTOFF')
                previous=self._scope(request,request.older_manifest_id,request.older_as_of)
        except LookupError as error: reason=str(error)
        if context and not explicit_cutoff and request.duplicate_policy=='reuse':
            for old in self.store.recent(limit=30):
                if old.context==context: continue  # exact scopes handled by the idempotency key below
                if old.context and old.context.manifest_id==context.manifest_id and old.context.context_manifest_id==context.context_manifest_id and old.code_hash==implementation_hash() and (created-old.created_at).total_seconds()<3600 and old.status in ('READY','RUNNING','COMPLETED','INCONCLUSIVE'):
                    if self._request_signature(old.request)==self._request_signature(request): return old
        refs=self._references(context) if context else {}
        budget=request.budgets or mode_budget(request.mode)
        mission=ResearchMission(mission_id=uuid4(),created_at=created,updated_at=created,request=request,context=context,
            previous_context=previous,budgets=budget,frozen_references=refs,code_hash=implementation_hash(),
            similar_mission_ids=[UUID(p['id']) for p in refs.get('prior',[])])
        key=digest({'request':request.model_dump(mode='json'),'context':context.model_dump(mode='json') if context else None,'code':mission.code_hash})
        if request.duplicate_policy=='fresh': key=digest({'key':key,'fresh':str(mission.mission_id)})
        mission=self.store.create(mission,key)
        if mission.status!='CREATED': return mission
        mission=self.store.save(mission.model_copy(update={'status':'PLANNING','usage':mission.usage.model_copy(update={'planner_iterations':1})}))
        if reason or not context:
            return self.store.save(mission.model_copy(update={'status':'WAITING_FOR_DATA','termination_reason':reason or 'SCOPE_UNAVAILABLE'}))
        started=time.perf_counter()
        try:
            plan=validate_plan(build_plan(request,context,previous),request,budget,context,previous)
            experiments=[]
            if request.experiment:
                experiments=[ExperimentProposal(proposal_id=digest(request.experiment.model_dump(mode='json'))[:20],
                    hypothesis='The predeclared registered strategy produces descriptive results under the chosen frozen scope; independent OOS evidence is required.',
                    definition=request.experiment,registered_at=now())]
            mission=mission.model_copy(update={'plan':plan,'experiments':experiments,'status':'READY',
                'activity':[{'action':'PLAN_VALIDATED','at':now().isoformat(),'planner_latency_ms':round((time.perf_counter()-started)*1000,2)}]})
        except ValueError:
            mission=mission.model_copy(update={'status':'FAILED','termination_reason':'PLAN_POLICY_REJECTED'})
        return self.store.save(mission)

    def _guard(self,mission):
        if self.store.cancelled(mission.mission_id): raise MissionStop('OWNER_CANCELLED')
        if mission.deadline_at and now()>=mission.deadline_at: raise MissionStop('DEADLINE_EXHAUSTED')
        if mission.code_hash!=implementation_hash(): raise MissionStop('ORCHESTRATION_VERSION_UNAVAILABLE')

    def _record_guard(self,step,context):
        if step.tool_id in ('opportunity.candidate','opportunity.thesis'):
            from .opportunity_store import OpportunityStore
            store=OpportunityStore(self.catalog.dsn)
            record=store.candidate(UUID(step.arguments['candidate_id'])) if step.tool_id.endswith('candidate') else store.thesis(UUID(step.arguments['thesis_id']),step.arguments['version'])
            if not record or max(record.created_at,getattr(record,'updated_at',record.created_at))>context.as_of:
                raise LookupError('RESEARCH_RECORD_NOT_KNOWN_AT_CUTOFF')

    def _extra_tool(self,mission,step,registry,*,replay=False):
        tool=step.tool_id; records=[]; started=time.perf_counter()
        def add(kind,label,value=None,**kw):
            records.append(registry._evidence(tool,kind,label,value=value,version='1.0.0',**kw))
        if tool=='mission.challenge_candidate':
            from .opportunity import OpportunityService
            from .opportunity_store import OpportunityStore
            from .opportunity_contracts import ScanRequest
            request=mission.request; store=OpportunityStore(self.catalog.dsn)
            if request.thesis_id:
                thesis=store.thesis(request.thesis_id,request.thesis_version)
                candidates=[thesis.candidate] if thesis and thesis.updated_at<=registry.context.as_of else []
            elif request.candidate_id:
                candidate=store.candidate(request.candidate_id)
                candidates=[candidate] if candidate and candidate.created_at<=registry.context.as_of else []
            else:
                scan=OpportunityService(self.catalog).scan(ScanRequest(mode='pinned',manifest_id=registry.context.manifest_id,
                    as_of=registry.context.as_of,symbol=registry.context.symbol,record=False))
                candidates=[c for c in scan.candidates if c.outcome=='candidate']
                rank={'strong':3,'moderate':2,'weak':1}
                candidates=sorted(candidates,key=lambda c:(-rank[c.detector_strength],c.symbol,c.detector_id))[:1]
            if not candidates:
                add('mission_limit','No supported current candidate to challenge',None,reason='Canonical scanner returned no eligible candidate; no synthetic thesis was created')
            for c in candidates:
                if c.source_manifest_id!=registry.context.manifest_id or c.as_of>registry.context.as_of:
                    raise LookupError('CANDIDATE_OUTSIDE_PINNED_SCOPE')
                add('candidate_status','Challenged candidate status',c.status,symbol=c.symbol,source_id=str(c.candidate_id),
                    reason=f'{c.detector_id}; {c.detector_strength}; deterministic strength ranking, not calibrated probability')
                for condition in c.trigger_conditions+c.confirmation_conditions+c.invalidation_conditions+c.rejection_conditions:
                    add('candidate_condition',condition.kind+': '+condition.description,condition.observed,symbol=c.symbol,
                        source_id=str(c.candidate_id),reason='MET' if condition.met else 'NOT_MET' if condition.met is False else 'UNAVAILABLE')
                for text in c.contradictions+c.rejection_reasons:
                    add('contradiction','Canonical challenge: '+text,'present',symbol=c.symbol,source_id=str(c.candidate_id))
                add('contradiction','A ranked observational candidate does not establish a profitable edge','present',symbol=c.symbol,
                    source_id=str(c.candidate_id),reason='Require independent quantitative support; selection bias, false confirmation and missing domains remain possible')
        elif tool=='mission.compare_states':
            def indexed(scope):
                return {(e.tool_id,e.kind,e.label,e.symbol,e.unit,e.version,digest(e.parameters)):e for s in mission.plan.steps if s.output and s.scope==scope and s.tool_id in ('instrument.features','intelligence.context') for e in s.output.evidence}
            old=indexed('previous'); current=indexed('current')
            for key in sorted(old.keys()|current.keys(),key=str):
                a=old.get(key); b=current.get(key)
                if not a or not b:
                    e=a or b
                    add('mission_comparison','Coverage change: '+e.label,'ADDED' if b else 'REMOVED',symbol=e.symbol,
                        source_id='diff:'+str(a.evidence_id if a else '')+':'+str(b.evidence_id if b else ''),reason='Coverage changes do not imply a market change or causation')
                elif a.value!=b.value:
                    numeric=type(a.value) in (int,float) and type(b.value) in (int,float)
                    add('mission_comparison','Change in '+b.label,b.value-a.value if numeric else f'{a.value} -> {b.value}',
                        unit=b.unit if numeric else None,symbol=b.symbol,source_id='diff:'+a.evidence_id+':'+b.evidence_id,
                        parameters={'before':a.value,'after':b.value} if numeric else {},reason='Comparable tool, feature version, parameters and units; fixed earlier/current knowledge cutoffs; no causal inference')
            if not records: add('mission_comparison','Comparable pinned evidence change','UNCHANGED_OR_UNAVAILABLE',reason='Inspect both pinned scopes; no assertion of improvement')
        elif tool=='mission.quant_evidence':
            found=False
            for ref in mission.frozen_references.get('quant',[]):
                item=QuantStore(self.catalog.dsn).get(UUID(ref['id']),as_of=registry.context.as_of)
                core={k:item[k] for k in ('schema_version','kind','definition','result')}
                if digest(core)!=ref['content_hash']: raise ValueError('FROZEN_QUANT_HASH_MISMATCH')
                strategy=item.get('definition',{}).get('definition',{}).get('strategy_id') or item.get('definition',{}).get('base',{}).get('strategy_id') or item.get('definition',{}).get('strategy_id')
                if strategy and strategy!=mission.request.strategy_id: continue
                if ref['kind']=='walk_forward':
                    found=True; result=item['result']; recorded=datetime.fromisoformat(ref['created_at'])
                    name='Momentum' if strategy=='momentum' else mission.request.strategy_id
                    add('quant_metric',name+' temporal OOS return',result.get('oos_total_return_compounded_reset_capital'),unit='fraction',source_id='quant:'+ref['id'],source_recorded_at=recorded,
                        reason='Compounded reset fold capital; not a continuous deployable portfolio')
                    add('quant_metric',name+' temporal OOS N',result.get('oos_N'),unit='trades',source_id='quant:'+ref['id'],source_recorded_at=recorded)
                    add('quant_limit','Quant OOS limitations','Selected survivors, dependent trades, regime mismatch and reset-capital fold aggregation; no supported edge established.',source_id='quant:'+ref['id'],source_recorded_at=recorded)
                elif ref['kind'] in ('robustness','sensitivity','monte_carlo','comparison'):
                    add('quant_reference','Quant '+ref['kind']+' artifact',ref['id'],source_id='quant:'+ref['id'],source_recorded_at=datetime.fromisoformat(ref['created_at']))
            if not found: add('quant_limit','Quant OOS evidence unavailable',None,reason='NO_VISIBLE_REGISTERED_OOS_STUDY')
        elif tool=='mission.prior':
            for ref in mission.frozen_references.get('prior',[]):
                old=self.store.get(UUID(ref['id']),ref['revision'])
                if old.content_hash!=ref['content_hash'] or old.updated_at>registry.context.as_of: raise ValueError('FUTURE_OR_CHANGED_RESEARCH_MEMORY')
                add('mission_memory','Earlier mission (historical research only)',str(old.mission_id),source_id='mission:'+str(old.mission_id),source_recorded_at=old.updated_at,
                    parameters={'revision':old.revision},reason=f'Historical {old.status}; manifest {old.context.manifest_id}; cutoff {old.context.as_of.isoformat()}; inspect frozen checkpoint for conclusion')
            if not records: add('mission_limit','Earlier relevant research unavailable',None)
        elif tool=='mission.quant_backtest':
            from .quant import QuantService
            proposal=mission.experiments[0]
            if replay:
                if not proposal.run_id: raise LookupError('EXPERIMENT_RESULT_UNAVAILABLE')
                result=QuantStore(self.catalog.dsn).get(proposal.run_id)
            else:
                # The typed definition is the only executable input. This callback cannot run arbitrary code.
                result=QuantService(self.catalog,self.settings.environment,progress=lambda _:self._guard(mission)).run(proposal.definition).model_dump(mode='json')
            run_id=result['run_id']
            with connect(self.catalog.dsn) as c:
                at=c.execute('SELECT created_at FROM quant_artifacts WHERE artifact_id=%s',(run_id,)).fetchone()[0]
            for key in ('N','net_total_return','max_drawdown'):
                value=result['metrics'].get(key)
                add('quant_counterfactual','Retrospective experiment '+key,value,source_id='quant:'+str(run_id),source_as_of=registry.context.as_of,
                    source_recorded_at=at,reason='RETROSPECTIVE_COUNTERFACTUAL')
        return ToolRun(tool_id=tool,version='1.0.0',description=CAPABILITIES[tool].side_effects,
            inputs={'manifest_id':str(registry.context.manifest_id),'as_of':registry.context.as_of.isoformat(),**step.arguments},
            status='ok' if any(e.value is not None for e in records) else 'unavailable',evidence=records,
            output_hash=digest([e.model_dump(mode='json') for e in records]),elapsed_ms=round((time.perf_counter()-started)*1000,2))

    def _execute(self,mission,step,*,replay=False):
        scope=mission.previous_context if step.scope=='previous' else mission.context
        registry=ToolRegistry(self.catalog,scope)
        self._record_guard(step,scope)
        return self._extra_tool(mission,step,registry,replay=replay) if step.tool_id.startswith('mission.') else registry.execute(step.tool_id,step.arguments)

    def _synthesize(self,mission,token=None,*,allow_model=True):
        claims,hypotheses,contradictions,quality,graph=evaluate(mission)
        metadata={'provider':'deterministic','status':'no_model_configured','paid_api_cost_inr':0,
            'configured_provider':self.gateway.provider,'locality':self.gateway.locality,
            'routing':{'scope':'deterministic','planner':'deterministic','evaluator':'deterministic','synthesis':'claim_id_curation'},'selected_claim_ids':[]}
        usage=mission.usage
        if allow_model and self.gateway.provider!='deterministic' and usage.model_calls<mission.budgets.max_model_calls:
            private=any(CAPABILITIES[s.tool_id].privacy=='OWNER_PRIVATE' for s in mission.plan.steps if s.output)
            if self.gateway.locality!='local' or not may_send_context(self.settings,self.gateway,contains_private_data=private):
                metadata['status']='PRIVACY_OR_ZERO_COST_POLICY_BLOCKED'
            elif not mission.deadline_at or (mission.deadline_at-now()).total_seconds()<16:
                metadata['status']='MODEL_DEADLINE_BUDGET_BLOCKED'
            else:
                usage=usage.model_copy(update={'model_calls':usage.model_calls+1})
                mission=self.store.save(mission.model_copy(update={'usage':usage}),token)
                # Never provide source prose, notes, journal entries or model-authored instructions.
                public_tools={s.tool_id for s in mission.plan.steps if CAPABILITIES[s.tool_id].privacy=='MARKET_PUBLIC'}
                by_id={e.evidence_id:e for e in evidence(mission)}
                candidates=[c.model_dump(mode='json') for c in claims if c.type in ('CALCULATION','CLASSIFICATION') and all(by_id[k].tool_id in public_tools and (isinstance(by_id[k].value,(float,int)) or by_id[k].kind=='dimension') for k in c.evidence_ids)][:12]
                try:
                    model_started=time.perf_counter()
                    result=self.gateway.select_claims(mission.request.goal,candidates)
                    allowed={c['claim_id'] for c in candidates}
                    if not result.selected_claim_ids or any(k not in allowed for k in result.selected_claim_ids): raise ValueError('MODEL_SELECTED_UNKNOWN_CLAIM')
                    metadata.update({'provider':result.provider,'model':result.model,'status':result.status,'latency_ms':result.latency_ms,'selected_claim_ids':list(result.selected_claim_ids)})
                    usage=usage.model_copy(update={'model_input_tokens':result.input_tokens,'model_output_tokens':result.output_tokens})
                except Exception:
                    metadata.update({'status':'MODEL_FAILED_DETERMINISTIC_FALLBACK','attempted_provider':self.gateway.provider,
                        'latency_ms':round((time.perf_counter()-model_started)*1000,2)})
        mission=mission.model_copy(update={'claims':claims,'hypotheses':hypotheses,'contradictions':contradictions,
            'limitations':[c for c in claims if c.type=='LIMITATION'],'evaluator':quality,'evidence_graph':graph,'model_metadata':metadata,'usage':usage})
        return mission.model_copy(update={'report':render_report(mission)})

    def run(self,key):
        mission=self.store.get(key)
        if mission.status in ('COMPLETED','INCONCLUSIVE','CANCELLED'): return mission
        if not mission.context: return mission  # A later scope requires a new mission, never a silent re-pin.
        if mission.termination_reason=='PLAN_POLICY_REJECTED': return mission
        validate_plan(mission.plan,mission.request,mission.budgets,mission.context,mission.previous_context)
        token=self.store.acquire(key,60)
        lease=heartbeat(lambda:self.store.renew(key,token)); lease.__enter__()
        started=time.perf_counter()
        earlier_elapsed=mission.usage.elapsed_ms
        def save(m): return self.store.save(m,token)
        try:
            self._guard(mission)
            mission=save(mission.model_copy(update={'status':'RUNNING','termination_reason':None,
                'deadline_at':mission.deadline_at or now()+timedelta(seconds=mission.budgets.timeout_seconds)}))
            for index in range(32):
                if index>=len(mission.plan.steps): break
                step=mission.plan.steps[index]
                if step.status=='DONE':
                    mission=save(mission.model_copy(update={'usage':mission.usage.model_copy(update={'cache_hits':mission.usage.cache_hits+1})}))
                    continue
                while True:
                    self._guard(mission)
                    if mission.usage.tool_calls>=mission.budgets.max_tool_calls: raise MissionStop('TOOL_BUDGET_EXHAUSTED')
                    if step.attempts>=2: raise MissionStop('TOOL_REPEATEDLY_FAILED')
                    counts={'tool_calls':mission.usage.tool_calls+1}
                    if step.scope=='previous' or step.tool_id=='mission.compare_states':
                        if mission.usage.historical_comparisons>=mission.budgets.max_historical_comparisons: raise MissionStop('HISTORICAL_BUDGET_EXHAUSTED')
                        counts['historical_comparisons']=mission.usage.historical_comparisons+1
                    if step.tool_id=='mission.quant_backtest':
                        if mission.usage.quant_runs>=mission.budgets.max_quant_runs: raise MissionStop('QUANT_BUDGET_EXHAUSTED')
                        counts['quant_runs']=mission.usage.quant_runs+1
                    step=step.model_copy(update={'status':'RUNNING','attempts':step.attempts+1})
                    steps=list(mission.plan.steps); steps[index]=step
                    mission=save(mission.model_copy(update={'plan':mission.plan.model_copy(update={'steps':steps}),'usage':mission.usage.model_copy(update=counts)}))
                    try:
                        output=self._execute(mission,step)
                        self._guard(mission)
                        step=step.model_copy(update={'status':'DONE','output':output,'error_code':None})
                        experiments=mission.experiments
                        if step.tool_id=='mission.quant_backtest' and output.evidence:
                            experiments=[experiments[0].model_copy(update={'status':'EXECUTED','run_id':UUID(output.evidence[0].source_id.removeprefix('quant:'))})]
                        steps=list(mission.plan.steps); steps[index]=step
                        mission=save(mission.model_copy(update={'experiments':experiments,'plan':mission.plan.model_copy(update={'steps':steps}),
                            'usage':mission.usage.model_copy(update={'elapsed_ms':earlier_elapsed+round((time.perf_counter()-started)*1000,2)}),
                            'activity':mission.activity+[{'action':'TOOL_FINISHED','step_id':step.step_id,'tool_id':step.tool_id,'latency_ms':output.elapsed_ms,'evidence_N':len(output.evidence),'status':output.status,'at':now().isoformat()}]}))
                        negative=any(e.label=='Momentum temporal OOS return' and type(e.value) in (int,float) and e.value<=0 for e in output.evidence)
                        pending=sum(s.status=='PENDING' for s in mission.plan.steps)
                        if negative and mission.request.mode!='QUICK_RESEARCH' and 'opportunities' in mission.request.approved_domains and not any(s.tool_id=='mission.challenge_candidate' for s in mission.plan.steps) and mission.usage.replans<mission.budgets.max_replans and mission.usage.planner_iterations<mission.budgets.max_planner_iterations and mission.usage.tool_calls+pending+1<=mission.budgets.max_tool_calls:
                            challenge=PlanStep(step_id='adversarial_challenge',question='Does a canonical candidate withstand the negative historical result?',tool_id='mission.challenge_candidate',domain='opportunities',
                                expected_evidence='Canonical conditions, counter-evidence or no supported candidate',reason='Negative OOS challenges the attractiveness assumption',depends_on=[step.step_id])
                            plan=validate_plan(mission.plan.model_copy(update={'steps':mission.plan.steps+[challenge]}),mission.request,mission.budgets,mission.context,mission.previous_context)
                            mission=save(mission.model_copy(update={'plan':plan,'usage':mission.usage.model_copy(update={'replans':mission.usage.replans+1,'planner_iterations':mission.usage.planner_iterations+1}),
                                'replans':mission.replans+[{'trigger':'NEGATIVE_OOS_COUNTER_EVIDENCE','action':'ADD_APPROVED_CANDIDATE_CHALLENGE','context_unchanged':True,'at':now().isoformat()}]}))
                        break
                    except MissionStop: raise
                    except Exception:
                        step=step.model_copy(update={'status':'FAILED','error_code':'APPROVED_TOOL_FAILED'})
                        steps=list(mission.plan.steps); steps[index]=step
                        mission=save(mission.model_copy(update={'plan':mission.plan.model_copy(update={'steps':steps}),
                            'activity':mission.activity+[{'action':'TOOL_FAILED','step_id':step.step_id,'error_code':'APPROVED_TOOL_FAILED','at':now().isoformat()}]}))
                        if step.attempts<2 and mission.usage.replans<mission.budgets.max_replans and mission.usage.planner_iterations<mission.budgets.max_planner_iterations:
                            mission=save(mission.model_copy(update={'usage':mission.usage.model_copy(update={'replans':mission.usage.replans+1,'planner_iterations':mission.usage.planner_iterations+1}),
                                'replans':mission.replans+[{'trigger':'TOOL_FAILURE','step_id':step.step_id,'action':'RETRY_SAME_APPROVED_STEP','context_unchanged':True,'at':now().isoformat()}]}))
                            continue
                        if step.required: raise MissionStop('REQUIRED_TOOL_FAILED')
                        break
            self._guard(mission)
            mission=self._synthesize(mission,token)
            self._guard(mission)
            unavailable=any(s.required and s.output and (s.output.status=='unavailable' or
                any(e.kind=='context_limit' and e.label==s.domain+' coverage' and e.value in ('UNKNOWN','UNSUPPORTED','STALE') for e in s.output.evidence) or
                all(e.value is None for e in s.output.evidence)) for s in mission.plan.steps)
            failed=any(s.status=='FAILED' for s in mission.plan.steps)
            status='WAITING_FOR_DATA' if unavailable else 'PARTIAL' if failed else 'INCONCLUSIVE'
            # Factual quick/context questions may be satisfied without implying an investable edge.
            if status=='INCONCLUSIVE' and mission.request.mode=='QUICK_RESEARCH' and not mission.contradictions and mission.evaluator['answered_with_limits']:
                status='COMPLETED'
            reason='REQUIRED_DATA_UNAVAILABLE' if unavailable else 'OPTIONAL_TOOL_FAILED' if failed else 'INVESTIGATION_FINISHED_WITH_EXPLICIT_LIMITS'
            mission=save(mission.model_copy(update={'status':status,'termination_reason':reason,
                'usage':mission.usage.model_copy(update={'elapsed_ms':earlier_elapsed+round((time.perf_counter()-started)*1000,2)}),
                'activity':mission.activity+[{'action':'GROUNDED_DOSSIER_SAVED','at':now().isoformat()}]}))
        except MissionStop as error:
            if str(error)=='OWNER_CANCELLED': return self.store.get(key)
            mission=self._synthesize(mission,allow_model=False)
            mission=save(mission.model_copy(update={'status':'FAILED' if mission.status=='READY' else 'PARTIAL','termination_reason':str(error),
                'usage':mission.usage.model_copy(update={'elapsed_ms':earlier_elapsed+round((time.perf_counter()-started)*1000,2)})}))
        except ValueError:
            if self.store.cancelled(key): return self.store.get(key)
            raise
        finally:
            lease.__exit__(None,None,None)
            self.store.release(key,token)
        return mission

    def replay(self,key):
        mission=self.store.get(key)
        if mission.code_hash!=implementation_hash(): return {'mission_id':str(key),'status':'ORCHESTRATION_VERSION_UNAVAILABLE','matched':False}
        checks=[]
        for step in mission.plan.steps:
            if not step.output: continue
            try:
                output=self._execute(mission,step,replay=True)
                checks.append({'step_id':step.step_id,'matched':output.output_hash==step.output.output_hash})
            except Exception: checks.append({'step_id':step.step_id,'matched':False,'reason':'PINNED_REPLAY_UNAVAILABLE'})
        _,rejected=validate_claims(mission.claims,evidence(mission),[mission.context,mission.previous_context],counterfactual=bool(mission.request.experiment))
        matched=bool(checks) and all(c['matched'] for c in checks) and not rejected
        return {'mission_id':str(key),'status':'VERIFIED' if matched else 'UNAVAILABLE_OR_MISMATCH',
            'matched':matched,'checks':checks,'grounding_rejected':rejected,'model_narrative_reexecuted':False,'scope_unchanged':True}

    def diff(self,older,newer):
        a=self.store.get(older); b=self.store.get(newer)
        def indexed(m):
            return {(e.tool_id,e.kind,e.label,e.symbol,e.unit,e.version,digest(e.parameters)):e for e in evidence(m)
                if m.context and e.as_of==m.context.as_of}
        left=indexed(a); right=indexed(b); rows=[]
        for key in sorted(left.keys()|right.keys(),key=str):
            x=left.get(key); y=right.get(key)
            if x and y and x.value==y.value: continue
            rows.append({'tool_id':key[0],'label':key[2],'symbol':key[3],'before':x.value if x else None,'after':y.value if y else None,
                'change':'CHANGED' if x and y else 'ADDED' if y else 'REMOVED','before_evidence':x.evidence_id if x else None,'after_evidence':y.evidence_id if y else None,
                'delta':y.value-x.value if x and y and type(x.value) in (int,float) and type(y.value) in (int,float) else None})
        return {'older_mission_id':str(older),'newer_mission_id':str(newer),'older_scope':a.context.model_dump(mode='json') if a.context else None,
            'newer_scope':b.context.model_dump(mode='json') if b.context else None,'evidence_changes':rows,
            'hypothesis_before':[h.model_dump(mode='json') for h in a.hypotheses],'hypothesis_after':[h.model_dump(mode='json') for h in b.hypotheses],
            'causal_inference':False,'quantitative_support_before':a.evaluator.get('quantitative_support'),'quantitative_support_after':b.evaluator.get('quantitative_support')}

    def enqueue(self,key):
        mission=self.store.get(key)
        with connect(self.catalog.dsn) as c:
            active=c.execute('SELECT lease_token IS NOT NULL AND lease_until>now() FROM research_missions WHERE mission_id=%s',(key,)).fetchone()[0]
        if active: raise ValueError('MISSION_ALREADY_RUNNING')
        return JobQueue(self.catalog.dsn).enqueue('cortex_mission',f'mission:{key}:revision:{mission.revision}',{'mission_id':str(key)})

    def worker(self,job_id=None):
        queue=JobQueue(self.catalog.dsn); job=queue.claim(lease_seconds=60,kind='cortex_mission',job_id=job_id)
        if not job: return {'status':'NO_JOB'}
        try:
            with heartbeat(lambda:queue.renew(job.job_id,job.attempts,60)):
                mission=self.run(UUID(job.payload['mission_id']))
            queue.finish(job.job_id,job.attempts)
            return {'status':'DONE','mission_id':str(mission.mission_id),'mission_status':mission.status}
        except Exception:
            queue.finish(job.job_id,job.attempts,'MISSION_WORKER_FAILED',max_attempts=2)
            return {'status':'FAILED','error_code':'MISSION_WORKER_FAILED'}
