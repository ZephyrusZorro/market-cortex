"""Append-only local journals, frozen predictions and evaluation revisions."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from uuid import UUID, uuid4

from psycopg.conninfo import conninfo_to_dict

from .database import connect
from .learning_contracts import (JournalDraft, JournalEntry, JournalRevision,
                                PredictionEvaluation, PredictionRecord)


def encoded(value) -> str:
    return json.dumps(value.model_dump(mode="json") if hasattr(value, "model_dump") else value,
                      default=str)


class LearningStore:
    def __init__(self, dsn: str, environment: str):
        self.dsn, self.environment = dsn, environment

    def guard(self, classification: str) -> None:
        if classification == "SYNTHETIC_TEST" and (self.environment != "PILOT_TEST" or
            not conninfo_to_dict(self.dsn).get("dbname", "").lower().endswith("_test")):
            raise ValueError("SYNTHETIC_LEARNING_REQUIRES_TEST_DATABASE")

    def create_journal(self, draft: JournalDraft, frozen_links: dict) -> JournalEntry:
        self.guard(draft.classification)
        now = datetime.now(timezone.utc)
        entry = JournalEntry(**draft.model_dump(), entry_id=uuid4(), revision=1,
            created_at=now, recorded_at=now, frozen_links=frozen_links)
        with connect(self.dsn) as connection:
            connection.execute("INSERT INTO journal_entries VALUES (%s,1,%s)", (entry.entry_id, now))
            connection.execute("INSERT INTO journal_revisions(entry_id,revision,recorded_at,reason,payload) VALUES (%s,1,%s,%s,%s)",
                (entry.entry_id, entry.recorded_at, "OWNER_CREATED" if draft.author == "owner" else "CORTEX_TEMPLATE_ACCEPTED", encoded(entry)))
        return entry

    def journal(self, entry_id: UUID, revision: int | None = None) -> JournalEntry | None:
        with connect(self.dsn) as connection:
            row = connection.execute("""SELECT r.payload FROM journal_entries e JOIN journal_revisions r
                ON r.entry_id=e.entry_id AND r.revision=COALESCE(%s,e.current_revision)
                WHERE e.entry_id=%s""", (revision, entry_id)).fetchone()
        return JournalEntry.model_validate(row[0]) if row else None

    def journals(self, *, as_of: datetime, search: str = "", category: str | None = None,
                 tag: str | None = None, limit: int | None = 100) -> list[JournalEntry]:
        with connect(self.dsn) as connection:
            rows = connection.execute("""SELECT r.payload FROM journal_entries e
                JOIN LATERAL (SELECT payload FROM journal_revisions WHERE entry_id=e.entry_id
                    AND recorded_at<=%s ORDER BY revision DESC LIMIT 1) r ON true
                WHERE (r.payload->>'title' ILIKE %s OR r.payload->>'notes' ILIKE %s)
                AND (%s::text IS NULL OR r.payload->>'category'=%s)
                AND (%s::text IS NULL OR r.payload->'tags' ? %s)
                ORDER BY e.created_at DESC,e.entry_id LIMIT %s""",
                (as_of, f"%{search}%", f"%{search}%", category, category, tag, tag, limit)).fetchall()
        return [JournalEntry.model_validate(row[0]) for row in rows]

    def revise_journal(self, entry_id: UUID, request: JournalRevision, frozen_links: dict) -> JournalEntry:
        self.guard(request.draft.classification)
        with connect(self.dsn) as connection:
            row = connection.execute("SELECT current_revision FROM journal_entries WHERE entry_id=%s FOR UPDATE",
                                     (entry_id,)).fetchone()
            if row is None:
                raise LookupError("JOURNAL_NOT_FOUND")
            if row[0] != request.expected_revision:
                raise ValueError("JOURNAL_REVISION_CONFLICT")
            prior = connection.execute("SELECT payload FROM journal_revisions WHERE entry_id=%s AND revision=%s",
                                       (entry_id, row[0])).fetchone()[0]
            if prior["classification"] != request.draft.classification:
                raise ValueError("JOURNAL_CLASSIFICATION_IMMUTABLE")
            entry = JournalEntry(**request.draft.model_dump(), entry_id=entry_id, revision=row[0]+1,
                created_at=prior["created_at"], recorded_at=datetime.now(timezone.utc), frozen_links=frozen_links)
            connection.execute("INSERT INTO journal_revisions(entry_id,revision,recorded_at,reason,payload) VALUES (%s,%s,%s,%s,%s)",
                               (entry_id, entry.revision, entry.recorded_at, request.reason, encoded(entry)))
            connection.execute("UPDATE journal_entries SET current_revision=%s WHERE entry_id=%s",
                               (entry.revision, entry_id))
        return entry

    def journal_history(self, entry_id: UUID) -> list[dict]:
        with connect(self.dsn) as connection:
            rows = connection.execute("SELECT payload,reason FROM journal_revisions WHERE entry_id=%s ORDER BY revision",
                                      (entry_id,)).fetchall()
        return [{"entry":row[0], "reason":row[1]} for row in rows]

    def save_prediction(self, prediction: PredictionRecord) -> PredictionRecord:
        self.guard(prediction.classification)
        with connect(self.dsn) as connection:
            recorded = connection.execute("SELECT clock_timestamp()").fetchone()[0].astimezone(timezone.utc)
            if prediction.registration == "PRE_REGISTERED" and recorded>=datetime.fromisoformat(prediction.original_context["first_outcome_close_at"]):
                raise ValueError("HORIZON_ALREADY_STARTED_USE_RETROSPECTIVE")
            prediction = prediction.model_copy(update={"created_at":recorded})
            connection.execute("""INSERT INTO prediction_records
                (prediction_id,created_at,source_manifest_id,as_of,registration,original_context_hash,payload,current_revision)
                VALUES (%s,%s,%s,%s,%s,%s,%s,1)""", (prediction.prediction_id, prediction.created_at,
                prediction.manifest_id, prediction.as_of, prediction.registration,
                prediction.original_context_hash, encoded(prediction)))
            connection.execute("INSERT INTO prediction_revisions(prediction_id,revision,status,reason) VALUES (%s,1,'OPEN','EXPLICIT_CREATION')",
                               (prediction.prediction_id,))
        return prediction

    def predictions(self, *, as_of: datetime, prediction_id: UUID | None = None,
                    status: str | None = None, limit: int | None = 200) -> list[PredictionRecord]:
        with connect(self.dsn) as connection:
            rows = connection.execute("""SELECT p.payload,r.revision,r.status,r.evaluation_id FROM prediction_records p
                JOIN LATERAL (SELECT revision,status,evaluation_id FROM prediction_revisions WHERE prediction_id=p.prediction_id
                    AND recorded_at<=%s ORDER BY revision DESC LIMIT 1) r ON true
                WHERE p.created_at<=%s AND (%s::uuid IS NULL OR p.prediction_id=%s)
                AND (%s::text IS NULL OR r.status=%s) ORDER BY p.created_at DESC,p.prediction_id LIMIT %s""",
                (as_of, as_of, prediction_id, prediction_id, status, status, limit)).fetchall()
        return [PredictionRecord.model_validate({**row[0], "revision":row[1], "status":row[2],
                                                "evaluation_id":row[3]}) for row in rows]

    def prediction(self, prediction_id: UUID, as_of: datetime | None = None) -> PredictionRecord | None:
        rows = self.predictions(as_of=as_of or datetime.now(timezone.utc), prediction_id=prediction_id)
        return rows[0] if rows else None

    def performance_records(self, as_of: datetime, classification: str | None = None):
        with connect(self.dsn) as connection:
            rows = connection.execute("""SELECT p.payload,r.revision,r.status,r.evaluation_id,e.payload
                FROM prediction_records p JOIN LATERAL (
                    SELECT revision,status,evaluation_id FROM prediction_revisions
                    WHERE prediction_id=p.prediction_id AND recorded_at<=%s
                    ORDER BY revision DESC LIMIT 1) r ON true
                LEFT JOIN prediction_evaluations e ON e.evaluation_id=r.evaluation_id
                WHERE p.created_at<=%s AND (%s::text IS NULL OR p.payload->>'classification'=%s)
                ORDER BY p.created_at,p.prediction_id""", (as_of,as_of,classification,classification)).fetchall()
        return [(PredictionRecord.model_validate({**r[0],"revision":r[1],"status":r[2],"evaluation_id":r[3]}),
                 PredictionEvaluation.model_validate(r[4]) if r[4] else None) for r in rows]

    def prediction_history(self, prediction_id: UUID) -> list[dict]:
        with connect(self.dsn) as connection:
            rows = connection.execute("""SELECT revision,status,recorded_at,reason,evaluation_id FROM prediction_revisions
                WHERE prediction_id=%s ORDER BY revision""", (prediction_id,)).fetchall()
        return [dict(zip(("revision","status","recorded_at","reason","evaluation_id"), row)) for row in rows]

    def evaluation(self, evaluation_id: UUID) -> PredictionEvaluation | None:
        with connect(self.dsn) as connection:
            row = connection.execute("SELECT payload FROM prediction_evaluations WHERE evaluation_id=%s", (evaluation_id,)).fetchone()
        return PredictionEvaluation.model_validate(row[0]) if row else None

    def evaluations(self, prediction_id: UUID) -> list[PredictionEvaluation]:
        with connect(self.dsn) as connection:
            rows = connection.execute("SELECT payload FROM prediction_evaluations WHERE prediction_id=%s ORDER BY evaluated_at",
                                      (prediction_id,)).fetchall()
        return [PredictionEvaluation.model_validate(row[0]) for row in rows]

    def save_evaluation(self, evaluation: PredictionEvaluation) -> PredictionEvaluation:
        with connect(self.dsn) as connection:
            head = connection.execute("SELECT current_revision,original_context_hash FROM prediction_records WHERE prediction_id=%s FOR UPDATE",
                                      (evaluation.prediction_id,)).fetchone()
            if head is None or head[1] != evaluation.original_context_hash:
                raise ValueError("PREDICTION_CONTEXT_MISMATCH")
            prior_status = connection.execute("SELECT status FROM prediction_revisions WHERE prediction_id=%s AND revision=%s",
                                             (evaluation.prediction_id,head[0])).fetchone()[0]
            if prior_status == "CANCELLED":
                raise ValueError("CANCELLED_PREDICTION_CANNOT_EVALUATE")
            prior = connection.execute("SELECT payload FROM prediction_evaluations WHERE evaluation_id=%s",
                                       (evaluation.evaluation_id,)).fetchone()
            if prior:
                return PredictionEvaluation.model_validate(prior[0])
            current_evaluation = connection.execute("""SELECT e.as_of FROM prediction_revisions r
                JOIN prediction_evaluations e ON e.evaluation_id=r.evaluation_id
                WHERE r.prediction_id=%s AND r.revision=%s""", (evaluation.prediction_id,head[0])).fetchone()
            if current_evaluation and evaluation.as_of < current_evaluation[0]:
                raise ValueError("EVALUATION_CUTOFF_CANNOT_MOVE_BACKWARD")
            connection.execute("""INSERT INTO prediction_evaluations VALUES (%s,%s,%s,%s,%s,%s)""",
                (evaluation.evaluation_id,evaluation.prediction_id,evaluation.evaluation_manifest_id,
                 evaluation.as_of,evaluation.evaluated_at,encoded(evaluation)))
            connection.execute("""INSERT INTO prediction_revisions(prediction_id,revision,status,reason,evaluation_id)
                VALUES (%s,%s,%s,'DETERMINISTIC_EVALUATION',%s)""",
                (evaluation.prediction_id,head[0]+1,evaluation.status,evaluation.evaluation_id))
            connection.execute("UPDATE prediction_records SET current_revision=%s WHERE prediction_id=%s",
                               (head[0]+1,evaluation.prediction_id))
        return evaluation

    def cancel(self, prediction_id: UUID, reason: str) -> PredictionRecord:
        with connect(self.dsn) as connection:
            row = connection.execute("SELECT current_revision FROM prediction_records WHERE prediction_id=%s FOR UPDATE", (prediction_id,)).fetchone()
            if row is None:
                raise LookupError("PREDICTION_NOT_FOUND")
            status = connection.execute("SELECT status FROM prediction_revisions WHERE prediction_id=%s AND revision=%s", (prediction_id,row[0])).fetchone()[0]
            if status not in ("OPEN", "PENDING_EVALUATION", "INCONCLUSIVE", "UNMEASURABLE"):
                raise ValueError("ONLY_UNRESOLVED_PREDICTIONS_CAN_CANCEL")
            connection.execute("INSERT INTO prediction_revisions(prediction_id,revision,status,reason) VALUES (%s,%s,'CANCELLED',%s)",
                               (prediction_id,row[0]+1,reason))
            connection.execute("UPDATE prediction_records SET current_revision=%s WHERE prediction_id=%s", (row[0]+1,prediction_id))
        return self.prediction(prediction_id)

    def save_edge(self, payload: dict) -> dict:
        self.guard(payload["classification"])
        with connect(self.dsn) as connection:
            connection.execute("INSERT INTO edge_library VALUES (%s,%s,%s)",
                               (payload["edge_id"],payload["created_at"],encoded(payload)))
        return payload

    def edges(self, as_of: datetime) -> list[dict]:
        with connect(self.dsn) as connection:
            rows = connection.execute("SELECT payload FROM edge_library WHERE created_at<=%s ORDER BY created_at DESC,edge_id LIMIT 100", (as_of,)).fetchall()
            revisions = connection.execute("SELECT DISTINCT ON(edge_id) edge_id,payload FROM quant_edge_evidence WHERE recorded_at<=%s ORDER BY edge_id,revision DESC",(as_of,)).fetchall()
        evidence={str(k):p for k,p in revisions}
        return [{**row[0],**({"status":evidence[str(row[0]["edge_id"])]["status"],"quant_evidence":evidence[str(row[0]["edge_id"]) ]}
                               if str(row[0]["edge_id"]) in evidence else {})} for row in rows]
