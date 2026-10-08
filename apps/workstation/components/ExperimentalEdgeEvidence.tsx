'use client';
import {useState} from 'react';
import {getJson,shortId} from '@/lib/api';
type Link={experiment_id:string;edge_id:string;stance:string;conclusion:string;holdout:string;metrics:{N:number;baseline_skill:number|null};effect:string};
export default function ExperimentalEdgeEvidence(){
  const [links,setLinks]=useState<Link[]|null>(null),[error,setError]=useState('');
  return <section className="panel"><div className="panel-head"><h2>Experimental Quant evidence</h2><button className="button" onClick={()=>{setError('');getJson<{items:Link[]}>('experimental/edges/evidence').then(r=>setLinks(r.items)).catch(e=>setError(e.message));}}>Inspect linked experiments</button></div><div className="panel-body">
    <p className="muted">Supporting and counter experiments attach immutable evidence. Edge status requires a separate review.</p>
    {error&&<p role="alert">{error}</p>}{links&&!links.length&&<p>No experimental evidence linked yet.</p>}
    {links?.map((l,i)=><div className="data-row" key={i}><span>{shortId(l.edge_id)} ← {shortId(l.experiment_id)} · {l.stance} · {l.holdout}</span><strong>{l.conclusion} · N={l.metrics.N}</strong></div>)}
  </div></section>;
}
