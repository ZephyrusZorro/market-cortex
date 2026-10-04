"""Registered strategies, replay, walk-forward, bounded research and learning."""
import itertools
import platform
import time
from datetime import date, datetime, time as daytime, timedelta, timezone
from pathlib import Path
from uuid import UUID, NAMESPACE_URL, uuid5

import numpy as np

from .features import CALCULATION_CODE_HASH, FEATURE_VERSION
from .opportunity import CODE_HASH as DETECTOR_CODE_HASH
from .opportunity_contracts import ScanRequest
from .opportunity_detectors import DETECTORS
from .quant_contracts import (BacktestDefinition,BacktestManifest,BacktestRun,Decision,GridRequest,
    StrategyDefinition,StrategyParameters,WalkForwardDefinition)
from .quant_engine import simulate
from .quant_metrics import drawdowns,metrics,streak
from .quant_replay import ReplayCatalog,ReplayOpportunityService,capture,days
from .quant_store import QuantStore,digest

ENGINE_VERSION="quant_daily_v1"


def _snapshot_code_hash():
    paths=[Path(__file__),*Path(__file__).parent.glob("quant_*.py"),Path(__file__).with_name("market_state.py"),
           *[Path(__file__).with_name(name+".py") for name in ("risk","alignment","calendar","quality","identity","breadth","features","indicators")]]
    return digest({p.name:p.read_bytes().replace(b"\r\n",b"\n").decode() for p in sorted(paths)})


IMPLEMENTATION_HASH=_snapshot_code_hash()


def code_hash():
    """Hash the implementation loaded by this process, even during a source edit."""
    return IMPLEMENTATION_HASH


def strategies():
    items=[StrategyDefinition(strategy_id=k,detector_id=k,description=f"Canonical {k}; VALID only, long-only fixed exits",
        required_features=DETECTORS[k].definition.required_features,minimum_history=DETECTORS[k].definition.minimum_history)
        for k in ("momentum","breakout","trend_continuation","pullback")]
    return items+[StrategyDefinition(strategy_id=k,detector_id=None,detector_version=None,
        description="Predetermined buy-and-hold allocation, costs included; no detector quality claim",
        entry_policy="predetermined_allocation_v1",exit_policy="period_end_v1",minimum_history=0)
        for k in ("buy_hold","equal_weight")]


def decision_hash(candidate):
    # Wall-clock creation and calculation duration are never part of research identity.
    return {k:v for k,v in candidate.model_dump(mode="json").items() if k not in ("created_at","elapsed_ms")}


class QuantService:
    def __init__(self,catalog,environment="LOCAL",progress=None):
        self.catalog=catalog
        self.environment=environment
        self.progress=progress
        self.store=QuantStore(catalog.dsn)
        self._sources={}
        self._decisions={}
        self._scan_cache={}

    def source(self,d):
        key=(d.manifest_id,d.source_as_of)
        if key not in self._sources:
            source=capture(self.catalog,*key)
            source_hash=digest(source)
            self.store.save("source",source,source_hash)
            self._sources[key]=(source,source_hash)
        return self._sources[key]

    def decisions(self,d,source,source_hash):
        key=(source_hash,d.replay_policy,d.publication_lag_seconds,d.strategy_id,tuple(d.symbols),d.start,d.end)
        if key in self._decisions:
            return self._decisions[key]
        catalog=ReplayCatalog(source,d.replay_policy,d.publication_lag_seconds)
        service=ReplayOpportunityService(catalog)
        output=[]
        if d.strategy_id in ("buy_hold","equal_weight"):
            signal=d.start-timedelta(days=2)
            cutoff=datetime.combine(signal+timedelta(days=1),daytime.min,timezone.utc)+timedelta(seconds=d.publication_lag_seconds)
            for s in d.symbols:
                payload={"strategy":d.strategy_id,"symbol":s,"session":str(signal),"source":source_hash}
                output.append(Decision(symbol=s,session=signal,cutoff=cutoff,outcome="baseline",status="PREDETERMINED",
                    enter=True,reason="REGISTERED_BASELINE_ALLOCATION",observation_ids=[],evidence_hash=digest(payload)))
        else:
            for day in days(d.start,d.end):
                cutoff=datetime.combine(day+timedelta(days=1),daytime.min,timezone.utc)+timedelta(seconds=d.publication_lag_seconds)
                if cutoff>d.source_as_of:
                    continue
                scan_key=(source_hash,d.replay_policy,d.publication_lag_seconds,day)
                if scan_key not in self._scan_cache:
                    scan=service.scan(ScanRequest(mode="pinned",manifest_id=d.manifest_id,as_of=cutoff))
                    self._scan_cache[scan_key]=(scan,service.last_state,service.visible_inputs)
                    if self.progress and day.day in (1,15):
                        self.progress(f"Canonical replay {day}; {d.replay_policy}")
                scan,last_state,visible_inputs=self._scan_cache[scan_key]
                found={c.symbol:c for c in scan.candidates if c.detector_id==d.strategy_id}
                for s in d.symbols:
                    c=found.get(s)
                    state={k:v for k,v in last_state.model_dump(mode="json").items()
                           if k not in ("calculated_at","elapsed_ms")} if last_state else None
                    payload=decision_hash(c) if c else None
                    # An old latest bar cannot generate a fresh decision on a missing session.
                    enter=bool(c and c.status=="VALID" and c.event_date==day)
                    refs=[str(b.envelope.observation_id) for b in visible_inputs.get(s,[])
                          if b.session_date>=day-timedelta(days=180)]
                    output.append(Decision(symbol=s,session=day,cutoff=cutoff,candidate=payload,state=state,
                        outcome=c.outcome if c else "insufficient_data",status=c.status if c else "WATCHING",enter=enter,
                        reason="VALID_ENTRY" if enter else "NO_VALID_CURRENT_SESSION_CANDIDATE",
                        observation_ids=refs,evidence_hash=digest({"candidate":payload,"source":source_hash,"session":day})))
        self._decisions[key]=output
        return output

    def run(self,d:BacktestDefinition,source=None,persist=True,use_cache=True):
        started=time.perf_counter()
        d=BacktestDefinition.model_validate(d.model_dump())
        if d.source_as_of>datetime.now(timezone.utc):
            raise ValueError("FUTURE_SOURCE_CUTOFF_FORBIDDEN")
        if not use_cache:
            self._decisions.clear()
            self._scan_cache.clear()
        if d.classification=="SYNTHETIC_TEST" and self.environment!="PILOT_TEST":
            raise ValueError("SYNTHETIC_QUANT_REQUIRES_PILOT_TEST")
        if d.classification=="SYNTHETIC_TEST" and self.catalog.dsn:
            from psycopg.conninfo import conninfo_to_dict
            if not conninfo_to_dict(self.catalog.dsn).get("dbname","").endswith("_test"):
                raise ValueError("SYNTHETIC_QUANT_REQUIRES_TEST_DATABASE")
        if source is None:
            source,source_hash=self.source(d)
        else:
            source_hash=digest(source)
        frozen={"definition":d.model_dump(mode="json"),"source_hash":source_hash,"engine":ENGINE_VERSION,
                "code":code_hash(),"detector":DETECTOR_CODE_HASH,"features":CALCULATION_CODE_HASH,
                "feature_version":FEATURE_VERSION,"strategy":next(s.model_dump(mode="json") for s in strategies() if s.strategy_id==d.strategy_id)}
        frozen["runtime"]={"python":platform.python_version(),"numpy":np.__version__}
        input_hash=digest(frozen)
        cached=self.store.by_hash("run",input_hash) if persist and use_cache else None
        if cached:
            return BacktestRun.model_validate(cached)
        decisions=self.decisions(d,source,source_hash)
        catalog=ReplayCatalog(source,d.replay_policy,d.publication_lag_seconds)
        # BTC benchmark needs outcome bars even for an alt-only strategy.
        execution_definition=d.model_copy(update={"symbols":list(dict.fromkeys(d.symbols+["BTCUSDT"]))})
        bars=catalog.execution_bars(execution_definition)
        trades,curve,engine_warnings=simulate(d,decisions,bars)
        dds,dd=drawdowns(curve)
        curve=[p.model_copy(update={"drawdown":v}) for p,v in zip(curve,dds)]
        summary=metrics(curve,trades,d.capital,d.annualization,d.risk_free_rate)
        if any(w.startswith("BENCHMARK_UNAVAILABLE") for w in engine_warnings):
            summary["benchmark_return"]=None
            summary["benchmark_relative_return"]=None
        regimes=[]
        for regime in sorted(set(t.regime for t in trades)):
            subset=[t for t in trades if t.regime==regime]
            regimes.append({"dimension":"overall_regime","regime":regime,"N":len(subset),"net_pnl":sum(t.net_pnl for t in subset),
                "mean_return":float(np.mean([t.return_fraction for t in subset])),"win_rate":sum(t.net_pnl>0 for t in subset)/len(subset)})
        evidence={decision.evidence_hash:decision for decision in decisions}
        dimension_groups={}
        for trade in trades:
            decision=evidence.get(trade.decision_hash)
            if decision and decision.state:
                for item in decision.state.get("dimensions",[]):
                    if item["name"] in ("trend","momentum","volatility","breadth","market_participation","correlation_state"):
                        dimension_groups.setdefault((item["name"],item["category"]),[]).append(trade)
        for (dimension,category),subset in sorted(dimension_groups.items()):
            regimes.append({"dimension":dimension,"regime":category,"N":len(subset),
                "net_pnl":sum(t.net_pnl for t in subset),"mean_return":float(np.mean([t.return_fraction for t in subset])),
                "win_rate":sum(t.net_pnl>0 for t in subset)/len(subset)})
        controls=self.controls(decisions,bars,d)
        warnings=["RESEARCH_ONLY; LONG_ONLY; NO_LEVERAGE; NO_ORDER_EXECUTION",
            "SELECTED_SURVIVOR_PILOT5_UNIVERSE; NOT_SURVIVORSHIP_SAFE",
            "DAILY_OHLC_EXCURSIONS_ARE_BOUNDS; INTRABAR_SEQUENCE_UNKNOWN",
            "FEES_SLIPPAGE_SPREAD_ARE_ASSUMPTIONS; BENCHMARK_GROSS_BUY_HOLD",
            "IN_SAMPLE_SINGLE_RUN; NO_EDGE_CLAIM; DEPENDENT_TRADES; MULTIPLE_TESTING",
            "UPSTOX_ALPACA_DEFERRED_NOT_CONFIGURED; EQUITY_ACTIONS_NOT_SUPPORTED",*engine_warnings]
        if d.execution.timing=="next_open":
            warnings.append("PUBLICATION_LAG_MISSES_IMMEDIATE_NEXT_OPEN; FIRST_OPEN_STRICTLY_AFTER_CUTOFF_USED")
        if d.execution.ambiguity=="target_first":
            warnings.append("OPTIMISTIC_INTRABAR_SENSITIVITY; NOT_DEFAULT_RESULT")
        if d.replay_policy=="HISTORICAL_RECONSTRUCTION":
            warnings.append("ASSUMED_HISTORICAL_RECONSTRUCTION; NOT_OBSERVED_POINT_IN_TIME; FIRST_REVISION_ONLY; MAPPING_DISCOVERY_AND_FRESHNESS_ASSUMED; ORIGINAL_TIMESTAMPS_PRESERVED")
        else:
            warnings.append("AS_RECORDED_REQUIRES_INGESTION_AVAILABILITY_AND_MANIFEST_KNOWN_BY_EACH_CUTOFF")
        if len(trades)<30:
            warnings.append("INSUFFICIENT_TRADE_SAMPLE_N_LT_30")
        if d.strategy_id in ("buy_hold","equal_weight"):
            warnings.append("BASELINE_HAS_NO_STOP_POLICY; R_AND_STOP_BASED_HEAT_UNAVAILABLE")
        if not trades:
            warnings.append("NO_TRADES; INSUFFICIENT_EVIDENCE_OR_NO_VALID_SIGNALS")
        manifest=BacktestManifest(source_hash=source_hash,manifest_id=d.manifest_id,source_as_of=d.source_as_of,
            engine_version=ENGINE_VERSION,code_hash=frozen["code"],detector_code_hash=DETECTOR_CODE_HASH,
            feature_code_hash=CALCULATION_CODE_HASH,calendar_versions={k:v["version"] for k,v in source["calendars"].items()},
            environment={"python":platform.python_version(),"numpy":np.__version__,"environment":self.environment},
            definition_hash=digest(frozen["definition"]),input_hash=input_hash)
        payload={"decisions":[x.model_dump(mode="json") for x in decisions],"trades":[x.model_dump(mode="json") for x in trades],
                 "equity":[x.model_dump(mode="json") for x in curve],"metrics":summary,"drawdown":dd,"controls":controls,"regimes":regimes}
        result=BacktestRun(run_id=uuid5(NAMESPACE_URL,input_hash),created_at=datetime.now(timezone.utc),definition=d,
            manifest=manifest,decisions=decisions,trades=trades,equity=curve,metrics=summary,drawdown=dd,
            regime_performance=regimes,controls=controls,warnings=warnings,result_hash=digest(payload),
            elapsed_ms=round((time.perf_counter()-started)*1000,3))
        if persist:
            self.store.save("source",source,source_hash)
            self.store.save("run",result.model_dump(mode="json"),input_hash,result.run_id)
        return result

    @staticmethod
    def controls(decisions,bars,d):
        groups={}
        for decision in decisions:
            start=bars.get(decision.symbol,{}).get(decision.session+timedelta(days=1))
            end=bars.get(decision.symbol,{}).get(decision.session+timedelta(days=6))
            if start is None or end is None:
                continue
            key=decision.status
            groups.setdefault(key,[]).append(float(end.close/start.close)-1)
        return {"registration":"RETROSPECTIVE_COUNTERFACTUAL", "horizon_sessions":5,
            "entry_reference":"next_close", "costs":"zero_cost_descriptive_control_not_trade_performance",
            "groups":[{"status":k,"N":len(v),"mean_return":float(np.mean(v)),"win_rate":sum(x>0 for x in v)/len(v)} for k,v in sorted(groups.items())],
            "warning":"OVERLAPPING_DEPENDENT_EVENTS; NO_PRE_REGISTERED_RESULT; NO_CAUSAL_REJECTION_BENEFIT_CLAIM"}

    def replay(self,run_id):
        saved=BacktestRun.model_validate(self.store.get(run_id,"run"))
        source=self.store.by_hash("source",saved.manifest.source_hash)
        if source is None or digest(source)!=saved.manifest.source_hash:
            raise ValueError("FROZEN_SOURCE_HASH_MISMATCH")
        if code_hash()!=saved.manifest.code_hash or DETECTOR_CODE_HASH!=saved.manifest.detector_code_hash or CALCULATION_CODE_HASH!=saved.manifest.feature_code_hash:
            return {"run_id":str(run_id),"status":"VERSION_UNAVAILABLE","saved_result_hash":saved.result_hash,
                    "warning":"CHECK_OUT_RECORDED_ENGINE_VERSION_TO_RECOMPUTE; SAVED_ARTIFACT_REMAINS_VIEWABLE"}
        recomputed=self.run(saved.definition,source,persist=False,use_cache=False)
        return {"run_id":str(run_id),"status":"MATCH" if recomputed.result_hash==saved.result_hash else "MISMATCH",
                "saved_result_hash":saved.result_hash,"recomputed_result_hash":recomputed.result_hash}

    def study(self,kind,definition,payload):
        value={"schema_version":"quant_study_v1","kind":kind,"definition":definition,"result":payload}
        study_hash=digest(value)
        value.update(study_id=str(uuid5(NAMESPACE_URL,f"quant:{kind}:{study_hash}")),created_at=datetime.now(timezone.utc).isoformat(),
                     warnings=["MULTIPLE_TESTING; ALL_TESTED_ROWS_RETAINED; NO_SIGNIFICANCE_CORRECTION","RECONSTRUCTED_OOS_IS_TEMPORAL_HOLDOUT_NOT_PROSPECTIVE_EVIDENCE"])
        self.store.save(kind,value,study_hash,UUID(value["study_id"]))
        return value

    def grid(self,request):
        source,_=self.source(request.definition)
        rows=[]
        for hold,stop in itertools.product(sorted(request.holding_sessions),sorted(request.stop_fraction)):
            params=request.definition.parameters.model_copy(update={"holding_sessions":hold,"stop_fraction":stop})
            run=self.run(request.definition.model_copy(update={"parameters":params}),source)
            rows.append({"parameters":params.model_dump(),"run_id":str(run.run_id),"metrics":run.metrics})
        return rows

    def sensitivity(self,request:GridRequest):
        rows=self.grid(request)
        values=[r["metrics"]["total_return"] for r in rows]
        return self.study("sensitivity",request.model_dump(mode="json"),{"combinations":len(rows),"rows":rows,
            "positive_fraction":sum(v>0 for v in values)/len(values),"range":[min(values),max(values)],
            "winner":max(rows,key=lambda r:r["metrics"]["total_return"]),"objective":"net_total_return; descriptive_in_sample"})

    def walk_forward(self,request:WalkForwardDefinition):
        d=request.definition
        timeline=days(d.start,d.end)
        folds=[]
        for index in range(request.max_folds):
            train_end_index=request.train_sessions-1+index*request.step_sessions
            validation_end_index=train_end_index+request.validation_sessions
            if validation_end_index>=len(timeline):
                break
            train_start_index=0 if request.mode=="expanding" else train_end_index-request.train_sessions+1
            train=d.model_copy(update={"start":timeline[train_start_index],"end":timeline[train_end_index]})
            search=self.grid(GridRequest(definition=train,holding_sessions=request.holding_sessions,stop_fraction=request.stop_fraction))
            # Tie-break depends on the fixed grid ordering, never validation outcomes.
            winner=max(search,key=lambda row:row["metrics"]["total_return"])
            selected=StrategyParameters.model_validate(winner["parameters"])
            oos=d.model_copy(update={"start":timeline[train_end_index+1],"end":timeline[validation_end_index],"parameters":selected})
            result=self.run(oos)
            folds.append({"fold":index+1,"train_start":str(train.start),"train_end":str(train.end),
                "validation_start":str(oos.start),"validation_end":str(oos.end),"selected_parameters":selected.model_dump(),
                "search_results":search,"training_run_id":winner["run_id"],"training_score":winner["metrics"]["total_return"],
                "oos_run_id":str(result.run_id),"oos_metrics":result.metrics,"freeze_hash":digest(winner),
                "boundary":"POSITIONS_LIQUIDATED_AT_TRAIN_END; OOS_STARTS_FLAT; PREVIOUS_COMPLETED_HISTORY_ALLOWED"})
        if not folds:
            raise ValueError("INSUFFICIENT_HISTORY_FOR_WALK_FORWARD")
        sample=sum(f["oos_metrics"]["N"] for f in folds)
        return self.study("walk_forward",request.model_dump(mode="json"),{"folds":folds,"search_count":len(folds),
            "parameter_combinations_tested":sum(len(f["search_results"]) for f in folds),"oos_N":sample,
            "oos_total_return_compounded_reset_capital":float(np.prod([1+f["oos_metrics"]["total_return"] for f in folds])-1),
            "sample_status":"INSUFFICIENT_OOS_SAMPLE" if sample<30 else "DESCRIPTIVE_TEMPORAL_OOS; NOT_PROVEN"})

    def robustness(self,d):
        variants=[("asset:"+s,d.model_copy(update={"symbols":[s]})) for s in d.symbols]
        variants+=[("cost:zero",d.model_copy(update={"costs":d.costs.model_copy(update={"entry_fee_bps":0,"exit_fee_bps":0,"slippage_bps":0,"spread_bps":0,"fixed_fee":0})})),
            ("cost:stress",d.model_copy(update={"costs":d.costs.model_copy(update={"entry_fee_bps":30,"exit_fee_bps":30,"slippage_bps":20})})),
            ("timing:close",d.model_copy(update={"execution":d.execution.model_copy(update={"timing":"next_close"})})),
            ("timing:delay",d.model_copy(update={"execution":d.execution.model_copy(update={"delay_sessions":2})}))]
        midpoint=d.start+(d.end-d.start)//2
        if (d.end-d.start).days>=60:
            variants+=[("period:first",d.model_copy(update={"end":midpoint})),("period:second",d.model_copy(update={"start":midpoint+timedelta(days=1)}))]
        for hold in sorted(set([max(1,d.parameters.holding_sessions-2),d.parameters.holding_sessions+2])):
            variants.append((f"holding:{hold}",d.model_copy(update={"parameters":d.parameters.model_copy(update={"holding_sessions":hold})})))
        rows=[]
        for label,definition in variants:
            result=self.run(definition)
            rows.append({"dimension":label,"run_id":str(result.run_id),"metrics":result.metrics,"regimes":result.regime_performance})
        sample=min(r["metrics"]["N"] for r in rows)
        positive=sum(r["metrics"]["total_return"]>0 for r in rows)/len(rows)
        # ROBUST_CANDIDATE deliberately requires separate OOS evidence; this standalone study cannot award it.
        category="INSUFFICIENT_EVIDENCE" if sample<30 else "MIXED" if positive>=.5 else "FRAGILE"
        return self.study("robustness",d.model_dump(mode="json"),{"rows":rows,"classification":category,"minimum_cell_N":sample,
            "positive_fraction":positive,"rule":"N<30 in any cell => INSUFFICIENT; otherwise >=50% positive => MIXED; else FRAGILE; no standalone robust promotion"})

    def monte_carlo(self,request):
        run=BacktestRun.model_validate(self.store.get(request.run_id,"run"))
        values=np.array([t.net_pnl/run.definition.capital for t in run.trades])
        n=len(values)
        if n<2:
            raise ValueError("MONTE_CARLO_REQUIRES_AT_LEAST_TWO_TRADES")
        rng=np.random.default_rng(request.seed)
        terminal=[]; drawdown=[]; streaks=[]
        for _ in range(request.simulations):
            sampled=rng.choice(values,size=n,replace=True) if request.method=="bootstrap" else rng.permutation(values)
            equity=np.concatenate(([1.],1+np.cumsum(sampled)))
            peaks=np.maximum.accumulate(equity)
            terminal.append(float(equity[-1]-1))
            drawdown.append(float(np.min(equity/peaks-1)))
            streaks.append(streak(sampled,False))
        percent=lambda v:{str(p):float(np.percentile(v,p)) for p in (5,25,50,75,95)}
        return self.study("monte_carlo",request.model_dump(mode="json"),{"source_trade_N":n,"simulations":request.simulations,
            "method":request.method,"seed":request.seed,"terminal_return":percent(terminal),"max_drawdown":percent(drawdown),
            "losing_streak":percent(streaks),"sample_status":"INSUFFICIENT_SAMPLE_N_LT_30" if n<30 else "EMPIRICAL_SAMPLE_ONLY",
            "methodology":"ADDITIVE_FIXED_INITIAL_CAPITAL_PNL_CONTRIBUTIONS; IGNORES_OVERLAP_AND_DEPENDENCE; NOT_PRICE_FORECAST",
            "ruin_paths_N":sum(v<=-1 for v in terminal)})

    def compare(self,request):
        rows=[]
        definitions=[]
        for run_id in request.run_ids:
            run=BacktestRun.model_validate(self.store.get(run_id,"run"))
            definitions.append(run.definition.model_dump(mode="json"))
            rows.append({"run_id":str(run_id),"strategy":run.definition.strategy_id,"period":[str(run.definition.start),str(run.definition.end)],
                "replay_policy":run.definition.replay_policy,"costs":run.definition.costs.model_dump(),"metrics":run.metrics,
                "warnings":run.warnings})
        normalized=[{k:v for k,v in d.items() if k not in ("strategy_id","parameters")} for d in definitions]
        return self.study("comparison",request.model_dump(mode="json"),{"rows":rows,"directly_comparable":all(d==normalized[0] for d in normalized),
            "warning":"COMPARE_DIFFERENT_ASSUMPTIONS_EXPLICITLY; EVERY_ROW_EXPOSES_N; SINGLE_RUNS_ARE_IN_SAMPLE"})

    def attach_edge(self,request):
        from psycopg.types.json import Jsonb
        from .database import connect
        runs=[BacktestRun.model_validate(self.store.get(k,"run")) for k in request.run_ids]
        studies=[self.store.get(k) for k in request.study_ids]
        now=datetime.now(timezone.utc)
        with connect(self.catalog.dsn) as c:
            edge=c.execute("SELECT payload FROM edge_library WHERE edge_id=%s FOR UPDATE",(request.edge_id,)).fetchone()
            if edge is None:
                raise LookupError("EDGE_NOT_FOUND")
            edge=edge[0]
            for run in runs:
                if run.definition.strategy_id!=edge["detector_id"] or run.definition.strategy_version!=edge["detector_version"]:
                    raise ValueError("EDGE_DETECTOR_VERSION_MISMATCH")
                if run.definition.classification!=edge["classification"]:
                    raise ValueError("EDGE_CLASSIFICATION_MISMATCH")
            base=runs[0].definition
            for study in studies:
                sd=study.get("definition",{})
                sd=sd.get("definition",sd)
                if sd.get("strategy_id")!=base.strategy_id or sd.get("manifest_id")!=str(base.manifest_id) or sd.get("replay_policy")!=base.replay_policy:
                    raise ValueError("UNRELATED_STUDY_CANNOT_SUPPORT_EDGE")
            if request.status=="EARLY_EVIDENCE" and not any(r.metrics["N"]>=10 for r in runs):
                raise ValueError("EARLY_EVIDENCE_REQUIRES_AT_LEAST_10_TRADES")
            if request.status=="SUPPORTED":
                by_kind={s["kind"]:s["result"] for s in studies}
                wf=by_kind.get("walk_forward",{})
                sensitivity=by_kind.get("sensitivity",{})
                robustness=by_kind.get("robustness",{})
                assets={t.symbol for r in runs for t in r.trades}
                regimes={t.regime for r in runs for t in r.trades if t.regime not in ("unknown","insufficient_data")}
                if (any(r.definition.replay_policy!="AS_RECORDED" for r in runs) or
                    max(r.metrics["N"] for r in runs)<30 or len(assets)<3 or len(regimes)<2 or
                    wf.get("oos_N",0)<30 or wf.get("oos_total_return_compounded_reset_capital",0)<=0 or
                    sensitivity.get("positive_fraction",0)<.7 or robustness.get("minimum_cell_N",0)<30 or
                    robustness.get("positive_fraction",0)<.7 or
                    not any(r.definition.costs.entry_fee_bps>0 and r.definition.costs.exit_fee_bps>0 for r in runs)):
                    raise ValueError("SUPPORTED_REQUIRES_RECORDED_OOS_SAMPLE_COST_ASSET_REGIME_AND_PARAMETER_EVIDENCE")
            revision=c.execute("SELECT coalesce(max(revision),0) FROM quant_edge_evidence WHERE edge_id=%s",(request.edge_id,)).fetchone()[0]
            if revision!=request.expected_revision:
                raise ValueError("EDGE_REVISION_CONFLICT")
            payload={"edge_id":str(request.edge_id),"revision":revision+1,"recorded_at":now.isoformat(),
                "status":request.status,"reason":request.reason,"registration":"RETROSPECTIVE_QUANT_EVIDENCE",
                "run_ids":[str(k) for k in request.run_ids],"study_ids":[str(k) for k in request.study_ids],
                "result_hashes":[r.result_hash for r in runs],"trade_N":sum(r.metrics["N"] for r in runs),
                "replay_policies":sorted(set(r.definition.replay_policy for r in runs)),
                "warning":"EXPLICIT_OWNER_RESEARCH_REVISION; DOES_NOT_ALTER_PRE_REGISTERED_PREDICTIONS"}
            c.execute("INSERT INTO quant_edge_evidence VALUES (%s,%s,%s,%s)",(request.edge_id,revision+1,now,Jsonb(payload)))
        return payload
