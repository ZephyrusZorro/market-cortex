import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import MarketsPage from '../app/markets/page';

vi.mock('../components/charts',()=>({SourcePriceChart:({bars}:{bars:unknown[]})=><div role="img" aria-label={`real source chart ${bars.length}`}/> }));
const instrument=(symbol:string)=>({provider:'binance',native_id:symbol,symbol,name:symbol,market:'CRYPTO',
  exchange:'BINANCE_SPOT',currency:'USDT',status:'TRADING',present:true,live_entitlement:'PUBLIC_SPOT_SUBJECT_TO_AVAILABILITY'});
const row={start_at:'2026-10-10T00:00:00+00:00',end_at:'2026-10-11T00:00:00+00:00',available_at:'2026-10-11T12:00:00+00:00',
  open:'100',high:'102',low:'99',close:'101',volume:'123',currency:'USDT',source_hash:'source',feed:'spot_public',adjustment_basis:'raw'};
afterEach(()=>{vi.unstubAllGlobals();vi.useRealTimers();});
function api(failHistory=false) {
  const fetcher=vi.fn(async(url:string)=>{
    const parsed=new URL(url,'http://local');
    let payload:unknown={items:[]};let ok=true;
    if(parsed.pathname.endsWith('/catalog'))payload={items:[instrument(parsed.searchParams.get('query')==='ETHUSDT'?'ETHUSDT':'BTCUSDT')],total:1,next_offset:null,snapshots:{binance:'snapshot'}};
    if(parsed.pathname.endsWith('/history'))payload={items:[],state:'UNAVAILABLE'};
    if(parsed.pathname.endsWith('/history/fetch')){payload=failHistory?{code:'SOURCE_UNAVAILABLE'}:{items:[row],state:'HISTORICAL'};ok=!failHistory;}
    return {ok,json:async()=>payload};
  });
  vi.stubGlobal('fetch',fetcher);return fetcher;
}
describe('market explorer functional entry',()=>{
  it('loads BTC from exact discovery without requiring a click, and switches to ETH',async()=>{
    const fetcher=api();render(<MarketsPage/>);
    expect(await screen.findByRole('heading',{name:'BTCUSDT'})).toBeInTheDocument();
    expect(await screen.findByRole('img',{name:'real source chart 1'})).toBeInTheDocument();
    expect(screen.getByText(/Historical close:/)).toHaveTextContent('101 USDT');
    const posted=fetcher.mock.calls.find(call=>call[0].endsWith('/history/fetch'));
    expect(posted).toBeDefined();
    fireEvent.click(screen.getByRole('button',{name:'ETHUSDT chart'}));
    expect(await screen.findByRole('heading',{name:'ETHUSDT'})).toBeInTheDocument();
    await waitFor(()=>expect(screen.getByRole('img',{name:'real source chart 1'})).toBeInTheDocument());
  });
  it('retains a history failure when the catalog refresh succeeds, without fake candles',async()=>{
    api(true);render(<MarketsPage/>);
    expect(await screen.findByRole('alert')).toHaveTextContent('History: SOURCE_UNAVAILABLE');
    fireEvent.change(screen.getByRole('textbox',{name:'Search instruments'}),{target:{value:'BTC'}});
    await waitFor(()=>expect(screen.getByRole('button',{name:/BTCUSDT ·/})).toBeInTheDocument());
    expect(screen.getByRole('alert')).toHaveTextContent('History: SOURCE_UNAVAILABLE');
    expect(screen.queryByRole('img')).not.toBeInTheDocument();
  });
  it('refreshes missing closed bars once at a UTC boundary while the real feed is labeled live',async()=>{
    vi.useFakeTimers();vi.setSystemTime(new Date('2026-10-14T23:59:30Z'));
    const fetcher=api();const previous=fetcher.getMockImplementation()!;
    fetcher.mockImplementation(async(url:string)=>url.includes('/prices?')?{ok:true,json:async()=>({items:[{
      native_id:'BTCUSDT',price:'101',bid:null,ask:null,event_at:'2026-10-14T23:59:30Z',received_at:'2026-10-14T23:59:30Z',
      feed:'spot_public',state:'LIVE',source_hash:'source',is_final:false,candle:null}]})}:previous(url));
    render(<MarketsPage/>);
    await act(async()=>{await vi.advanceTimersByTimeAsync(500);});
    expect(fetcher.mock.calls.filter(call=>call[0].endsWith('/history/fetch'))).toHaveLength(1);
    await act(async()=>{await vi.advanceTimersByTimeAsync(41000);});
    expect(fetcher.mock.calls.filter(call=>call[0].endsWith('/history/fetch'))).toHaveLength(2);
    await act(async()=>{await vi.advanceTimersByTimeAsync(4000);});
    expect(fetcher.mock.calls.filter(call=>call[0].endsWith('/history/fetch'))).toHaveLength(2);
  });
});
