'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';
import { ApiError, appendParams, category, getJson, number, postJson, shortId,
  type Context, type InstrumentView, type Mode } from '@/lib/api';
import { PriceChart } from './charts';

type Condition = { condition_id: string; kind: string; metric: string; operator: string;
  threshold: number | number[] | string; observed: number | string | null; met: boolean | null;
  evidence_ids: string[]; description: string };
type Evidence = { evidence_id: string; metric: string; value: number | string | null; unit: string | null;
  source_id: string | null; feature_version: string | null; quality: string | null;
  freshness: string | null; coverage: number | null; reason: string | null };
type Candidate = { candidate_id: string; symbol: string; instrument_id: string; detector_id: string;
  detector_version: string; outcome: string; status: string; detector_strength: string;
  horizon: string;
  event_date: string | null; as_of: string; source_manifest_id: string; bias: string;
  market_regime: string | null; market_state_id: string | null; evidence: Evidence[];
  trigger_conditions: Condition[]; confirmation_conditions: Condition[];
  invalidation_conditions: Condition[]; rejection_conditions: Condition[];
  supporting_evidence_ids: string[]; opposing_evidence_ids: string[]; contradictions: string[];
  rejection_reasons: string[]; coverage: number; freshness: string; data_quality: string;
  evidence_hash: string };
type Scan = { scan_id: string; source_manifest_id: string; as_of: string; market_regime: string | null;
  counts: Record<string, number>; elapsed_ms: number; recorded_events: number; candidates: Candidate[] };
type Thesis = { thesis_id: string; version: number; symbol: string; detector_id: string; status: string;
  statement: string; candidate_ids: string[]; source_manifest_id: string; as_of: string;
  created_at: string; updated_at: string; supporting_evidence_ids: string[];
  opposing_evidence_ids: string[]; risk_factors: string[]; data_limitations: string[];
  confirmation_conditions: Condition[]; invalidation_conditions: Condition[];
  cortex_run_ids: string[]; candidate: Candidate;
  transitions: { from_status: string | null; to_status: string; at: string; actor: string;
    reason: string; source_manifest_id: string; changed_evidence_ids: string[] }[] };
type Detector = { detector_id: string; version: string; description: string; enabled: boolean;
  unsupported_reason: string | null };
const STATUS_ORDER = ['WATCHING','DEVELOPING','AWAITING_CONFIRMATION','VALID','NO_EDGE','EVENT_RISK','AVOID','INVALIDATED'];

function errorCode(problem: unknown) { return problem instanceof ApiError ? problem.code : 'REQUEST_FAILED'; }
function observed(value: number | string | null) { return value == null ? 'unavailable' :
  typeof value === 'number' ? number(value, 4) : value; }
function statusTone(value: string) { return ['VALID', 'candidate'].includes(value) ? 'good' :
  ['NO_EDGE', 'AVOID', 'INVALIDATED', 'rejected'].includes(value) ? 'bad' : 'warn'; }
function ConditionList({ title, rows }: { title: string; rows: Condition[] }) {
  return <div><h3 className="op-subhead">{title}</h3>{rows.length ? <div className="data-list">{rows.map((item) =>
    <div className="data-row" key={item.condition_id}><span className="label">{item.description}</span>
      <span className="value"><span className={`badge ${item.met === true ? 'good' : item.met === false ? 'bad' : 'warn'}`}>
        {item.met === null ? 'unknown' : item.met ? 'met' : 'not met'}</span> {observed(item.observed)} / {Array.isArray(item.threshold) ?
        item.threshold.join('–') : item.threshold}</span></div>)}</div> : <p className="muted small">No conditions.</p>}</div>;
}

function ThesisRiskPanel({ thesis, context }: { thesis: Thesis; context: Context }) {
  const [portfolios, setPortfolios] = useState<{portfolio_id:string; name:string; base_currency:string}[]>([]);
  const [portfolioId, setPortfolioId] = useState('');
  const [quantity, setQuantity] = useState('1');
  const [entry, setEntry] = useState('');
  const [invalidation, setInvalidation] = useState('');
  const [result, setResult] = useState<{delta_heat:string|null; delta_gross_exposure:string|null;
    after:{positions:{symbol:string; atr14:number|null; drawdown:number|null;
      risk_to_invalidation:string|null; current_r:string|null; freshness:string}[]}}|null>(null);
  const [error, setError] = useState<string|null>(null);
  useEffect(() => { getJson<{items:typeof portfolios}>('risk/portfolios').then((response) => {
    const items = Array.isArray(response.items) ? response.items : [];
    setPortfolios(items); setPortfolioId(items[0]?.portfolio_id ?? '');
  }).catch((problem) => setError(errorCode(problem))); }, []);
  const compare = async () => {
    setError(null);
    try {
      const response = await postJson<typeof result>(`risk/theses/${thesis.thesis_id}/risk`, {
        portfolio_id: portfolioId, risk: {manifest_id:context.source_manifest_id, as_of:context.as_of},
        quantity, reference_price:entry, invalidation_price:invalidation || null });
      setResult(response);
    } catch (problem) { setError(errorCode(problem)); }
  };
  const added = result?.after.positions.at(-1);
  return <div><h3 className="op-subhead">Deterministic thesis risk · hypothetical</h3>
    <p className="muted small">Quantity and entry are explicit research assumptions. The backend uses the stored invalidation condition where it defines a price; otherwise enter one below. No position is added.</p>
    {portfolios.length ? <div className="op-controls"><select className="select" aria-label="Risk portfolio" value={portfolioId} onChange={(e) => setPortfolioId(e.target.value)}>{portfolios.map((item) => <option key={item.portfolio_id} value={item.portfolio_id}>{item.name} · {item.base_currency}</option>)}</select>
      <input className="input" aria-label="Risk quantity" type="number" min="0" step="any" value={quantity} onChange={(e) => setQuantity(e.target.value)} />
      <input className="input" aria-label="Risk reference price" type="number" min="0" step="any" placeholder="Entry/reference USDT" value={entry} onChange={(e) => setEntry(e.target.value)} />
      <input className="input" aria-label="Risk invalidation price" type="number" min="0" step="any" placeholder="Optional invalidation USDT" value={invalidation} onChange={(e) => setInvalidation(e.target.value)} />
      <button className="button" disabled={!portfolioId || !entry || !quantity} onClick={compare}>Compare risk</button></div> :
      <p className="muted small">Create a local portfolio in Portfolio &amp; Risk to compare incremental heat and exposure.</p>}
    {error && <div className="callout error">{error}</div>}
    {result && <div className="callout">Exposure change {result.delta_gross_exposure == null ? 'unavailable' : number(Number(result.delta_gross_exposure),2)} USDT · heat change {result.delta_heat == null ? 'unknown' : number(Number(result.delta_heat),2)} USDT. {added?.symbol} ATR14 {added?.atr14 == null ? 'unavailable' : number(added.atr14,2)} · drawdown {added?.drawdown == null ? 'unavailable' : `${number(added.drawdown*100,2)}%`} · current R {added?.current_r ?? 'unavailable'} · {added?.freshness}. This is not a trade size.</div>}
  </div>;
}

export default function OpportunityPane({ context, mode, watchlistIds }: {
  context: Context; mode: Mode; watchlistIds: string[]
}) {
  const [tab, setTab] = useState<'scanner' | 'theses' | 'ledger'>('scanner');
  const [definitions, setDefinitions] = useState<Detector[]>([]);
  const [scan, setScan] = useState<Scan | null>(null);
  const [theses, setTheses] = useState<Thesis[]>([]);
  const [ledger, setLedger] = useState<Candidate[]>([]);
  const [candidate, setCandidate] = useState<Candidate | null>(null);
  const [thesis, setThesis] = useState<Thesis | null>(null);
  const [chart, setChart] = useState<InstrumentView | null>(null);
  const [detector, setDetector] = useState('all');
  const [symbol, setSymbol] = useState('all');
  const [outcome, setOutcome] = useState('all');
  const [status, setStatus] = useState('all');
  const [strength, setStrength] = useState('all');
  const [freshness, setFreshness] = useState('all');
  const [regimeFilter, setRegimeFilter] = useState('all');
  const [conflictFilter, setConflictFilter] = useState('all');
  const [sortBy, setSortBy] = useState('symbol');
  const [watchOnly, setWatchOnly] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [review, setReview] = useState<string | null>(null);
  const [ownerReason, setOwnerReason] = useState('');
  const [ownerStatus, setOwnerStatus] = useState('WATCHING');

  const loadLists = useCallback(async () => {
    const [saved, rejected] = await Promise.all([
      getJson<{ items: Thesis[] }>('opportunities/theses'),
      getJson<{ items: Candidate[] }>('opportunities/candidates', new URLSearchParams({ limit: '100' }))]);
    setTheses(saved.items); setLedger(rejected.items.filter((item) => item.outcome !== 'candidate'));
  }, []);
  const runScan = useCallback(async (record = false) => {
    setBusy(true); setError(null);
    try {
      const result = await postJson<Scan>('opportunities/scan', {
        mode, manifest_id: context.source_manifest_id, as_of: context.as_of,
        symbol: symbol === 'all' ? undefined : symbol,
        detector_id: detector === 'all' ? undefined : detector, record });
      setScan(result);
      if (record) await loadLists();
    } catch (problem) { setError(errorCode(problem)); }
    finally { setBusy(false); }
  }, [context, mode, symbol, detector, loadLists]);

  useEffect(() => {
    let active = true;
    getJson<{ items: Detector[] }>('opportunities/detectors')
      .then((value) => { if (active) setDefinitions(value.items); })
      .catch((problem) => { if (active) setError(errorCode(problem)); });
    loadLists().catch((problem) => { if (active) setError(errorCode(problem)); });
    return () => { active = false; };
  }, [loadLists]);
  useEffect(() => { void runScan(false); }, [runScan]);
  useEffect(() => {
    if (!candidate || !candidate.event_date) { setChart(null); return; }
    let active = true;
    const from = new Date(`${candidate.event_date}T00:00:00Z`);
    from.setUTCDate(from.getUTCDate() - 180);
    const params = appendParams(new URLSearchParams({ manifest_id: candidate.source_manifest_id,
      as_of: candidate.as_of }), { from: from.toISOString().slice(0, 10), to: candidate.event_date });
    getJson<InstrumentView>(`workstation/instrument/${candidate.instrument_id}`, params)
      .then((value) => { if (active) setChart(value); }).catch(() => { if (active) setChart(null); });
    return () => { active = false; };
  }, [candidate]);
  useEffect(() => { if (candidate && tab === 'scanner') document.getElementById('op-candidate-detail')?.scrollIntoView?.({ behavior: 'smooth', block: 'start' }); }, [candidate, tab]);
  useEffect(() => { if (thesis && tab === 'theses') document.getElementById('op-thesis-detail')?.scrollIntoView?.({ behavior: 'smooth', block: 'start' }); }, [thesis, tab]);

  const visible = useMemo(() => (scan?.candidates ?? []).filter((item) =>
    (outcome === 'all' || item.outcome === outcome) && (status === 'all' || item.status === status) &&
    (strength === 'all' || item.detector_strength === strength) &&
    (freshness === 'all' || item.freshness === freshness) &&
    (regimeFilter === 'all' || item.market_regime === regimeFilter) &&
    (conflictFilter === 'all' || (conflictFilter === 'present') === (item.contradictions.length > 0)) &&
    (!watchOnly || watchlistIds.includes(item.instrument_id))).sort((left, right) =>
    sortBy === 'contradictions' ? right.contradictions.length - left.contradictions.length :
    sortBy === 'status' ? STATUS_ORDER.indexOf(left.status) - STATUS_ORDER.indexOf(right.status) :
    String(left[sortBy as 'symbol' | 'detector_id' | 'detector_strength' | 'freshness' | 'market_regime'] ?? '')
      .localeCompare(String(right[sortBy as 'symbol' | 'detector_id' | 'detector_strength' | 'freshness' | 'market_regime'] ?? ''))),
    [scan, outcome, status, strength, freshness, regimeFilter, conflictFilter, sortBy, watchOnly, watchlistIds]);
  const groupedTheses = useMemo(() => STATUS_ORDER.map((name) => ({ name,
    items: theses.filter((item) => item.status === name) })).filter((item) => item.items.length), [theses]);
  const selectedDefinition = definitions.find((item) => item.detector_id === candidate?.detector_id);
  const createThesis = async () => {
    if (!candidate || busy) return;
    setBusy(true); setError(null);
    try {
      let created: Thesis;
      try {
        created = await postJson<Thesis>('opportunities/theses', { candidate_id: candidate.candidate_id });
      } catch (problem) {
        if (!(problem instanceof ApiError) || problem.code !== 'CANDIDATE_NOT_FOUND') throw problem;
        const recorded = await postJson<Scan>('opportunities/scan', { mode: 'pinned',
          manifest_id: candidate.source_manifest_id, as_of: candidate.as_of,
          symbol: candidate.symbol, detector_id: candidate.detector_id, record: true });
        if (!recorded.candidates.some((item) => item.candidate_id === candidate.candidate_id))
          throw new ApiError('CANDIDATE_CONTEXT_CHANGED', 409);
        created = await postJson<Thesis>('opportunities/theses', { candidate_id: candidate.candidate_id });
      }
      setThesis(created); setTab('theses'); await loadLists();
    } catch (problem) { setError(errorCode(problem)); }
    finally { setBusy(false); }
  };
  const monitor = async () => {
    if (!thesis || busy) return;
    setBusy(true); setError(null);
    try {
      const updated = await postJson<Thesis>(`opportunities/theses/${thesis.thesis_id}/monitor`,
        { mode, manifest_id: context.source_manifest_id, as_of: context.as_of });
      setThesis(updated); await loadLists();
    } catch (problem) { setError(errorCode(problem)); }
    finally { setBusy(false); }
  };
  const reviewThesis = async () => {
    if (!thesis || busy) return;
    setBusy(true); setError(null); setReview(null);
    try {
      const result = await postJson<{ review_status: string; thesis: Thesis; run: { answer: string } }>(
        `opportunities/theses/${thesis.thesis_id}/review`, {});
      setThesis(result.thesis); setReview(`${result.review_status}\n\n${result.run.answer}`); await loadLists();
    } catch (problem) { setError(errorCode(problem)); }
    finally { setBusy(false); }
  };
  const decide = async () => {
    if (!thesis || busy || ownerReason.trim().length < 8) return;
    setBusy(true); setError(null);
    try {
      const updated = await postJson<Thesis>(`opportunities/theses/${thesis.thesis_id}/decision`,
        { status: ownerStatus, reason: ownerReason.trim() });
      setThesis(updated); setOwnerReason(''); await loadLists();
    } catch (problem) { setError(errorCode(problem)); }
    finally { setBusy(false); }
  };

  return <div className="stack opportunity-page">
    <div className="page-head"><div><div className="eyebrow">MARKET CORTEX / STRUCTURED RESEARCH</div>
      <h1>Opportunities &amp; Theses</h1><p>Deterministic daily-bar situations across Binance Pilot 5. Research only; no orders, win probabilities or execution.</p></div>
      <div className="head-meta">PINNED EVIDENCE<strong>{shortId(context.source_manifest_id)}</strong></div></div>
    <div className="pillbar">{(['scanner', 'theses', 'ledger'] as const).map((item) =>
      <button key={item} className={tab === item ? 'active' : ''} onClick={() => setTab(item)}>
        {item === 'ledger' ? 'Rejection ledger' : item === 'theses' ? `Thesis board · ${theses.length}` : 'Scanner'}</button>)}</div>
    {error && <div className="callout error"><strong>{error}</strong> · The current context could not be evaluated.</div>}
    {tab === 'scanner' && <>
      <section className="panel"><div className="panel-head"><h2>Scanner controls</h2><span className="sub">{mode} · {context.as_of}</span></div>
        <div className="panel-body"><div className="op-controls">
          <label className="field">Detector<select className="select" aria-label="Detector" value={detector} onChange={(e) => setDetector(e.target.value)}><option value="all">All enabled</option>
            {definitions.filter((item) => item.enabled).map((item) => <option key={item.detector_id} value={item.detector_id}>{category(item.detector_id)}</option>)}</select></label>
          <label className="field">Instrument<select className="select" aria-label="Instrument" value={symbol} onChange={(e) => setSymbol(e.target.value)}><option value="all">Pilot 5</option>
            {context.members.map((item) => <option key={item.symbol} value={item.symbol}>{item.symbol}</option>)}</select></label>
          <button className="button primary" disabled={busy} onClick={() => void runScan(false)}>{busy ? 'Scanning…' : 'Run scan'}</button>
          <button className="button" disabled={busy} onClick={() => void runScan(true)}>Run &amp; record ledger</button>
        </div><p className="panel-caption">Scans are ephemeral until recorded. Recording deduplicates candidate and rejection events by their evidence state.</p></div></section>
      {scan && <><div className="grid four"><div className="metric"><div className="metric-label">Candidate outcomes</div><div className="metric-value">{scan.counts.candidate}</div><div className="metric-foot">Includes WATCHING and incomplete confirmation</div></div>
        <div className="metric"><div className="metric-label">Rejected / NO_EDGE</div><div className="metric-value">{scan.counts.rejected}</div><div className="metric-foot">Rules stayed fixed</div></div>
        <div className="metric"><div className="metric-label">Insufficient</div><div className="metric-value">{scan.counts.insufficient_data}</div><div className="metric-foot">Missing history or features</div></div>
        <div className="metric"><div className="metric-label">Scan time</div><div className="metric-value small-value">{number(scan.elapsed_ms, 0)} ms</div><div className="metric-foot">{scan.recorded_events} new ledger events</div></div></div>
        <section className="panel"><div className="panel-head"><h2>Detector results</h2><span className="sub">{visible.length} shown of {scan.candidates.length}</span></div><div className="panel-body">
          <div className="op-filters"><select className="select" aria-label="Outcome filter" value={outcome} onChange={(e) => setOutcome(e.target.value)}><option value="all">All outcomes</option><option value="candidate">Candidates</option><option value="rejected">Rejected</option><option value="insufficient_data">Insufficient</option></select>
            <select className="select" aria-label="Status filter" value={status} onChange={(e) => setStatus(e.target.value)}><option value="all">All statuses</option>{['WATCHING','DEVELOPING','AWAITING_CONFIRMATION','VALID','NO_EDGE','AVOID','INVALIDATED'].map((item) => <option key={item}>{item}</option>)}</select>
            <select className="select" aria-label="Strength filter" value={strength} onChange={(e) => setStrength(e.target.value)}><option value="all">All strengths</option>{['weak','moderate','strong'].map((item) => <option key={item}>{item}</option>)}</select>
            <select className="select" aria-label="Freshness filter" value={freshness} onChange={(e) => setFreshness(e.target.value)}><option value="all">All freshness</option>{[...new Set(scan.candidates.map((item) => item.freshness))].map((item) => <option key={item}>{item}</option>)}</select>
            <select className="select" aria-label="Market-state filter" value={regimeFilter} onChange={(e) => setRegimeFilter(e.target.value)}><option value="all">All regimes</option>{[...new Set(scan.candidates.map((item) => item.market_regime).filter(Boolean))].map((item) => <option key={item} value={item!}>{category(item!)}</option>)}</select>
            <select className="select" aria-label="Contradiction filter" value={conflictFilter} onChange={(e) => setConflictFilter(e.target.value)}><option value="all">All contradictions</option><option value="present">With contradictions</option><option value="none">No contradictions</option></select>
            <select className="select" aria-label="Sort results" value={sortBy} onChange={(e) => setSortBy(e.target.value)}><option value="symbol">Instrument</option><option value="detector_id">Detector</option><option value="status">Status</option><option value="detector_strength">Strength</option><option value="freshness">Freshness</option><option value="market_regime">Regime</option><option value="contradictions">Most contradictions</option></select>
            <label className="row small"><input type="checkbox" checked={watchOnly} onChange={(e) => setWatchOnly(e.target.checked)} /> Watchlist only</label></div>
        </div><div className="table-wrap"><table><thead><tr><th>Instrument</th><th>Detector</th><th>Outcome</th><th>Status</th><th>Strength</th><th>Freshness</th><th>Regime</th><th>Conflict</th><th></th></tr></thead><tbody>{visible.map((item) =>
          <tr key={item.candidate_id}><td className="symbol">{item.symbol}{watchlistIds.includes(item.instrument_id) && <small>★ WATCHLIST</small>}</td>
            <td>{category(item.detector_id)}</td><td><span className={`badge ${statusTone(item.outcome)}`}>{category(item.outcome)}</span></td>
            <td><span className={`badge ${statusTone(item.status)}`}>{category(item.status)}</span></td>
            <td>{item.detector_strength}</td><td>{item.freshness}</td><td>{category(item.market_regime ?? 'unavailable')}</td>
            <td>{item.contradictions.length}</td><td><button className="button" onClick={() => setCandidate(item)}>Inspect</button></td></tr>)}</tbody></table>
          {!visible.length && <div className="empty"><strong>No qualifying opportunity in this filter</strong><span>Rejections and missing data remain available in the ledger.</span></div>}</div></section></>}
      {candidate && <section className="panel" id="op-candidate-detail"><div className="panel-head"><div><h2>{candidate.symbol} · {category(candidate.detector_id)}</h2><span className="sub">{selectedDefinition?.description ?? 'Versioned daily-bar detector'}</span></div>
        <button className="button" onClick={() => setCandidate(null)}>Close</button></div><div className="panel-body stack">
        <div className="row wrap"><span className={`badge ${statusTone(candidate.status)}`}>{category(candidate.status)}</span><span className="badge">{candidate.detector_strength} evidence</span>
          <span className="badge">{candidate.bias} bias</span><span className="badge">{candidate.market_regime ?? 'regime unavailable'}</span>
          <span className="badge">{candidate.freshness}</span></div>
        <div className="callout">Detected {candidate.event_date ?? 'unknown'} · detector v{candidate.detector_version} · manifest {shortId(candidate.source_manifest_id)} · as of {candidate.as_of} · source quality {candidate.data_quality} · coverage {(candidate.coverage * 100).toFixed(0)}%.</div>
        {candidate.rejection_reasons.length > 0 && <div className="callout warn"><strong>Rejection / no edge</strong><p>{candidate.rejection_reasons.join('; ')}</p></div>}
        {candidate.contradictions.length > 0 && <div className="callout warn"><strong>Contradictions</strong><p>{candidate.contradictions.join('; ')}</p></div>}
        <div className="grid two"><ConditionList title="Triggers" rows={candidate.trigger_conditions} /><ConditionList title="Confirmation needed" rows={candidate.confirmation_conditions} />
          <ConditionList title="Research invalidation" rows={candidate.invalidation_conditions} /><ConditionList title="Rejection rules" rows={candidate.rejection_conditions} /></div>
        <div><h3 className="op-subhead">Evidence &amp; lineage</h3><div className="table-wrap"><table><thead><tr><th>Metric</th><th>Value</th><th>Unit</th><th>Feature / comparison ref</th><th>Coverage</th><th>Reason</th></tr></thead><tbody>
          {candidate.evidence.map((item) => <tr key={item.evidence_id}><td>{item.metric}</td><td className="numeric">{observed(item.value)}</td><td>{item.unit ?? '—'}</td><td className="mono">{shortId(item.source_id)}</td>
            <td>{item.coverage == null ? '—' : `${(item.coverage*100).toFixed(0)}%`}</td><td>{item.reason ?? '—'}</td></tr>)}</tbody></table></div></div>
        {chart && <div><h3 className="op-subhead">Stored daily bars · candidate session {candidate.event_date}</h3><PriceChart bars={chart.bars} features={chart.features} /></div>}
        <div className="row wrap"><button className="button primary" disabled={busy} onClick={createThesis}>Record &amp; create thesis</button>
          <span className="subtle">A thesis preserves this exact candidate, manifest and cutoff.</span></div>
      </div></section>}</>}
    {tab === 'ledger' && <section className="panel"><div className="panel-head"><h2>Rejection / no-edge ledger</h2><span className="sub">Recorded local events, including insufficient evidence</span></div>
      <div className="table-wrap"><table><thead><tr><th>Instrument</th><th>Detector</th><th>Outcome</th><th>Reason</th><th>Manifest</th><th>As of</th><th></th></tr></thead><tbody>{ledger.map((item) =>
        <tr key={item.candidate_id}><td className="symbol">{item.symbol}</td><td>{category(item.detector_id)}</td><td><span className={`badge ${statusTone(item.outcome)}`}>{category(item.outcome)}</span></td>
          <td>{item.rejection_reasons.join('; ') || item.contradictions.join('; ') || 'Evidence unavailable'}</td><td className="mono">{shortId(item.source_manifest_id)}</td><td>{item.as_of.slice(0,16)}</td>
          <td><button className="button" onClick={() => { setCandidate(item); setTab('scanner'); }}>Inspect</button></td></tr>)}</tbody></table>
        {!ledger.length && <div className="empty"><strong>No recorded rejections yet</strong><span>Run and record a scan to seed the ledger.</span></div>}</div></section>}
    {tab === 'theses' && <><section className="panel"><div className="panel-head"><h2>Structured thesis board</h2><span className="sub">{theses.length} local theses · statuses are deterministic or owner decisions</span></div>
      {groupedTheses.map((group) => <div key={group.name} className="op-thesis-group"><h3 className="op-subhead">{category(group.name)} · {group.items.length}</h3><div className="table-wrap"><table><thead><tr><th>Instrument</th><th>Detector</th><th>Status</th><th>Version</th><th>Manifest</th><th>Changed</th><th></th></tr></thead><tbody>{group.items.map((item) =>
        <tr key={item.thesis_id}><td className="symbol">{item.symbol}</td><td>{category(item.detector_id)}</td><td><span className={`badge ${statusTone(item.status)}`}>{category(item.status)}</span></td>
          <td>v{item.version}</td><td className="mono">{shortId(item.source_manifest_id)}</td><td>{item.updated_at.slice(0,16)}</td>
          <td><button className="button" onClick={() => { setThesis(item); setReview(null); }}>Open</button></td></tr>)}</tbody></table></div></div>)}
        {!theses.length && <div className="empty"><strong>No theses yet</strong><span>Open a scanner result and create one from recorded evidence.</span></div>}</section>
      {thesis && <section className="panel" id="op-thesis-detail"><div className="panel-head"><div><h2>{thesis.symbol} · {category(thesis.detector_id)} · v{thesis.version}</h2><span className="sub">{thesis.statement}</span></div><button className="button" onClick={() => setThesis(null)}>Close</button></div>
        <div className="panel-body stack"><div className="row wrap"><span className={`badge ${statusTone(thesis.status)}`}>{category(thesis.status)}</span>
          <span className="badge">{thesis.candidate_ids.length} candidate version(s)</span><span className="badge">{thesis.cortex_run_ids.length} CORTEX review(s)</span></div>
          <div className="callout">Manifest {shortId(thesis.source_manifest_id)} · as of {thesis.as_of} · thesis ID {thesis.thesis_id} · research horizon {thesis.candidate.horizon}.</div>
          <div className="row wrap"><button className="button primary" disabled={busy} onClick={monitor}>Re-evaluate in selected context</button>
            <button className="button" disabled={busy} onClick={reviewThesis}>CORTEX evidence review</button></div>
          {review && <div className="callout op-review">{review}</div>}
          <div className="grid two"><ConditionList title="Confirmation" rows={thesis.confirmation_conditions} /><ConditionList title="Invalidation" rows={thesis.invalidation_conditions} /></div>
          <ThesisRiskPanel thesis={thesis} context={context} />
          <div className="grid two"><div><h3 className="op-subhead">Risk / contradictions</h3>{thesis.risk_factors.map((item) => <div className="data-row" key={item}>{item}</div>)}</div>
            <div><h3 className="op-subhead">Data limitations</h3>{thesis.data_limitations.map((item) => <div className="data-row" key={item}>{item}</div>)}</div></div>
          <div><h3 className="op-subhead">Owner decision · audited</h3><div className="op-controls"><select className="select" aria-label="Owner status" value={ownerStatus} onChange={(e) => setOwnerStatus(e.target.value)}>
            {['WATCHING','NO_EDGE','EVENT_RISK','AVOID'].map((item) => <option key={item}>{item}</option>)}</select>
            <input className="input" aria-label="Decision reason" placeholder="Reason (at least 8 characters)" value={ownerReason} onChange={(e) => setOwnerReason(e.target.value)} />
            <button className="button" disabled={busy || ownerReason.trim().length < 8} onClick={decide}>Record decision</button></div></div>
          <div><h3 className="op-subhead">Version history</h3><div className="data-list">{thesis.transitions.map((item, index) =>
            <div className="data-row" key={`${index}:${item.at}`}><span className="label">{item.actor} · {item.from_status ?? 'NEW'} → {item.to_status} · {item.reason}</span>
              <span className="value">{item.at.slice(0,16)} · {shortId(item.source_manifest_id)}</span></div>)}</div></div>
        </div></section>}</>}
    <p className="panel-caption">Deferred detectors: {definitions.filter((item) => !item.enabled).map((item) =>
      `${category(item.detector_id)} (${item.unsupported_reason})`).join(' · ')}.</p>
  </div>;
}
