import { describe, expect, it, vi } from 'vitest';
import { ApiError, appendParams, contextParams, getJson, pinnedParams } from '../lib/api';

describe('research API client', () => {
  it('pins every downstream query to the resolved manifest and cutoff', () => {
    const context = { source_manifest_id: 'manifest-1', as_of: '2026-10-02T21:54:00+00:00' };
    const query = appendParams(pinnedParams(context as never), { from: '2025-09-01', to: '2026-10-01' });
    expect(query.get('manifest_id')).toBe('manifest-1');
    expect(query.get('as_of')).toBe(context.as_of);
    expect(query.get('from')).toBe('2025-09-01');
  });
  it('omits moving head controls in latest mode and includes historical as-of only when selected', () => {
    expect(contextParams({ mode: 'latest' }).size).toBe(0);
    expect(contextParams({ mode: 'pinned', manifestId: 'old' }).get('manifest_id')).toBe('old');
    const old = contextParams({ mode: 'historical', manifestId: 'old', asOf: '2026-01-01T00:00:00Z' });
    expect(old.get('as_of')).toBe('2026-01-01T00:00:00Z');
  });
  it('retains a backend error code instead of substituting a zero', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => ({ ok: false, status: 404,
      json: async () => ({ detail: { code: 'MANIFEST_NOT_FOUND' } }) })));
    await expect(getJson('workstation/context')).rejects.toEqual(new ApiError('MANIFEST_NOT_FOUND', 404));
  });
});
