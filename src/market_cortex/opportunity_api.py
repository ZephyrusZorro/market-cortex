"""Local-only, bounded opportunity and thesis research API."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException, Query

from .config import Settings
from .cortex import CortexService
from .cortex_contracts import ResearchRequest
from .market_state import PILOT_SYMBOLS
from .opportunity import OpportunityService
from .opportunity_contracts import (ScanRequest, ThesisCreateRequest, ThesisDecisionRequest,
                                    ThesisMonitorRequest)
from .opportunity_store import OpportunityStore
from .storage import PostgresCatalog


def router_for(catalog: PostgresCatalog, settings: Settings) -> APIRouter:
    router = APIRouter(prefix="/api/v1/opportunities", tags=["opportunities"])
    service = OpportunityService(catalog)
    store = OpportunityStore(catalog.dsn)

    def error(exc: Exception) -> HTTPException:
        return HTTPException(404 if isinstance(exc, LookupError) else 422,
                             detail={"code": str(exc).splitlines()[0][:100]})

    @router.get("/detectors")
    def detectors() -> dict:
        return {"items": [item.model_dump(mode="json") for item in service.detector_definitions()]}

    @router.post("/scan")
    def scan(request: ScanRequest) -> dict:
        try:
            return service.scan(request).model_dump(mode="json")
        except (LookupError, ValueError, KeyError) as exc:
            raise error(exc) from None

    @router.get("/candidates")
    def candidates(symbol: str | None = None, outcome: str | None = None,
                   limit: int = Query(50, ge=1, le=200)) -> dict:
        if symbol is not None and symbol not in PILOT_SYMBOLS:
            raise HTTPException(422, detail={"code": "UNSUPPORTED_PILOT_SYMBOL"})
        if outcome is not None and outcome not in {"candidate", "rejected", "insufficient_data", "unsupported"}:
            raise HTTPException(422, detail={"code": "UNKNOWN_OUTCOME"})
        return {"items": [item.model_dump(mode="json") for item in
                          store.recent_candidates(symbol=symbol, outcome=outcome, limit=limit)]}

    @router.get("/candidates/{candidate_id}")
    def candidate(candidate_id: UUID) -> dict:
        item = store.candidate(candidate_id)
        if item is None:
            raise HTTPException(404, detail={"code": "CANDIDATE_NOT_FOUND"})
        return item.model_dump(mode="json")

    @router.post("/theses")
    def create_thesis(request: ThesisCreateRequest) -> dict:
        try:
            return store.create_thesis(request.candidate_id, request.cortex_run_id).model_dump(mode="json")
        except (LookupError, ValueError) as exc:
            raise error(exc) from None

    @router.get("/theses")
    def theses(symbol: str | None = None, limit: int = Query(50, ge=1, le=200)) -> dict:
        if symbol is not None and symbol not in PILOT_SYMBOLS:
            raise HTTPException(422, detail={"code": "UNSUPPORTED_PILOT_SYMBOL"})
        return {"items": [item.model_dump(mode="json") for item in
                          store.recent_theses(symbol=symbol, limit=limit)]}

    @router.get("/theses/{thesis_id}")
    def thesis(thesis_id: UUID, version: int | None = Query(None, ge=1)) -> dict:
        item = store.thesis(thesis_id, version)
        if item is None:
            raise HTTPException(404, detail={"code": "THESIS_NOT_FOUND"})
        return item.model_dump(mode="json")

    @router.get("/theses/{thesis_id}/versions")
    def versions(thesis_id: UUID) -> dict:
        items = store.versions(thesis_id)
        if not items:
            raise HTTPException(404, detail={"code": "THESIS_NOT_FOUND"})
        return {"items": [item.model_dump(mode="json") for item in items]}

    @router.get("/theses/{thesis_id}/comparison")
    def comparison(thesis_id: UUID, from_version: int = Query(1, ge=1),
                   to_version: int | None = Query(None, ge=1)) -> dict:
        earlier = store.thesis(thesis_id, from_version)
        later = store.thesis(thesis_id, to_version)
        if earlier is None or later is None:
            raise HTTPException(404, detail={"code": "THESIS_VERSION_NOT_FOUND"})
        return {"thesis_id": str(thesis_id), "from_version": earlier.version,
                "to_version": later.version, "from_status": earlier.status, "to_status": later.status,
                "from_manifest_id": str(earlier.source_manifest_id),
                "to_manifest_id": str(later.source_manifest_id),
                "added_evidence_ids": sorted(set(later.supporting_evidence_ids + later.opposing_evidence_ids) -
                                             set(earlier.supporting_evidence_ids + earlier.opposing_evidence_ids)),
                "removed_evidence_ids": sorted(set(earlier.supporting_evidence_ids + earlier.opposing_evidence_ids) -
                                               set(later.supporting_evidence_ids + later.opposing_evidence_ids)),
                "new_contradictions": sorted(set(later.candidate.contradictions) -
                                             set(earlier.candidate.contradictions)),
                "status_changed": earlier.status != later.status}

    @router.post("/theses/{thesis_id}/monitor")
    def monitor(thesis_id: UUID, request: ThesisMonitorRequest) -> dict:
        prior = store.thesis(thesis_id)
        if prior is None:
            raise HTTPException(404, detail={"code": "THESIS_NOT_FOUND"})
        try:
            result = service.scan(ScanRequest(mode=request.mode,
                manifest_id=request.manifest_id, as_of=request.as_of,
                symbol=prior.symbol, detector_id=prior.detector_id, record=True))
            current = next(item for item in result.candidates if item.symbol == prior.symbol and
                           item.detector_id == prior.detector_id)
            return store.advance(thesis_id, current).model_dump(mode="json")
        except StopIteration:
            raise HTTPException(422, detail={"code": "DETECTOR_EVALUATION_UNAVAILABLE"}) from None
        except (LookupError, ValueError, KeyError) as exc:
            raise error(exc) from None

    @router.post("/theses/{thesis_id}/decision")
    def decision(thesis_id: UUID, request: ThesisDecisionRequest) -> dict:
        prior = store.thesis(thesis_id)
        if prior is None:
            raise HTTPException(404, detail={"code": "THESIS_NOT_FOUND"})
        try:
            return store.advance(thesis_id, prior.candidate, actor="owner",
                requested_status=request.status, reason=request.reason).model_dump(mode="json")
        except ValueError as exc:
            raise error(exc) from None

    @router.post("/theses/{thesis_id}/review")
    def review(thesis_id: UUID) -> dict:
        thesis = store.thesis(thesis_id)
        if thesis is None:
            raise HTTPException(404, detail={"code": "THESIS_NOT_FOUND"})
        candidate = thesis.candidate
        question = (f"Review {candidate.symbol} {candidate.detector_id} research candidate "
                    f"{candidate.candidate_id}. Describe stored market evidence, counter-evidence, "
                    "missing data and invalidation conditions; do not give an order recommendation.")
        try:
            run = CortexService(catalog, settings).research(ResearchRequest(question=question,
                mode="pinned", manifest_id=candidate.source_manifest_id,
                as_of=candidate.as_of, symbol=candidate.symbol,
                candidate_id=candidate.candidate_id, depth="deep"))
            if run.failure_state:
                return {"review_status": "INSUFFICIENT_CORTEX_EVIDENCE",
                        "candidate": candidate.model_dump(mode="json"),
                        "thesis": thesis.model_dump(mode="json"), "run": run.model_dump(mode="json")}
            updated = store.advance(thesis_id, candidate, cortex_run_id=run.run_id)
            return {"review_status": "GROUNDED_RESEARCH_ATTACHED",
                    "candidate": candidate.model_dump(mode="json"),
                    "thesis": updated.model_dump(mode="json"), "run": run.model_dump(mode="json")}
        except (LookupError, ValueError) as exc:
            raise error(exc) from None

    return router
