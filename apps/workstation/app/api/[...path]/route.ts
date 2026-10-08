import { NextRequest, NextResponse } from 'next/server';

const allowed = /^v1\/(health|features(?:\/(?:series|compute))?|workstation\/(?:context|overview|comparison|instrument\/[0-9a-f-]{36}|manifest\/[0-9a-f-]{36})|cortex\/(?:status|tools|runs(?:\/[0-9a-f-]{36}(?:\/replay)?)?)|opportunities\/(?:detectors|candidates(?:\/[0-9a-f-]{36})?|theses(?:\/[0-9a-f-]{36}(?:\/(?:versions|comparison))?)?)|risk\/(?:portfolios(?:\/[0-9a-f-]{36}(?:\/versions)?)?|snapshots\/[0-9a-f-]{36}))$/;
const postAllowed = /^v1\/(?:cortex\/research|opportunities\/(?:scan|theses(?:\/[0-9a-f-]{36}\/(?:monitor|decision|review))?)|risk\/(?:portfolios(?:\/[0-9a-f-]{36}\/(?:positions|calculate|scenario|overlay))?|sizing|theses\/[0-9a-f-]{36}\/risk))$/;

function localHost(request: NextRequest) {
  try {
    const host = new URL(`http://${request.headers.get('host') ?? request.nextUrl.host}`);
    return ['127.0.0.1', '[::1]', 'localhost'].includes(host.hostname) && !host.username && !host.password
      && host.pathname === '/' && !host.search && !host.hash
      && ['127.0.0.1', '[::1]', 'localhost'].includes(request.nextUrl.hostname);
  } catch { return false; }
}

function backendUrl() {
  try {
    const backend = new URL(process.env.MARKET_CORTEX_API_URL ?? 'http://127.0.0.1:8765');
    if (backend.protocol !== 'http:' || !['127.0.0.1', '[::1]', 'localhost'].includes(backend.hostname)
        || backend.username || backend.password || backend.pathname !== '/' || backend.search || backend.hash) return null;
    return backend;
  } catch { return null; }
}

const learningGet = /^v1\/learning\/(?:journal(?:\/[0-9a-f-]{36}(?:\/revisions)?)?|predictions(?:\/[0-9a-f-]{36}(?:\/postmortem)?)?|evaluations\/[0-9a-f-]{36}|review-queue|performance|failures|edges|links)$/;
const learningPost = /^v1\/learning\/(?:journal(?:\/[0-9a-f-]{36}\/revisions)?|predictions(?:\/[0-9a-f-]{36}\/(?:evaluate|cancel))?|evaluate-due|edges)$/;
const quantGet = /^v1\/quant\/(?:strategies|runs(?:\/[0-9a-f-]{36}(?:\/(?:trades|metrics))?)?|studies(?:\/[0-9a-f-]{36})?|jobs\/[0-9a-f-]{36})$/;
const quantPost = /^v1\/quant\/(?:jobs(?:\/[0-9a-f-]{36}\/retry)?|runs\/[0-9a-f-]{36}\/replay|edges\/evidence)$/;
const intelligenceGet = /^v1\/intelligence\/(?:context|coverage|compare|facts\/[0-9a-f-]{36}|snapshots\/[0-9a-f-]{36}|domains\/(?:macro|events|news|derivatives|fundamentals|options|onchain))$/;
const intelligencePost = /^v1\/intelligence\/event-study$/;
const missionsGet = /^v1\/cortex\/missions(?:\/(?:status|tools|templates|[0-9a-f-]{36}(?:\/(?:plan|evidence|hypotheses|report|history|diff))?))?$/;
const missionsPost = /^v1\/cortex\/missions(?:\/[0-9a-f-]{36}\/(?:execute|cancel|resume|replay))?$/;

const personalGet = /^v1\/personalization\/(?:profile|memories(?:\/[0-9a-f-]{36}(?:\/history)?)?|proposals|export|tools(?:\/personal\.[a-z_]+)?|snapshots\/[0-9a-f-]{36}|missions\/[0-9a-f-]{36}\/review)$/;
const personalPost = /^v1\/personalization\/(?:refresh|preferences|feedback|attestations|query|memories\/[0-9a-f-]{36}\/action|proposals\/[0-9a-f-]{36}\/action|missions(?:\/[0-9a-f-]{36}\/replay)?)$/;

const experimentalGet = /^v1\/experimental\/(?:registry|hypotheses(?:\/[0-9a-f-]{36})?|experiments(?:\/[0-9a-f-]{36}(?:\/(?:history|result|dataset|governance|reports\/[a-z_]+))?)?|artifacts\/[0-9a-f-]{36}|jobs\/[0-9a-f-]{36}|ledger|edges\/evidence|tools)$/;
const experimentalPost = /^v1\/experimental\/(?:hypotheses|experiments(?:\/[0-9a-f-]{36}\/(?:jobs|replay))?|jobs\/[0-9a-f-]{36}\/(?:cancel|retry)|compare|analogues|proposals|governance|edges\/evidence|query|missions|dossiers\/[0-9a-f-]{36}\/replay)$/;

export async function GET(request: NextRequest, context: { params: Promise<{ path: string[] }> }) {
  if (!localHost(request)) return NextResponse.json({ code: 'LOCAL_ONLY' }, { status: 403 });
  const { path } = await context.params;
  const route = path.join('/');
  if (!allowed.test(route) && !/^v1\/operations\/(?:status|preflight)$/.test(route) && !learningGet.test(route) && !quantGet.test(route) && !intelligenceGet.test(route) && !missionsGet.test(route) && !personalGet.test(route) && !experimentalGet.test(route)) return NextResponse.json({ code: 'ROUTE_NOT_AVAILABLE' }, { status: 404 });
  const backend = backendUrl();
  if (!backend) {
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

export async function POST(request: NextRequest, context: { params: Promise<{ path: string[] }> }) {
  if (!localHost(request)) return NextResponse.json({ code: 'LOCAL_ONLY' }, { status: 403 });
  const origin = request.headers.get('origin');
  const incomingOrigin = new URL(`http://${request.headers.get('host') ?? request.nextUrl.host}`).origin;
  if (origin && origin !== incomingOrigin) return NextResponse.json({ code: 'UNTRUSTED_LOCAL_ORIGIN' }, { status: 403 });
  const { path } = await context.params;
  const route = path.join('/');
  if (!postAllowed.test(route) && !learningPost.test(route) && !quantPost.test(route) && !intelligencePost.test(route) && !missionsPost.test(route) && !personalPost.test(route) && !experimentalPost.test(route)) return NextResponse.json({ code: 'ROUTE_NOT_AVAILABLE' }, { status: 404 });
  const backend = backendUrl();
  if (!backend) return NextResponse.json({ code: 'BACKEND_MUST_BE_LOOPBACK' }, { status: 503 });
  const body = await request.text();
  if (Buffer.byteLength(body, 'utf8') > (route.startsWith('v1/learning/') ? 48000 : 8192)) return NextResponse.json({ code: 'REQUEST_TOO_LARGE' }, { status: 413 });
  try {
    const response = await fetch(new URL(`/api/${route}`, backend), {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body,
      cache: 'no-store', signal: AbortSignal.timeout(60_000)
    });
    return new NextResponse(await response.text(), { status: response.status,
      headers: { 'Content-Type': 'application/json', 'Cache-Control': 'no-store' } });
  } catch {
    return NextResponse.json({ code: 'BACKEND_UNAVAILABLE', retryable: true }, { status: 503 });
  }
}
