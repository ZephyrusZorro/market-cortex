"""Hand-calculated accounting and causal replay fixtures, independent of live prices."""
from datetime import date,datetime,timedelta,timezone
from decimal import Decimal
from uuid import uuid4

import pytest

from market_cortex.quant import QuantService
from market_cortex.quant_contracts import (BacktestDefinition,CostModel,Decision,EquityPoint,ExecutionPolicy,
    GridRequest,SizingPolicy,StrategyParameters,WalkForwardDefinition)
from market_cortex.quant_engine import simulate
from market_cortex.quant_metrics import drawdowns,metrics
from market_cortex.quant_replay import ReplayCatalog,ReplayOpportunityService,ReplayFeatureEngine
from market_cortex.opportunity_contracts import ScanRequest
from test_foundation import identity,bar,calendar

Z=timezone.utc


def definition(**changes):
    value=dict(strategy_id="momentum",manifest_id=uuid4(),source_as_of=datetime(2025,2,1,tzinfo=Z),
        start=date(2025,1,2),end=date(2025,1,4),symbols=["BTCUSDT"],benchmark="cash",
        capital=1000,sizing=SizingPolicy(mode="fixed_quantity",value=1),
        costs=CostModel(entry_fee_bps=0,exit_fee_bps=0,slippage_bps=0),
        parameters=StrategyParameters(holding_sessions=1,stop_fraction=.2,target_r=2))
    value.update(changes)
    return BacktestDefinition(**value)


def fixtures(d,ohlc=None):
    i,m=identity()
    cal=calendar()
    records={}
    for day in (d.start,d.start+timedelta(days=1),d.end):
        b=bar(i,m,cal,day=day,close="110")
        records[day]=b.model_copy(update={"high":Decimal("115"),"low":Decimal("95")})
    if ohlc:
        day=d.start+timedelta(days=1)
        records[day]=records[day].model_copy(update={k:Decimal(str(v)) for k,v in ohlc.items()})
    signal=d.start-timedelta(days=1)
    decision=Decision(symbol="BTCUSDT",session=signal,cutoff=datetime.combine(d.start,datetime.min.time(),Z)+timedelta(seconds=60),
        outcome="candidate",status="VALID",enter=True,reason="GOLDEN",observation_ids=[],evidence_hash="fixture")
    return [decision],{"BTCUSDT":records}


def test_golden_single_win_fees_cash_equity_and_r():
    d=definition(costs=CostModel(entry_fee_bps=100,exit_fee_bps=100,slippage_bps=0))
    decisions,bars=fixtures(d)
    trades,curve,_=simulate(d,decisions,bars)
    t=trades[0]
    assert t.entry_session==date(2025,1,3) and t.entry_at>t.signal_at
    assert t.net_pnl==pytest.approx(7.9)
    assert t.gross_pnl==10 and t.entry_fee==1 and t.exit_fee==1.1
    assert t.r_multiple==pytest.approx(7.9/20)
    assert curve[-1].cash==pytest.approx(1007.9) and curve[-1].net==pytest.approx(1007.9)
    assert curve[-1].gross==pytest.approx(1010)
    assert curve[-1].realized_pnl==pytest.approx(7.9) and curve[-1].unrealized_pnl==0
    result=metrics(curve,trades,1000)
    assert result["N"]==1 and result["win_rate"]==1 and result["profit_factor"] is None
    assert result["total_return"]==pytest.approx(.0079) and result["cagr"] is None


@pytest.mark.parametrize("policy,expected",[("stop_first",-20),("target_first",40)])
def test_ambiguous_daily_bar_is_explicit(policy,expected):
    d=definition(execution=ExecutionPolicy(ambiguity=policy))
    decisions,bars=fixtures(d,{"high":150,"low":70})
    trades,curve,_=simulate(d,decisions,bars)
    assert trades[0].ambiguous and trades[0].net_pnl==pytest.approx(expected)
    assert trades[0].mae==pytest.approx(-.3) and trades[0].mfe==pytest.approx(.5)


def test_gap_stop_and_next_close_cannot_use_entry_bar_high_low():
    d=definition(parameters=StrategyParameters(holding_sessions=10,stop_fraction=.2,target_r=2))
    decisions,bars=fixtures(d)
    bars["BTCUSDT"][d.end]=bars["BTCUSDT"][d.end].model_copy(update={"open":Decimal("60"),"low":Decimal("50"),"close":Decimal("70")})
    trades,_,_=simulate(d,decisions,bars)
    assert trades[0].exit_reference==60 and trades[0].exit_reason=="gap_stop"
    d=d.model_copy(update={"execution":ExecutionPolicy(timing="next_close")})
    decisions,bars=fixtures(d)
    bars["BTCUSDT"][d.start]=bars["BTCUSDT"][d.start].model_copy(update={"low":Decimal("1"),"high":Decimal("10000")})
    trades,_,_=simulate(d,decisions,bars)
    assert trades[0].entry_session==d.start and not trades[0].ambiguous


def test_next_close_full_day_publication_lag_requires_later_close():
    d=definition(execution=ExecutionPolicy(timing='next_close'))
    decisions,bars=fixtures(d)
    decisions[0]=decisions[0].model_copy(update={'cutoff':datetime.combine(d.start+timedelta(days=1),datetime.min.time(),Z)})
    trades,_,_=simulate(d,decisions,bars)
    assert trades[0].entry_session==d.start+timedelta(days=1)
    assert trades[0].entry_at>decisions[0].cutoff


def test_slippage_spread_cash_cap_and_accounting_each_day():
    d=definition(capital=100,sizing=SizingPolicy(mode="fixed_notional",value=100000),
        costs=CostModel(entry_fee_bps=10,exit_fee_bps=10,slippage_bps=20,spread_bps=40))
    decisions,bars=fixtures(d)
    trades,curve,_=simulate(d,decisions,bars)
    assert trades[0].entry_price==pytest.approx(100.4)
    assert trades[0].exit_price==pytest.approx(109.56)
    for p in curve:
        assert p.cash>=0 and p.net==pytest.approx(p.cash+p.position_value)
        assert p.net==pytest.approx(d.capital+p.realized_pnl+p.unrealized_pnl)
        assert p.net<=p.gross


def test_fixed_exit_fee_reserve_prevents_borrowing_and_baseline_r_is_null():
    d=definition(capital=250,costs=CostModel(entry_fee_bps=0,exit_fee_bps=0,slippage_bps=0,fixed_fee=100),
        sizing=SizingPolicy(mode="fixed_notional",value=1000))
    decisions,bars=fixtures(d,{"open":100,"high":110,"low":70,"close":80})
    trades,curve,_=simulate(d,decisions,bars)
    assert trades[0].quantity==.5 and all(p.cash>=0 for p in curve)
    baseline=definition(strategy_id="buy_hold",parameters=StrategyParameters(holding_sessions=2))
    decisions,bars=fixtures(baseline)
    trades,curve,_=simulate(baseline,decisions,bars)
    assert trades[0].r_multiple is None and metrics(curve,trades,baseline.capital)["average_r"] is None
    assert any(p.heat is None for p in curve)


def test_two_trades_streaks_and_loss_metrics():
    d=definition(end=date(2025,1,7))
    decisions,bars=fixtures(d)
    cal=calendar(); i,m=identity()
    for offset in range(6):
        day=d.start+timedelta(days=offset)
        b=bar(i,m,cal,day=day,close="110" if offset<4 else "90")
        bars["BTCUSDT"][day]=b.model_copy(update={"high":Decimal("115"),"low":Decimal("85")})
    second=decisions[0].model_copy(update={"session":date(2025,1,4),"cutoff":datetime(2025,1,5,0,1,tzinfo=Z),"evidence_hash":"second"})
    trades,curve,_=simulate(d,decisions+[second],bars)
    stats=metrics(curve,trades,d.capital)
    assert [t.net_pnl for t in trades]==[10,-10]
    assert stats["total_return"]==0 and stats["profit_factor"]==1 and stats["payoff_ratio"]==1
    assert stats["win_rate"]==.5 and stats["consecutive_wins"]==1 and stats["consecutive_losses"]==1


def test_known_drawdown_start_trough_recovery_and_unrecovered():
    def point(i,value):
        return EquityPoint(session=date(2025,1,1)+timedelta(days=i),cash=value,position_value=0,net=value,gross=value,
            benchmark=1000,realized_pnl=value-1000,unrealized_pnl=0,exposure=0,heat=0,concurrent_positions=0,turnover_notional=0)
    curve=[point(i,v) for i,v in enumerate([1000,900,800,850,1000,950])]
    values,report=drawdowns(curve)
    assert values==pytest.approx([0,-.1,-.2,-.15,0,-.05])
    assert report["maximum"]["start"]=="2025-01-01" and report["maximum"]["trough"]=="2025-01-03"
    assert report["maximum"]["recovery"]=="2025-01-05" and report["max_duration_sessions"]==4 and report["unrecovered"]


def synthetic_source(n=130):
    cal=calendar(); pinned=uuid4(); instruments=[]; mappings=[]; bars=[]
    for s in ("BTCUSDT","ETHUSDT","SOLUSDT","BNBUSDT","XRPUSDT"):
        i,m=identity(native=s); instruments.append(i.model_dump(mode="json")); mappings.append(m.model_dump(mode="json"))
        for k in range(n):
            day=date(2025,1,1)+timedelta(days=k)
            price=100+k*.3+(k%7)*.5
            b=bar(i,m,cal,day=day,close=str(price),available=(cal.session(day).close_at+timedelta(seconds=60)).isoformat())
            env=b.envelope.model_copy(update={"ingested_at":b.envelope.available_at})
            b=b.model_copy(update={"envelope":env,"open":Decimal(str(price-1)),"high":Decimal(str(price+2)),"low":Decimal(str(price-2)),"volume":Decimal(100+k%7*10)})
            bars.append(b.model_dump(mode="json"))
    return {"manifest_id":str(pinned),"manifest_times":{str(pinned):"2024-01-01T00:00:00Z"},
        "instruments":instruments,"mappings":mappings,"bars":bars,
        "calendars":{"XCRY":{"venue":cal.venue.model_dump(mode="json"),"calendar_id":cal.calendar_id,"version":cal.version}}}


def test_strict_recording_late_arrival_corrections_and_identity_cutoffs():
    source=synthetic_source(3)
    cutoff=datetime(2025,1,4,0,1,tzinfo=Z)
    b=source["bars"][1]
    b["envelope"]["ingested_at"]="2025-01-10T00:00:00Z"
    old=source["bars"][0]
    correction={**old,"close":"999","envelope":{**old["envelope"],"observation_id":str(uuid4()),"supersedes_observation_id":old["envelope"]["observation_id"],
        "quality_state":"corrected","available_at":"2025-01-10T00:00:00Z","ingested_at":"2025-01-10T00:00:00Z"}}
    source["bars"].append(correction)
    cat=ReplayCatalog(source,"AS_RECORDED")
    args=dict(instrument_id=UUID(source["instruments"][0]["instrument_id"]),start=datetime(2025,1,1,tzinfo=Z),end=cutoff,as_of=cutoff)
    _,visible=cat.bars(**args)
    assert len(visible)==2 and float(visible[0].close)==100
    source["mappings"][0]["available_at"]="2025-01-10T00:00:00Z"
    assert ReplayCatalog(source,"AS_RECORDED").bars(**args)[1]==[]
    reconstruction=ReplayCatalog(source,"HISTORICAL_RECONSTRUCTION")
    _,visible=reconstruction.bars(**args)
    assert len(visible)==3 and float(visible[0].close)==100
    assert visible[1].envelope.ingested_at>cutoff  # Actual provenance was never rewritten.


def test_future_candles_cannot_change_canonical_historical_decision():
    source=synthetic_source(80)
    cutoff=datetime(2025,3,10,0,1,tzinfo=Z)
    request=ScanRequest(mode="pinned",manifest_id=UUID(source["manifest_id"]),as_of=cutoff,detector_id="trend_continuation")
    before=ReplayOpportunityService(ReplayCatalog(source,"AS_RECORDED")).scan(request)
    for b in source["bars"]:
        if date.fromisoformat(b["session_date"])>=cutoff.date():
            b.update(close="99999",high="100000",low="99998",open="99999")
    after=ReplayOpportunityService(ReplayCatalog(source,"AS_RECORDED")).scan(request)
    assert [c.evidence_hash for c in before.candidates]==[c.evidence_hash for c in after.candidates]
    assert [c.status for c in before.candidates]==[c.status for c in after.candidates]


def test_reconstruction_freshness_assumption_preserves_actual_source_timestamps():
    source=synthetic_source(130)
    for b in source["bars"]:
        b["envelope"]["ingested_at"]="2026-01-01T00:00:00Z"
        b["envelope"]["available_at"]="2026-01-01T00:00:00Z"
        b["envelope"]["availability_basis"]="observed_arrival"
    cutoff=datetime(2025,4,30,0,1,tzinfo=Z)
    args=dict(instrument_id=UUID(source["instruments"][0]["instrument_id"]),start_date=date(2025,1,1),
              end_date=date(2025,4,29),as_of=cutoff,manifest_id=UUID(source["manifest_id"]),provider_id="binance")
    series=ReplayFeatureEngine(ReplayCatalog(source,"HISTORICAL_RECONSTRUCTION")).load(**args)
    assert series.freshness_state=="current" and series.bars[-1].envelope.available_at>cutoff
    recorded=ReplayFeatureEngine(ReplayCatalog(source,"AS_RECORDED")).load(**args)
    assert recorded.freshness_state=="no_data" and not any(recorded.bars)
    result=ReplayOpportunityService(ReplayCatalog(source,"HISTORICAL_RECONSTRUCTION")).scan(
        ScanRequest(mode="pinned",manifest_id=UUID(source["manifest_id"]),as_of=cutoff,detector_id="trend_continuation"))
    assert any(c.status=="VALID" for c in result.candidates)


def test_contracts_reject_same_close_arbitrary_code_bad_grid_overlap():
    with pytest.raises(ValueError):
        ExecutionPolicy(timing="same_close")
    with pytest.raises(ValueError):
        definition(strategy_id="exec_python")
    with pytest.raises(ValueError):
        definition(parameters={"python":"print(1)"})
    with pytest.raises(ValueError):
        GridRequest(definition=definition(),holding_sessions=[5,5])
    with pytest.raises(ValueError):
        WalkForwardDefinition(definition=definition(),step_sessions=10,validation_sessions=20)


from uuid import UUID


def test_independent_daily_statistics_and_inappropriate_ratios():
    import math
    # Geometric +1%/-1% daily alternation, 366 known returns. The sample
    # volatility is closed form; Sharpe at zero RF is exactly zero.
    value=1000.; points=[]
    for k in range(367):
        if k:
            value*=1.01 if k%2 else .99
        points.append(EquityPoint(session=date(2025,1,1)+timedelta(days=k),cash=value,position_value=0,
            net=value,gross=value,benchmark=1000,realized_pnl=value-1000,unrealized_pnl=0,
            exposure=0,heat=0,concurrent_positions=0,turnover_notional=0))
    result=metrics(points,[],1000)
    expected_final=(1.01*.99)**183
    assert result['total_return']==pytest.approx(expected_final-1)
    assert result['cagr']==pytest.approx(expected_final**(365/366)-1)
    assert result['annualized_volatility']==pytest.approx(.01*math.sqrt(366/365)*math.sqrt(365))
    assert result['downside_deviation']==pytest.approx(.01*math.sqrt(365/2))
    assert result['sharpe']==pytest.approx(0,abs=1e-10) and result['sortino']==pytest.approx(0,abs=1e-10)
    assert result['average_r'] is None and result['profit_factor'] is None
    assert metrics(points[:10],[],1000)['sharpe'] is None


def test_immutable_definition_result_and_study_hash_tampering_rejected():
    from market_cortex.quant_store import QuantStore,digest
    payload={'definition':{'capital':1000},'manifest':{'definition_hash':digest({'capital':1000})},
        'decisions':[],'trades':[],'equity':[],'metrics':{'N':0},'drawdown':{},'controls':{},'regime_performance':[]}
    payload['result_hash']=digest({k:payload[k] for k in ('decisions','trades','equity','metrics','drawdown','controls')}|{'regimes':[]})
    assert QuantStore.verify(payload)==payload
    payload['definition']['capital']=2000
    with pytest.raises(ValueError,match='DEFINITION_HASH'):
        QuantStore.verify(payload)
    payload['definition']['capital']=1000;payload['metrics']['N']=1
    with pytest.raises(ValueError,match='RESULT_HASH'):
        QuantStore.verify(payload)
    core={'schema_version':'quant_study_v1','kind':'sensitivity','definition':{},'result':{'rows':[]}}
    frozen=digest(core)
    assert QuantStore.verify_content('sensitivity',core,frozen)==core
    core['result']['rows'].append({'total_return':99})
    with pytest.raises(ValueError,match='CONTENT_HASH'):
        QuantStore.verify_content('sensitivity',core,frozen)


@pytest.mark.parametrize('question,expected',[
    ('Compare momentum and trend continuation',['momentum','trend_continuation']),
    ('How has the breakout strategy performed?',['breakout'])])
def test_cortex_quant_questions_select_every_named_registered_strategy(question,expected):
    from market_cortex.cortex import CortexService
    from market_cortex.cortex_contracts import ResearchRequest
    from test_phase4_cortex import FakeCatalog,context,settings
    ctx=context()
    plan=CortexService(FakeCatalog(),settings())._plan(ResearchRequest(
        question=question,mode='pinned',manifest_id=ctx.manifest_id,as_of=ctx.as_of),ctx)
    assert plan[0][0]=='dataset.context'
    assert [args['strategy_id'] for tool,args,_ in plan if tool=='quant.runs']==expected
    assert all(tool in ('dataset.context','quant.runs') for tool,_,_ in plan)


def test_quant_disclosure_survives_model_selection_and_includes_other_strategy():
    from market_cortex.cortex import CortexService,_claim
    from market_cortex.cortex_contracts import ResearchRequest
    from test_phase4_cortex import FakeCatalog,context,settings,evidence
    ctx=context()
    values=[('Quant momentum m context','N=108; period=2024..2026; costs=10bps; OOS=in-sample'),
            ('Quant momentum m total_return',-.26),('Quant trend_continuation t context','N=145; period=2024..2026; costs=10bps; OOS=in-sample'),
            ('Quant trend_continuation t total_return',-.21)]
    claims=[_claim('OBSERVATION',f'{label}: {value}.',[evidence(ctx,label,value)],'neutral') for label,value in values]
    service=CortexService(FakeCatalog(),settings())
    answer=service._synthesize(ResearchRequest(question='Compare momentum and trend continuation',mode='pinned',
        manifest_id=ctx.manifest_id,as_of=ctx.as_of),ctx,claims,{claims[1].claim_id},'weak')
    assert 'Quant Lab research' in answer and 'N=108' in answer and 'N=145' in answer
    assert 'costs=10bps' in answer and 'OOS=in-sample' in answer and '-0.21' in answer
    assert 'next stored daily close crosses SMA20' not in answer
