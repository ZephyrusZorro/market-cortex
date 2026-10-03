"""Local PostgreSQL research-run manifests and read-only retrieval."""

from __future__ import annotations

import json
from datetime import datetime
from uuid import UUID

from .cortex_contracts import ResearchRun
from .database import connect


class ResearchRunStore:
    def __init__(self, dsn: str):
        self.dsn = dsn

    def save(self, run: ResearchRun) -> None:
        payload = run.model_dump(mode="json")
        with connect(self.dsn) as connection:
            connection.execute("""INSERT INTO cortex_research_runs
                (run_id, created_at, manifest_id, as_of, primary_symbol, evidence_hash, payload)
                VALUES (%s, %s, %s, %s, %s, %s, %s)""",
                (run.run_id, run.created_at, run.context.manifest_id, run.context.as_of,
                 run.context.symbol, run.evidence_hash, json.dumps(payload)))

    def get(self, run_id: UUID) -> ResearchRun | None:
        with connect(self.dsn) as connection:
            row = connection.execute("SELECT payload FROM cortex_research_runs WHERE run_id = %s",
                                     (run_id,)).fetchone()
        return ResearchRun.model_validate(row[0]) if row else None

    def recent(self, *, symbol: str | None = None, limit: int = 20,
               before: datetime | None = None) -> list[dict]:
        if not 1 <= limit <= 50:
            raise ValueError("INVALID_RUN_LIST_LIMIT")
        with connect(self.dsn) as connection:
            rows = connection.execute("""SELECT run_id, created_at, primary_symbol, manifest_id, as_of,
                payload->'request'->>'question', payload->>'failure_state'
                FROM cortex_research_runs WHERE (%s::text IS NULL OR primary_symbol = %s)
                  AND (%s::timestamptz IS NULL OR created_at < %s)
                ORDER BY created_at DESC LIMIT %s""", (symbol, symbol, before, before, limit)).fetchall()
        return [{"run_id": str(row[0]), "created_at": row[1].isoformat(),
                 "symbol": row[2], "manifest_id": str(row[3]), "as_of": row[4].isoformat(),
                 "question": row[5], "failure_state": row[6]} for row in rows]
