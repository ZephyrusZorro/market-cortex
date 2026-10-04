"""Local reviewed research jobs and immutable reads. No uploaded code."""
from datetime import datetime,timezone
from uuid import UUID
import re

from fastapi import APIRouter,BackgroundTasks,HTTPException
from pydantic import Field

from .database import connect
from .jobs import JobQueue
from .quant import QuantService,strategies
from .quant_contracts import (BacktestDefinition,CompareRequest,EdgeEvidenceRequest,GridRequest,
    MonteCarloRequest,Strict,WalkForwardDefinition)
from .quant_store import digest


class QuantJobRequest(Strict):
    operation: str=Field(pattern="^(backtest|walk_forward|sensitivity|robustness|monte_carlo|comparison)$")
    payload: dict = Field(max_length=50)


MODELS={"backtest":BacktestDefinition,"walk_forward":WalkForwardDefinition,"sensitivity":GridRequest,
        "robustness":BacktestDefinition,"monte_carlo":MonteCarloRequest,"comparison":CompareRequest}


def run_job(service,job_id):
    queue=JobQueue(service.catalog.dsn)
    job=queue.claim(3600,kind="quant_research",job_id=job_id)
    if not job:
        return
    try:
        op=job.payload["operation"]
        request=MODELS[op].model_validate(job.payload["payload"])
        result=getattr(service,"run" if op=="backtest" else "compare" if op=="comparison" else op)(request)
        result_id=result.run_id if hasattr(result,"run_id") else UUID(result["study_id"])
        with connect(service.catalog.dsn) as c:
            c.execute("UPDATE jobs SET result_ref=%s WHERE job_id=%s AND state='leased' AND attempts=%s",
                      (result_id,job.job_id,job.attempts))
        queue.finish(job.job_id,job.attempts)
    except Exception as exc:
        # Never persist exception text: it can contain DSNs, provider responses or private inputs.
        code=str(exc) if isinstance(exc,(ValueError,LookupError)) and re.fullmatch(r"[A-Z0-9_]{1,90}",str(exc)) else "QUANT_RESEARCH_FAILED"
        queue.finish(job.job_id,job.attempts,code,max_attempts=1)


def router_for(catalog,settings):
    router=APIRouter(prefix="/api/v1/quant",tags=["quant"])
    service=QuantService(catalog,settings.environment)
    def call(action):
        try:
            result=action()
            return result.model_dump(mode="json") if hasattr(result,"model_dump") else result
        except (ValueError,LookupError,KeyError) as exc:
            code=str(exc) if re.fullmatch(r"[A-Z0-9_]{1,90}",str(exc)) else "QUANT_REQUEST_FAILED"
            raise HTTPException(404 if isinstance(exc,LookupError) else 422,detail={"code":code}) from None

    @router.get("/strategies")
    def registry():
        return {"items":[s.model_dump(mode="json") for s in strategies()],"costs_are_assumptions":True}

    @router.get("/runs")
    def runs():
        return {"items":service.store.recent(),"search_counts":service.store.search_counts()}

    @router.get("/runs/{run_id}")
    def run(run_id:UUID):
        return call(lambda:service.store.get(run_id,"run"))

    @router.get("/runs/{run_id}/trades")
    def trades(run_id:UUID):
        return call(lambda:{"items":service.store.get(run_id,"run")["trades"]})

    @router.get("/runs/{run_id}/metrics")
    def metric(run_id:UUID):
        return call(lambda:service.store.get(run_id,"run")["metrics"])

    @router.post("/runs/{run_id}/replay")
    def replay(run_id:UUID):
        return call(lambda:service.replay(run_id))

    @router.get("/studies/{study_id}")
    def study(study_id:UUID):
        return call(lambda:service.store.get(study_id))

    @router.get("/studies")
    def studies():
        return {"items":[r for kind in ("walk_forward","sensitivity","robustness","monte_carlo","comparison") for r in service.store.recent(kind)]}

    @router.post("/jobs",status_code=202)
    def enqueue(request:QuantJobRequest,background:BackgroundTasks):
        from pydantic import ValidationError
        try:
            parsed=MODELS[request.operation].model_validate(request.payload)
        except ValidationError:
            raise HTTPException(422,detail={"code":"INVALID_QUANT_DEFINITION"}) from None
        definition=parsed.definition if hasattr(parsed,"definition") else parsed
        if hasattr(definition,"source_as_of") and definition.source_as_of>datetime.now(timezone.utc):
            raise HTTPException(422,detail={"code":"FUTURE_SOURCE_CUTOFF_FORBIDDEN"})
        value={"operation":request.operation,"payload":parsed.model_dump(mode="json")}
        job_id=JobQueue(catalog.dsn).enqueue("quant_research",f"quant:{digest(value)}",value)
        background.add_task(run_job,service,job_id)
        return {"job_id":str(job_id),"status":"queued"}

    @router.post("/jobs/{job_id}/retry",status_code=202)
    def retry(job_id:UUID,background:BackgroundTasks):
        with connect(catalog.dsn) as c:
            row=c.execute("UPDATE jobs SET state='ready',next_attempt_at=now(),error_code=NULL WHERE job_id=%s AND kind='quant_research' AND state='dead' RETURNING job_id",(job_id,)).fetchone()
        if row is None:
            raise HTTPException(422,detail={"code":"ONLY_FAILED_QUANT_JOBS_CAN_RETRY"})
        background.add_task(run_job,service,job_id)
        return {"job_id":str(job_id),"status":"queued"}

    @router.get("/jobs/{job_id}")
    def status(job_id:UUID):
        with connect(catalog.dsn) as c:
            row=c.execute("SELECT state,attempts,error_code,result_ref FROM jobs WHERE job_id=%s AND kind='quant_research'",(job_id,)).fetchone()
        if row is None:
            raise HTTPException(404,detail={"code":"QUANT_JOB_NOT_FOUND"})
        return {"job_id":str(job_id),"status":{"ready":"queued","leased":"running","done":"completed","dead":"failed"}[row[0]],
                "attempts":row[1],"error_code":row[2],"result_ref":str(row[3]) if row[3] else None}

    @router.post("/edges/evidence")
    def attach(request:EdgeEvidenceRequest):
        return call(lambda:service.attach_edge(request))
    return router
