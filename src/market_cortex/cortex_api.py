"""Local CORTEX research and research-run inspection API."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException, Query

from .config import Settings
from .cortex import CortexService
from .cortex_contracts import ResearchRequest
from .cortex_tools import SPECS
from .market_state import PILOT_SYMBOLS
from .storage import PostgresCatalog


def router_for(catalog: PostgresCatalog, settings: Settings) -> APIRouter:
    router = APIRouter(prefix="/api/v1/cortex", tags=["cortex"])
    service = CortexService(catalog, settings)

    @router.get("/status")
    def status() -> dict:
        return {"status": "ready", "environment": settings.environment,
                "model_provider": service.gateway.provider,
                "model_locality": service.gateway.locality,
                "deterministic_fallback": True, "orchestration_version": "cortex_orchestrator_v1"}

    @router.get("/tools")
    def tools() -> dict:
        return {"items": [{"tool_id": item.tool_id, "version": item.version,
            "description": item.description, "input_schema": item.input_schema.model_json_schema(),
            "output_schema": item.output_schema.model_json_schema(),
            "allowed_scope": item.allowed_scope, "failure_states": item.failure_states}
            for item in SPECS.values()]}

    @router.post("/research")
    def research(request: ResearchRequest) -> dict:
        try:
            return service.research(request).model_dump(mode="json")
        except (LookupError, ValueError) as error:
            code = str(error).splitlines()[0][:80]
            raise HTTPException(422 if isinstance(error, ValueError) else 404,
                                detail={"code": code}) from None

    @router.get("/runs")
    def recent_runs(symbol: str | None = None, limit: int = Query(20, ge=1, le=50)) -> dict:
        if symbol is not None and symbol not in PILOT_SYMBOLS:
            raise HTTPException(422, detail={"code": "UNSUPPORTED_PILOT_SYMBOL"})
        return {"items": service.store.recent(symbol=symbol, limit=limit)}

    @router.get("/runs/{run_id}")
    def get_run(run_id: UUID) -> dict:
        run = service.store.get(run_id)
        if run is None:
            raise HTTPException(404, detail={"code": "RESEARCH_RUN_NOT_FOUND"})
        return run.model_dump(mode="json")

    @router.get("/runs/{run_id}/replay")
    def replay(run_id: UUID) -> dict:
        try:
            return service.replay(run_id)
        except LookupError:
            raise HTTPException(404, detail={"code": "RESEARCH_RUN_NOT_FOUND"}) from None

    return router
