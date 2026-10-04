"""Deterministic daily expectation evaluation and descriptive research learning."""
from __future__ import annotations

import hashlib
import statistics
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from uuid import UUID, NAMESPACE_URL, uuid4, uuid5

from .cortex_store import ResearchRunStore
from .database import connect
from .features import FeatureEngine, FeatureRequest
from .learning_contracts import (EdgeDraft, EvaluationRequest, JournalDraft, PredictionDefinition,
                                PredictionEvaluation, PredictionRecord)
from .learning_store import LearningStore
from .market_state import MarketStateEngine, MarketStateRequest
from .opportunity_store import OpportunityStore
from .portfolio_store import PortfolioStore
from .risk import RiskService, digest, money
from .workstation import build_context

CODE_HASH = hashlib.sha256(Path(__file__).read_bytes().replace(b"\r\n",b"\n")).hexdigest()
MIN_DESCRIPTIVE_SAMPLE = 30
TERMINAL_OUTCOMES = {"CONFIRMED", "INVALIDATED", "INCONCLUSIVE", "UNMEASURABLE"}


def session_horizon(calendar, baseline: date, count: int) -> list[date]:
    dates = []
    for offset in range(1,81):
        day = baseline+timedelta(days=offset)
        if calendar.session(day).status != "holiday":
            dates.append(day)
        if len(dates)==count:
            return dates
    raise ValueError("EVALUATION_CALENDAR_UNAVAILABLE")


def compare_rule(value: Decimal, comparator: str, threshold: Decimal) -> str:
    if value == threshold and comparator in ("gt", "lt"):
        return "INCONCLUSIVE"
    met = {"gt":value>threshold, "gte":value>=threshold,
           "lt":value<threshold, "lte":value<=threshold}[comparator]
    return "CONFIRMED" if met else "INVALIDATED"


def evaluate_values(prediction: PredictionRecord, closes: list[Decimal | None],
                    benchmark: list[Decimal | None] | None = None,
                    volatility: Decimal | None = None) -> dict:
    """Exact horizon, close-only excursions; no missing-session compression."""
    if len(closes) != prediction.horizon_sessions or any(value is None for value in closes):
        return {"status":"INCONCLUSIVE", "warnings":["EXPECTED_SESSION_GAP"], "metric_value":None}
    base = Decimal(prediction.original_context["baseline_price"])
    returns = [value/base-1 for value in closes]
    forward, bench_return = returns[-1], None
    metric = forward
    if prediction.prediction_type in ("relative_performance", "relative_strength_persistence"):
        if benchmark is None or len(benchmark) != len(closes) or any(value is None for value in benchmark):
            return {"status":"INCONCLUSIVE", "warnings":["BENCHMARK_SESSION_GAP"], "metric_value":None}
        other_base = Decimal(prediction.original_context["benchmark_price"])
        relative = [left-(right/other_base-1) for left,right in zip(returns,benchmark)]
        bench_return = benchmark[-1]/other_base-1
        metric = relative[-1] if prediction.prediction_type == "relative_performance" else min(relative)
    elif prediction.prediction_type in ("thesis_survival", "breakout_hold", "invalidation"):
        metric = min(closes)
    elif prediction.prediction_type == "volatility_state":
        if volatility is None:
            return {"status":"UNMEASURABLE", "warnings":["VOLATILITY_HISTORY_UNAVAILABLE"], "metric_value":None}
        metric = volatility
    outcome_r = (closes[-1]-base)/(base-prediction.invalidation_price) \
        if prediction.invalidation_price is not None else None
    return {"status":compare_rule(metric,prediction.comparator,prediction.threshold),
        "metric_value":money(metric), "forward_return":money(forward),
        "benchmark_return":money(bench_return) if bench_return is not None else None,
        "mae_close":money(min([Decimal(0),*returns])), "mfe_close":money(max([Decimal(0),*returns])),
        "hypothetical_forward_r":money(outcome_r) if outcome_r is not None else None, "warnings":[]}


def descriptive(values: list[Decimal]) -> dict:
    if not values:
        return {"N":0,"mean":None,"median":None,"stddev":None,"q25":None,"q75":None}
    ordered = sorted(values)
    def quantile(fraction: Decimal):
        index = fraction*(len(ordered)-1)
        lower = int(index)
        return money(ordered[lower]+(ordered[min(lower+1,len(ordered)-1)]-ordered[lower])*(index-lower))
    return {"N":len(values),"mean":str(money(sum(values)/len(values))),
        "median":str(money(Decimal(statistics.median(values)))),
        "stddev":str(money(Decimal(statistics.stdev(values)))) if len(values)>1 else None,
        "q25":str(quantile(Decimal(".25"))),"q75":str(quantile(Decimal(".75")))}


class LearningService:
    def __init__(self, catalog, environment: str):
        self.catalog, self.environment = catalog, environment
        self.store = LearningStore(catalog.dsn,environment)
        self.features = FeatureEngine(catalog)
        self.opportunities = OpportunityStore(catalog.dsn)

    def context(self, manifest_id: UUID, as_of: datetime) -> dict:
        if as_of > datetime.now(timezone.utc):
            raise ValueError("FUTURE_CONTEXT_CUTOFF_FORBIDDEN")
        context = build_context(self.catalog,as_of=as_of,manifest_id=manifest_id)
        if datetime.fromisoformat(context["manifest"]["created_at"]) > as_of:
            raise ValueError("MANIFEST_NOT_YET_KNOWN_AT_CUTOFF")
        return context

    def freeze_links(self, links, manifest: UUID, cutoff: datetime, classification: str) -> dict:
        ancestors = RiskService(self.catalog,self.environment)._manifest_ancestors(manifest)
        frozen = {}
        identities,_ = self.catalog.load_identity()
        if any(value not in {i.instrument_id for i in identities} for value in links.instrument_ids):
            raise ValueError("LINK_INSTRUMENT_NOT_FOUND")
        for kind, value in (("candidate",links.candidate_id),("thesis",links.thesis_id),
                           ("research_run",links.research_run_id),("risk_snapshot",links.risk_snapshot_id),
                           ("prediction",links.prediction_id)):
            if value is None:
                continue
            if kind == "candidate":
                item = self.opportunities.candidate(value)
            elif kind == "thesis":
                visible = [item for item in self.opportunities.versions(value) if item.updated_at<=cutoff
                           and item.as_of<=cutoff and item.source_manifest_id in ancestors]
                item = visible[-1] if visible else None
            elif kind == "research_run":
                item = ResearchRunStore(self.catalog.dsn).get(value)
            elif kind == "risk_snapshot":
                item = PortfolioStore(self.catalog.dsn,self.environment).risk_snapshot(value,known_at=cutoff)
            else:
                item = self.store.prediction(value,cutoff)
            if item is None:
                raise LookupError(f"LINK_{kind.upper()}_NOT_VISIBLE")
            payload = item.model_dump(mode="json") if hasattr(item,"model_dump") else item
            source = payload.get("context",payload)
            source_manifest = source.get("source_manifest_id",source.get("manifest_id"))
            known = payload.get("updated_at",payload.get("created_at",payload.get("as_of")))
            if UUID(source_manifest) not in ancestors or datetime.fromisoformat(source["as_of"])>cutoff \
                or known is not None and datetime.fromisoformat(known)>cutoff:
                raise ValueError("LINK_CONTEXT_NOT_VISIBLE_AT_CUTOFF")
            if (payload.get("classification") == "SYNTHETIC_TEST" or
                payload.get("portfolio_classification") == "SYNTHETIC_TEST_PORTFOLIO") and classification != "SYNTHETIC_TEST":
                raise ValueError("SYNTHETIC_LINK_REQUIRES_SYNTHETIC_RECORD")
            frozen[kind] = payload
        if links.portfolio_id:
            store = PortfolioStore(self.catalog.dsn,self.environment)
            visible = [row["version"] for row in store.versions(links.portfolio_id)
                       if datetime.fromisoformat(row["recorded_at"])<=cutoff]
            portfolio = store.get(links.portfolio_id,max(visible)) if visible else None
            if portfolio is None or not any(p.position_id==links.position_id for p in portfolio.positions):
                raise ValueError("LINK_PORTFOLIO_POSITION_NOT_VISIBLE")
            if portfolio.classification == "SYNTHETIC_TEST_PORTFOLIO" and classification != "SYNTHETIC_TEST":
                raise ValueError("SYNTHETIC_LINK_REQUIRES_SYNTHETIC_RECORD")
            frozen["portfolio"] = portfolio.model_dump(mode="json")
        return frozen

    def journal(self, draft: JournalDraft):
        self.context(draft.manifest_id,draft.as_of)
        return self.store.create_journal(draft,self.freeze_links(draft.links,draft.manifest_id,
                                                               draft.as_of,draft.classification))

    def create_prediction(self, request: PredictionDefinition) -> PredictionRecord:
        self.store.guard(request.classification)
        context = self.context(request.manifest_id,request.as_of)
        member = next(m for m in context["members"] if m["symbol"]==request.symbol)
        if not member["last_session"]:
            raise ValueError("PREDICTION_BASELINE_DATA_UNAVAILABLE")
        baseline = request.baseline_session or date.fromisoformat(member["last_session"])
        if baseline > date.fromisoformat(member["last_session"]):
            raise ValueError("PREDICTION_BASELINE_AFTER_VISIBLE_HISTORY")
        loaded = self.features.load(instrument_id=UUID(member["instrument_id"]),
            start_date=baseline-timedelta(days=180),end_date=baseline,
            as_of=request.as_of,manifest_id=request.manifest_id,provider_id="binance")
        if not loaded.bars or loaded.bars[-1] is None:
            raise ValueError("PREDICTION_BASELINE_BAR_MISSING")
        horizon_calendar = self.catalog.load_calendar(loaded.instrument.primary_venue_id,
            datetime.combine(baseline,datetime.min.time(),timezone.utc),
            datetime.combine(baseline+timedelta(days=81),datetime.min.time(),timezone.utc))
        dates = session_horizon(horizon_calendar,baseline,request.horizon_sessions)
        if len(dates)!=request.horizon_sessions:
            raise ValueError("EVALUATION_CALENDAR_UNAVAILABLE")
        now = datetime.now(timezone.utc)
        if request.registration == "PRE_REGISTERED" and horizon_calendar.session(dates[0]).close_at<=now:
            raise ValueError("HORIZON_ALREADY_STARTED_USE_RETROSPECTIVE")
        price = Decimal(str(loaded.bars[-1].close))
        if request.invalidation_price is not None and request.invalidation_price>=price:
            raise ValueError("LONG_INVALIDATION_MUST_BE_BELOW_BASELINE")
        linked = self.freeze_links(request.links,request.manifest_id,request.as_of,request.classification)
        candidate = linked.get("candidate",linked.get("thesis",{}).get("candidate",{}))
        if candidate and candidate["instrument_id"] != member["instrument_id"]:
            raise ValueError("PREDICTION_CANDIDATE_INSTRUMENT_MISMATCH")
        computed = {}
        for feature,params in (("annualized_volatility",{"period":20}), ("atr",{"period":14}),
                               ("rsi",{"period":14})):
            result = self.features.calculate(FeatureRequest(instrument_id=loaded.instrument.instrument_id,
                start_date=loaded.dates[0],end_date=baseline,as_of=request.as_of,
                manifest_id=request.manifest_id,provider_id="binance",feature=feature,parameters=params),loaded)
            computed[feature] = {"feature_id":result.feature_id,"value":result.points[-1].value,
                                 "version":result.definition.version,"freshness":result.freshness}
        original = {"baseline_price":str(price),"baseline_observation_id":str(loaded.bars[-1].envelope.observation_id),
            "instrument_id":member["instrument_id"],"calendar_id":loaded.calendar.calendar_id,
            "first_outcome_close_at":horizon_calendar.session(dates[0]).close_at.isoformat(),
            "calendar_version":loaded.calendar.version,"provider":"binance","adjustment_basis":"raw",
            "features":computed,"source_freshness":loaded.freshness_state,
            "source_quality":loaded.bars[-1].envelope.quality_state,"linked":linked,
            "market_state":None,"benchmark_price":None,"benchmark_instrument_id":None}
        if request.benchmark_symbol:
            other = next(m for m in context["members"] if m["symbol"]==request.benchmark_symbol)
            benchmark = self.features.load(instrument_id=UUID(other["instrument_id"]),
                start_date=baseline,end_date=baseline,as_of=request.as_of,
                manifest_id=request.manifest_id,provider_id="binance")
            if not benchmark.bars or benchmark.bars[-1] is None:
                raise ValueError("BENCHMARK_BASELINE_MISSING")
            original.update(benchmark_price=str(benchmark.bars[-1].close),
                benchmark_instrument_id=other["instrument_id"],
                benchmark_observation_id=str(benchmark.bars[-1].envelope.observation_id))
        if context["history_start"]:
            state = MarketStateEngine(self.catalog).compute(MarketStateRequest(
                history_start=max(date.fromisoformat(context["history_start"]),baseline-timedelta(days=180)),
                evaluation_date=baseline,as_of=request.as_of,manifest_id=request.manifest_id))
            original["market_state"] = state.model_dump(mode="json")
        definition = request.model_dump(mode="json")
        original["definition"] = definition
        original_hash = digest({"context":original,"horizon_dates":dates})
        record = PredictionRecord(**{**request.model_dump(),"baseline_session":baseline},
            prediction_id=uuid4(),created_at=now,due_session=dates[-1],
            due_at=horizon_calendar.session(dates[-1]).close_at,horizon_dates=dates,
            original_context=original,original_context_hash=original_hash,
            evidence_strength=candidate.get("detector_strength","weak"),
            detector_id=candidate.get("detector_id","owner_hypothesis"),
            detector_version=candidate.get("detector_version","1.0.0"))
        return self.store.save_prediction(record)

    def evaluate(self, prediction_id: UUID, request: EvaluationRequest) -> PredictionEvaluation:
        prediction = self.store.prediction(prediction_id)
        if prediction is None:
            raise LookupError("PREDICTION_NOT_FOUND")
        if prediction.status == "CANCELLED":
            raise ValueError("CANCELLED_PREDICTION_CANNOT_EVALUATE")
        self.context(request.manifest_id,request.as_of)
        if prediction.manifest_id not in RiskService(self.catalog,self.environment)._manifest_ancestors(request.manifest_id):
            raise ValueError("EVALUATION_MANIFEST_MUST_DESCEND_FROM_SOURCE")
        values = {"status":"PENDING_EVALUATION","warnings":["HORIZON_NOT_COMPLETE"],"metric_value":None}
        observed,ids,features,quality = 0,[],[],"unavailable"
        if request.as_of>=prediction.due_at:
            loaded = self.features.load(instrument_id=UUID(prediction.original_context["instrument_id"]),
                start_date=prediction.baseline_session-timedelta(days=100),end_date=prediction.due_session,
                as_of=request.as_of,manifest_id=request.manifest_id,provider_id="binance")
            by_date = dict(zip(loaded.dates,loaded.bars))
            bars = [by_date.get(day) for day in prediction.horizon_dates]
            if prediction.registration == "PRE_REGISTERED":
                bars = [bar if bar is None or (bar.envelope.available_at>prediction.created_at
                        and bar.end_at>prediction.created_at) else None for bar in bars]
            closes = [Decimal(str(bar.close)) if bar else None for bar in bars]
            observed = sum(bar is not None for bar in bars)
            ids = [bar.envelope.observation_id for bar in bars if bar]
            quality = "valid" if all(bar and bar.envelope.quality_state in ("valid","corrected") for bar in bars) else "gaps_or_uncertain"
            benchmark = None
            if prediction.benchmark_symbol:
                other = self.features.load(instrument_id=UUID(prediction.original_context["benchmark_instrument_id"]),
                    start_date=prediction.horizon_dates[0],end_date=prediction.due_session,
                    as_of=request.as_of,manifest_id=request.manifest_id,provider_id="binance")
                other_dates = dict(zip(other.dates,other.bars))
                other_bars = [other_dates.get(day) for day in prediction.horizon_dates]
                if prediction.registration == "PRE_REGISTERED":
                    other_bars = [bar if bar is None or (bar.envelope.available_at>prediction.created_at
                        and bar.end_at>prediction.created_at) else None for bar in other_bars]
                benchmark = [Decimal(str(bar.close)) if bar else None for bar in other_bars]
                ids += [bar.envelope.observation_id for bar in other_bars if bar]
                observed = min(observed,sum(bar is not None for bar in other_bars))
                if any(bar is None or bar.envelope.quality_state not in ("valid","corrected") for bar in other_bars):
                    quality = "gaps_or_uncertain"
            volatility = None
            if prediction.prediction_type == "volatility_state":
                feature = self.features.calculate(FeatureRequest(instrument_id=loaded.instrument.instrument_id,
                    start_date=loaded.dates[0],end_date=prediction.due_session,as_of=request.as_of,
                    manifest_id=request.manifest_id,provider_id="binance",feature="annualized_volatility",
                    parameters={"period":20}),loaded)
                features.append(feature.feature_id)
                volatility = Decimal(str(feature.points[-1].value)) if feature.points and feature.points[-1].value is not None else None
            values = evaluate_values(prediction,closes,benchmark,volatility)
        if prediction.original_context["source_freshness"] != "current":
            values["warnings"].append("PREDICTION_TIME_DATA_NOT_CURRENT")
        if prediction.registration == "RETROSPECTIVE_EVALUATION":
            values["warnings"].append("RETROSPECTIVE_NOT_A_PRE_REGISTERED_FORECAST")
        payload = dict(calculation_code_hash=CODE_HASH,prediction_id=prediction_id,
            original_context_hash=prediction.original_context_hash,source_manifest_id=prediction.manifest_id,
            evaluation_manifest_id=request.manifest_id,as_of=request.as_of,
            registration=prediction.registration,metric_value=None,forward_return=None,benchmark_return=None,
            mae_close=None,mfe_close=None,hypothetical_forward_r=None,expected_sessions=prediction.horizon_sessions,
            observed_sessions=observed,observation_ids=ids,feature_ids=features,
            source_quality=prediction.original_context["source_quality"],evaluation_quality=quality,
            prediction_freshness=prediction.original_context["source_freshness"])
        payload.update(values)
        evaluation = PredictionEvaluation(**payload,evaluation_id=uuid5(NAMESPACE_URL,digest(payload)),
                                         evaluated_at=datetime.now(timezone.utc))
        return self.store.save_evaluation(evaluation)

    def review_queue(self, as_of: datetime) -> dict:
        predictions = self.store.predictions(as_of=as_of,limit=None)
        unresolved = [p for p in predictions if p.status in ("OPEN","PENDING_EVALUATION","INCONCLUSIVE","UNMEASURABLE")]
        due = [p for p in unresolved if p.due_at<=as_of]
        return {"as_of":as_of.isoformat(),"open_N":len(unresolved),"due_N":len(due),
            "due":[p.model_dump(mode="json") for p in due],
            "unresolved":[p.model_dump(mode="json") for p in unresolved],
            "recent_outcomes":[p.model_dump(mode="json") for p in predictions if p.status in TERMINAL_OUTCOMES][:20],
            "recent_thesis_changes":[t.model_dump(mode="json") for t in self.opportunities.recent_theses(limit=20)
                                     if t.updated_at<=as_of],
            "warnings":[]}

    def evaluate_due(self, request: EvaluationRequest) -> dict:
        results = [self.evaluate(UUID(p["prediction_id"]),request).model_dump(mode="json")
                   for p in self.review_queue(request.as_of)["due"]]
        return {"evaluated_N":len(results),"items":results,"as_of":request.as_of.isoformat(),
                "manifest_id":str(request.manifest_id)}

    def postmortem(self, prediction_id: UUID) -> JournalDraft:
        prediction = self.store.prediction(prediction_id)
        if prediction is None or prediction.evaluation_id is None:
            raise ValueError("EVALUATION_REQUIRED_FOR_POSTMORTEM")
        evaluation = self.store.evaluation(prediction.evaluation_id)
        if evaluation.status not in TERMINAL_OUTCOMES:
            raise ValueError("COMPLETED_OUTCOME_REQUIRED_FOR_POSTMORTEM")
        return JournalDraft(category="outcome_review",title=f"Review: {prediction.title}"[:180],
            notes="Evidence template. Add owner observations about what was missed and done correctly.",
            structured_content={"original_expectation":prediction.title,
                "exact_rule":f"{prediction.prediction_type} {prediction.comparator} {prediction.threshold}; {prediction.horizon_sessions} sessions",
                "actual_outcome":f"{evaluation.status}; metric={evaluation.metric_value}",
                "original_evidence":prediction.original_context_hash,
                "counter_evidence":str(prediction.original_context.get("linked",{}).get("candidate",{}).get("contradictions",[])),
                "data_limitations":"; ".join(evaluation.warnings),"what_was_missed":"Owner review required",
                "done_correctly":"Owner review required","reusable_lesson":"Owner review required",
                "execution":"Research outcome; no trade or realized P/L inferred"},
            links=prediction.links.model_copy(update={"prediction_id":prediction_id}),
            manifest_id=evaluation.evaluation_manifest_id,as_of=datetime.now(timezone.utc),
            classification=prediction.classification,author="cortex_template",tags=["post-mortem",prediction.registration])

    def performance(self, *, as_of: datetime, eligible_only: bool = False,
                    classification: str | None = None) -> dict:
        with connect(self.catalog.dsn) as connection:
            ledger = connection.execute("""SELECT detector_id,detector_version,outcome,status,count(*)
                FROM opportunity_candidates WHERE recorded_at<=%s AND as_of<=%s
                GROUP BY detector_id,detector_version,outcome,status ORDER BY detector_id,detector_version,outcome,status""",
                (as_of,as_of)).fetchall()
        groups = {}
        for p,evaluation in self.store.performance_records(as_of,classification):
            regime = (p.original_context.get("market_state") or {}).get("regime",{}).get("category","unavailable")
            volatility_regime = next((d["category"] for d in (p.original_context.get("market_state") or {}).get("dimensions",[])
                                      if d["name"]=="volatility"),"unavailable")
            key = (p.detector_id,p.detector_version,p.registration,p.classification,p.prediction_type,
                   p.horizon_sessions,p.comparator,str(p.threshold),p.benchmark_symbol)
            group = groups.setdefault(key,{"detector_id":p.detector_id,"detector_version":p.detector_version,
                "registration":p.registration,"classification":p.classification,"prediction_type":p.prediction_type,
                "horizon_sessions":p.horizon_sessions,"comparator":p.comparator,"threshold":str(p.threshold),
                "benchmark_symbol":p.benchmark_symbol,"N":0,"usable_N":0,"missing_inconclusive_N":0,
                "excluded_quality_N":0,"outcomes":{},"evidence_strength":{},"regime":{},"volatility_regime":{},"feature_versions":[],
                "research_run_linked_N":0,"counter_evidence_present_N":0,
                "usable_confirmed_N":0,"usable_invalidated_N":0,
                "source_manifests":[],"evaluation_manifests":[],
                "returns":[],"metric_values":[],"benchmark_returns":[],"r_outcomes":[],"mae":[],"mfe":[],"prediction_ids":[]})
            group["N"]+=1
            group["prediction_ids"].append(str(p.prediction_id))
            if str(p.manifest_id) not in group["source_manifests"]:
                group["source_manifests"].append(str(p.manifest_id))
            group["outcomes"][p.status]=group["outcomes"].get(p.status,0)+1
            run = p.original_context.get("linked",{}).get("research_run")
            group["research_run_linked_N"]+=int(run is not None)
            group["counter_evidence_present_N"]+=int(bool(run and any(c["stance"] in ("counter","limitation") for c in run["claims"])))
            if evaluation is not None and str(evaluation.evaluation_manifest_id) not in group["evaluation_manifests"]:
                group["evaluation_manifests"].append(str(evaluation.evaluation_manifest_id))
            eligible = evaluation is not None and evaluation.evaluation_quality=="valid" and evaluation.prediction_freshness=="current"
            if eligible_only and not eligible:
                group["excluded_quality_N"]+=1
                continue
            if evaluation is None or p.status not in ("CONFIRMED","INVALIDATED"):
                group["missing_inconclusive_N"]+=1
                continue
            group["usable_N"]+=1
            group["usable_confirmed_N"]+=int(p.status=="CONFIRMED")
            group["usable_invalidated_N"]+=int(p.status=="INVALIDATED")
            for field,value in (("returns",evaluation.forward_return),("metric_values",evaluation.metric_value),
                                ("benchmark_returns",evaluation.benchmark_return),("r_outcomes",evaluation.hypothetical_forward_r),
                                ("mae",evaluation.mae_close),("mfe",evaluation.mfe_close)):
                if value is not None:
                    group[field].append(value)
            for dimension,label in (("evidence_strength",p.evidence_strength),("regime",regime),("volatility_regime",volatility_regime)):
                segment = group[dimension].setdefault(label,{"N":0,"confirmed_N":0,"returns":[]})
                segment["N"]+=1
                segment["confirmed_N"]+=int(p.status=="CONFIRMED")
                if evaluation.forward_return is not None:
                    segment["returns"].append(evaluation.forward_return)
            versions = {name:value["version"] for name,value in p.original_context["features"].items()}
            if versions not in group["feature_versions"]:
                group["feature_versions"].append(versions)
        output = []
        for group in groups.values():
            group["forward_return"] = descriptive(group.pop("returns"))
            group["metric_distribution"] = descriptive(group.pop("metric_values"))
            group["benchmark_return"] = descriptive(group.pop("benchmark_returns"))
            group["hypothetical_r_expectancy"] = descriptive(group.pop("r_outcomes"))
            group["mae_close"] = descriptive(group.pop("mae"))
            group["mfe_close"] = descriptive(group.pop("mfe"))
            for dimension in ("evidence_strength","regime","volatility_regime"):
                for segment in group[dimension].values():
                    segment["forward_return"] = descriptive(segment.pop("returns"))
            group["sample_sufficient"] = group["usable_N"]>=MIN_DESCRIPTIVE_SAMPLE
            decided = group["usable_confirmed_N"]+group["usable_invalidated_N"]
            group["descriptive_confirmation_fraction"] = str(money(Decimal(group["usable_confirmed_N"])/decided)) if decided else None
            group["confirmation_fraction_N"] = decided
            group["warnings"] = ["OBSERVATIONAL_SELECTION_NOT_CAUSAL", "OVERLAPPING_HORIZONS_MAY_NOT_BE_INDEPENDENT"]
            if not group["sample_sufficient"]:
                group["warnings"].append("SMALL_SAMPLE_NO_EDGE_CLAIM")
            output.append(group)
        payload = {"calculation_version":"learning_descriptive_v1","as_of":as_of.isoformat(),
            "eligible_only":eligible_only,"minimum_descriptive_N":MIN_DESCRIPTIVE_SAMPLE,
            "prediction_N":sum(g["N"] for g in output),"usable_N":sum(g["usable_N"] for g in output),
            "groups":output,"candidate_ledger":[dict(zip(("detector_id","detector_version","outcome","status","N"),row)) for row in ledger],
            "candidate_ledger_N":sum(row[-1] for row in ledger),
            "warnings":["REJECTIONS_NO_EDGE_UNSUPPORTED_AND_INSUFFICIENT_ARE_COUNTED",
                "FORWARD_OUTCOMES_EXIST_ONLY_FOR_EXPLICIT_PREDICTIONS",
                "PRE_REGISTERED_AND_RETROSPECTIVE_GROUPS_ARE_SEPARATE",
                "NO_CALIBRATED_PROBABILITIES_OR_AUTOMATIC_RULE_CHANGES"]}
        return {**payload,"report_id":digest(payload)}

    def edge(self, request: EdgeDraft) -> dict:
        now = datetime.now(timezone.utc)
        report = self.performance(as_of=now,classification=request.classification)
        groups = [g for g in report["groups"] if g["detector_id"]==request.detector_id and
            g["detector_version"]==request.detector_version and g["registration"]==request.registration]
        if request.regime is not None:
            groups = [{**g,"selected_regime_statistics":g["regime"][request.regime],
                       "usable_N":g["regime"][request.regime]["N"]} for g in groups if request.regime in g["regime"]]
        return self.store.save_edge({**request.model_dump(mode="json"),"edge_id":str(uuid4()),
            "schema_version":"edge_hypothesis_v1","created_at":now.isoformat(),
            "status":"HYPOTHESIS","supporting_statistics":groups,"report_id":report["report_id"],
            "usable_N":sum(g["usable_N"] for g in groups),"warnings":["NOT_A_PROVEN_EDGE","OWNER_HYPOTHESIS_NO_RULE_MUTATION"]})
