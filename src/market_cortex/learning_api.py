"""Validated local journal and learning operations; no execution or rule mutation."""
from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query

from .learning import LearningService
from .learning_contracts import (CancelPrediction, EdgeDraft, EvaluationRequest,
                                 JournalDraft, JournalRevision, PredictionDefinition)


def router_for(catalog, settings):
    router = APIRouter(prefix="/api/v1/learning",tags=["learning"])
    service = LearningService(catalog,settings.environment)

    def cutoff(value):
        if value is not None and (value.tzinfo is None or value.utcoffset() is None):
            raise HTTPException(422,detail={"code":"OFFSET_REQUIRED"})
        value = value or datetime.now(timezone.utc)
        if value>datetime.now(timezone.utc):
            raise HTTPException(422,detail={"code":"FUTURE_CONTEXT_CUTOFF_FORBIDDEN"})
        return value

    def call(action):
        try:
            item = action()
            return item.model_dump(mode="json") if hasattr(item,"model_dump") else item
        except (ValueError,LookupError,KeyError) as exc:
            code = str(exc).splitlines()[0][:100]
            raise HTTPException(404 if isinstance(exc,LookupError) else 422,detail={"code":code}) from None

    @router.get("/journal")
    def journals(as_of: datetime | None = None, search: str = Query("",max_length=200),
                 category: str | None = Query(None,max_length=40), tag: str | None = Query(None,max_length=100)):
        return {"items":[item.model_dump(mode="json") for item in service.store.journals(
            as_of=cutoff(as_of),search=search,category=category,tag=tag)]}

    @router.post("/journal")
    def create_journal(request: JournalDraft):
        return call(lambda:service.journal(request))

    @router.get("/journal/{entry_id}")
    def journal(entry_id: UUID, revision: int | None = Query(None,ge=1)):
        item = service.store.journal(entry_id,revision)
        if item is None:
            raise HTTPException(404,detail={"code":"JOURNAL_NOT_FOUND"})
        return item.model_dump(mode="json")

    @router.get("/journal/{entry_id}/revisions")
    def journal_history(entry_id: UUID):
        return {"items":service.store.journal_history(entry_id)}

    @router.post("/journal/{entry_id}/revisions")
    def revise(entry_id: UUID, request: JournalRevision):
        def action():
            service.context(request.draft.manifest_id,request.draft.as_of)
            frozen = service.freeze_links(request.draft.links,request.draft.manifest_id,
                                          request.draft.as_of,request.draft.classification)
            return service.store.revise_journal(entry_id,request,frozen)
        return call(action)

    @router.get("/predictions")
    def predictions(as_of: datetime | None = None, status: str | None = None):
        return {"items":[p.model_dump(mode="json") for p in service.store.predictions(as_of=cutoff(as_of),status=status)]}

    @router.post("/predictions")
    def create_prediction(request: PredictionDefinition):
        return call(lambda:service.create_prediction(request))

    @router.get("/predictions/{prediction_id}")
    def prediction(prediction_id: UUID, as_of: datetime | None = None):
        known_at = cutoff(as_of)
        item = service.store.prediction(prediction_id,known_at)
        if item is None:
            raise HTTPException(404,detail={"code":"PREDICTION_NOT_FOUND"})
        return {"prediction":item.model_dump(mode="json"),
                "revisions":[r for r in service.store.prediction_history(prediction_id) if r["recorded_at"]<=known_at],
                "evaluations":[e.model_dump(mode="json") for e in service.store.evaluations(prediction_id) if e.evaluated_at<=known_at]}

    @router.post("/predictions/{prediction_id}/evaluate")
    def evaluate(prediction_id: UUID, request: EvaluationRequest):
        return call(lambda:service.evaluate(prediction_id,request))

    @router.post("/predictions/{prediction_id}/cancel")
    def cancel(prediction_id: UUID, request: CancelPrediction):
        return call(lambda:service.store.cancel(prediction_id,request.reason))

    @router.get("/predictions/{prediction_id}/postmortem")
    def postmortem(prediction_id: UUID):
        return call(lambda:service.postmortem(prediction_id))

    @router.get("/evaluations/{evaluation_id}")
    def evaluation(evaluation_id: UUID):
        item = service.store.evaluation(evaluation_id)
        if item is None:
            raise HTTPException(404,detail={"code":"EVALUATION_NOT_FOUND"})
        return item.model_dump(mode="json")

    @router.get("/review-queue")
    def queue(as_of: datetime | None = None):
        return service.review_queue(cutoff(as_of))

    @router.post("/evaluate-due")
    def evaluate_due(request: EvaluationRequest):
        return call(lambda:service.evaluate_due(request))

    @router.get("/performance")
    def performance(as_of: datetime | None = None, eligible_only: bool = False,
                    classification: str | None = Query(None,pattern="^(OWNER_RESEARCH|SYNTHETIC_TEST)$")):
        return service.performance(as_of=cutoff(as_of),eligible_only=eligible_only,classification=classification)

    @router.get("/failures")
    def failures(as_of: datetime | None = None):
        entries = [e for e in service.store.journals(as_of=cutoff(as_of),limit=None) if e.failure_category]
        patterns = {}
        for entry in entries:
            key = f"{entry.classification}:{entry.failure_category}"
            patterns[key]=patterns.get(key,0)+1
        return {"N":len(entries),"patterns":patterns,"items":[e.model_dump(mode="json") for e in entries],
                "warning":"OWNER_NOTES_AND_ACCEPTED_TEMPLATES_NOT_MACHINE_INFERRED_MISTAKES"}

    @router.get("/edges")
    def edges(as_of: datetime | None = None):
        return {"items":service.store.edges(cutoff(as_of))}

    @router.post("/edges")
    def edge(request: EdgeDraft):
        return call(lambda:service.edge(request))

    @router.get("/links")
    def links(thesis_id: UUID | None = None, research_run_id: UUID | None = None):
        def linked(item):
            return (thesis_id is not None and item.links.thesis_id==thesis_id) or (
                research_run_id is not None and item.links.research_run_id==research_run_id)
        now = datetime.now(timezone.utc)
        return {"predictions":[p.model_dump(mode="json") for p in service.store.predictions(as_of=now,limit=None) if linked(p)],
                "journal":[e.model_dump(mode="json") for e in service.store.journals(as_of=now,limit=None) if linked(e)]}
    return router
