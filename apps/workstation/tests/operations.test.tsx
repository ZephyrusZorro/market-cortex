import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import OperationalStatus from '../components/OperationalStatus';
import { getJson } from '../lib/api';
vi.mock('../lib/api', () => ({ getJson: vi.fn() }));
describe('operational status', () => {
  it('keeps refresh history separate from historical context and reports failed jobs', async () => {
    vi.mocked(getJson).mockResolvedValue({ environment: 'PILOT_TEST', expected_closed_session: '2026-10-07',
      items: [{ instrument_id: 'i', last_session: '2026-10-03', freshness: 'STALE' }],
      jobs: [{ job_id: 'j', symbol: 'BTCUSDT', state: 'dead', attempts: 3, error_code: 'RATE_LIMITED', next_attempt_at: '2026-10-08' }] });
    render(<OperationalStatus />);
    expect(await screen.findByText(/0\/1 instruments fresh/)).toBeInTheDocument();
    expect(screen.getByText('RATE_LIMITED')).toBeInTheDocument();
    expect(screen.getByText(/independent of pinned historical research/)).toBeInTheDocument();
    expect(screen.getByText(/does not start ingestion/)).toBeInTheDocument();
  });
  it('reports unavailable diagnostics without inventing success', async () => {
    vi.mocked(getJson).mockRejectedValue(new Error('offline'));
    render(<OperationalStatus />);
    expect(await screen.findByRole('alert')).toHaveTextContent('Operational diagnostics unavailable');
  });
});
