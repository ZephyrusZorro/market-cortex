import {fireEvent,render,screen,waitFor} from '@testing-library/react';
import {describe,expect,it,vi} from 'vitest';
import QuantPane from '../components/QuantPane';
import type {Context} from '../lib/api';

vi.mock('../components/charts',()=>({QuantChart:()=> <div>Equity curve net gross benchmark drawdown</div>}));
const id='aaaaaaaa-aaaa-4aaa-aaaa-aaaaaaaaaaaa';
const context={source_manifest_id:id,as_of:'2026-10-04T12:00:00Z',history_start:'2025-09-01',evaluation_date:'2026-10-03',
  members:[{symbol:'BTCUSDT',instrument_id:id}]} as Context;
const definition={strategy_id:'momentum',start:'2025-09-01',end:'2026-10-03',replay_policy:'HISTORICAL_RECONSTRUCTION',costs:{entry_fee_bps:10},execution:{timing:'next_open'}};
const run={run_id:id,definition,metrics:{N:2,total_return:-.03,max_drawdown:-.05},warnings:['INSUFFICIENT_TRADE_SAMPLE_N_LT_30'],trades:[{trade_id:id,symbol:'BTCUSDT',entry_session:'2026-01-01',exit_session:'2026-01-10',net_pnl:-10,exit_reason:'stop',decision_hash:'frozen'}],
  equity:[],decisions:[{evidence_hash:'frozen',status:'VALID'}],regime_performance:[],controls:{groups:[],warning:'RETROSPECTIVE_COUNTERFACTUAL'},manifest:{source_hash:'original'},drawdown:{},result_hash:'frozen'};
function mockFetch() {
  return vi.fn(async (url:unknown,init?:RequestInit)=>{
    const path=String(url);let payload:unknown={items:[]};
    if(path.endsWith('/strategies'))payload={items:[{strategy_id:'momentum',version:'1.0.0',entry_policy:'valid_only_v1',description:'Canonical momentum'}]};
    if(path.endsWith('/runs'))payload={items:[{artifact_id:id,strategy_id:'momentum',metrics:run.metrics}],search_counts:{unique_run_combinations:4}};
    if(path.endsWith(`/runs/${id}`))payload=run;
    if(path.endsWith('/jobs')&&init?.method==='POST')payload={job_id:id,status:'queued'};
    if(path.endsWith('/studies'))payload={items:[{artifact_id:id,kind:'walk_forward'}]};
    if(path.endsWith(`/studies/${id}`))payload={study_id:id,kind:'walk_forward',warnings:['TEMPORAL_OOS_NOT_PROSPECTIVE'],result:{oos_N:2,sample_status:'INSUFFICIENT_OOS_SAMPLE',oos_total_return_compounded_reset_capital:-.05,folds:[{fold:1,train_start:'2025-01-01',train_end:'2025-06-01',validation_start:'2025-06-02',validation_end:'2025-09-01',selected_parameters:{holding_sessions:5},training_score:.1,oos_metrics:{N:2,total_return:-.05},search_results:[{parameters:{holding_sessions:5},metrics:{N:3,total_return:.1}},{parameters:{holding_sessions:10},metrics:{N:4,total_return:-.4}}]}]}};
    return new Response(JSON.stringify(payload),{status:200,headers:{'Content-Type':'application/json'}});
  });
}

describe('Quant Lab',()=>{
  it('defaults to recorded replay and submits a typed strategy with explicit costs',async()=>{
    const fetch=mockFetch();vi.stubGlobal('fetch',fetch);render(<QuantPane context={context}/>);
    await screen.findByRole('option',{name:'momentum'});
    expect(screen.getByLabelText('Replay policy')).toHaveValue('AS_RECORDED');
    fireEvent.click(screen.getByText('Queue backtest'));
    await waitFor(()=>expect(fetch.mock.calls.some(call=>call[1]?.method==='POST')).toBe(true));
    const call=fetch.mock.calls.find(call=>call[1]?.method==='POST')!;
    const body=JSON.parse(call[1]!.body as string);
    expect(body.operation).toBe('backtest');expect(body.payload.manifest_id).toBe(id);
    expect(body.payload.execution.timing).toBe('next_open');expect(body.payload.costs.entry_fee_bps).toBe(10);
    expect(body.payload).not.toHaveProperty('code');
  });
  it('opens saved detail with samples, poor results, trade evidence and bounded studies',async()=>{
    vi.stubGlobal('fetch',mockFetch());render(<QuantPane context={context}/>);
    fireEvent.click(await screen.findByRole('button',{name:/Open aaaaaaaa/}));
    await screen.findByText(/run detail/);
    expect(screen.getByText(/N=2 · 2025-09-01/)).toBeInTheDocument();
    expect(screen.getByText('INSUFFICIENT_TRADE_SAMPLE_N_LT_30')).toBeInTheDocument();
    expect(screen.getByText('Equity curve net gross benchmark drawdown')).toBeInTheDocument();
    fireEvent.click(screen.getByText('Inspect trade'));expect(await screen.findByText(/Trade inspector/)).toBeInTheDocument();
    fireEvent.click(screen.getByText('Research studies'));
    expect(screen.getByText('Run walk-forward')).toBeInTheDocument();expect(screen.getByLabelText('Holding grid')).toHaveValue('5,10,15');
    expect(screen.getByText('Run sensitivity')).toBeInTheDocument();expect(screen.getByText('Run Monte Carlo')).toBeInTheDocument();
    fireEvent.click(await screen.findByRole('button',{name:/walk_forward · aaaaaaaa/}));
    await screen.findByText(/Fold 1: train/);
    expect(screen.getByText('TEMPORAL_OOS_NOT_PROSPECTIVE')).toBeInTheDocument();
    expect(screen.getByText('-0.4')).toBeInTheDocument();
  });
});
