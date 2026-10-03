"""Read-only, manifest-aware view models for the local research workstation.

These routes compose existing catalog and Phase 2 calculations. They never
compute financial indicators independently or modify Phase 1 evidence.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query

from .alignment import compare
from .database import connect
from .features import FeatureEngine, FeatureRequest
from .identity import IdentityRegistry, IdentityError
from .market_state import MarketStateEngine, MarketStateRequest, PILOT_SYMBOLS
from .storage import PostgresCatalog


def _cutoff(value: datetime | None) -> datetime:
    if value is None:
        return datetime.now(timezone.utc)
    if value.tzinfo is None or value.utcoffset() is None:
        raise HTTPException(422, detail={"code": "OFFSET_REQUIRED"})
    return value.astimezone(timezone.utc)


def _error(error: Exception) -> HTTPException:
    if isinstance(error, KeyError):
        return HTTPException(404, detail={"code": "MANIFEST_NOT_FOUND"})
    if isinstance(error, LookupError):
        return HTTPException(404, detail={"code": str(error).splitlines()[0][:80]})
    return HTTPException(422, detail={"code": str(error).splitlines()[0][:80]})


def build_context(catalog: PostgresCatalog, *, as_of: datetime,
                  manifest_id: UUID | None = None) -> dict:
    pinned = manifest_id or catalog.head()
    if pinned is None:
        raise LookupError("DATASET_EMPTY")
    instruments, mappings = catalog.load_identity()
    registry = IdentityRegistry(instruments, mappings)
    members: list[dict] = []
    with connect(catalog.dsn) as connection:
        manifest = connection.execute("""SELECT manifest_id, parent_manifest_id, created_at, schema_version,
            selection_policy_version FROM dataset_manifests WHERE manifest_id = %s""", (pinned,)).fetchone()
        if manifest is None:
            raise KeyError("manifest not found")
        available = connection.execute("""SELECT manifest_id, parent_manifest_id, created_at
            FROM dataset_manifests ORDER BY created_at DESC LIMIT 30""").fetchall()
        for symbol in PILOT_SYMBOLS:
            try:
                instrument = registry.resolve(provider_id="binance", identifier_type="exchange_pair",
                                              identifier_value=symbol, at=as_of, known_at=as_of)
            except IdentityError:
                members.append({"symbol": symbol, "instrument_id": None, "currency": None,
                                "first_session": None, "last_session": None, "observed_sessions": 0,
                                "status": "MAPPING_UNAVAILABLE_AT_CUTOFF"})
                continue
            row = connection.execute("""WITH RECURSIVE chain AS (
                SELECT manifest_id, parent_manifest_id FROM dataset_manifests WHERE manifest_id = %s
                UNION ALL SELECT m.manifest_id, m.parent_manifest_id FROM dataset_manifests m
                JOIN chain ON chain.parent_manifest_id = m.manifest_id)
                SELECT min(o.session_date), max(o.session_date), count(DISTINCT o.session_date)
                FROM observations o JOIN chain ON o.manifest_id = chain.manifest_id
                WHERE o.instrument_id = %s AND o.provider_id = 'binance' AND o.interval = 'P1D'
                  AND o.adjustment_basis = 'raw' AND o.quality_state IN ('valid', 'corrected')
                  AND o.available_at <= %s""", (pinned, instrument.instrument_id, as_of)).fetchone()
            first, last, count = row
            members.append({"symbol": symbol, "instrument_id": str(instrument.instrument_id),
                            "currency": instrument.trading_currency,
                            "venue_id": instrument.primary_venue_id,
                            "first_session": first.isoformat() if first else None,
                            "last_session": last.isoformat() if last else None,
                            "observed_sessions": count,
                            "status": "available" if count else "NO_VISIBLE_OBSERVATIONS"})
    firsts = [date.fromisoformat(item["first_session"]) for item in members if item["first_session"]]
    lasts = [date.fromisoformat(item["last_session"]) for item in members if item["last_session"]]
    # The common evaluation date is never later than the least current member.
    common_date = min(lasts).isoformat() if len(lasts) == len(PILOT_SYMBOLS) else None
    return {"universe_id": "binance_pilot_5", "universe_label": "Binance Pilot 5",
            "source_manifest_id": str(pinned), "head_manifest_id": str(catalog.head()),
            "manifest": {"manifest_id": str(manifest[0]),
                         "parent_manifest_id": str(manifest[1]) if manifest[1] else None,
                         "created_at": manifest[2].isoformat(), "schema_version": manifest[3],
                         "selection_policy_version": manifest[4]},
            "recent_manifests": [{"manifest_id": str(row[0]),
                                  "parent_manifest_id": str(row[1]) if row[1] else None,
                                  "created_at": row[2].isoformat()} for row in available],
            "as_of": as_of.isoformat(), "evaluation_date": common_date,
            "history_start": min(firsts).isoformat() if firsts else None,
            "members": members,
            "providers": [
                {"provider_id": "binance", "label": "Binance public daily bars",
                 "status": "VALIDATED_PUBLIC" if any(item["observed_sessions"] for item in members) else "DATA_UNAVAILABLE",
                 "credential_state": "PUBLIC_NO_CREDENTIAL", "interval": "P1D"},
                {"provider_id": "upstox", "label": "Upstox adapter",
                 "status": "DEFERRED_NOT_CONFIGURED", "credential_state": "NOT_CONFIGURED", "interval": "P1D"},
                {"provider_id": "alpaca", "label": "Alpaca adapter",
                 "status": "DEFERRED_NOT_CONFIGURED", "credential_state": "NOT_CONFIGURED", "interval": "P1D"}],
            "display": {"primary_currency": "INR", "secondary_currency": "USD",
                        "native_prices_only": True, "timezone": "Asia/Kolkata"}}


def _feature(engine: FeatureEngine, loaded, name: str, start: date, end: date,
             **parameters: int | float) -> dict:
    result = engine.calculate(FeatureRequest(instrument_id=loaded.instrument.instrument_id,
        feature=name, start_date=start, end_date=end, as_of=loaded.as_of,
        manifest_id=loaded.manifest_id, provider_id=loaded.provider_id,
        adjustment_basis=loaded.adjustment_basis, parameters=parameters), loaded)
    point = result.points[-1] if result.points else None
    return {"feature_id": result.feature_id, "name": name,
            "value": point.value if point else None, "reason": point.reason if point else "NO_SESSION",
            "unit": result.definition.unit, "version": result.definition.version,
            "calculation_version": result.definition.calculation_version,
            "parameters": result.resolved_parameters, "observed_sessions": result.observed_sessions,
            "expected_sessions": result.expected_sessions, "freshness": result.freshness,
            "source_manifest_id": str(result.source_manifest_id)}


def router_for(catalog: PostgresCatalog) -> APIRouter:
    router = APIRouter(prefix="/api/v1/workstation", tags=["workstation"])

    @router.get("/context")
    def context(as_of: datetime | None = None, manifest_id: UUID | None = None) -> dict:
        try:
            return build_context(catalog, as_of=_cutoff(as_of), manifest_id=manifest_id)
        except (KeyError, LookupError, ValueError) as error:
            raise _error(error) from None

    @router.get("/overview")
    def overview(as_of: datetime | None = None, manifest_id: UUID | None = None) -> dict:
        cutoff = _cutoff(as_of)
        try:
            ctx = build_context(catalog, as_of=cutoff, manifest_id=manifest_id)
            if not ctx["evaluation_date"] or not ctx["history_start"]:
                return {"context": ctx, "items": [], "state": None,
                        "reason": "INCOMPLETE_PILOT_UNIVERSE"}
            end, start = date.fromisoformat(ctx["evaluation_date"]), date.fromisoformat(ctx["history_start"])
            engine = FeatureEngine(catalog)
            items = []
            for member in ctx["members"]:
                loaded = engine.load(instrument_id=UUID(member["instrument_id"]),
                    start_date=start, end_date=end, as_of=cutoff,
                    manifest_id=UUID(ctx["source_manifest_id"]), provider_id="binance")
                latest = loaded.bars[-1] if loaded.bars else None
                values = {name: _feature(engine, loaded, name, start, end, **parameters)
                          for name, parameters in (("arithmetic_return", {}), ("rolling_return", {"period": 20}),
                                                   ("sma", {"period": 20}), ("rsi", {"period": 14}),
                                                   ("annualized_volatility", {"period": 20}),
                                                   ("relative_volume", {"period": 20}))}
                items.append({**member, "session_date": end.isoformat(),
                              "close": float(latest.close) if latest else None,
                              "observation_id": str(latest.envelope.observation_id) if latest else None,
                              "quality": latest.envelope.quality_state if latest else "unavailable",
                              "freshness": loaded.freshness_state, "features": values})
            state = MarketStateEngine(catalog).compute(MarketStateRequest(
                history_start=start, evaluation_date=end, as_of=cutoff,
                manifest_id=UUID(ctx["source_manifest_id"])))
            return {"context": ctx, "items": items, "state": state.model_dump(mode="json")}
        except (KeyError, LookupError, ValueError) as error:
            raise _error(error) from None

    @router.get("/instrument/{instrument_id}")
    def instrument_view(instrument_id: UUID, from_date: date = Query(alias="from"),
                        to_date: date = Query(alias="to"), as_of: datetime | None = None,
                        manifest_id: UUID | None = None) -> dict:
        if from_date > to_date or (to_date - from_date).days > 5000:
            raise HTTPException(422, detail={"code": "INVALID_CHART_WINDOW"})
        cutoff = _cutoff(as_of)
        try:
            ctx = build_context(catalog, as_of=cutoff, manifest_id=manifest_id)
            member = next((item for item in ctx["members"] if item["instrument_id"] == str(instrument_id)), None)
            if member is None:
                raise LookupError("UNSUPPORTED_INSTRUMENT")
            engine = FeatureEngine(catalog)
            loaded = engine.load(instrument_id=instrument_id, start_date=from_date, end_date=to_date,
                                 as_of=cutoff, manifest_id=UUID(ctx["source_manifest_id"]), provider_id="binance")
            bars = [{"session_date": bar.session_date.isoformat(), "open": float(bar.open),
                     "high": float(bar.high), "low": float(bar.low), "close": float(bar.close),
                     "volume": float(bar.volume) if bar.volume is not None else None,
                     "observation_id": str(bar.envelope.observation_id),
                     "source_batch_id": str(bar.envelope.source_batch_id),
                     "available_at": bar.envelope.available_at.isoformat() if bar.envelope.available_at else None,
                     "quality": bar.envelope.quality_state, "currency": bar.quote_currency}
                    for bar in loaded.bars if bar is not None]
            specs = (("sma", {"period": 20}), ("sma", {"period": 50}),
                     ("ema", {"period": 20}), ("bollinger_upper", {"period": 20}),
                     ("bollinger_lower", {"period": 20}), ("rsi", {"period": 14}),
                     ("macd_histogram", {}), ("atr", {"period": 14}),
                     ("annualized_volatility", {"period": 20}), ("relative_volume", {"period": 20}),
                     ("drawdown", {}))
            features = {}
            for name, parameters in specs:
                result = engine.calculate(FeatureRequest(instrument_id=instrument_id, feature=name,
                    start_date=from_date, end_date=to_date, as_of=cutoff,
                    manifest_id=UUID(ctx["source_manifest_id"]), provider_id="binance",
                    parameters=parameters), loaded)
                key = f"{name}_{parameters['period']}" if "period" in parameters else name
                features[key] = {"feature_id": result.feature_id, "unit": result.definition.unit,
                    "parameters": result.resolved_parameters, "version": result.definition.version,
                    "calculation_version": result.definition.calculation_version,
                    "freshness": result.freshness, "observed_sessions": result.observed_sessions,
                    "expected_sessions": result.expected_sessions,
                    "points": [{"session_date": point.session_date.isoformat(), "value": point.value,
                                "reason": point.reason} for point in result.points]}
            return {"context": ctx, "instrument": member, "from": from_date.isoformat(),
                    "to": to_date.isoformat(), "bars": bars, "features": features,
                    "freshness": loaded.freshness_state,
                    "missing_sessions": [day.isoformat() for day in loaded.missing_dates]}
        except (KeyError, LookupError, ValueError) as error:
            raise _error(error) from None

    @router.get("/comparison")
    def comparison(instrument_ids: list[UUID] = Query(), from_date: date = Query(alias="from"),
                   to_date: date = Query(alias="to"), window: int = Query(60, ge=2, le=365),
                   as_of: datetime | None = None, manifest_id: UUID | None = None) -> dict:
        if not 2 <= len(instrument_ids) <= 5 or len(set(instrument_ids)) != len(instrument_ids) or from_date > to_date:
            raise HTTPException(422, detail={"code": "INVALID_COMPARISON_SELECTION"})
        cutoff = _cutoff(as_of)
        try:
            ctx = build_context(catalog, as_of=cutoff, manifest_id=manifest_id)
            allowed = {UUID(item["instrument_id"]): item["symbol"] for item in ctx["members"] if item["instrument_id"]}
            if any(item not in allowed for item in instrument_ids):
                raise LookupError("UNSUPPORTED_INSTRUMENT")
            engine = FeatureEngine(catalog)
            loaded = {item: engine.load(instrument_id=item, start_date=from_date, end_date=to_date,
                                       as_of=cutoff, manifest_id=UUID(ctx["source_manifest_id"]),
                                       provider_id="binance") for item in instrument_ids}
            performance = {}
            for item in instrument_ids:
                result = engine.calculate(FeatureRequest(instrument_id=item, feature="cumulative_return",
                    start_date=from_date, end_date=to_date, as_of=cutoff,
                    manifest_id=UUID(ctx["source_manifest_id"]), provider_id="binance"), loaded[item])
                performance[allowed[item]] = [{"session_date": p.session_date.isoformat(), "value": p.value}
                                              for p in result.points]
            matrix = []
            for left in instrument_ids:
                row = []
                for right in instrument_ids:
                    result = compare(loaded[left], loaded[right], kind="correlation", window=window)
                    point = result.points[-1] if result.points else None
                    row.append({"target": allowed[left], "reference": allowed[right],
                                "value": point.value if point else None,
                                "count": point.observation_count if point else 0,
                                "coverage": point.coverage if point else 0,
                                "missingness": point.missingness if point else 1,
                                "stability": point.stability if point else None,
                                "reason": point.unknown_reason if point else "NO_SESSION",
                                "result_id": result.result_id,
                                "version": result.calculation_version})
                matrix.append(row)
            return {"context": ctx, "members": [allowed[item] for item in instrument_ids],
                    "window": window, "from": from_date.isoformat(), "to": to_date.isoformat(),
                    "alignment_policy": "same_session", "performance": performance, "matrix": matrix}
        except (KeyError, LookupError, ValueError) as error:
            raise _error(error) from None

    @router.get("/manifest/{manifest_id}")
    def manifest_view(manifest_id: UUID) -> dict:
        try:
            artifacts = catalog.artifacts_for(manifest_id)
            with connect(catalog.dsn) as connection:
                row = connection.execute("""SELECT parent_manifest_id, created_at, schema_version,
                    selection_policy_version FROM dataset_manifests WHERE manifest_id = %s""", (manifest_id,)).fetchone()
                if row is None:
                    raise KeyError("manifest not found")
                batches = connection.execute("""WITH RECURSIVE chain AS (
                    SELECT manifest_id, parent_manifest_id FROM dataset_manifests WHERE manifest_id = %s
                    UNION ALL SELECT m.manifest_id, m.parent_manifest_id FROM dataset_manifests m
                    JOIN chain ON chain.parent_manifest_id = m.manifest_id)
                    SELECT o.provider_id, count(DISTINCT o.source_batch_id), count(*)
                    FROM observations o JOIN chain ON o.manifest_id = chain.manifest_id
                    GROUP BY o.provider_id ORDER BY o.provider_id""", (manifest_id,)).fetchall()
            return {"manifest_id": str(manifest_id), "parent_manifest_id": str(row[0]) if row[0] else None,
                    "created_at": row[1].isoformat(), "schema_version": row[2],
                    "selection_policy_version": row[3], "file_count": len(artifacts),
                    "rows_in_files": sum(item.row_count for item in artifacts),
                    "files": [{"sha256": item.content_hash, "rows": item.row_count,
                               "venue_id": item.venue_id, "min_event_at": item.min_event_at.isoformat(),
                               "max_event_at": item.max_event_at.isoformat()}
                              for item in artifacts],
                    "providers": [{"provider_id": item[0], "source_batches": item[1],
                                   "observations": item[2]} for item in batches],
                    "storage": catalog.scan_storage()}
        except KeyError as error:
            raise _error(error) from None

    return router
