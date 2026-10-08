'use client';
import {useCallback,useEffect,useState} from 'react';
import {ApiError,getJson,postJson,shortId,type Context} from '@/lib/api';

type Row=Record<string,unknown>;
type Definition={hypothesis_id:string;dataset:{manifest_id:string;source_as_of:string;start:string;end:string};validation:Row;model:Row;configuration:Row};
type Experiment={experiment_id:string;content_hash:string;hypothesis_hash:string;recorded_at:string;status:string;definition:Definition;event:Row};
type Recorded={study_id:string;definition:Definition;result:{experiment_id:string;manifest:Row;dataset_ref:{artifact_id:string;content_hash:string};model_refs:{artifact_id:string}[];result_hash:string;result:{status:string;conclusion:string;warnings:string[];reports:Record<string,unknown>}}};
type Job={job_id:string;status:string;error_code:string|null};
const tabs=['Explorer','Hypotheses','Dataset','Models','Features','Regimes','Analogues','Validation','Robustness','Calibration','Governance'] as const;
const fmt=(v:unknown):string=>v==null?'unavailable':typeof v==='number'?v.toPrecision(5):typeof v==='object'?JSON.stringify(v):String(v);
function Table({rows}:{rows:Row[]}){
  if(!rows.length)return <p className="muted">Insufficient evidence or no recorded observations.</p>;
  const columns=Array.from(new Set(rows.flatMap(r=>Object.keys(r))));
  return <div className="experiment-table"><table className="table"><thead><tr>{columns.map(c=><th key={c}>{c.replaceAll('_',' ')}</th>)}</tr></thead><tbody>{rows.map((r,i)=><tr key={i}>{columns.map(c=><td key={c}><span title={fmt(r[c])}>{fmt(r[c])}</span></td>)}</tr>)}</tbody></table></div>;
}
function Json({value,label='Complete recorded evidence'}:{value:unknown;label?:string}){
  return <details><summary>{label}</summary><pre className="experiment-json">{JSON.stringify(value,null,2)}</pre></details>;
}
function FoldChart({rows}:{rows:Row[]}) {
  const values=rows.flatMap(r=>[Number((r.metrics as Row)?.rmse),Number((r.mean_baseline as Row)?.rmse)]).filter(Number.isFinite);
  const max=Math.max(.0001,...values);
  if(!rows.length)return null;
  return <figure className="experiment-chart"><svg viewBox={`0 0 700 ${rows.length*42+35}`} role="img" aria-label="Recorded temporal test RMSE: model and mean baseline">
    {rows.map((r,i)=><g key={i}><text x="0" y={i*42+18} fill="#98a4a0" fontSize="11">Fold {String(r.fold)}</text>
      <rect x="75" y={i*42+6} width={550*Number((r.metrics as Row).rmse)/max} height="10" fill="#75b2a5"/>
      <rect x="75" y={i*42+20} width={550*Number((r.mean_baseline as Row).rmse)/max} height="10" fill="#77837f"/>
      <text x="630" y={i*42+20} fill="#bdc8c4" fontSize="10">N {String(r.test_N)}</text></g>)}
    <text x="75" y={rows.length*42+18} fill="#98a4a0" fontSize="11">RMSE · teal model · grey training-mean baseline · lower error is better</text>
  </svg></figure>;
}
export default function ExperimentalPane({context,environment}:{context:Context;environment?:string}){
  const [tab,setTab]=useState<typeof tabs[number]>('Explorer'),[items,setItems]=useState<Experiment[]>([]),[chosen,setChosen]=useState('');
  const [registry,setRegistry]=useState<{models:{registry_id:string}[];features:string[]}|null>(null),[hypotheses,setHypotheses]=useState<Row[]>([]);
  const [recorded,setRecorded]=useState<Recorded|null>(null),[dataset,setDataset]=useState<Row|null>(null),[extra,setExtra]=useState<unknown>(null);
  const [ledger,setLedger]=useState<Row[]>([]),[governance,setGovernance]=useState<Row[]>([]),[links,setLinks]=useState<Row[]>([]);
  const [loading,setLoading]=useState(true),[busy,setBusy]=useState(false),[error,setError]=useState(''),[job,setJob]=useState<Job|null>(null);
  const [question,setQuestion]=useState('Does causal momentum improve forward-return forecasts over the training mean?');
  const [rationale,setRationale]=useState('Trend persistence may contain a weak association, subject to costs and regime changes.');
  const [falsification,setFalsification]=useState('Reject if temporal error improvement is below 2% or unstable across folds.');
  const [feature,setFeature]=useState(['momentum_5','momentum_20','trend_persistence','volatility_20','relative_strength','volume_ratio']);
  const [model,setModel]=useState('ridge'),[target,setTarget]=useState('return'),[horizon,setHorizon]=useState('5');
  const [start,setStart]=useState(context.history_start??''),[end,setEnd]=useState(context.evaluation_date??'');
  const [reason,setReason]=useState('Review temporal evidence, dependence and repeated holdout exposure.'),[decision,setDecision]=useState('CANDIDATE_FOR_REVIEW');
  const [comparison,setComparison]=useState<string[]>([]),[reference,setReference]=useState(context.evaluation_date??''),[symbol,setSymbol]=useState('BTCUSDT');
  const [edge,setEdge]=useState(''),[stance,setStance]=useState('COUNTER');
  const [proposalAlpha,setProposalAlpha]=useState('1');
  const load=useCallback(async()=>{
    const [e,h,r,l,el]=await Promise.all([getJson<{items:Experiment[]}>('experimental/experiments'),getJson<{items:Row[]}>('experimental/hypotheses'),
      getJson<{models:{registry_id:string}[];features:string[]}>('experimental/registry'),getJson<{items:Row[]}>('experimental/ledger'),getJson<{items:Row[]}>('experimental/edges/evidence')]);
    setItems(e.items);setHypotheses(h.items);setRegistry(r);setLedger(l.items);setLinks(el.items);
  },[]);
  const inspect=useCallback(async(id:string)=>{
    setRecorded(null);setDataset(null);setExtra(null);
    const g=await getJson<{items:Row[]}>(`experimental/experiments/${id}/governance`);setGovernance(g.items);
    try{setRecorded(await getJson<Recorded>(`experimental/experiments/${id}/result`));}
    catch(e){if(!(e instanceof ApiError&&e.status===404))throw e;}
  },[]);
  useEffect(()=>{let live=true;load().catch(e=>{if(live)setError(e instanceof Error?e.message:'Backend unavailable');}).finally(()=>{if(live)setLoading(false);});return()=>{live=false;};},[load]);
  useEffect(()=>{if(chosen)inspect(chosen).catch(e=>setError(e.message));},[chosen,inspect]);
  const action=async(fn:()=>Promise<unknown>)=>{setBusy(true);setError('');try{await fn();}catch(e){setError(e instanceof Error?e.message:'Research request failed');}finally{setBusy(false);}};
  useEffect(()=>{
    if(!job||!['queued','running'].includes(job.status))return;
    const timer=setInterval(()=>{getJson<Job>(`experimental/jobs/${job.job_id}`).then(async j=>{setJob(j);if(j.status==='completed'){await load();await inspect(chosen);}}).catch(e=>setError(e.message));},2000);
    return()=>clearInterval(timer);
  },[job,chosen,load,inspect]);
  const selected=items.find(i=>i.experiment_id===chosen),r=recorded?.result.result.reports;
  const reportRows=(k:string)=>Array.isArray(r?.[k])?r[k] as Row[]:[];
  const artifact=async(ref:{artifact_id:string})=>{const a=await getJson<{result:unknown}>(`experimental/artifacts/${ref.artifact_id}`);setExtra(a.result);};
  const create=async()=>{
    const h=await postJson<{hypothesis_id:string}>('experimental/hypotheses',{question,rationale,relationship:'Registered causal features may reduce temporal forecasting error.',falsification,
      features:feature,target,symbols:context.members.map(m=>m.symbol),registration:'EXPLORATORY',minimum_oos_rows:100,minimum_improvement:.02});
    const e=await postJson<Experiment>('experimental/experiments',{hypothesis_id:h.hypothesis_id,dataset:{manifest_id:context.source_manifest_id,source_as_of:context.as_of,start,end,horizon_sessions:Number(horizon),replay_policy:'HISTORICAL_RECONSTRUCTION'},model:{registry_id:model}});
    await load();setChosen(e.experiment_id);setTab('Explorer');
  };
  return <div className="experimental-lab">
    <header className="panel experiment-hero"><div><span className="eyebrow">QUANT LAB / EXPERIMENTAL RESEARCH</span><h1>Advanced Research Laboratory</h1>
      <p className="muted">Frozen hypotheses. Purged temporal validation. Evidence before confidence.</p></div><span className="badge">LOCAL ONLY · RESEARCH</span></header>
    <div className="experiment-warning">No supported edge established. Prior momentum temporal OOS <strong>−7.82% · N=82</strong> remains negative evidence. Historical windows are examined; genuine unseen validation is unavailable.</div>
    {error&&<div className="error-banner" role="alert">{error}</div>}
    {loading?<p role="status">Loading experimental registry…</p>:<>
    <div className="row wrap mb12" role="tablist" aria-label="Advanced laboratory sections">{tabs.map(t=><button key={t} className={`button ${tab===t?'primary':''}`} role="tab" aria-selected={tab===t} onClick={()=>{setTab(t);setExtra(null);}}>{t}</button>)}</div>
    <div className="row wrap mb12"><label>Recorded experiment<select className="input" aria-label="Recorded experiment" value={chosen} onChange={e=>setChosen(e.target.value)}><option value="">Select an experiment</option>{items.map(i=><option key={i.experiment_id} value={i.experiment_id}>{i.definition.model.registry_id as string} · {i.status} · {shortId(i.experiment_id)}</option>)}</select></label>
      <button className="button" disabled={busy} onClick={()=>action(load)}>Refresh registry</button>
      {selected&&<><span className="badge">{selected.status}</span><button className="button primary" disabled={busy||['REJECTED','ARCHIVED'].includes(selected.status)||Boolean(job&&['queued','running'].includes(job.status))} onClick={()=>action(async()=>setJob(await postJson<Job>(`experimental/experiments/${chosen}/jobs`,{})))}>Run registered experiment</button>
      <button className="button" disabled={busy||!recorded} onClick={()=>action(async()=>setExtra(await postJson(`experimental/experiments/${chosen}/replay`,{})))}>Replay evidence</button></>}
      {job&&<><span role="status">Job {job.status}{job.error_code?` · ${job.error_code}`:''}</span>{['queued','running'].includes(job.status)&&<button className="button" onClick={()=>action(async()=>setJob(await postJson<Job>(`experimental/jobs/${job.job_id}/cancel`,{})))}>Cancel research job</button>}</>}
    </div>
    {tab==='Hypotheses'&&<section className="panel"><div className="panel-head"><h2>Freeze a research question</h2><span>Exploratory registration</span></div><div className="panel-body">
      <div className="experiment-form"><label>Research question<textarea className="input" value={question} onChange={e=>setQuestion(e.target.value)}/></label><label>Market rationale<textarea className="input" value={rationale} onChange={e=>setRationale(e.target.value)}/></label><label>Falsification criteria<textarea className="input" value={falsification} onChange={e=>setFalsification(e.target.value)}/></label></div>
      <div className="row wrap mt12"><label>Model<select className="input" value={model} onChange={e=>setModel(e.target.value)}>{registry?.models.map(m=><option key={m.registry_id}>{m.registry_id}</option>)}</select></label>
      <label>Target<select className="input" value={target} onChange={e=>setTarget(e.target.value)}>{['return','excess_return','volatility','mae','mfe','direction'].map(t=><option key={t}>{t}</option>)}</select></label>
      <label>Horizon sessions<input className="input" type="number" min={1} max={30} value={horizon} onChange={e=>setHorizon(e.target.value)}/></label>
      <label>History from<input className="input" type="date" value={start} onChange={e=>setStart(e.target.value)}/></label><label>History through<input className="input" type="date" value={end} onChange={e=>setEnd(e.target.value)}/></label></div>
      <div className="row wrap mt12">{registry?.features.map(f=><label key={f}><input type="checkbox" checked={feature.includes(f)} onChange={e=>setFeature(e.target.checked?[...feature,f]:feature.filter(x=>x!==f))}/>{f.replaceAll('_',' ')}</label>)}</div>
      <p className="muted small">240 training sessions, 90 test sessions, 4 folds, 5-session embargo. Train-only feature ranking and regularization. Sparse context yields insufficient evidence. ₹0 local CPU.</p>
      <button className="button primary" disabled={busy||!feature.length||question.length<10||rationale.length<10||falsification.length<10||!start||!end} onClick={()=>action(create)}>Freeze hypothesis and register experiment</button>
      <Json value={hypotheses} label="Registered hypotheses and falsification rules"/></div></section>}
    {tab==='Explorer'&&<section className="panel"><div className="panel-head"><h2>Experiment explorer</h2><span>{items.length} recorded definitions</span></div><div className="panel-body">
      {!items.length?<p>No experiments registered. Open Hypotheses to freeze a question.</p>:<Table rows={items.map(i=>({id:shortId(i.experiment_id),model:i.definition.model.registry_id,status:i.status,start:i.definition.dataset.start,end:i.definition.dataset.end,registered:i.recorded_at}))}/>}</div></section>}
    {recorded&&<div className="experiment-metrics">{['N','rmse','mae','baseline_skill'].map(k=><div className="panel" key={k}><span className="muted small">{k.replaceAll('_',' ')}</span><strong>{fmt((r?.metrics as Row)?.[k])}</strong></div>)}<div className="panel"><span className="muted small">Finding</span><strong>{recorded.result.result.conclusion.replaceAll('_',' ')}</strong></div></div>}
    {selected&&<p className="muted small experiment-hash">Definition {selected.content_hash} · manifest {selected.definition.dataset.manifest_id} · {selected.definition.dataset.source_as_of}</p>}
    {tab==='Dataset'&&recorded&&<section className="panel"><div className="panel-head"><h2>Dataset provenance and missingness</h2></div><div className="panel-body"><button className="button" disabled={busy} onClick={()=>action(async()=>{const d=await getJson<{result:Row}>(`experimental/experiments/${chosen}/dataset`);setDataset(d.result);})}>Inspect derived dataset</button>
      {dataset&&<><Table rows={[Object.fromEntries(Object.entries(dataset).filter(([k])=>k!=='rows'))]}/><Table rows={(dataset.rows as Row[]).slice(0,10)}/><Json value={dataset} label="All derived rows and separate labels"/></>}</div></section>}
    {tab==='Models'&&<section className="panel"><div className="panel-head"><h2>Model laboratory</h2><span>Safe JSON · no uploaded models</span></div><div className="panel-body"><FoldChart rows={reportRows('folds')}/><Table rows={reportRows('folds').map(f=>({fold:f.fold,training:f.training_window,test:f.test_window,train_N:f.train_N,test_N:f.test_N,model:selected?.definition.model.registry_id,metrics:f.metrics,baseline:f.mean_baseline,calibration:f.probability_status}))}/>
      <div className="row wrap mt12">{recorded?.result.model_refs.map((ref,i)=><button className="button" key={ref.artifact_id} onClick={()=>action(()=>artifact(ref))}>Inspect model fold {i+1}</button>)}</div>
      <h3>Compare frozen experiments</h3><div className="row wrap">{items.map(i=><label key={i.experiment_id}><input type="checkbox" checked={comparison.includes(i.experiment_id)} onChange={e=>setComparison(e.target.checked?[...comparison,i.experiment_id]:comparison.filter(x=>x!==i.experiment_id))}/>{shortId(i.experiment_id)} · {i.definition.model.registry_id as string}</label>)}</div>
      <button className="button mt12" disabled={busy||comparison.length<2||comparison.length>8} onClick={()=>action(async()=>artifact(await postJson<{artifact_id:string}>('experimental/compare',{experiment_ids:comparison}))) }>Compare recorded evidence</button></div></section>}
    {tab==='Features'&&<section className="panel"><div className="panel-head"><h2>Feature research · association is not causation</h2></div><div className="panel-body"><h3>Importance by fold</h3><Table rows={reportRows('feature_importance')}/><h3>Redundancy</h3><Table rows={reportRows('feature_redundancy')}/><h3>Factor sensitivity to outliers</h3><Table rows={reportRows('factor_research')}/><h3>Fixed feature ablation</h3><Table rows={reportRows('feature_ablation')}/></div></section>}
    {tab==='Regimes'&&<section className="panel"><div className="panel-head"><h2>Regime and factor stability</h2></div><div className="panel-body"><p className="muted">Experimental fixed price proxy: volatility ≥3.5%, momentum ±2%. Canonical Market State remains separate.</p><Table rows={reportRows('regime_research')}/><h3>Assets</h3><Table rows={reportRows('asset_research')}/><h3>Periods</h3><Table rows={reportRows('period_research')}/><Json value={r?.regime_transitions} label="Descriptive transitions and censored durations"/></div></section>}
    {tab==='Analogues'&&<section className="panel"><div className="panel-head"><h2>Historical analogues</h2></div><div className="panel-body"><p className="muted">Past feature distance selects matches; subsequent historical outcomes are displayed after selection. No forecast probability.</p><div className="row wrap"><label>Reference date<input className="input" type="date" value={reference} onChange={e=>setReference(e.target.value)}/></label><label>Reference symbol<select className="input" value={symbol} onChange={e=>setSymbol(e.target.value)}>{context.members.map(m=><option key={m.symbol}>{m.symbol}</option>)}</select></label><button className="button" disabled={busy||!recorded||!reference} onClick={()=>action(async()=>artifact(await postJson<{artifact_id:string}>('experimental/analogues',{experiment_id:chosen,reference_date:reference,symbol,limit:5})))}>Find historical analogues</button></div></div></section>}
    {tab==='Validation'&&<section className="panel"><div className="panel-head"><h2>Temporal validation</h2><span>Targets purged · embargo enforced</span></div><div className="panel-body"><Table rows={reportRows('folds').map(({model,...f})=>f)}/><h3>Every inner parameter trial</h3><Table rows={reportRows('search')}/><Json value={recorded?.result.manifest} label="Frozen experiment manifest"/></div></section>}
    {tab==='Robustness'&&<section className="panel"><div className="panel-head"><h2>Robustness, drift and uncertainty</h2></div><div className="panel-body"><Table rows={reportRows('drift')}/><Json value={r?.robustness} label="Coverage, cost proxy and robustness"/><Json value={r?.uncertainty} label="Moving block bootstrap; conditional uncertainty"/><Json value={r?.meta_labeling} label="Meta-labeling prerequisites"/><p className="muted">Canonical Quant Lab provides bar-based cost, timing, delay and slippage stress; supplied portfolio shocks remain in Portfolio & Risk.</p></div></section>}
    {tab==='Calibration'&&<section className="panel"><div className="panel-head"><h2>Probability diagnostics</h2></div><div className="panel-body"><p>{fmt((r?.calibration as Row)?.status??'PROBABILITY_UNAVAILABLE')}</p><Table rows={((r?.calibration as Row)?.bins??[]) as Row[]}/><Json value={r?.calibration}/></div></section>}
    {tab==='Governance'&&<section className="panel"><div className="panel-head"><h2>Research governance and search history</h2><span>Promotion is research only</span></div><div className="panel-body"><Table rows={ledger}/><Json value={r?.multiple_testing} label="Multiple testing assumptions and unavailable methods"/>
      <div className="row wrap mt12"><label>Decision<select className="input" value={decision} onChange={e=>setDecision(e.target.value)}>{['EXPERIMENTAL','CANDIDATE_FOR_REVIEW','REJECTED','HUMAN_APPROVED_RESEARCH_BASELINE','ARCHIVED'].map(d=><option key={d}>{d}</option>)}</select></label><label>Review reason<input className="input" value={reason} onChange={e=>setReason(e.target.value)}/></label>
      <button className="button" disabled={busy||!chosen||reason.length<10||(decision==='HUMAN_APPROVED_RESEARCH_BASELINE'&&environment!=='OWNER_MAIN')} onClick={()=>action(async()=>{await postJson('experimental/governance',{experiment_id:chosen,decision,reason,expected_revision:governance.length,owner_confirmed:decision==='HUMAN_APPROVED_RESEARCH_BASELINE'});await load();await inspect(chosen);})}>Record human review</button>
      <label>Proposal regularization<input className="input" type="number" min={0.0001} max={10000} value={proposalAlpha} onChange={e=>setProposalAlpha(e.target.value)}/></label>
      <button className="button" disabled={busy||!recorded||reason.length<10||Number(proposalAlpha)<0.0001||Number(proposalAlpha)>10000} onClick={()=>action(async()=>{setExtra(await postJson('experimental/proposals',{parent_experiment_id:chosen,reason,definition:{...selected!.definition,model:{registry_id:selected!.definition.model.registry_id==='ensemble'?'ridge':'ensemble',alphas:[Number(proposalAlpha)]}}}));await load();})}>Propose registered model revision</button>
      <button className="button" disabled={busy||!recorded} onClick={()=>action(async()=>artifact(await postJson<{artifact_id:string}>('experimental/missions',{experiment_id:chosen,authorize_run:false,max_tool_calls:8})))}>CORTEX challenge and save dossier</button></div>
      <Table rows={governance}/><h3>Edge Library evidence</h3><div className="row wrap"><label>Existing Edge ID<input className="input" value={edge} onChange={e=>setEdge(e.target.value)}/></label><select aria-label="Evidence stance" className="input" value={stance} onChange={e=>setStance(e.target.value)}>{['COUNTER','INCONCLUSIVE','SUPPORTING'].map(s=><option key={s}>{s}</option>)}</select><button className="button" disabled={busy||!recorded||!/^[0-9a-f-]{36}$/.test(edge)||reason.length<10} onClick={()=>action(async()=>{await postJson('experimental/edges/evidence',{experiment_id:chosen,edge_id:edge,stance,reason});await load();})}>Attach research evidence</button></div><Table rows={links}/></div></section>}
    {chosen&&!recorded&&tab!=='Explorer'&&tab!=='Hypotheses'&&<p className="muted">This definition has no completed research result. Run the registered experiment to inspect evidence.</p>}
    {extra!=null&&<section className="panel"><div className="panel-head"><h2>Recorded research detail</h2></div><div className="panel-body">{Array.isArray((extra as Row).matches)&&<Table rows={(extra as Row).matches as Row[]}/>}<Json value={extra}/></div></section>}
    {recorded&&<details className="experiment-limitations"><summary>Scientific limitations and full result</summary>{recorded.result.result.warnings.map(w=><p key={w}>{w}</p>)}<Json value={recorded}/></details>}
    </>}
  </div>;
}
