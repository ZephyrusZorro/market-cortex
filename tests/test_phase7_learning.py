"""Independently calculable expectation outcomes and statistical invariants."""
from datetime import date, datetime, timezone
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest

from market_cortex.learning import LearningService, compare_rule, descriptive, evaluate_values, session_horizon
from market_cortex.learning_contracts import JournalDraft, PredictionDefinition


def prediction(kind="relative_performance", **updates):
    values = dict(prediction_type=kind,horizon_sessions=5,comparator="gt",threshold=Decimal(0),
        invalidation_price=Decimal("90"),original_context={"baseline_price":"100","benchmark_price":"100"})
    values.update(updates)
    return SimpleNamespace(**values)


@pytest.mark.parametrize("last,expected,metric",[("120","CONFIRMED",".1"),("105","INVALIDATED","-.05"),("110","INCONCLUSIVE","0")])
def test_golden_relative_outperformance(last,expected,metric):
    result = evaluate_values(prediction(),[Decimal("100")]*4+[Decimal(last)],
                             [Decimal("100")]*4+[Decimal("110")])
    assert result["status"]==expected and result["metric_value"]==Decimal(metric)


def test_missing_session_does_not_shift_horizon():
    result = evaluate_values(prediction(),[Decimal("110"),None,Decimal("120"),Decimal("130"),Decimal("140")],
                             [Decimal("100")]*5)
    assert result["status"]=="INCONCLUSIVE" and result["metric_value"] is None
    assert result["warnings"]==["EXPECTED_SESSION_GAP"]


@pytest.mark.parametrize("kind,prices,threshold,comparator,expected",[
    ("thesis_survival",[101,99,97,96,100],95,"gt","CONFIRMED"),
    ("thesis_survival",[101,99,94,96,100],95,"gt","INVALIDATED"),
    ("breakout_hold",[101,99,95,96,100],95,"gt","INCONCLUSIVE"),
    ("breakout_hold",[101,99,95,96,100],95,"gte","CONFIRMED"),
    ("invalidation",[101,99,94,96,100],95,"lt","CONFIRMED"),
    ("forward_return",[100,101,102,103,110],.05,"gt","CONFIRMED"),
    ("relative_strength_persistence",[105,106,104,103,102],0,"gt","CONFIRMED")])
def test_golden_rule_categories(kind,prices,threshold,comparator,expected):
    record = prediction(kind,threshold=Decimal(str(threshold)),comparator=comparator)
    result = evaluate_values(record,list(map(Decimal,prices)),[Decimal(100)]*5)
    assert result["status"]==expected


def test_volatility_uses_explicit_canonical_feature_value_and_missing_is_unknown():
    record = prediction("volatility_state",threshold=Decimal(".4"))
    result = evaluate_values(record,[Decimal(100)]*5,volatility=Decimal(".5"))
    assert result["status"]=="CONFIRMED" and result["metric_value"]==Decimal(".5")
    assert evaluate_values(record,[Decimal(100)]*5)["status"]=="UNMEASURABLE"


def test_close_excursions_and_hypothetical_r_are_exact_not_inferred_trades():
    result = evaluate_values(prediction("forward_return"),list(map(Decimal,[105,95,90,110,120])))
    assert result["forward_return"]==Decimal(".2")
    assert result["mae_close"]==Decimal("-.1") and result["mfe_close"]==Decimal(".2")
    assert result["hypothetical_forward_r"]==Decimal("2")
    assert evaluate_values(prediction("forward_return",invalidation_price=None),[Decimal(100)]*5)["hypothetical_forward_r"] is None


def test_descriptive_golden_sample_size_mean_median_and_quantiles():
    stats = descriptive(list(map(Decimal,[1,2,3,4])))
    assert stats["N"]==4 and Decimal(stats["mean"])==Decimal("2.5")
    assert Decimal(stats["median"])==Decimal("2.5")
    assert Decimal(stats["q25"])==Decimal("1.75") and Decimal(stats["q75"])==Decimal("3.25")
    assert descriptive([])["mean"] is None and descriptive([Decimal(1)])["stddev"] is None


@pytest.mark.parametrize("change",[
    {"horizon_sessions":1},{"horizon_sessions":21},{"symbol":"FAKEUSDT"},
    {"prediction_type":"relative_performance"},{"benchmark_symbol":"ETHUSDT"},
    {"prediction_type":"breakout_hold","threshold":0},{"prediction_type":"invalidation","comparator":"gt"},
    {"calibrated_probability":.8},{"threshold":"NaN"},{"as_of":datetime(2026,10,4)}])
def test_invalid_definitions_rejected(change):
    payload = dict(title="Known forward return expectation",prediction_type="forward_return",symbol="BTCUSDT",
        horizon_sessions=5,comparator="gt",threshold="0",manifest_id=uuid4(),as_of=datetime.now(timezone.utc))
    payload.update(change)
    with pytest.raises(ValueError):
        PredictionDefinition(**payload)


def test_boundary_comparators_are_falsifiable_and_no_fake_probability():
    assert compare_rule(Decimal(1),"gt",Decimal(1))=="INCONCLUSIVE"
    assert compare_rule(Decimal(1),"gte",Decimal(1))=="CONFIRMED"
    with pytest.raises(ValueError):
        JournalDraft(category="observation",title="Test note",manifest_id=uuid4(),as_of=datetime.now(timezone.utc),
                     failure_category="stale_data")


def test_horizon_counts_explicit_open_sessions_and_refuses_missing_calendar():
    from market_cortex.calendar import CalendarMissing,SessionCalendar
    from market_cortex.contracts import Venue
    statuses={date(2026,10,3):"holiday",date(2026,10,4):"holiday",
              date(2026,10,5):"open",date(2026,10,6):"open"}
    class Calendar:
        def session(self,day):
            if day not in statuses:
                raise CalendarMissing("explicit calendar unavailable")
            return SimpleNamespace(status=statuses[day])
    assert session_horizon(Calendar(),date(2026,10,2),2)==[date(2026,10,5),date(2026,10,6)]
    with pytest.raises(CalendarMissing):
        session_horizon(Calendar(),date(2026,10,2),3)
    crypto=SessionCalendar(Venue(venue_id="XCRY",timezone="UTC",session_kind="24x7"),"crypto_daily","v1")
    assert session_horizon(crypto,date(2026,10,2),2)==[date(2026,10,3),date(2026,10,4)]


def test_performance_never_merges_detector_versions_or_registration_and_counts_rejections(monkeypatch):
    ids=[uuid4() for _ in range(3)]
    records={}
    outcomes={}
    for pid,version,registration,status,ret in zip(ids,["1.0.0","1.0.0","2.0.0"],
            ["PRE_REGISTERED","RETROSPECTIVE_EVALUATION","RETROSPECTIVE_EVALUATION"],
            ["CONFIRMED","INVALIDATED","CONFIRMED"],[".1","-.2",".3"]):
        records[pid]=SimpleNamespace(prediction_id=pid,detector_id="breakout",detector_version=version,
            registration=registration,classification="SYNTHETIC_TEST",prediction_type="forward_return",
            horizon_sessions=5,comparator="gt",threshold=Decimal(0),benchmark_symbol=None,status=status,
            evidence_strength="weak",manifest_id=uuid4(),evaluation_id=pid,
            original_context={"features":{"volatility":{"version":"1.0.0"}},
                              "market_state":{"regime":{"category":"risk_on"}},"linked":{}})
        outcomes[pid]=SimpleNamespace(evaluation_manifest_id=uuid4(),evaluation_quality="valid",
            prediction_freshness="current",forward_return=Decimal(ret),metric_value=Decimal(ret),benchmark_return=None,hypothetical_forward_r=None,
            mae_close=Decimal("-.1"),mfe_close=Decimal(".1"))
    class Connection:
        def __enter__(self): return self
        def __exit__(self,*args): pass
        def execute(self,sql,args):
            self.rows=[("breakout","1.0.0","rejected","NO_EDGE",2)] if "GROUP BY" in sql else [(pid,) for pid in ids]
            return self
        def fetchall(self): return self.rows
    monkeypatch.setattr("market_cortex.learning.connect",lambda dsn:Connection())
    service=LearningService.__new__(LearningService)
    service.catalog=SimpleNamespace(dsn="synthetic")
    service.store=SimpleNamespace(performance_records=lambda cutoff,classification:[(records[pid],outcomes[pid]) for pid in ids])
    report=service.performance(as_of=datetime.now(timezone.utc))
    assert report["prediction_N"]==3 and report["usable_N"]==3 and report["candidate_ledger_N"]==2
    assert {(g["detector_version"],g["registration"]) for g in report["groups"]}=={
        ("1.0.0","PRE_REGISTERED"),("1.0.0","RETROSPECTIVE_EVALUATION"),("2.0.0","RETROSPECTIVE_EVALUATION")}
    assert all(g["N"]==1 and sum(g["outcomes"].values())==1 for g in report["groups"])
    assert report["candidate_ledger"][0]["outcome"]=="rejected"
