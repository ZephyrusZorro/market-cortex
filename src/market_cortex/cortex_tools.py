"""Allowlisted CORTEX domain tools backed by existing deterministic engines."""

from __future__ import annotations

import hashlib
import json
import re
import time
from dataclasses import dataclass
from datetime import date
from typing import Callable
from uuid import UUID

from pydantic import BaseModel, ConfigDict, field_validator

from .alignment import compare
from .cortex_contracts import Evidence, ResearchContext, ToolRun
from .features import FeatureEngine, FeatureRequest
from .market_state import MarketStateEngine, MarketStateRequest, PILOT_SYMBOLS
from .storage import PostgresCatalog
from .cortex_store import ResearchRunStore


def digest(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                     default=str).encode()).hexdigest()


class NoArguments(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SymbolArguments(BaseModel):
    model_config = ConfigDict(extra="forbid")
    symbol: str

    @field_validator("symbol")
    @classmethod
    def pilot_only(cls, value: str) -> str:
        if value not in PILOT_SYMBOLS:
            raise ValueError("UNSUPPORTED_PILOT_SYMBOL")
        return value


class PairArguments(BaseModel):
    model_config = ConfigDict(extra="forbid")
    target: str
    reference: str

    @field_validator("target", "reference")
    @classmethod
    def pilot_only(cls, value: str) -> str:
        if value not in PILOT_SYMBOLS:
            raise ValueError("UNSUPPORTED_PILOT_SYMBOL")
        return value


@dataclass(frozen=True)
class ToolSpec:
    tool_id: str
    version: str
    description: str
    input_schema: type[BaseModel]
    output_schema: type[BaseModel] = ToolRun
    allowed_scope: str = "binance_pilot_5_read_only"
    failure_states: tuple[str, ...] = ("insufficient", "unavailable")


SPECS = {
    "dataset.context": ToolSpec("dataset.context", "1.0.0", "Resolved manifest, cutoff and pilot coverage", NoArguments),
    "instrument.features": ToolSpec("instrument.features", "1.0.0", "Stored close and Phase 2 feature bundle", SymbolArguments),
    "market.state": ToolSpec("market.state", "1.0.0", "Phase 2 market state, regime and breadth", NoArguments),
    "asset.compare": ToolSpec("asset.compare", "1.0.0", "Phase 2 relative strength and correlation", PairArguments),
    "dataset.manifest": ToolSpec("dataset.manifest", "1.0.0", "Published manifest ancestry and files", NoArguments),
    "research.prior": ToolSpec("research.prior", "1.0.0", "Prior saved research, historical context only", SymbolArguments),
}


class ToolRegistry:
    def __init__(self, catalog: PostgresCatalog, context: ResearchContext):
        self.catalog = catalog
        self.context = context
        self.engine = FeatureEngine(catalog)
        self._loaded = {}

    def _evidence(self, tool_id: str, kind: str, label: str, *, value=None, symbol=None,
                  unit=None, session_date=None, source_id=None, version=None,
                  parameters=None, observation_id=None, quality=None, freshness=None,
                  coverage=None, reason=None, source_manifest_id=None,
                  source_as_of=None, source_recorded_at=None) -> Evidence:
        payload = {"tool_id": tool_id, "kind": kind, "label": label, "symbol": symbol,
                   "value": value, "unit": unit, "session_date": session_date,
                   "manifest_id": str(self.context.manifest_id), "as_of": self.context.as_of.isoformat(),
                   "source_id": source_id, "provider_id": "binance" if tool_id in
                   {"instrument.features", "market.state", "asset.compare"} else None,
                   "source_manifest_id": str(source_manifest_id) if source_manifest_id else None,
                   "source_as_of": source_as_of.isoformat() if source_as_of else None,
                   "source_recorded_at": source_recorded_at.isoformat() if source_recorded_at else None,
                   "version": version, "parameters": parameters or {},
                   "observation_id": str(observation_id) if observation_id else None,
                   "quality": quality, "freshness": freshness, "coverage": coverage, "reason": reason}
        return Evidence(evidence_id=digest(payload)[:20], tool_id=tool_id, kind=kind,
                        label=label, symbol=symbol, instrument_id=self.context.members.get(symbol),
                        value=value, unit=unit, session_date=session_date,
                        manifest_id=self.context.manifest_id, as_of=self.context.as_of,
                        source_id=source_id, version=version, parameters=parameters or {},
                        provider_id=payload["provider_id"],
                        source_manifest_id=source_manifest_id,
                        source_as_of=source_as_of, source_recorded_at=source_recorded_at,
                        observation_id=observation_id, quality=quality, freshness=freshness,
                        coverage=coverage, reason=reason)

    def execute(self, tool_id: str, arguments: dict) -> ToolRun:
        if tool_id not in SPECS:
            raise ValueError("TOOL_NOT_APPROVED")
        spec = SPECS[tool_id]
        parsed = spec.input_schema.model_validate(arguments)
        started = time.perf_counter()
        action: dict[str, Callable] = {
            "dataset.context": self._context, "instrument.features": self._features,
            "market.state": self._state, "asset.compare": self._compare,
            "dataset.manifest": self._manifest, "research.prior": self._prior}
        evidence = action[tool_id](parsed)
        status = "ok" if evidence and any(item.value is not None for item in evidence) else "insufficient"
        values = [item.model_dump(mode="json") for item in evidence]
        return ToolRun(tool_id=tool_id, version=spec.version, description=spec.description,
                       inputs={**parsed.model_dump(mode="json"),
                               "manifest_id": str(self.context.manifest_id),
                               "as_of": self.context.as_of.isoformat()},
                       status=status, evidence=evidence, output_hash=digest(values),
                       elapsed_ms=round((time.perf_counter() - started) * 1000, 2))

    def _context(self, _: NoArguments) -> list[Evidence]:
        return [self._evidence("dataset.context", "manifest", "Research manifest",
            value=str(self.context.manifest_id), source_id=str(self.context.manifest_id)),
            self._evidence("dataset.context", "availability", "Availability cutoff",
            value=self.context.as_of.isoformat(), unit="UTC"),
            self._evidence("dataset.context", "coverage", "Pilot members visible",
            value=len(self.context.members), unit="of 5", coverage=len(self.context.members) / 5),
            self._evidence("dataset.context", "environment", "Data environment",
            value=self.context.environment)]

    def _load(self, symbol: str):
        end_date = self.context.evaluation_date or self.context.member_last_sessions.get(symbol)
        if symbol not in self.context.members or end_date is None or self.context.history_start is None:
            return None
        if symbol not in self._loaded:
            self._loaded[symbol] = self.engine.load(instrument_id=self.context.members[symbol],
                start_date=self.context.history_start, end_date=end_date,
                as_of=self.context.as_of, manifest_id=self.context.manifest_id,
                provider_id="binance")
        return self._loaded[symbol]

    def _features(self, args: SymbolArguments) -> list[Evidence]:
        tool_id = "instrument.features"
        end_date = self.context.evaluation_date or self.context.member_last_sessions.get(args.symbol)
        loaded = self._load(args.symbol)
        if loaded is None:
            return [self._evidence(tool_id, "missing", "No visible observations", symbol=args.symbol,
                                   reason="NO_VISIBLE_OBSERVATIONS_AT_CUTOFF")]
        last = loaded.bars[-1] if loaded.bars else None
        result = []
        if last is not None:
            result.append(self._evidence(tool_id, "observation", "Latest stored close",
                symbol=args.symbol, value=float(last.close), unit=last.quote_currency,
                session_date=last.session_date, source_id=str(last.envelope.source_batch_id),
                observation_id=last.envelope.observation_id,
                quality=last.envelope.quality_state, freshness=loaded.freshness_state))
        specs = (("arithmetic_return", {}), ("rolling_return", {"period": 20}),
                 ("sma", {"period": 20}), ("sma", {"period": 50}),
                 ("rsi", {"period": 14}), ("annualized_volatility", {"period": 20}),
                 ("relative_volume", {"period": 20}), ("drawdown", {}),
                 ("macd_histogram", {}))
        for name, params in specs:
            series = self.engine.calculate(FeatureRequest(
                instrument_id=self.context.members[args.symbol], feature=name,
                start_date=self.context.history_start, end_date=end_date,
                as_of=self.context.as_of, manifest_id=self.context.manifest_id,
                provider_id="binance", parameters=params), loaded)
            point = series.points[-1] if series.points else None
            label = f"{name}({params['period']})" if "period" in params else name
            result.append(self._evidence(tool_id, "feature", label, symbol=args.symbol,
                value=point.value if point else None, unit=series.definition.unit,
                session_date=point.session_date if point else end_date,
                source_id=series.feature_id, version=series.definition.version,
                parameters=series.resolved_parameters,
                observation_id=point.observation_id if point else None,
                quality=point.input_quality if point else None, freshness=series.freshness,
                coverage=(series.observed_sessions / series.expected_sessions)
                    if series.expected_sessions else None,
                reason=point.reason if point else "NO_SESSION"))
        return result

    def _state(self, _: NoArguments) -> list[Evidence]:
        tool_id = "market.state"
        if self.context.evaluation_date is None or self.context.history_start is None:
            return [self._evidence(tool_id, "missing", "Market state unavailable",
                                   reason="INCOMPLETE_PILOT_UNIVERSE")]
        snapshot = MarketStateEngine(self.catalog).compute(MarketStateRequest(
            history_start=self.context.history_start, evaluation_date=self.context.evaluation_date,
            as_of=self.context.as_of, manifest_id=self.context.manifest_id))
        result = [self._evidence(tool_id, "regime", "Pilot regime", value=snapshot.regime.category,
                 source_id=snapshot.snapshot_id, version=snapshot.regime.rule_version,
                 reason=snapshot.regime.unknown_reason)]
        for dimension in snapshot.dimensions:
            result.append(self._evidence(tool_id, "dimension", dimension.name,
                value=dimension.category, source_id=snapshot.snapshot_id,
                version=dimension.rule_version, freshness=dimension.freshness,
                coverage=dimension.eligible_members / dimension.total_members
                    if dimension.total_members else None,
                reason=dimension.unknown_reason))
        if snapshot.breadth:
            result.append(self._evidence(tool_id, "breadth", "Pilot above SMA20",
                value=snapshot.breadth.above_sma.percentage, unit="percent",
                source_id=snapshot.breadth.snapshot_id,
                coverage=snapshot.breadth.above_sma.eligible / 5))
        return result

    def _compare(self, args: PairArguments) -> list[Evidence]:
        tool_id = "asset.compare"
        if args.target == args.reference:
            raise ValueError("COMPARISON_REQUIRES_DISTINCT_MEMBERS")
        left, right = self._load(args.target), self._load(args.reference)
        if left is None or right is None:
            return [self._evidence(tool_id, "missing", "Comparison unavailable",
                                   reason="NO_VISIBLE_OBSERVATIONS_AT_CUTOFF")]
        result = []
        for kind in ("relative_strength", "correlation"):
            series = compare(left, right, kind=kind, window=20 if kind == "relative_strength" else 60)
            point = series.points[-1] if series.points else None
            result.append(self._evidence(tool_id, "comparison", kind,
                symbol=args.target, value=point.value if point else None,
                unit="fractional_outperformance" if kind == "relative_strength" else "pearson_r",
                session_date=point.session_date if point else self.context.evaluation_date,
                source_id=series.result_id, version=series.calculation_version,
                parameters={"window": series.window},
                observation_id=point.target_observation_id if point else None,
                coverage=point.coverage if point else None,
                reason=point.unknown_reason if point else "NO_SESSION"))
        return result

    def _manifest(self, _: NoArguments) -> list[Evidence]:
        artifacts = self.catalog.artifacts_for(self.context.manifest_id)
        return [self._evidence("dataset.manifest", "manifest", "Immutable files in ancestry",
                value=len(artifacts), unit="files", source_id=str(self.context.manifest_id)),
                self._evidence("dataset.manifest", "manifest", "Rows in ancestry files",
                value=sum(item.row_count for item in artifacts), unit="rows",
                source_id=str(self.context.manifest_id))]

    def _prior(self, args: SymbolArguments) -> list[Evidence]:
        store = ResearchRunStore(self.catalog.dsn)
        rows = store.recent(symbol=args.symbol, limit=3, before=self.context.as_of)
        result = []
        for row in rows:
            prior = store.get(UUID(row["run_id"]))
            if prior is None:
                continue
            section = prior.answer.split("Conclusion\n", 1)
            summary = section[1].splitlines()[0] if len(section) == 2 else (
                prior.claims[0].text if prior.claims else "No recorded conclusion")
            summary = re.sub(r"\s*\[[a-f0-9]{20}\]", "", summary).removeprefix("- ").strip()[:300]
            result.append(self._evidence("research.prior", "prior_run", "Earlier research conclusion",
                symbol=args.symbol, value=summary, source_id=str(prior.run_id),
                version=prior.orchestration_version, source_manifest_id=prior.context.manifest_id,
                source_as_of=prior.context.as_of, source_recorded_at=prior.created_at,
                reason="HISTORICAL_CONTEXT_ONLY"))
        return result
