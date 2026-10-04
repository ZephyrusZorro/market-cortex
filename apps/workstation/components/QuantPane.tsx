'use client';

import {useEffect,useState} from 'react';
import {ApiError,getJson,postJson,shortId,type Context} from '@/lib/api';
import {QuantChart} from './charts';

type Strategy={strategy_id:string;version:string;description:string;entry_policy:string;exit_policy:string;required_features:string[];minimum_history:number};
type Row={artifact_id:string;strategy_id:string;kind?:string;metrics:Record<string,number|null>};
type Definition={strategy_id:string;start:string;end:string;replay_policy:string;costs:Record<string,number>;execution:Record<string,unknown>;parameters:Record<string,number>;manifest_id:string;source_as_of:string};
type Trade={trade_id:string;symbol:string;signal_at:string;entry_session:string;exit_session:string;net_pnl:number;return_fraction:number;r_multiple:number|null;exit_reason:string;ambiguous:boolean;decision_hash:string;[key:string]:unknown};
type Run={run_id:string;definition:Definition;metrics:Record<string,number|null>;warnings:string[];trades:Trade[];result_hash:string;manifest:Record<string,unknown>;regime_performance:Record<string,unknown>[];controls:{groups:Record<string,unknown>[];warning:string};drawdown:Record<string,unknown>;
  equity:{session:string;net:number;gross:number;benchmark:number;drawdown:number}[];decisions:{symbol:string;session:string;evidence_hash:string;[key:string]:unknown}[]};
type Study={study_id:string;kind:string;warnings:string[];result:Record<string,unknown>};
type Job={job_id:string;status:string;result_ref:string|null;error_code:string|null};
const fmt=(v:unknown)=>v==null?'unavailable':typeof v==='number'?Number(v.toFixed(6)).toString():typeof v==='object'?JSON.stringify(v):String(v);
const flatten=(row:Record<string,unknown>)=>{const {metrics,...identity}=row;const m=metrics as Record<string,unknown>;return {N:m.N,net_return:m.total_return,max_drawdown:m.max_drawdown,gross_return:m.gross_total_return,...identity,win_rate:m.win_rate,profit_factor:m.profit_factor};};
function DataTable({rows}:{rows:Record<string,unknown>[]}) {
  if(!rows.length)return <p className="muted">Insufficient observations.</p>;
  const columns=Array.from(new Set(rows.flatMap(r=>Object.keys(r))));
  return <div style={{overflowX:'auto'}}><table className="table"><thead><tr>{columns.map(k=><th key={k}>{k.replaceAll('_',' ')}</th>)}</tr></thead><tbody>{rows.map((r,i)=><tr key={i}>{columns.map(k=><td key={k}>{fmt(r[k])}</td>)}</tr>)}</tbody></table></div>;
}
function StudyResult({study}:{study:Study}) {
  const r=study.result;
  const rows=(r.rows??[]) as Record<string,unknown>[];
  const folds=(r.folds??[]) as Record<string,unknown>[];
  const origin=Date.parse(String(folds[0]?.train_start)),finish=Date.parse(String(folds.at(-1)?.validation_end))+86400000;
  const segment=(start:unknown,end:unknown)=>({left:`${100*(Date.parse(String(start))-origin)/(finish-origin)}%`,width:`${100*(Date.parse(String(end))+86400000-Date.parse(String(start)))/(finish-origin)}%`});
  return <section className="panel"><div className="panel-head"><h2>{study.kind.replaceAll('_',' ')} · {shortId(study.study_id)}</h2></div><div className="panel-body">
    {study.warnings.map(w=><p className="muted small" key={w}>{w}</p>)}
    {study.kind==='walk_forward'?<><p>OOS N: {fmt(r.oos_N)} · {fmt(r.sample_status)} · compound return: {fmt(r.oos_total_return_compounded_reset_capital)}</p>
      <p className="muted small">Timeline: grey training · teal validation. All training combinations are shown below each fold.</p>
      {folds.map((fold,i)=><details key={i} open><summary>Fold {fmt(fold.fold)}: train {fmt(fold.train_start)}–{fmt(fold.train_end)} → OOS {fmt(fold.validation_start)}–{fmt(fold.validation_end)}</summary>
        <div role="img" aria-label={`Fold ${fold.fold} training and validation date ranges`} style={{position:'relative',height:18,background:'#13211e',marginTop:10,borderRadius:3}}><span title="Training" style={{position:'absolute',height:18,background:'#697773',borderRadius:3,...segment(fold.train_start,fold.train_end)}}/><span title="Out of sample validation" style={{position:'absolute',height:18,background:'#6aaea2',borderRadius:3,...segment(fold.validation_start,fold.validation_end)}}/></div>
        <p style={{overflowWrap:'anywhere'}}>Frozen parameters: {fmt(fold.selected_parameters)} · train score: {fmt(fold.training_score)}</p>
        <p>Out of sample results</p><DataTable rows={[flatten({metrics:fold.oos_metrics})]}/>
        <p>All training combinations</p><DataTable rows={(fold.search_results as Record<string,unknown>[]).map(flatten)}/></details>)}</>:
      study.kind==='monte_carlo'?<><p>Source trades N: {fmt(r.source_trade_N)} · simulations: {fmt(r.simulations)} · seed: {fmt(r.seed)} · {fmt(r.method)}</p><p>{fmt(r.sample_status)}</p><p className="muted">{fmt(r.methodology)}</p>
        <DataTable rows={['terminal_return','max_drawdown','losing_streak'].map(metric=>({metric,...r[metric] as Record<string,unknown>}))}/></>:
      <><p>{study.kind==='robustness'?`Classification: ${fmt(r.classification)} · minimum cell N: ${fmt(r.minimum_cell_N)} · positive fraction: ${fmt(r.positive_fraction)}`:study.kind==='comparison'?`Directly comparable: ${fmt(r.directly_comparable)} · every requested run is shown`:`Combinations: ${fmt(r.combinations??rows.length)} · positive fraction: ${fmt(r.positive_fraction)} · return range: ${fmt(r.range)}`}</p>
        <DataTable rows={rows.map(flatten)}/></>}
    <details><summary>Complete study definition, metrics and lineage</summary><pre style={{whiteSpace:'pre-wrap'}}>{JSON.stringify(study,null,2)}</pre></details>
  </div></section>;
}

export default function QuantPane({context}:{context:Context}) {
  const [strategies,setStrategies]=useState<Strategy[]>([]),[runs,setRuns]=useState<Row[]>([]),[studies,setStudies]=useState<Row[]>([]);
  const [selected,setSelected]=useState<string[]>([]),[run,setRun]=useState<Run|null>(null),[study,setStudy]=useState<Study|null>(null);
  const [strategy,setStrategy]=useState('momentum'),[start,setStart]=useState(context.history_start??''),[end,setEnd]=useState(context.evaluation_date??'');
  const [policy,setPolicy]=useState('AS_RECORDED'),[timing,setTiming]=useState('next_open'),[ambiguity,setAmbiguity]=useState('stop_first');
  const [capital,setCapital]=useState('10000'),[hold,setHold]=useState('10'),[stop,setStop]=useState('0.08'),[target,setTarget]=useState('2');
  const [fee,setFee]=useState('10'),[slippage,setSlippage]=useState('5'),[spread,setSpread]=useState('0'),[benchmark,setBenchmark]=useState('same_universe_equal_weight');
  const [exitFee,setExitFee]=useState('10'),[fixedFee,setFixedFee]=useState('0'),[openId,setOpenId]=useState('');
  const [symbols,setSymbols]=useState(context.members.map(m=>m.symbol)),[sizing,setSizing]=useState('equal_weight'),[sizeValue,setSizeValue]=useState('0.01');
  const [positions,setPositions]=useState('5'),[delay,setDelay]=useState('0'),[lag,setLag]=useState('60');
  const [gridH,setGridH]=useState('5,10,15'),[gridS,setGridS]=useState('0.06,0.08,0.10'),[train,setTrain]=useState('120'),[validation,setValidation]=useState('60'),[mode,setMode]=useState('rolling');
  const [seed,setSeed]=useState('42'),[simulations,setSimulations]=useState('500'),[mcMethod,setMcMethod]=useState('bootstrap');
  const [job,setJob]=useState<Job|null>(null),[operation,setOperation]=useState(''),[error,setError]=useState(''),[counts,setCounts]=useState<unknown>();
  const [trade,setTrade]=useState<Trade|null>(null),[tab,setTab]=useState('Backtests'),[busy,setBusy]=useState(false);
  const [edges,setEdges]=useState<{edge_id:string;title:string;quant_evidence?:{revision:number}}[]>([]),[edgeId,setEdgeId]=useState(''),[edgeStatus,setEdgeStatus]=useState('HYPOTHESIS'),[reason,setReason]=useState(''),[message,setMessage]=useState('');
  const fail=(e:unknown)=>setError(e instanceof ApiError?e.code:'REQUEST_FAILED');
  async function refresh() {
    const [a,b,c,d]=await Promise.all([getJson<{items:Strategy[]}>('quant/strategies'),getJson<{items:Row[];search_counts:unknown}>('quant/runs'),getJson<{items:Row[]}>('quant/studies'),getJson<{items:typeof edges}>('learning/edges')]);
    setStrategies(a.items);setRuns(b.items);setCounts(b.search_counts);setStudies(c.items);setEdges(d.items);
  }
  useEffect(()=>{refresh().catch(fail);},[]); // The parent remounts when the pinned context changes.
  useEffect(()=>{setTrade(null);},[run?.run_id]);
  useEffect(()=>{
    if(!job||!['queued','running'].includes(job.status))return;
    const timer=setInterval(()=>{getJson<Job>(`quant/jobs/${job.job_id}`).then(async j=>{setJob(j);
      if(j.status==='completed'&&j.result_ref){if(operation==='backtest')setRun(await getJson<Run>(`quant/runs/${j.result_ref}`));else setStudy(await getJson<Study>(`quant/studies/${j.result_ref}`));await refresh();}
      if(j.status==='failed')setError(j.error_code??'QUANT_RESEARCH_FAILED');
    }).catch(fail);},1500);return()=>clearInterval(timer);
  },[job?.job_id,job?.status,operation]);
  const definition=()=>({strategy_id:strategy,manifest_id:context.source_manifest_id,source_as_of:context.as_of,start,end,symbols,
    replay_policy:policy,capital:Number(capital),max_positions:Number(positions),publication_lag_seconds:Number(lag),benchmark,
    parameters:{holding_sessions:Number(hold),stop_fraction:Number(stop),target_r:Number(target)},
    execution:{timing,ambiguity,delay_sessions:Number(delay)},costs:{entry_fee_bps:Number(fee),exit_fee_bps:Number(exitFee),fixed_fee:Number(fixedFee),slippage_bps:Number(slippage),spread_bps:Number(spread)},sizing:{mode:sizing,value:Number(sizeValue)}});
  async function launch(op:string,payload:unknown) {
    setError('');setBusy(true);setOperation(op);
    try{const queued=await postJson<{job_id:string}>('quant/jobs',{operation:op,payload});setJob({job_id:queued.job_id,status:'queued',result_ref:null,error_code:null});}
    catch(e){fail(e);}finally{setBusy(false);}
  }
  const grid=()=>({definition:run?.definition??definition(),holding_sessions:gridH.split(',').map(Number),stop_fraction:gridS.split(',').map(Number)});
  const field=(label:string,value:string,set:(v:string)=>void)=><label className="small muted">{label}<input className="input" aria-label={label} value={value} onChange={e=>set(e.target.value)}/></label>;
  const working=busy||['queued','running'].includes(job?.status??'');
  return <div className="stack"><section className="panel"><div className="panel-head"><h2>Quant Lab</h2><span className="badge">Research only</span></div><div className="panel-body">
    <p className="muted">Registered strategies · immutable evidence · explicit costs · temporal validation. Historical reconstruction is assumed research; strict replay uses actual recording times.</p>
    <div className="row wrap">{['Strategies','Backtests','Research studies','Edge evidence'].map(t=><button className={`button ${tab===t?'active':''}`} key={t} onClick={()=>setTab(t)}>{t}</button>)}</div>
    {error&&<p role="alert">{error}</p>}{job&&<p role="status">Research job: {job.status} · {shortId(job.job_id)}</p>}
    {job?.status==='failed'&&<button className="button" onClick={()=>postJson(`quant/jobs/${job.job_id}/retry`,{}).then(()=>setJob({...job,status:'queued'})).catch(fail)}>Retry failed research</button>}
  </div></section>
  {tab==='Strategies'&&<DataTable rows={strategies.map(s=>({...s}))}/>}
  {tab==='Backtests'&&<><section className="panel"><div className="panel-head"><h2>Create backtest</h2><span>Pinned manifest {shortId(context.source_manifest_id)}</span></div><div className="panel-body">
    <div className="row wrap"><label>Strategy<select className="input" aria-label="Quant strategy" value={strategy} onChange={e=>{setStrategy(e.target.value);if(e.target.value==='buy_hold'){setSymbols([symbols[0]??context.members[0]?.symbol].filter(Boolean));if(sizing==='fractional_risk')setSizing('equal_weight');}if(e.target.value==='equal_weight'){setPositions(String(Math.max(Number(positions),symbols.length)));if(sizing==='fractional_risk')setSizing('equal_weight');}}}>{strategies.map(s=><option key={s.strategy_id}>{s.strategy_id}</option>)}</select></label>
      <label>Replay policy<select className="input" aria-label="Replay policy" value={policy} onChange={e=>setPolicy(e.target.value)}><option>AS_RECORDED</option><option>HISTORICAL_RECONSTRUCTION</option></select></label>
      {field('Start session',start,setStart)}{field('End session',end,setEnd)}{field('Capital USDT',capital,setCapital)}{field('Max positions',positions,setPositions)}
      <label>Entry timing<select className="input" aria-label="Entry timing" value={timing} onChange={e=>setTiming(e.target.value)}><option>next_open</option><option>next_close</option></select></label>
      <label>Ambiguity<select className="input" value={ambiguity} onChange={e=>setAmbiguity(e.target.value)}><option>stop_first</option><option>target_first</option></select></label>
      {field('Entry delay sessions',delay,setDelay)}{field('Publication lag seconds',lag,setLag)}{field('Hold sessions',hold,setHold)}{field('Stop fraction',stop,setStop)}{field('Target R',target,setTarget)}
      {field('Entry fee bps',fee,setFee)}{field('Exit fee bps',exitFee,setExitFee)}{field('Fixed fee per fill USDT',fixedFee,setFixedFee)}{field('Slippage each side bps',slippage,setSlippage)}{field('Spread proxy bps',spread,setSpread)}
      <label>Sizing<select className="input" value={sizing} onChange={e=>setSizing(e.target.value)}>{['equal_weight','fixed_notional','fixed_quantity','fractional_risk'].map(v=><option key={v}>{v}</option>)}</select></label>{field('Sizing value',sizeValue,setSizeValue)}
      <label>Benchmark<select className="input" value={benchmark} onChange={e=>setBenchmark(e.target.value)}>{['same_universe_equal_weight','BTCUSDT','cash'].map(v=><option key={v}>{v}</option>)}</select></label>
    </div><div className="row wrap mt12">{context.members.map(m=><label key={m.symbol}><input type="checkbox" checked={symbols.includes(m.symbol)} onChange={e=>setSymbols(e.target.checked?(strategy==='buy_hold'?[m.symbol]:[...symbols,m.symbol]):symbols.filter(s=>s!==m.symbol))}/>{m.symbol}</label>)}</div>
    <p className="muted small">Publication lag can miss the immediately following open. No leverage. Costs and spreads are proxies; daily intrabar order is unknown.</p>
    <button className="button" disabled={working||!symbols.length} onClick={()=>launch('backtest',definition())}>Queue backtest</button>
  </div></section><section className="panel"><div className="panel-head"><h2>Saved runs</h2><button className="button" onClick={()=>refresh().catch(fail)}>Refresh</button></div><div className="panel-body">
    <div className="row wrap">{field('Saved run ID',openId,setOpenId)}<button className="button" disabled={!openId} onClick={()=>getJson<Run>(`quant/runs/${openId.trim()}`).then(setRun).catch(fail)}>Open saved run ID</button></div>
    <p className="muted small">Latest 50 runs. Search history: {fmt(counts)}</p>{runs.map(r=><div className="data-row" key={r.artifact_id}><label><input type="checkbox" aria-label={`Compare ${r.artifact_id}`} checked={selected.includes(r.artifact_id)} onChange={e=>setSelected(e.target.checked?[...selected,r.artifact_id]:selected.filter(s=>s!==r.artifact_id))}/>{r.strategy_id} · N={fmt(r.metrics?.N)} · return={fmt(r.metrics?.total_return)}</label>
      <button className="button" onClick={()=>getJson<Run>(`quant/runs/${r.artifact_id}`).then(setRun).catch(fail)}>Open {shortId(r.artifact_id)}</button></div>)}
    <button className="button mt12" disabled={working||selected.length<2} onClick={()=>launch('comparison',{run_ids:selected})}>Compare selected runs</button>
  </div></section></>}
  {run&&tab==='Backtests'&&<><section className="panel"><div className="panel-head"><h2>{run.definition.strategy_id} · run detail</h2><button className="button" onClick={()=>postJson(`quant/runs/${run.run_id}/replay`,{}).then(r=>setMessage(fmt(r))).catch(fail)}>Verify saved replay</button></div><div className="panel-body">
    <p>N={run.metrics.N} · {run.definition.start}–{run.definition.end} · {run.definition.replay_policy} · single run in-sample</p><p>Costs: {fmt(run.definition.costs)} · execution: {fmt(run.definition.execution)}</p>
    {run.warnings.map(w=><p className="muted small" key={w}>{w}</p>)}{run.metrics.benchmark_return==null&&<p className="muted">Benchmark unavailable for this replay.</p>}<QuantChart points={run.equity} benchmarkAvailable={run.metrics.benchmark_return!=null}/>
    <DataTable rows={Object.entries(run.metrics).map(([metric,value])=>({metric,value}))}/>
    <details><summary>Drawdown episodes and immutable lineage</summary><pre style={{whiteSpace:'pre-wrap'}}>{JSON.stringify({drawdown:run.drawdown,manifest:run.manifest,result_hash:run.result_hash},null,2)}</pre></details>
    <h3>Daily simulated trades</h3>{run.trades.map(t=><div className="data-row" key={t.trade_id}><span>{t.symbol} · {t.entry_session} → {t.exit_session} · P/L {fmt(t.net_pnl)} · {t.exit_reason}{t.ambiguous?' · AMBIGUOUS':''}</span><button className="button" onClick={()=>setTrade(t)}>Inspect trade</button></div>)}
    {trade&&<details open><summary>Trade inspector · {trade.symbol}</summary><DataTable rows={Object.entries(trade).filter(([key])=>!['source_observation_ids','decision_hash'].includes(key)).map(([field,value])=>({field,value}))}/>
      <details><summary>Frozen detector evidence, state and observation lineage</summary><pre style={{whiteSpace:'pre-wrap'}}>{JSON.stringify({observations:trade.source_observation_ids,manifest:run.definition.manifest_id,decision:run.decisions.find(d=>d.evidence_hash===trade.decision_hash)},null,2)}</pre></details></details>}
    <h3>Regimes · per-cell sample sizes</h3><DataTable rows={run.regime_performance}/><h3>Rejected / NO_EDGE retrospective controls</h3><p className="muted">{run.controls.warning}</p><DataTable rows={run.controls.groups}/>
  </div></section></>}
  {tab==='Research studies'&&<section className="panel"><div className="panel-head"><h2>Bounded research</h2></div><div className="panel-body"><p>Uses the open run definition; all grid combinations are retained. Validation chooses parameters using training results only.</p>
    {run&&<p>Open run: {run.definition.strategy_id} · {shortId(run.run_id)} · N={run.metrics.N} · {run.definition.start}–{run.definition.end} · {run.definition.replay_policy}</p>}
    <div className="row wrap">{field('Holding grid',gridH,setGridH)}{field('Stop grid',gridS,setGridS)}{field('Train sessions',train,setTrain)}{field('OOS sessions',validation,setValidation)}<select className="input" aria-label="Walk-forward mode" value={mode} onChange={e=>setMode(e.target.value)}><option>rolling</option><option>expanding</option></select></div>
    <div className="row wrap mt12"><button className="button" disabled={working} onClick={()=>launch('sensitivity',grid())}>Run sensitivity</button><button className="button" disabled={working} onClick={()=>launch('walk_forward',{...grid(),mode,train_sessions:Number(train),validation_sessions:Number(validation),step_sessions:Number(validation)})}>Run walk-forward</button><button className="button" disabled={working} onClick={()=>launch('robustness',run?.definition??definition())}>Run robustness</button></div>
    <div className="row wrap mt12">{field('Monte Carlo seed',seed,setSeed)}{field('Simulations',simulations,setSimulations)}<select className="input" value={mcMethod} onChange={e=>setMcMethod(e.target.value)}><option>bootstrap</option><option>permutation</option></select><button className="button" disabled={working||!run} onClick={()=>launch('monte_carlo',{run_id:run?.run_id,seed:Number(seed),simulations:Number(simulations),method:mcMethod})}>Run Monte Carlo</button></div>
    <div className="row wrap mt12">{studies.map(s=><button className="button" key={s.artifact_id} onClick={()=>getJson<Study>(`quant/studies/${s.artifact_id}`).then(setStudy).catch(fail)}>{s.kind} · {shortId(s.artifact_id)}</button>)}</div>
  </div></section>}
  {study&&<StudyResult study={study}/>}
  {tab==='Edge evidence'&&<section className="panel"><div className="panel-head"><h2>Explicit Edge Library evidence</h2></div><div className="panel-body"><p>Attaches the open run and study to an existing matching hypothesis. Supported status requires recorded OOS, costs, assets, regimes, parameter stability and sample thresholds.</p>
    <div className="row wrap"><select className="input" aria-label="Edge hypothesis" value={edgeId} onChange={e=>setEdgeId(e.target.value)}><option value="">Select hypothesis</option>{edges.map(e=><option key={e.edge_id} value={e.edge_id}>{e.title}</option>)}</select><select className="input" aria-label="Edge status" value={edgeStatus} onChange={e=>setEdgeStatus(e.target.value)}>{['HYPOTHESIS','EARLY_EVIDENCE','SUPPORTED','WEAKENED','REJECTED'].map(v=><option key={v}>{v}</option>)}</select>{field('Evidence revision reason',reason,setReason)}
    <button className="button" disabled={!edgeId||!run||reason.length<12} onClick={()=>postJson('quant/edges/evidence',{edge_id:edgeId,run_ids:[run?.run_id],study_ids:study?[study.study_id]:[],status:edgeStatus,expected_revision:edges.find(e=>e.edge_id===edgeId)?.quant_evidence?.revision??0,reason}).then(async v=>{setMessage(fmt(v));await refresh();}).catch(fail)}>Attach explicit evidence</button></div>
  </div></section>}{message&&<p role="status">{message}</p>}
  </div>;
}
