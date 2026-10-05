"""Append-only hashed mission checkpoints with a lease and cancellation boundary."""
from datetime import datetime, timedelta, timezone
from uuid import uuid4
from psycopg.types.json import Jsonb

from .database import connect
from .intelligence_store import digest
from .mission_contracts import ResearchMission, TRANSITIONS


def sealed(mission):
    return mission.model_copy(update={'content_hash':digest(mission.model_dump(mode='json',exclude={'content_hash'}))})


class MissionStore:
    def __init__(self,dsn): self.dsn=dsn
    def create(self,mission,key):
        mission=sealed(mission)
        with connect(self.dsn) as c:
            row=c.execute('INSERT INTO research_missions(mission_id,request_key,created_at,current_revision) VALUES (%s,%s,%s,1) ON CONFLICT(request_key) DO NOTHING RETURNING mission_id',
                (mission.mission_id,key,mission.created_at)).fetchone()
            if row: self._insert(c,mission)
            else: return self.get(c.execute('SELECT mission_id FROM research_missions WHERE request_key=%s',(key,)).fetchone()[0])
        return mission
    @staticmethod
    def _insert(c,mission):
        c.execute('INSERT INTO research_mission_checkpoints VALUES (%s,%s,%s,%s,%s,%s)',
            (mission.mission_id,mission.revision,datetime.now(timezone.utc),mission.status,mission.content_hash,Jsonb(mission.model_dump(mode='json'))))
    def get(self,key,revision=None):
        with connect(self.dsn) as c:
            row=c.execute('SELECT p.payload,p.content_hash FROM research_mission_checkpoints p JOIN research_missions m USING(mission_id) WHERE p.mission_id=%s AND p.revision=COALESCE(%s,m.current_revision)',(key,revision)).fetchone()
        return self._verified(row)
    @staticmethod
    def _verified(row):
        if not row: raise LookupError('MISSION_NOT_FOUND')
        m=ResearchMission.model_validate(row[0])
        if digest(row[0]|{})!=digest(m.model_dump(mode='json')) or sealed(m).content_hash!=row[1] or m.content_hash!=row[1]: raise ValueError('MISSION_HASH_MISMATCH')
        return m
    def get_at(self,key,as_of):
        with connect(self.dsn) as c:
            row=c.execute('SELECT payload,content_hash FROM research_mission_checkpoints WHERE mission_id=%s AND recorded_at<=%s ORDER BY revision DESC LIMIT 1',(key,as_of)).fetchone()
        return self._verified(row)
    def save(self,mission,token=None):
        with connect(self.dsn) as c:
            row=c.execute('SELECT current_revision,cancelled,lease_token,lease_until>now() FROM research_missions WHERE mission_id=%s FOR UPDATE',(mission.mission_id,)).fetchone()
            if not row or row[0]!=mission.revision: raise ValueError('MISSION_CHECKPOINT_CONFLICT')
            if row[1] and mission.status!='CANCELLED': raise ValueError('MISSION_CANCELLED')
            if row[2] is not None and row[2]!=token: raise ValueError('MISSION_ALREADY_RUNNING')
            if row[2] is not None and not row[3]: raise ValueError('MISSION_LEASE_EXPIRED')
            previous=self.get(mission.mission_id)
            if mission.status!=previous.status and mission.status not in TRANSITIONS[previous.status]: raise ValueError('INVALID_MISSION_TRANSITION')
            if mission.context!=previous.context or mission.previous_context!=previous.previous_context or mission.request!=previous.request or mission.budgets!=previous.budgets or mission.frozen_references!=previous.frozen_references or mission.code_hash!=previous.code_hash:
                raise ValueError('IMMUTABLE_MISSION_SCOPE')
            if previous.deadline_at is not None and mission.deadline_at!=previous.deadline_at: raise ValueError('DEADLINE_RESET_FORBIDDEN')
            for field in ('tool_calls','planner_iterations','replans','quant_runs','historical_comparisons','model_calls'):
                if getattr(mission.usage,field)<getattr(previous.usage,field): raise ValueError('BUDGET_RESET_FORBIDDEN')
            result=sealed(mission.model_copy(update={'revision':mission.revision+1,'updated_at':datetime.now(timezone.utc)}))
            self._insert(c,result)
            c.execute('UPDATE research_missions SET current_revision=%s WHERE mission_id=%s',(result.revision,result.mission_id))
        return result
    def acquire(self,key,seconds):
        token=uuid4()
        with connect(self.dsn) as c:
            row=c.execute('UPDATE research_missions SET lease_token=%s,lease_until=%s WHERE mission_id=%s AND NOT cancelled AND (lease_token IS NULL OR lease_until<now()) RETURNING mission_id',
                (token,datetime.now(timezone.utc)+timedelta(seconds=seconds),key)).fetchone()
        if not row: raise ValueError('MISSION_ALREADY_RUNNING_OR_CANCELLED')
        return token
    def release(self,key,token):
        with connect(self.dsn) as c: c.execute('UPDATE research_missions SET lease_token=NULL,lease_until=NULL WHERE mission_id=%s AND lease_token=%s',(key,token))
    def renew(self,key,token,seconds=60):
        with connect(self.dsn) as c:
            return bool(c.execute('UPDATE research_missions SET lease_until=now()+(%s * interval \'1 second\') WHERE mission_id=%s AND lease_token=%s AND lease_until>now() AND NOT cancelled RETURNING mission_id',(seconds,key,token)).fetchone())
    def cancelled(self,key):
        with connect(self.dsn) as c: return c.execute('SELECT cancelled FROM research_missions WHERE mission_id=%s',(key,)).fetchone()[0]
    def cancel(self,key):
        with connect(self.dsn) as c:
            c.execute('SELECT mission_id FROM research_missions WHERE mission_id=%s FOR UPDATE',(key,))
            m=self.get(key)
            if m.status=='CANCELLED' or m.status in ('COMPLETED','INCONCLUSIVE'): return m
            result=sealed(m.model_copy(update={'status':'CANCELLED','termination_reason':'OWNER_CANCELLED','revision':m.revision+1,'updated_at':datetime.now(timezone.utc)}))
            self._insert(c,result)
            c.execute('UPDATE research_missions SET cancelled=true,current_revision=%s WHERE mission_id=%s',(result.revision,key))
        return result
    def recent(self,as_of=None,limit=20):
        with connect(self.dsn) as c:
            rows=c.execute('SELECT p.payload,p.content_hash FROM research_missions m JOIN LATERAL (SELECT payload,content_hash FROM research_mission_checkpoints WHERE mission_id=m.mission_id AND recorded_at<=%s ORDER BY revision DESC LIMIT 1) p ON true ORDER BY m.created_at DESC LIMIT %s',(as_of or datetime.now(timezone.utc),min(50,max(1,limit)))).fetchall()
        return [self._verified(row) for row in rows]
    def history(self,key):
        with connect(self.dsn) as c:
            rows=c.execute('SELECT revision,recorded_at,status,content_hash FROM research_mission_checkpoints WHERE mission_id=%s ORDER BY revision',(key,)).fetchall()
        return [{'revision':r,'recorded_at':at.isoformat(),'status':s,'content_hash':h} for r,at,s,h in rows]
