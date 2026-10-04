"""Loopback-only, local portfolio research routes. No broker operations."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID, NAMESPACE_URL, uuid5

from fastapi import APIRouter, HTTPException, Query
from pydantic import Field, model_validator

from .config import Settings
from .opportunity_store import OpportunityStore
from .risk import RiskService, digest, research_sizing, run_scenario
from .risk_contracts import (OverlayRequest, PortfolioCreate, PositionChange,
                             PositionInput, RiskRequest, ScenarioDefinition,
                             SizingRequest, Strict)
from .storage import PostgresCatalog


class ScenarioRequest(Strict):
    risk: RiskRequest = Field(default_factory=RiskRequest)
    scenario: ScenarioDefinition


class ThesisRiskRequest(Strict):
    portfolio_id: UUID
    risk: RiskRequest = Field(default_factory=RiskRequest)
    quantity: Decimal = Field(gt=0)
    reference_price: Decimal = Field(gt=0)
    invalidation_price: Decimal | None = Field(default=None, gt=0)
    target_price: Decimal | None = Field(default=None, gt=0)
    scenario: ScenarioDefinition | None = None

    @model_validator(mode="after")
    def valid_long_levels(self) -> "ThesisRiskRequest":
        if self.invalidation_price is not None and self.invalidation_price >= self.reference_price:
            raise ValueError("LONG_INVALIDATION_MUST_BE_BELOW_ENTRY")
        if self.target_price is not None and self.target_price <= self.reference_price:
            raise ValueError("LONG_TARGET_MUST_BE_ABOVE_ENTRY")
        return self


def router_for(catalog: PostgresCatalog, settings: Settings) -> APIRouter:
    router = APIRouter(prefix="/api/v1/risk", tags=["risk"])
    service = RiskService(catalog, settings.environment)

    def error(exc: Exception) -> HTTPException:
        return HTTPException(404 if isinstance(exc, LookupError) else 422,
                             detail={"code": str(exc).splitlines()[0][:100]})

    @router.get("/portfolios")
    def portfolios() -> dict:
        return {"items": [item.model_dump(mode="json") for item in service.store.list()]}

    @router.post("/portfolios")
    def create(request: PortfolioCreate) -> dict:
        try:
            return service.store.create(request).model_dump(mode="json")
        except ValueError as exc:
            raise error(exc) from None

    @router.get("/portfolios/{portfolio_id}")
    def portfolio(portfolio_id: UUID, version: int | None = Query(None, ge=1)) -> dict:
        item = service.store.get(portfolio_id, version)
        if item is None:
            raise HTTPException(404, detail={"code":"PORTFOLIO_NOT_FOUND"})
        return item.model_dump(mode="json")

    @router.get("/portfolios/{portfolio_id}/versions")
    def versions(portfolio_id: UUID) -> dict:
        if service.store.get(portfolio_id) is None:
            raise HTTPException(404, detail={"code":"PORTFOLIO_NOT_FOUND"})
        return {"items": service.store.versions(portfolio_id)}

    @router.post("/portfolios/{portfolio_id}/positions")
    def change(portfolio_id: UUID, request: PositionChange) -> dict:
        prior = service.store.get(portfolio_id)
        if prior is None:
            raise HTTPException(404, detail={"code":"PORTFOLIO_NOT_FOUND"})
        try:
            service.validate_position(request.position, prior)
            return service.store.change(portfolio_id, request).model_dump(mode="json")
        except (ValueError, LookupError) as exc:
            raise error(exc) from None

    @router.post("/portfolios/{portfolio_id}/calculate")
    def calculate(portfolio_id: UUID, request: RiskRequest) -> dict:
        try:
            return service.snapshot(portfolio_id, request).model_dump(mode="json")
        except (LookupError, ValueError, KeyError) as exc:
            raise error(exc) from None

    @router.get("/snapshots/{snapshot_id}")
    def saved_snapshot(snapshot_id: UUID) -> dict:
        item = service.store.risk_snapshot(snapshot_id)
        if item is None:
            raise HTTPException(404, detail={"code":"RISK_SNAPSHOT_NOT_FOUND"})
        return item

    @router.post("/portfolios/{portfolio_id}/scenario")
    def scenario(portfolio_id: UUID, request: ScenarioRequest) -> dict:
        try:
            snapshot = service.snapshot(portfolio_id, request.risk.model_copy(update={"persist":False}))
            return run_scenario(snapshot, request.scenario).model_dump(mode="json")
        except (LookupError, ValueError, KeyError) as exc:
            raise error(exc) from None

    @router.post("/portfolios/{portfolio_id}/overlay")
    def overlay(portfolio_id: UUID, request: OverlayRequest) -> dict:
        try:
            return service.overlay(portfolio_id, request)
        except (LookupError, ValueError, KeyError) as exc:
            raise error(exc) from None

    @router.post("/sizing")
    def sizing(request: SizingRequest) -> dict:
        return {key: str(value) if isinstance(value, Decimal) else value
                for key, value in research_sizing(request).items()}

    @router.post("/theses/{thesis_id}/risk")
    def thesis_risk(thesis_id: UUID, request: ThesisRiskRequest) -> dict:
        versions = OpportunityStore(catalog.dsn).versions(thesis_id)
        if not versions:
            raise HTTPException(404, detail={"code":"THESIS_NOT_FOUND"})
        cutoff = request.risk.as_of or datetime.now(timezone.utc)
        visible = [item for item in versions if item.updated_at <= cutoff and item.as_of <= cutoff]
        if not visible:
            raise HTTPException(422, detail={"code":"THESIS_NOT_VISIBLE_AT_CUTOFF"})
        thesis = visible[-1]
        identities, _ = catalog.load_identity()
        instrument = next((item for item in identities if item.instrument_id == thesis.instrument_id), None)
        if instrument is None:
            raise HTTPException(422, detail={"code":"INSTRUMENT_NOT_FOUND"})
        position = PositionInput(position_id=uuid5(NAMESPACE_URL, digest({
            "route":"thesis_risk", "thesis_id":str(thesis_id),
            "portfolio_id":str(request.portfolio_id), "quantity":str(request.quantity),
            "entry":str(request.reference_price),
            "invalidation":str(request.invalidation_price),
            "manifest_id":str(request.risk.manifest_id),
            "as_of":request.risk.as_of.isoformat() if request.risk.as_of else None})),
            instrument_id=thesis.instrument_id,
            quantity=request.quantity, average_cost=request.reference_price,
            native_currency=instrument.trading_currency, opened_at=cutoff,
            thesis_id=thesis_id, invalidation_price=request.invalidation_price,
            target_price=request.target_price, source_type="manual")
        try:
            return service.overlay(request.portfolio_id,
                OverlayRequest(risk=request.risk.model_copy(update={"as_of":cutoff}), hypothetical_position=position,
                               scenario=request.scenario))
        except (LookupError, ValueError, KeyError) as exc:
            raise error(exc) from None

    return router
