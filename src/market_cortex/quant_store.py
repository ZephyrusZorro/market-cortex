"""Immutable content-addressed research artifacts and explicit edge revisions."""
import hashlib
import json
from datetime import datetime, timezone
from uuid import UUID, NAMESPACE_URL, uuid5

from psycopg.types.json import Jsonb

from .database import connect


def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(",",":"),default=str,allow_nan=False).encode()).hexdigest()


class QuantStore:
    def __init__(self,dsn):
        self.dsn=dsn

    def save(self,kind,payload,content_hash=None,artifact_id=None):
        value_hash=content_hash or digest(payload)
        key=artifact_id or uuid5(NAMESPACE_URL,f"quant:{kind}:{value_hash}")
        with connect(self.dsn) as c:
            c.execute("INSERT INTO quant_artifacts VALUES (%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING",
                      (key,kind,value_hash,datetime.now(timezone.utc),Jsonb(payload)))
            row=c.execute("SELECT content_hash,payload FROM quant_artifacts WHERE artifact_id=%s",(key,)).fetchone()
            if row is None or row[0]!=value_hash:
                raise ValueError("IMMUTABLE_QUANT_ID_CONFLICT")
            if kind=="run" and row[1].get("result_hash")!=payload.get("result_hash"):
                raise ValueError("IMMUTABLE_QUANT_RESULT_CONFLICT")
        return key

    def get(self,key,kind=None,as_of=None):
        with connect(self.dsn) as c:
            row=c.execute("SELECT kind,created_at,payload,content_hash FROM quant_artifacts WHERE artifact_id=%s",(key,)).fetchone()
        if row is None or (kind and row[0]!=kind) or (as_of and row[1]>as_of):
            raise LookupError("QUANT_ARTIFACT_NOT_VISIBLE")
        return self.verify(row[2]) if row[0]=="run" else self.verify_content(row[0],row[2],row[3])

    def by_hash(self,kind,value_hash):
        with connect(self.dsn) as c:
            row=c.execute("SELECT payload FROM quant_artifacts WHERE kind=%s AND content_hash=%s",(kind,value_hash)).fetchone()
        return self.verify(row[0]) if row and kind=="run" else self.verify_content(kind,row[0],value_hash) if row else None

    @staticmethod
    def verify_content(kind,payload,content_hash):
        core=payload if kind=="source" else {k:payload[k] for k in ("schema_version","kind","definition","result")}
        if digest(core)!=content_hash:
            raise ValueError("QUANT_CONTENT_HASH_MISMATCH")
        return payload

    @staticmethod
    def verify(payload):
        if digest(payload["definition"])!=payload["manifest"]["definition_hash"]:
            raise ValueError("QUANT_DEFINITION_HASH_MISMATCH")
        fields={"decisions":payload["decisions"],"trades":payload["trades"],"equity":payload["equity"],
                "metrics":payload["metrics"],"drawdown":payload["drawdown"],"controls":payload["controls"],
                "regimes":payload["regime_performance"]}
        if digest(fields)!=payload["result_hash"]:
            raise ValueError("QUANT_RESULT_HASH_MISMATCH")
        return payload

    def recent(self,kind="run",as_of=None):
        with connect(self.dsn) as c:
            rows=c.execute("SELECT artifact_id,created_at,payload FROM quant_artifacts WHERE kind=%s AND created_at<=%s ORDER BY created_at DESC LIMIT 50",
                           (kind,as_of or datetime.now(timezone.utc))).fetchall()
        return [{"artifact_id":str(k),"created_at":at.isoformat(),
                 "strategy_id":p.get("definition",{}).get("strategy_id"),"metrics":p.get("metrics"),
                 "kind":kind,"warnings":p.get("warnings",[])} for k,at,p in rows]

    def search_counts(self):
        with connect(self.dsn) as c:
            rows=c.execute("SELECT kind,count(*) FROM quant_artifacts GROUP BY kind").fetchall()
            strategies=c.execute("SELECT count(DISTINCT payload->'definition'->>'strategy_id') FROM quant_artifacts WHERE kind='run'").fetchone()[0]
        return {"artifact_counts":dict(rows),"strategies_examined":strategies,
                "unique_run_combinations":dict(rows).get("run",0),"warning":"MULTIPLE_TESTING; NO_SIGNIFICANCE_CORRECTION; DEPENDENT_TRADES"}
