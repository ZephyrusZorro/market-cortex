import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import CortexPane from '../components/CortexPane';

const manifest = '8b5bbfd6-699d-4c40-8f9f-3377604a61ea';
const cutoff = '2026-10-02T21:54:00Z';
const context = { source_manifest_id: manifest, as_of: cutoff,
  members: [{ symbol: 'BTCUSDT', instrument_id: 'dbe1c9c1-a1c1-4c95-b74c-1973f640a462' },
    { symbol: 'ETHUSDT', instrument_id: 'e7069c4c-2d48-49fd-85ef-55bbda6d22c2' }],
  recent_manifests: [] };
const evidence = (id: string, label: string, value: number) => ({ evidence_id: id,
  tool_id: 'instrument.features', kind: 'feature', label, symbol: 'BTCUSDT', value,
  unit: 'index', session_date: '2026-10-01', manifest_id: manifest, as_of: cutoff,
  source_id: 'feature-id', version: '1.0.0', parameters: { period: 14 }, observation_id: 'obs',
  quality: 'valid', freshness: 'stale', coverage: 1, reason: null });
const first = evidence('11111111111111111111', 'Latest stored close', 84880.05);
const second = evidence('22222222222222222222', 'rsi(14)', 64.8);
const run = { run_id: 'aaaaaaaa-aaaa-4aaa-aaaa-aaaaaaaaaaaa', created_at: cutoff,
  context: { mode: 'latest', manifest_id: manifest, as_of: cutoff, symbol: 'BTCUSDT',
    compare_symbol: null, environment: 'PILOT_TEST', evaluation_date: '2026-10-01' },
  tools: [{ tool_id: 'instrument.features', version: '1.0.0', description: 'features',
    inputs: { manifest_id: manifest, as_of: cutoff }, status: 'ok', evidence: [first, second],
    output_hash: 'abc', elapsed_ms: 4 }],
  claims: [{ claim_id: 'claim-1', type: 'CALCULATION', text: 'BTC RSI14 was 64.8.',
    evidence_ids: [second.evidence_id], stance: 'neutral' }], evidence_strength: 'weak',
  answer: `Evidence\n- BTC RSI14 was 64.8. [${second.evidence_id}]\n\nCounter-evidence\n- None`,
  warnings: [], failure_state: null, model_provider: 'deterministic', model_id: null,
  model_status: 'no_model_configured', model_latency_ms: 0, evidence_hash: 'abc' };

describe('CORTEX workstation', () => {
  it('sends explicit market context and makes citations inspectable with no model', async () => {
    const fetcher = vi.fn(async (url: string, options?: RequestInit) => {
      const path = new URL(url, 'http://local').pathname;
      const payload = path.endsWith('/status') ? { status: 'ready', environment: 'PILOT_TEST',
        model_provider: 'deterministic', deterministic_fallback: true } :
        path.endsWith('/runs') ? { items: [] } : path.endsWith('/research') ? run : {};
      return { ok: true, status: 200, json: async () => payload };
    });
    vi.stubGlobal('fetch', fetcher);
    render(<CortexPane context={context as never} mode="latest" symbol="BTCUSDT" />);
    expect(await screen.findByText('PILOT_TEST')).toBeInTheDocument();
    expect((screen.getByLabelText('Ask CORTEX') as HTMLTextAreaElement).value).toBe('Analyze BTCUSDT.');
    fireEvent.click(screen.getByRole('button', { name: /Ask CORTEX/ }));
    await screen.findByText(/Saved run/);
    const call = fetcher.mock.calls.find(([url]) => String(url).endsWith('/research'))!;
    const body = JSON.parse((call[1] as RequestInit).body as string);
    expect(body).toMatchObject({ mode: 'latest', manifest_id: manifest, as_of: cutoff,
      symbol: 'BTCUSDT', depth: 'deep' });
    expect(screen.getByText(/no_model_configured/)).toBeInTheDocument();
    expect(screen.getByText('84880.05')).toBeInTheDocument();
    fireEvent.click(screen.getAllByRole('button', { name: '[22222222]' })[0]);
    expect(screen.getByText('64.8')).toBeInTheDocument();
    expect(screen.getByText('rsi(14)')).toBeInTheDocument();
  });

  it('shows failed research without inventing market values', async () => {
    vi.stubGlobal('fetch', vi.fn(async (url: string) => {
      const path = new URL(url, 'http://local').pathname;
      if (path.endsWith('/research')) return { ok: false, status: 503,
        json: async () => ({ detail: { code: 'SERVICE_UNAVAILABLE' } }) };
      return { ok: true, status: 200, json: async () => path.endsWith('/runs') ? { items: [] } :
        { status: 'ready', environment: 'PILOT_TEST', model_provider: 'deterministic' } };
    }));
    render(<CortexPane context={context as never} mode="latest" symbol="BTCUSDT" />);
    fireEvent.click(screen.getByRole('button', { name: /Ask CORTEX/ }));
    await waitFor(() => expect(screen.getByText('SERVICE UNAVAILABLE')).toBeInTheDocument());
    expect(screen.queryByText('84880.05')).not.toBeInTheDocument();
  });
});
