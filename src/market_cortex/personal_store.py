"""Append-only personal records; all retrieval uses knowledge recording time."""
from datetime import datetime, timezone
from uuid import uuid4
from psycopg.types.json import Jsonb
from psycopg.conninfo import conninfo_to_dict
from .database import connect
from .intelligence_store import digest
from .personal_contracts import PersonalMemory, AdaptationProposal, PersonalizationSnapshot


def now(): return datetime.now(timezone.utc)


class PersonalStore:
    def __init__(self,dsn,environment): self.dsn,self.environment=dsn,environment
    @property
    def owner_ready(self):
        return self.environment=='OWNER_MAIN' and not conninfo_to_dict(self.dsn).get('dbname','').lower().endswith('_test')
    def guard(self,audience,*,write=False):
        test=conninfo_to_dict(self.dsn).get('dbname','').lower().endswith('_test')
        if audience=='SYNTHETIC_VALIDATION' and not (self.environment=='PILOT_TEST' and test): raise ValueError('SYNTHETIC_PERSONALIZATION_REQUIRES_TEST_DATABASE')
        if audience=='OWNER_RESEARCH' and write and not self.owner_ready: raise ValueError('OWNER_PERSONALIZATION_REQUIRES_OWNER_MAIN')
    def append(self,kind,audience,key,payload,expected=None):
        self.guard(audience,write=True)
        with connect(self.dsn) as c:
            c.execute('SELECT pg_advisory_xact_lock(%s)',(837241915,))
            row=c.execute('SELECT record_id,current_version FROM personal_records WHERE kind=%s AND audience=%s AND dedup_key=%s FOR UPDATE',(kind,audience,key)).fetchone()
            if expected is not None and (not row or row[1]!=expected): raise ValueError('PERSONAL_VERSION_CONFLICT')
            from uuid import UUID
            proposed_id=payload.get('item',{}).get('memory_id' if kind=='MEMORY' else 'proposal_id')
            record_id,version=(row[0],row[1]+1) if row else (UUID(str(proposed_id)) if proposed_id else uuid4(),1)
            if row:
                old=c.execute('SELECT payload FROM personal_record_versions WHERE record_id=%s AND version=%s',row).fetchone()[0]
                if old==payload: return self.get(record_id)
            else: c.execute('INSERT INTO personal_records(record_id,kind,audience,dedup_key,current_version) VALUES (%s,%s,%s,%s,1)',(record_id,kind,audience,key))
            payload={**payload,'record_id':str(record_id),'version':version,'recorded_at':now().isoformat()}
            c.execute('INSERT INTO personal_record_versions(record_id,version,content_hash,payload) VALUES (%s,%s,%s,%s)',(record_id,version,digest(payload),Jsonb(payload)))
            c.execute('UPDATE personal_records SET current_version=%s WHERE record_id=%s',(version,record_id))
        return payload
    def get(self,key,as_of=None,version=None):
        with connect(self.dsn) as c:
            row=c.execute('SELECT r.kind,r.audience,p.payload,p.content_hash FROM personal_records r JOIN LATERAL (SELECT payload,content_hash FROM personal_record_versions WHERE record_id=r.record_id AND recorded_at<=%s AND (%s::integer IS NULL OR version=%s) ORDER BY version DESC LIMIT 1) p ON true WHERE r.record_id=%s',(as_of or now(),version,version,key)).fetchone()
        if not row: raise LookupError('PERSONAL_RECORD_NOT_KNOWN')
        if digest(row[2])!=row[3]: raise ValueError('PERSONAL_RECORD_HASH_MISMATCH')
        return {**row[2],'kind':row[0],'audience':row[1]}
    def list(self,kind,audience,as_of):
        self.guard(audience)
        with connect(self.dsn) as c:
            rows=c.execute('SELECT p.payload,p.content_hash FROM personal_records r JOIN LATERAL (SELECT payload,content_hash FROM personal_record_versions WHERE record_id=r.record_id AND recorded_at<=%s ORDER BY version DESC LIMIT 1) p ON true WHERE r.kind=%s AND r.audience=%s ORDER BY r.created_at,r.record_id',(as_of,kind,audience)).fetchall()
        for payload,h in rows:
            if digest(payload)!=h: raise ValueError('PERSONAL_RECORD_HASH_MISMATCH')
        return [p for p,h in rows]
    def history(self,key):
        self.get(key)
        with connect(self.dsn) as c: rows=c.execute('SELECT version,recorded_at,content_hash,payload FROM personal_record_versions WHERE record_id=%s ORDER BY version',(key,)).fetchall()
        return [{'version':v,'recorded_at':t.isoformat(),'content_hash':h,'payload':p} for v,t,h,p in rows]
    def save_snapshot(self,snapshot):
        # Empty owner previews in a test environment remain explicitly OWNER snapshots
        # with no owner records; they cannot activate preferences or inferred memory.
        self.guard(snapshot.audience)
        if snapshot.audience=='OWNER_RESEARCH' and not self.owner_ready and any(e.classification=='OWNER_RESEARCH' for e in snapshot.evidence): raise ValueError('OWNER_EVIDENCE_ENVIRONMENT_MISMATCH')
        snapshot=snapshot.model_copy(update={'content_hash':digest(snapshot.model_dump(mode='json',exclude={'content_hash'}))})
        with connect(self.dsn) as c:
            c.execute('INSERT INTO personalization_snapshots(snapshot_id,audience,as_of,content_hash,payload) VALUES (%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING',(snapshot.snapshot_id,snapshot.audience,snapshot.as_of,snapshot.content_hash,Jsonb(snapshot.model_dump(mode='json'))))
        return self.snapshot(snapshot.snapshot_id)
    def snapshot(self,key,known_at=None):
        with connect(self.dsn) as c: row=c.execute('SELECT payload,content_hash FROM personalization_snapshots WHERE snapshot_id=%s AND (%s::timestamptz IS NULL OR recorded_at<=%s)',(key,known_at,known_at)).fetchone()
        if not row: raise LookupError('PERSONAL_SNAPSHOT_NOT_KNOWN')
        m=PersonalizationSnapshot.model_validate(row[0])
        if digest(m.model_dump(mode='json',exclude={'content_hash'}))!=row[1] or m.content_hash!=row[1]: raise ValueError('PERSONAL_SNAPSHOT_HASH_MISMATCH')
        return m
    @staticmethod
    def memory(row): return PersonalMemory.model_validate({**row['item'],'memory_id':row['record_id'],'version':row['version'],'persisted':True})
    @staticmethod
    def proposal(row): return AdaptationProposal.model_validate({**row['item'],'proposal_id':row['record_id'],'version':row['version'],'recorded_at':row['recorded_at']})
