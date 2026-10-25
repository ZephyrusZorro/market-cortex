import type { ChartBar } from './api';

export type NativeInstrument = { provider: string; native_id: string; symbol: string; name: string;
  exchange: string; market: string; currency: string; status: string; present: boolean; live_entitlement: string };
export type SourceCandle = { start_at: string; end_at: string; available_at: string; open: string;
  high: string; low: string; close: string; volume: string; currency: string; source_hash: string; feed: string;
  adjustment_basis: string; volume_unit?: string; interval?: string };
export type PriceEvent = { native_id: string; price: string | null; bid: string | null; ask: string | null;
  event_at: string; received_at: string; feed: string; state: 'LIVE' | 'DELAYED' | 'STALE' | 'UNAVAILABLE';
  source_hash: string; is_final: boolean; candle: null | { interval: string; start_at: string; end_at: string;
    open: string; high: string; low: string; close: string; volume: string } };

export function historyWindow(provider: string, interval: string, days: number, now = new Date()) {
  // Match the independent source service's finalization grace. A declared UTC
  // boundary alone does not prove the public REST mirror has its final values.
  if(provider==='binance')now=new Date(now.getTime()-10_000);
  if(provider==='binance' && interval==='1M') {
    const end=new Date(Date.UTC(now.getUTCFullYear(),now.getUTCMonth(),1));
    return {start:new Date(Date.UTC(end.getUTCFullYear(),end.getUTCMonth()-Math.max(1,Math.floor(days/30)),1)),end};
  }
  if(provider==='binance' && interval==='1w') {
    const end=new Date(Date.UTC(now.getUTCFullYear(),now.getUTCMonth(),now.getUTCDate()));
    end.setUTCDate(end.getUTCDate()-(end.getUTCDay()+6)%7);
    return {start:new Date(end.getTime()-Math.max(1,Math.floor(days/7))*7*86400000),end};
  }
  const seconds: Record<string, number> = { '1m':60,'5m':300,'15m':900,'1h':3600,'4h':14400,'1d':86400 };
  // Binance bars start on UTC boundaries. A rolling daily start omits the
  // first requested session and produces 29 candles for a 30-day selection.
  const step = provider === 'binance' ? seconds[interval] : undefined;
  const end = new Date(step ? Math.floor(now.getTime()/(step*1000))*step*1000 : now.getTime());
  return { start:new Date(end.getTime()-days*86400000), end };
}

export function chartBars(rows: SourceCandle[]): ChartBar[] {
  return rows.map(row => {
    const values = ['open', 'high', 'low', 'close', 'volume'].map(key => {
      const value = row[key as keyof SourceCandle];
      if (typeof value !== 'string' || !value.trim() || !/^[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?$/.test(value))
        throw new Error('INVALID_SOURCE_CANDLE');
      return Number(value);
    });
    if (values.some(v => !Number.isFinite(v) || v < 0) || values[2] > Math.min(values[0], values[3]) ||
      values[1] < Math.max(values[0], values[3])) throw new Error('INVALID_SOURCE_CANDLE');
    return { session_date: row.start_at, open: values[0], high: values[1], low: values[2], close: values[3],
      volume: values[4], observation_id: `${row.source_hash}:${row.start_at}`, source_batch_id: row.source_hash,
      available_at: row.available_at, quality: 'SOURCE_SAMPLE', currency: row.currency };
  });
}

export function chartWithStream(rows: SourceCandle[], event: PriceEvent | null, interval: string, currency: string) {
  const series = new Map(rows.map(row => [row.start_at, row]));
  if (event?.candle && event.candle.interval === interval && ['LIVE','DELAYED'].includes(event.state)) {
    const existing=series.get(event.candle.start_at);
    const sample = { ...event.candle, available_at: event.received_at, currency, source_hash: event.source_hash,
      feed: event.feed, adjustment_basis: event.feed.startsWith('v3_')?'provider_unspecified':'raw' };
    // A real stream candle may update the display. It never replaces stored research evidence.
    // An older provisional stream sample cannot replace a later REST close.
    if (!existing || Date.parse(event.received_at)>=Date.parse(existing.available_at)) series.set(sample.start_at, sample);
  }
  return chartBars([...series.values()].sort((a,b)=>a.start_at.localeCompare(b.start_at)));
}

export async function marketJson<T>(path: string, init?: RequestInit): Promise<T> {
  for(let attempt=0;attempt<5;attempt++) {
    const response = await fetch(`/api/market-data/${path}`, { cache: 'no-store', ...init });
    const result = await response.json();
    if(response.ok)return result;
    const code=result.code ?? result.detail?.code ?? 'MARKET_DATA_UNAVAILABLE';
    // Only retry local admission contention. Provider/network failures retain
    // their own bounded backend policy and are never retried indefinitely.
    if(!['HISTORY_REQUEST_BUSY','ARCHIVE_WRITER_BUSY'].includes(code)||attempt===4)throw new Error(code);
    await new Promise<void>((resolve,reject)=>{
      if(init?.signal?.aborted){reject(new Error('REQUEST_CANCELLED'));return;}
      const abort=()=>{clearTimeout(timer);reject(new Error('REQUEST_CANCELLED'));};
      const timer=setTimeout(()=>{init?.signal?.removeEventListener('abort',abort);resolve();},300*2**attempt);
      init?.signal?.addEventListener('abort',abort,{once:true});
    });
  }
  throw new Error('HISTORY_REQUEST_BUSY');
}
