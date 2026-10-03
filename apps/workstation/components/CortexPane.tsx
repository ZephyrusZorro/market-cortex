'use client';

import { useEffect, useMemo, useState } from 'react';
import { Activity, ArrowRight, BookOpenText, CheckCircle2, CircleAlert, FileClock, Microscope } from 'lucide-react';
import { ApiError, getJson, postJson, shortId, type Context, type Mode } from '@/lib/api';

type Evidence = { evidence_id: string; tool_id: string; kind: string; label: string; symbol: string | null;
  value: string | number | null; unit: string | null; session_date: string | null; manifest_id: string;
  as_of: string; source_id: string | null; provider_id: string | null; source_manifest_id: string | null;
  source_as_of: string | null; source_recorded_at: string | null; version: string | null; parameters: Record<string, number>;
  observation_id: string | null; quality: string | null; freshness: string | null; coverage: number | null;
  reason: string | null };
type ToolRun = { tool_id: string; version: string; description: string; inputs: Record<string, unknown>;
  status: string; evidence: Evidence[]; output_hash: string; elapsed_ms: number };
type Claim = { claim_id: string; type: string; text: string; evidence_ids: string[]; stance: string };
type ResearchRun = { run_id: string; created_at: string; context: { mode: string; manifest_id: string; as_of: string;
  symbol: string | null; compare_symbol: string | null; environment: string; evaluation_date: string | null };
  tools: ToolRun[]; claims: Claim[]; evidence_strength: string; answer: string; warnings: string[];
  failure_state: string | null; model_provider: string; model_id: string | null; model_status: string;
  model_latency_ms: number; deterministic_latency_ms: number; total_latency_ms: number; evidence_hash: string };
type SavedRun = { run_id: string; created_at: string; symbol: string | null; manifest_id: string;
  as_of: string; question: string; failure_state: string | null };
type Status = { status: string; environment: string; model_provider: string; deterministic_fallback: boolean };

function formatDate(value: string) {
  return new Date(value).toLocaleString('en-GB', { timeZone: 'Asia/Kolkata', dateStyle: 'medium', timeStyle: 'short' }) + ' IST';
}
function display(value: unknown): string {
  return value == null ? '—' : typeof value === 'object' ? JSON.stringify(value) : String(value);
}

export default function CortexPane({ context, mode, symbol }: { context: Context; mode: Mode; symbol: string | null }) {
  const [question, setQuestion] = useState(symbol ? `Analyze ${symbol}.` : 'What is the current Binance Pilot 5 market state?');
  const [depth, setDepth] = useState<'quick' | 'deep'>('deep');
  const [other, setOther] = useState('');
  const [olderManifest, setOlderManifest] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [status, setStatus] = useState<Status | null>(null);
  const [run, setRun] = useState<ResearchRun | null>(null);
  const [activeEvidence, setActiveEvidence] = useState<string | null>(null);
  const [recent, setRecent] = useState<SavedRun[]>([]);
  const [replay, setReplay] = useState<boolean | null>(null);
  const evidence = useMemo(() => run?.tools.flatMap((item) => item.evidence) ?? [], [run]);
  const selected = evidence.find((item) => item.evidence_id === activeEvidence) ?? evidence[0];

  useEffect(() => {
    getJson<Status>('cortex/status').then(setStatus).catch(() => setStatus(null));
    getJson<{ items: SavedRun[] }>('cortex/runs', symbol ? new URLSearchParams({ symbol }) : undefined)
      .then((result) => setRecent(result.items)).catch(() => setRecent([]));
  }, [symbol]);

  const ask = async () => {
    if (question.trim().length < 3 || busy) return;
    setBusy(true); setError(null); setReplay(null);
    try {
      const payload = { question: question.trim(), mode, manifest_id: context.source_manifest_id,
        as_of: context.as_of, symbol: symbol ?? undefined, compare_symbol: other || undefined,
        older_manifest_id: olderManifest || undefined, depth };
      const result = await postJson<ResearchRun>('cortex/research', payload);
      setRun(result); setActiveEvidence(result.tools.flatMap((item) => item.evidence)[0]?.evidence_id ?? null);
      getJson<{ items: SavedRun[] }>('cortex/runs', symbol ? new URLSearchParams({ symbol }) : undefined)
        .then((listing) => setRecent(listing.items)).catch(() => {});
    } catch (problem) { setError(problem instanceof ApiError ? problem.code : 'RESEARCH_UNAVAILABLE'); }
    finally { setBusy(false); }
  };
  const openRun = async (id: string) => {
    setBusy(true); setError(null); setReplay(null);
    try { const result = await getJson<ResearchRun>(`cortex/runs/${id}`);
      setRun(result); setActiveEvidence(result.tools.flatMap((item) => item.evidence)[0]?.evidence_id ?? null); }
    catch (problem) { setError(problem instanceof ApiError ? problem.code : 'RESEARCH_UNAVAILABLE'); }
    finally { setBusy(false); }
  };
  const checkReplay = async () => {
    if (!run) return;
    try { const result = await getJson<{ evidence_reproducible: boolean }>(`cortex/runs/${run.run_id}/replay`);
      setReplay(result.evidence_reproducible); }
    catch { setReplay(false); }
  };
  const linkedAnswer = (text: string) => text.split(/(\[[a-f0-9]{20}\])/g).map((piece, index) => {
    const id = piece.startsWith('[') && piece.endsWith(']') ? piece.slice(1, -1) : null;
    return id && evidence.some((item) => item.evidence_id === id) ?
      <button className="cortex-citation" key={index} onClick={() => setActiveEvidence(id)} title="Inspect evidence">[{id.slice(0, 8)}]</button> : piece;
  });

  return <div className="stack cortex-page">
    <div className="page-head"><div><div className="eyebrow">MARKET CORTEX / EVIDENCE-GROUNDED RESEARCH</div>
      <h1>CORTEX v1</h1><p>Ask a market question. Each answer is assembled from approved, deterministic evidence and a skeptic pass.</p></div>
      <div className="head-meta">ACTIVE ENVIRONMENT<strong>{status?.environment ?? 'UNLABELED'}</strong></div></div>
    <div className="grid four mb14"><div className="metric"><div className="metric-label">Research mode</div><div className="metric-value small-value">{mode}</div>
      <div className="metric-foot">Manifest {shortId(context.source_manifest_id)}</div></div>
      <div className="metric"><div className="metric-label">As-of cutoff</div><div className="metric-value small-value">{formatDate(context.as_of)}</div>
      <div className="metric-foot">Availability, not market quote time</div></div>
      <div className="metric"><div className="metric-label">Research focus</div><div className="metric-value small-value">{symbol ?? 'Pilot market state'}</div>
      <div className="metric-foot">Binance Pilot 5 · P1D</div></div>
      <div className="metric"><div className="metric-label">Model gateway</div><div className="metric-value small-value">{status?.model_provider ?? 'Checking'}</div>
      <div className="metric-foot">Deterministic fallback always available</div></div></div>
    <div className="grid main-side"><div className="stack"><section className="panel"><div className="panel-head"><div><h2>Research question</h2><span className="sub">No unrestricted SQL, shell, web or broker tools</span></div></div>
      <div className="panel-body"><textarea className="textarea" aria-label="Ask CORTEX" value={question}
        placeholder="What evidence supports the current BTC trend?" onChange={(event) => setQuestion(event.target.value)} />
        <div className="row wrap mt12"><label className="small muted">Depth <select className="select" aria-label="Research depth" value={depth} onChange={(event) => setDepth(event.target.value as 'quick' | 'deep')}>
          <option value="quick">Quick</option><option value="deep">Deep with state and lineage</option></select></label>
          <label className="small muted">Compare <select className="select" aria-label="Compare instrument" value={other} onChange={(event) => setOther(event.target.value)}>
            <option value="">None</option>{context.members.filter((item) => item.symbol !== symbol && item.instrument_id).map((item) =>
              <option value={item.symbol} key={item.symbol}>{item.symbol}</option>)}</select></label>
          <label className="small muted">Older manifest <select className="select" aria-label="Older manifest" value={olderManifest} onChange={(event) => setOlderManifest(event.target.value)}>
            <option value="">None</option>{context.recent_manifests.filter((item) => item.manifest_id !== context.source_manifest_id).map((item) =>
              <option value={item.manifest_id} key={item.manifest_id}>{shortId(item.manifest_id)} · {item.created_at.slice(0, 10)}</option>)}</select></label>
          <button className="button primary" disabled={busy || question.trim().length < 3} onClick={ask}>{busy ? 'Researching…' : 'Ask CORTEX'} <ArrowRight size={14}/></button></div>
        <div className="callout mt12">The active {mode} manifest and cutoff are sent with this question. For an earlier cutoff, change the workstation research context first. Stored daily data can be stale.</div>
        {error && <div className="callout error mt12"><strong>{error.replaceAll('_', ' ')}</strong><p>No market value was substituted for the failed request.</p></div>}</div></section>
      {run && <><section className="panel"><div className="panel-head"><div><h2>Research answer</h2><span className="sub">Saved run {shortId(run.run_id)} · {formatDate(run.created_at)}</span></div>
        <span className={`badge ${run.evidence_strength === 'weak' ? 'warn' : 'good'}`}>{run.evidence_strength} evidence</span></div>
        <div className="panel-body"><div className="cortex-answer">{linkedAnswer(run.answer)}</div>
          {run.failure_state && <div className="callout warn mt12">{run.failure_state.replaceAll('_', ' ')}</div>}
          {run.warnings.length > 0 && <div className="callout warn mt12">{run.warnings.join(' · ')}</div>}
          <div className="row wrap between border-top mt18 pad16 micro muted"><span>Model: {run.model_provider} · {run.model_status} · ₹0 API spend</span>
            <span>Tools {run.deterministic_latency_ms?.toFixed(0) ?? '—'} ms · model {run.model_latency_ms.toFixed(0)} ms · total {run.total_latency_ms?.toFixed(0) ?? '—'} ms</span>
            <span>Evidence hash {shortId(run.evidence_hash)}</span></div></div></section>
        <section className="panel"><div className="panel-head"><div><h2>Evidence and counter-evidence</h2><span className="sub">Structured claims; select citations to inspect source values</span></div></div>
          <div className="panel-body cortex-claims">{run.claims.map((claim) => <div className="data-row" key={claim.claim_id}><span className={`badge ${claim.stance === 'counter' || claim.stance === 'limitation' ? 'warn' : 'info'}`}>{claim.type}</span>
            <span className="grow">{claim.text}</span><span className="row wrap">{claim.evidence_ids.map((id) =>
              <button key={id} className="cortex-citation" onClick={() => setActiveEvidence(id)}>[{id.slice(0, 8)}]</button>)}</span></div>)}</div></section></>}
    </div><div className="stack"><section className="panel"><div className="panel-head"><div><h2>Evidence inspector</h2><span className="sub">Click a citation in the answer</span></div><Microscope size={17}/></div>
      <div className="panel-body">{selected ? <div className="data-list">{Object.entries({
        'Evidence ID': selected.evidence_id, Tool: selected.tool_id, Kind: selected.kind, Label: selected.label,
        Instrument: selected.symbol, Value: selected.value, Unit: selected.unit, Session: selected.session_date,
        Manifest: selected.manifest_id, 'As of': selected.as_of, Provider: selected.provider_id, 'Source ID': selected.source_id,
        'Source manifest': selected.source_manifest_id, 'Source as-of': selected.source_as_of,
        'Source recorded': selected.source_recorded_at,
        Version: selected.version, Parameters: selected.parameters, Observation: selected.observation_id,
        Quality: selected.quality, Freshness: selected.freshness, Coverage: selected.coverage,
        'Null reason': selected.reason }).map(([label, value]) => <div className="data-row" key={label}><span className="label">{label}</span>
          <span className="value cortex-value" title={display(value)}>{display(value)}</span></div>)}</div> :
          <div className="empty"><BookOpenText size={20}/><strong>No evidence selected</strong><span>Ask a question or open a saved run.</span></div>}</div></section>
      {run && <section className="panel"><div className="panel-head"><div><h2>Tool activity</h2><span className="sub">Approved deterministic reads</span></div><Activity size={16}/></div>
        <div className="panel-body"><div className="data-list">{run.tools.map((tool, index) => <div className="data-row" key={`${tool.tool_id}-${index}`}><span className="label">{tool.tool_id}</span>
          <span className="value">{tool.status} · {tool.evidence.length} refs · {tool.elapsed_ms.toFixed(0)} ms</span></div>)}</div>
          <button className="button mt12" onClick={checkReplay}>Replay stored evidence</button>
          {replay !== null && <div className={`callout mt12 ${replay ? '' : 'warn'}`}>{replay ? <CheckCircle2 size={14}/> : <CircleAlert size={14}/>} {replay ? 'Pinned evidence hashes match.' : 'Evidence replay differs or is unavailable.'} Language generation is not replayed.</div>}</div></section>}
      <section className="panel"><div className="panel-head"><div><h2>Saved research</h2><span className="sub">Local catalog · prior conclusions are historical context</span></div><FileClock size={16}/></div>
        <div className="panel-body"><div className="cortex-history">{recent.length ? recent.map((item) => <button key={item.run_id} onClick={() => openRun(item.run_id)} disabled={busy}>
          <strong>{item.question}</strong><small>{formatDate(item.created_at)} · {shortId(item.manifest_id)} · {item.symbol ?? 'Pilot'}</small></button>) :
          <div className="subtle">No saved run in this context yet.</div>}</div></div></section>
    </div></div></div>;
}
