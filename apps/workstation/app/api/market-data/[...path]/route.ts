import { NextRequest, NextResponse } from 'next/server';

function backend(request: NextRequest) {
  const host = new URL(`http://${request.headers.get('host') ?? request.nextUrl.host}`);
  if (!['localhost', '127.0.0.1', '[::1]'].includes(host.hostname) || host.username || host.password ||
      host.pathname !== '/' || host.search || host.hash) throw new Error('LOCAL_ONLY');
  const origin = request.headers.get('origin');
  if (origin && origin !== host.origin) throw new Error('LOCAL_ONLY');
  const value = process.env.MARKET_CORTEX_MARKET_DATA_API_URL;
  if (!value) throw new Error('INDEPENDENT_DATA_SERVICE_NOT_CONFIGURED');
  const url = new URL(value);
  if (url.protocol !== 'http:' || !['localhost', '127.0.0.1', '[::1]'].includes(url.hostname) ||
      url.username || url.password || url.pathname !== '/' || url.search || url.hash ||
      ['8765', '8001', '3000', '3002', '5432', '55432'].includes(url.port)) throw new Error('INDEPENDENT_LOOPBACK_SERVICE_REQUIRED');
  return url;
}

async function proxy(request: NextRequest, context: { params: Promise<{ path: string[] }> }) {
  try {
    const url = backend(request);
    const route = (await context.params).path.join('/');
    const permitted = request.method === 'GET' ? ['health', 'catalog', 'history', 'prices'] : ['history/fetch'];
    if (!permitted.includes(route)) return NextResponse.json({ code: 'ROUTE_NOT_AVAILABLE' }, { status: 404 });
    const body = request.method === 'POST' ? await request.text() : undefined;
    if (body && Buffer.byteLength(body, 'utf8') > 8192) return NextResponse.json({ code: 'REQUEST_TOO_LARGE' }, { status: 413 });
    const response = await fetch(new URL(`/api/v1/market-data/${route}${request.nextUrl.search}`, url), {
      method: request.method, body, headers: body ? { 'Content-Type': 'application/json' } : undefined,
      cache: 'no-store', signal: AbortSignal.timeout(60_000)
    });
    return new NextResponse(await response.text(), { status: response.status,
      headers: { 'Content-Type': 'application/json', 'Cache-Control': 'no-store' } });
  } catch (error) {
    const safe = error instanceof Error && ['LOCAL_ONLY', 'INDEPENDENT_DATA_SERVICE_NOT_CONFIGURED',
      'INDEPENDENT_LOOPBACK_SERVICE_REQUIRED'].includes(error.message) ? error.message : 'MARKET_DATA_UNAVAILABLE';
    return NextResponse.json({ code: safe }, { status: safe === 'LOCAL_ONLY' ? 403 : 503 });
  }
}
export const GET = proxy;
export const POST = proxy;
