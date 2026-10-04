'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';
import { Activity, ArrowDownRight, ArrowUpRight, BarChart3, BookOpenText, Check,
  ChevronRight, CircleHelp, Command, Database, FileClock, Gauge, HeartPulse,
  LayoutDashboard, Lightbulb, ListFilter, RefreshCw, Search, Settings2, ShieldCheck,
  Star, Table2, X } from 'lucide-react';
import { PriceChart, SeriesChart } from './charts';
import CortexPane from './CortexPane';
import OpportunityPane from './OpportunityPane';
import PortfolioPane from './PortfolioPane';
import LearningPane from './LearningPane';
import QuantPane from './QuantPane';
import { ApiError, appendParams, category, contextParams, getJson, number, percent, pinnedParams, shortId,
  type ChartFeature, type Comparison, type Context, type Dimension, type FeatureDefinition, type FeatureSeries,
  type InstrumentView, type ManifestDetail, type MarketState, type Mode, type Overview, type OverviewItem,
  type ResearchSelection } from '@/lib/api';

type View = 'overview' | 'instruments' | 'analytics' | 'market-state' | 'compare' | 'coverage' | 'research' | 'system' | 'cortex' | 'opportunities' | 'portfolio' | 'learning' | 'quant';
const NAV: { id: View; label: string; icon: typeof LayoutDashboard; key: string }[] = [
  { id: 'overview', label: 'Overview', icon: LayoutDashboard, key: '1' },
  { id: 'instruments', label: 'Instruments', icon: BarChart3, key: '2' },
  { id: 'analytics', label: 'Feature Explorer', icon: ListFilter, key: '3' },
  { id: 'market-state', label: 'Market State', icon: Gauge, key: '4' },
  { id: 'compare', label: 'Compare & Breadth', icon: Table2, key: '5' },
  { id: 'coverage', label: 'Data & Coverage', icon: Database, key: '6' },
  { id: 'research', label: 'Research Desk', icon: BookOpenText, key: '7' },
  { id: 'system', label: 'System & Lineage', icon: Settings2, key: '8' },
  { id: 'cortex', label: 'CORTEX Research', icon: HeartPulse, key: '9' },
  { id: 'opportunities', label: 'Opportunities', icon: Lightbulb, key: '0' },
  { id: 'portfolio', label: 'Portfolio & Risk', icon: ShieldCheck, key: 'p' },
  { id: 'learning', label: 'Journal & Learning', icon: FileClock, key: 'j' },
  { id: 'quant', label: 'Quant Lab', icon: Activity, key: 'q' }
];
type Watchlist = { id: string; name: string; instrumentIds: string[] };
type WatchSignal = { symbol: string; detector_id: string; status: string; outcome?: string;
  source_manifest_id: string; as_of: string; updated_at?: string };
const WATCH_KEY = 'market-cortex.watchlists.v1';
const PREF_KEY = 'market-cortex.preferences.v1';
const UTC = 'en-GB';

function tone(value: string | null | undefined): 'good' | 'bad' | 'warn' | 'info' | 'pinned' | '' {
  if (!value) return '';
  if (['current', 'available', 'complete', 'up', 'positive', 'broad_positive', 'bounded', 'VALIDATED_PUBLIC', 'ready'].includes(value)) return 'good';
  if (['stale', 'unknown', 'unavailable', 'insufficient', 'DEFERRED_NOT_CONFIGURED', 'partial', 'elevated'].includes(value)) return 'warn';
  if (['down', 'negative', 'database_unavailable', 'BACKEND_UNAVAILABLE'].includes(value)) return 'bad';
  return 'info';
}
function Badge({ value, title }: { value: string | null | undefined; title?: string }) {
  return <span title={title} className={`badge ${tone(value)}`}>{category(value ?? 'unknown')}</span>;
}
function Panel({ title, subtitle, action, children, noPad = false }: {
  title: string; subtitle?: string; action?: React.ReactNode; children: React.ReactNode; noPad?: boolean
}) {
  return <section className={`panel ${noPad ? 'no-pad' : ''}`}><div className="panel-head"><div><h2>{title}</h2>{subtitle && <span className="sub">{subtitle}</span>}</div>{action}</div><div className="panel-body">{children}</div></section>;
}
function Metric({ label, value, foot, className = '' }: { label: string; value: string; foot: string; className?: string }) {
  return <div className="metric"><div className="metric-label">{label}</div><div className={`metric-value ${className}`}>{value}</div><div className="metric-foot">{foot}</div></div>;
}
function Empty({ title, body }: { title: string; body: string }) {
  return <div className="empty"><CircleHelp size={22} /><strong>{title}</strong><span>{body}</span></div>;
}
function Loading({ label = 'Loading pinned research data…' }: { label?: string }) {
  return <div aria-busy="true" className="stack"><div className="callout">{label}</div><div className="grid four">{[1,2,3,4].map((i) =>
    <div className="skeleton" key={i} style={{ height: 112 }} />)}</div><div className="skeleton" style={{ height: 320 }} /></div>;
}
function ErrorPanel({ error, retry }: { error: string; retry: () => void }) {
  const message: Record<string, string> = {
    BACKEND_UNAVAILABLE: 'The local FastAPI service is unavailable. Start it on 127.0.0.1:8765 and retry.',
    DATABASE_NOT_CONFIGURED: 'Set the PostgreSQL connection in the backend process environment.',
    SERVICE_UNAVAILABLE: 'The local catalog or Parquet store could not answer this request.',
    MANIFEST_NOT_FOUND: 'The selected manifest no longer exists in this catalog.',
    OFFSET_REQUIRED: 'Enter a timestamp with a timezone offset.',
    DATASET_EMPTY: 'No committed dataset is available in this catalog.'
  };
  return <div className="callout error"><strong>{category(error)}</strong><p>{message[error] ?? 'This research request could not be completed. The workstation did not substitute zero values.'}</p>
    <button className="button" onClick={retry}><RefreshCw size={14} /> Retry</button></div>;
}
function dateTime(value: string | null | undefined) {
  return value ? new Date(value).toLocaleString(UTC, { timeZone: 'Asia/Kolkata', year: 'numeric', month: 'short', day: '2-digit', hour: '2-digit', minute: '2-digit', hour12: false }) + ' IST' : '—';
}
function localCutoff(value: string): string {
  const parts = new Intl.DateTimeFormat('sv-SE', { timeZone: 'Asia/Kolkata', year: 'numeric', month: '2-digit',
    day: '2-digit', hour: '2-digit', minute: '2-digit', hour12: false }).format(new Date(value));
  return parts;
}
function metricRows(dimension: Dimension) {
  return Object.entries(dimension.metrics).map(([name, value]) => <div className="data-row" key={name}>
    <span className="label">{category(name)}</span><span className="value">{number(value, 4)}</span></div>);
}
function featureCategory(name: string) {
  if (/return|roc/.test(name)) return 'Returns';
  if (/volume/.test(name)) return 'Volume';
  if (/drawdown|peak|recovery/.test(name)) return 'Drawdown';
  if (/rsi|macd/.test(name)) return 'Momentum';
  if (/volatility|atr|true_range|bollinger|rolling_std|high_low_range/.test(name)) return 'Volatility';
  return 'Trend';
}
function signed(value: number | null | undefined) { return value == null ? '' : value >= 0 ? 'positive' : 'negative'; }
function levelPercent(value: number | null | undefined, digits = 1) {
  return value == null ? '—' : `${(value * 100).toFixed(digits)}%`;
}
function latestPoint(feature?: ChartFeature) { return feature?.points.at(-1)?.value ?? null; }

export default function Workstation() {
  const [view, setView] = useState<View>('overview');
  const [selection, setSelection] = useState<ResearchSelection>({ mode: 'latest' });
  const [draft, setDraft] = useState<ResearchSelection>({ mode: 'latest' });
  const [contextOpen, setContextOpen] = useState(false);
  const [context, setContext] = useState<Context | null>(null);
  const [overview, setOverview] = useState<Overview | null>(null);
  const [overviewError, setOverviewError] = useState<string | null>(null);
  const [health, setHealth] = useState<string>('checking');
  const [dataEnvironment, setDataEnvironment] = useState('UNLABELED');
  const [cortexFocus, setCortexFocus] = useState<'instrument' | 'market'>('instrument');
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [refresh, setRefresh] = useState(0);
  const [instrumentId, setInstrumentId] = useState<string | null>(null);
  const [chart, setChart] = useState<InstrumentView | null>(null);
  const [chartError, setChartError] = useState<string | null>(null);
  const [chartLoading, setChartLoading] = useState(false);
  const [range, setRange] = useState('1Y');
  const [customFrom, setCustomFrom] = useState('');
  const [customTo, setCustomTo] = useState('');
  const [definitions, setDefinitions] = useState<FeatureDefinition[]>([]);
  const [featureQuery, setFeatureQuery] = useState('');
  const [featureFilter, setFeatureFilter] = useState('All');
  const [featureName, setFeatureName] = useState('sma');
  const [featurePeriod, setFeaturePeriod] = useState<string>('');
  const [featureSeries, setFeatureSeries] = useState<FeatureSeries | null>(null);
  const [featureError, setFeatureError] = useState<string | null>(null);
  const [featureLoading, setFeatureLoading] = useState(false);
  const [comparison, setComparison] = useState<Comparison | null>(null);
  const [compareError, setCompareError] = useState<string | null>(null);
  const [compareLoading, setCompareLoading] = useState(false);
  const [compareIds, setCompareIds] = useState<string[]>([]);
  const [compareWindow, setCompareWindow] = useState(60);
  const [selectedCell, setSelectedCell] = useState<[number, number]>([0, 1]);
  const [manifest, setManifest] = useState<ManifestDetail | null>(null);
  const [manifestError, setManifestError] = useState<string | null>(null);
  const [commandOpen, setCommandOpen] = useState(false);
  const [commandQuery, setCommandQuery] = useState('');
  const [watchlists, setWatchlists] = useState<Watchlist[]>([]);
  const [activeWatchlist, setActiveWatchlist] = useState<string>('');
  const [watchName, setWatchName] = useState('');
  const [note, setNote] = useState('');
  const [savedNote, setSavedNote] = useState(false);
  const [watchSignals, setWatchSignals] = useState<{ candidates: WatchSignal[]; theses: WatchSignal[] }>({ candidates: [], theses: [] });

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const candidate = params.get('view') as View;
    if (NAV.some((item) => item.id === candidate)) setView(candidate);
    try {
      const stored = JSON.parse(localStorage.getItem(WATCH_KEY) ?? '[]') as Watchlist[];
      if (Array.isArray(stored)) setWatchlists(stored);
      const prefs = JSON.parse(localStorage.getItem(PREF_KEY) ?? '{}') as { instrumentId?: string; range?: string };
      if (prefs.instrumentId) setInstrumentId(prefs.instrumentId);
      if (prefs.range) setRange(prefs.range);
    } catch { /* Local preferences may be absent or corrupt; no market data is affected. */ }
  }, []);
  useEffect(() => { if (instrumentId) localStorage.setItem(PREF_KEY, JSON.stringify({ instrumentId, range })); }, [instrumentId, range]);
  useEffect(() => { localStorage.setItem(WATCH_KEY, JSON.stringify(watchlists)); }, [watchlists]);
  const navigate = useCallback((next: View) => {
    setView(next); window.history.pushState({}, '', next === 'overview' ? '/' : `/?view=${next}`);
  }, []);
  const reload = () => setRefresh((n) => n + 1);
  useEffect(() => {
    let cancelled = false;
    setLoading(true); setError(null); setOverviewError(null); setOverview(null); setContext(null);
    getJson<{ status: string; settings?: { environment?: string } }>('health').then((result) => {
      if (!cancelled) { setHealth(result.status); setDataEnvironment(result.settings?.environment ?? 'UNLABELED'); }
    })
      .catch(() => { if (!cancelled) setHealth('BACKEND_UNAVAILABLE'); });
    getJson<Context>('workstation/context', contextParams(selection)).then(async (ctx) => {
      if (cancelled) return;
      setContext(ctx);
      setInstrumentId((current) => ctx.members.some((member) => member.instrument_id === current) ? current :
        ctx.members.find((member) => member.symbol === 'BTCUSDT')?.instrument_id ?? null);
      setCompareIds(ctx.members.filter((member) => member.instrument_id).map((member) => member.instrument_id!));
    }).catch((problem) => { if (!cancelled) setError(problem instanceof ApiError ? problem.code : 'REQUEST_FAILED'); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [selection, refresh]);

  useEffect(() => {
    if (!context || overview || !['overview','market-state','compare'].includes(view)) return;
    let cancelled = false;
    setOverviewError(null);
    getJson<Overview>('workstation/overview', pinnedParams(context)).then((result) => {
      if (!cancelled) setOverview(result);
    }).catch((problem) => {
      if (!cancelled) setOverviewError(problem instanceof ApiError ? problem.code : 'REQUEST_FAILED');
    });
    return () => { cancelled = true; };
  }, [context, view, overview]);

  useEffect(() => {
    if (!context || !instrumentId || !context.evaluation_date || !context.history_start ||
        (view !== 'instruments' && view !== 'research')) return;
    let cancelled = false;
    setChartLoading(true); setChartError(null); setChart(null);
    const params = appendParams(pinnedParams(context), { from: context.history_start, to: context.evaluation_date });
    getJson<InstrumentView>(`workstation/instrument/${instrumentId}`, params)
      .then((result) => { if (!cancelled) setChart(result); })
      .catch((problem) => { if (!cancelled) setChartError(problem instanceof ApiError ? problem.code : 'REQUEST_FAILED'); })
      .finally(() => { if (!cancelled) setChartLoading(false); });
    return () => { cancelled = true; };
  }, [context, instrumentId, view]);
  useEffect(() => {
    if (view !== 'analytics') return;
    let cancelled = false;
    getJson<{ items: FeatureDefinition[] }>('features')
      .then((result) => { if (!cancelled) setDefinitions(result.items); })
      .catch(() => { if (!cancelled) setDefinitions([]); });
    return () => { cancelled = true; };
  }, [view]);
  const selectedDefinition = definitions.find((item) => item.name === featureName);
  useEffect(() => {
    if (view !== 'analytics' || !context?.evaluation_date || !context.history_start || !instrumentId) return;
    let cancelled = false;
    setFeatureLoading(true); setFeatureError(null); setFeatureSeries(null);
    const params = appendParams(pinnedParams(context), {
      name: featureName, instrument_id: instrumentId, from: context.history_start, to: context.evaluation_date,
      period: featurePeriod && selectedDefinition?.parameter_defaults.period !== undefined ? featurePeriod : undefined
    });
    getJson<FeatureSeries>('features/series', params)
      .then((result) => { if (!cancelled) setFeatureSeries(result); })
      .catch((problem) => { if (!cancelled) setFeatureError(problem instanceof ApiError ? problem.code : 'REQUEST_FAILED'); })
      .finally(() => { if (!cancelled) setFeatureLoading(false); });
    return () => { cancelled = true; };
  }, [view, context, instrumentId, featureName, featurePeriod, selectedDefinition?.parameter_defaults.period]);
  useEffect(() => {
    if (view !== 'compare' || !context?.evaluation_date || !context.history_start || compareIds.length < 2) return;
    let cancelled = false;
    setCompareLoading(true); setCompareError(null); setComparison(null);
    const params = appendParams(pinnedParams(context), { from: context.history_start,
      to: context.evaluation_date, window: compareWindow });
    compareIds.forEach((id) => params.append('instrument_ids', id));
    getJson<Comparison>('workstation/comparison', params)
      .then((result) => { if (!cancelled) setComparison(result); })
      .catch((problem) => { if (!cancelled) setCompareError(problem instanceof ApiError ? problem.code : 'REQUEST_FAILED'); })
      .finally(() => { if (!cancelled) setCompareLoading(false); });
    return () => { cancelled = true; };
  }, [view, context, compareIds, compareWindow]);
  useEffect(() => {
    if (view !== 'system' || !context) return;
    let cancelled = false;
    setManifest(null); setManifestError(null);
    getJson<ManifestDetail>(`workstation/manifest/${context.source_manifest_id}`)
      .then((result) => { if (!cancelled) setManifest(result); })
      .catch((problem) => { if (!cancelled) setManifestError(problem instanceof ApiError ? problem.code : 'REQUEST_FAILED'); });
    return () => { cancelled = true; };
  }, [view, context]);
  const noteContext = selection.mode === 'latest' ? 'latest' : selection.mode === 'pinned' ?
    context?.source_manifest_id : `${context?.source_manifest_id}.${context?.as_of}`;
  const noteKey = context && instrumentId ? `market-cortex.note.v1.${instrumentId}.${noteContext}` : null;
  useEffect(() => { if (view === 'research' && noteKey) { setNote(localStorage.getItem(noteKey) ?? ''); setSavedNote(false); } }, [view, noteKey]);
  useEffect(() => {
    if (view !== 'research' || !context) return;
    let active = true;
    Promise.all([getJson<{ items: WatchSignal[] }>('opportunities/candidates', new URLSearchParams({ limit: '200' })),
      getJson<{ items: WatchSignal[] }>('opportunities/theses', new URLSearchParams({ limit: '200' }))])
      .then(([candidates, theses]) => { if (active) setWatchSignals({ candidates: candidates.items ?? [], theses: theses.items ?? [] }); })
      .catch(() => { if (active) setWatchSignals({ candidates: [], theses: [] }); });
    return () => { active = false; };
  }, [view, context]);
  useEffect(() => {
    const handle = (event: KeyboardEvent) => {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'k') { event.preventDefault(); setCommandOpen(true); }
      if (event.key === 'Escape') setCommandOpen(false);
    };
    window.addEventListener('keydown', handle); return () => window.removeEventListener('keydown', handle);
  }, []);

  const state = overview?.state ?? null;
  const dimension = (name: string) => state?.dimensions.find((item) => item.name === name);
  const selectedMember = context?.members.find((item) => item.instrument_id === instrumentId) ?? null;
  const freshness = dimension('data_freshness')?.category ?? 'unknown';
  const available = context?.members.filter((item) => item.instrument_id) ?? [];
  const visibleBars = chart?.bars ?? [];
  const viewRange = useMemo(() => {
    if (!visibleBars.length) return { from: undefined, to: undefined };
    if (range === 'Custom') return { from: customFrom || visibleBars[0].session_date,
      to: customTo || visibleBars.at(-1)!.session_date };
    const count: Record<string, number> = { '1M': 30, '3M': 90, '6M': 180, '1Y': 365, '2Y': 730, Max: visibleBars.length };
    return { from: visibleBars[Math.max(0, visibleBars.length - (count[range] ?? visibleBars.length))].session_date,
      to: visibleBars.at(-1)!.session_date };
  }, [visibleBars, range, customFrom, customTo]);
  const openInstrument = (id: string) => { setInstrumentId(id); navigate('instruments'); };
  const applyContext = () => {
    if (draft.mode === 'historical') {
      if (!draft.asOf) { setError('HISTORICAL_CUTOFF_REQUIRED'); return; }
      if (!/^\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}$/.test(draft.asOf)) { setError('INVALID_AS_OF'); return; }
      const parsed = new Date(`${draft.asOf.replace(' ', 'T')}:00+05:30`);
      if (Number.isNaN(parsed.getTime())) { setError('INVALID_AS_OF'); return; }
      setSelection({ ...draft, asOf: parsed.toISOString() });
    } else setSelection({ mode: draft.mode, manifestId: draft.mode === 'pinned' ? draft.manifestId : undefined });
    setContextOpen(false); setError(null);
  };
  const updateWatchlists = (next: Watchlist[]) => setWatchlists(next);
  const currentWatchlist = watchlists.find((item) => item.id === activeWatchlist) ?? watchlists[0];
  const addWatchlist = () => {
    const name = watchName.trim(); if (!name) return;
    const next = { id: crypto.randomUUID(), name, instrumentIds: [] };
    updateWatchlists([...watchlists, next]); setActiveWatchlist(next.id); setWatchName('');
  };
  const toggleWatchMember = (id: string) => {
    if (!currentWatchlist) return;
    updateWatchlists(watchlists.map((item) => item.id === currentWatchlist.id ? { ...item,
      instrumentIds: item.instrumentIds.includes(id) ? item.instrumentIds.filter((member) => member !== id)
        : [...item.instrumentIds, id] } : item));
  };
  const saveNote = () => { if (!noteKey) return; localStorage.setItem(noteKey, note); setSavedNote(true); };

  function instrumentSelector() {
    return <select aria-label="Select instrument" className="select" value={instrumentId ?? ''}
      onChange={(event) => setInstrumentId(event.target.value)}>{available.map((item) =>
        <option key={item.instrument_id} value={item.instrument_id!}>{item.symbol} · {item.currency}</option>)}</select>;
  }
  function header(title: string, description: string, right?: React.ReactNode) {
    return <div className="page-head"><div><div className="eyebrow">MARKET CORTEX / {context?.universe_label ?? 'Research'}</div>
      <h1>{title}</h1><p>{description}</p></div>{right}</div>;
  }
  function stateCard(item: Dimension, detailed = false) {
    return <div className="state-card" key={item.name}><div className="row between"><span className="title">{category(item.name)}</span><Badge value={item.freshness} /></div>
      <div className="category">{category(item.category)}</div>
      <div className="details">{item.scope} · {item.eligible_members}/{item.total_members} eligible · {item.timeframe}</div>
      {detailed && <><div className="metrics">{metricRows(item)}</div>
        <div className="micro muted mt12">Rule {item.rule_version} · {shortId(item.source_manifest_id)}</div>
        {item.unknown_reason && <div className="callout warn mt12">{category(item.unknown_reason)}</div>}
        <details className="mt12"><summary className="small">Evidence references ({item.evidence_refs.length})</summary>
          <div className="evidence mt12">{item.evidence_refs.length ? item.evidence_refs.join('\n') : 'No supporting observation'}</div></details></>}</div>;
  }

  function overviewPage() {
    if (!overview) return <Loading />;
    const btc = overview.items.find((item) => item.symbol === 'BTCUSDT');
    return <>{header('Market overview', 'A scoped, deterministic read of the five Binance public daily-bar instruments.',
      <div className="head-meta">EVALUATION SESSION<strong>{context?.evaluation_date ?? 'Unavailable'}</strong></div>)}
      <div className="grid four mb14">
        <Metric label="Pilot universe" value={`${overview.items.length} / 5`} foot="Binance Pilot 5 · daily bars" />
        <Metric label="BTC last close" value={btc?.close == null ? '—' : number(btc.close, 2)} foot={`Native quote · ${btc?.currency ?? 'USDT'} · ${btc?.session_date ?? '—'}`} />
        <Metric label="BTC daily return" value={percent(btc?.features.arithmetic_return?.value)} foot="Backend arithmetic return" className={signed(btc?.features.arithmetic_return?.value)} />
        <Metric label="Regime" value={category(state?.regime.category ?? 'unknown')} foot={`Rules ${state?.regime.rule_version ?? 'unavailable'}`} />
      </div>
      <div className="grid main-side"><div className="stack">
        <Panel title="Pilot universe" subtitle="Native prices · values from Phase 1/2" action={<Badge value={freshness} />} noPad>
          <div className="table-wrap"><table><thead><tr><th>Instrument</th><th className="numeric">Close</th><th className="numeric">1D</th><th className="numeric">20D</th><th className="numeric">RSI 14</th><th className="numeric">Vol 20</th><th>Freshness</th><th></th></tr></thead>
            <tbody>{overview.items.map((item) => <tr key={item.instrument_id} className="clickable" onClick={() => item.instrument_id && openInstrument(item.instrument_id)}>
              <td><span className="symbol">{item.symbol}<small>{item.currency} · {item.venue_id}</small></span></td>
              <td className="numeric">{number(item.close)}</td>
              <td className={`numeric ${signed(item.features.arithmetic_return?.value)}`}>{percent(item.features.arithmetic_return?.value)}</td>
              <td className={`numeric ${signed(item.features.rolling_return?.value)}`}>{percent(item.features.rolling_return?.value)}</td>
              <td className="numeric">{number(item.features.rsi?.value, 1)}</td>
              <td className="numeric">{levelPercent(item.features.annualized_volatility?.value)}</td>
              <td><Badge value={item.freshness} /></td><td><ChevronRight size={14} /></td></tr>)}</tbody></table></div>
        </Panel>
        <Panel title="Research boundary" subtitle="Source and scope"><div className="callout">This is <strong>Binance Pilot 5</strong>, a five-instrument sample. Breadth, correlation and regime labels describe this sample only. Prices remain in their native quote currency; no INR or USD conversion is inferred.</div></Panel>
      </div><div className="stack">
        <Panel title="Market state" subtitle="Rule-based · explainable" action={<button className="button ghost" onClick={() => navigate('market-state')}>Inspect <ChevronRight size={13}/></button>}>
          <div className="data-list">{['trend','momentum','volatility','breadth','relative_strength','correlation_state','uncertainty'].map((name) => {
            const item = dimension(name); return <div className="data-row" key={name}><span className="label">{category(name)}</span><Badge value={item?.category ?? 'unknown'} /></div>;
          })}</div></Panel>
        <Panel title="Dataset context" subtitle="Pinned within this screen"><div className="data-list">
          <div className="data-row"><span className="label">Manifest</span><span className="value" title={context?.source_manifest_id}>{shortId(context?.source_manifest_id)}</span></div>
          <div className="data-row"><span className="label">As-of cutoff</span><span className="value">{dateTime(context?.as_of)}</span></div>
          <div className="data-row"><span className="label">Freshness</span><Badge value={freshness}/></div>
          <div className="data-row"><span className="label">Coverage</span><span className="value">{number(dimension('market_participation')?.metrics.observed_members, 0)} / 5</span></div>
          <div className="data-row"><span className="label">Snapshot</span><span className="value" title={state?.snapshot_id}>{shortId(state?.snapshot_id)}</span></div>
        </div></Panel>
      </div></div></>;
  }

  function instrumentPage(research = false) {
    const last = chart?.bars.at(-1);
    const rangeChoices = ['1M', '3M', '6M', '1Y', '2Y', 'Max', 'Custom'];
    return <>{header(research ? 'Research desk' : 'Instrument workspace',
      research ? 'A context-bound chart and local notes for the selected instrument.' :
        'Real stored OHLC, volume and Phase 2 indicator series. Zoom and inspect without recalculating values in the browser.',
      <div className="row">{instrumentSelector()}<button className="button" onClick={() => { setCortexFocus('instrument'); navigate('cortex'); }}>Ask CORTEX</button></div>)}
      {chartLoading ? <Loading label="Loading immutable bars and backend feature series…" /> : chartError ?
        <ErrorPanel error={chartError} retry={reload} /> : !chart || !chart.bars.length ?
        <Empty title="No visible bars" body="This manifest and cutoff contain no chartable observations for the selected instrument." /> : <>
        <div className="grid four mb14">
          <Metric label="Latest stored close" value={number(last?.close)} foot={`${last?.currency ?? 'native'} · ${last?.session_date ?? '—'}`} />
          <Metric label="RSI 14" value={number(latestPoint(chart.features.rsi_14), 1)} foot="Wilder · backend feature" />
          <Metric label="ATR 14" value={number(latestPoint(chart.features.atr_14))} foot="Quote price units · backend feature" />
          <Metric label="Relative volume" value={number(latestPoint(chart.features.relative_volume_20))} foot="Traded base-asset volume / 20D average" />
        </div>
        <Panel title={`${selectedMember?.symbol ?? 'Instrument'} · Daily OHLC`} subtitle={`${chart.bars.length} visible bars · ${chart.missing_sessions.length} missing expected sessions · ${chart.freshness} freshness`}
          action={<div className="pillbar">{rangeChoices.map((choice) =>
            <button key={choice} className={range === choice ? 'active' : ''} onClick={() => setRange(choice)}
              disabled={choice === '2Y' && chart.bars.length < 730 || choice === '1Y' && chart.bars.length < 365}>{choice}</button>)}</div>}>
          {range === 'Custom' && <div className="row wrap mb14"><label className="small muted">From <input aria-label="Custom start" className="input" type="date" min={chart.bars[0].session_date} max={chart.bars.at(-1)?.session_date} value={customFrom} onChange={(e) => setCustomFrom(e.target.value)} /></label>
            <label className="small muted">To <input aria-label="Custom end" className="input" type="date" min={chart.bars[0].session_date} max={chart.bars.at(-1)?.session_date} value={customTo} onChange={(e) => setCustomTo(e.target.value)} /></label></div>}
          <PriceChart bars={chart.bars} features={chart.features} visibleFrom={viewRange.from} visibleTo={viewRange.to} />
          <div className="row wrap between border-top pad16 small muted"><span>Candles, overlays, RSI and MACD are backend derived. All timestamps are UTC daily sessions.</span>
            <span className="mono">Raw · P1D · {shortId(context?.source_manifest_id)}</span></div>
        </Panel>
        <div className="grid main-side mt18"><Panel title="Indicator readout" subtitle="Backend canonical values · current evaluation session">
          <div className="grid three">{Object.entries(chart.features).filter(([name]) =>
            ['sma_20','sma_50','ema_20','rsi_14','macd_histogram','atr_14','annualized_volatility_20','relative_volume_20','drawdown'].includes(name)).map(([name, item]) =>
              <div className="state-card" key={name}><div className="title">{category(name)}</div>
                <div className="category mono" style={{ fontSize: 18 }}>{item.points.at(-1)?.value == null ? '—' :
                  item.unit.includes('fraction') ? item.unit === 'annual_fraction' ? levelPercent(item.points.at(-1)?.value) : percent(item.points.at(-1)?.value) : number(item.points.at(-1)?.value, 3)}</div>
                <div className="details">{item.unit} · {item.version} · {item.points.at(-1)?.reason ?? item.freshness}</div>
              </div>)}</div></Panel>
          <Panel title="Observation provenance" subtitle="Inspect the source behind the final candle"><div className="data-list">
            <div className="data-row"><span className="label">Observation</span><span className="value" title={last?.observation_id}>{shortId(last?.observation_id)}</span></div>
            <div className="data-row"><span className="label">Source batch</span><span className="value" title={last?.source_batch_id}>{shortId(last?.source_batch_id)}</span></div>
            <div className="data-row"><span className="label">Available at</span><span className="value">{dateTime(last?.available_at)}</span></div>
            <div className="data-row"><span className="label">Quality</span><Badge value={last?.quality}/></div>
            <div className="data-row"><span className="label">Manifest</span><span className="value" title={context?.source_manifest_id}>{shortId(context?.source_manifest_id)}</span></div>
            <div className="data-row"><span className="label">As of</span><span className="value">{dateTime(context?.as_of)}</span></div>
          </div></Panel></div>
        {research && <div className="grid two mt18"><Panel title="Research notes" subtitle="Local browser storage · tied to instrument, manifest and as-of">
          <textarea className="textarea" aria-label="Research notes" placeholder="Record observations, counterevidence, or questions. No AI generation is active." value={note}
            onChange={(event) => { setNote(event.target.value); setSavedNote(false); }} />
          <div className="row between mt12"><span className="subtle">These notes stay in this browser profile and are not backed up with PostgreSQL.</span>
            <button className="button primary" onClick={saveNote}>{savedNote ? <Check size={14} /> : <BookOpenText size={14} />}{savedNote ? 'Saved' : 'Save note'}</button></div>
        </Panel><Panel title="Watchlists" subtitle="Local only · canonical instrument IDs"
          action={<button className="button ghost" onClick={() => navigate('opportunities')}>Open opportunities</button>}>
          <div className="row wrap mb14"><select className="select grow" aria-label="Active watchlist" value={currentWatchlist?.id ?? ''} onChange={(e) => setActiveWatchlist(e.target.value)}>
            {!currentWatchlist && <option value="">No watchlist</option>}{watchlists.map((item) => <option value={item.id} key={item.id}>{item.name}</option>)}</select>
            {currentWatchlist && <button className="button danger" onClick={() => { updateWatchlists(watchlists.filter((item) => item.id !== currentWatchlist.id)); setActiveWatchlist(''); }}>Delete</button>}</div>
          <div className="row mb14"><input className="input grow" aria-label="New watchlist name" placeholder="New watchlist name" value={watchName} onChange={(e) => setWatchName(e.target.value)} />
            <button className="button" onClick={addWatchlist}>Create</button></div>
          {currentWatchlist && <><div className="row mb14"><input className="input grow" aria-label="Rename watchlist" value={currentWatchlist.name} onChange={(e) =>
            updateWatchlists(watchlists.map((item) => item.id === currentWatchlist.id ? { ...item, name: e.target.value } : item))} /></div>
            <div className="data-list">{available.map((item) => {
              const watched = currentWatchlist.instrumentIds.includes(item.instrument_id!);
              const recorded = watchSignals.candidates.find((entry) => entry.symbol === item.symbol &&
                entry.outcome === 'candidate' && entry.source_manifest_id === context?.source_manifest_id &&
                entry.as_of <= (context?.as_of ?? ''));
              const thesisSignal = watchSignals.theses.find((entry) => entry.symbol === item.symbol &&
                entry.source_manifest_id === context?.source_manifest_id && entry.as_of <= (context?.as_of ?? ''));
              return <div className="data-row" key={item.instrument_id}>
              <span className="row wrap"><span className="symbol">{item.symbol}</span>{watched && recorded && <span className="badge info" title="Recorded candidate at this manifest and cutoff">{category(recorded.detector_id)} · {category(recorded.status)}</span>}
                {watched && thesisSignal && <span className="badge warn" title={`Last thesis change: ${dateTime(thesisSignal.updated_at)}`}>{category(thesisSignal.detector_id)} thesis · {category(thesisSignal.status)} · {dateTime(thesisSignal.updated_at)}</span>}</span>
              <button className="button ghost" onClick={() => toggleWatchMember(item.instrument_id!)}>
                <Star size={13} fill={currentWatchlist.instrumentIds.includes(item.instrument_id!) ? 'currentColor' : 'none'} />
                {currentWatchlist.instrumentIds.includes(item.instrument_id!) ? 'Remove' : 'Add'}</button></div>; })}</div></>}
        </Panel></div>}
      </>}</>;
  }

  function analyticsPage() {
    const matches = definitions.filter((item) => (featureFilter === 'All' || featureCategory(item.name) === featureFilter) &&
      `${item.name} ${item.description}`.toLowerCase().includes(featureQuery.toLowerCase()));
    const last = featureSeries?.points.at(-1);
    return <>{header('Feature Explorer', 'Browse the Phase 2 registry, change approved parameters, and inspect exact backend outputs.', instrumentSelector())}
      <div className="grid four mb14"><Metric label="Registered features" value={String(definitions.length || '—')} foot="Versioned backend catalog" />
        <Metric label="Selected feature" value={featureName.replaceAll('_',' ')} foot={selectedDefinition?.version ?? 'Loading registry'} />
        <Metric label="Observed sessions" value={`${featureSeries?.observed_sessions ?? '—'} / ${featureSeries?.expected_sessions ?? '—'}`} foot="At selected manifest and cutoff" />
        <Metric label="Feature freshness" value={featureSeries?.freshness ?? '—'} foot="Backend source assessment" /></div>
      <div className="feature-layout"><Panel title="Feature registry" subtitle={`${matches.length} matching definitions`} noPad>
        <div className="pad16"><input className="input" style={{ width: '100%' }} aria-label="Search features" placeholder="Search feature name or definition…" value={featureQuery} onChange={(e) => setFeatureQuery(e.target.value)} />
          <div className="pillbar mt12">{['All','Returns','Trend','Momentum','Volatility','Volume','Drawdown'].map((item) =>
            <button className={featureFilter === item ? 'active' : ''} key={item} onClick={() => setFeatureFilter(item)}>{item}</button>)}</div></div>
        <div className="feature-list">{matches.map((item) => <button key={item.name} className={`feature-item ${featureName === item.name ? 'active' : ''}`}
          onClick={() => { setFeatureName(item.name); setFeaturePeriod(''); }}><strong>{item.name}</strong><small>{item.description}</small></button>)}</div>
      </Panel><div className="stack"><Panel title={selectedDefinition?.name ?? featureName} subtitle={selectedDefinition?.description ?? 'Registry definition'} action={<Badge value={featureSeries?.freshness ?? 'unknown'} />}>
        {selectedDefinition ? <><div className="grid three">
          <div className="data-list"><div className="data-row"><span className="label">Current value</span><span className="value">{number(last?.value, 4)}</span></div><div className="data-row"><span className="label">Unit</span><span className="value">{selectedDefinition.unit}</span></div></div>
          <div className="data-list"><div className="data-row"><span className="label">Min history</span><span className="value">{selectedDefinition.min_history}</span></div><div className="data-row"><span className="label">Inputs</span><span className="value">{selectedDefinition.required_inputs.join(', ')}</span></div></div>
          <div className="data-list"><div className="data-row"><span className="label">Feature version</span><span className="value">{selectedDefinition.version}</span></div><div className="data-row"><span className="label">Calculation</span><span className="value">{selectedDefinition.calculation_version}</span></div></div>
        </div>{selectedDefinition.parameter_defaults.period !== undefined && <div className="row mt18">
          <label className="small muted" htmlFor="feature-period">Period</label><input id="feature-period" className="input" style={{ width: 90 }} type="number" min={2} max={1000}
            value={featurePeriod || selectedDefinition.parameter_defaults.period} onChange={(e) => setFeaturePeriod(e.target.value)} />
          <span className="subtle">Backend validates this parameter.</span></div>}
        {last?.reason && <div className="callout warn mt12">No value: {category(last.reason)}</div>}</> : <Empty title="Registry unavailable" body="The feature registry could not be loaded." />}
      </Panel><Panel title="Feature history" subtitle="Expected sessions and nulls are retained">
        {featureLoading ? <div className="skeleton" style={{ height: 270 }} /> : featureError ? <ErrorPanel error={featureError} retry={reload} /> :
          featureSeries ? <><SeriesChart series={[{ name: featureName, points: featureSeries.points }]} unit={featureSeries.definition.unit} />
            <div className="row wrap between border-top pad16 micro muted"><span>Missing sessions: {featureSeries.missing_sessions.length} · Current reason: {last?.reason ?? 'none'}</span>
              <span className="mono" title={featureSeries.feature_id}>Feature ID {shortId(featureSeries.feature_id)}</span></div></> : <Empty title="No feature" body="Select a registry definition." />}</Panel>
        <Panel title="Provenance" subtitle="No browser-side indicator calculations"><div className="data-list">
          <div className="data-row"><span className="label">Manifest</span><span className="value" title={featureSeries?.source_manifest_id}>{shortId(featureSeries?.source_manifest_id)}</span></div>
          <div className="data-row"><span className="label">As of</span><span className="value">{dateTime(featureSeries?.request.as_of)}</span></div>
          <div className="data-row"><span className="label">Parameters</span><span className="value">{JSON.stringify(featureSeries?.resolved_parameters ?? {})}</span></div>
          <div className="data-row"><span className="label">Code hash</span><span className="value" title={selectedDefinition?.calculation_code_hash}>{shortId(selectedDefinition?.calculation_code_hash)}</span></div>
        </div></Panel></div></div></>;
  }

  function statePage() {
    return <>{header('Market State', 'Every dimension comes from explicit Phase 2 features, comparisons or breadth rules.',
      <div className="row"><div className="head-meta">SNAPSHOT ID<strong title={state?.snapshot_id}>{shortId(state?.snapshot_id)}</strong></div>
        <button className="button" onClick={() => { setCortexFocus('market'); navigate('cortex'); }}>Ask CORTEX</button></div>)}
      {!state ? <Empty title="State unavailable" body="The selected research context does not have a computable state snapshot." /> : <>
        <div className="grid four mb14"><Metric label="Rule regime" value={category(state.regime.category)} foot={`Version ${state.regime.rule_version}`} />
          <Metric label="Breadth universe" value={state.breadth ? `${state.breadth.observed_members} / ${state.breadth.total_members}` : '—'} foot="Binance Pilot 5 only" />
          <Metric label="Source freshness" value={freshness} foot="No intraday or quote claim" />
          <Metric label="Uncertainty" value={category(dimension('uncertainty')?.category ?? 'unknown')} foot="Unknown and missing members surfaced" /></div>
        <Panel title="Transparent regime" subtitle="Descriptive rule baseline, not a prediction">
          <div className="row wrap between"><div><div className="eyebrow">CLASSIFICATION</div><div style={{ fontSize: 26, textTransform: 'capitalize', marginTop: 5 }}>{category(state.regime.category)}</div></div>
            <Badge value={state.regime.unknown_reason ? 'unknown' : 'current'} /></div>
          <div className="row wrap mt18">{state.regime.rules_fired.map((rule) => <span className="badge info" key={rule}>{rule}</span>)}</div>
          {state.regime.unknown_reason && <div className="callout warn mt12">{category(state.regime.unknown_reason)}</div>}
          <div className="subtle mt12">As of {dateTime(state.request.as_of)} · manifest {shortId(state.source_manifest_id)} · rule code {shortId(state.calculation_version)}</div>
        </Panel><div className="section-title">Evidence-backed dimensions</div><div className="state-grid">{state.dimensions.map((item) => stateCard(item, true))}</div>
      </>}</>;
  }

  function comparePage() {
    const members = available.filter((item) => compareIds.includes(item.instrument_id!));
    const cell = comparison?.matrix[selectedCell[0]]?.[selectedCell[1]];
    const breadth = state?.breadth;
    return <>{header('Compare & breadth', 'Backend-aligned multi-asset context. Correlation always carries a window, count and coverage.')}
      <Panel title="Comparison setup" subtitle="Same Binance UTC daily session calendar"><div className="row wrap between">
        <div className="row wrap">{available.map((item) => <label key={item.instrument_id} className="row badge" style={{ cursor: 'pointer' }}>
          <input type="checkbox" checked={compareIds.includes(item.instrument_id!)} onChange={() =>
            setCompareIds((ids) => ids.includes(item.instrument_id!) ? ids.filter((id) => id !== item.instrument_id) : [...ids, item.instrument_id!])} />{item.symbol}</label>)}</div>
        <div className="row"><label className="small muted" htmlFor="corr-window">Pearson window</label><select id="corr-window" className="select" value={compareWindow} onChange={(e) => setCompareWindow(Number(e.target.value))}>
          {[20,30,60,90,120].map((n) => <option key={n} value={n}>{n} returns</option>)}</select></div></div>
      </Panel><div className="grid main-side mt18"><div className="stack"><Panel title="Normalized performance" subtitle="Backend cumulative return · first visible session = 0">
        {compareLoading ? <div className="skeleton" style={{ height: 300 }} /> : compareError ? <ErrorPanel error={compareError} retry={reload} /> : comparison ?
          <SeriesChart series={members.map((item) => ({ name: item.symbol, points: comparison.performance[item.symbol] ?? [] }))} unit="fraction" height={320} /> :
          <Empty title="Select at least two" body="Choose two to five pilot members for a backend-aligned comparison." />}</Panel>
        <Panel title="Pearson correlation matrix" subtitle={`${compareWindow} aligned log-return pairs · Binance UTC sessions`} noPad>
          {comparison ? <div className="matrix"><table><thead><tr><th>Pair</th>{comparison.members.map((name) => <th key={name}>{name.replace('USDT','')}</th>)}</tr></thead>
            <tbody>{comparison.members.map((name, i) => <tr key={name}><th>{name.replace('USDT','')}</th>{comparison.matrix[i].map((entry, j) =>
              <td key={entry.reference}><button className={`matrix-cell ${entry.value != null && entry.value >= .75 ? 'strong' : ''} ${entry.value != null && entry.value < 0 ? 'negative' : ''} ${selectedCell[0] === i && selectedCell[1] === j ? 'selected' : ''}`}
                title={`${entry.count}/${compareWindow} pairs · coverage ${number(entry.coverage * 100, 0)}%`} onClick={() => setSelectedCell([i,j])}>{number(entry.value, 2)}</button></td>)}</tr>)}</tbody></table></div> :
            <Empty title="Matrix unavailable" body="A valid two-to-five member selection is needed." />}</Panel>
      </div><div className="stack"><Panel title="Selected correlation" subtitle="Window and sample details">
        {cell ? <div className="data-list"><div className="data-row"><span className="label">Pair</span><span className="value">{cell.target} / {cell.reference}</span></div>
          <div className="data-row"><span className="label">Pearson r</span><span className="value">{number(cell.value, 4)}</span></div>
          <div className="data-row"><span className="label">Window</span><span className="value">{comparison?.window} returns</span></div>
          <div className="data-row"><span className="label">Observed pairs</span><span className="value">{cell.count}</span></div>
          <div className="data-row"><span className="label">Coverage</span><span className="value">{number(cell.coverage * 100, 1)}%</span></div>
          <div className="data-row"><span className="label">Missingness</span><span className="value">{number(cell.missingness * 100, 1)}%</span></div>
          <div className="data-row"><span className="label">Stability</span><span className="value">{number(cell.stability, 4)}</span></div>
          <div className="data-row"><span className="label">Reason</span><span className="value">{cell.reason ?? 'none'}</span></div>
          <div className="data-row"><span className="label">Version</span><span className="value">{cell.version}</span></div>
        </div> : <Empty title="Select a cell" body="Correlation details appear here." />}</Panel>
        <Panel title="Breadth & participation" subtitle="Exact Binance Pilot 5 universe">
          {breadth ? <div className="data-list">{([
            ['Above SMA 20', breadth.above_sma], ['Positive 20D', breadth.positive_lookback],
            ['New high 20D', breadth.new_high], ['New low 20D', breadth.new_low]
          ] as const).map(([label, metric]) => <div className="data-row" key={label}><span className="label">{label}</span>
            <span className="value">{number(metric.percentage, 0)}% · {metric.positive}/{metric.eligible}</span></div>)}
            <div className="data-row"><span className="label">Advance / decline</span><span className="value">{breadth.advancing} / {breadth.declining} · eligible {breadth.advance_decline_eligible}</span></div>
            <div className="data-row"><span className="label">Observed members</span><span className="value">{breadth.observed_members}/{breadth.total_members}</span></div>
          </div> : <Empty title="Breadth unavailable" body="The selected context has insufficient eligible pilot members." />}</Panel>
      </div></div></>;
  }

  function coveragePage() {
    return <>{header('Data & coverage', 'What is present in this local catalog, which sources are configured, and where the evidence stops.')}
      <div className="grid three mb14">{context?.providers.map((provider) => <div className="metric" key={provider.provider_id}>
        <div className="row between"><span className="metric-label">{provider.label}</span><Badge value={provider.status}/></div>
        <div className="metric-value" style={{ fontSize: 20, textTransform: 'capitalize' }}>{provider.provider_id}</div>
        <div className="metric-foot">{category(provider.credential_state)} · {provider.interval} · {provider.provider_id === 'binance' ? 'Public, stored daily observations' : 'Adapter present; live validation pending'}</div>
      </div>)}</div>
      <div className="grid main-side"><Panel title="Pilot instrument coverage" subtitle="Visible under selected manifest and as-of" noPad>
        <div className="table-wrap"><table><thead><tr><th>Instrument</th><th>First session</th><th>Last session</th><th className="numeric">Observed sessions</th><th>Status</th></tr></thead>
          <tbody>{context?.members.map((member) => <tr key={member.symbol}><td className="symbol">{member.symbol}<small>{member.currency ?? 'unknown'} · raw P1D</small></td>
            <td className="mono">{member.first_session ?? '—'}</td><td className="mono">{member.last_session ?? '—'}</td>
            <td className="numeric">{number(member.observed_sessions, 0)}</td><td><Badge value={member.status}/></td></tr>)}</tbody></table></div>
      </Panel><div className="stack"><Panel title="Interpretation" subtitle="Limits of this dataset"><div className="callout">The latest stored daily session is <strong>{context?.evaluation_date ?? 'unavailable'}</strong>. This is historical daily market data, not a live quote. The freshness badge comes from Phase 2 policy at the selected cutoff.</div>
        <div className="callout warn mt12">Upstox and Alpaca live data remain <strong>DEFERRED_NOT_CONFIGURED</strong>. Their adapters are retained; no India or US market coverage is claimed.</div>
        <div className="callout mt12">Primary display preference: INR. Secondary: USD. Market prices remain in native quote currency until a sourced FX series exists.</div></Panel>
        <Panel title="Current research scope" subtitle="No silent extrapolation"><div className="data-list">
          <div className="data-row"><span className="label">Universe</span><span className="value">{context?.universe_label}</span></div>
          <div className="data-row"><span className="label">Common evaluation</span><span className="value">{context?.evaluation_date ?? '—'}</span></div>
          <div className="data-row"><span className="label">Current head published</span><span className="value">{dateTime(context?.recent_manifests.find((item) => item.manifest_id === context.head_manifest_id)?.created_at)}</span></div>
          <div className="data-row"><span className="label">Source freshness</span><Badge value={freshness}/></div>
          <div className="data-row"><span className="label">Time zone</span><span className="value">Asia/Kolkata</span></div>
        </div></Panel></div></div></>;
  }

  function systemPage() {
    return <>{header('System & lineage', 'Inspect the selected dataset ancestry and local service state without exposing credentials.')}
      <div className="grid four mb14"><Metric label="Backend" value={category(health)} foot="Local loopback read API" />
        <Metric label="Manifest files" value={manifest ? number(manifest.file_count, 0) : '—'} foot="Content addressed Parquet" />
        <Metric label="Rows in files" value={manifest ? number(manifest.rows_in_files, 0) : '—'} foot="Ancestry file row total" />
        <Metric label="Storage integrity" value={manifest ? manifest.storage.missing.length || manifest.storage.corrupt.length ? 'Needs review' : 'Verified' : '—'} foot="Read-only hash inventory" /></div>
      {manifestError ? <ErrorPanel error={manifestError} retry={reload} /> : !manifest ? <Loading label="Inspecting manifest ancestry and file hashes…" /> : <div className="grid main-side">
        <div className="stack"><Panel title="Selected manifest" subtitle="Catalog metadata"><div className="data-list">
          <div className="data-row"><span className="label">Manifest ID</span><span className="value" title={manifest.manifest_id}>{manifest.manifest_id}</span></div>
          <div className="data-row"><span className="label">Parent</span><span className="value" title={manifest.parent_manifest_id ?? ''}>{manifest.parent_manifest_id ?? 'Genesis'}</span></div>
          <div className="data-row"><span className="label">Created</span><span className="value">{dateTime(manifest.created_at)}</span></div>
          <div className="data-row"><span className="label">Schema</span><span className="value">{manifest.schema_version}</span></div>
          <div className="data-row"><span className="label">Selection policy</span><span className="value">{manifest.selection_policy_version}</span></div>
          <div className="data-row"><span className="label">Dataset head</span><span className="value" title={context?.head_manifest_id}>{shortId(context?.head_manifest_id)}</span></div>
        </div></Panel><Panel title="Files in ancestry" subtitle={`${manifest.file_count} immutable Parquet artifacts`} noPad>
          <div className="table-wrap" style={{ maxHeight: 410 }}><table><thead><tr><th>SHA-256</th><th className="numeric">Rows</th><th>Venue</th><th>First event</th><th>Last event</th></tr></thead>
            <tbody>{manifest.files.map((file) => <tr key={file.sha256}><td className="mono" title={file.sha256}>{shortId(file.sha256)}</td>
              <td className="numeric">{file.rows}</td><td>{file.venue_id}</td><td className="mono">{file.min_event_at.slice(0,10)}</td><td className="mono">{file.max_event_at.slice(0,10)}</td></tr>)}</tbody></table></div>
        </Panel></div><div className="stack"><Panel title="Source batches" subtitle="Referenced by observations"><div className="data-list">{manifest.providers.map((provider) =>
          <div className="data-row" key={provider.provider_id}><span className="label">{provider.provider_id}</span><span className="value">{provider.source_batches} batches · {provider.observations} observations</span></div>)}</div></Panel>
          <Panel title="Storage inventory" subtitle="Read-only integrity check"><div className="data-list">
            {([['Referenced files', manifest.storage.referenced], ['Missing files', manifest.storage.missing.length],
              ['Corrupt files', manifest.storage.corrupt.length], ['Unreferenced files', manifest.storage.unreferenced.length],
              ['Staged files', manifest.storage.staged_count]] as const).map(([label, count]) =>
              <div className="data-row" key={label}><span className="label">{label}</span><span className="value">{count}</span></div>)}</div></Panel>
          <Panel title="Research safeguards" subtitle="Local-first boundary"><div className="data-list">
            <div className="data-row"><span className="label">Price adjustment</span><span className="value">raw</span></div>
            <div className="data-row"><span className="label">Frontend FX conversion</span><span className="value">disabled</span></div>
            <div className="data-row"><span className="label">Order execution</span><span className="value">not available</span></div>
            <div className="data-row"><span className="label">API scope</span><span className="value">Read endpoints plus local research, candidate and thesis records</span></div>
          </div></Panel></div></div>}</>;
  }

  const commandItems = [...NAV.map((item) => ({ label: item.label, detail: 'Navigate workspace', kind: 'page' as const, id: item.id })),
    ...available.map((item) => ({ label: item.symbol, detail: `${item.currency} · Instrument`, kind: 'instrument' as const, id: item.instrument_id! })),
    ...definitions.map((item) => ({ label: item.name, detail: item.description, kind: 'feature' as const, id: item.name }))]
    .filter((item) => `${item.label} ${item.detail}`.toLowerCase().includes(commandQuery.toLowerCase())).slice(0, 18);
  const runCommand = (item: typeof commandItems[number]) => {
    if (item.kind === 'page') navigate(item.id as View);
    if (item.kind === 'instrument') openInstrument(item.id);
    if (item.kind === 'feature') { setFeatureName(item.id); navigate('analytics'); }
    setCommandOpen(false); setCommandQuery('');
  };

  return <div className="app"><aside className="rail"><div className="brand"><span className="brand-mark">MC</span><div><strong>MARKET CORTEX</strong><small>RESEARCH WORKSTATION</small></div></div>
    <div className="rail-label">Workspace</div><nav className="nav" aria-label="Main navigation">{NAV.map((item) => {
      const Icon = item.icon; return <button key={item.id} onClick={() => { if (item.id === 'cortex') setCortexFocus(view === 'market-state' ? 'market' : 'instrument'); navigate(item.id); }} className={view === item.id ? 'active' : ''}>
        <Icon />{item.label}<span className="key">{item.key}</span></button>;
    })}</nav><div className="rail-spacer"/><div className="rail-bottom"><div><span className={`tiny-dot ${health === 'ready' ? 'good' : 'bad'}`}/><strong>{health === 'ready' ? 'LOCAL SYSTEM READY' : category(health).toUpperCase()}</strong></div>
      <div>Research only · No execution</div><div>Phase 8 · v0.8.0</div></div></aside>
    <main className="main"><header className="topbar"><button className="search-trigger" onClick={() => setCommandOpen(true)}><Search size={15} /> Search markets, features, pages <kbd>Ctrl K</kbd></button>
      <div className="top-grow" /><span className={`top-tag env-badge ${dataEnvironment === 'UNLABELED' ? 'warning' : ''}`}>{dataEnvironment.replaceAll('_', ' / ')}</span><span className="top-tag"><span className={`tiny-dot ${health === 'ready' ? 'good' : 'bad'}`} /> API {category(health)}</span>
      <span className="top-tag"><FileClock size={13} /> {selection.mode === 'latest' ? 'Latest head' : selection.mode === 'pinned' ? 'Pinned research' : 'Historical research'}</span>
      <button className="button icon ghost" title="Refresh research context" aria-label="Refresh research context" onClick={reload}><RefreshCw size={15} /></button></header>
      <div className="content"><div className={`context-strip ${selection.mode === 'latest' ? '' : 'historical'}`}>
        <span className="mode">{selection.mode === 'latest' ? 'Latest dataset head' : selection.mode === 'pinned' ? 'Pinned research mode' : 'Historical research mode'}</span>
        <span className="sep" /><span className="detail">Manifest <b title={context?.source_manifest_id}>{shortId(context?.source_manifest_id)}</b></span>
        <span className="sep" /><span className="detail">As of <b>{dateTime(context?.as_of)}</b></span>
        <span className="sep" /><span className="detail">Freshness <b>{freshness}</b></span>
        <button className="button ghost" onClick={() => { setDraft({ ...selection,
          asOf: selection.asOf ? localCutoff(selection.asOf) : '' }); setContextOpen((open) => !open); }}>Change context</button></div>
      {contextOpen && <Panel title="Research context" subtitle="Select a dataset and availability cutoff before opening analytical views" action={<button className="button icon ghost" onClick={() => setContextOpen(false)}><X size={14}/></button>}>
        <div className="pillbar mb14">{(['latest','pinned','historical'] as Mode[]).map((mode) => <button key={mode} className={draft.mode === mode ? 'active' : ''} onClick={() => setDraft({ ...draft, mode })}>{category(mode)}</button>)}</div>
        <div className="form-row"><div className="field"><label htmlFor="manifest-choice">Manifest</label><select id="manifest-choice" className="select" disabled={draft.mode === 'latest'} value={draft.manifestId ?? ''}
          onChange={(event) => setDraft({ ...draft, manifestId: event.target.value || undefined })}>
          <option value="">Current head</option>{context?.recent_manifests.map((item) => <option key={item.manifest_id} value={item.manifest_id}>{shortId(item.manifest_id)} · {item.created_at.slice(0,10)}</option>)}</select></div>
          <div className="field"><label htmlFor="cutoff-choice">As-of cutoff · local time</label><input id="cutoff-choice" className="input" type="text" inputMode="numeric"
            placeholder="YYYY-MM-DD HH:mm" disabled={draft.mode !== 'historical'}
            value={draft.asOf ?? ''} onChange={(event) => { const value = event.currentTarget.value;
              setDraft((current) => ({ ...current, asOf: value })); }} /></div>
          <div className="field"><label>Apply</label><button className="button primary" onClick={applyContext}>Open research context <ChevronRight size={14}/></button></div></div>
        <div className="callout mt12">Pinned mode keeps a published manifest fixed. Historical mode also cuts off observation availability at the selected instant. Every screen carries the resolved manifest and cutoff.</div>
      </Panel>}
      {error || (['overview','market-state','compare'].includes(view) && overviewError) ? <ErrorPanel error={error??overviewError!} retry={reload} /> : loading && !context ? <Loading /> : !context ?
        <Empty title="No research context" body="The catalog has not returned a usable context." /> :
        view === 'overview' ? overviewPage() : view === 'instruments' ? instrumentPage() :
        view === 'analytics' ? analyticsPage() : view === 'market-state' ? statePage() :
        view === 'compare' ? comparePage() : view === 'coverage' ? coveragePage() :
        view === 'research' ? instrumentPage(true) : view === 'opportunities' ?
          <OpportunityPane key={`${context.source_manifest_id}.${context.as_of}`} context={context}
            mode={selection.mode} watchlistIds={currentWatchlist?.instrumentIds ?? []} /> : view === 'portfolio' ?
          <PortfolioPane key={`${context.source_manifest_id}.${context.as_of}`} context={context} /> : view === 'learning' ?
          <LearningPane key={`${context.source_manifest_id}.${context.as_of}`} context={context} /> : view === 'quant' ?
          <QuantPane key={`${context.source_manifest_id}.${context.as_of}`} context={context} /> : view === 'cortex' ?
          <CortexPane key={`${context.source_manifest_id}.${context.as_of}.${cortexFocus}`} context={context}
            mode={selection.mode} symbol={cortexFocus === 'market' ? null : selectedMember?.symbol ?? null} /> : systemPage()}
      </div></main>
    {commandOpen && <div className="modal-backdrop" onClick={() => setCommandOpen(false)}><div className="modal" role="dialog" aria-label="Command search" onClick={(e) => e.stopPropagation()}>
      <div className="modal-head"><Command size={17} color="var(--accent)" /><input aria-label="Command search input" autoFocus placeholder="Find an instrument, feature or workspace…" value={commandQuery} onChange={(e) => setCommandQuery(e.target.value)} />
        <button className="button icon ghost" onClick={() => setCommandOpen(false)}><X size={14}/></button></div>
      <div className="modal-body">{commandItems.length ? commandItems.map((item) => <button className="command-item" key={`${item.kind}:${item.id}`} onClick={() => runCommand(item)}>
        {item.kind === 'instrument' ? <BarChart3/> : item.kind === 'feature' ? <Activity/> : <ChevronRight/>}
        <span><strong>{item.label}</strong><small>{item.detail}</small></span></button>) : <Empty title="No match" body="Try a symbol, feature name or page." />}</div>
      <div className="modal-foot">LOCAL SEARCH · NO AI REQUEST</div></div></div>}</div>;
}
