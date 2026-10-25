'use client';

import { useEffect, useMemo, useRef, useState } from 'react';
import { SourcePriceChart } from '@/components/charts';
import { chartWithStream, historyWindow, marketJson, type NativeInstrument, type PriceEvent, type SourceCandle } from '@/lib/market-data';

type Catalog = { items: NativeInstrument[]; total: number; next_offset: number | null; snapshots: Record<string,string> };
export default function MarketsPage() {
  const [provider, setProvider] = useState('binance');
  const [query, setQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState('TRADING');
  const [offset, setOffset] = useState(0);
  const [catalog, setCatalog] = useState<Catalog>({ items: [], total: 0, next_offset: null, snapshots: {} });
  const [selected, setSelected] = useState<NativeInstrument | null>(null);
  const [interval, setTimeframe] = useState('1d');
  const [days, setDays] = useState(30);
  const [rows, setRows] = useState<SourceCandle[]>([]);
  const [price, setPrice] = useState<PriceEvent | null>(null);
  const [streamCandle, setStreamCandle] = useState<PriceEvent | null>(null);
  const [catalogError, setCatalogError] = useState('');
  const [historyError, setHistoryError] = useState('');
  const [loading, setLoading] = useState(false);
  const [reloadHistory,setReloadHistory]=useState(0);
  const [state, setState] = useState('UNAVAILABLE');
  const selection = useRef(0);
  const shortcut = useRef(0);
  const defaultStarted = useRef(false);
  useEffect(() => {
    if (provider !== 'binance' || defaultStarted.current) return;
    let disposed = false;
    // Exact discovery identity, never a fabricated default price/series.
    marketJson<Catalog>('catalog?provider=binance&query=BTCUSDT&status=TRADING&limit=10')
      .then(result => {
        const btc=result.items.find(item=>item.native_id==='BTCUSDT');
        if (!disposed && btc) { defaultStarted.current=true; setSelected(current=>current ?? btc); }
      }).catch(e=>{if(!disposed)setHistoryError(e.message);});
    return () => {disposed=true;};
  }, [provider]);
  const chooseBinance = async (symbol: string) => {
    const ticket=++shortcut.current;
    setHistoryError('');
    try {
      const result=await marketJson<Catalog>(`catalog?${new URLSearchParams({provider:'binance',query:symbol,status:'TRADING',limit:'10'})}`);
      const item=result.items.find(value=>value.native_id===symbol);
      if(ticket!==shortcut.current)return;
      if(!item)throw new Error('ACTIVE_NATIVE_INSTRUMENT_NOT_FOUND');
      setSelected(item);
    } catch(e) {if(ticket===shortcut.current)setHistoryError(e instanceof Error?e.message:'DISCOVERY_UNAVAILABLE');}
  };
  useEffect(() => {
    let disposed = false;
    const timer = setTimeout(() => {
      const params = new URLSearchParams({ provider, query, offset: String(offset), limit: '50' });
      if (statusFilter) params.set('status',statusFilter);
      if (offset>0 && catalog.snapshots[provider]) params.set('snapshot',catalog.snapshots[provider]);
      marketJson<Catalog>(`catalog?${params}`)
        .then(result => { if (!disposed) { setCatalog(result); setCatalogError(''); } })
        .catch(e => { if (!disposed) { setCatalog({items:[],total:0,next_offset:null,snapshots:{}}); setCatalogError(e.message); } });
    }, 250);
    return () => { disposed = true; clearTimeout(timer); };
  }, [provider, query, offset, statusFilter]);
  useEffect(() => {
    if (!selected) return;
    const controller=new AbortController();
    const ticket = ++selection.current;
    setRows([]); setPrice(null); setStreamCandle(null); setState('UNAVAILABLE'); setLoading(true); setHistoryError('');
    const {start,end} = historyWindow(selected.provider,interval,days);
    let knownEnd=end.getTime();
    let historyInFlight=true;
    let automaticRefreshStopped=false;
    const current = () => ticket === selection.current;
    const load = async (range={start,end}) => {
      historyInFlight=true;
      if(current())setLoading(true);
      const params = new URLSearchParams({ provider:selected.provider,native_id:selected.native_id,
        interval,start:range.start.toISOString(),end:range.end.toISOString(),limit:'5000' });
      try {
        const cached = await marketJson<{items:SourceCandle[];state:string}>(`history?${params}`,{signal:controller.signal});
        if (!current()) return;
        setRows(cached.items); setState(cached.state);
        const fetched = await marketJson<{items:SourceCandle[];state:string}>('history/fetch', {
          method: 'POST', signal:controller.signal,headers: {'Content-Type':'application/json'}, body: JSON.stringify({
            provider: selected.provider, native_id: selected.native_id, interval, start: range.start.toISOString(), end: range.end.toISOString() }) });
        if (current()) { setRows(fetched.items); setState(fetched.state);knownEnd=range.end.getTime(); }
      } catch (e) {automaticRefreshStopped=true;if (current()) setHistoryError(e instanceof Error ? e.message : 'HISTORY_UNAVAILABLE'); }
      finally {historyInFlight=false;if (current()) setLoading(false); }
    };
    void load();
    const poll = async () => {
      try {
        const result = await marketJson<{items:PriceEvent[]}>(`prices?${new URLSearchParams({provider:selected.provider,native_id:selected.native_id})}`);
        if (current()) {
          const ordered=[...result.items].sort((a,b)=>b.event_at.localeCompare(a.event_at));
          setPrice(ordered.find(item=>item.price!==null && !item.candle) ?? ordered[0] ?? null);
          setStreamCandle(ordered.find(item=>item.candle!==null && item.candle?.interval===interval) ?? null);
          // The shared collector supplies real prices. On a completed UTC
          // Binance boundary, the existing cache service fetches only missing
          // closed bars; a failed refresh requires an explicit retry.
          const range=historyWindow(selected.provider,interval,days);
          if(selected.provider==='binance' && ordered.some(item=>item.state==='LIVE') &&
              range.end.getTime()>knownEnd && !historyInFlight && !automaticRefreshStopped)void load(range);
        }
      } catch { if (current()) {setPrice(null);setStreamCandle(null);} }
    };
    void poll();
    const timer = setInterval(poll, 2000);
    return () => { selection.current++;controller.abort();clearInterval(timer); };
  }, [selected, interval, days,reloadHistory]);
  const bars = useMemo(()=>chartWithStream(rows,streamCandle,interval,selected?.currency ?? ''),
    [rows,streamCandle,interval,selected?.currency]);
  return <main style={{padding:24,maxWidth:1500,margin:'auto'}}>
    <h1>Market data explorer</h1>
    <p>Independent provider evidence · {catalog.total.toLocaleString('en-IN')} matching catalog records · discovery is separate from stored history</p>
    <div className="panel" style={{padding:16,display:'flex',gap:16,flexWrap:'wrap'}}>
      <label>Market <select aria-label="Market" value={provider} onChange={e=>{selection.current++;shortcut.current++;setProvider(e.target.value);setStatusFilter(e.target.value==='binance'?'TRADING':e.target.value==='upstox'?'LISTED':'active');setOffset(0);setSelected(null);setRows([]);setPrice(null);setStreamCandle(null);setLoading(false);setState('UNAVAILABLE');setHistoryError('');}}>
        <option value="binance">Binance spot</option><option value="upstox">India NSE/BSE</option><option value="alpaca">US equities/ETFs</option>
      </select></label>
      <label>Search <input aria-label="Search instruments" value={query} placeholder="Symbol, name, native ID or ISIN" onChange={e=>{setQuery(e.target.value);setOffset(0);}} /></label>
      <label>Status <select aria-label="Instrument status" value={statusFilter} onChange={e=>{setStatusFilter(e.target.value);setOffset(0);}}>
        <option value={provider==='binance'?'TRADING':provider==='upstox'?'LISTED':'active'}>Active/listed</option>
        <option value="">All source statuses</option>
        <option value={provider==='binance'?'BREAK':provider==='upstox'?'SUSPENDED':'inactive'}>Inactive/suspended</option>
      </select></label>
      <button disabled={offset===0} onClick={()=>setOffset(Math.max(0,offset-50))}>Previous</button>
      <button disabled={catalog.next_offset===null} onClick={()=>setOffset(catalog.next_offset ?? 0)}>Next</button>
    </div>
    {catalogError && <p role="alert">Catalog: {catalogError}</p>}
    <div style={{display:'grid',gridTemplateColumns:'minmax(240px,1fr) minmax(0,3fr)',gap:16,marginTop:16}}>
      <section className="panel" style={{padding:12,maxHeight:750,overflow:'auto'}} aria-label="Instrument catalog">
        {catalog.items.map(item=><button key={item.native_id} onClick={()=>{shortcut.current++;setSelected(item);}} style={{display:'block',width:'100%',textAlign:'left',padding:10}}>
          <strong>{item.symbol}</strong> · {item.exchange}<br/>{item.name}<br/><small>{item.status} · {item.live_entitlement}</small>
        </button>)}
        {!catalog.items.length && <p>Catalog unavailable or no matches. No prices have been substituted.</p>}
      </section>
      <section className="panel" style={{padding:16}}>
        {provider==='binance' && <div><button onClick={()=>void chooseBinance('BTCUSDT')}>BTCUSDT chart</button> <button onClick={()=>void chooseBinance('ETHUSDT')}>ETHUSDT chart</button></div>}
        <h2>{selected?.symbol ?? 'Select an instrument'}</h2>
        {selected && <p>{loading && rows.length===0?'LOADING':price?.state ?? state} · {price?.feed ?? rows[0]?.feed ?? 'No stored source observations for this selection'}</p>}
        {historyError && <p role="alert">History: {historyError} {selected && <button onClick={()=>setReloadHistory(value=>value+1)}>Retry history</button>}</p>}
        {selected && !price && <p>Live feed unavailable for this instrument — no active observation in the collector. Historical candles are separate.</p>}
        {price && <p>Last trade: {price.price ?? 'unavailable'} · bid {price.bid ?? 'unavailable'} · ask {price.ask ?? 'unavailable'}<br/>
          Source timestamp {price.event_at} · received {price.received_at}</p>}
        {streamCandle && <p>{streamCandle.is_final?'Source reports closed':'Forming'} stream candle · {streamCandle.state} · display only; excluded from pinned historical research</p>}
        {rows.length>0 && <p>Historical close: {rows.at(-1)?.close} {selected?.currency} · {rows.length} closed candles · {rows[0].adjustment_basis}</p>}
        {rows.length>0 && <p aria-label="Latest closed OHLCV" data-source-interval={rows.at(-1)?.interval} data-history-ready={!loading}>Open {rows.at(-1)?.open} · high {rows.at(-1)?.high} · low {rows.at(-1)?.low} · close {rows.at(-1)?.close}<br/>
          Volume {rows.at(-1)?.volume} {rows.at(-1)?.volume_unit ?? 'provider native units'} · candle start {rows.at(-1)?.start_at} · close boundary {rows.at(-1)?.end_at}</p>}
        <label>Timeframe <select aria-label="Timeframe" value={interval} onChange={e=>{setTimeframe(e.target.value);setDays(['1m','5m','15m'].includes(e.target.value)?1:['1w','1M'].includes(e.target.value)?365:30);}}>
          {['1m','5m','15m','1h','4h','1d','1w','1M'].map(v=><option key={v}>{v}</option>)}</select></label>
        <label> History <select aria-label="History range" value={days} onChange={e=>setDays(Number(e.target.value))}>
          {[1,7,30,90,365].filter(v=>(!['1m','5m','15m'].includes(interval)||v<=7) && (interval!=='1M'||v>=30) && (interval!=='1w'||v>=7)).map(v=><option key={v} value={v}>{v} days</option>)}</select></label>
        {loading && <p role="status">Loading cached/provider history…</p>}
        {bars.length>0 ? <SourcePriceChart key={`${selected?.provider}:${selected?.native_id}:${interval}`} bars={bars}/> : <p>{!selected?'Select an active instrument to load genuine history. BTCUSDT is the initial Binance selection.':loading?'Retrieving genuine cached/provider candles…':'UNAVAILABLE — no genuine candles returned for this selection.'}</p>}
        {rows.length>0 && <p>UTC range {rows[0].start_at} through {rows.at(-1)?.end_at} · latest observation received {rows.at(-1)?.available_at}</p>}
        <p>Broker calendars and corporate-action lineage require verification. Alpaca IEX volume covers IEX only. Streaming requires a separately authorized selected-symbol collector.</p>
      </section>
    </div>
  </main>;
}
