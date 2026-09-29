"""Local read API. No provider credentials, broker operations, or write routes."""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta, timezone
from uuid import UUID, uuid4

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import JSONResponse

from .config import Settings
from .contracts import utc
from .database import connect
from .quality import disagreements
from .storage import ArtifactStore, PostgresCatalog

logger = logging.getLogger("market_cortex.api")


def create_app(settings: Settings | None = None, catalog: PostgresCatalog | None = None) -> FastAPI:
    settings = settings or Settings.load()
    app = FastAPI(title="MARKET CORTEX", version="0.1.0", docs_url="/docs", redoc_url=None)
    store = catalog or (PostgresCatalog(settings.database_url, ArtifactStore(settings.data_root)) if settings.database_url else None)

    @app.middleware("http")
    async def loopback_only(request: Request, call_next):
        if request.client and request.client.host not in ("127.0.0.1", "::1", "testclient"):
            return JSONResponse(status_code=403, content={"code": "LOCAL_ONLY"})
        return await call_next(request)

    def utc_or_422(value: datetime) -> datetime:
        try:
            return utc(value)
        except ValueError:
            raise HTTPException(422, detail={"code": "OFFSET_REQUIRED"}) from None

    def database() -> PostgresCatalog:
        if store is None:
            raise HTTPException(503, detail={"code": "DATABASE_NOT_CONFIGURED", "retryable": False})
        return store

    @app.exception_handler(Exception)
    async def internal_error(request: Request, error: Exception) -> JSONResponse:
        correlation_id = str(uuid4())
        # No exception string: it can contain a DSN, request URL, or credential.
        logger.error("internal_error correlation_id=%s error_type=%s", correlation_id, type(error).__name__)
        return JSONResponse(status_code=503, content={"code": "SERVICE_UNAVAILABLE",
                                                       "correlation_id": correlation_id, "retryable": True})

    @app.get("/api/v1/health")
    def health() -> dict:
        result = {"status": "ready" if store else "not_configured", "settings": settings.safe_summary()}
        if store:
            try:
                result["manifest_id"] = str(store.head()) if store.head() else None
            except Exception:
                result["status"] = "database_unavailable"
        return result

    @app.get("/api/v1/instruments")
    def instruments(query: str = Query(min_length=1, max_length=64), provider_id: str | None = None,
                    venue_id: str | None = None, as_of: datetime | None = None, limit: int = Query(50, ge=1, le=200)) -> dict:
        at = utc_or_422(as_of or datetime.now(timezone.utc))
        instruments_, mappings = database().load_identity()
        matches = [m for m in mappings if m.identifier_value.lower() == query.lower()
                   and (provider_id is None or m.provider_id == provider_id)
                   and (venue_id is None or m.venue_id == venue_id)
                   and m.valid_from <= at and (m.valid_to is None or at < m.valid_to)]
        by_id = {item.instrument_id: item for item in instruments_}
        rows = [{"instrument": by_id[m.instrument_id].model_dump(mode="json"),
                 "mapping": m.model_dump(mode="json")} for m in matches[:limit] if m.instrument_id in by_id]
        return {"items": rows, "ambiguous": len({m.instrument_id for m in matches}) > 1,
                "truncated": len(matches) > limit, "as_of": at.isoformat()}

    @app.get("/api/v1/calendars/{venue_id}/sessions")
    def sessions(venue_id: str, from_date: date = Query(alias="from"), to_date: date = Query(alias="to"),
                 calendar_id: str | None = None, version: str | None = None) -> dict:
        if from_date > to_date or (to_date - from_date).days > 366:
            raise HTTPException(422, detail={"code": "INVALID_CALENDAR_RANGE"})
        start = datetime.combine(from_date, datetime.min.time(), timezone.utc) - timedelta(days=1)
        end = datetime.combine(to_date + timedelta(days=1), datetime.min.time(), timezone.utc) + timedelta(days=1)
        from .calendar import CalendarMissing
        try:
            cal = database().load_calendar(venue_id, start, end, calendar_id, version)
            days = [cal.session(from_date + timedelta(days=offset)).model_dump(mode="json")
                    for offset in range((to_date - from_date).days + 1)]
        except CalendarMissing:
            raise HTTPException(404, detail={"code": "CALENDAR_COVERAGE_MISSING"}) from None
        return {"calendar_id": cal.calendar_id, "version": cal.version, "items": days}

    @app.get("/api/v1/bars")
    def bars(instrument_id: UUID, from_at: datetime = Query(alias="from"), to_at: datetime = Query(alias="to"),
             as_of: datetime | None = None, manifest_id: UUID | None = None, interval: str = "P1D",
             adjustment_basis: str = "raw", provider_id: str | None = None,
             offset: int = Query(0, ge=0), limit: int = Query(200, ge=1, le=500)) -> dict:
        if interval != "P1D":
            raise HTTPException(422, detail={"code": "UNSUPPORTED_RESOLUTION"})
        start, end = utc_or_422(from_at), utc_or_422(to_at)
        if start >= end:
            raise HTTPException(422, detail={"code": "INVALID_INTERVAL"})
        try:
            pinned, records = database().bars(instrument_id=instrument_id, start=start, end=end,
                                              as_of=utc_or_422(as_of or datetime.now(timezone.utc)),
                                              manifest_id=manifest_id, adjustment_basis=adjustment_basis,
                                              provider_id=provider_id)
        except KeyError:
            raise HTTPException(404, detail={"code": "MANIFEST_NOT_FOUND"}) from None
        conflicts = disagreements(records)
        return {"manifest_id": str(pinned) if pinned else None, "selection_policy": "all_providers_v1",
                "as_of": utc_or_422(as_of or datetime.now(timezone.utc)).isoformat(),
                "items": [b.model_dump(mode="json") for b in records[offset:offset + limit]],
                "next_offset": offset + limit if offset + limit < len(records) else None,
                "total": len(records),
                "conflicts": [{"session_date": str(c.session_date), "provider_ids": c.provider_ids,
                               "close_values": [str(v) for v in c.close_values]} for c in conflicts]}

    @app.get("/api/v1/manifests/{manifest_id}")
    def manifest(manifest_id: UUID) -> dict:
        try:
            artifacts = database().artifacts_for(manifest_id)
        except KeyError:
            raise HTTPException(404, detail={"code": "MANIFEST_NOT_FOUND"}) from None
        return {"manifest_id": str(manifest_id), "files_in_ancestry": [
            {"sha256": a.content_hash, "rows": a.row_count, "venue_id": a.venue_id,
             "min_event_at": a.min_event_at, "max_event_at": a.max_event_at} for a in artifacts]}

    @app.get("/api/v1/data-health")
    def data_health() -> dict:
        repo = database()
        with connect(repo.dsn) as connection:
            rows = connection.execute("""SELECT provider_id, count(*), max(end_at)
                FROM observations GROUP BY provider_id ORDER BY provider_id""").fetchall()
            quarantined = connection.execute("SELECT count(*) FROM quarantine").fetchone()[0]
            jobs = connection.execute("SELECT state, count(*) FROM jobs GROUP BY state ORDER BY state").fetchall()
        return {"manifest_id": str(repo.head()) if repo.head() else None, "providers": [
                    {"provider_id": row[0], "observations": row[1], "latest_end_at": row[2]} for row in rows],
                "quarantined": quarantined, "jobs": dict(jobs),
                "notice": "Latest event time is not a validated per-market freshness verdict."}

    return app


app = create_app()
