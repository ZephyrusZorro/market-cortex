'use client';

import { useEffect, useMemo, useState } from 'react';
import { ApiError, getJson, postJson, shortId, type Context } from '@/lib/api';

type Evidence = { evidence_id: string; tool_id: string; label: string; kind: string; value: string | number | null;
  manifest_id: string; as_of: string; source_id: string | null; source_manifest_id: string | null; source_recorded_at: string | null;
  observation_id: string | null; freshness: string | null; reason: string | null; parameters: Record<string, unknown> };
type Claim = { claim_id: string; type: string; text: string; evidence_ids: string[] };
type Step = { step_id: string; question: string; tool_id: string; reason: string; required: boolean; scope: string;
  depends_on: string[]; status: string; attempts: number; error_code: string | null; output: { evidence: Evidence[]; elapsed_ms: number; output_hash: string } | null };
type Hypothesis = { hypothesis_id: string; statement: string; status: string; originating_evidence: string[];
  support: string[]; contradictions: string[]; test_requirements: string[] };
type Mission = { mission_id: string; revision: number; created_at: string; status: string; termination_reason: string | null;
  request: { goal: string; mode: string }; context: { manifest_id: string; as_of: string; context_manifest_id: string | null } | null;
  budgets: { max_tool_calls: number; max_model_calls: number; max_replans: number; max_quant_runs: number; timeout_seconds: number };
  usage: { tool_calls: number; model_calls: number; replans: number; quant_runs: number; elapsed_ms: number; api_cost_inr: number; cache_hits: number };
  plan: { steps: Step[] }; hypotheses: Hypothesis[]; claims: Claim[]; contradictions: Claim[]; limitations: Claim[];
  report: string; evaluator: Record<string, unknown>; activity: Record<string, unknown>[]; model_metadata: Record<string, unknown>;
  evidence_graph: { nodes?: unknown[]; edges?: unknown[] }; similar_mission_ids: string[]; deadline_at: string | null };
const modes = ['QUICK_RESEARCH', 'DEEP_RESEARCH', 'HISTORICAL_RESEARCH', 'STRATEGY_RESEARCH', 'THESIS_REVIEW', 'CHANGE_ANALYSIS'] as const;
const templates = ['instrument_deep_dive', 'market_review', 'thesis_challenge', 'strategy_review', 'what_changed', 'historical', 'event_context'];
const ongoing = (m: Mission) => ['RUNNING', 'READY', 'PLANNING', 'CREATED'].includes(m.status);
const show = (v: unknown) => v == null ? 'Unavailable' : typeof v === 'object' ? JSON.stringify(v) : String(v);

export default function ResearchLabPane({ context, symbol }: { context: Context; symbol: string | null }) {
  const [goal, setGoal] = useState(`Investigate whether ${symbol ?? 'BTCUSDT'} momentum is currently attractive and whether historical evidence supports it.`);
  const [mode, setMode] = useState<string>('DEEP_RESEARCH');
  const [template, setTemplate] = useState('instrument_deep_dive');
  const [compare, setCompare] = useState('');
  const [older, setOlder] = useState('');
  const [thesis, setThesis] = useState('');
  const [version, setVersion] = useState(1);
  const [cutoff, setCutoff] = useState(context.as_of);
  const [requiredOptions, setRequiredOptions] = useState(false);
  const [fresh, setFresh] = useState(false);
  const [toolLimit, setToolLimit] = useState(16);
  const [modelLimit, setModelLimit] = useState(0);
  const [mission, setMission] = useState<Mission | null>(null);
  const [history, setHistory] = useState<Mission[]>([]);
  const [busy, setBusy] = useState(false);
  const [queued, setQueued] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [active, setActive] = useState<string | null>(null);
  const [search, setSearch] = useState('');
  const [replay, setReplay] = useState<Record<string, unknown> | null>(null);
  const [diff, setDiff] = useState<Record<string, unknown> | null>(null);
  const [source, setSource] = useState<unknown>(null);
  const evidence = useMemo(() => mission?.plan.steps.flatMap(s => s.output?.evidence ?? []) ?? [], [mission]);
  const selected = evidence.find(e => e.evidence_id === active) ?? evidence[0];
  const visibleHistory = history.map(m => mission?.mission_id === m.mission_id ? mission : m);
  const refreshHistory = () => getJson<{ items: Mission[] }>('cortex/missions').then(r => setHistory(r.items)).catch(() => {});
  useEffect(() => { refreshHistory(); }, []);
  useEffect(() => {
    if (!mission || !ongoing(mission)) return;
    if (mission.status === 'READY' && !queued) return;
    const timer = setInterval(() => {
      getJson<Mission>(`cortex/missions/${mission.mission_id}`).then(setMission).catch(() => {});
    }, 1500);
    return () => clearInterval(timer);
  }, [mission?.mission_id, mission?.status, queued]);
  const act = async (action: () => Promise<void>) => {
    setBusy(true); setError(null);
    try { await action(); } catch (e) { setError(e instanceof ApiError ? e.code : 'RESEARCH_UNAVAILABLE'); }
    finally { setBusy(false); }
  };
  const create = () => act(async () => {
    const result = await postJson<Mission>('cortex/missions', { goal: goal.trim(), mode, template, symbol: symbol ?? undefined,
      compare_symbol: compare || undefined, manifest_id: context.source_manifest_id, as_of: cutoff,
      previous_mission_id: mode === 'CHANGE_ANALYSIS' ? older || undefined : undefined,
      thesis_id: mode === 'THESIS_REVIEW' ? thesis || undefined : undefined, thesis_version: mode === 'THESIS_REVIEW' ? version : undefined,
      duplicate_policy: fresh ? 'fresh' : 'reuse',
      approved_domains: ['market', 'intelligence', 'opportunities', 'quant', 'memory', 'learning', ...(requiredOptions ? ['options'] : [])],
      required_domains: ['market', ...(requiredOptions ? ['options'] : [])], excluded_domains: ['journal', 'portfolio'],
      budgets: { max_tool_calls: toolLimit, max_model_calls: modelLimit, max_replans: 1, max_planner_iterations: 2, max_quant_runs: 0,
        max_historical_comparisons: 3, timeout_seconds: mode === 'QUICK_RESEARCH' ? 120 : 300, api_cost_budget_inr: 0 } });
    setMission(result); setQueued(false); setActive(null); setReplay(null); setDiff(null); refreshHistory();
  });
  const operate = (action: string) => act(async () => {
    if (!mission) return;
    const path = `cortex/missions/${mission.mission_id}`;
    if (action === 'replay') setReplay(await postJson<Record<string, unknown>>(`${path}/replay`, {}));
    else {
      await postJson(`${path}/${action}`, {});
      setQueued(action === 'execute' || action === 'resume');
      setMission(await getJson<Mission>(path)); refreshHistory();
    }
  });
  const cite = (ids: string[]) => ids.map(id => <button key={id} className="cortex-citation" title="Inspect evidence" onClick={() => { setActive(id); setSource(null); }}>[{id.slice(0, 8)}]</button>);
  const linkedReport = (text: string) => text.split(/(\[[a-f0-9]{20}\])/g).map((piece, i) => {
    const id = piece.startsWith('[') ? piece.slice(1, -1) : '';
    return evidence.some(e => e.evidence_id === id) ? <span key={i}>{cite([id])}</span> : piece;
  });
  const inspectSource = () => act(async () => {
    if (!selected) return;
    if (selected.source_id?.startsWith('quant:')) {
      const id = selected.source_id.slice(6);
      setSource(await getJson(`quant/${selected.kind === 'quant_counterfactual' ? 'runs' : 'studies'}/${id}`));
    } else if (selected.observation_id && selected.kind.startsWith('context_')) {
      setSource(await getJson(`intelligence/facts/${selected.observation_id}`, new URLSearchParams({ as_of: selected.as_of })));
    } else setSource(selected);
  });
  return <div className="stack cortex-page research-lab">
    <div className="page-head"><div><div className="eyebrow">CORTEX v2 / BOUNDED AUTONOMOUS RESEARCH</div>
      <h1>Research Lab</h1><p>Define a goal, inspect the plan, and follow deterministic evidence into a cited dossier.</p></div>
      <div className="head-meta">PAID API BUDGET<strong>₹0</strong><span>Local research · Pilot 5 daily data</span></div></div>
    <div className="grid main-side"><div className="stack"><section className="panel"><div className="panel-head"><h2>New mission</h2><span className="badge">Deterministic fallback</span></div>
      <div className="panel-body"><label className="small muted" htmlFor="mission-goal">Research goal</label>
        <textarea id="mission-goal" className="textarea" maxLength={600} value={goal} onChange={e => setGoal(e.target.value)} />
        <div className="row wrap mt12"><label>Mode <select className="select" aria-label="Mission mode" value={mode} onChange={e => { setMode(e.target.value); if (e.target.value === 'QUICK_RESEARCH') setToolLimit(6); else setToolLimit(16); }}>
          {modes.map(m => <option key={m}>{m}</option>)}</select></label>
          <label>Template <select className="select" aria-label="Mission template" value={template} onChange={e => setTemplate(e.target.value)}>{templates.map(t => <option key={t}>{t}</option>)}</select></label>
          <label>Compare <select className="select" aria-label="Mission comparison" value={compare} onChange={e => setCompare(e.target.value)}><option value="">None</option>{context.members.filter(m => m.symbol !== symbol).map(m => <option key={m.symbol}>{m.symbol}</option>)}</select></label></div>
        <div className="row wrap mt12"><label>Knowledge cutoff <input className="input" aria-label="Mission cutoff" value={cutoff} onChange={e => setCutoff(e.target.value)} /></label>
          <label>Tool limit <input className="input" aria-label="Mission tool limit" type="number" min={1} max={32} value={toolLimit} onChange={e => setToolLimit(Number(e.target.value))} /></label>
          <label>Local model calls <input className="input" aria-label="Mission model limit" type="number" min={0} max={2} value={modelLimit} onChange={e => setModelLimit(Number(e.target.value))} /></label></div>
        {mode === 'CHANGE_ANALYSIS' && <label className="row mt12">Previous mission <input className="input" aria-label="Previous mission ID" value={older} onChange={e => setOlder(e.target.value)} /></label>}
        {mode === 'THESIS_REVIEW' && <div className="row mt12"><label>Thesis ID <input className="input" aria-label="Thesis ID" value={thesis} onChange={e => setThesis(e.target.value)} /></label><label>Version <input className="input" aria-label="Thesis version" type="number" min={1} value={version} onChange={e => setVersion(Number(e.target.value))} /></label></div>}
        <div className="row wrap mt12"><label><input type="checkbox" checked={requiredOptions} onChange={e => setRequiredOptions(e.target.checked)} /> Require options evidence</label>
          <label><input type="checkbox" checked={fresh} onChange={e => setFresh(e.target.checked)} /> Fresh investigation</label>
          <button className="button primary" disabled={busy || goal.trim().length < 3} onClick={create}>Create research plan</button></div>
        {error && <div role="alert" className="callout warn mt12">{error.replaceAll('_', ' ')}</div>}
      </div></section>
      {mission && <><div className="grid four"><div className="metric"><div className="metric-label">Mission</div><div className="metric-value small-value">{mission.status}</div><div className="metric-foot">{shortId(mission.mission_id)} · checkpoint {mission.revision}</div></div>
        <div className="metric"><div className="metric-label">Tools / models</div><div className="metric-value small-value">{mission.usage.tool_calls}/{mission.budgets.max_tool_calls} · {mission.usage.model_calls}/{mission.budgets.max_model_calls}</div><div className="metric-foot">Replans {mission.usage.replans}/{mission.budgets.max_replans}</div></div>
        <div className="metric"><div className="metric-label">Research work</div><div className="metric-value small-value">{(mission.usage.elapsed_ms / 1000).toFixed(1)}s</div><div className="metric-foot">Deadline {mission.budgets.timeout_seconds}s · cache {mission.usage.cache_hits}</div></div>
        <div className="metric"><div className="metric-label">Paid API cost</div><div className="metric-value small-value">₹{mission.usage.api_cost_inr}</div><div className="metric-foot">Quant runs {mission.usage.quant_runs}/{mission.budgets.max_quant_runs}</div></div></div>
        <div className="panel panel-body"><div className="row wrap"><button className="button primary" disabled={busy || queued || mission.status !== 'READY'} onClick={() => operate('execute')}>{queued && ongoing(mission) ? 'Mission queued' : 'Start mission'}</button>
          <button className="button" title="Recover an interrupted mission after its worker lease expires; an active worker remains protected." disabled={busy || !['PARTIAL', 'FAILED', 'WAITING_FOR_DATA', 'RUNNING'].includes(mission.status)} onClick={() => operate('resume')}>Resume checkpoint</button>
          <button className="button" disabled={busy || !ongoing(mission)} onClick={() => operate('cancel')}>Cancel mission</button>
          <button className="button" disabled={busy || evidence.length === 0} onClick={() => operate('replay')}>Verify replay</button></div>
          <p className="small muted">{mission.termination_reason ?? 'Plan ready for bounded research'} · Market {shortId(mission.context?.manifest_id ?? '')} · As of {mission.context?.as_of ?? 'Unavailable'} · Context {shortId(mission.context?.context_manifest_id ?? '')}</p>
          {replay && <div role="status" className="callout">Replay: {show(replay.status)} · evidence matched: {show(replay.matched)}</div>}
        </div>
        <section className="panel"><div className="panel-head"><h2>Mission plan</h2><span className="sub">Dependencies and mandatory evidence</span></div><div className="table-scroll"><table><thead><tr><th>Step / subquestion</th><th>Approved tool</th><th>Scope</th><th>Status</th></tr></thead><tbody>
          {mission.plan.steps.map(s => <tr key={s.step_id}><td>{s.question}<div className="small muted">{s.required ? 'Required' : 'Optional'} · depends on {s.depends_on.join(', ') || 'none'}</div></td><td>{s.tool_id}</td><td>{s.scope}</td><td>{s.status}{s.error_code && <div>{s.error_code}</div>}</td></tr>)}</tbody></table></div></section>
        <section className="panel"><div className="panel-head"><h2>Activity</h2><span className="sub">Recorded actions and tool latency</span></div><div className="panel-body">{mission.activity.map((a, i) => <div className="row small" key={i}>{show(a.action)} · {show(a.tool_id ?? a.step_id ?? a.at)} {a.latency_ms != null && `· ${a.latency_ms}ms`}</div>)}</div></section>
        <section className="panel"><div className="panel-head"><h2>Hypotheses and alternatives</h2></div><div className="panel-body">{mission.hypotheses.map(h => <div key={h.hypothesis_id} className="callout mb14"><strong>{h.status}</strong><p>{h.statement}</p><div>{cite(h.originating_evidence)}</div><div className="small muted">Tests required: {h.test_requirements.join('; ')}</div><div className="small">Support {cite(h.support)} · Counter-evidence {cite(h.contradictions)}</div></div>)}</div></section>
        <section className="panel"><div className="panel-head"><h2>Quant evidence</h2><span className="sub">Stored studies remain historical</span></div><div className="panel-body">{evidence.filter(e => e.tool_id.startsWith('mission.quant') || e.tool_id.startsWith('quant.')).map(e => <div key={e.evidence_id}>{e.label}: {show(e.value)} {cite([e.evidence_id])}</div>)}</div></section>
        <section className="panel"><div className="panel-head"><h2>Contradictions / Skeptic</h2></div><div className="panel-body">{mission.contradictions.map(c => <p key={c.claim_id}>{c.text} {cite(c.evidence_ids)}</p>)}</div></section>
        <section className="panel"><div className="panel-head"><h2>Cited research dossier</h2><span className="badge">{show(mission.model_metadata.provider)}</span></div><div className="panel-body"><div className="mission-report">{linkedReport(mission.report || 'Evidence collection has not finished.')}</div>
          <details className="mt12"><summary>Evidence quality dimensions</summary><pre className="code-block">{JSON.stringify(mission.evaluator, null, 2)}</pre></details>
          <details className="mt12"><summary>Evidence graph · {mission.evidence_graph.nodes?.length ?? 0} nodes</summary><pre className="code-block">{JSON.stringify(mission.evidence_graph, null, 2)}</pre></details>
        </div></section>
      </>}
    </div><aside className="stack"><section className="panel"><div className="panel-head"><h2>Mission history</h2><button className="button ghost" onClick={refreshHistory}>Refresh</button></div><div className="panel-body">
      {history.length === 0 && <p className="muted">No saved missions in this environment.</p>}{visibleHistory.map(m => <div className="mb14" key={m.mission_id}><button className="button ghost" onClick={() => act(async () => { setMission(await getJson<Mission>(`cortex/missions/${m.mission_id}`)); setQueued(false); setActive(null); setSource(null); setReplay(null); })}>{m.request.goal}</button>
        <div className="small muted">{m.status} · {shortId(m.mission_id)}</div>{mission && m.mission_id !== mission.mission_id && <button className="cortex-citation" onClick={() => act(async () => { setDiff(await getJson(`cortex/missions/${mission.mission_id}/diff`, new URLSearchParams({ older: m.mission_id }))); })}>Compare with selected mission</button>}</div>)}
      {diff && <details open><summary>Structured changes</summary><pre className="code-block">{JSON.stringify(diff, null, 2)}</pre></details>}
    </div></section>
      <section className="panel"><div className="panel-head"><h2>Evidence inspector</h2><span className="sub">{evidence.length} records</span></div><div className="panel-body">
        <input className="input" aria-label="Filter mission evidence" placeholder="Filter evidence" value={search} onChange={e => setSearch(e.target.value)} />
        <select className="select mt12 mission-evidence-select" aria-label="Select mission evidence" value={selected?.evidence_id ?? ''} onChange={e => { setActive(e.target.value); setSource(null); }}>{evidence.filter(e => `${e.label} ${e.tool_id}`.toLowerCase().includes(search.toLowerCase())).map(e => <option key={e.evidence_id} value={e.evidence_id}>{e.label}</option>)}</select>
        {selected ? <><h3>{selected.label}</h3><div className="metric-value small-value">{show(selected.value)}</div><p className="small muted">{selected.tool_id} · {selected.freshness ?? 'Freshness unspecified'}</p><pre className="code-block">{JSON.stringify(selected, null, 2)}</pre><button className="button" onClick={inspectSource}>Inspect source artifact</button>{source != null && <pre className="code-block">{JSON.stringify(source, null, 2)}</pre>}</> : <p className="muted">Select a citation once evidence is collected.</p>}
      </div></section>
    </aside></div>
  </div>;
}
