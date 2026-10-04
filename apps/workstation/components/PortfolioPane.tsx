'use client';

import { useCallback, useEffect, useState } from 'react';
import { ApiError, category, getJson, number, postJson, shortId, type Context } from '@/lib/api';

type Position = { position_id: string; instrument_id: string; quantity: string; average_cost: string;
  native_currency: string; opened_at: string; closed_at: string | null; thesis_id: string | null;
  invalidation_price: string | null; target_price: string | null; note: string; source_type: string };
type Portfolio = { portfolio_id: string; name: string; base_currency: string; capital: string;
  classification: string; version: number; updated_at: string; positions: Position[] };
type PositionRisk = { position_id: string; symbol: string; quantity: string; native_currency: string;
  reference_price: string | null; market_value: string | null; unrealized_pnl: string | null;
  annualized_volatility: number | null; atr14: number | null; drawdown: number | null;
  risk_to_invalidation: string | null; one_r: string | null; current_r: string | null;
  invalidation_price: string | null; freshness: string; thesis_id: string | null; warnings: string[] };
type Risk = { snapshot_id: string; portfolio_version: number; portfolio_classification: string;
  source_manifest_id: string; as_of: string; calculation_version: string; capital: string;
  base_currency: string; market_regime: string | null; positions: PositionRisk[];
  portfolio_market_value: string | null; unrealized_pnl: string | null;
  exposure: { gross: string | null; net: string | null; by_instrument: Record<string,string>;
    by_currency: Record<string,string>; by_strategy: Record<string,string>;
    by_asset_class: Record<string,string>; by_provider: Record<string,string>;
    concentration_weights: Record<string,string>; concentration_flags: string[];
    concentration_threshold: string };
  heat_amount: string | null; heat_percent: string | null; btc_sensitivity_proxy: string | null;
  portfolio_drawdown: string | null; correlation_cluster_flags: string[];
  correlations: { left: string; right: string; correlation: number | null; sample_count: number;
    coverage: number; unknown_reason: string | null }[];
  coverage: number; price_freshness: string; feature_freshness: string;
  market_state_freshness: string; warnings: string[] };
type Scenario = { portfolio_pnl: string | null; portfolio_change_percent: string | null;
  position_pnl: Record<string,string | null>; coverage: number; warnings: string[] };
type Thesis = { thesis_id: string; symbol: string; detector_id: string; status: string };
type Overlay = { label: string; delta_gross_exposure: string | null; delta_heat: string | null;
  delta_btc_sensitivity_proxy: string | null; before: Risk; after: Risk;
  before_scenario: Scenario | null; after_scenario: Scenario | null };

function amount(value: string | number | null | undefined, digits = 2) {
  return value == null ? 'unavailable' : number(Number(value), digits);
}
function code(problem: unknown) { return problem instanceof ApiError ? problem.code : 'REQUEST_FAILED'; }

export default function PortfolioPane({ context }: { context: Context }) {
  const [portfolios, setPortfolios] = useState<Portfolio[]>([]);
  const [selected, setSelected] = useState('');
  const [risk, setRisk] = useState<Risk | null>(null);
  const [scenario, setScenario] = useState<Scenario | null>(null);
  const [overlay, setOverlay] = useState<Overlay | null>(null);
  const [theses, setTheses] = useState<Thesis[]>([]);
  const [versions, setVersions] = useState<{ version: number; action: string; reason: string; recorded_at: string }[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [name, setName] = useState('Research portfolio');
  const [capital, setCapital] = useState('100000');
  const [currency, setCurrency] = useState('INR');
  const [symbol, setSymbol] = useState('BTCUSDT');
  const [quantity, setQuantity] = useState('1');
  const [cost, setCost] = useState('');
  const [invalidation, setInvalidation] = useState('');
  const [reason, setReason] = useState('Manual research position entry');
  const [editingId, setEditingId] = useState('');
  const [shock, setShock] = useState('-10');
  const [shockTarget, setShockTarget] = useState('all');
  const [thesisId, setThesisId] = useState('');
  const [overlayQuantity, setOverlayQuantity] = useState('1');
  const [overlayCost, setOverlayCost] = useState('');
  const [overlayInvalidation, setOverlayInvalidation] = useState('');
  const shockAssumptions = () => Object.fromEntries((shockTarget === 'all' ?
    context.members.map((item) => item.symbol) : [shockTarget]).map((item) =>
    [item, String(Number(shock) / 100)]));

  const load = useCallback(async () => {
    const [list, savedTheses] = await Promise.all([
      getJson<{items:Portfolio[]}>('risk/portfolios'),
      getJson<{items:Thesis[]}>('opportunities/theses')]);
    setPortfolios(list.items); setTheses(savedTheses.items);
    setSelected((prior) => list.items.some((item) => item.portfolio_id === prior) ? prior :
      list.items[0]?.portfolio_id ?? '');
  }, []);
  useEffect(() => { load().catch((problem) => setError(code(problem))); }, [load]);
  const portfolio = portfolios.find((item) => item.portfolio_id === selected);
  const pinned = { manifest_id: context.source_manifest_id, as_of: context.as_of };
  const calculate = useCallback(async (persist = false) => {
    if (!selected) return;
    setBusy(true); setError(null);
    try {
      const result = await postJson<Risk>(`risk/portfolios/${selected}/calculate`, { ...pinned, persist });
      setRisk(result); setScenario(null); setOverlay(null);
      const history = await getJson<{items: typeof versions}>(`risk/portfolios/${selected}/versions`);
      setVersions(history.items);
    } catch (problem) { setError(code(problem)); }
    finally { setBusy(false); }
  }, [selected, context.source_manifest_id, context.as_of]);
  useEffect(() => { void calculate(false); }, [calculate]);
  const createPortfolio = async () => {
    setBusy(true); setError(null);
    try {
      const created = await postJson<Portfolio>('risk/portfolios', {
        name, base_currency: currency, capital, classification: 'OWNER_RESEARCH' });
      await load(); setSelected(created.portfolio_id);
    } catch (problem) { setError(code(problem)); }
    finally { setBusy(false); }
  };
  const savePosition = async () => {
    const member = context.members.find((item) => item.symbol === symbol);
    if (!selected || !member?.instrument_id || !cost || !quantity) return;
    const existing = portfolio?.positions.find((item) => item.position_id === editingId);
    setBusy(true); setError(null);
    try {
      await postJson(`risk/portfolios/${selected}/positions`, { action: existing ? 'update' : 'add', reason,
        position: { ...existing, instrument_id: member.instrument_id, quantity, average_cost: cost,
          native_currency: existing?.native_currency ?? 'USDT',
          opened_at: existing?.opened_at ?? new Date().toISOString(),
          invalidation_price: invalidation || null, source_type: existing?.source_type ?? 'manual' } });
      setEditingId(''); setCost(''); setInvalidation('');
      await load(); await calculate(false);
    } catch (problem) { setError(code(problem)); }
    finally { setBusy(false); }
  };
  const editPosition = (position: Position) => {
    const member = context.members.find((item) => item.instrument_id === position.instrument_id);
    if (!member) { setError('POSITION_INSTRUMENT_NOT_IN_CONTEXT'); return; }
    setEditingId(position.position_id); setSymbol(member.symbol);
    setQuantity(position.quantity); setCost(position.average_cost);
    setInvalidation(position.invalidation_price ?? '');
    setReason('Owner correction to research position');
  };
  const closePosition = async (position: Position) => {
    if (!selected || reason.length < 8) return;
    setBusy(true); setError(null);
    try {
      await postJson(`risk/portfolios/${selected}/positions`, { action:'close', reason,
        position:{...position, closed_at:new Date().toISOString()} });
      setEditingId(''); await load(); await calculate(false);
    } catch (problem) { setError(code(problem)); }
    finally { setBusy(false); }
  };
  const runScenario = async () => {
    if (!selected || !risk) return;
    setBusy(true); setError(null);
    try {
      const shocks = shockAssumptions();
      const result = await postJson<Scenario>(`risk/portfolios/${selected}/scenario`, {
        risk: { ...pinned, portfolio_version: risk.portfolio_version },
        scenario: { name: 'Owner what-if', kind: shockTarget === 'all' ? 'broad_crypto_shock' : 'instrument_shock', shocks } });
      setScenario(result);
    } catch (problem) { setError(code(problem)); }
    finally { setBusy(false); }
  };
  const runOverlay = async () => {
    if (!selected || !risk || !thesisId || !overlayCost || !overlayQuantity) return;
    setBusy(true); setError(null);
    try {
      const result = await postJson<Overlay>(`risk/theses/${thesisId}/risk`, {
        portfolio_id: selected, risk: { ...pinned, portfolio_version: risk.portfolio_version },
        quantity: overlayQuantity, reference_price: overlayCost,
        invalidation_price: overlayInvalidation || null,
        scenario: { name:'Owner what-if overlay',
          kind:shockTarget === 'all' ? 'broad_crypto_shock' : 'instrument_shock',
          shocks:shockAssumptions() } });
      setOverlay(result);
    } catch (problem) { setError(code(problem)); }
    finally { setBusy(false); }
  };

  return <div className="stack"><div className="page-head"><div><div className="eyebrow">MARKET CORTEX / LOCAL RESEARCH</div>
    <h1>Portfolio &amp; Risk</h1><p>Versioned owner-entered positions and deterministic, pinned what-if risk. No broker connection or orders.</p></div>
    <div className="head-meta">SOURCE MANIFEST<strong>{shortId(context.source_manifest_id)}</strong></div></div>
    {error && <div className="callout error"><strong>{error}</strong> · Missing values remain unavailable.</div>}
    <section className="panel"><div className="panel-head"><h2>Portfolio context</h2><span className="sub">Local only · {context.as_of}</span></div><div className="panel-body stack">
      <div className="row wrap"><select className="select" aria-label="Portfolio" value={selected} onChange={(e) => setSelected(e.target.value)}>
        {!portfolios.length && <option value="">No portfolio yet</option>}{portfolios.map((item) =>
          <option key={item.portfolio_id} value={item.portfolio_id}>{item.name} · {item.classification}</option>)}</select>
        <button className="button" disabled={!selected || busy} onClick={() => void calculate(false)}>Recalculate</button>
        <button className="button primary" disabled={!selected || busy} onClick={() => void calculate(true)}>Save pinned snapshot</button></div>
      <div className="op-controls"><input className="input" aria-label="Portfolio name" value={name} onChange={(e) => setName(e.target.value)} />
        <input className="input" aria-label="Portfolio capital" type="number" min="1" value={capital} onChange={(e) => setCapital(e.target.value)} />
        <select className="select" aria-label="Portfolio currency" value={currency} onChange={(e) => setCurrency(e.target.value)}><option>INR</option><option>USD</option><option>USDT</option></select>
        <button className="button primary" disabled={busy || !name || Number(capital) <= 0} onClick={createPortfolio}>Create local portfolio</button></div>
      {portfolio && <div className="callout">{portfolio.classification} · v{portfolio.version} · capital {amount(portfolio.capital)} {portfolio.base_currency}. Pilot market values are native USDT; cross-currency totals need governed FX data.</div>}
    </div></section>
    {portfolio && <section className="panel"><div className="panel-head"><h2>Manual research position</h2><span className="sub">Additions, corrections and closures append a portfolio version</span></div><div className="panel-body stack"><div className="op-controls">
      <select className="select" aria-label="Position instrument" value={symbol} disabled={!!editingId} onChange={(e) => setSymbol(e.target.value)}>{context.members.map((item) => <option key={item.symbol}>{item.symbol}</option>)}</select>
      <input className="input" aria-label="Quantity" type="number" min="0" step="any" value={quantity} onChange={(e) => setQuantity(e.target.value)} />
      <input className="input" aria-label="Average cost USDT" type="number" min="0" step="any" placeholder="Average cost USDT" value={cost} onChange={(e) => setCost(e.target.value)} />
      <input className="input" aria-label="Invalidation price USDT" type="number" min="0" step="any" placeholder="Optional invalidation" value={invalidation} onChange={(e) => setInvalidation(e.target.value)} />
      <input className="input" aria-label="Position reason" value={reason} onChange={(e) => setReason(e.target.value)} />
      <button className="button" disabled={busy || !cost || !quantity || reason.length < 8} onClick={savePosition}>{editingId ? 'Save correction' : 'Record position'}</button>
      {editingId && <button className="button" onClick={() => { setEditingId(''); setCost(''); setInvalidation(''); }}>Cancel edit</button>}</div>
      <div className="data-list">{portfolio.positions.filter((item) => !item.closed_at).map((item) => <div className="data-row" key={item.position_id}>
        <span className="label">{context.members.find((member) => member.instrument_id === item.instrument_id)?.symbol ?? shortId(item.instrument_id)} · {amount(item.quantity,4)} · cost {amount(item.average_cost)} {item.native_currency}</span>
        <span className="value"><button className="button" disabled={busy} onClick={() => editPosition(item)}>Edit</button>{' '}
          <button className="button" disabled={busy || reason.length < 8} onClick={() => void closePosition(item)}>Close research position</button></span></div>)}</div></div></section>}
    {risk && <><div className="grid four"><div className="metric"><div className="metric-label">Priced positions value</div><div className="metric-value">{amount(risk.portfolio_market_value)}</div><div className="metric-foot">{risk.portfolio_market_value == null ? 'FX or price unavailable' : `${risk.base_currency} · excludes unrecorded cash`}</div></div>
      <div className="metric"><div className="metric-label">Unrealized P/L</div><div className="metric-value">{amount(risk.unrealized_pnl)}</div><div className="metric-foot">{risk.unrealized_pnl == null ? 'FX or cost unavailable' : risk.base_currency}</div></div>
      <div className="metric"><div className="metric-label">Portfolio heat</div><div className="metric-value">{risk.heat_percent == null ? 'unknown' : `${amount(Number(risk.heat_percent)*100)}%`}</div><div className="metric-foot">Current price to explicit invalidation / capital</div></div>
      <div className="metric"><div className="metric-label">BTC sensitivity proxy</div><div className="metric-value">{risk.btc_sensitivity_proxy == null ? 'unknown' : `${amount(Number(risk.btc_sensitivity_proxy)*100)}%`}</div><div className="metric-foot">Correlation-weighted, not regression beta</div></div>
      <div className="metric"><div className="metric-label">Coverage</div><div className="metric-value">{amount(risk.coverage*100)}%</div><div className="metric-foot">Price {risk.price_freshness} · features {risk.feature_freshness} · state {risk.market_state_freshness}</div></div></div>
      <section className="panel"><div className="panel-head"><h2>Position risk</h2><span className="sub">Risk snapshot {shortId(risk.snapshot_id)} · {risk.calculation_version}</span></div><div className="panel-body"><p className="panel-caption">Portfolio drawdown: {risk.portfolio_drawdown == null ? 'unavailable (no equity series)' : `${amount(Number(risk.portfolio_drawdown)*100)}%`}. Position figures are in each instrument’s native currency.</p></div><div className="table-wrap"><table><thead><tr><th>Instrument</th><th>Qty</th><th>Stored price</th><th>Value</th><th>P/L</th><th>Drawdown</th><th>Volatility</th><th>ATR14</th><th>Invalidation</th><th>Risk to invalidation</th><th>Current R</th><th>Thesis</th><th>Freshness</th></tr></thead><tbody>{risk.positions.map((item) =>
        <tr key={item.position_id}><td className="symbol">{item.symbol}</td><td>{amount(item.quantity, 4)}</td><td>{amount(item.reference_price)}</td><td>{amount(item.market_value)}</td><td>{amount(item.unrealized_pnl)}</td>
          <td>{item.drawdown == null ? 'unavailable' : `${amount(item.drawdown*100)}%`}</td><td>{item.annualized_volatility == null ? 'unavailable' : `${amount(item.annualized_volatility*100)}%`}</td><td>{amount(item.atr14)}</td><td>{amount(item.invalidation_price)}</td><td>{amount(item.risk_to_invalidation)}</td><td>{amount(item.current_r)}</td><td>{item.thesis_id ? shortId(item.thesis_id) : 'unlinked'}</td><td>{item.freshness}</td></tr>)}</tbody></table></div></section>
      <div className="grid two"><section className="panel"><div className="panel-head"><h2>Exposure &amp; concentration</h2></div><div className="panel-body"><div className="data-list">{Object.entries(risk.exposure.by_instrument).map(([key,value]) =>
        <div className="data-row" key={key}><span className="label">{key}{risk.exposure.concentration_flags.includes(key) ? ' · concentration' : ''}</span><span className="value">{amount(value)} {risk.positions.find((item) => item.symbol === key)?.native_currency ?? 'native'} · {risk.exposure.concentration_weights[key] == null ? 'unknown' : `${amount(Number(risk.exposure.concentration_weights[key])*100)}%`}</span></div>)}</div>
        <p className="panel-caption">Flag threshold: {amount(Number(risk.exposure.concentration_threshold)*100)}% of measured gross exposure. Currency: {Object.entries(risk.exposure.by_currency).map(([key,value]) => `${key} ${amount(value)}`).join(' · ') || 'none'}. Asset class: {Object.entries(risk.exposure.by_asset_class).map(([key,value]) => `${key} ${amount(value)}`).join(' · ') || 'none'}. Provider: {Object.entries(risk.exposure.by_provider).map(([key,value]) => `${key} ${amount(value)}`).join(' · ') || 'none'}. Strategy/thesis: {Object.entries(risk.exposure.by_strategy).map(([key,value]) => `${key === 'unlinked' ? key : shortId(key)} ${amount(value)}`).join(' · ') || 'none'}.</p></div></section>
      <section className="panel"><div className="panel-head"><h2>Correlation clusters</h2><span className="sub">60 aligned log-return samples</span></div><div className="panel-body"><div className="data-list">{risk.correlations.map((item) => <div className="data-row" key={`${item.left}:${item.right}`}><span className="label">{item.left} / {item.right}</span><span className="value">{item.correlation == null ? 'unavailable' : amount(item.correlation, 3)} · n={item.sample_count} · {amount(item.coverage*100)}%</span></div>)}</div>
        {!risk.correlations.length && <p className="muted small">Add two priced Pilot 5 instruments for paired correlation.</p>}
        <p className="panel-caption">Concentrated clusters (correlation ≥ 0.80 and combined weight ≥ 50%): {risk.correlation_cluster_flags?.join(' · ') || 'none measured'}.</p></div></section></div>
      <section className="panel"><div className="panel-head"><h2>What-if scenario</h2><span className="sub">Explicit shock assumptions; no forecast</span></div><div className="panel-body stack"><div className="op-controls"><select className="select" aria-label="Shock target" value={shockTarget} onChange={(e) => setShockTarget(e.target.value)}><option value="all">All Pilot 5 crypto</option>{context.members.map((item) => <option key={item.symbol}>{item.symbol}</option>)}</select>
        <input className="input" aria-label="Shock percent" type="number" value={shock} onChange={(e) => setShock(e.target.value)} />
        <button className="button primary" disabled={busy || !Number.isFinite(Number(shock))} onClick={runScenario}>Run what-if</button></div>
        {scenario && <><div className="callout"><strong>What-if P/L: {amount(scenario.portfolio_pnl)} {risk.base_currency}</strong> · portfolio change {scenario.portfolio_change_percent == null ? 'unavailable' : `${amount(Number(scenario.portfolio_change_percent)*100)}%`}. Coverage {amount(scenario.coverage*100)}%. {scenario.warnings.join('; ')}</div>
          <div className="data-list">{risk.positions.map((item) => <div className="data-row" key={item.position_id}><span className="label">{item.symbol} assumed contribution</span><span className="value">{amount(scenario.position_pnl[item.position_id])} {item.native_currency}</span></div>)}</div></>}</div></section>
      <section className="panel"><div className="panel-head"><h2>Hypothetical thesis risk</h2><span className="sub">Does not add a position</span></div><div className="panel-body stack"><div className="op-controls"><select className="select" aria-label="Thesis for overlay" value={thesisId} onChange={(e) => setThesisId(e.target.value)}><option value="">Select thesis</option>{theses.map((item) => <option value={item.thesis_id} key={item.thesis_id}>{item.symbol} · {category(item.detector_id)} · {item.status}</option>)}</select>
        <input className="input" aria-label="Hypothetical quantity" type="number" step="any" min="0" value={overlayQuantity} onChange={(e) => setOverlayQuantity(e.target.value)} />
        <input className="input" aria-label="Hypothetical entry USDT" type="number" step="any" min="0" placeholder="Entry/reference price" value={overlayCost} onChange={(e) => setOverlayCost(e.target.value)} />
        <input className="input" aria-label="Hypothetical invalidation USDT" type="number" step="any" min="0" placeholder="Optional explicit invalidation" value={overlayInvalidation} onChange={(e) => setOverlayInvalidation(e.target.value)} />
        <button className="button" disabled={busy || !thesisId || !overlayCost} onClick={runOverlay}>Compare before / after</button></div>
        {overlay && <div className="callout">{overlay.label} · exposure change {amount(overlay.delta_gross_exposure)} {risk.base_currency} · heat change {amount(overlay.delta_heat)} {risk.base_currency} · BTC proxy change {amount(overlay.delta_btc_sensitivity_proxy)}. Concentration before: {overlay.before.exposure.concentration_flags.join(', ') || 'none'}; after: {overlay.after.exposure.concentration_flags.join(', ') || 'none'}. What-if P/L before: {amount(overlay.before_scenario?.portfolio_pnl)}; after: {amount(overlay.after_scenario?.portfolio_pnl)} {risk.base_currency}.{overlay.after.heat_amount == null ? ' Incremental heat is unknown without valid invalidation, price and FX.' : ''}</div>}</div></section>
      <section className="panel"><div className="panel-head"><h2>Freshness, unknown risk &amp; history</h2></div><div className="panel-body stack"><div className="callout warn">{risk.warnings.length ? risk.warnings.join('; ') : 'No additional risk warning under these rules.'} Stored daily data can be stale. This snapshot describes evidence at {risk.as_of}; it is not a live risk feed.</div>
        <div className="data-list">{versions.map((item) => <div className="data-row" key={item.version}><span className="label">v{item.version} · {category(item.action)} · {item.reason}</span><span className="value">{item.recorded_at.slice(0,16)}</span></div>)}</div></div></section></>}
  </div>;
}
