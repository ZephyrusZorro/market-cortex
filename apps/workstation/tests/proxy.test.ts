import { afterEach, describe, expect, it, vi } from 'vitest';
import { NextRequest } from 'next/server';
import { GET, POST } from '../app/api/[...path]/route';

afterEach(() => { vi.unstubAllEnvs(); vi.unstubAllGlobals(); });
const context = { params: Promise.resolve({ path: ['v1', 'cortex', 'research'] }) };
describe('local write proxy', () => {
  it('accepts the incoming loopback origin when Next internally uses localhost', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ status: 200, text: async () => '{}' }));
    const request = new NextRequest('http://localhost:3000/api/v1/cortex/research', { method: 'POST',
      headers: { host: '127.0.0.1:3000', origin: 'http://127.0.0.1:3000' }, body: '{}' });
    expect((await POST(request, context)).status).toBe(200);
  });
  it('rejects rebinding Host headers on private reads', async () => {
    const fetch = vi.fn(); vi.stubGlobal('fetch', fetch);
    const request = new NextRequest('http://127.0.0.1:3000/api/v1/health', { headers: { host: 'evil.example' } });
    expect((await GET(request, { params: Promise.resolve({ path: ['v1', 'health'] }) })).status).toBe(403);
    expect(fetch).not.toHaveBeenCalled();
  });
  it('rejects foreign browser origins before touching the backend', async () => {
    const fetch = vi.fn(); vi.stubGlobal('fetch', fetch);
    const request = new NextRequest('http://127.0.0.1:3000/api/v1/cortex/research', {
      method: 'POST', headers: { origin: 'https://evil.example' }, body: '{}' });
    expect((await POST(request, context)).status).toBe(403);
    expect(fetch).not.toHaveBeenCalled();
  });
  it.each(['http://user:secret@127.0.0.1:8765', 'http://127.0.0.1:8765?secret=x', 'invalid'])('rejects unsafe backend configuration', async value => {
    vi.stubEnv('MARKET_CORTEX_API_URL', value);
    const request = new NextRequest('http://127.0.0.1:3000/api/v1/health');
    const result = await GET(request, { params: Promise.resolve({ path: ['v1', 'health'] }) });
    expect(result.status).toBe(503);
  });
  it('bounds UTF8 request bytes and never forwards an oversized body', async () => {
    const fetch = vi.fn(); vi.stubGlobal('fetch', fetch);
    const request = new NextRequest('http://127.0.0.1:3000/api/v1/cortex/research', {
      method: 'POST', body: '₹'.repeat(3000) });
    expect((await POST(request, context)).status).toBe(413);
    expect(fetch).not.toHaveBeenCalled();
  });
  it('reports backend absence without exposing exception details', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('secret connection detail')));
    const request = new NextRequest('http://127.0.0.1:3000/api/v1/health');
    const result = await GET(request, { params: Promise.resolve({ path: ['v1', 'health'] }) });
    expect(result.status).toBe(503);
    expect(await result.json()).toEqual({ code: 'BACKEND_UNAVAILABLE', retryable: true });
  });
});
