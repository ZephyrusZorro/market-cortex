'use client';

import ExperimentalEdgeEvidence from './ExperimentalEdgeEvidence';
import { useCallback, useEffect, useState } from 'react';
import { ApiError, getJson, postJson, shortId, type Context } from '@/lib/api';

type Entry = {entry_id:string; revision:number; category:string; title:string; notes:string;
  tags:string[]; as_of:string; recorded_at:string; classification:string; author:string;
  structured_content:Record<string,string>; failure_category:string|null; links:Record<string,unknown>};
type Prediction = {prediction_id:string; title:string; symbol:string; detector_id:string;
  detector_version:string; registration:string; classification:string; status:string;
  horizon_sessions:number; due_session:string; created_at:string; evidence_strength:string;
  baseline_session:string; manifest_id:string; original_context_hash:string;
  original_context:Record<string,unknown>; prediction_type:string; comparator:string; threshold:string};
type Evaluation = {evaluation_id:string; status:string; metric_value:string|null; forward_return:string|null;
  evaluation_manifest_id:string; source_manifest_id:string; observed_sessions:number; expected_sessions:number;
  prediction_freshness:string; evaluation_quality:string; warnings:string[]; evaluated_at:string};
type Group = {detector_id:string; detector_version:string; registration:string; classification:string;
  prediction_type:string; horizon_sessions:number; N:number; usable_N:number; missing_inconclusive_N:number;
  excluded_quality_N:number; outcomes:Record<string,number>; forward_return:{N:number;mean:string|null;median:string|null};
  metric_distribution?:{N:number;mean:string|null;median:string|null};
  benchmark_return?:{N:number;mean:string|null};
  hypothetical_r_expectancy:{N:number;mean:string|null}; evidence_strength:Record<string,{N:number;confirmed_N:number}>;
  regime:Record<string,{N:number;confirmed_N:number}>; volatility_regime?:Record<string,{N:number;confirmed_N:number}>; warnings:string[]};
type Report = {as_of?:string;prediction_N:number; usable_N:number; candidate_ledger_N:number; report_id:string;
  minimum_descriptive_N:number; groups:Group[]; warnings:string[];
  candidate_ledger:{detector_id:string;detector_version:string;outcome:string;status:string;N:number}[]};
type Edge = {edge_id:string;title:string;hypothesis:string;status:string;usable_N:number;registration:string;detector_version:string};
const types = ['forward_return','relative_performance','thesis_survival','breakout_hold','invalidation','relative_strength_persistence','volatility_state'];
const categories = ['observation','research_note','thesis_note','decision','review','mistake','lesson','hypothesis','outcome_review'];
const failures = ['stale_data','insufficient_history','contradiction_ignored','invalidation_undefined','overconcentration','late_thesis','participation_missing','correlation_overlooked','other_owner_observation'];
const fmt = (value:unknown) => value==null ? 'unavailable' : String(value);
const err = (error:unknown) => error instanceof ApiError ? error.code : 'REQUEST_FAILED';

export function LearningLinksPanel({thesisId,runId}:{thesisId?:string;runId?:string}) {
  const [linked,setLinked] = useState<{predictions:Prediction[];journal:Entry[]}|null>(null);
  useEffect(() => { getJson<typeof linked>('learning/links',new URLSearchParams(thesisId ? {thesis_id:thesisId} : {research_run_id:runId??''}))
    .then(setLinked).catch(() => setLinked(null)); },[thesisId,runId]);
  return <section className="panel"><div className="panel-head"><h2>Prediction and outcome links</h2></div><div className="panel-body">
    <p className="muted small">Research status and evaluated outcomes are separate. No execution is inferred.</p>
    {linked?.predictions?.length ? linked.predictions.map(p => <div className="data-row" key={p.prediction_id}>
      <span>{p.title} · {p.registration}</span><strong>{p.status} · {p.horizon_sessions} sessions</strong></div>) :
      <p className="muted small">No linked prediction recorded.</p>}
    {linked?.journal?.map(e => <div className="data-row" key={e.entry_id}><span>{e.category} · {e.title}</span><span>revision {e.revision}</span></div>)}
    <a className="button mt12" href="/?view=learning">Open Journal & Learning</a>
  </div></section>;
}

export default function LearningPane({context}:{context:Context}) {
  const [tab,setTab] = useState('journal');
  const [entries,setEntries] = useState<Entry[]>([]);
  const [predictions,setPredictions] = useState<Prediction[]>([]);
  const [report,setReport] = useState<Report|null>(null);
  const [edges,setEdges] = useState<Edge[]>([]);
  const [queue,setQueue] = useState<{open_N:number;due_N:number;due:Prediction[];recent_outcomes:Prediction[]}|null>(null);
  const [detail,setDetail] = useState<{prediction:Prediction;evaluations:Evaluation[];revisions:{revision:number;status:string;reason:string}[]}|null>(null);
  const [error,setError] = useState<string|null>(null);
  const [busy,setBusy] = useState(false);
  const [search,setSearch] = useState('');
  const [filter,setFilter] = useState('');
  const [quality,setQuality] = useState(false);
  const [title,setTitle] = useState('');
  const [notes,setNotes] = useState('');
  const [category,setCategory] = useState('research_note');
  const [tags,setTags] = useState('');
  const [failure,setFailure] = useState('');
  const [edit,setEdit] = useState<Entry|null>(null);
  const [history,setHistory] = useState<{entry:Entry;reason:string}[]>([]);
  const [reason,setReason] = useState('');
  const [links,setLinks] = useState<Record<string,string>>({});
  const [structured,setStructured] = useState<Record<string,string>>({});
  const [author,setAuthor] = useState('owner');
  const [classification,setClassification] = useState('OWNER_RESEARCH');
  const [instrumentIds,setInstrumentIds] = useState<string[]>([]);
  const [symbol,setSymbol] = useState('BTCUSDT');
  const [benchmark,setBenchmark] = useState('ETHUSDT');
  const [predictionTitle,setPredictionTitle] = useState('');
  const [predictionType,setPredictionType] = useState('forward_return');
  const [horizon,setHorizon] = useState('5');
  const [registration,setRegistration] = useState('PRE_REGISTERED');
  const [baseline,setBaseline] = useState('');
  const [threshold,setThreshold] = useState('0');
  const [comparator,setComparator] = useState('gt');
  const [invalidation,setInvalidation] = useState('');
  const [predictionLinks,setPredictionLinks] = useState<Record<string,string>>({});
  const [evalCutoff,setEvalCutoff] = useState(context.as_of);
  const [edgeTitle,setEdgeTitle] = useState('');
  const [edgeHypothesis,setEdgeHypothesis] = useState('');
  const [edgeDetector,setEdgeDetector] = useState('momentum');
  const [edgeVersion,setEdgeVersion] = useState('1.0.0');
  const [edgeRegistration,setEdgeRegistration] = useState('RETROSPECTIVE_EVALUATION');
  const reload = useCallback(async () => {
    const values = await Promise.all([
      getJson<{items:Entry[]}>('learning/journal',new URLSearchParams({search})),
      getJson<{items:Prediction[]}>('learning/predictions'),getJson<Report>('learning/performance',new URLSearchParams({eligible_only:String(quality)})),
      getJson<typeof queue>('learning/review-queue'),getJson<{items:Edge[]}>('learning/edges')]);
    setEntries(values[0].items);setPredictions(values[1].items);setReport(values[2]);setQueue(values[3]);setEdges(values[4].items);
  },[search,quality]);
  useEffect(() => { reload().catch(e => setError(err(e))); },[reload]);
  const run = async (action:()=>Promise<void>) => { setBusy(true);setError(null);
    try { await action();await reload(); } catch(e) {setError(err(e));} finally {setBusy(false);} };
  const cleanLinks = (values:Record<string,string>) => Object.fromEntries(Object.entries(values).filter(([,v]) => v));
  const saveJournal = () => run(async () => {
    const draft = {category,title,notes,tags:tags.split(',').map(t => t.trim()).filter(Boolean),
      structured_content:structured,links:{...cleanLinks(links),instrument_ids:instrumentIds},manifest_id:context.source_manifest_id,
      as_of:new Date().toISOString(),author,failure_category:failure||null,
      classification:edit?.classification ?? classification};
    if(edit) await postJson(`learning/journal/${edit.entry_id}/revisions`,{expected_revision:edit.revision,reason,draft});
    else await postJson('learning/journal',draft);
    setEdit(null);setTitle('');setNotes('');setLinks({});setStructured({});setAuthor('owner');setHistory([]);setReason('');setClassification('OWNER_RESEARCH');setInstrumentIds([]);
  });
  const openJournal = async (e:Entry) => {
    setEdit(e);setTitle(e.title);setNotes(e.notes);setCategory(e.category);setTags(e.tags.join(','));
    setFailure(e.failure_category??'');setStructured(e.structured_content);setAuthor('owner');setClassification(e.classification);
    setInstrumentIds((e.links.instrument_ids as string[])??[]);
    setLinks(Object.fromEntries(Object.entries(e.links).filter(([,v]) => typeof v==='string')) as Record<string,string>);
    try { setHistory((await getJson<{items:typeof history}>(`learning/journal/${e.entry_id}/revisions`)).items); } catch(e) {setError(err(e));}
  };
  const createPrediction = () => run(async () => {
    const relative = predictionType.includes('relative');
    await postJson('learning/predictions',{title:predictionTitle,symbol,prediction_type:predictionType,
      benchmark_symbol:relative?benchmark:null,horizon_sessions:Number(horizon),comparator,threshold,
      invalidation_price:invalidation||null,baseline_session:baseline||null,registration,
      manifest_id:context.source_manifest_id,as_of:context.as_of,links:cleanLinks(predictionLinks)});
    setPredictionTitle('');
  });
  const openPrediction = async (id:string) => { try {setDetail(await getJson<typeof detail>(`learning/predictions/${id}`));} catch(e){setError(err(e));} };
  const evaluate = (id:string) => run(async () => {
    await postJson(`learning/predictions/${id}/evaluate`,{manifest_id:context.source_manifest_id,as_of:evalCutoff});
    await openPrediction(id);
  });
  const postmortem = (id:string) => run(async () => {
    const draft = await getJson<Entry>(`learning/predictions/${id}/postmortem`);
    setEdit(null);setTitle(draft.title);setNotes(draft.notes);setCategory(draft.category);
    setTags(draft.tags.join(','));setStructured(draft.structured_content);setAuthor('cortex_template');
    setClassification(draft.classification);setInstrumentIds((draft.links.instrument_ids as string[])??[]);
    setLinks(Object.fromEntries(Object.entries(draft.links).filter(([,v]) => typeof v==='string')) as Record<string,string>);
    setTab('journal');
  });
  const visiblePredictions = predictions.filter(p => !filter || (filter==='DUE' ?
    (queue?.due??[]).some(d => d.prediction_id===p.prediction_id) : p.status===filter));
  const linkInputs = (values:Record<string,string>,change:(v:Record<string,string>)=>void,prediction=false) =>
    <div className="row wrap mt12">{(prediction ? ['candidate_id','thesis_id','research_run_id','risk_snapshot_id'] :
      ['candidate_id','thesis_id','prediction_id','research_run_id','risk_snapshot_id']).map(key =>
      <label className="small muted" key={key}>{key.replaceAll('_',' ')} <input className="input" aria-label={`${prediction?'Prediction':'Journal'} ${key}`}
        placeholder="Optional UUID" value={values[key]??''} onChange={e=>change({...values,[key]:e.target.value})}/></label>)}</div>;
  return <div className="stack learning-page"><section className="panel"><div className="panel-head"><div><h2>Journal & Learning</h2>
    <span className="sub">Local private research · explicit expectations · immutable evidence</span></div>
    <button className="button" disabled={busy} onClick={()=>run(async()=>{})}>Refresh records</button></div>
    <div className="panel-body"><div className="row wrap">{['journal','predictions','review','performance','lessons'].map(t =>
      <button key={t} className={`button ${tab===t?'primary':''}`} onClick={()=>{setTab(t);setFilter('');}}>{t==='predictions'?'Prediction Ledger':t==='review'?'Review Queue':t==='lessons'?'Lessons & Edges':t==='performance'?'Performance': 'Journal'}</button>)}</div>
      <div className="callout mt12">Source manifest {shortId(context.source_manifest_id)} · cutoff {context.as_of}. Outcomes are research measurements. Retrospective records are separate from pre-registered predictions.</div>
      {error&&<div className="callout error mt12" role="alert">{error}</div>}</div></section>
    {tab==='journal'&&<div className="grid two"><section className="panel"><div className="panel-head"><h2>{edit?'Revise journal':'Create journal entry'}</h2></div><div className="panel-body">
      <label>Entry type <select className="select" aria-label="Journal entry type" value={category} onChange={e=>setCategory(e.target.value)}>{categories.map(c=><option key={c}>{c}</option>)}</select></label>
      <label>Title <input className="input" aria-label="Journal title" value={title} onChange={e=>setTitle(e.target.value)}/></label>
      <label>Notes <textarea className="input" aria-label="Journal notes" rows={6} value={notes} onChange={e=>setNotes(e.target.value)}/></label>
      <label>Tags <input className="input" aria-label="Journal tags" value={tags} onChange={e=>setTags(e.target.value)} placeholder="Comma separated"/></label>
      <label>Instruments <select multiple className="select" aria-label="Journal instruments" value={instrumentIds} onChange={e=>setInstrumentIds(Array.from(e.target.selectedOptions,o=>o.value))}>{context.members.filter(m=>m.instrument_id).map(m=><option value={m.instrument_id!} key={m.symbol}>{m.symbol}</option>)}</select></label>
      {['lesson','mistake','outcome_review'].includes(category)&&<label>Recorded failure category <select className="select" aria-label="Failure category" value={failure} onChange={e=>setFailure(e.target.value)}><option value="">None</option>{failures.map(f=><option key={f}>{f}</option>)}</select></label>}
      {linkInputs(links,setLinks)}
      {Object.entries(structured).map(([key,value])=><label className="small" key={key}>{key.replaceAll('_',' ')}<textarea className="input" value={value} onChange={e=>setStructured({...structured,[key]:e.target.value})}/></label>)}
      {edit&&<label>Revision reason <input className="input" aria-label="Journal revision reason" value={reason} onChange={e=>setReason(e.target.value)}/></label>}
      <p className="muted small">Author: {author}. Notes record their new writing time; prior revisions preserve the original belief.</p>
      <button className="button primary" disabled={busy||title.length<3||(!!edit&&reason.length<8)} onClick={saveJournal}>{edit?'Save revision':'Save journal entry'}</button>
      {history.length>0&&<div className="data-list mt12">{history.map(h=><div className="data-row" key={h.entry.revision}><span>Revision {h.entry.revision}: {h.entry.title}</span><span>{h.reason}</span></div>)}</div>}
    </div></section><section className="panel"><div className="panel-head"><h2>Research timeline</h2></div><div className="panel-body">
      <input className="input" aria-label="Search journal" placeholder="Search title or notes" value={search} onChange={e=>setSearch(e.target.value)}/>
      {entries.length?entries.map(e=><button className="button mt12" key={e.entry_id} onClick={()=>openJournal(e)}>
        {e.title} · {e.category} · revision {e.revision} · {e.tags.join(', ')} · {e.classification}</button>):<p>No journal entries recorded.</p>}
    </div></section></div>}
    {tab==='predictions'&&<><section className="panel"><div className="panel-head"><h2>Define a falsifiable expectation</h2></div><div className="panel-body">
      <label>Prediction title <input className="input" aria-label="Prediction title" value={predictionTitle} onChange={e=>setPredictionTitle(e.target.value)}/></label>
      <div className="row wrap"><label>Metric <select className="select" aria-label="Prediction metric" value={predictionType} onChange={e=>setPredictionType(e.target.value)}>{types.map(t=><option key={t}>{t}</option>)}</select></label>
      <label>Instrument <select className="select" aria-label="Prediction instrument" value={symbol} onChange={e=>setSymbol(e.target.value)}>{context.members.map(m=><option key={m.symbol}>{m.symbol}</option>)}</select></label>
      {predictionType.includes('relative')&&<label>Benchmark <select className="select" aria-label="Prediction benchmark" value={benchmark} onChange={e=>setBenchmark(e.target.value)}>{context.members.filter(m=>m.symbol!==symbol).map(m=><option key={m.symbol}>{m.symbol}</option>)}</select></label>}
      <label>Sessions <input className="input" aria-label="Prediction horizon sessions" type="number" min="2" max="20" value={horizon} onChange={e=>setHorizon(e.target.value)}/></label>
      <label>Comparator <select className="select" aria-label="Prediction comparator" value={comparator} onChange={e=>setComparator(e.target.value)}>{['gt','gte','lt','lte'].map(c=><option key={c}>{c}</option>)}</select></label>
      <label>Threshold <input className="input" aria-label="Prediction threshold" type="number" step="any" value={threshold} onChange={e=>setThreshold(e.target.value)}/></label>
      <label>Registration <select className="select" aria-label="Prediction registration" value={registration} onChange={e=>setRegistration(e.target.value)}><option>PRE_REGISTERED</option><option>RETROSPECTIVE_EVALUATION</option></select></label>
      <label>Baseline session <input className="input" aria-label="Prediction baseline session" type="date" value={baseline} onChange={e=>setBaseline(e.target.value)}/></label>
      <label>Optional R invalidation <input className="input" aria-label="Prediction invalidation price" type="number" step="any" value={invalidation} onChange={e=>setInvalidation(e.target.value)}/></label></div>
      <div className="callout mt12">Returns use fractional thresholds (0.05 = 5%). Survival/invalidation use close-price levels. Volatility uses annualized 20-session volatility. Pre-registration is refused if the first outcome session already completed.</div>
      {linkInputs(predictionLinks,setPredictionLinks,true)}<button className="button primary mt12" disabled={busy||predictionTitle.length<5} onClick={createPrediction}>Record expectation</button>
    </div></section><section className="panel"><div className="panel-head"><h2>Prediction Ledger</h2><select className="select" aria-label="Prediction status filter" value={filter} onChange={e=>setFilter(e.target.value)}><option value="">All</option>{['OPEN','DUE','PENDING_EVALUATION','CONFIRMED','INVALIDATED','INCONCLUSIVE','UNMEASURABLE','CANCELLED'].map(s=><option key={s}>{s}</option>)}</select></div>
      <div className="table-wrap"><table><thead><tr>{['Expectation','Instrument','Detector/version','Registration','Sessions / due','Strength','Status'].map(t=><th key={t}>{t}</th>)}</tr></thead><tbody>{visiblePredictions.map(p=><tr key={p.prediction_id}>
      <td><button className="button" onClick={()=>openPrediction(p.prediction_id)}>{p.title}</button></td><td>{p.symbol}</td><td>{p.detector_id} / {p.detector_version}</td><td>{p.registration}<small>{p.classification}</small></td><td>{p.horizon_sessions} / {p.due_session}</td><td>{p.evidence_strength}</td><td>{p.status}</td></tr>)}</tbody></table></div></section>
      {detail&&<section className="panel"><div className="panel-head"><h2>{detail.prediction.title}</h2><span className="badge">{detail.prediction.status}</span></div><div className="panel-body">
        <p>Frozen context {shortId(detail.prediction.original_context_hash)} · source {shortId(detail.prediction.manifest_id)} · baseline {detail.prediction.baseline_session} · {detail.prediction.registration}</p>
        <details><summary>Original evidence and linked versions</summary><pre>{JSON.stringify(detail.prediction.original_context,null,2)}</pre></details>
        <label>Evaluation cutoff <input className="input" aria-label="Evaluation cutoff" value={evalCutoff} onChange={e=>setEvalCutoff(e.target.value)}/></label><button className="button" onClick={()=>setEvalCutoff(new Date().toISOString())}>Use now as evaluation cutoff</button>
        <button className="button primary" disabled={busy||detail.prediction.status==='CANCELLED'} onClick={()=>evaluate(detail.prediction.prediction_id)}>Evaluate with active manifest</button>
        {detail.evaluations.map(e=><div className="callout mt12" key={e.evaluation_id}><strong>{e.status}</strong> · metric {fmt(e.metric_value)} · forward return {fmt(e.forward_return)} · sessions {e.observed_sessions}/{e.expected_sessions}<p>Evaluation manifest {shortId(e.evaluation_manifest_id)} · quality {e.evaluation_quality} · original freshness {e.prediction_freshness}</p><p>{e.warnings.join(' · ')}</p></div>)}
        {detail.evaluations.some(e=>['CONFIRMED','INVALIDATED','INCONCLUSIVE','UNMEASURABLE'].includes(e.status))&&<button className="button mt12" disabled={busy} onClick={()=>postmortem(detail.prediction.prediction_id)}>Draft post-mortem</button>}
        <div className="data-list mt12">{detail.revisions.map(r=><div className="data-row" key={r.revision}><span>Revision {r.revision} · {r.status}</span><span>{r.reason}</span></div>)}</div>
      </div></section>}</>}
    {tab==='review'&&<section className="panel"><div className="panel-head"><h2>Review Queue</h2></div><div className="panel-body"><p>Open/unresolved N={queue?.open_N??0} · due N={queue?.due_N??0}</p>
      <label>Evaluation cutoff <input className="input" aria-label="Batch evaluation cutoff" value={evalCutoff} onChange={e=>setEvalCutoff(e.target.value)}/></label>
      <button className="button" disabled={busy} onClick={()=>run(async()=>{await postJson('learning/evaluate-due',{manifest_id:context.source_manifest_id,as_of:evalCutoff});})}>Evaluate due with active manifest</button>
      {queue?.due.map(p=><div className="data-row" key={p.prediction_id}><button className="button" onClick={()=>{setTab('predictions');openPrediction(p.prediction_id);}}>{p.title}</button><span>{p.status} · {p.due_session} · {p.registration}</span></div>)}
      <h3 className="mt18">Recent outcomes</h3>{queue?.recent_outcomes.map(p=><div className="data-row" key={p.prediction_id}><span>{p.title}</span><span>{p.status}</span></div>)}
    </div></section>}
    {tab==='performance'&&report&&<><section className="panel"><div className="panel-head"><h2>Descriptive performance</h2><label><input type="checkbox" checked={quality} onChange={e=>setQuality(e.target.checked)}/> Eligible quality/freshness only</label></div><div className="panel-body">
      <p className="muted small">Ledger report recorded through {report.as_of??'current request cutoff'} · {shortId(report.report_id)}. Source market context is shown above.</p>
      <p>Prediction N={report.prediction_N} · usable outcome N={report.usable_N} · candidate/rejection ledger N={report.candidate_ledger_N} · sample threshold {report.minimum_descriptive_N}</p><p className="callout">{report.warnings.join(' · ')}</p>
      {report.groups.map((g,i)=><section className="mt18" key={i}><h3>{g.detector_id} v{g.detector_version} · {g.registration}</h3><p>{g.prediction_type} · {g.horizon_sessions} sessions · {g.classification}</p><div className="data-list">
        <div className="data-row"><span>N / usable / missing / excluded quality</span><strong>{g.N} / {g.usable_N} / {g.missing_inconclusive_N} / {g.excluded_quality_N}</strong></div>
        <div className="data-row"><span>Mean / median forward return (fraction)</span><strong>{fmt(g.forward_return.mean)} / {fmt(g.forward_return.median)} · N={g.forward_return.N}</strong></div>
        {g.metric_distribution&&<div className="data-row"><span>Mean / median defined metric</span><strong>{fmt(g.metric_distribution.mean)} / {fmt(g.metric_distribution.median)} · N={g.metric_distribution.N}</strong></div>}
        {g.benchmark_return&&<div className="data-row"><span>Mean benchmark return (fraction)</span><strong>{fmt(g.benchmark_return.mean)} · N={g.benchmark_return.N}</strong></div>}
        <div className="data-row"><span>Hypothetical forward R expectancy</span><strong>{fmt(g.hypothetical_r_expectancy.mean)} · N={g.hypothetical_r_expectancy.N}</strong></div>
        <div className="data-row"><span>Outcome counts</span><span>{JSON.stringify(g.outcomes)}</span></div>
        {Object.entries(g.evidence_strength).map(([k,v])=><div className="data-row" key={k}><span>{k} evidence</span><span>N={v.N} · confirmed N={v.confirmed_N}</span></div>)}
        {Object.entries(g.regime).map(([k,v])=><div className="data-row" key={k}><span>{k} regime</span><span>N={v.N} · confirmed N={v.confirmed_N}</span></div>)}
        {Object.entries(g.volatility_regime??{}).map(([k,v])=><div className="data-row" key={k}><span>{k} volatility regime</span><span>N={v.N} · confirmed N={v.confirmed_N}</span></div>)}
      </div><p className="callout warn mt12">{g.warnings.join(' · ')}</p></section>)}
      {!report.groups.length&&<p>No evaluated prediction cohort yet. No accuracy or edge claim is available.</p>}
    </div></section><section className="panel"><div className="panel-head"><h2>Candidate and rejection coverage</h2></div><div className="table-wrap"><table><thead><tr><th>Detector/version</th><th>Outcome</th><th>Status</th><th>N</th></tr></thead><tbody>{report.candidate_ledger.map((r,i)=><tr key={i}><td>{r.detector_id}/{r.detector_version}</td><td>{r.outcome}</td><td>{r.status}</td><td>{r.N}</td></tr>)}</tbody></table></div></section></>}
    {tab==='lessons'&&<><section className="panel"><div className="panel-head"><h2>Failure and lesson memory</h2></div><div className="panel-body"><p>Only explicit journal categories and owner observations are counted.</p>{entries.filter(e=>e.failure_category).map(e=><div className="data-row" key={e.entry_id}><span>{e.title} · {e.failure_category}</span><span>revision {e.revision} · {e.author}</span></div>)}<button className="button mt12" onClick={()=>{setTab('journal');setCategory('lesson');}}>Record a lesson</button></div></section>
      <section className="panel"><div className="panel-head"><h2>Edge Library hypotheses</h2></div><div className="panel-body"><p className="callout">Hypotheses preserve supporting statistics at creation. No edge is proven and no rule is changed automatically.</p>
      <label>Title <input className="input" aria-label="Edge title" value={edgeTitle} onChange={e=>setEdgeTitle(e.target.value)}/></label><label>Hypothesis <textarea className="input" aria-label="Edge hypothesis" value={edgeHypothesis} onChange={e=>setEdgeHypothesis(e.target.value)}/></label>
      <div className="row wrap"><label>Detector <input className="input" aria-label="Edge detector" value={edgeDetector} onChange={e=>setEdgeDetector(e.target.value)}/></label><label>Version <input className="input" aria-label="Edge detector version" value={edgeVersion} onChange={e=>setEdgeVersion(e.target.value)}/></label><label>Registration <select className="select" aria-label="Edge registration" value={edgeRegistration} onChange={e=>setEdgeRegistration(e.target.value)}><option>RETROSPECTIVE_EVALUATION</option><option>PRE_REGISTERED</option></select></label></div>
      <button className="button primary mt12" disabled={busy||edgeTitle.length<5||edgeHypothesis.length<10} onClick={()=>run(async()=>{await postJson('learning/edges',{title:edgeTitle,hypothesis:edgeHypothesis,detector_id:edgeDetector,detector_version:edgeVersion,registration:edgeRegistration});setEdgeTitle('');setEdgeHypothesis('');})}>Save edge hypothesis</button>
      <ExperimentalEdgeEvidence/>{edges.map(e=><div className="data-row mt12" key={e.edge_id}><span>{e.title} · {e.registration} · v{e.detector_version}</span><strong>{e.status} · usable N={e.usable_N}</strong></div>)}</div></section></>}
  </div>;
}
