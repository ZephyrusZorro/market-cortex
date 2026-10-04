"""Long-only daily research accounting, isolated from providers and order APIs."""
from dataclasses import dataclass, field
from datetime import datetime, time, timedelta, timezone
from decimal import Decimal
from uuid import NAMESPACE_URL, uuid5

from .quant_contracts import EquityPoint, SimulatedTrade
from .quant_replay import days
from .risk import research_sizing
from .risk_contracts import SizingRequest


@dataclass
class BacktestPosition:
    symbol: str
    decision: object
    bar: object
    quantity: float
    reference: float
    entry: float
    fee: float
    stop: float
    target: float
    held: int=0
    mae: float=0
    mfe: float=0
    observations: list[str]=field(default_factory=list)


def simulate(definition, decisions, bars):
    d=definition
    cash=d.capital
    friction=realized=0.
    positions={}
    pending={}
    trades=[]
    curve=[]
    warnings=[]
    by_day={}
    for item in decisions:
        by_day.setdefault(item.session,[]).append(item)
        if item.enter and item.session<d.start:
            scheduled=item.session+timedelta(days=1+d.execution.delay_sessions)
            if d.execution.timing=="next_open":
                while datetime.combine(scheduled,time.min,timezone.utc)<=item.cutoff:
                    scheduled+=timedelta(days=1)
            else:
                scheduled=max(scheduled,d.start)
                while datetime.combine(scheduled+timedelta(days=1),time.min,timezone.utc)<=item.cutoff:
                    scheduled+=timedelta(days=1)
            if d.start<=scheduled<=d.end:
                pending[item.symbol]=(scheduled,item)
    impact=(d.costs.slippage_bps+d.costs.spread_bps/2)/10000
    capital=d.capital
    timeline=days(d.start,d.end)
    benchmark_symbols=["BTCUSDT"] if d.benchmark=="BTCUSDT" else d.symbols
    bases={s:float(bars.get(s,{}).get(d.start).open) for s in benchmark_symbols if bars.get(s,{}).get(d.start)}
    if d.benchmark!="cash" and len(bases)!=len(benchmark_symbols):
        warnings.append("BENCHMARK_UNAVAILABLE_FULL_PERIOD; CASH_REFERENCE_USED_NOT_VALID_BENCHMARK")
    curve.append(EquityPoint(session=d.start-timedelta(days=1),cash=cash,position_value=0,net=cash,gross=cash,
        benchmark=cash,realized_pnl=0,unrealized_pnl=0,exposure=0,heat=0,concurrent_positions=0,turnover_notional=0))

    def close(symbol,bar,reference,reason,ambiguous=False):
        nonlocal cash,friction,realized,turnover
        p=positions.pop(symbol)
        price=reference*(1-impact)
        fee=p.quantity*price*d.costs.exit_fee_bps/10000+d.costs.fixed_fee
        proceeds=p.quantity*price-fee
        pnl=proceeds-p.quantity*p.entry-p.fee
        cash+=proceeds
        realized+=pnl
        friction+=p.quantity*(reference-price)+fee
        turnover+=p.quantity*reference
        gross=p.quantity*(reference-p.reference)
        entry_at=p.bar.start_at if d.execution.timing=="next_open" else p.bar.end_at
        exit_at=bar.start_at if reason=="gap_stop" else bar.end_at
        regime=p.decision.candidate.get("market_regime") if p.decision.candidate else "baseline"
        trades.append(SimulatedTrade(trade_id=uuid5(NAMESPACE_URL,f"{p.decision.evidence_hash}:{entry_at}:{exit_at}:{reason}"),
            symbol=symbol,signal_session=p.decision.session,signal_at=p.decision.cutoff,decision_hash=p.decision.evidence_hash,
            entry_session=p.bar.session_date,entry_at=entry_at,exit_session=bar.session_date,exit_at=exit_at,
            quantity=p.quantity,entry_reference=p.reference,exit_reference=reference,entry_price=p.entry,exit_price=price,
            entry_fee=p.fee,exit_fee=fee,friction=gross-pnl,gross_pnl=gross,net_pnl=pnl,
            return_fraction=pnl/(p.quantity*p.reference),r_multiple=pnl/(p.quantity*(p.entry-p.stop))
                if d.strategy_id not in ("buy_hold","equal_weight") else None,
            holding_sessions=p.held,exit_reason=reason,ambiguous=ambiguous,mae=p.mae,mfe=p.mfe,
            regime=regime or "unknown",source_observation_ids=list(dict.fromkeys(p.observations))))

    def enter(symbol,decision,bar):
        nonlocal cash,friction,turnover
        if symbol in positions or len(positions)>=d.max_positions:
            return
        reference=float(bar.open if d.execution.timing=="next_open" else bar.close)
        at=bar.start_at if d.execution.timing=="next_open" else bar.end_at
        if at<=decision.cutoff:
            raise ValueError("ENTRY_NOT_AFTER_SIGNAL_AVAILABILITY")
        price=reference*(1+impact)
        stop=price*(1-d.parameters.stop_fraction)
        if d.sizing.mode=="fixed_quantity":
            requested=d.sizing.value
        elif d.sizing.mode=="fractional_risk":
            equity=cash+sum(p.quantity*float(bars[p.symbol][bar.session_date-timedelta(days=1)].close)
                            for p in positions.values())
            sized=research_sizing(SizingRequest(capital=Decimal(str(equity)),entry_price=Decimal(str(price)),
                invalidation_price=Decimal(str(stop)),risk_percent=Decimal(str(d.sizing.value))))
            requested=float(sized["hypothetical_quantity"])
        else:
            slots=len(d.symbols) if d.strategy_id in ("buy_hold","equal_weight") else d.max_positions
            requested=(capital/slots if d.sizing.mode=="equal_weight" else d.sizing.value)/price
        # Existing positions' fixed exit fees, plus both sides of this new fill.
        reserves=d.costs.fixed_fee*(len(positions)+2)
        quantity=min(requested,max(0,(cash-reserves)/(price*(1+d.costs.entry_fee_bps/10000))))
        if quantity*price<1e-8:
            return
        fee=quantity*price*d.costs.entry_fee_bps/10000+d.costs.fixed_fee
        cash-=quantity*price+fee
        if cash<0 and cash>-1e-7:
            cash=0
        if cash<0:
            raise ValueError("NEGATIVE_SIMULATED_CASH")
        friction+=quantity*(price-reference)+fee
        turnover+=quantity*reference
        positions[symbol]=BacktestPosition(symbol,decision,bar,quantity,reference,price,fee,stop,
                                          price+(price-stop)*d.parameters.target_r)

    for day in timeline:
        turnover=0.
        # Prior decisions schedule entries. Sorted symbols make cash contention deterministic.
        for symbol,(scheduled,decision) in sorted(list(pending.items())):
            if scheduled==day and d.execution.timing=="next_open":
                pending.pop(symbol)
                bar=bars.get(symbol,{}).get(day)
                if bar is None:
                    warnings.append(f"MISSING_EXECUTION_BAR:{symbol}:{day}; SIGNAL_EXPIRED")
                else:
                    enter(symbol,decision,bar)
        for symbol,p in sorted(list(positions.items())):
            bar=bars.get(symbol,{}).get(day)
            if bar is None:
                raise ValueError("OPEN_POSITION_HAS_MISSING_MARK; RUN_INVALID")
            p.observations.append(str(bar.envelope.observation_id))
            p.held+=1
            # Next-close entries cannot use earlier high/low of their entry candle.
            if day>p.bar.session_date or d.execution.timing=="next_open":
                p.mae=min(p.mae,float(bar.low)/p.entry-1)
                p.mfe=max(p.mfe,float(bar.high)/p.entry-1)
                stop=float(bar.low)<=p.stop
                target=float(bar.high)>=p.target
                baseline=d.strategy_id in ("buy_hold","equal_weight")
                if not baseline and float(bar.open)<=p.stop:
                    close(symbol,bar,float(bar.open),"gap_stop")
                    continue
                if not baseline and (stop or target):
                    choose_stop=stop and (not target or d.execution.ambiguity=="stop_first")
                    close(symbol,bar,p.stop if choose_stop else p.target,"stop" if choose_stop else "target",stop and target)
                    continue
            if day==d.end or (d.strategy_id not in ("buy_hold","equal_weight") and p.held>=d.parameters.holding_sessions):
                close(symbol,bar,float(bar.close),"period_end" if day==d.end else "time_exit")
        if d.execution.timing=="next_close":
            for symbol,(scheduled,decision) in sorted(list(pending.items())):
                if scheduled==day:
                    pending.pop(symbol)
                    bar=bars.get(symbol,{}).get(day)
                    if bar and day<d.end:
                        enter(symbol,decision,bar)
                    elif not bar:
                        warnings.append(f"MISSING_EXECUTION_BAR:{symbol}:{day}; SIGNAL_EXPIRED")
        for decision in by_day.get(day,[]):
            if not decision.enter or decision.symbol in positions or decision.symbol in pending:
                continue
            scheduled=day+timedelta(days=1+d.execution.delay_sessions)
            if d.execution.timing=="next_open":
                while datetime.combine(scheduled,time.min,timezone.utc)<=decision.cutoff:
                    scheduled+=timedelta(days=1)
            else:
                while datetime.combine(scheduled+timedelta(days=1),time.min,timezone.utc)<=decision.cutoff:
                    scheduled+=timedelta(days=1)
            if scheduled<=d.end:
                pending[decision.symbol]=(scheduled,decision)
        value=sum(p.quantity*float(bars[s][day].close) for s,p in positions.items())
        basis=sum(p.quantity*p.entry+p.fee for p in positions.values())
        net=cash+value
        unrealized=value-basis
        if abs(net-(capital+realized+unrealized))>1e-6*max(1,capital):
            raise ValueError("ACCOUNTING_DOES_NOT_RECONCILE")
        benchmark=capital
        if d.benchmark!="cash" and len(bases)==len(benchmark_symbols):
            if any(not bars.get(s,{}).get(day) for s in bases):
                raise ValueError("BENCHMARK_MISSING_SESSION")
            benchmark=capital*sum(float(bars[s][day].close)/bases[s] for s in bases)/len(bases)
        curve.append(EquityPoint(session=day,cash=cash,position_value=value,net=net,gross=net+friction,
            benchmark=benchmark,realized_pnl=realized,unrealized_pnl=unrealized,exposure=value/net if net>0 else 0,
            heat=None if positions and d.strategy_id in ("buy_hold","equal_weight") else
                sum(p.quantity*(p.entry-p.stop) for p in positions.values())/net if net>0 else 0,
            concurrent_positions=len(positions),turnover_notional=turnover))
    return trades,curve,list(dict.fromkeys(warnings))
