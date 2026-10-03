"""Append-only candidate ledger and versioned local research theses."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from uuid import UUID, uuid4

from .database import connect
from .opportunity_contracts import Candidate, ScanResult, Thesis, ThesisTransition


TERMINAL = frozenset({"NO_EDGE", "AVOID", "INVALIDATED"})
OWNER_ALLOWED = frozenset({"WATCHING", "NO_EDGE", "EVENT_RISK", "AVOID"})
VALID_TRANSITIONS = {
    "WATCHING": {"WATCHING", "DEVELOPING", "AWAITING_CONFIRMATION", "VALID", "NO_EDGE", "EVENT_RISK", "AVOID"},
    "DEVELOPING": {"WATCHING", "DEVELOPING", "AWAITING_CONFIRMATION", "VALID", "NO_EDGE", "EVENT_RISK", "AVOID", "INVALIDATED"},
    "AWAITING_CONFIRMATION": {"WATCHING", "DEVELOPING", "AWAITING_CONFIRMATION", "VALID", "NO_EDGE", "EVENT_RISK", "AVOID", "INVALIDATED"},
    "VALID": {"WATCHING", "DEVELOPING", "AWAITING_CONFIRMATION", "VALID", "NO_EDGE", "EVENT_RISK", "AVOID", "INVALIDATED"},
    "NO_EDGE": {"NO_EDGE", "WATCHING"},
    "EVENT_RISK": {"EVENT_RISK", "WATCHING", "NO_EDGE", "AVOID"},
    "AVOID": {"AVOID", "WATCHING"},
    "INVALIDATED": {"INVALIDATED", "WATCHING"},
}


class OpportunityStore:
    def __init__(self, dsn: str):
        self.dsn = dsn

    def record_scan(self, scan: ScanResult) -> int:
        inserted = 0
        with connect(self.dsn) as connection:
            for candidate in scan.candidates:
                row = connection.execute("""INSERT INTO opportunity_candidates
                    (candidate_id, scan_id, manifest_id, as_of, symbol, detector_id,
                     detector_version, outcome, status, evidence_hash, payload)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                    ON CONFLICT (candidate_id) DO NOTHING RETURNING candidate_id""",
                    (candidate.candidate_id, scan.scan_id, candidate.source_manifest_id,
                     candidate.as_of, candidate.symbol, candidate.detector_id,
                     candidate.detector_version, candidate.outcome, candidate.status,
                     candidate.evidence_hash, json.dumps(candidate.model_dump(mode="json")))).fetchone()
                inserted += int(row is not None)
        return inserted

    def candidate(self, candidate_id: UUID) -> Candidate | None:
        with connect(self.dsn) as connection:
            row = connection.execute("SELECT payload FROM opportunity_candidates WHERE candidate_id=%s",
                                     (candidate_id,)).fetchone()
        return Candidate.model_validate(row[0]) if row else None

    def recent_candidates(self, *, symbol: str | None = None, outcome: str | None = None,
                          limit: int = 50) -> list[Candidate]:
        if not 1 <= limit <= 200:
            raise ValueError("INVALID_LIMIT")
        with connect(self.dsn) as connection:
            rows = connection.execute("""SELECT payload FROM opportunity_candidates
                WHERE (%s::text IS NULL OR symbol=%s) AND (%s::text IS NULL OR outcome=%s)
                ORDER BY recorded_at DESC, candidate_id LIMIT %s""",
                (symbol, symbol, outcome, outcome, limit)).fetchall()
        return [Candidate.model_validate(row[0]) for row in rows]

    def thesis(self, thesis_id: UUID, version: int | None = None) -> Thesis | None:
        with connect(self.dsn) as connection:
            row = connection.execute("""SELECT v.payload FROM research_theses h
                JOIN research_thesis_versions v ON v.thesis_id=h.thesis_id
                AND v.version=COALESCE(%s, h.current_version)
                WHERE h.thesis_id=%s""", (version, thesis_id)).fetchone()
        return Thesis.model_validate(row[0]) if row else None

    def recent_theses(self, *, symbol: str | None = None, limit: int = 50) -> list[Thesis]:
        if not 1 <= limit <= 200:
            raise ValueError("INVALID_LIMIT")
        with connect(self.dsn) as connection:
            rows = connection.execute("""SELECT v.payload FROM research_theses h
                JOIN research_thesis_versions v ON v.thesis_id=h.thesis_id AND v.version=h.current_version
                WHERE (%s::text IS NULL OR h.symbol=%s) ORDER BY h.created_at DESC LIMIT %s""",
                (symbol, symbol, limit)).fetchall()
        return [Thesis.model_validate(row[0]) for row in rows]

    def versions(self, thesis_id: UUID) -> list[Thesis]:
        with connect(self.dsn) as connection:
            rows = connection.execute("""SELECT payload FROM research_thesis_versions
                WHERE thesis_id=%s ORDER BY version""", (thesis_id,)).fetchall()
        return [Thesis.model_validate(row[0]) for row in rows]

    @staticmethod
    def _verify_run(connection, run_id: UUID, candidate: Candidate) -> None:
        row = connection.execute("""SELECT manifest_id, as_of, primary_symbol, payload->>'failure_state'
            FROM cortex_research_runs WHERE run_id=%s""", (run_id,)).fetchone()
        if row is None or row[0] != candidate.source_manifest_id or row[1] != candidate.as_of or \
                row[2] != candidate.symbol or row[3] is not None:
            raise ValueError("CORTEX_RUN_CONTEXT_MISMATCH")

    def create_thesis(self, candidate_id: UUID, cortex_run_id: UUID | None = None) -> Thesis:
        with connect(self.dsn) as connection:
            row = connection.execute("SELECT payload FROM opportunity_candidates WHERE candidate_id=%s",
                                     (candidate_id,)).fetchone()
            if row is None:
                raise LookupError("CANDIDATE_NOT_FOUND")
            candidate = Candidate.model_validate(row[0])
            if candidate.outcome == "unsupported":
                raise ValueError("UNSUPPORTED_CANDIDATE_CANNOT_FORM_THESIS")
            if cortex_run_id:
                self._verify_run(connection, cortex_run_id, candidate)
            existing = connection.execute("SELECT thesis_id FROM research_theses WHERE original_candidate_id=%s",
                                          (candidate_id,)).fetchone()
            if existing:
                return self.thesis(existing[0])
            now = datetime.now(timezone.utc)
            transition = ThesisTransition(from_status=None, to_status=candidate.status, at=now,
                actor="detector", reason="THESIS_CREATED_FROM_RECORDED_CANDIDATE",
                source_manifest_id=candidate.source_manifest_id, as_of=candidate.as_of,
                changed_evidence_ids=[item.evidence_id for item in candidate.evidence])
            limitations = ["Daily close-only evidence; no intraday or order-book confirmation"]
            if candidate.freshness != "current":
                limitations.append(f"Source freshness: {candidate.freshness}")
            if candidate.market_regime == "insufficient_data":
                limitations.append("Market-state requirements unavailable")
            thesis = Thesis(thesis_id=uuid4(), version=1, candidate_ids=[candidate_id],
                instrument_id=candidate.instrument_id, symbol=candidate.symbol,
                detector_id=candidate.detector_id, detector_version=candidate.detector_version,
                status=candidate.status, horizon=candidate.horizon,
                market_regime=candidate.market_regime,
                statement=f"{candidate.symbol} {candidate.detector_id.replace('_',' ')} research: "
                          f"{candidate.outcome}; {candidate.status} under versioned daily rules.",
                supporting_evidence_ids=candidate.supporting_evidence_ids,
                opposing_evidence_ids=candidate.opposing_evidence_ids,
                confirmation_conditions=candidate.confirmation_conditions,
                invalidation_conditions=candidate.invalidation_conditions,
                assumptions=["Source bars are final and mapped to the intended Binance spot pair"],
                risk_factors=list(dict.fromkeys(candidate.contradictions +
                    candidate.rejection_reasons + ["Daily-bar false positive risk"])),
                data_limitations=limitations,
                source_manifest_id=candidate.source_manifest_id, as_of=candidate.as_of,
                feature_versions={item.metric: item.feature_version for item in candidate.evidence
                                  if item.feature_version},
                cortex_run_ids=[cortex_run_id] if cortex_run_id else [],
                created_at=now, updated_at=now, transitions=[transition], candidate=candidate)
            connection.execute("""INSERT INTO research_theses
                (thesis_id, original_candidate_id, symbol, detector_id, created_at, current_version)
                VALUES (%s,%s,%s,%s,%s,1)""",
                (thesis.thesis_id, candidate_id, candidate.symbol, candidate.detector_id, now))
            self._insert_version(connection, thesis, "detector")
        return thesis

    @staticmethod
    def _insert_version(connection, thesis: Thesis, actor: str) -> None:
        connection.execute("""INSERT INTO research_thesis_versions
            (thesis_id, version, status, manifest_id, as_of, candidate_id, evidence_hash, actor, payload)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
            (thesis.thesis_id, thesis.version, thesis.status, thesis.source_manifest_id,
             thesis.as_of, thesis.candidate.candidate_id, thesis.candidate.evidence_hash,
             actor, json.dumps(thesis.model_dump(mode="json"))))

    def advance(self, thesis_id: UUID, candidate: Candidate, *, actor: str = "detector",
                requested_status: str | None = None, reason: str | None = None,
                cortex_run_id: UUID | None = None) -> Thesis:
        with connect(self.dsn) as connection:
            head = connection.execute("SELECT current_version FROM research_theses WHERE thesis_id=%s FOR UPDATE",
                                      (thesis_id,)).fetchone()
            if head is None:
                raise LookupError("THESIS_NOT_FOUND")
            row = connection.execute("""SELECT payload FROM research_thesis_versions
                WHERE thesis_id=%s AND version=%s""", (thesis_id, head[0])).fetchone()
            previous = Thesis.model_validate(row[0])
            if candidate.symbol != previous.symbol or candidate.detector_id != previous.detector_id or \
                    candidate.instrument_id != previous.instrument_id:
                raise ValueError("THESIS_CANDIDATE_SCOPE_MISMATCH")
            if candidate.as_of < previous.as_of:
                raise ValueError("THESIS_CONTEXT_MOVES_BACKWARD")
            if actor == "owner":
                if requested_status not in OWNER_ALLOWED or not reason or len(reason.strip()) < 8:
                    raise ValueError("INVALID_OWNER_DECISION")
                status = requested_status
            elif actor == "detector":
                status = candidate.status
                if previous.status in TERMINAL | {"EVENT_RISK"}:
                    status = previous.status
                elif previous.status == "VALID" and status in {"NO_EDGE", "INVALIDATED", "AVOID"}:
                    status = "INVALIDATED"
                elif status == "INVALIDATED" and previous.status not in {"VALID", "AWAITING_CONFIRMATION", "DEVELOPING"}:
                    status = "NO_EDGE"
            else:
                raise ValueError("INVALID_TRANSITION_ACTOR")
            if status not in VALID_TRANSITIONS[previous.status]:
                raise ValueError("FORBIDDEN_THESIS_TRANSITION")
            if cortex_run_id:
                self._verify_run(connection, cortex_run_id, candidate)
            if actor == "detector" and candidate.candidate_id == previous.candidate.candidate_id and status == previous.status and \
                    cortex_run_id in (None, *previous.cortex_run_ids):
                return previous
            now = datetime.now(timezone.utc)
            changed = sorted({item.evidence_id for item in candidate.evidence} ^
                             {item.evidence_id for item in previous.candidate.evidence})
            transition = ThesisTransition(from_status=previous.status, to_status=status, at=now,
                actor=actor, reason=reason or ("CORTEX_REVIEW_ATTACHED" if cortex_run_id else
                    "EVIDENCE_UPDATED_STATUS_UNCHANGED" if status == previous.status else
                    "DETECTOR_RULES_REEVALUATED"), source_manifest_id=candidate.source_manifest_id,
                as_of=candidate.as_of, changed_evidence_ids=changed)
            updated = previous.model_copy(update={
                "version": previous.version + 1,
                "candidate_ids": previous.candidate_ids + ([candidate.candidate_id]
                    if candidate.candidate_id not in previous.candidate_ids else []),
                "status": status, "market_regime": candidate.market_regime,
                "supporting_evidence_ids": candidate.supporting_evidence_ids,
                "opposing_evidence_ids": candidate.opposing_evidence_ids,
                "confirmation_conditions": candidate.confirmation_conditions,
                "invalidation_conditions": candidate.invalidation_conditions,
                "risk_factors": list(dict.fromkeys(previous.risk_factors + candidate.contradictions +
                    candidate.rejection_reasons)),
                "source_manifest_id": candidate.source_manifest_id, "as_of": candidate.as_of,
                "feature_versions": {item.metric: item.feature_version for item in candidate.evidence
                                     if item.feature_version},
                "cortex_run_ids": previous.cortex_run_ids + ([cortex_run_id] if cortex_run_id and
                    cortex_run_id not in previous.cortex_run_ids else []),
                "updated_at": now, "transitions": previous.transitions + [transition],
                "candidate": candidate,
            })
            self._insert_version(connection, updated, actor)
            connection.execute("UPDATE research_theses SET current_version=%s WHERE thesis_id=%s",
                               (updated.version, thesis_id))
        return updated
