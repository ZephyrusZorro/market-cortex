"""Deterministic claim grounding, hypothesis tests and evidence quality dimensions."""
import math

from .intelligence_store import digest
from .mission_contracts import Hypothesis, MissionClaim


def evidence(mission):
    return [e for step in mission.plan.steps if step.output for e in step.output.evidence]


def fact_text(e):
    value=e.value if e.value is not None else 'UNAVAILABLE'
    if e.unit=='fraction' and type(value) in (int,float): value=f'{value} ({value*100:+.2f}%)'
    if isinstance(value,str) and len(value)>6000: value=value[:6000]+' [inspect full evidence]'
    return f'{e.label}: {value}'+(f' {e.unit}' if e.unit else '')+'.'


def claim(kind,text,refs,stance='neutral',value=None,numeric_id=None):
    ids=[e.evidence_id for e in refs]
    return MissionClaim(claim_id=digest({'type':kind,'text':text,'refs':ids})[:20],type=kind,text=text,
        evidence_ids=ids,stance=stance,observed_value=value,numeric_evidence_id=numeric_id)


def validate_claims(claims,records,contexts,*,counterfactual=False):
    by_id={e.evidence_id:e for e in records}; accepted=[]; rejected=[]
    scopes={(str(c.manifest_id),c.as_of):c for c in contexts if c}
    for item in claims:
        reason=None
        if not item.evidence_ids or any(key not in by_id for key in item.evidence_ids): reason='CITATION_REQUIRED'
        for key in item.evidence_ids:
            if key not in by_id: continue
            e=by_id[key]; scope=scopes.get((str(e.manifest_id),e.as_of))
            if scope is None: reason='WRONG_MANIFEST_OR_CUTOFF'
            elif (e.source_as_of and e.source_as_of>scope.as_of) or (e.source_recorded_at and e.source_recorded_at>scope.as_of and not (counterfactual and e.tool_id=='mission.quant_backtest' and e.reason=='RETROSPECTIVE_COUNTERFACTUAL')): reason='FUTURE_EVIDENCE'
            elif e.kind.startswith('context_') and e.source_manifest_id and e.source_manifest_id!=scope.context_manifest_id: reason='WRONG_CONTEXT_MANIFEST'
            elif e.symbol and e.symbol not in scope.members: reason='CLAIM_SCOPE_EXCEEDS_EVIDENCE'
            if isinstance(e.value,float) and not math.isfinite(e.value): reason='INVALID_NUMERICAL_EVIDENCE'
        if item.numeric_evidence_id:
            e=by_id.get(item.numeric_evidence_id)
            if not e or e.evidence_id not in item.evidence_ids or item.observed_value!=e.value or item.text!=fact_text(e): reason='NUMERIC_MISMATCH'
        elif item.type in ('FACT','CALCULATION','CLASSIFICATION'): reason='CANONICAL_VALUE_REFERENCE_REQUIRED'
        if reason: rejected.append({'claim_id':item.claim_id,'reason':reason})
        else: accepted.append(item)
    return accepted,rejected


def evaluate(mission):
    records=evidence(mission)
    claims=[]; skeptic=[]; alternatives=[]
    for e in records:
        limitation=e.value is None or e.kind in ('missing','context_limit','quant_limit','learning_limit','mission_limit')
        kind='LIMITATION' if limitation else 'CALCULATION' if isinstance(e.value,(float,int)) else 'CLASSIFICATION'
        claims.append(claim(kind,fact_text(e),[e],'limitation' if limitation else 'neutral',e.value,e.evidence_id))
        if e.freshness in ('stale','unknown'):
            skeptic.append(claim('CONTRADICTION','Stored evidence is stale or has unknown freshness; current attractiveness cannot be established from it.',[e],'counter'))
        if e.kind=='contradiction' or e.label=='Source conflict':
            skeptic.append(claim('CONTRADICTION','A retrieved deterministic conflict must remain unresolved unless new sourced evidence resolves it.',[e],'counter'))
        if e.label=='Momentum temporal OOS return' and isinstance(e.value,(int,float)) and e.value<=0:
            skeptic.append(claim('CONTRADICTION','Recorded momentum temporal OOS evidence is nonpositive; it does not support a historical momentum edge.',[e],'counter'))
        if e.label=='rsi(14)' and isinstance(e.value,(int,float)) and (e.value>70 or e.value<30):
            skeptic.append(claim('CONTRADICTION','RSI is outside the declared 30–70 descriptive range; continuation and reversal explanations remain competing hypotheses.',[e],'counter'))
    current=[e for e in records if mission.context and e.as_of==mission.context.as_of and (not e.symbol or e.symbol==mission.context.symbol)]
    support=[e for e in current if e.label in ('rolling_return(20)','macd_histogram') and isinstance(e.value,(int,float)) and e.value>0]
    opposing=[e for e in current if e.label in ('rolling_return(20)','macd_histogram') and isinstance(e.value,(int,float)) and e.value<=0]
    if support or opposing:
        stale=any(e.freshness in ('stale','unknown') for e in support+opposing)
        status='INCONCLUSIVE' if stale else 'WEAKENED' if support and opposing else 'SUPPORTED_BY_CURRENT_EVIDENCE' if support else 'CONTRADICTED'
        hypothesis=Hypothesis(hypothesis_id='current_momentum',statement='Positive canonical momentum is present; this does not imply future profitability or improvement over an earlier state.',
            originating_evidence=[e.evidence_id for e in support+opposing],test_requirements=['rolling_return(20)','macd_histogram','freshness','aligned earlier state for improvement'],
            support=[e.evidence_id for e in support],contradictions=[e.evidence_id for e in opposing],status=status)
    else:
        hypothesis=Hypothesis(hypothesis_id='current_momentum',statement='Current momentum support requires sufficient visible canonical features.',
            originating_evidence=[e.evidence_id for e in records[:1]],test_requirements=['visible canonical features'],status='INCONCLUSIVE')
    quant_refs=[e for e in records if e.label=='Momentum temporal OOS return' and type(e.value) in (int,float)]
    if quant_refs:
        alternatives.append(Hypothesis(hypothesis_id='historical_momentum_support',statement='Registered momentum has positive temporal OOS support in the saved Pilot 5 study.',
            originating_evidence=[e.evidence_id for e in quant_refs],test_requirements=['independent temporal OOS','regime-aligned evidence','sufficient independent sample'],
            support=[e.evidence_id for e in quant_refs if e.value>0],contradictions=[e.evidence_id for e in quant_refs if e.value<=0],
            status='CONTRADICTED' if any(e.value<=0 for e in quant_refs) else 'INCONCLUSIVE'))
    for labels,statement,requirements in (
        (('correlation','relative_strength','Pilot above SMA20'),'Broad crypto beta may explain apparent asset momentum; aligned comparison can describe participation, not causation.',['aligned returns','relative strength','broader universe']),
        (('annualized_volatility(20)',),'Volatility expansion may explain unstable momentum; a single current volatility value cannot establish a change.',['earlier comparable volatility','adequate regime sample']),
        (('derivatives.oi_change_fraction','derivatives.funding_latest'),'Derivatives positioning is an alternative explanation; funding and OI do not identify short covering or causal position ownership.',['contract-aligned series','position attribution unavailable']),
    ):
        refs=[e for e in current if e.label in labels and e.value is not None]
        if refs: alternatives.append(Hypothesis(hypothesis_id=digest(statement)[:16],statement=statement,
            originating_evidence=[e.evidence_id for e in refs],test_requirements=requirements,status='INCONCLUSIVE'))
    thesis_refs=[e for e in current if e.kind in ('thesis_status','candidate_status','candidate_summary') and e.value in ('REJECTED','INVALIDATED','EXPIRED','NO_EDGE')]
    if thesis_refs: skeptic.append(claim('CONTRADICTION','Canonical candidate/thesis evidence rejects or invalidates the reviewed setup; narrative interpretation cannot override it.',thesis_refs[:10],'counter'))
    claims+=skeptic
    accepted,rejected=validate_claims(claims,records,[mission.context,mission.previous_context],counterfactual=bool(mission.request.experiment))
    approved_ids={c.claim_id for c in accepted}
    skeptic=[c for c in skeptic if c.claim_id in approved_ids]
    domains={s.domain for s in mission.plan.steps if s.status=='DONE' and s.output and s.output.status!='unavailable' and not any(e.kind=='context_limit' and e.label==s.domain+' coverage' and e.value in ('UNKNOWN','UNSUPPORTED','STALE') for e in s.output.evidence)}
    missing=set(mission.request.required_domains)-domains
    quality={'evidence_count':len(records),'domains_examined':sorted(domains),'mandatory_domains_missing':sorted(missing),
        'freshness':sorted({e.freshness for e in records if e.freshness}),
        'source_tools':sorted({e.tool_id for e in records}), 'contradiction_N':len(skeptic),
        'source_diversity':{'provider_ids':sorted({e.provider_id for e in records if e.provider_id}),
            'source_record_N':len({e.source_id for e in records if e.source_id}),'basis':'Distinct recorded sources and tools, not statistically independent confirmation'},
        'quant_trade_sample_N':[e.value for e in records if e.label.endswith('temporal OOS N')],
        'unavailable_domains':[e.label for e in records if e.kind=='context_limit' and e.value in ('UNKNOWN','UNSUPPORTED','STALE')],
        'sample_sufficiency':'INSUFFICIENT_OR_NOT_ESTABLISHED', 'quantitative_support':'NO_SUPPORTED_EDGE_ESTABLISHED',
        'rejected_claims':rejected,'budgets_respected':all(getattr(mission.usage,key)<=getattr(mission.budgets,'max_'+key) for key in
            ('tool_calls','planner_iterations','replans','quant_runs','historical_comparisons','model_calls')),
        'api_cost_inr':0,'probability_score':None,'adversarial_review':'Check stale data, incompatible scopes, source conflicts, negative OOS and untested alternative explanations',
        'answered_with_limits':bool(records) and not missing,'causality':'NOT_ESTABLISHED'}
    nodes=[]; edges=[]
    for s in mission.plan.steps:
        if not s.output: continue
        tool_node='step:'+s.step_id
        nodes.append({'id':tool_node,'type':'tool','tool_id':s.tool_id,'output_hash':s.output.output_hash})
        for e in s.output.evidence:
            nodes.append({'id':e.evidence_id,'type':'evidence','source_id':e.source_id,'observation_id':str(e.observation_id) if e.observation_id else None,
                          'manifest_id':str(e.manifest_id),'source_manifest_id':str(e.source_manifest_id) if e.source_manifest_id else None,'as_of':e.as_of.isoformat()})
            edges.append({'from':e.evidence_id,'to':tool_node,'relation':'produced_by'})
            artifact='artifact:'+str(e.source_id or e.evidence_id)
            nodes.append({'id':artifact,'type':'feature_context_backtest','kind':e.kind,'source_id':e.source_id,'version':e.version})
            edges.append({'from':tool_node,'to':artifact,'relation':'reads_or_calculates'})
            for value,kind in ((e.source_manifest_id or e.manifest_id,'manifest'),(e.observation_id or e.source_id,'observation_source')):
                if value:
                    key=kind+':'+str(value)
                    nodes.append({'id':key,'type':kind})
                    edges.append({'from':e.evidence_id,'to':key,'relation':'derived_from'})
                    edges.append({'from':artifact if kind=='manifest' else 'manifest:'+str(e.source_manifest_id or e.manifest_id),'to':key,'relation':'references'})
    for c in accepted:
        nodes.append({'id':c.claim_id,'type':'claim'})
        edges.extend({'from':c.claim_id,'to':key,'relation':'supported_by'} for key in c.evidence_ids)
    return accepted,[hypothesis,*alternatives],skeptic,quality,{'nodes':list({n['id']:n for n in nodes}.values()),'edges':edges}


def render_report(mission):
    def lines(claims): return [f'- {c.text} '+ ' '.join('['+key+']' for key in c.evidence_ids) for c in claims]
    indexed={e.evidence_id:e for e in evidence(mission)}
    def from_tools(tools,kinds=None):
        return [c for c in mission.claims if c.stance!='counter' and any(indexed[key].tool_id in tools and (kinds is None or indexed[key].kind in kinds) for key in c.evidence_ids)]
    rows=['# Research Mission',mission.request.goal,'','## Scope',
        f'{mission.request.mode} · {mission.request.universe} (selected Pilot 5; narrow universe) · {mission.request.horizon_days} day research horizon',
        f'Market manifest {mission.context.manifest_id if mission.context else "UNAVAILABLE"}; cutoff {mission.context.as_of.isoformat() if mission.context else mission.request.as_of}; context manifest {mission.context.context_manifest_id if mission.context else "UNAVAILABLE"}',
        '', '## Findings']
    rows+=lines(from_tools({'instrument.features','market.state'})[:24]) or ['- No sufficiently grounded canonical market finding.']
    support={key for h in mission.hypotheses for key in h.support}
    rows+=['','## Supporting Evidence']+lines([c for c in mission.claims if c.numeric_evidence_id in support])
    rows+=['','## Contextual Evidence']+lines(from_tools({'intelligence.context','intelligence.options','intelligence.events','intelligence.news','intelligence.onchain','intelligence.fundamentals'},
        {'context_calculation','context_limit','context_event_risk'})[:30])
    rows+=['','## Opportunity / Thesis Challenge']+lines(from_tools({'opportunity.candidate','opportunity.thesis','mission.challenge_candidate'})[:15])
    rows+=['','## Changes Between Pinned States']+lines(from_tools({'mission.compare_states'})[:24])
    rows+=['','## Historical and Quant Evidence']+lines([c for c in mission.claims if 'OOS' in c.text or c.text.startswith(('Quant','Earlier mission'))])
    rows+=['','## Contradictions / Skeptic']+lines(mission.contradictions)
    rows+=['','## Alternative Explanations']+[f'- {h.statement} Status: {h.status}. Missing tests: '+', '.join(h.test_requirements)+'. '+ ' '.join('['+key+']' for key in h.originating_evidence) for h in mission.hypotheses]
    rows+=['','## Limitations and Unknowns']+lines(mission.limitations)
    rows+=['','## Conclusion','INCONCLUSIVE / NO SUPPORTED EDGE. Current descriptive evidence does not establish future profitability; missing or stale evidence remains unknown.',
        '', '## Suggested Next Research','Collect recorded context and prospective outcomes; predeclare evaluation before any experiment. No strategy, thesis, risk or Edge Library rule was changed.',
        '', '## Provenance',f'Orchestration {mission.orchestration_version}; implementation {mission.code_hash}; approved tool outputs and citations are inspectable in the evidence graph.']
    return '\n'.join(rows)
