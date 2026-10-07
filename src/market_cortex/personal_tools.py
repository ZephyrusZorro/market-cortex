"""Small deterministic LOCAL_ONLY personal tool registry; no raw database query."""
TOOLS={
    'personal.profile':'observed_behavior','personal.mistakes':'patterns','personal.strengths':'patterns',
    'personal.strategy_fit':'strategy_evidence','personal.memories':'memories','personal.cortex_failures':'patterns',
    'personal.proposals':'proposals','personal.timeline':'timeline','personal.review':'review_queue'}


def metadata():
    return [{'tool_id':k,'version':'1.0.0','deterministic':True,'access':'READ_ONLY','privacy':'LOCAL_ONLY',
        'historical_support':True,'cost_class':'FREE_LOCAL','side_effects':'none'} for k in TOOLS]


def execute(service,tool,query):
    if tool not in TOOLS: raise ValueError('PERSONAL_TOOL_NOT_ALLOWED')
    snapshot=service.profile(query); field=TOOLS[tool]
    if field=='timeline':
        items=[{'source_kind':e.source_kind,'source_id':str(e.source_id),'version':e.source_version,'recorded_at':e.recorded_at.isoformat(),
            'subject':e.subject,'evidence_ids':[e.evidence_id]} for e in snapshot.evidence]
        items += [{'source_kind':'proposal','source_id':str(p.proposal_id),'version':p.version,'recorded_at':p.recorded_at.isoformat(),'status':p.status} for p in snapshot.proposals]
        items=sorted(items,key=lambda i:(i['recorded_at'],i['source_id']))
    else: items=getattr(snapshot,field)
    if tool=='personal.mistakes': items=[p for p in items if p['subject']=='OWNER_PROCESS' and p['key'].startswith(('failure:','risk:','outcome:'))]
    elif tool=='personal.strengths': items=[p for p in items if p['key'].startswith('strength:')]
    elif tool=='personal.cortex_failures': items=[p for p in items if p['subject']=='CORTEX_PROCESS']
    return {'tool_id':tool,'as_of':snapshot.as_of.isoformat(),'privacy':'LOCAL_ONLY','items':items,
        'sample':snapshot.observed_behavior,'evidence':snapshot.evidence,'limitations':snapshot.limitations}
