import { describe, expect, it, vi, afterEach } from 'vitest';
import { chartBars, chartWithStream, historyWindow, marketJson, type SourceCandle, type PriceEvent } from '../lib/market-data';
import { GET, POST } from '../app/api/market-data/[...path]/route';
import { NextRequest } from 'next/server';

const candle: SourceCandle = { start_at:'2026-10-10T00:00:00+00:00',end_at:'2026-10-11T00:00:00+00:00',
  available_at:'2026-10-11T12:00:00+00:00',open:'1',high:'3',low:'0.5',close:'2',volume:'100',currency:'USDT',
  source_hash:'hash',feed:'spot_public',adjustment_basis:'raw' };
afterEach(()=>{vi.unstubAllGlobals();vi.unstubAllEnvs();vi.useRealTimers();});

describe('genuine market data chart boundary',()=>{
  it('requests thirty complete UTC daily sessions rather than twenty-nine rolling sessions',()=>{
    const range=historyWindow('binance','1d',30,new Date('2026-10-12T03:45:00Z'));
    expect(range.end.toISOString()).toBe('2026-10-12T00:00:00.000Z');
    expect(range.start.toISOString()).toBe('2026-09-12T00:00:00.000Z');
    expect((range.end.getTime()-range.start.getTime())/86400000).toBe(30);
    expect(historyWindow('binance','1m',1,new Date('2026-10-12T03:45:23Z')).end.toISOString()).toBe('2026-10-12T03:45:00.000Z');
    expect(historyWindow('upstox','1h',1,new Date('2026-10-12T03:45:23Z')).end.toISOString()).toBe('2026-10-12T03:45:23.000Z');
    const months=historyWindow('binance','1M',365,new Date('2026-10-14T12:00:00Z'));
    expect(months.start.toISOString()).toBe('2025-10-01T00:00:00.000Z');
    expect(months.end.toISOString()).toBe('2026-10-01T00:00:00.000Z');
    const weeks=historyWindow('binance','1w',365,new Date('2026-10-14T12:00:00Z'));
    expect(weeks.end.toISOString()).toBe('2026-10-12T00:00:00.000Z');
    expect((weeks.end.getTime()-weeks.start.getTime())/86400000).toBe(364);
  });
  it('waits for source finalization after a declared UTC close',()=>{
    expect(historyWindow('binance','1m',1,new Date('2026-10-14T12:51:01Z')).end.toISOString()).toBe('2026-10-14T12:50:00.000Z');
    expect(historyWindow('binance','1m',1,new Date('2026-10-14T12:51:11Z')).end.toISOString()).toBe('2026-10-14T12:51:00.000Z');
    expect(historyWindow('binance','1d',30,new Date('2026-10-15T00:00:01Z')).end.toISOString()).toBe('2026-10-14T00:00:00.000Z');
  });
  it('uses source values and preserves provenance',()=>{
    const row=chartBars([candle])[0];
    expect([row.open,row.high,row.low,row.close,row.volume]).toEqual([1,3,0.5,2,100]);
    expect(row.observation_id).toContain('hash');expect(row.available_at).toBe(candle.available_at);
    expect(chartBars([])).toEqual([]);
  });
  it('rejects empty, nonfinite and inconsistent source prices',()=>{
    for(const close of ['', 'NaN','Infinity','9'])expect(()=>chartBars([{...candle,close}])).toThrow('INVALID_SOURCE_CANDLE');
  });
  it('uses actual stream candles and does not create candles from quotes',()=>{
    const event={native_id:'ADAUSDT',price:'2.5',bid:null,ask:null,event_at:candle.available_at,
      received_at:candle.available_at,feed:'spot_public',state:'LIVE',source_hash:'stream',is_final:false,
      candle:{...candle,interval:'1d',close:'2.5'}} as PriceEvent;
    expect(chartWithStream([candle],event,'1d','USDT')[0].close).toBe(2.5);
    expect(chartWithStream([candle],{...event,candle:null},'1d','USDT')[0].close).toBe(2);
    expect(chartWithStream([candle],event,'1h','USDT')[0].close).toBe(2);
    expect(chartWithStream([candle],{...event,state:'STALE'},'1d','USDT')[0].close).toBe(2);
    expect(chartWithStream([{...candle,available_at:'2026-10-11T13:00:00Z'}],event,'1d','USDT')[0].close).toBe(2);
    expect(candle.close).toBe('2');
  });
  it('shows explicit source errors instead of substituting prices',async()=>{
    vi.stubGlobal('fetch',vi.fn(async()=>({ok:false,json:async()=>({code:'NOT_CONFIGURED'})})));
    await expect(marketJson('history')).rejects.toThrow('NOT_CONFIGURED');
  });
  it('recovers bounded local history contention and stops when the retry budget is exhausted',async()=>{
    vi.useFakeTimers();
    const busy={ok:false,json:async()=>({code:'HISTORY_REQUEST_BUSY'})};
    const fetcher=vi.fn().mockResolvedValueOnce(busy).mockResolvedValueOnce({ok:true,json:async()=>({items:[]})});
    vi.stubGlobal('fetch',fetcher);
    const success=marketJson('history/fetch');
    await vi.runAllTimersAsync();await expect(success).resolves.toEqual({items:[]});
    expect(fetcher).toHaveBeenCalledTimes(2);
    fetcher.mockReset().mockResolvedValue(busy);
    const exhausted=expect(marketJson('history/fetch')).rejects.toThrow('HISTORY_REQUEST_BUSY');
    await vi.runAllTimersAsync();await exhausted;expect(fetcher).toHaveBeenCalledTimes(5);
  });
});

describe('independent market proxy',()=>{
  const context=(...path:string[])=>({params:Promise.resolve({path})});
  it('is disabled without an independent backend and refuses owner ports',async()=>{
    vi.stubEnv('MARKET_CORTEX_MARKET_DATA_API_URL','');
    expect((await GET(new NextRequest('http://127.0.0.1:3017/api/market-data/catalog'),context('catalog'))).status).toBe(503);
    vi.stubEnv('MARKET_CORTEX_MARKET_DATA_API_URL','http://127.0.0.1:8765');
    expect((await GET(new NextRequest('http://127.0.0.1:3017/api/market-data/catalog'),context('catalog'))).status).toBe(503);
  });
  it('allows only selected data routes and rejects remote origin',async()=>{
    vi.stubEnv('MARKET_CORTEX_MARKET_DATA_API_URL','http://127.0.0.1:8677');
    expect((await GET(new NextRequest('http://127.0.0.1:3017/api/market-data/orders'),context('orders'))).status).toBe(404);
    expect((await POST(new NextRequest('http://127.0.0.1:3017/api/market-data/history/fetch',
      {method:'POST',headers:{origin:'https://evil.example'},body:'{}'}),context('history','fetch'))).status).toBe(403);
  });
});
