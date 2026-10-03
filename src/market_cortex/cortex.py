"""Single-orchestrator, evidence-grounded CORTEX v1 research."""

from __future__ import annotations

import re
import time
from datetime import date, datetime, time as daytime, timedelta, timezone
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

from .config import Settings
from .cortex_contracts import Claim, Evidence, ResearchContext, ResearchRequest, ResearchRun, ToolRun
from .cortex_gateway import ModelGateway, NoModelGateway, gateway_from_environment, may_send_context
from .cortex_store import ResearchRunStore
from .cortex_tools import SPECS, ToolRegistry, digest
from .market_state import PILOT_SYMBOLS
from .storage import PostgresCatalog
from .workstation import build_context


ORCHESTRATION_VERSION = "cortex_orchestrator_v1"


def _claim(kind: str, text: str, evidence: list[Evidence], stance: str = "neutral") -> Claim:
    ids = [item.evidence_id for item in evidence]
    return Claim(claim_id=digest({"kind": kind, "text": text, "ids": ids})[:20],
                 type=kind, text=text, evidence_ids=ids, stance=stance)


def _number(value: float | int | str | None, digits: int = 2) -> str:
    if not isinstance(value, (float, int)):
        return "unavailable"
    return f"{value:,.{digits}f}"


def _percent(value: float | int | str | None, digits: int = 1) -> str:
    return f"{value * 100:+.{digits}f}%" if isinstance(value, (float, int)) else "unavailable"


def _natural_cutoff(question: str) -> datetime | None:
    match = re.search(r"\bas of\s+(\d{4}-\d{2}-\d{2}|[A-Za-z]+\s+\d{1,2},?\s+\d{4})", question, re.I)
    if not match:
        return None
    raw = match.group(1).replace(",", "")
    try:
        day = date.fromisoformat(raw) if raw[0].isdigit() else datetime.strptime(raw, "%B %d %Y").date()
    except ValueError:
        return None
    return datetime.combine(day, daytime(23, 59, 59), ZoneInfo("Asia/Kolkata")).astimezone(timezone.utc)


class CortexService:
    def __init__(self, catalog: PostgresCatalog, settings: Settings, *,
                 gateway: ModelGateway | None = None):
        self.catalog = catalog
        self.settings = settings
        self.gateway = gateway if gateway is not None else gateway_from_environment()
        self.store = ResearchRunStore(catalog.dsn)

    def _resolve(self, request: ResearchRequest) -> ResearchContext:
        cutoff = request.as_of or datetime.now(timezone.utc)
        if request.mode == "latest" and request.manifest_id is not None and request.manifest_id != self.catalog.head():
            raise LookupError("WORKSTATION_CONTEXT_CHANGED")
        context = build_context(self.catalog, as_of=cutoff,
                                manifest_id=request.manifest_id)
        present = {item["symbol"]: UUID(item["instrument_id"]) for item in context["members"]
                   if item["instrument_id"]}
        tokens = re.findall(r"\b[A-Z]{2,8}(?:USDT)?\b", request.question.upper())
        mentioned = [item for item in PILOT_SYMBOLS if item in tokens or item.removesuffix("USDT") in tokens]
        unsupported = [item for item in tokens if item.endswith("USDT") and item not in PILOT_SYMBOLS]
        if unsupported:
            raise LookupError("UNSUPPORTED_PILOT_SYMBOL")
        symbol = request.symbol or (mentioned[0] if mentioned else None)
        second = request.compare_symbol or next((item for item in mentioned if item != symbol), None)
        if symbol and symbol not in present:
            # The mapping itself can be unavailable at a historical cutoff.
            second = None
        return ResearchContext(mode=request.mode, manifest_id=UUID(context["source_manifest_id"]),
            as_of=cutoff, evaluation_date=date.fromisoformat(context["evaluation_date"])
                if context["evaluation_date"] else None,
            history_start=date.fromisoformat(context["history_start"])
                if context["history_start"] else None,
            members=present, symbol=symbol, compare_symbol=second,
            environment=self.settings.environment, base_currency=self.settings.base_currency)

    def _plan(self, request: ResearchRequest, context: ResearchContext) -> list[tuple[str, dict, ResearchContext]]:
        question = request.question.lower()
        plan = [("dataset.context", {}, context)]
        if context.symbol:
            plan.append(("instrument.features", {"symbol": context.symbol}, context))
        market_question = any(term in question for term in ("market state", "regime", "breadth", "pilot", "trend", "volatility", "evidence"))
        if market_question or not context.symbol or request.depth == "deep":
            plan.append(("market.state", {}, context))
        if context.symbol and context.compare_symbol:
            plan.append(("instrument.features", {"symbol": context.compare_symbol}, context))
            plan.append(("asset.compare", {"target": context.symbol, "reference": context.compare_symbol}, context))
        if "relative strength" in question and any(word in question for word in ("which", "strongest", "five", "pilot")):
            for symbol in PILOT_SYMBOLS:
                if symbol in context.members and symbol != context.symbol:
                    plan.append(("instrument.features", {"symbol": symbol}, context))
        if request.depth == "deep":
            plan.append(("dataset.manifest", {}, context))
        if context.symbol and any(term in question for term in ("previous", "last week", "prior research", "conclude")):
            plan.append(("research.prior", {"symbol": context.symbol}, context))
        historical = request.older_manifest_id or ("one month ago" in question or "earlier manifest" in question)
        if historical and context.symbol:
            old_cutoff = context.as_of if request.older_manifest_id else context.as_of - timedelta(days=30)
            old_data = build_context(self.catalog, as_of=old_cutoff,
                                     manifest_id=request.older_manifest_id or context.manifest_id)
            old_context = ResearchContext(mode="historical", manifest_id=UUID(old_data["source_manifest_id"]),
                as_of=old_cutoff, evaluation_date=date.fromisoformat(old_data["evaluation_date"])
                    if old_data["evaluation_date"] else None,
                history_start=date.fromisoformat(old_data["history_start"])
                    if old_data["history_start"] else None,
                members={item["symbol"]: UUID(item["instrument_id"]) for item in old_data["members"]
                         if item["instrument_id"]}, symbol=context.symbol,
                compare_symbol=None, environment=context.environment,
                base_currency=context.base_currency)
            plan.append(("dataset.context", {}, old_context))
            plan.append(("instrument.features", {"symbol": context.symbol}, old_context))
            if "state" in question or "regime" in question:
                plan.append(("market.state", {}, old_context))
        # Tool selection is code-controlled, bounded, and deduplicated; no model tool calls.
        unique = {}
        for tool_id, args, ctx in plan:
            unique[(tool_id, digest(args), str(ctx.manifest_id), ctx.as_of.isoformat())] = (tool_id, args, ctx)
        return list(unique.values())[:14]

    def _collect(self, plan: list[tuple[str, dict, ResearchContext]]) -> tuple[list[ToolRun], list[str]]:
        tools, warnings = [], []
        registry_cache = {}
        for tool_id, arguments, context in plan:
            key = (context.manifest_id, context.as_of)
            registry = registry_cache.setdefault(key, ToolRegistry(self.catalog, context))
            try:
                tools.append(registry.execute(tool_id, arguments))
            except (LookupError, ValueError):
                warnings.append(f"{tool_id}:UNAVAILABLE")
                tools.append(ToolRun(tool_id=tool_id, version=SPECS[tool_id].version,
                    description=SPECS[tool_id].description,
                    inputs={**arguments, "manifest_id": str(context.manifest_id),
                            "as_of": context.as_of.isoformat()}, status="unavailable",
                    evidence=[], output_hash=digest([]), elapsed_ms=0))
        return tools, warnings

    def _claims(self, context: ResearchContext, tools: list[ToolRun]) -> list[Claim]:
        all_evidence = [item for run in tools for item in run.evidence]
        current = [item for item in all_evidence if item.manifest_id == context.manifest_id
                   and item.as_of == context.as_of]
        claims: list[Claim] = []

        def pick(label: str, symbol: str | None = None, source=current) -> Evidence | None:
            return next((item for item in source if item.label == label and
                         (symbol is None or item.symbol == symbol)), None)

        symbol = context.symbol
        if symbol:
            close = pick("Latest stored close", symbol)
            if close and close.value is not None:
                claims.append(_claim("OBSERVATION", f"{symbol} closed at {_number(close.value)} {close.unit} on {close.session_date}.",
                                     [close], "support"))
            for label, name in (("arithmetic_return", "daily return"),
                                ("rolling_return(20)", "20-session return")):
                item = pick(label, symbol)
                if item and item.value is not None:
                    claims.append(_claim("CALCULATION", f"{symbol} {name} was {_percent(item.value)}.",
                                         [item], "support" if item.value >= 0 else "counter"))
            sma = pick("sma(20)", symbol)
            if close and sma and close.value is not None and sma.value is not None:
                direction = "above" if close.value > sma.value else "below" if close.value < sma.value else "at"
                claims.append(_claim("INTERPRETATION",
                    f"{symbol} closed {direction} its {_number(sma.value)} {close.unit} SMA20.",
                    [close, sma], "support" if direction == "above" else "counter"))
            rsi = pick("rsi(14)", symbol)
            if rsi and rsi.value is not None:
                claims.append(_claim("CALCULATION", f"{symbol} RSI14 was {_number(rsi.value, 1)}.",
                                     [rsi], "neutral"))
            vol = pick("annualized_volatility(20)", symbol)
            if vol and vol.value is not None:
                claims.append(_claim("CALCULATION", f"{symbol} annualized 20-session volatility was {_percent(vol.value).lstrip('+')}.",
                                     [vol], "neutral"))
            drawdown = pick("drawdown", symbol)
            if drawdown and drawdown.value is not None and drawdown.value < -0.1:
                claims.append(_claim("LIMITATION", f"{symbol} remains {_percent(drawdown.value)} below its window peak.",
                                     [drawdown], "limitation"))
        regime = pick("Pilot regime")
        if regime and regime.value:
            claims.append(_claim("CLASSIFICATION", f"Binance Pilot 5 regime is {regime.value} under its versioned rules.",
                                 [regime], "neutral"))
        for name in ("trend", "momentum", "volatility", "breadth", "data_freshness", "uncertainty"):
            dimension = pick(name)
            if dimension and dimension.value:
                claims.append(_claim("CLASSIFICATION", f"Pilot {name.replace('_', ' ')} is {dimension.value}.",
                                     [dimension], "neutral"))
        relative = pick("relative_strength", symbol)
        if relative and relative.value is not None and context.compare_symbol:
            leader = symbol if relative.value > 0 else context.compare_symbol if relative.value < 0 else "neither"
            claims.append(_claim("INTERPRETATION",
                f"On the aligned 20-session relative-strength measure, {leader} led ({symbol} versus {context.compare_symbol}: {_percent(relative.value)} fractional outperformance).",
                [relative], "support"))
        correlation = pick("correlation", symbol)
        if correlation and correlation.value is not None and context.compare_symbol:
            claims.append(_claim("CALCULATION",
                f"{symbol}/{context.compare_symbol} 60-return Pearson correlation was {_number(correlation.value, 3)} with {_percent(correlation.coverage).lstrip('+')} coverage.",
                [correlation], "neutral"))
        ranked = [(item.symbol, item.value, item) for item in current
                  if item.label == "rolling_return(20)" and item.value is not None]
        if len(ranked) >= 3 and len({row[0] for row in ranked}) >= 3:
            top = max(ranked, key=lambda row: row[1])
            claims.append(_claim("INTERPRETATION",
                f"Among measured pilot members, {top[0]} had the strongest 20-session return at {_percent(top[1])}.",
                [row[2] for row in ranked], "support"))
        old = [item for item in all_evidence if item.manifest_id != context.manifest_id or item.as_of != context.as_of]
        if symbol and old:
            old_close = pick("Latest stored close", symbol, old)
            current_close = pick("Latest stored close", symbol)
            if old_close and current_close and old_close.value is not None and current_close.value is not None:
                claims.append(_claim("CALCULATION",
                    f"Compared with the older research context, {symbol} moved from {_number(old_close.value)} to {_number(current_close.value)} {current_close.unit}; the contexts use distinct manifest/cutoff evidence.",
                    [old_close, current_close], "neutral"))
            else:
                old_marker = pick("No visible observations", symbol, old)
                if old_marker:
                    claims.append(_claim("LIMITATION", "The earlier research context has no visible observations for this instrument.",
                                         [old_marker], "limitation"))
        for item in current:
            if item.kind == "prior_run" and item.value:
                claims.append(_claim("OBSERVATION", f"A prior {item.symbol} research run concluded (historical context only): {item.value}",
                                     [item], "neutral"))
        return claims

    def _challenge(self, context: ResearchContext, tools: list[ToolRun], claims: list[Claim]) -> list[Claim]:
        evidence = [item for run in tools for item in run.evidence
                    if item.manifest_id == context.manifest_id and item.as_of == context.as_of]
        by_label = {item.label: item for item in evidence}
        result = []
        trend, momentum, breadth = (by_label.get(name) for name in ("trend", "momentum", "breadth"))
        if trend and momentum and trend.value == "up" and momentum.value not in {"positive", "unknown"}:
            result.append(_claim("INTERPRETATION", "Trend points up while momentum does not confirm it.",
                                 [trend, momentum], "counter"))
        if trend and breadth and trend.value == "up" and breadth.value in {"broad_negative", "weak", "negative"}:
            result.append(_claim("INTERPRETATION", "The upward trend lacks broad pilot participation.",
                                 [trend, breadth], "counter"))
        if context.symbol:
            close = next((item for item in evidence if item.label == "Latest stored close" and item.symbol == context.symbol), None)
            rsi = next((item for item in evidence if item.label == "rsi(14)" and item.symbol == context.symbol), None)
            if close and rsi and isinstance(rsi.value, (int, float)) and rsi.value < 40 and trend and trend.value == "up":
                result.append(_claim("INTERPRETATION", "Weak RSI conflicts with the pilot's upward trend classification.",
                                     [rsi, trend], "counter"))
        freshness = by_label.get("data_freshness")
        if freshness and freshness.value in {"stale", "unknown"}:
            result.append(_claim("LIMITATION", "Stored daily observations are stale or have uncertain freshness at this cutoff.",
                                 [freshness], "limitation"))
        coverage = by_label.get("Pilot members visible")
        if coverage and isinstance(coverage.value, int) and coverage.value < 5:
            result.append(_claim("LIMITATION", "The five-member pilot is incomplete under this manifest and cutoff.",
                                 [coverage], "limitation"))
        if context.symbol and not any(item.kind == "observation" and item.symbol == context.symbol for item in evidence):
            missing = next((item for item in evidence if item.kind == "missing" and item.symbol == context.symbol), None)
            if missing:
                result.append(_claim("LIMITATION", "No stored market observation is visible for the selected instrument.",
                                     [missing], "limitation"))
        # A five-pair sample and deferred equity providers are always a relevant scope limit.
        pilot = by_label.get("Pilot members visible")
        if pilot:
            result.append(_claim("LIMITATION", "The evidence covers only Binance Pilot 5; India and US live sources remain deferred.",
                                 [pilot], "limitation"))
        return result

    @staticmethod
    def _strength(context: ResearchContext, tools: list[ToolRun], claims: list[Claim]) -> str:
        evidence = [item for run in tools for item in run.evidence
                    if item.manifest_id == context.manifest_id and item.as_of == context.as_of]
        coverage = next((item for item in evidence if item.label == "Pilot members visible"), None)
        conflicts = any(item.stance == "counter" and item.type == "INTERPRETATION" for item in claims)
        stale = any(item.freshness in {"stale", "unknown"} for item in evidence if item.freshness)
        support_kinds = {item.tool_id for item in evidence if item.value is not None and
                         item.tool_id in {"instrument.features", "market.state", "asset.compare"}}
        if not coverage or coverage.value != 5 or stale:
            return "weak"
        if len(support_kinds) >= 2 and not conflicts:
            return "strong" if len(support_kinds) >= 3 else "moderate"
        return "weak" if conflicts else "moderate"

    def _synthesize(self, request: ResearchRequest, context: ResearchContext,
                    claims: list[Claim], selected: set[str], strength: str) -> str:
        def render(item: Claim) -> str:
            return f"- {item.text} " + " ".join(f"[{evidence_id}]" for evidence_id in item.evidence_ids)
        support = [item for item in claims if item.stance in {"support", "neutral"}
                   and item.claim_id in selected]
        question = request.question.lower()
        def priority(item: Claim) -> int:
            value = item.text.lower()
            if "relative strength" in question and "strongest" in value:
                return 0
            if (any(term in question for term in ("compare", "stronger", "versus")) and
                    any(term in value for term in ("relative-strength", "pearson correlation"))):
                return 0
            if any(term in question for term in ("changed", "earlier manifest", "one month ago")) and "compared with the older" in value:
                return 0
            if any(term in question for term in ("conclude", "previous", "prior research", "last week")) and "research run concluded" in value:
                return 0
            return 1
        support.sort(key=priority)
        counter = [item for item in claims if item.stance == "counter"]
        limits = [item for item in claims if item.stance == "limitation"]
        title = (f"{context.symbol} research" if context.symbol else "Binance Pilot 5 research")
        header = (f"{title} | {context.mode} | manifest {context.manifest_id} | "
                  f"as of {context.as_of.isoformat()} | evidence strength: {strength}")
        if any(term in question for term in ("contradict", "bearish", "counter-evidence")) and counter:
            conclusion = counter[0]
        elif any(term in question for term in ("missing", "insufficient", "unavailable")) and limits:
            conclusion = limits[0]
        elif support and priority(support[0]) == 0:
            conclusion = support[0]
        else:
            conclusion = next((item for item in support if item.type in {"INTERPRETATION", "CLASSIFICATION"}),
                              support[0] if support else None)
        lines = [header, "", "Conclusion",
                 render(conclusion) if conclusion else "- Insufficient visible deterministic evidence for a market conclusion.",
                 "", "Evidence"]
        lines += [render(item) for item in support[:10]] or ["- Insufficient visible deterministic evidence for a directional conclusion."]
        lines += ["", "Counter-evidence"] + ([render(item) for item in counter] or ["- No direct indicator conflict was detected in the retrieved evidence."])
        lines += ["", "Limits"] + ([render(item) for item in limits] or ["- No additional scoped limitation was identified."])
        if context.symbol:
            sma = next((item for item in claims if "closed above" in item.text or "closed below" in item.text), None)
            lines += ["", "Invalidation", "- Recheck the interpretation if the next stored daily close crosses SMA20 or momentum/state evidence changes."
                      + (" " + " ".join(f"[{e}]" for e in sma.evidence_ids) if sma else "")]
        lines += ["", "This is a description of stored evidence, not a forecast or trade instruction."]
        return "\n".join(lines)

    def research(self, request: ResearchRequest, *, persist: bool = True) -> ResearchRun:
        started = time.perf_counter()
        inferred = _natural_cutoff(request.question) if request.mode == "latest" else None
        if inferred:
            request = ResearchRequest.model_validate({**request.model_dump(mode="python"),
                "mode": "historical", "as_of": inferred})
        context = self._resolve(request)
        plan = self._plan(request, context)
        tools, warnings = self._collect(plan)
        claims = self._claims(context, tools)
        claims += self._challenge(context, tools, claims)
        if not claims:
            marker = next((item for run in tools for item in run.evidence if item.kind == "coverage"), None)
            if marker:
                claims.append(_claim("LIMITATION", "The selected context lacks enough visible evidence for a market conclusion.",
                                     [marker], "limitation"))
        evidence_ids = {item.evidence_id for run in tools for item in run.evidence}
        if any(not set(claim.evidence_ids) <= evidence_ids for claim in claims):
            raise RuntimeError("UNGROUNDED_CLAIM")
        selected = {item.claim_id for item in claims}
        model_result = NoModelGateway().select_claims(request.question, [item.model_dump(mode="json") for item in claims])
        # Freeform questions are unclassified owner text. Only a loopback/local
        # gateway may see them in v1, regardless of the broad cloud setting.
        if may_send_context(self.settings, self.gateway, contains_private_data=True):
            try:
                model_result = self.gateway.select_claims(request.question,
                    [item.model_dump(mode="json") for item in claims])
                selected = set(model_result.selected_claim_ids)
                if not selected or not selected <= {item.claim_id for item in claims}:
                    raise ValueError("MODEL_SELECTED_UNKNOWN_CLAIM")
            except (OSError, TimeoutError, ValueError, KeyError, TypeError, IndexError):
                warnings.append("LOCAL_MODEL_UNAVAILABLE_OR_INVALID")
                model_result = NoModelGateway().select_claims(request.question,
                    [item.model_dump(mode="json") for item in claims])
                selected = set(model_result.selected_claim_ids)
        else:
            warnings.append("MODEL_BLOCKED_BY_PRIVACY_POLICY")
        strength = self._strength(context, tools, claims)
        answer = self._synthesize(request, context, claims, selected, strength)
        evidence_hash = digest([{"tool_id": item.tool_id, "inputs": item.inputs,
                                 "output_hash": item.output_hash} for item in tools])
        has_observation = any(item.kind == "observation" for run in tools for item in run.evidence)
        run = ResearchRun(run_id=uuid4(), created_at=datetime.now(timezone.utc),
            request=request, context=context, tools=tools, claims=claims,
            evidence_strength=strength, answer=answer, warnings=warnings,
            failure_state=None if has_observation or context.symbol is None and
                any(item.kind == "regime" for run in tools for item in run.evidence)
                else "INSUFFICIENT_EVIDENCE",
            evidence_hash=evidence_hash, model_provider=model_result.provider,
            model_id=model_result.model, model_status=model_result.status,
            model_latency_ms=model_result.latency_ms,
            deterministic_latency_ms=round(sum(item.elapsed_ms for item in tools), 2),
            total_latency_ms=round((time.perf_counter() - started) * 1000, 2),
            model_input_tokens=model_result.input_tokens,
            model_output_tokens=model_result.output_tokens)
        if persist:
            self.store.save(run)
        return run

    def replay(self, run_id: UUID) -> dict:
        stored = self.store.get(run_id)
        if stored is None:
            raise LookupError("RESEARCH_RUN_NOT_FOUND")
        checks = []
        for prior in stored.tools:
            manifest = UUID(prior.inputs["manifest_id"])
            cutoff = datetime.fromisoformat(prior.inputs["as_of"])
            if manifest == stored.context.manifest_id and cutoff == stored.context.as_of:
                context = stored.context
            else:
                raw = build_context(self.catalog, as_of=cutoff, manifest_id=manifest)
                context = ResearchContext(mode="historical", manifest_id=manifest, as_of=cutoff,
                    universe_id=stored.context.universe_id,
                    evaluation_date=date.fromisoformat(raw["evaluation_date"])
                        if raw["evaluation_date"] else None,
                    history_start=date.fromisoformat(raw["history_start"])
                        if raw["history_start"] else None,
                    members={item["symbol"]: UUID(item["instrument_id"]) for item in raw["members"]
                             if item["instrument_id"]}, symbol=stored.context.symbol,
                    compare_symbol=None, environment=stored.context.environment,
                    base_currency=stored.context.base_currency)
            arguments = {key: value for key, value in prior.inputs.items()
                         if key not in {"manifest_id", "as_of"}}
            try:
                current = ToolRegistry(self.catalog, context).execute(prior.tool_id, arguments)
                match = current.output_hash == prior.output_hash
                new_hash = current.output_hash
            except (LookupError, ValueError):
                match, new_hash = False, None
            checks.append({"tool_id": prior.tool_id, "manifest_id": str(manifest),
                           "as_of": cutoff.isoformat(), "stored_hash": prior.output_hash,
                           "replayed_hash": new_hash, "matched": match})
        return {"run_id": str(run_id), "evidence_reproducible": all(item["matched"] for item in checks),
                "language_reproducible": False, "checks": checks,
                "stored_evidence_hash": stored.evidence_hash}
