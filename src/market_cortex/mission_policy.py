"""Explicit research capabilities, bounded workflow templates and plan validation."""
from dataclasses import asdict, dataclass

from .cortex_tools import SPECS
from .mission_contracts import MissionBudget, MissionPlan, PlanStep
from .quant_contracts import BacktestDefinition


@dataclass(frozen=True)
class Capability:
    tool_id: str
    domain: str
    version: str = '1.0.0'
    deterministic: bool = True
    access: str = 'READ_ONLY'
    cost_class: str = 'FREE_LOCAL'
    latency_class: str = 'BOUNDED_LOCAL'
    privacy: str = 'MARKET_PUBLIC'
    as_of_support: bool = True
    autonomous: bool = True
    side_effects: str = 'none'


CAPABILITIES = {name:Capability(name,domain,privacy=privacy) for domain,privacy,names in (
    ('market','MARKET_PUBLIC',('dataset.context','dataset.manifest','instrument.features','market.state','asset.compare')),
    ('intelligence','MARKET_PUBLIC',tuple('intelligence.'+name for name in ('context','macro','derivatives','provenance'))),
    ('events','MARKET_PUBLIC',('intelligence.events',)), ('news','MARKET_PUBLIC',('intelligence.news',)),
    ('options','MARKET_PUBLIC',('intelligence.options',)),('onchain','MARKET_PUBLIC',('intelligence.onchain',)),
    ('fundamentals','MARKET_PUBLIC',('intelligence.fundamentals',)),
    ('opportunities','OWNER_PRIVATE',('opportunity.scan','opportunity.candidate','opportunity.thesis')),
    ('quant','OWNER_PRIVATE',('quant.runs','quant.run','quant.study','quant.trade','mission.quant_evidence')),
    ('memory','OWNER_PRIVATE',('research.prior','mission.prior')),
    ('learning','OWNER_PRIVATE',('learning.predictions','learning.prediction','learning.performance','learning.edges')),
    ('journal','OWNER_PRIVATE',('learning.journal','learning.entry')),
    ('portfolio','OWNER_PRIVATE',('risk.portfolio','risk.scenario','risk.overlay')),
) for name in names}
CAPABILITIES['mission.quant_backtest']=Capability('mission.quant_backtest','quant',access='RESEARCH_ARTIFACT_ONLY',
    privacy='OWNER_PRIVATE',latency_class='BOUNDED_QUANT',side_effects='immutable quant research artifacts; no strategy/risk/source mutation')
CAPABILITIES['mission.compare_states']=Capability('mission.compare_states','market')
CAPABILITIES['mission.challenge_candidate']=Capability('mission.challenge_candidate','opportunities',privacy='OWNER_PRIVATE')


def metadata():
    return [{**asdict(c),'description':SPECS[c.tool_id].description if c.tool_id in SPECS else
             {'mission.quant_evidence':'Inspect frozen stored OOS/study references at cutoff',
              'mission.prior':'Retrieve earlier missions as historical research only',
              'mission.compare_states':'Compare compatible features and contextual evidence from two pinned states',
              'mission.challenge_candidate':'Challenge the strongest canonical ephemeral candidate or selected recorded candidate; no ledger mutation',
              'mission.quant_backtest':'One owner-approved registered backtest; preregistered proposal required'}[c.tool_id],
             'required_data_domains':[c.domain]} for c in CAPABILITIES.values()]


def mode_budget(mode):
    return MissionBudget(max_tool_calls=6 if mode=='QUICK_RESEARCH' else 16,
        timeout_seconds=120 if mode=='QUICK_RESEARCH' else 300)


def build_plan(request,context,previous=None):
    steps=[]
    def add(key,tool,question,domain,arguments=None,*,required=False,scope='current'):
        if domain not in request.approved_domains or domain in request.excluded_domains: return
        steps.append(PlanStep(step_id=key,question=question,tool_id=tool,domain=domain,
            arguments=arguments or {},expected_evidence='Typed tool evidence with manifests, knowledge cutoff and source IDs',
            reason='Relevant declared research domain; collect evidence before interpretation',
            depends_on=['availability'] if steps else [],required=required or domain in request.required_domains,scope=scope))
    add('availability','dataset.context','What data and freshness are available?','market',required=True)
    symbol=context.symbol
    if symbol: add('features','instrument.features','What do current canonical features show?','market',{'symbol':symbol},required=True)
    if context.compare_symbol and symbol:
        add('relative','asset.compare','Does aligned relative strength confirm the focal asset?','market',{'target':symbol,'reference':context.compare_symbol})
    quick=request.mode=='QUICK_RESEARCH'
    if not quick or request.template=='market_review': add('state','market.state','What is the narrow Pilot 5 state?','market')
    add('context','intelligence.context','What contextual facts, conflicts and unavailable domains matter?','intelligence',{'symbol':symbol})
    for domain in ('options','events','news','fundamentals','onchain'):
        if domain in request.required_domains:
            add('required_'+domain,'intelligence.'+domain,'Is the required source domain actually available?',domain,{'symbol':symbol},required=True)
    if not quick:
        add('opportunities','opportunity.scan','What do canonical detector evaluations support or reject?','opportunities',{'symbol':symbol})
    if request.candidate_id: add('candidate','opportunity.candidate','Inspect the recorded candidate and rejection reasons','opportunities',{'candidate_id':str(request.candidate_id)})
    if request.thesis_id: add('thesis','opportunity.thesis','Challenge the frozen thesis version and invalidation history','opportunities',{'thesis_id':str(request.thesis_id),'version':request.thesis_version},required=True)
    if request.template=='thesis_challenge' or request.mode=='THESIS_REVIEW':
        add('challenge','mission.challenge_candidate','What canonical conditions and counter-evidence weaken the selected setup?','opportunities',required=True)
    if not quick or any(term in request.goal.lower() for term in ('histor','support','edge','strategy')):
        add('quant','mission.quant_evidence','What saved OOS, robustness and sample evidence supports this registered strategy?','quant',required=request.mode=='STRATEGY_RESEARCH')
    if not quick and symbol: add('memory','mission.prior','What prior research exists, and what remains historical?','memory')
    if request.template in ('market_review','thesis_challenge','strategy_review') or request.mode in ('STRATEGY_RESEARCH','THESIS_REVIEW'):
        add('learning','learning.performance','Do recorded outcomes expose failures or weak samples?','learning')
        add('predictions','learning.predictions','Which outcomes remain pending?','learning')
    if request.portfolio_id: add('risk','risk.portfolio','What frozen local portfolio risk is relevant?','portfolio',{'portfolio_id':str(request.portfolio_id)})
    if previous:
        if symbol: add('previous_features','instrument.features','What actually changed in canonical features?','market',{'symbol':symbol},scope='previous')
        add('previous_context','intelligence.context','What changed in derivative/macro coverage and facts?','intelligence',{'symbol':symbol},scope='previous')
        add('changes','mission.compare_states','Which comparable evidence values or coverage states changed?','market')
        if steps[-1].step_id=='changes':
            steps[-1]=steps[-1].model_copy(update={'depends_on':[s.step_id for s in steps[:-1] if s.step_id in ('features','context','previous_features','previous_context')]})
    if request.experiment: add('experiment','mission.quant_backtest','Execute exactly one predeclared registered definition','quant',request.experiment.model_dump(mode='json'),required=True)
    return MissionPlan(steps=steps)


def validate_plan(plan,request,budgets,context,previous=None):
    plan=MissionPlan.model_validate(plan.model_dump())
    keys={s.step_id for s in plan.steps}
    if len(keys)!=len(plan.steps) or not keys: raise ValueError('INVALID_PLAN')
    if len(plan.steps)>budgets.max_tool_calls: raise ValueError('PLAN_EXCEEDS_TOOL_BUDGET')
    seen=set(); depth={}; quant=historical=0
    for s in plan.steps:
        cap=CAPABILITIES.get(s.tool_id)
        if not cap or not cap.autonomous: raise ValueError('TOOL_NOT_APPROVED_FOR_AUTONOMY')
        if cap.domain!=s.domain or cap.domain not in request.approved_domains or cap.domain in request.excluded_domains:
            raise ValueError('PLAN_DOMAIN_POLICY_BLOCK')
        if not set(s.depends_on)<=seen: raise ValueError('CIRCULAR_OR_UNORDERED_PLAN')
        depth[s.step_id]=1+max((depth[d] for d in s.depends_on),default=0)
        if depth[s.step_id]>4: raise ValueError('EXCESSIVE_PLAN_DEPTH')
        scope=previous if s.scope=='previous' else context
        if scope is None: raise ValueError('INVALID_MANIFEST_SCOPE')
        if s.scope=='previous': historical+=1
        if s.tool_id=='mission.compare_states':
            if previous is None: raise ValueError('CHANGE_BASELINE_REQUIRED')
            historical+=1
        if s.tool_id in SPECS:
            SPECS[s.tool_id].input_schema.model_validate(s.arguments)
            if s.arguments.get('context_manifest_id') not in (None,str(scope.context_manifest_id),scope.context_manifest_id):
                raise ValueError('CONTEXT_SCOPE_OVERRIDE_FORBIDDEN')
            for field in ('symbol','target','reference'):
                if s.arguments.get(field) and s.arguments[field] not in scope.members: raise ValueError('INSTRUMENT_NOT_VISIBLE')
        elif s.tool_id=='mission.quant_backtest':
            d=BacktestDefinition.model_validate(s.arguments); quant+=1
            if not request.experiment or d!=request.experiment: raise ValueError('EXPERIMENT_NOT_PREAPPROVED')
            if d.manifest_id!=context.manifest_id or d.source_as_of!=context.as_of or (d.end-d.start).days>31:
                raise ValueError('EXPERIMENT_SCOPE_OR_WINDOW_INVALID')
        elif s.arguments: raise ValueError('UNEXPECTED_TOOL_ARGUMENTS')
        seen.add(s.step_id)
    if quant>budgets.max_quant_runs or historical>budgets.max_historical_comparisons: raise ValueError('PLAN_EXCEEDS_RESEARCH_BUDGET')
    if not set(request.required_domains)<={s.domain for s in plan.steps}: raise ValueError('MANDATORY_DOMAIN_NOT_PLANNED')
    return plan
