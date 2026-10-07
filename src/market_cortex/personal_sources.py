"""Canonical evidence normalization. Free text never creates behavioral facts."""
from datetime import datetime
from uuid import UUID
from .database import connect
from .intelligence_store import digest
from .personal_contracts import PersonalEvidence
from .personal_store import now
from .quant_store import QuantStore


def timestamp(value): return datetime.fromisoformat(value.replace('Z','+00:00')) if isinstance(value,str) else value


class PersonalSources:
    def __init__(self,store): self.store=store
    def record(self,kind,key,version,as_of):
        queries={
            'journal':('SELECT payload,recorded_at FROM journal_revisions WHERE entry_id=%s AND revision=%s AND recorded_at<=%s',),
            'mission':('SELECT payload,recorded_at FROM research_mission_checkpoints WHERE mission_id=%s AND revision=%s AND recorded_at<=%s',),
            'thesis':('SELECT payload,recorded_at FROM research_thesis_versions WHERE thesis_id=%s AND version=%s AND recorded_at<=%s',),
            'risk':('SELECT payload,recorded_at FROM portfolio_risk_snapshots WHERE snapshot_id=%s AND portfolio_version=%s AND recorded_at<=%s',),
            'research':('SELECT payload,created_at FROM cortex_research_runs WHERE run_id=%s AND 1=%s AND created_at<=%s',)}
        if kind not in queries: raise ValueError('UNTRUSTED_PERSONAL_SOURCE')
        with connect(self.store.dsn) as c: row=c.execute(queries[kind][0],(key,version,as_of)).fetchone()
        if not row: raise LookupError('PERSONAL_SOURCE_NOT_KNOWN')
        return row
    @staticmethod
    def normalize(kind,key,version,payload,recorded,audience):
        symbol=payload.get('symbol'); strategy=payload.get('detector_id'); subject='OWNER_PROCESS'
        source_at=payload.get('as_of') or payload.get('context',{}).get('as_of') or recorded
        facts={}
        if kind=='journal':
            if payload.get('classification')=='SYNTHETIC_TEST' and audience=='OWNER_RESEARCH': raise ValueError('SYNTHETIC_SOURCE_EXCLUDED')
            facts={'category':payload['category'],'failure_category':payload.get('failure_category'),'review_complete':payload['category'] in ('review','outcome_review')}
        elif kind=='prediction':
            facts={k:payload.get(k) for k in ('horizon_sessions','status','registration','due_at','evidence_strength')}
            facts.update(payload.get('_evaluation',{})); strategy=payload.get('detector_id')
        elif kind=='thesis':
            candidate=payload.get('candidate',{})
            if candidate.get('data_environment')=='PILOT_TEST' and audience=='OWNER_RESEARCH': raise ValueError('SYNTHETIC_SOURCE_EXCLUDED')
            facts={'status':payload['status'],'invalidation_defined':bool(payload.get('invalidation_conditions')),
                'counter_evidence_recorded':bool(payload.get('opposing_evidence_ids')),'risk_recorded':bool(payload.get('risk_factors'))}
        elif kind=='risk':
            if payload.get('portfolio_classification')!='OWNER_RESEARCH' and audience=='OWNER_RESEARCH': raise ValueError('SYNTHETIC_SOURCE_EXCLUDED')
            if any(p.get('source_type')=='synthetic_fixture' for p in payload.get('positions',[])): raise ValueError('SYNTHETIC_SOURCE_EXCLUDED')
            facts={'missing_invalidation':bool(payload.get('unknown_risk_position_ids')),'correlation_warning':bool(payload.get('correlation_cluster_flags')),
                'research_unit':str(payload.get('portfolio_id'))+':'+str(payload.get('portfolio_version')),'real_trading_inference':False}
        elif kind=='mission':
            context=payload.get('context') or {}
            if audience=='OWNER_RESEARCH' and context.get('environment')!='OWNER_MAIN': raise ValueError('MISSION_ORIGIN_NOT_OWNER_MAIN')
            request=payload['request']; symbol=request.get('symbol'); strategy=request.get('strategy_id')
            steps=payload.get('plan',{}).get('steps',[]); done=[s for s in steps if s.get('status')=='DONE']
            facts={'mode':request['mode'],'horizon':request['horizon_days'],'status':payload['status'],
                'tool_sequence':[s['tool_id'] for s in done],
                'quant_expected':any(s['domain']=='quant' for s in steps),'context_expected':any(s['domain']=='intelligence' for s in steps),
                'quant_reviewed':any(s['domain']=='quant' for s in done),'context_reviewed':any(s['domain']=='intelligence' for s in done),
                'historical_reviewed':any(s.get('scope')=='previous' for s in done),
                'contradictions_recorded':bool(payload.get('contradictions')),'rejected_claim_N':len(payload.get('evaluator',{}).get('rejected_claims',[])),
                'tool_failure':any(s.get('status')=='FAILED' for s in steps),
                'freshness':payload.get('evaluator',{}).get('freshness',[])}
        elif kind=='research':
            context=payload.get('context',{})
            if audience=='OWNER_RESEARCH' and context.get('environment')!='OWNER_MAIN': raise ValueError('RESEARCH_ORIGIN_NOT_OWNER_MAIN')
            symbol=context.get('symbol'); facts={'status':'FAILED' if payload.get('failure_state') else 'RECORDED','rejected_claim_N':len(payload.get('rejected_claims',[]))}
        return PersonalEvidence(evidence_id=digest({'kind':kind,'key':str(key),'version':version,'hash':digest(payload)})[:24],
            source_kind=kind,source_id=key,source_version=version,recorded_at=recorded,source_as_of=timestamp(source_at),
            classification=audience,content_hash=digest(payload),subject=subject,symbol=symbol,strategy=strategy,facts=facts)
    def collect(self,audience,as_of):
        self.store.guard(audience); records=[]; excluded={}; eligible=self.store.owner_ready or audience=='SYNTHETIC_VALIDATION'
        # Imported/old missions/theses are not implicitly genuine owner actions.
        attestations=self.store.list('ATTESTATION',audience,as_of) if eligible else []
        latest={}
        for a in attestations:
            k=(a['source_kind'],a['source_id']); latest[k]=a
        for (kind,key),a in latest.items():
            try:
                payload,recorded=self.record(kind,UUID(key),a['source_version'],as_of)
                version=a['source_version']
                if kind in ('mission','thesis'):
                    table,column,id_column=('research_mission_checkpoints','revision','mission_id') if kind=='mission' else ('research_thesis_versions','version','thesis_id')
                    with connect(self.store.dsn) as c:
                        # Identifiers come from this fixed two-entry mapping only.
                        row=c.execute(f'SELECT payload,recorded_at,{column} FROM {table} WHERE {id_column}=%s AND {column}>=%s AND recorded_at<=%s ORDER BY {column} DESC LIMIT 1',(UUID(key),version,as_of)).fetchone()
                    if row: payload,recorded,version=row
                e=self.normalize(kind,UUID(key),version,payload,recorded,audience)
                if e.source_as_of<=as_of: records.append(e)
            except (LookupError,ValueError): excluded[kind]=excluded.get(kind,0)+1
        if eligible:
            from .learning_store import LearningStore
            learning=LearningStore(self.store.dsn,self.store.environment)
            for j in learning.journals(as_of=as_of,limit=None):
                wanted='OWNER_RESEARCH' if audience=='OWNER_RESEARCH' else 'SYNTHETIC_TEST'
                if j.classification!=wanted: excluded['journal']=excluded.get('journal',0)+1; continue
                e=self.normalize('journal',j.entry_id,j.revision,j.model_dump(mode='json'),j.recorded_at,audience)
                if e.source_as_of<=as_of: records.append(e)
            for p,ev in learning.performance_records(as_of):
                wanted='OWNER_RESEARCH' if audience=='OWNER_RESEARCH' else 'SYNTHETIC_TEST'
                if p.classification!=wanted: excluded['prediction']=excluded.get('prediction',0)+1; continue
                payload=p.model_dump(mode='json')
                if ev and ev.evaluated_at<=as_of and ev.as_of<=as_of:
                    payload['_evaluation']={'outcome_status':ev.status,'forward_return':str(ev.forward_return) if ev.forward_return is not None else None,
                        'quality':ev.evaluation_quality,'outcome_known_at':ev.evaluated_at.isoformat()}
                elif ev:
                    payload['status']='OPEN'; payload['evaluation_id']=None
                with connect(self.store.dsn) as c:
                    recorded=c.execute('SELECT recorded_at FROM prediction_revisions WHERE prediction_id=%s AND revision=%s AND recorded_at<=%s',(p.prediction_id,p.revision,as_of)).fetchone()[0]
                e=self.normalize('prediction',p.prediction_id,p.revision,payload,max(recorded,ev.evaluated_at) if ev and ev.evaluated_at<=as_of else recorded,audience)
                if e.source_as_of<=as_of: records.append(e)
        else:
            with connect(self.store.dsn) as c:
                excluded['unverified_or_test_catalog_record_N']=c.execute('SELECT (SELECT count(*) FROM journal_entries WHERE created_at<=%s)+(SELECT count(*) FROM prediction_records WHERE created_at<=%s)+(SELECT count(*) FROM research_missions WHERE created_at<=%s)+(SELECT count(*) FROM research_theses WHERE created_at<=%s)+(SELECT count(*) FROM portfolio_risk_snapshots WHERE recorded_at<=%s)',(as_of,as_of,as_of,as_of,as_of)).fetchone()[0]
        # Numeric strategy evidence is useful even when owner history is empty.
        with connect(self.store.dsn) as c:
            studies=c.execute("SELECT artifact_id,created_at,content_hash FROM quant_artifacts WHERE kind='walk_forward' AND created_at<=%s ORDER BY created_at DESC LIMIT 20",(as_of,)).fetchall()
        seen=set()
        for key,at,h in studies:
            item=QuantStore(self.store.dsn).get(key,as_of=as_of)
            d=item.get('definition',{}); strategy=d.get('definition',{}).get('strategy_id') or d.get('base',{}).get('strategy_id') or d.get('strategy_id')
            if not strategy or strategy in seen: continue
            seen.add(strategy); result=item['result']
            records.append(PersonalEvidence(evidence_id=digest({'quant':str(key),'hash':h})[:24],source_kind='quant',source_id=key,source_version=1,
                recorded_at=at,source_as_of=at,classification='STRATEGY_EVIDENCE',content_hash=h,subject='STRATEGY_EVIDENCE',strategy=strategy,
                facts={'oos_return':result.get('oos_total_return_compounded_reset_capital'),'N':result.get('oos_N'),
                    'limitation':'Reset-capital folds; selected survivors and dependent trades; not a continuous portfolio or established edge.'}))
        for p in self.store.list('MEMORY',audience,as_of) if eligible else []:
            item=p['item']
            if item['source_type']=='EXPLICIT':
                records.append(PersonalEvidence(evidence_id='preference:'+p['record_id']+':'+str(p['version']),source_kind='preference',source_id=UUID(p['record_id']),source_version=p['version'],
                    recorded_at=timestamp(p['recorded_at']),source_as_of=timestamp(p['recorded_at']),classification=audience,content_hash=digest(p),subject='OWNER_PROCESS',
                    facts={'key':item['key'],'value':item['value'],'status':item['status']}))
        for f in self.store.list('FEEDBACK',audience,as_of) if eligible else []:
            records.append(PersonalEvidence(evidence_id='feedback:'+f['record_id'],source_kind='feedback',source_id=UUID(f['record_id']),source_version=f['version'],
                recorded_at=timestamp(f['recorded_at']),source_as_of=timestamp(f['recorded_at']),classification=audience,content_hash=digest(f),subject='OWNER_PROCESS',
                facts={k:f[k] for k in ('target_kind','target_id','rating')}))
        return sorted(records,key=lambda e:(e.recorded_at,e.evidence_id)),excluded
