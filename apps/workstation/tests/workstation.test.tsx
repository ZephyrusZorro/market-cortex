import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import Workstation from '../components/Workstation';

vi.mock('../components/charts', () => ({
  PriceChart: () => <div role="img" aria-label="backend candle chart" />,
  SeriesChart: () => <div role="img" aria-label="backend series chart" />
}));

const manifest = '8b5bbfd6-699d-4c40-8f9f-3377604a61ea';
const old = 'bbc98286-3136-4ff4-9602-e6d8065570c5';
const ids = ['dbe1c9c1-a1c1-4c95-b74c-1973f640a462', 'e7069c4c-2d48-49fd-85ef-55bbda6d22c2',
  'eb97fc2c-34c8-441b-b4c9-5792343ab55d', '982aa9ce-e6c8-4dee-958a-dd5c5a6d6340',
  '294adbc0-32da-415e-b5c1-c219193d8953'];
const symbols = ['BTCUSDT','ETHUSDT','SOLUSDT','BNBUSDT','XRPUSDT'];
const members = symbols.map((symbol, i) => ({ symbol, instrument_id: ids[i], currency: 'USDT',
  venue_id: 'BINANCE_SPOT', first_session: '2025-09-01', last_session: '2026-10-01',
  observed_sessions: 396, status: 'available' }));
const context = { universe_id: 'binance_pilot_5', universe_label: 'Binance Pilot 5',
  source_manifest_id: manifest, head_manifest_id: manifest, as_of: '2026-10-02T21:54:00Z',
  evaluation_date: '2026-10-01', history_start: '2025-09-01',
  manifest: { manifest_id: manifest, parent_manifest_id: old, created_at: '2026-10-03T00:00:00Z',
    schema_version: '1', selection_policy_version: 'all_providers_v1' },
  recent_manifests: [{ manifest_id: manifest, parent_manifest_id: old, created_at: '2026-10-03T00:00:00Z' },
    { manifest_id: old, parent_manifest_id: null, created_at: '2026-10-03T00:00:00Z' }],
  members, providers: [{ provider_id: 'binance', label: 'Binance public daily bars', status: 'VALIDATED_PUBLIC',
    credential_state: 'PUBLIC_NO_CREDENTIAL', interval: 'P1D' },
    { provider_id: 'upstox', label: 'Upstox adapter', status: 'DEFERRED_NOT_CONFIGURED', credential_state: 'NOT_CONFIGURED', interval: 'P1D' },
    { provider_id: 'alpaca', label: 'Alpaca adapter', status: 'DEFERRED_NOT_CONFIGURED', credential_state: 'NOT_CONFIGURED', interval: 'P1D' }],
  display: { primary_currency: 'INR', secondary_currency: 'USD', native_prices_only: true, timezone: 'Asia/Kolkata' } };
const featureValue = (name: string, value: number) => ({ feature_id: `${name}-id`, name, value, reason: null, unit: 'fraction',
  version: '1.0.0', calculation_version: 'daily_float64_v1', parameters: {}, observed_sessions: 396,
  expected_sessions: 396, freshness: 'current', source_manifest_id: manifest });
const items = members.map((member) => ({ ...member, session_date: '2026-10-01', close: 84880.05,
  observation_id: 'obs', quality: 'valid', freshness: 'current', features: {
    arithmetic_return: featureValue('arithmetic_return', .015), rolling_return: featureValue('rolling_return', .099),
    rsi: featureValue('rsi', 64.8), annualized_volatility: featureValue('annualized_volatility', .42) } }));
const dimensions = ['trend','momentum','volatility','breadth','relative_strength','correlation_state',
  'market_participation','data_freshness','uncertainty'].map((name) => ({ name, category: name === 'data_freshness' ? 'current' : 'mixed',
    metrics: { observed: 5 }, evidence_refs: ['feature-id'], scope: 'binance_pilot_5', timeframe: 'P1D',
    source_manifest_id: manifest, rule_version: 'market_state_rules_v1', eligible_members: 5, total_members: 5,
    freshness: 'current', unknown_reason: null }));
const state = { snapshot_id: 'snapshot-id', source_manifest_id: manifest, calculation_version: 'market_state_rules_v1',
  request: { as_of: context.as_of, history_start: context.history_start, evaluation_date: context.evaluation_date },
  dimensions, breadth: null, regime: { category: 'mixed', rules_fired: ['R7_MIXED_OR_DISAGREEING_DIMENSIONS'],
    evidence_refs: ['feature-id'], rule_version: 'regime_rules_v1', unknown_reason: null }, missing_members: [] };
const definition = { name: 'rsi', version: '1.0.0', calculation_version: 'daily_float64_v1',
  calculation_code_hash: 'hash', description: 'Wilder RSI; flat run is 50', required_inputs: ['close'],
  parameter_defaults: { period: 14 }, min_history: 'period + 1 bars', default_min_history: 15,
  unit: 'index_0_100', supported_intervals: ['P1D'] };

function mockApi() {
  const fetcher = vi.fn(async (url: string) => {
    const path = new URL(url, 'http://local').pathname;
    let payload: unknown;
    if (path.endsWith('/health')) payload = { status: 'ready' };
    else if (path.endsWith('/context')) payload = context;
    else if (path.endsWith('/overview')) payload = { context, items, state };
    else if (path.endsWith('/features')) payload = { items: [definition] };
    else if (path.endsWith('/features/series')) payload = { feature_id: 'rsi-id', definition,
      source_manifest_id: manifest, request: { as_of: context.as_of }, resolved_parameters: { period: 14 },
      expected_sessions: 396, observed_sessions: 396, freshness: 'current', missing_sessions: [],
      points: [{ session_date: '2026-10-01', value: 64.8, reason: null, observation_id: 'obs', input_quality: 'valid' }] };
    else payload = {};
    return { ok: true, status: 200, json: async () => payload };
  });
  vi.stubGlobal('fetch', fetcher);
  return fetcher;
}

describe('research workstation', () => {
  it('shows a loading state before the catalog responds', () => {
    vi.stubGlobal('fetch', vi.fn(() => new Promise(() => {})));
    render(<Workstation />);
    expect(screen.getByText(/Loading pinned research data/)).toBeInTheDocument();
  });
  it('shows the five-pair universe and rule-backed market state', async () => {
    mockApi(); render(<Workstation />);
    expect(await screen.findByRole('heading', { name: 'Market overview' })).toBeInTheDocument();
    expect(screen.getAllByText('84,880.05').length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText('Binance Pilot 5', { exact: false }).length).toBeGreaterThanOrEqual(1);
    fireEvent.click(screen.getByRole('button', { name: /Market State/ }));
    expect(screen.getByText('R7_MIXED_OR_DISAGREEING_DIMENSIONS')).toBeInTheDocument();
  });
  it('makes deferred provider coverage explicit', async () => {
    mockApi(); render(<Workstation />);
    await screen.findByRole('heading', { name: 'Market overview' });
    fireEvent.click(screen.getByRole('button', { name: /Data & Coverage/ }));
    expect(screen.getByText('Upstox adapter')).toBeInTheDocument();
    expect(screen.getByText('Alpaca adapter')).toBeInTheDocument();
    expect(screen.getAllByText(/DEFERRED NOT CONFIGURED/).length).toBeGreaterThanOrEqual(2);
  });
  it('sends an explicit old manifest in pinned mode', async () => {
    const fetcher = mockApi(); render(<Workstation />);
    await screen.findByRole('heading', { name: 'Market overview' });
    fireEvent.click(screen.getByRole('button', { name: 'Change context' }));
    fireEvent.click(screen.getByRole('button', { name: 'pinned' }));
    fireEvent.change(screen.getByLabelText('Manifest'), { target: { value: old } });
    fireEvent.click(screen.getByRole('button', { name: /Open research context/ }));
    await waitFor(() => expect(fetcher.mock.calls.some(([url]) => String(url).includes(`manifest_id=${old}`))).toBe(true));
    expect(screen.getByText('Pinned research mode')).toBeInTheDocument();
  });
  it('converts the IST cutoff to UTC in historical mode', async () => {
    const fetcher = mockApi(); render(<Workstation />);
    await screen.findByRole('heading', { name: 'Market overview' });
    fireEvent.click(screen.getByRole('button', { name: 'Change context' }));
    fireEvent.click(screen.getByRole('button', { name: 'historical' }));
    fireEvent.change(screen.getByLabelText('As-of cutoff · local time'), { target: { value: '2026-10-03 03:24' } });
    fireEvent.click(screen.getByRole('button', { name: /Open research context/ }));
    await waitFor(() => expect(fetcher.mock.calls.some(([url]) => decodeURIComponent(String(url)).includes('as_of=2026-10-02T21:54:00.000Z'))).toBe(true));
    expect(screen.getByText('Historical research mode')).toBeInTheDocument();
  });
  it('loads registry definitions and searches the Feature Explorer', async () => {
    mockApi(); render(<Workstation />);
    await screen.findByRole('heading', { name: 'Market overview' });
    fireEvent.click(screen.getByRole('button', { name: /Feature Explorer/ }));
    fireEvent.click(await screen.findByRole('button', { name: /rsi Wilder/ }));
    fireEvent.change(screen.getByLabelText('Search features'), { target: { value: 'rsi' } });
    expect(screen.getByText('1 matching definitions')).toBeInTheDocument();
    await waitFor(() => expect(screen.getByText('64.8')).toBeInTheDocument());
  });
  it('shows a local backend failure without invented market values', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => { throw new TypeError('network down'); }));
    render(<Workstation />);
    expect((await screen.findAllByText('BACKEND UNAVAILABLE')).length).toBeGreaterThanOrEqual(1);
    expect(screen.queryByText('84,880.05')).not.toBeInTheDocument();
  });
});
