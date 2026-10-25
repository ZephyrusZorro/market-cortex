import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { SourcePriceChart } from '../components/charts';

const engine=vi.hoisted(()=>({setOption:vi.fn(),resize:vi.fn(),dispose:vi.fn()}));
const init=vi.hoisted(()=>vi.fn(()=>engine));
vi.mock('echarts',()=>({init}));
afterEach(()=>{vi.unstubAllGlobals();vi.clearAllMocks();});
it('updates actual candle data without recreating the canvas and resetting navigation',async()=>{
  vi.stubGlobal('ResizeObserver',class {observe(){}disconnect(){}});
  const bar={session_date:'2026-10-11',open:100,high:102,low:99,close:101,volume:123,
    observation_id:'source',source_batch_id:'source',available_at:'2026-10-12T00:00:01Z',quality:'SOURCE_SAMPLE',currency:'USDT'};
  const view=render(<SourcePriceChart bars={[bar]}/>);
  await waitFor(()=>expect(init).toHaveBeenCalledTimes(1));
  view.rerender(<SourcePriceChart bars={[{...bar,close:100.5}]}/>);
  expect(init).toHaveBeenCalledTimes(1);expect(engine.dispose).not.toHaveBeenCalled();
  expect(engine.setOption).toHaveBeenCalledTimes(2);
  view.unmount();expect(engine.dispose).toHaveBeenCalledTimes(1);
});
it('zooms and pans actual source slices and preserves the viewport on a price update',async()=>{
  vi.stubGlobal('ResizeObserver',class {observe(){}disconnect(){}});
  const bars=Array.from({length:8},(_,i)=>({session_date:`2026-10-${String(i+1).padStart(2,'0')}`,
    open:100+i,high:102+i,low:99+i,close:101+i,volume:123+i,observation_id:`source-${i}`,
    source_batch_id:'source',available_at:'2026-10-12T00:00:01Z',quality:'SOURCE_SAMPLE',currency:'USDT'}));
  const view=render(<SourcePriceChart bars={bars}/>);
  await waitFor(()=>expect(init).toHaveBeenCalledTimes(1));
  fireEvent.click(screen.getByRole('button',{name:'Zoom in'}));
  expect(screen.getByLabelText('Chart viewport')).toHaveTextContent('4 of 8 source candles · 2026-10-05 through 2026-10-08');
  fireEvent.click(screen.getByRole('button',{name:'Pan earlier'}));
  expect(screen.getByLabelText('Chart viewport')).toHaveTextContent('2026-10-04 through 2026-10-07');
  view.rerender(<SourcePriceChart bars={bars.map((bar,i)=>i===7?{...bar,close:107.5}:bar)}/>);
  expect(screen.getByLabelText('Chart viewport')).toHaveTextContent('2026-10-04 through 2026-10-07');
  expect(init).toHaveBeenCalledTimes(1);
  fireEvent.click(screen.getByRole('button',{name:'Reset view'}));
  expect(screen.getByLabelText('Chart viewport')).toHaveTextContent('8 of 8 source candles');
});
