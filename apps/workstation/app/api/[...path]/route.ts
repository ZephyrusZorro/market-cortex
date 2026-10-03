import { NextRequest, NextResponse } from 'next/server';

const allowed = /^v1\/(health|features(?:\/(?:series|compute))?|workstation\/(?:context|overview|comparison|instrument\/[0-9a-f-]{36}|manifest\/[0-9a-f-]{36}))$/;

export async function GET(request: NextRequest, context: { params: Promise<{ path: string[] }> }) {
  const { path } = await context.params;
  const route = path.join('/');
  if (!allowed.test(route)) return NextResponse.json({ code: 'ROUTE_NOT_AVAILABLE' }, { status: 404 });
  const backend = new URL(process.env.MARKET_CORTEX_API_URL ?? 'http://127.0.0.1:8765');
  if (!['127.0.0.1', '::1', '[::1]', 'localhost'].includes(backend.hostname)) {
    return NextResponse.json({ code: 'BACKEND_MUST_BE_LOOPBACK' }, { status: 503 });
  }
  const target = new URL(`/api/${route}${request.nextUrl.search}`, backend);
  try {
    const response = await fetch(target, { cache: 'no-store', signal: AbortSignal.timeout(45_000) });
    return new NextResponse(await response.text(), {
      status: response.status,
      headers: { 'Content-Type': 'application/json', 'Cache-Control': 'no-store' }
    });
  } catch {
    return NextResponse.json({ code: 'BACKEND_UNAVAILABLE', retryable: true }, { status: 503 });
  }
}
