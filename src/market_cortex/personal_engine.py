"""Transparent descriptive patterns. Counts describe records, never personality or edge."""
from collections import Counter
from datetime import timedelta
from statistics import median
from uuid import NAMESPACE_URL, uuid5
from .intelligence_store import digest
from .personal_contracts import PersonalMemory, PersonalizationSnapshot

ALGORITHM_VERSION='personal_patterns_v1'
MIN_REPEATED=3
MIN_STRONG=10
RECENCY_DAYS=90


def sufficiency(n):
    return 'INSUFFICIENT_HISTORY' if n==0 else 'EARLY_PATTERN' if n<MIN_REPEATED else 'REPEATED_PATTERN' if n<MIN_STRONG else 'STRONG_PATTERN'


def usable(memory,as_of):
    return memory.status in ('ACTIVE','OWNER_CONFIRMED') and (memory.expires_at is None or memory.expires_at>as_of)


def build_snapshot(evidence,controls,proposals,audience,as_of,code_hash,excluded=None):
    visible=[e for e in evidence if e.recorded_at<=as_of and e.source_as_of<=as_of and e.classification in (audience,'STRATEGY_EVIDENCE')]
    # One entity/revision is one research instance, not repeated checkpoint counts.
    unique={}
    for e in visible:
        unit=(e.source_kind,e.facts.get('research_unit',str(e.source_id)))
        if unit not in unique or (e.source_version,e.recorded_at)>(unique[unit].source_version,unique[unit].recorded_at): unique[unit]=e
    visible=sorted(unique.values(),key=lambda e:(e.recorded_at,e.evidence_id))
    behavior=[e for e in visible if e.classification==audience and e.source_kind not in ('preference','feedback')]
    recent=[e for e in behavior if e.recorded_at>=as_of-timedelta(days=RECENCY_DAYS)]
    old=[e for e in behavior if e not in recent]
    missions=[e for e in recent if e.source_kind=='mission']
    theses=[e for e in recent if e.source_kind=='thesis']
    journals=[e for e in recent if e.source_kind=='journal']
    predictions=[e for e in recent if e.source_kind=='prediction']
    patterns=[]; memories=[]; coaching=[]
    def pattern(key,title,rows,eligible,*,subject='OWNER_PROCESS',kind='FAILURE',value=None):
        ids=[e.evidence_id for e in rows]; n=len(rows)
        if not n: return
        recent_half=eligible[-10:]; prior=eligible[:-10] if len(eligible)>10 else []
        count=lambda seq:sum(e in rows for e in seq)
        before=count(prior)/len(prior) if prior else None
        after=count(recent_half)/len(recent_half) if recent_half else None
        improving=bool(len(prior)>=3 and len(recent_half)>=3 and (after>before if kind=='PROCEDURAL' else after<before))
        p={'key':key,'statement':title,'sample_N':n,'eligible_N':len(eligible),'sufficiency':sufficiency(n),
           'evidence_ids':ids,'subject':subject,'current_window_days':RECENCY_DAYS,
           'prior_window_N':len(prior),'recent_window_N':len(recent_half),'prior_matching_N':count(prior),'recent_matching_N':count(recent_half),
           'change':'IMPROVING' if improving else 'INSUFFICIENT_COMPARABLE_WINDOWS' if not prior else 'NO_IMPROVEMENT_ESTABLISHED'}
        patterns.append(p)
        memory=PersonalMemory(memory_id=uuid5(NAMESPACE_URL,f'personal:{audience}:{key}'),key=key,memory_type=kind,
            source_type='LEARNED_FROM_OUTCOMES' if key.startswith('outcome:') else 'OBSERVED',audience=audience,algorithm_version=ALGORITHM_VERSION,
            statement=title,value=value,evidence_ids=ids,sample_N=n,sufficiency=sufficiency(n),subject=subject,
            created_at=min(e.recorded_at for e in rows),last_validated=as_of,expires_at=as_of+timedelta(days=RECENCY_DAYS))
        override=next((m for m in sorted(controls,key=lambda m:(m.source_type!='EXPLICIT',-m.last_validated.timestamp())) if m.key==key and (m.owner_override or m.source_type=='EXPLICIT')),None)
        if override: memory=override
        else:
            saved=next((m for m in controls if m.key==key and m.evidence_ids==ids and m.algorithm_version==memory.algorithm_version),None)
            if saved: memory=saved
        memories.append(memory)
        if n>=MIN_REPEATED and memory.status not in ('DISABLED','REJECTED','SUPERSEDED','EXPIRED') and (memory.expires_at is None or memory.expires_at>as_of) and memory.owner_override not in ('CORRECTED','REJECTED','DISABLED','RETIRED') and not improving:
            coaching.append({'key':key,'subject':subject,'message':title,'sample_N':n,'eligible_N':len(eligible),'evidence_ids':ids,'memory_id':str(memory.memory_id)})
    failures=sorted({e.facts.get('failure_category') for e in journals if e.facts.get('failure_category')})
    for failure in failures:
        rows=[e for e in journals if e.facts.get('failure_category')==failure]
        pattern('failure:'+failure,'Owner-recorded review/lesson category: '+failure.replace('_',' ')+'. These are research observations, not a permanent owner trait.',rows,journals)
    pattern('strength:invalidation','The cited recorded theses include explicit invalidation conditions.',[e for e in theses if e.facts.get('invalidation_defined')],theses,kind='PROCEDURAL')
    pattern('failure:invalidation_undefined','Recorded theses lack explicit invalidation conditions; review invalidation before relying on the thesis.',[e for e in theses if not e.facts.get('invalidation_defined')],theses)
    pattern('strength:contradiction_recorded','Recorded theses include opposing evidence.',[e for e in theses if e.facts.get('counter_evidence_recorded')],theses,kind='PROCEDURAL')
    pattern('strength:post_review','Canonical owner journal contains completed review records.',[e for e in journals if e.facts.get('review_complete')],journals,kind='PROCEDURAL')
    for key,label,fn in (
        ('quant_ignored','CORTEX investigations omitted planned Quant evidence.',lambda f:f.get('quant_expected') and not f.get('quant_reviewed')),
        ('context_ignored','CORTEX investigations omitted planned contextual evidence.',lambda f:f.get('context_expected') and not f.get('context_reviewed')),
        ('tool_failure','CORTEX investigations contain failed approved tools.',lambda f:f.get('tool_failure')),
        ('overstated_conclusion','CORTEX grounding caught rejected claims; inspect the rejected claims rather than assuming a factual error.',lambda f:f.get('rejected_claim_N',0)>0),
        ('data_staleness','CORTEX investigations used explicitly stale evidence; this does not establish that the owner ignored it.',lambda f:'stale' in f.get('freshness',[]))):
        eligible=[e for e in missions if e.facts.get('status') in ('COMPLETED','INCONCLUSIVE','PARTIAL','FAILED')]
        pattern('cortex:'+key,label,[e for e in eligible if fn(e.facts)],eligible,subject='CORTEX_PROCESS')
    risk=[e for e in recent if e.source_kind=='risk']
    pattern('risk:missing_invalidation','Research portfolio snapshots contain unknown risk/invalidation. No real trading behavior is inferred.',[e for e in risk if e.facts.get('missing_invalidation')],risk)
    pattern('risk:correlation','Research portfolio snapshots contain canonical correlation warnings. No real trading behavior is inferred.',[e for e in risk if e.facts.get('correlation_warning')],risk)
    for strategy in sorted({e.strategy for e in predictions if e.strategy}):
        decided=[e for e in predictions if e.strategy==strategy and e.facts.get('outcome_status') in ('CONFIRMED','INVALIDATED') and e.facts.get('registration')=='PRE_REGISTERED']
        pattern('outcome:'+strategy,'Pre-registered '+strategy+' expectations have recorded invalidations; owner-process outcomes do not establish strategy edge.',[e for e in decided if e.facts['outcome_status']=='INVALIDATED'],decided,kind='PREDICTION')
    sequences={tuple(e.facts.get('tool_sequence',[])) for e in missions if e.facts.get('tool_sequence')}
    for sequence in sorted(sequences):
        rows=[e for e in missions if tuple(e.facts.get('tool_sequence',[]))==sequence]
        pattern('routine:'+digest(sequence)[:12],'Observed approved research sequence: '+', '.join(sequence)+'. No unrecorded clicks or intent are inferred.',rows,missions,kind='PROCEDURAL')
    for key,fld in (('preferred_instrument','symbol'),('default_mode','mode'),('default_horizon','horizon')):
        candidates=[e for e in missions if (getattr(e,'symbol') if fld=='symbol' else e.facts.get(fld)) is not None]
        frequencies=Counter(getattr(e,'symbol') if fld=='symbol' else e.facts[fld] for e in candidates)
        if frequencies:
            value=sorted(frequencies,key=lambda x:(-frequencies[x],str(x)))[0]
            rows=[e for e in candidates if (e.symbol if fld=='symbol' else e.facts[fld])==value]
            pattern(key,'Observed research usage: '+key.replace('_',' ')+' = '+str(value)+'. This is an observed pattern, not an explicit preference.',rows,candidates,kind='SEMANTIC',value=value)
    # Explicit owner controls are never replaced by fresh inference.
    by_key={m.key:m for m in memories}
    for m in sorted(controls,key=lambda m:(m.source_type=='EXPLICIT',m.last_validated)):
        if m.source_type=='EXPLICIT' or m.owner_override: by_key[m.key]=m
        elif m.key not in by_key:
            by_key[m.key]=m.model_copy(update={'status':'EXPIRED' if m.expires_at and m.expires_at<=as_of else m.status})
    for e in visible:
        if e.source_kind not in ('mission','research','prediction','quant'): continue
        kind='STRATEGY' if e.source_kind=='quant' else 'PREDICTION' if e.source_kind=='prediction' else 'WORKING' if e.facts.get('status') in ('READY','RUNNING','PLANNING') else 'EPISODIC'
        key='record:'+e.source_kind+':'+str(e.source_id)
        if key in by_key and by_key[key].owner_override: continue
        by_key[key]=PersonalMemory(memory_id=uuid5(NAMESPACE_URL,f'personal:{audience}:{key}'),key=key,memory_type=kind,
            source_type='LEARNED_FROM_OUTCOMES' if kind in ('STRATEGY','PREDICTION') else 'OBSERVED',audience=audience,
            status='ACTIVE',statement='Canonical '+e.source_kind+' record; inspect source facts and original knowledge time. It is not a stable owner habit.',
            evidence_ids=[e.evidence_id],sample_N=1,sufficiency='EARLY_PATTERN',subject=e.subject,
            created_at=e.recorded_at,last_validated=as_of,expires_at=as_of+timedelta(days=RECENCY_DAYS))
        saved=next((m for m in controls if m.key==key and m.evidence_ids==[e.evidence_id]),None)
        if saved: by_key[key]=saved
        if e.source_kind=='mission':
            market_key='market:'+str(e.source_id)
            by_key[market_key]=by_key[key].model_copy(update={'memory_id':uuid5(NAMESPACE_URL,f'personal:{audience}:{market_key}'),'key':market_key,
                'memory_type':'MARKET','statement':'Historical scope and evidence of the recorded market investigation; current market truth requires fresh canonical evidence.'})
    memories=[m.model_copy(update={'status':'EXPIRED'}) if m.expires_at and m.expires_at<=as_of and m.status in ('ACTIVE','TENTATIVE','OWNER_CONFIRMED') else m for m in by_key.values()]
    strategies=[]
    for e in visible:
        if e.subject!='STRATEGY_EVIDENCE': continue
        strategies.append({'strategy':e.strategy,'oos_return':e.facts.get('oos_return'),'N':e.facts.get('N'),
            'owner_usage_N':sum(r.strategy==e.strategy for r in behavior),'behavior_fit':'INSUFFICIENT_HISTORY',
            'edge_status':'NO_SUPPORTED_EDGE_ESTABLISHED','evidence_ids':[e.evidence_id],'limitations':e.facts.get('limitation')})
        if type(e.facts.get('oos_return')) in (int,float) and e.facts['oos_return']<=0:
            coaching.append({'key':'strategy:'+str(e.strategy),'subject':'STRATEGY_EVIDENCE',
                'message':f"Saved {e.strategy} temporal OOS return is {e.facts['oos_return']*100:.2f}% (N={e.facts.get('N')}). Review this counter-evidence; personal preference does not establish an edge.",
                'sample_N':e.facts.get('N'),'evidence_ids':[e.evidence_id]})
    for strategy in sorted({e.strategy for e in behavior if e.strategy}):
        if any(s['strategy']==strategy for s in strategies): continue
        rows=[e for e in behavior if e.strategy==strategy]
        strategies.append({'strategy':strategy,'owner_usage_N':len(rows),'N':None,'oos_return':None,'behavior_fit':'NOT_ESTABLISHED',
            'edge_status':'NO_SUPPORTED_EDGE_ESTABLISHED','evidence_ids':[e.evidence_id for e in rows],'limitations':'Usage frequency is not evidence of owner suitability or profitability.'})
    feedback=[e for e in visible if e.source_kind=='feedback']
    feedback_groups={}
    for e in feedback:
        feedback_groups.setdefault((e.facts['target_kind'],e.facts['target_id'],e.facts['rating']),[]).append(e)
    for (kind,target,rating),rows in feedback_groups.items():
        if len(rows)>=3 and rating in ('INCORRECT','IRRELEVANT','NEEDS_EVIDENCE'):
            coaching.append({'key':'feedback:'+str(target),'subject':'OWNER_PROCESS','message':'Repeated owner feedback requests a review of this local '+kind.lower()+'. No memory or workflow was silently changed.',
                'sample_N':len(rows),'evidence_ids':[e.evidence_id for e in rows]})
    count_dim=lambda rows,key:{'eligible_N':len(rows),'complete_N':sum(bool(e.facts.get(key)) for e in rows),'evidence_ids':[e.evidence_id for e in rows]}
    baseline={'thesis_invalidation':count_dim(theses,'invalidation_defined'),'thesis_counter_evidence':count_dim(theses,'counter_evidence_recorded'),
        'thesis_risk':count_dim(theses,'risk_recorded'),'mission_quant':count_dim(missions,'quant_reviewed'),
        'mission_context':count_dim(missions,'context_reviewed'),'historical_comparison':count_dim(missions,'historical_reviewed'),
        'journal_review':count_dim(journals,'review_complete'),'probability_score':None}
    review=[]
    for e in recent:
        if e.source_kind=='prediction' and e.facts.get('status') in ('OPEN','PENDING_EVALUATION'):
            due=e.facts.get('due_at'); is_due=bool(due and __import__('datetime').datetime.fromisoformat(due.replace('Z','+00:00'))<=as_of)
            review.append({'priority':1 if is_due else 4,'reason':'PREDICTION_DUE' if is_due else 'PREDICTION_PENDING','source_id':str(e.source_id),'evidence_ids':[e.evidence_id]})
        elif e.source_kind=='mission' and e.facts.get('status') in ('PARTIAL','FAILED','WAITING_FOR_DATA'):
            review.append({'priority':2,'reason':'UNRESOLVED_RESEARCH','source_id':str(e.source_id),'evidence_ids':[e.evidence_id]})
        elif e.source_kind=='thesis' and e.facts.get('status') in ('INVALIDATED','EVENT_RISK'):
            review.append({'priority':1,'reason':'RECORDED_THESIS_STATUS','source_id':str(e.source_id),'evidence_ids':[e.evidence_id]})
        elif e.source_kind=='risk' and (e.facts.get('missing_invalidation') or e.facts.get('correlation_warning')):
            review.append({'priority':2,'reason':'RESEARCH_RISK_WARNING','source_id':str(e.source_id),'evidence_ids':[e.evidence_id]})
    study=[{'question':'Which recorded evidence challenges this research conclusion?','source_id':str(e.source_id),'evidence_ids':[e.evidence_id],
        'answer_basis':e.facts} for e in recent if e.facts.get('failure_category') or e.facts.get('outcome_status')=='INVALIDATED' or e.facts.get('status') in ('INVALIDATED','FAILED')][:20]
    horizons=[e.facts['horizon'] for e in missions if type(e.facts.get('horizon')) is int]
    observed={'genuine_owner_record_N':len(behavior) if audience=='OWNER_RESEARCH' else 0,'validation_record_N':len(behavior) if audience=='SYNTHETIC_VALIDATION' else 0,
        'recent_record_N':len(recent),'historical_record_N':len(old),'history_state':sufficiency(len(behavior)),
        'source_counts':dict(Counter(e.source_kind for e in behavior)),'instrument_frequency':dict(Counter(e.symbol for e in missions if e.symbol)),
        'mode_frequency':dict(Counter(e.facts['mode'] for e in missions if e.facts.get('mode'))),'strategy_frequency':dict(Counter(e.strategy for e in behavior if e.strategy)),
        'feedback_counts':dict(Counter(e.facts['rating'] for e in feedback)),
        'median_horizon':median(horizons) if horizons else None,'excluded_sources':excluded or {},
        'repeat_threshold':MIN_REPEATED,'strong_threshold':MIN_STRONG,'recency_days':RECENCY_DAYS}
    limitations=['DESCRIPTIVE_RESEARCH_BEHAVIOR_NOT_CAUSAL_OR_PROFITABILITY','NO_PSYCHOLOGICAL_PROFILING','NO_REAL_TRADING_INFERENCE',
        'UNKNOWN_VIEW_AND_TOOL_CLICK_HISTORY_NOT_INFERRED','EVENT_PROXIMITY_REQUIRES_VERIFIED_EVENT_EVIDENCE','OVERLAPPING_RECORDS_AND_OUTCOMES_MAY_BE_DEPENDENT']
    if len(behavior)<3: limitations.append('INSUFFICIENT_OWNER_HISTORY_FOR_RECURRING_HABITS')
    data=dict(audience=audience,as_of=as_of,algorithm_version=ALGORITHM_VERSION,implementation_hash=code_hash,evidence=visible,memories=memories,proposals=proposals,
        observed_behavior=observed,baseline=baseline,patterns=patterns,coaching=coaching,strategy_evidence=strategies,
        review_queue=sorted(review,key=lambda r:(r['priority'],r['source_id'])),study_items=study,limitations=limitations)
    key=uuid5(NAMESPACE_URL,'personal-snapshot:'+digest({k:([x.model_dump(mode='json') for x in v] if isinstance(v,list) and v and hasattr(v[0],'model_dump') else v) for k,v in data.items()}))
    return PersonalizationSnapshot(snapshot_id=key,**data)
