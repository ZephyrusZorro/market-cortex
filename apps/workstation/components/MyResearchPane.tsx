'use client';

import { useCallback, useEffect, useState } from 'react';
import { getJson, postJson, category, shortId, type Context } from '@/lib/api';

type Evidence={evidence_id:string;source_kind:string;source_id:string;source_version:number;recorded_at:string;classification:string;subject:string;facts:Record<string,unknown>};
type Memory={persisted:boolean;memory_id:string;version:number;key:string;memory_type:string;source_type:string;status:string;statement:string;value:string|number|null;sample_N:number;sufficiency:string;evidence_ids:string[];last_validated:string;owner_override:string|null};
type Proposal={proposal_id:string;version:number;key:string;value:string|number;status:string;rationale:string;risk:string;evidence_ids:string[]};
type Item={key?:string;message?:string;statement?:string;sample_N?:number;subject?:string;evidence_ids:string[];change?:string};
type Profile={snapshot_id:string;audience:string;as_of:string;algorithm_version:string;privacy:string;evidence:Evidence[];memories:Memory[];proposals:Proposal[];
  observed_behavior:{genuine_owner_record_N:number;validation_record_N:number;recent_record_N:number;history_state:string;median_horizon:number|null;source_counts:Record<string,number>;instrument_frequency:Record<string,number>};
  baseline:Record<string,unknown>;patterns:Item[];coaching:Item[];strategy_evidence:{strategy:string;oos_return:number|null;N:number|null;owner_usage_N:number;behavior_fit:string;edge_status:string;evidence_ids:string[]}[];
  review_queue:{reason:string;priority:number;source_id:string;evidence_ids:string[]}[];study_items:{question:string;answer_basis:unknown;evidence_ids:string[]}[];limitations:string[]};
type Mission={mission_id:string;status:string;plan:{steps:{step_id:string;tool_id:string;reason:string;status:string}[]};report:string;usage:{tool_calls:number;api_cost_inr:number}};
const ROOT='personalization';
function Panel({title,children}:{title:string;children:React.ReactNode}){return <section className="panel"><div className="panel-head"><h2>{title}</h2></div><div className="panel-body stack">{children}</div></section>;}

export default function MyResearchPane({context,environment}:{context:Context;environment:string}){
  const [audience,setAudience]=useState('OWNER_RESEARCH'); const [cutoff,setCutoff]=useState('');
  const [profile,setProfile]=useState<Profile|null>(null); const [error,setError]=useState(''); const [busy,setBusy]=useState(false);
  const [memory,setMemory]=useState<Memory|null>(null); const [evidence,setEvidence]=useState<Evidence|null>(null); const [history,setHistory]=useState<unknown>(null);
  const [search,setSearch]=useState(''); const [type,setType]=useState(''); const [status,setStatus]=useState('');
  const [prefKey,setPrefKey]=useState('default_horizon'); const [prefValue,setPrefValue]=useState('20'); const [correction,setCorrection]=useState('');
  const [question,setQuestion]=useState('What mistakes do I repeat?'); const [answer,setAnswer]=useState<unknown>(null);
  const [goal,setGoal]=useState('Investigate whether BTC momentum is currently attractive and whether historical evidence supports it.');
  const [mission,setMission]=useState<Mission|null>(null); const [replay,setReplay]=useState(''); const [review,setReview]=useState<unknown>(null);
  const [usePreferences,setUsePreferences]=useState(false); const [showStudy,setShowStudy]=useState(false);
  const canWrite=!cutoff&&(environment==='OWNER_MAIN'||audience==='SYNTHETIC_VALIDATION');
  const params=useCallback(()=>{const p=new URLSearchParams({audience});if(cutoff)p.set('as_of',cutoff);return p;},[audience,cutoff]);
  const load=useCallback(async()=>{try{setProfile(await getJson<Profile>(ROOT+'/profile',params()));setError('');}catch(e){setError(String(e));}},[params]);
  useEffect(()=>{void load();setMemory(null);setEvidence(null);setHistory(null);},[load]);
  useEffect(()=>{
    if(!mission||!['RUNNING','READY','QUEUED'].includes(mission.status))return;
    const timer=setInterval(()=>{void getJson<Mission>('cortex/missions/'+mission.mission_id).then(setMission).catch(e=>setError(String(e)));},1800);
    return ()=>clearInterval(timer);
  },[mission]);
  async function action(fn:()=>Promise<unknown>){setBusy(true);try{await fn();setError('');}catch(e){setError(String(e));}finally{setBusy(false);}}
  async function changeMemory(verb:string){if(!memory)return;await action(async()=>{
    const body:Record<string,unknown>={expected_version:memory.version,action:verb};
    if(verb==='correct')body.correction=['default_horizon','preferred_instrument','default_mode','preferred_view','review_emphasis'].includes(memory.key)?{audience,key:memory.key,value:memory.key==='default_horizon'?Number(correction):correction}:undefined;
    if(verb==='correct'&&!body.correction)body.statement=correction;
    setMemory(await postJson<Memory>(ROOT+'/memories/'+memory.memory_id+'/action',body));await load();
  });}
  const cite=(ids:string[])=><span className="personal-citations">{ids.slice(0,10).map(id=><button className="button ghost small" key={id} onClick={()=>setEvidence(profile?.evidence.find(e=>e.evidence_id===id)??null)}>[{id.slice(0,8)}]</button>)}</span>;
  const memoryRows=profile?.memories.filter(m=>(!type||m.memory_type===type)&&(!status||m.status===status)&&(m.statement+' '+m.key).toLowerCase().includes(search.toLowerCase()))??[];
  return <div className="stack personal-research">
    <div className="page-heading"><div><div className="eyebrow">LOCAL / EVIDENCE-BASED / REVERSIBLE</div><h1>My Research</h1><p>Inspect what your records support, review CORTEX lessons, and control research preferences.</p></div><span className="badge">LOCAL ONLY</span></div>
    {error&&<div className="callout error" role="alert">{error}</div>}
    <div className="research-controls"><label>Profile audience <select aria-label="Profile audience" value={audience} onChange={e=>setAudience(e.target.value)}><option value="OWNER_RESEARCH">Owner research</option>{environment==='PILOT_TEST'&&<option value="SYNTHETIC_VALIDATION">Synthetic validation — never owner history</option>}</select></label>
      <label>Historical cutoff <input aria-label="Profile historical cutoff" placeholder="ISO timestamp with offset" value={cutoff} onChange={e=>setCutoff(e.target.value)}/></label>
      <button className="button" disabled={busy||!!cutoff} onClick={()=>void action(async()=>{setProfile(await postJson<Profile>(ROOT+'/refresh',{audience}));})}>Refresh profile</button>
      <button className="button" onClick={()=>void action(async()=>setAnswer(await getJson(ROOT+'/export',params())))}>Inspect metadata export</button></div>
    {audience==='SYNTHETIC_VALIDATION'?<div className="callout">SYNTHETIC VALIDATION. These records test the implementation and describe no genuine owner habits.</div>:environment!=='OWNER_MAIN'&&<div className="callout">Owner history is unavailable in this catalog. Pilot/test records are excluded; owner preferences require a configured owner environment.</div>}
    {profile&&<>
      <div className="grid four">{[['Eligible owner records',profile.observed_behavior.genuine_owner_record_N],['History state',profile.observed_behavior.history_state.replaceAll('_',' ')],['Recent research records',profile.observed_behavior.recent_record_N],['Median mission horizon',profile.observed_behavior.median_horizon??'Unavailable']].map(([k,v])=><div className="metric" key={k}><div className="metric-label">{k}</div><div className="metric-value">{v}</div><div className="metric-foot">{profile.algorithm_version} · {profile.audience}</div></div>)}</div>
      <div className="grid two">
        <Panel title="Research habits and learning"><p>Recurring: at least 3 distinct records. Strong pattern: at least 10. Current window: 90 days. Record counts do not establish independent samples.</p>
          {!profile.patterns.length&&<div className="empty">INSUFFICIENT HISTORY — no recurring owner pattern established.</div>}
          {profile.patterns.map(p=><div className="personal-item" key={p.key}><strong>{p.statement}</strong><small>{p.subject} · N={p.sample_N} · {p.change}</small>{cite(p.evidence_ids)}</div>)}
          <details><summary>Transparent process baseline</summary><pre>{JSON.stringify(profile.baseline,null,2)}</pre></details></Panel>
        <Panel title="Coaching and CORTEX lessons">
          {profile.coaching.map(c=><div className="personal-item" key={c.key}><strong>{c.message}</strong><small>{c.subject} · N={c.sample_N}</small>{cite(c.evidence_ids)}</div>)}
          {!profile.coaching.length&&<p>No evidence-backed coaching item is available.</p>}
          <label>Ask your research history <input aria-label="Personal research question" value={question} onChange={e=>setQuestion(e.target.value)}/></label>
          <button className="button" onClick={()=>void action(async()=>setAnswer(await postJson(ROOT+'/query',{question,audience,as_of:cutoff||null})))}>Ask local history</button>
          {answer!==null&&<details open><summary>Inspect grounded answer / metadata</summary><pre>{JSON.stringify(answer,null,2)}</pre></details>}</Panel>
        <Panel title="Strategy evidence"><p>Research behavior fit and strategy edge are evaluated separately.</p>{profile.strategy_evidence.map(s=><div className="personal-item" key={s.strategy}><strong>{category(s.strategy)} · {s.edge_status}</strong><span>Temporal OOS: {s.oos_return===null?'Unavailable':(s.oos_return*100).toFixed(2)+'%'} · N={s.N??'Unavailable'}</span><small>Owner usage: {s.owner_usage_N} · {s.behavior_fit}</small>{cite(s.evidence_ids)}</div>)}</Panel>
        <Panel title="Daily review and study"><p>Priorities reflect recorded due dates, statuses and unresolved evidence.</p>{profile.review_queue.map((r,i)=><div className="personal-item" key={i}><strong>{category(r.reason)}</strong><small>Priority {r.priority} · record {shortId(r.source_id)}</small>{cite(r.evidence_ids)}</div>)}{!profile.review_queue.length&&<p>No eligible owner review item is due.</p>}
          {profile.study_items.map((s,i)=><div className="personal-item" key={i}><strong>{s.question}</strong>{cite(s.evidence_ids)}<details><summary>Review recorded answer basis</summary><pre>{JSON.stringify(s.answer_basis,null,2)}</pre></details></div>)}
          <details><summary>Learning timeline</summary>{profile.evidence.map(e=><div className="data-row" key={e.evidence_id}><span>{e.recorded_at.slice(0,10)} · {e.source_kind} · {e.subject}</span>{cite([e.evidence_id])}</div>)}</details></Panel>
        <Panel title="Explicit research preferences"><p>Inferred usage remains separate. Workflow changes require owner acceptance.</p>
          <label>Preference <select aria-label="Preference key" value={prefKey} onChange={e=>{setPrefKey(e.target.value);setPrefValue(e.target.value==='default_horizon'?'20':e.target.value==='review_emphasis'?'quant':e.target.value==='default_mode'?'DEEP_RESEARCH':e.target.value==='preferred_instrument'?'BTCUSDT':'my-research');}}>{['default_horizon','preferred_instrument','default_mode','preferred_view','review_emphasis'].map(k=><option key={k} value={k}>{category(k)}</option>)}</select></label>
          <label>Value <input aria-label="Preference value" value={prefValue} onChange={e=>setPrefValue(e.target.value)}/></label><button className="button primary" disabled={!canWrite||busy} onClick={()=>void action(async()=>{await postJson(ROOT+'/preferences',{audience,key:prefKey,value:prefKey==='default_horizon'?Number(prefValue):prefValue});await load();})}>Save explicit preference</button>
          {profile.memories.filter(m=>m.source_type==='EXPLICIT').map(m=><div className="personal-item" key={m.memory_id}><strong>{category(m.key)}: {m.value??m.statement}</strong><small>{m.status} · version {m.version}</small><button className="button" onClick={()=>{setMemory(m);setCorrection(String(m.value??m.statement));}}>Inspect preference</button></div>)}</Panel>
        <Panel title="Adaptation proposals">{!profile.proposals.length&&<p>No supported workflow proposal is available.</p>}{profile.proposals.map(p=><div className="personal-item" key={p.proposal_id}><strong>{category(p.key)} → {p.value}</strong><span>{p.rationale}</span><small>{p.status} · {p.risk} · version {p.version}</small>{cite(p.evidence_ids)}<div className="research-controls">{['accept','reject','retire'].map(verb=><button key={verb} className="button" disabled={!canWrite||busy||(verb==='retire'?p.status!=='ACTIVE':p.status!=='PROPOSED')} onClick={()=>void action(async()=>{await postJson(ROOT+'/proposals/'+p.proposal_id+'/action',{expected_version:p.version,action:verb});await load();})}>{category(verb)} proposal</button>)}</div></div>)}</Panel>
      </div>
      <Panel title="Memory inspector"><div className="research-controls"><input aria-label="Memory search" placeholder="Search memories" value={search} onChange={e=>setSearch(e.target.value)}/><select aria-label="Memory type" value={type} onChange={e=>setType(e.target.value)}><option value="">All types</option>{['WORKING','EPISODIC','SEMANTIC','PROCEDURAL','MARKET','STRATEGY','FAILURE','PREDICTION'].map(t=><option key={t}>{t}</option>)}</select><select aria-label="Memory status" value={status} onChange={e=>setStatus(e.target.value)}><option value="">All statuses</option>{['ACTIVE','TENTATIVE','OWNER_CONFIRMED','DISABLED','REJECTED','EXPIRED'].map(t=><option key={t}>{t}</option>)}</select></div>
        <div className="personal-memory-list">{memoryRows.map(m=><button className="button ghost" key={m.memory_id} onClick={()=>{setMemory(m);setCorrection(String(m.value??m.statement));setHistory(null);}}>{m.statement} · {m.source_type} · {m.status}</button>)}</div>
        {memory&&<div className="personal-item"><h3>{memory.statement}</h3><small>{memory.memory_type} · {memory.source_type} · {memory.status} · v{memory.version} · N={memory.sample_N} · last validated {memory.last_validated}</small>{cite(memory.evidence_ids)}
          <div className="research-controls">{['confirm','reject','disable','retire'].map(verb=><button className="button" key={verb} disabled={!canWrite||busy||!memory.persisted} onClick={()=>void changeMemory(verb)}>{category(verb)} memory</button>)}<button className="button" disabled={!memory.persisted} onClick={()=>void action(async()=>setHistory(await getJson(ROOT+'/memories/'+memory.memory_id+'/history')))}>Inspect revisions</button></div>
          <label>Owner correction <input aria-label="Owner memory correction" value={correction} onChange={e=>setCorrection(e.target.value)}/></label><button className="button" disabled={!canWrite||busy||!memory.persisted} onClick={()=>void changeMemory('correct')}>Save correction as new version</button>
          <button className="button" disabled={!canWrite||busy||!memory.persisted} onClick={()=>void action(async()=>{await postJson(ROOT+'/feedback',{audience,target_kind:'MEMORY',target_id:memory.memory_id,rating:'IRRELEVANT'});await load();})}>Record irrelevant feedback</button>
          {history!==null&&<pre>{JSON.stringify(history,null,2)}</pre>}</div>}
        {evidence&&<div className="personal-item"><h3>Evidence provenance</h3><pre>{JSON.stringify(evidence,null,2)}</pre></div>}
      </Panel>
      <Panel title="Personalized research plan"><label>Research goal <textarea aria-label="Personalized mission goal" value={goal} onChange={e=>setGoal(e.target.value)}/></label>
        <label><input type="checkbox" checked={usePreferences} onChange={e=>setUsePreferences(e.target.checked)}/> Apply explicit preferences to unspecified mission fields</label>
        <button className="button primary" disabled={busy||!!cutoff} onClick={()=>void action(async()=>{const frozen=await postJson<Profile>(ROOT+'/refresh',{audience});setProfile(frozen);setMission(await postJson<Mission>(ROOT+'/missions',{snapshot_id:frozen.snapshot_id,request:{goal,manifest_id:context.source_manifest_id},use_explicit_preferences:usePreferences}));setReplay('');})}>Create personalized plan</button>
        {mission&&<><strong>{mission.status} · {shortId(mission.mission_id)}</strong>{mission.plan.steps.map(s=><div className="data-row" key={s.step_id}><span>{s.tool_id}</span><small>{s.status} · {s.reason}</small></div>)}<div className="research-controls"><button className="button" disabled={busy||mission.status!=='READY'} onClick={()=>void action(async()=>{await postJson('cortex/missions/'+mission.mission_id+'/execute',{});setMission({...mission,status:'QUEUED'});})}>Start personalized investigation</button>
          <button className="button" disabled={!['COMPLETED','INCONCLUSIVE','PARTIAL'].includes(mission.status)} onClick={()=>void action(async()=>{const r=await postJson<{status:string;personalization_verified:boolean}>(ROOT+'/missions/'+mission.mission_id+'/replay',{});setReplay(r.status+' · personal evidence '+(r.personalization_verified?'verified':'unavailable'));setReview(await getJson(ROOT+'/missions/'+mission.mission_id+'/review'));})}>Verify personalized replay</button></div><span role="status">{replay}</span>{review!==null&&<details open><summary>Post-research process review</summary><pre>{JSON.stringify(review,null,2)}</pre></details>}{mission.report&&<details><summary>Cited research dossier</summary><pre>{mission.report}</pre></details>}</>}
      </Panel>
      <Panel title="Limits and provenance"><span>Snapshot {shortId(profile.snapshot_id)} · knowledge cutoff {profile.as_of} · {profile.privacy}</span>{profile.limitations.map(l=><small key={l}>{category(l)}</small>)}</Panel>
    </>}
  </div>;
}
