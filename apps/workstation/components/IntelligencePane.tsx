'use client';
import {useEffect,useState} from 'react';
import {ApiError,getJson,number,shortId,type Context} from '@/lib/api';

type Domain = 'macro'|'events'|'news'|'derivatives'|'fundamentals'|'options'|'onchain';
type Fact = {domain:Domain;kind:string;classification:string;classification_scope:string;logical_key:string;revision_number:number;
  value?:string;title?:string;scheduled_at?:string;category?:string;metric?:string;period_start?:string;period_end?:string;
  entity:{kind:string;key:string;mapping_version:string};contract?:{native_id:string;quantity_unit:string};
  envelope:{observation_id:string;provider_id:string;event_at:string;published_at:string|null;available_at:string;ingested_at:string;
    raw_content_hash:string;source_ref:string;unit:string;normalizer_version:string;quality_state:string;supersedes_observation_id:string|null}};
type Dimension = {status:string;reason:string;fact_ids:string[];metrics:Record<string,string|number|null>};
type Snapshot = {snapshot_id:string;content_hash:string;context_manifest_id:string|null;market_manifest_id:string;as_of:string;
  facts:Fact[];dimensions:Record<string,Dimension>;event_risk:{state:string;reason:string;horizon_days:number;fact_ids:string[]};
  conflicts:{metric:string;fact_ids:string[];values:string[];resolution:string}[];warnings:string[]};
type Source = {provider:string;domain:Domain;status:string;coverage:string[];authentication:string;cost:string;frequency:string;
  historical_depth:string;timestamp_semantics:string;rate_constraints:string;limitations:string[];fact_count:number;
  live_validated_at:string|null;last_ingested_at:string|null};
const domains:Domain[]=['macro','events','news','derivatives','fundamentals','options','onchain'];
const time=(value:string|null|undefined)=>value ? new Date(value).toISOString().replace('T',' ').replace('.000Z',' UTC') : 'Unknown';

function History({facts,label,unit}:{facts:Fact[];label:string;unit:string}) {
  const rows=[...facts].sort((a,b)=>a.envelope.event_at.localeCompare(b.envelope.event_at));
  const values=rows.map(f=>Number(f.value));
  if(values.length<2||values.some(v=>!Number.isFinite(v)))return <p className="sub">Insufficient history for {label}.</p>;
  const lo=Math.min(...values),hi=Math.max(...values),range=hi-lo||1;
  const points=values.map((v,i)=>`${10+i*780/(values.length-1)},${130-(v-lo)/range*110}`).join(' ');
  return <div><div className="panel-head"><strong>{label}</strong><span className="sub">N={values.length} · {unit} · {time(rows[0].envelope.event_at)} → {time(rows.at(-1)?.envelope.event_at)}</span></div>
    <svg viewBox="0 0 800 150" role="img" aria-label={`${label} history, ${unit}`} style={{width:'100%',height:150}}>
      <line x1="10" y1="130" x2="790" y2="130" stroke="#263431"/><polyline points={points} fill="none" stroke="#78b9c5" strokeWidth="2"/>
      <text x="10" y="15" fill="#98aaa8" fontSize="12">{number(hi,6)}</text><text x="10" y="147" fill="#98aaa8" fontSize="12">{number(lo,6)}</text></svg>
  </div>;
}

export default function IntelligencePane({context,instrumentId,compact=false}:{context:Context;instrumentId?:string|null;compact?:boolean}) {
  const [scope,setScope]=useState(instrumentId??context.members[0]?.instrument_id??'');
  const [tab,setTab]=useState<'overview'|'coverage'|Domain>('overview');
  const [snapshot,setSnapshot]=useState<Snapshot|null>(null);
  const [sources,setSources]=useState<Source[]>([]);
  const [error,setError]=useState<string|null>(null);
  const [inspected,setInspected]=useState<Fact|null>(null);
  const [expanded,setExpanded]=useState(!compact);
  const [refresh,setRefresh]=useState(0);
  const [manifestDraft,setManifestDraft]=useState('');
  const [manifest,setManifest]=useState('');
  useEffect(()=>{
    let alive=true;setError(null);setSnapshot(null);
    const params=new URLSearchParams({as_of:context.as_of,market_manifest_id:context.source_manifest_id});
    if(scope)params.set('instrument_id',scope);
    if(manifest)params.set('context_manifest_id',manifest);
    Promise.all([getJson<Snapshot>('intelligence/context',params),getJson<{items:Source[]}>('intelligence/coverage',new URLSearchParams({as_of:context.as_of}))])
      .then(([snap,registry])=>{if(alive){setSnapshot(snap);setSources(registry.items);}})
      .catch(err=>{if(alive)setError(err instanceof ApiError?err.code:'INTELLIGENCE_UNAVAILABLE');});
    return()=>{alive=false;};
  },[context.as_of,context.source_manifest_id,scope,manifest,refresh]);
  const inspect=async(f:Fact)=>{
    try {setInspected(await getJson<Fact>(`intelligence/facts/${f.envelope.observation_id}`,new URLSearchParams({as_of:context.as_of})));}
    catch {setError('SOURCE_INSPECTION_UNAVAILABLE');}
  };
  if(error)return <section className="panel"><div className="panel-head"><h2>Intelligence unavailable</h2></div><div className="panel-body"><p>{error} · Previously ingested market data remains independent.</p><button className="button" onClick={()=>setRefresh(v=>v+1)}>Retry context</button></div></section>;
  if(!snapshot)return <div className="callout" aria-busy="true">Loading contextual facts at the selected cutoff…</div>;
  const derivative=snapshot.dimensions.derivatives?.metrics??{};
  const facts=tab==='overview'||tab==='coverage'?snapshot.facts:snapshot.facts.filter(f=>f.domain===tab);
  return <div className="stack">
    <section className="panel"><div className="panel-head"><div><h2>{compact?'Instrument context':'Intelligence'}</h2><span className="sub">Frozen availability · source facts / extracted facts / interpretation remain distinct</span></div>
      {compact&&<button className="button" onClick={()=>setExpanded(v=>!v)}>{expanded?'Collapse context':'Explore context'}</button>}</div>
      <div className="panel-body"><div className="grid four">
        <div className="metric"><div className="metric-label">Event risk</div><strong>{snapshot.event_risk.state}</strong><p className="sub">{snapshot.event_risk.reason}</p></div>
        <div className="metric"><div className="metric-label">Funding / event</div><strong>{number(derivative.funding_latest as number|undefined,8)}</strong><p className="sub">fraction · {String(derivative.funding_N??0)} observations</p></div>
        <div className="metric"><div className="metric-label">Open interest</div><strong>{number(derivative.oi_latest as number|undefined,3)}</strong><p className="sub">{String(derivative.oi_unit??'Unavailable')} · {String(derivative.oi_N??0)} observations</p></div>
        <div className="metric"><div className="metric-label">Research status</div><strong>No supported edge</strong><p className="sub">Phase 8 momentum OOS −7.82%, N=82. Context is descriptive.</p></div>
      </div><p className="sub">As-of {time(snapshot.as_of)} · Context manifest {snapshot.context_manifest_id??'none visible'} · Snapshot {shortId(snapshot.snapshot_id)}</p>
      <p className="sub">Price/OI: {String(derivative.price_oi_state??'Unavailable')} · OI change fraction: {number(derivative.oi_change_fraction as number|undefined,6)} · Source freshness {time(sources.find(s=>s.domain==='derivatives')?.last_ingested_at)}</p></div></section>
    {expanded&&<>
      <div className="toolbar"><label>Instrument context <select aria-label="Intelligence instrument" value={scope} onChange={e=>setScope(e.target.value)}>
        <option value="">Universe context</option>{context.members.filter(m=>m.instrument_id).map(m=><option key={m.instrument_id} value={m.instrument_id!}>{m.symbol}</option>)}</select></label>
        <label>Context manifest <input aria-label="Context manifest" value={manifestDraft} onChange={e=>setManifestDraft(e.target.value)} placeholder="Automatic at cutoff or exact UUID"/></label>
        <button className="button" onClick={()=>setManifest(manifestDraft.trim())}>Pin context</button>
        <button className="button" onClick={()=>setRefresh(v=>v+1)}>Reload stored context</button></div>
      <div className="tabs" role="tablist" aria-label="Intelligence domains">{(['overview',...domains,'coverage'] as const).map(d=><button className={`button ${d===tab?'active':''}`} role="tab" aria-selected={d===tab} key={d} onClick={()=>{setTab(d);setInspected(null);}}>{d==='coverage'?'Source coverage':d==='overview'?'Context overview':d==='onchain'?'On-chain':d.charAt(0).toUpperCase()+d.slice(1)}</button>)}</div>
      {tab==='overview'?<section className="panel"><div className="panel-head"><h2>Context dimensions</h2></div><div className="panel-body">
        {Object.entries(snapshot.dimensions).map(([name,d])=><div className="data-row" key={name}><strong>{name}</strong><span className="badge">{d.status}</span><span className="sub">{d.fact_ids.length} facts · {d.reason}</span></div>)}
        <p className="sub">Interpretation: positive funding and rising OI carry no guaranteed direction. Calendar absence cannot establish event safety.</p>
        {snapshot.conflicts.map((c,i)=><div key={i} className="callout">Source conflict: {c.metric} · {c.values.join(' vs ')} · {c.resolution}. Both facts are retained.</div>)}
        <details><summary>Snapshot identity and limitations</summary><pre>{JSON.stringify({content_hash:snapshot.content_hash,context_manifest_id:snapshot.context_manifest_id,warnings:snapshot.warnings},null,2)}</pre></details>
      </div></section>:tab==='coverage'?<section className="panel"><div className="panel-head"><h2>Source coverage</h2><span className="sub">Adapters do not establish live coverage</span></div><div className="panel-body">
        {sources.map(s=><div className="stack" key={s.provider}><div className="data-row"><strong>{s.provider} · {s.domain}</strong><span className="badge">{s.status}</span><span>{s.fact_count} live facts · {s.cost} · Auth: {s.authentication}</span></div>
          <p className="sub">Coverage: {s.coverage.join('; ')||'No live instruments'} · {s.frequency} · {s.historical_depth} · Validated {time(s.live_validated_at)}</p>
          <p className="sub">{s.timestamp_semantics} · {s.rate_constraints}</p><ul>{s.limitations.map(l=><li key={l}>{l}</li>)}</ul></div>)}
      </div></section>:<section className="panel"><div className="panel-head"><h2>{tab} evidence</h2><span className="badge">{snapshot.dimensions[tab]?.status??'UNKNOWN'}</span></div><div className="panel-body">
        <p>{snapshot.dimensions[tab]?.reason}</p>
        {!facts.length?<div className="callout">Data unavailable at this cutoff. {sources.find(s=>s.domain===tab)?.status??'No configured source'}. Missing values are not zero.</div>:<>
          {tab==='derivatives'&&<><History facts={facts.filter(f=>f.kind==='funding')} label="Realized funding" unit="fraction per event"/>
            <History facts={facts.filter(f=>f.kind==='open_interest')} label="Daily open interest" unit={String(derivative.oi_unit??'source units')}/></>}
          {tab==='macro'&&<History facts={facts} label="Average outstanding Treasury Bills interest rate" unit="percent per annum; not a spot risk-free rate"/>}
          {tab==='events'&&<p className="sub">Timeline uses source event UTC instants; inspect publication and availability separately. Different categories retain their identity.</p>}
          <div className="table-wrap"><table><thead><tr><th>Type / classification</th><th>Event / period</th><th>Value / title</th><th>Source / revision</th><th>Availability</th><th/></tr></thead><tbody>
            {[...facts].reverse().slice(0,150).map(f=><tr key={f.envelope.observation_id}><td>{f.kind} · {f.classification}<br/>{f.classification_scope}</td><td>{time(f.scheduled_at??f.envelope.event_at)}{f.period_end&&<small>Period {f.period_start} → {f.period_end}</small>}</td>
              <td>{f.title??f.value??'Source metadata'}<small>{f.envelope.unit}</small></td><td>{f.envelope.provider_id} · v{f.revision_number}</td><td>{time(f.envelope.available_at)}</td><td><button className="button" onClick={()=>inspect(f)}>Inspect source</button></td></tr>)}
          </tbody></table></div><p className="sub">Showing latest {Math.min(150,facts.length)} of {facts.length}; domain API supports pagination.</p></>}
      </div></section>}
      {inspected&&<div className="modal-backdrop" onClick={()=>setInspected(null)} onKeyDown={e=>{if(e.key==='Escape')setInspected(null);}}><section className="modal" role="dialog" aria-modal="true" aria-label="Source inspector" style={{maxHeight:'85vh',overflow:'auto',width:'min(90vw,900px)'}} onClick={e=>e.stopPropagation()}><div className="panel-head"><h2>Source inspector</h2><button className="button" autoFocus onClick={()=>setInspected(null)}>Close inspector</button></div><div className="panel-body">
        <p>Normalized fact · immutable raw SHA256 · knowledge timestamps · entity mapping · quality · revision parent · transformation version. External text is untrusted.</p>
        <pre style={{whiteSpace:'pre-wrap',overflowWrap:'anywhere'}}>{JSON.stringify(inspected,null,2)}</pre></div></section></div>}
    </>}
  </div>;
}
