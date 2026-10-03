import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import OpportunityPane from '../components/OpportunityPane';

vi.mock('../components/charts', () => ({ PriceChart: () => <div role="img" aria-label="stored backend bars" /> }));

const manifest = '8b5bbfd6-699d-4c40-8f9f-3377604a61ea';
const cutoff = '2026-10-02T21:54:00Z';
const candidateId = 'aaaaaaaa-aaaa-4aaa-aaaa-aaaaaaaaaaaa';
const thesisId = 'bbbbbbbb-bbbb-4bbb-bbbb-bbbbbbbbbbbb';
const instrumentId = 'cccccccc-cccc-4ccc-cccc-cccccccccccc';
const context = { source_manifest_id: manifest, as_of: cutoff,
  history_start: '2026-06-01', evaluation_date: '2026-10-01',
  members: [{ symbol: 'BTCUSDT', instrument_id: instrumentId }] };
const condition = { condition_id: 'trigger:return20:gt', kind: 'trigger', metric: 'return20',
  operator: 'gt', threshold: 0.05, observed: 0.10, met: true,
  evidence_ids: ['evidence-1'], description: '20-session return exceeds 5%' };
const candidate = { candidate_id: candidateId, symbol: 'BTCUSDT', instrument_id: instrumentId,
  detector_id: 'momentum', detector_version: '1.0.0', outcome: 'candidate', status: 'WATCHING',
  detector_strength: 'weak', event_date: '2026-10-01', as_of: cutoff,
  source_manifest_id: manifest, bias: 'bullish', market_regime: 'uptrend_other',
  market_state_id: 'state-1', evidence: [{ evidence_id: 'evidence-1', metric: 'return20',
    value: 0.10, unit: 'fraction', source_id: 'feature-1', feature_version: '1.0.0',
    quality: 'valid', freshness: 'stale', coverage: 1, reason: null }],
  trigger_conditions: [condition], confirmation_conditions: [], invalidation_conditions: [],
  rejection_conditions: [], supporting_evidence_ids: ['evidence-1'], opposing_evidence_ids: [],
  contradictions: ['FRESHNESS_OR_MARKET_STATE_PREVENTS_VALID'], rejection_reasons: [],
  coverage: 1, freshness: 'stale', data_quality: 'valid', evidence_hash: 'hash', horizon: 'swing_days_2_to_20' };
const thesis = { thesis_id: thesisId, version: 1, symbol: 'BTCUSDT', detector_id: 'momentum',
  status: 'WATCHING', statement: 'BTCUSDT momentum research', candidate_ids: [candidateId],
  source_manifest_id: manifest, as_of: cutoff, created_at: cutoff, updated_at: cutoff,
  supporting_evidence_ids: ['evidence-1'], opposing_evidence_ids: [],
  risk_factors: ['Daily-bar false positive risk'], data_limitations: [],
  confirmation_conditions: [], invalidation_conditions: [], cortex_run_ids: [], candidate,
  transitions: [{ from_status: null, to_status: 'WATCHING', at: cutoff, actor: 'detector',
    reason: 'THESIS_CREATED_FROM_RECORDED_CANDIDATE', source_manifest_id: manifest,
    changed_evidence_ids: ['evidence-1'] }] };

function mockApi() {
  let candidateRecorded = false;
  const fetcher = vi.fn(async (url: string, options?: RequestInit) => {
    const path = new URL(url, 'http://local').pathname;
    if (path.endsWith('/theses') && options?.method === 'POST' && !candidateRecorded)
      return { ok: false, status: 404, json: async () => ({ detail: { code: 'CANDIDATE_NOT_FOUND' } }) };
    if (path.endsWith('/scan') && options?.body && JSON.parse(String(options.body)).record)
      candidateRecorded = true;
    const payload = path.endsWith('/detectors') ? { items: [{ detector_id: 'momentum',
      version: '1.0.0', description: 'Momentum research', enabled: true, unsupported_reason: null }] } :
      path.endsWith('/scan') ? { scan_id: 'scan-1', source_manifest_id: manifest, as_of: cutoff,
        market_regime: 'uptrend_other', counts: { candidate: 1, rejected: 0, insufficient_data: 0, unsupported: 0 },
        elapsed_ms: 42, recorded_events: options?.body && JSON.parse(String(options.body)).record ? 1 : 0,
        candidates: [candidate] } :
      path.endsWith('/candidates') ? { items: [] } :
      path.endsWith('/theses') && options?.method === 'POST' ? thesis :
      path.endsWith('/theses') ? { items: [thesis] } :
      path.endsWith('/review') ? { review_status: 'GROUNDED_RESEARCH_ATTACHED', thesis,
        run: { answer: 'Recorded candidate evidence, with a contradiction.' } } :
      path.endsWith('/monitor') ? thesis :
      path.includes('/instrument/') ? { bars: [], features: {} } : {};
    return { ok: true, status: 200, json: async () => payload };
  });
  vi.stubGlobal('fetch', fetcher);
  return fetcher;
}

describe('Phase 5 opportunity workstation', () => {
  it('pins the scan, exposes conditions and creates a structured thesis', async () => {
    const fetcher = mockApi();
    render(<OpportunityPane context={context as never} mode="historical" watchlistIds={[instrumentId]} />);
    expect(await screen.findByText('Detector results')).toBeInTheDocument();
    const scanCall = fetcher.mock.calls.find(([url]) => String(url).endsWith('/scan'))!;
    expect(JSON.parse(String(scanCall[1]?.body))).toMatchObject({ mode: 'historical',
      manifest_id: manifest, as_of: cutoff, record: false });
    expect(screen.getByText('★ WATCHLIST')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Inspect' }));
    expect(screen.getByText('20-session return exceeds 5%')).toBeInTheDocument();
    expect(screen.getByText(/FRESHNESS_OR_MARKET_STATE_PREVENTS_VALID/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Record & create thesis' }));
    await waitFor(() => expect(screen.getByText('Structured thesis board')).toBeInTheDocument());
    const recorded = fetcher.mock.calls.find(([url, options]) => String(url).endsWith('/scan') &&
      Boolean(options?.body && JSON.parse(String(options.body)).record));
    expect(recorded).toBeTruthy();
    expect(fetcher.mock.calls.some(([url]) => String(url).endsWith('/theses'))).toBe(true);
  });

  it('shows thesis history and grounds CORTEX review through the local endpoint', async () => {
    const fetcher = mockApi();
    render(<OpportunityPane context={context as never} mode="pinned" watchlistIds={[]} />);
    fireEvent.click(await screen.findByRole('button', { name: /Thesis board/ }));
    fireEvent.click(screen.getByRole('button', { name: 'Open' }));
    expect(screen.getByText(/THESIS_CREATED_FROM_RECORDED_CANDIDATE/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'CORTEX evidence review' }));
    expect(await screen.findByText(/Recorded candidate evidence, with a contradiction/)).toBeInTheDocument();
    expect(fetcher.mock.calls.some(([url]) => String(url).endsWith(`/theses/${thesisId}/review`))).toBe(true);
  });
});
