"""Durable DB jobs and transactional, idempotent local event consumption."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Callable
from uuid import UUID, uuid4

from psycopg.types.json import Jsonb

from .database import connect


@dataclass(frozen=True)
class Job:
    job_id: UUID
    kind: str
    idempotency_key: str
    attempts: int
    payload: dict


class JobQueue:
    def __init__(self, dsn: str):
        self.dsn = dsn

    def enqueue(self, kind: str, key: str, payload: dict) -> UUID:
        if any(term in kind.lower() for term in ("order", "execute", "broker_write")):
            raise ValueError("execution jobs are outside this research application")
        with connect(self.dsn) as connection:
            with connection.transaction():
                row = connection.execute("""INSERT INTO jobs
                    (job_id,kind,idempotency_key,state,attempts,next_attempt_at,payload)
                    VALUES (%s,%s,%s,'ready',0,now(),%s)
                    ON CONFLICT (idempotency_key) DO UPDATE SET idempotency_key = EXCLUDED.idempotency_key
                    RETURNING job_id""", (uuid4(), kind, key, Jsonb(payload))).fetchone()
                return row[0]

    def claim(self, lease_seconds: int = 60, *, kind: str | None = None, job_id: UUID | None = None) -> Job | None:
        if not 1 <= lease_seconds <= 3600:
            raise ValueError("invalid lease")
        with connect(self.dsn) as connection:
            with connection.transaction():
                row = connection.execute("""WITH candidate AS (
                    SELECT job_id FROM jobs WHERE ((state = 'ready' AND next_attempt_at <= now())
                       OR (state = 'leased' AND lease_until < now()))
                       AND (%s::text IS NULL OR kind=%s) AND (%s::uuid IS NULL OR job_id=%s)
                    ORDER BY next_attempt_at, job_id FOR UPDATE SKIP LOCKED LIMIT 1)
                    UPDATE jobs SET state = 'leased', attempts = attempts + 1,
                      lease_until = now() + (%s * interval '1 second')
                    FROM candidate WHERE jobs.job_id = candidate.job_id
                    RETURNING jobs.job_id,jobs.kind,jobs.idempotency_key,jobs.attempts,jobs.payload""",
                    (kind,kind,job_id,job_id,lease_seconds)).fetchone()
                return Job(*row) if row else None

    def finish(self, job_id: UUID, attempts: int, error_code: str | None = None,
               max_attempts: int = 3) -> str:
        if max_attempts < 1:
            raise ValueError("invalid max attempts")
        state = "done" if error_code is None else "dead" if attempts >= max_attempts else "ready"
        delay = min(900, 2 ** min(attempts, 10)) if error_code else 0
        with connect(self.dsn) as connection:
            with connection.transaction():
                row = connection.execute("""UPDATE jobs SET state = %s, error_code = %s,
                    next_attempt_at = now() + (%s * interval '1 second'), lease_until = NULL
                    WHERE job_id = %s AND state = 'leased' AND attempts = %s RETURNING job_id""",
                    (state, error_code, delay, job_id, attempts)).fetchone()
                if not row:
                    raise RuntimeError("stale job lease")
        return state


@dataclass(frozen=True)
class DomainEvent:
    event_id: UUID
    event_type: str
    schema_version: str
    occurred_at: datetime
    recorded_at: datetime
    aggregate_id: str
    correlation_id: UUID
    idempotency_key: str
    payload_ref: str


class OutboxConsumer:
    def __init__(self, dsn: str, consumer_id: str):
        self.dsn, self.consumer_id = dsn, consumer_id

    def consume_one(self, handler: Callable[[object, DomainEvent], None]) -> bool:
        """Handler must use the supplied DB connection for atomic side effects."""
        with connect(self.dsn) as connection:
            with connection.transaction():
                row = connection.execute("""SELECT event_id,event_type,schema_version,occurred_at,
                    recorded_at,aggregate_id,correlation_id,idempotency_key,payload_ref FROM outbox
                    WHERE NOT EXISTS (SELECT 1 FROM consumer_receipts r
                      WHERE r.consumer_id = %s AND r.event_id = outbox.event_id)
                    ORDER BY recorded_at,event_id FOR UPDATE SKIP LOCKED LIMIT 1""", (self.consumer_id,)).fetchone()
                if row is None:
                    return False
                event = DomainEvent(*row)
                exists = connection.execute("SELECT 1 FROM consumer_receipts WHERE consumer_id = %s AND event_id = %s",
                                            (self.consumer_id, event.event_id)).fetchone()
                if not exists:
                    handler(connection, event)
                    connection.execute("INSERT INTO consumer_receipts VALUES (%s,%s,now())",
                                       (self.consumer_id, event.event_id))
                connection.execute("UPDATE outbox SET delivered_at = COALESCE(delivered_at, now()) WHERE event_id = %s", (event.event_id,))
                return True
