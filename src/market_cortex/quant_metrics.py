"""Independent float64 descriptive statistics; undefined statistics remain null."""
import numpy as np


def streak(values, positive):
    longest=current=0
    for v in values:
        current=current+1 if (v>0 if positive else v<0) else 0
        longest=max(longest,current)
    return longest


def drawdowns(points):
    peak=points[0].net
    peak_day=points[0].session
    active=None
    episodes=[]
    series=[]
    for p in points:
        if p.net>=peak:
            if active:
                active["recovery"]=str(p.session)
                active["duration_sessions"]=(p.session-active.pop("start_date")).days
                episodes.append(active)
                active=None
            peak=p.net
            peak_day=p.session
        dd=p.net/peak-1 if peak>0 else 0
        series.append(dd)
        if dd<0:
            if active is None:
                active={"start":str(peak_day),"start_date":peak_day,"trough":str(p.session),
                        "depth":dd,"recovery":None,"duration_sessions":0}
            if dd<active["depth"]:
                active.update(depth=dd,trough=str(p.session))
    if active:
        active["duration_sessions"]=(points[-1].session-active.pop("start_date")).days
        episodes.append(active)
    return series,{"episodes":episodes,"maximum":min(episodes,key=lambda x:x["depth"]) if episodes else None,
                   "max_duration_sessions":max((x["duration_sessions"] for x in episodes),default=0),
                   "unrecovered":bool(episodes and episodes[-1]["recovery"] is None)}


def metrics(points, trades, capital, annualization=365, risk_free=0):
    equity=np.array([p.net for p in points],dtype=np.float64)
    returns=equity[1:]/equity[:-1]-1
    n=len(trades)
    pnls=np.array([t.net_pnl for t in trades],dtype=np.float64)
    trade_returns=np.array([t.return_fraction for t in trades],dtype=np.float64)
    rs=[t.r_multiple for t in trades if t.r_multiple is not None]
    wins=pnls[pnls>0]; losses=pnls[pnls<0]
    elapsed=(points[-1].session-points[0].session).days
    total=equity[-1]/capital-1
    volatility=float(np.std(returns,ddof=1)*np.sqrt(annualization)) if len(returns)>=2 else None
    excess=returns-((1+risk_free)**(1/annualization)-1)
    downside=float(np.sqrt(np.mean(np.minimum(excess,0)**2))*np.sqrt(annualization)) if len(returns)>=2 else None
    dds,dd=drawdowns(points)
    average=lambda x:float(np.mean(x)) if len(x) else None
    return {"N":n,"sessions":len(returns),"total_return":total,
        "gross_total_return":points[-1].gross/capital-1,
        "benchmark_return":points[-1].benchmark/capital-1,
        "benchmark_relative_return":equity[-1]/points[-1].benchmark-1 if points[-1].benchmark>0 else None,
        "cagr":float((equity[-1]/capital)**(annualization/elapsed)-1) if elapsed>=365 and equity[-1]>0 else None,
        "annualized_volatility":volatility,"max_drawdown":min(dds),
        "drawdown_duration_sessions":dd["max_duration_sessions"],
        "downside_deviation":downside,
        "sharpe":float(np.mean(excess)*annualization/volatility) if len(returns)>=30 and volatility and volatility>1e-12 else None,
        "sortino":float(np.mean(excess)*annualization/downside) if len(returns)>=30 and downside and downside>1e-12 else None,
        "risk_free_rate":risk_free,"annualization":annualization,
        "win_rate":len(wins)/n if n else None,"loss_rate":len(losses)/n if n else None,
        "average_trade_return":average(trade_returns),"median_trade_return":float(np.median(trade_returns)) if n else None,
        "best_trade_return":float(np.max(trade_returns)) if n else None,"worst_trade_return":float(np.min(trade_returns)) if n else None,
        "average_r":average(rs),"r_expectancy":average(rs),
        "payoff_ratio":float(np.mean(wins)/-np.mean(losses)) if len(wins) and len(losses) else None,
        "profit_factor":float(np.sum(wins)/-np.sum(losses)) if len(losses) else None,
        "exposure_time":sum(p.concurrent_positions>0 for p in points[1:])/len(returns) if len(returns) else None,
        "mean_exposure":average([p.exposure for p in points[1:]]),
        "turnover":sum(p.turnover_notional for p in points)/capital,
        "average_holding_sessions":average([t.holding_sessions for t in trades]),
        "consecutive_wins":streak(pnls,True),"consecutive_losses":streak(pnls,False),
        "net_pnl":float(np.sum(pnls)),"cost_drag":points[-1].gross-points[-1].net}
