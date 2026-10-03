"""Manifest-pinned, deterministic Pilot 5 opportunity scans."""

from __future__ import annotations

import hashlib
import json
import math
import time
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from uuid import UUID, uuid5, NAMESPACE_URL

from .alignment import compare
from .features import AnalyticalSeries, FeatureEngine, FeatureRequest
from .market_state import MarketStateEngine, MarketStateRequest, PILOT_SYMBOLS
from .opportunity_contracts import Candidate, OpportunityEvidence, ScanRequest, ScanResult
from .opportunity_detectors import DETECTORS, UNSUPPORTED, Detector, condition, definitions
from .storage import PostgresCatalog
from .workstation import build_context


def _portable_source(path: Path) -> bytes:
    return path.read_bytes().replace(b"\r\n", b"\n")


CODE_HASH = hashlib.sha256(_portable_source(Path(__file__)) +
                           _portable_source(Path(__import__("market_cortex.opportunity_detectors", fromlist=["x"]).__file__))).hexdigest()


def _hash(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, default=str,
                                     separators=(",", ":")).encode()).hexdigest()


def _uuid(value: object) -> UUID:
    return uuid5(NAMESPACE_URL, _hash(value))


@dataclass(frozen=True)
class Metric:
    value: float | None
    unit: str | None
    source_id: str | None
    version: str | None
    parameters: dict[str, int | float]
    reason: str | None = None
    coverage: float | None = None


FEATURES: dict[str, tuple[str, dict[str, int | float]]] = {
    "return20": ("rolling_return", {"period": 20}),
    "return5": ("rolling_return", {"period": 5}),
    "rsi14": ("rsi", {"period": 14}),
    "macd_histogram": ("macd_histogram", {}),
    "ma_alignment": ("ma_alignment", {}),
    "relative_volume": ("relative_volume", {"period": 20}),
    "price_vs_ma20": ("price_vs_ma", {"period": 20}),
    "price_vs_ma50": ("price_vs_ma", {"period": 50}),
    "ma_slope20": ("ma_slope", {"period": 20, "slope_period": 5}),
    "volatility_percentile": ("volatility_percentile", {"period": 20, "rank_window": 90}),
    "bollinger_bandwidth": ("bollinger_bandwidth", {"period": 20}),
    "annualized_volatility": ("annualized_volatility", {"period": 20}),
    "drawdown": ("drawdown", {}),
}


class OpportunityService:
    def __init__(self, catalog: PostgresCatalog):
        self.catalog = catalog
        self.features = FeatureEngine(catalog)

    @staticmethod
    def detector_definitions():
        return definitions()

    def _context(self, request: ScanRequest) -> tuple[dict, UUID, datetime]:
        cutoff = request.as_of or datetime.now(timezone.utc)
        if request.mode == "latest" and request.manifest_id and request.manifest_id != self.catalog.head():
            raise LookupError("WORKSTATION_CONTEXT_CHANGED")
        context = build_context(self.catalog, as_of=cutoff, manifest_id=request.manifest_id)
        manifest_id = UUID(context["source_manifest_id"])
        if datetime.fromisoformat(context["manifest"]["created_at"]) > cutoff:
            raise ValueError("MANIFEST_NOT_YET_KNOWN_AT_CUTOFF")
        return context, manifest_id, cutoff

    def _candidate(self, *, detector: Detector, symbol: str, loaded: AnalyticalSeries,
                   metrics: dict[str, Metric], regime: str | None, state_id: str | None,
                   cutoff: datetime, state_date: date | None = None) -> Candidate:
        started = time.perf_counter()
        definition = detector.definition
        event_date = loaded.dates[-1] if loaded.dates else None
        bar = loaded.bars[-1] if loaded.bars else None
        coverage = sum(item is not None for item in loaded.bars) / len(loaded.bars) if loaded.bars else 0
        quality = bar.envelope.quality_state if bar else "unavailable"
        used = {r.metric for r in detector.triggers + detector.confirmations +
                detector.invalidations + detector.rejections}
        if definition.detector_id == "breakout":
            used.add("prior_high20")
        evidence = []
        for key in sorted(used):
            metric = metrics.get(key, Metric(None, None, None, None, {}, "METRIC_UNAVAILABLE"))
            evidence.append(OpportunityEvidence(evidence_id=_hash({"metric": key,
                "source": metric.source_id, "value": metric.value, "date": event_date,
                "manifest": loaded.manifest_id, "as_of": cutoff})[:24], metric=key,
                value=metric.value, unit=metric.unit, symbol=symbol,
                instrument_id=loaded.instrument.instrument_id, session_date=event_date,
                source_manifest_id=loaded.manifest_id, as_of=cutoff,
                source_id=metric.source_id, feature_version=metric.version,
                parameters=metric.parameters, quality=quality,
                freshness=loaded.freshness_state, coverage=metric.coverage,
                reason=metric.reason))
        ids = {item.metric: item.evidence_id for item in evidence}

        def conditions(rules, kind):
            result = []
            for rule in rules:
                value = metrics.get(rule.metric, Metric(None, None, None, None, {})).value
                dynamic = metrics.get("prior_high20", Metric(None, None, None, None, {})).value \
                    if definition.detector_id == "breakout" and rule.metric == "close" else None
                item = condition(rule, kind, value, ids.get(rule.metric, ""),
                                 dynamic_threshold=dynamic)
                if dynamic is not None and ids.get("prior_high20"):
                    item.evidence_ids.append(ids["prior_high20"])
                result.append(item)
            return result

        trigger = conditions(detector.triggers, "trigger")
        confirmation = conditions(detector.confirmations, "confirmation")
        invalidation = conditions(detector.invalidations, "invalidation")
        rejection = conditions(detector.rejections, "rejection")
        if definition.detector_id == "breakout" and metrics["prior_high20"].value is None:
            # A positive close does not establish a breakout without the prior range.
            for item in trigger + invalidation:
                if item.metric == "close":
                    item.met = None
        rejection_reasons = [item.description for item in rejection if item.met is True]
        contradictions = [item.description for item in rejection + invalidation if item.met is True]
        if loaded.freshness_state != "current":
            contradictions.append(f"SOURCE_NOT_CURRENT:{loaded.freshness_state}")
        if regime in (None, "insufficient_data"):
            contradictions.append("MARKET_STATE_UNAVAILABLE")
        if coverage < definition.minimum_coverage:
            rejection_reasons.append("SOURCE_COVERAGE_BELOW_90_PERCENT")
        if len([item for item in loaded.bars if item is not None]) < definition.minimum_history:
            rejection_reasons.append("INSUFFICIENT_VISIBLE_HISTORY")
        if definition.detector_id == "breakout" and metrics["prior_high20"].value is None:
            rejection_reasons.append("PRIOR_20_HIGH_UNAVAILABLE")
        missing = any(item.met is None for item in trigger + confirmation)
        history_missing = "INSUFFICIENT_VISIBLE_HISTORY" in rejection_reasons
        if history_missing or coverage < definition.minimum_coverage or bar is None:
            outcome, status = "insufficient_data", "WATCHING"
        elif any(item.met is False for item in trigger):
            outcome, status = "rejected", "NO_EDGE"
            rejection_reasons.append("TRIGGER_NOT_MET")
        elif missing:
            outcome, status = "insufficient_data", "WATCHING"
        elif rejection_reasons:
            outcome, status = "rejected", "AVOID"
        else:
            outcome = "candidate"
            met = sum(item.met is True for item in confirmation)
            status = "VALID" if met == len(confirmation) else \
                     "AWAITING_CONFIRMATION" if met == len(confirmation) - 1 else "DEVELOPING"
        if outcome == "candidate" and any(item.met is True for item in invalidation):
            status = "INVALIDATED"
        if status == "VALID" and (loaded.freshness_state != "current" or
                                   regime in (None, "insufficient_data") or quality not in ("valid", "corrected")):
            status = "WATCHING"
            contradictions.append("FRESHNESS_OR_MARKET_STATE_PREVENTS_VALID")
        if status == "VALID" and state_date is not None and state_date != event_date:
            status = "WATCHING"
            contradictions.append("MARKET_STATE_DATE_BEHIND_CANDIDATE")
        if status == "VALID" and detector.bias == "bullish" and regime and regime.startswith("downtrend"):
            status = "AWAITING_CONFIRMATION"
            contradictions.append("BROAD_MARKET_DOWNTREND")
        supporting = [ids[item.metric] for item in trigger + confirmation if item.met is True]
        opposing = [ids[item.metric] for item in trigger + confirmation + rejection + invalidation
                    if (item.met is False and item.kind in ("trigger", "confirmation")) or
                       (item.met is True and item.kind in ("rejection", "invalidation"))]
        strength = "weak" if outcome != "candidate" or status in ("WATCHING", "DEVELOPING") or \
                    loaded.freshness_state != "current" or regime in (None, "insufficient_data") or \
                    quality not in ("valid", "corrected") else \
                   "strong" if status == "VALID" and not contradictions else "moderate"
        identity = {"symbol": symbol, "instrument": str(loaded.instrument.instrument_id),
                    "detector": definition.detector_id, "version": definition.version,
                    "code": CODE_HASH, "manifest": str(loaded.manifest_id), "as_of": cutoff.isoformat(),
                    "event_date": str(event_date), "evidence": [item.model_dump(mode="json") for item in evidence],
                    "regime": regime, "state_id": state_id}
        evidence_hash = _hash(identity)
        semantic_identity = {"symbol": symbol, "detector": definition.detector_id,
            "detector_version": definition.version, "code": CODE_HASH,
            "manifest": str(loaded.manifest_id), "event_date": str(event_date),
            "observation_id": str(bar.envelope.observation_id) if bar else None,
            "metrics": {key: metric.value for key, metric in sorted(metrics.items())},
            "regime": regime, "status": status, "outcome": outcome,
            "freshness": loaded.freshness_state, "quality": quality}
        return Candidate(candidate_id=_uuid(semantic_identity), created_at=datetime.now(timezone.utc),
            instrument_id=loaded.instrument.instrument_id, symbol=symbol,
            detector_id=definition.detector_id, detector_version=definition.version,
            outcome=outcome, status=status, detector_strength=strength,
            event_date=event_date, as_of=cutoff, source_manifest_id=loaded.manifest_id,
            bias=detector.bias, reference_symbol="BTCUSDT" if definition.detector_id == "relative_strength" else None,
            market_regime=regime, market_state_id=state_id, evidence=evidence,
            trigger_conditions=trigger, confirmation_conditions=confirmation,
            invalidation_conditions=invalidation, rejection_conditions=rejection,
            supporting_evidence_ids=list(dict.fromkeys(supporting)),
            opposing_evidence_ids=list(dict.fromkeys(opposing)), contradictions=contradictions,
            rejection_reasons=rejection_reasons, coverage=coverage,
            freshness=loaded.freshness_state, data_quality=quality,
            evidence_hash=evidence_hash, elapsed_ms=round((time.perf_counter()-started)*1000, 3))

    @staticmethod
    def _unsupported(symbol: str, loaded: AnalyticalSeries, detector_id: str,
                     version: str, reason: str, cutoff: datetime, regime: str | None,
                     state_id: str | None) -> Candidate:
        event_date = loaded.dates[-1] if loaded.dates else None
        identity = {"symbol": symbol, "instrument": str(loaded.instrument.instrument_id),
            "detector": detector_id, "version": version,
            "manifest": str(loaded.manifest_id), "event_date": str(event_date),
            "outcome": "unsupported", "reason": reason}
        return Candidate(candidate_id=_uuid(identity), created_at=datetime.now(timezone.utc),
            instrument_id=loaded.instrument.instrument_id, symbol=symbol,
            detector_id=detector_id, detector_version=version, outcome="unsupported",
            status="NO_EDGE", detector_strength="weak", event_date=event_date,
            as_of=cutoff, source_manifest_id=loaded.manifest_id, bias="neutral",
            market_regime=regime, market_state_id=state_id, evidence=[],
            trigger_conditions=[], confirmation_conditions=[], invalidation_conditions=[],
            rejection_conditions=[], supporting_evidence_ids=[], opposing_evidence_ids=[],
            contradictions=[], rejection_reasons=[reason], coverage=0,
            freshness=loaded.freshness_state, data_quality="not_applicable",
            evidence_hash=_hash(identity), elapsed_ms=0)

    def scan(self, request: ScanRequest) -> ScanResult:
        started = time.perf_counter()
        if request.detector_id and request.detector_id not in DETECTORS and request.detector_id not in UNSUPPORTED:
            raise ValueError("UNKNOWN_DETECTOR")
        context, manifest_id, cutoff = self._context(request)
        selected = [request.symbol] if request.symbol else list(PILOT_SYMBOLS)
        detectors = [DETECTORS[request.detector_id]] if request.detector_id in DETECTORS else \
                    list(DETECTORS.values()) if request.detector_id is None else []
        members = {item["symbol"]: item for item in context["members"]}
        common_day = date.fromisoformat(context["evaluation_date"]) if context["evaluation_date"] else None
        regime, state_id = None, None
        if common_day and context["history_start"]:
            snapshot = MarketStateEngine(self.catalog).compute(MarketStateRequest(
                history_start=max(date.fromisoformat(context["history_start"]), common_day-timedelta(days=180)),
                evaluation_date=common_day, as_of=cutoff, manifest_id=manifest_id))
            regime, state_id = snapshot.regime.category, snapshot.snapshot_id
        loaded: dict[str, AnalyticalSeries] = {}
        for symbol in selected:
            member = members[symbol]
            if member["instrument_id"] and member["last_session"] and member["first_session"]:
                end = date.fromisoformat(member["last_session"])
                start = max(date.fromisoformat(member["first_session"]), end-timedelta(days=180))
                loaded[symbol] = self.features.load(instrument_id=UUID(member["instrument_id"]),
                    start_date=start, end_date=end, as_of=cutoff, manifest_id=manifest_id,
                    provider_id="binance")
        if request.detector_id == "relative_strength" and "BTCUSDT" not in loaded and members["BTCUSDT"]["instrument_id"]:
            member = members["BTCUSDT"]
            if member["last_session"] and member["first_session"]:
                end = date.fromisoformat(member["last_session"])
                loaded["BTCUSDT"] = self.features.load(instrument_id=UUID(member["instrument_id"]),
                    start_date=max(date.fromisoformat(member["first_session"]), end-timedelta(days=180)),
                    end_date=end, as_of=cutoff, manifest_id=manifest_id, provider_id="binance")
        feature_cache: dict[tuple[str, str], Metric] = {}

        def feature(symbol: str, name: str) -> Metric:
            key = (symbol, name)
            if key not in feature_cache:
                series = loaded[symbol]
                feature_name, params = FEATURES[name]
                output = self.features.calculate(FeatureRequest(instrument_id=series.instrument.instrument_id,
                    feature=feature_name, start_date=series.dates[0], end_date=series.dates[-1],
                    as_of=cutoff, manifest_id=manifest_id, provider_id="binance", parameters=params), series)
                point = output.points[-1]
                feature_cache[key] = Metric(point.value, output.definition.unit, output.feature_id,
                    output.definition.version, output.resolved_parameters, point.reason,
                    output.observed_sessions / output.expected_sessions if output.expected_sessions else 0)
            return feature_cache[key]

        candidates = []
        for symbol in selected:
            if symbol not in loaded:
                continue
            series = loaded[symbol]
            if request.detector_id in UNSUPPORTED:
                candidates.append(self._unsupported(symbol, series, request.detector_id,
                    "0.0.0", UNSUPPORTED[request.detector_id], cutoff, regime, state_id))
                continue
            for detector in detectors:
                name = detector.definition.detector_id
                if name == "relative_strength" and symbol == "BTCUSDT":
                    candidates.append(self._unsupported(symbol, series, name,
                        detector.definition.version, "REFERENCE_EQUALS_TARGET",
                        cutoff, regime, state_id))
                    continue
                metrics: dict[str, Metric] = {}
                needed = {rule.metric for rule in detector.triggers + detector.confirmations +
                          detector.invalidations + detector.rejections}
                for metric in needed:
                    if metric in FEATURES:
                        metrics[metric] = feature(symbol, metric)
                bar = series.bars[-1] if series.bars else None
                if "close" in needed:
                    metrics["close"] = Metric(float(bar.close) if bar else None, "USDT",
                        str(bar.envelope.observation_id) if bar else None, None, {},
                        None if bar else "NO_VISIBLE_BAR")
                if name == "breakout":
                    prior = series.bars[-21:-1]
                    prior_high = max(float(item.high) for item in prior) if len(prior) == 20 and all(prior) else None
                    metrics["prior_high20"] = Metric(prior_high, "USDT", _hash([str(item.envelope.observation_id)
                        for item in prior]) if prior_high is not None else None, "prior_range_v1", {"period":20},
                        None if prior_high is not None else "INCOMPLETE_PRIOR_RANGE")
                if name == "relative_strength":
                    reference = loaded.get("BTCUSDT")
                    if reference:
                        result = compare(series, reference, kind="relative_strength", window=20)
                        point = result.points[-1]
                        metrics["relative_strength_btc20"] = Metric(point.value, "fraction",
                            result.result_id, result.calculation_version, {"window":20},
                            point.unknown_reason, point.coverage)
                    else:
                        metrics["relative_strength_btc20"] = Metric(None,"fraction",None,None,{},
                                                                       "BTC_REFERENCE_UNAVAILABLE")
                candidates.append(self._candidate(detector=detector, symbol=symbol,
                    loaded=series, metrics=metrics, regime=regime, state_id=state_id,
                    cutoff=cutoff, state_date=common_day))
        counts = {key: sum(item.outcome == key for item in candidates)
                  for key in ("candidate", "rejected", "insufficient_data", "unsupported")}
        result = ScanResult(scan_id=_uuid({"manifest": manifest_id, "as_of": cutoff,
            "symbol": request.symbol, "detector": request.detector_id,
            "candidates": [item.candidate_id for item in candidates]}),
            created_at=datetime.now(timezone.utc), request=request, source_manifest_id=manifest_id,
            as_of=cutoff, evaluation_date=common_day, market_regime=regime,
            candidates=candidates, counts=counts, elapsed_ms=round((time.perf_counter()-started)*1000, 3))
        result.unavailable_members = [symbol for symbol in selected if symbol not in loaded]
        if request.record:
            from .opportunity_store import OpportunityStore
            result.recorded_events = OpportunityStore(self.catalog.dsn).record_scan(result)
        return result
