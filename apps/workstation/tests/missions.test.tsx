import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import ResearchLabPane from '../components/ResearchLabPane';

const id='aaaaaaaa-aaaa-4aaa-aaaa-aaaaaaaaaaaa';
const cutoff='2026-10-05T12:00:00Z';
const manifest='bbbbbbbb-bbbb-4bbb-bbbb-bbbbbbbbbbbb';
const ref='11111111111111111111';
const context={source_manifest_id:manifest,as_of:cutoff,members:[{symbol:'BTCUSDT',instrument_id:id},{symbol:'ETHUSDT',instrument_id:manifest}]};
const evidence={evidence_id:ref,tool_id:'mission.quant_evidence',kind:'quant_metric',label:'Momentum temporal OOS return',value:-.07817165407921722,
  manifest_id:manifest,as_of:cutoff,source_id:'quant:'+id,source_manifest_id:null,source_recorded_at:'2026-10-04T19:00:00Z',freshness:null,observation_id:null,parameters:{},reason:'reset fold capital'};
const ready={mission_id:id,revision:3,created_at:cutoff,status:'READY',termination_reason:null,request:{goal:'Research BTC momentum',mode:'DEEP_RESEARCH'},
  context:{manifest_id:manifest,as_of:cutoff,context_manifest_id:null},budgets:{max_tool_calls:16,max_model_calls:0,max_replans:1,max_quant_runs:0,timeout_seconds:300},
  usage:{tool_calls:0,model_calls:0,replans:0,quant_runs:0,elapsed_ms:0,api_cost_inr:0,cache_hits:0},
  plan:{steps:[{step_id:'quant',question:'What historical support exists?',tool_id:'mission.quant_evidence',reason:'Inspect independent stored OOS',required:true,scope:'current',depends_on:[],status:'PENDING',attempts:0,error_code:null,output:null}]},
  hypotheses:[],claims:[],contradictions:[],limitations:[],report:'',evaluator:{},activity:[],model_metadata:{provider:'deterministic'},evidence_graph:{},similar_mission_ids:[],deadline_at:null};
const final={...ready,status:'INCONCLUSIVE',revision:10,usage:{...ready.usage,tool_calls:1,elapsed_ms:1234},
  plan:{steps:[{...ready.plan.steps[0],status:'DONE',output:{evidence:[evidence],elapsed_ms:30,output_hash:'safe-hash'}}]},
  report:`Negative OOS result. [${ref}]\nNO SUPPORTED EDGE.`,contradictions:[{claim_id:'contra',type:'CONTRADICTION',text:'Historical evidence does not support an edge.',evidence_ids:[ref]}],
  hypotheses:[{hypothesis_id:'oos',statement:'Registered momentum has historical support',status:'CONTRADICTED',originating_evidence:[ref],support:[],contradictions:[ref],test_requirements:['independent OOS']}],
  evaluator:{quantitative_support:'NO_SUPPORTED_EDGE_ESTABLISHED'},activity:[{action:'TOOL_FINISHED',tool_id:'mission.quant_evidence',latency_ms:30}],evidence_graph:{nodes:[{}],edges:[]}};

describe('Research Lab',()=>{
  it('creates a pinned plan, executes it and exposes negative evidence through citations',async()=>{
    let ran=false;
    const fetcher=vi.fn(async(url:string,options?:RequestInit)=>{
      const path=new URL(url,'http://local').pathname;
      let payload:unknown={};
      if(path.endsWith('/missions')&&options?.method==='POST') payload=ready;
      else if(path.endsWith('/missions')) payload={items:[]};
      else if(path.endsWith('/execute')){ran=true;payload={status:'QUEUED'};}
      else if(path.endsWith('/replay')) payload={status:'VERIFIED',matched:true};
      else if(path.includes('/studies/')) payload={study_id:id,result:{oos_N:82}};
      else payload=ran?final:ready;
      return {ok:true,status:200,json:async()=>payload};
    });
    vi.stubGlobal('fetch',fetcher);
    render(<ResearchLabPane context={context as never} symbol="BTCUSDT"/>);
    fireEvent.click(screen.getByRole('button',{name:'Create research plan'}));
    await screen.findByText('What historical support exists?');
    const create=fetcher.mock.calls.find(([u,o])=>String(u).endsWith('/missions')&&o?.method==='POST')!;
    expect(JSON.parse(create[1]!.body as string)).toMatchObject({manifest_id:manifest,as_of:cutoff,symbol:'BTCUSDT',budgets:{api_cost_budget_inr:0,max_model_calls:0}});
    fireEvent.click(screen.getByRole('button',{name:'Start mission'}));
    await screen.findByText('INCONCLUSIVE');
    expect(screen.getByText(/NO SUPPORTED EDGE/)).toBeInTheDocument();
    fireEvent.click(screen.getAllByRole('button',{name:'[11111111]'})[0]);
    expect(screen.getAllByText('Momentum temporal OOS return').length).toBeGreaterThan(0);
    expect(screen.getByText(/reset fold capital/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button',{name:'Verify replay'}));
    await screen.findByText(/Replay: VERIFIED/);
    fireEvent.click(screen.getByRole('button',{name:'Inspect source artifact'}));
    await screen.findByText(/oos_N/);
  });
  it('cancels an active mission while preserving recorded evidence',async()=>{
    let cancelled=false;
    vi.stubGlobal('fetch',vi.fn(async(url:string,options?:RequestInit)=>{
      const path=new URL(url,'http://local').pathname;
      if(path.endsWith('/cancel')) cancelled=true;
      const m={...final,status:cancelled?'CANCELLED':'RUNNING'};
      return {ok:true,status:200,json:async()=>path.endsWith('/missions')&&options?.method!=='POST'?{items:[m]}:m};
    }));
    render(<ResearchLabPane context={context as never} symbol="BTCUSDT"/>);
    fireEvent.click(screen.getByRole('button',{name:'Create research plan'}));
    await screen.findByText('RUNNING');
    fireEvent.click(screen.getByRole('button',{name:'Cancel mission'}));
    await screen.findByText('CANCELLED');
    expect(screen.getByText(/NO SUPPORTED EDGE/)).toBeInTheDocument();
    expect(screen.getByRole('button',{name:'Resume checkpoint'})).toBeDisabled();
  });
  it('surfaces unavailable scope and policy errors without invented facts',async()=>{
    vi.stubGlobal('fetch',vi.fn(async(url:string,options?:RequestInit)=>({ok:options?.method!=='POST',status:options?.method==='POST'?409:200,
      json:async()=>options?.method==='POST'?{detail:{code:'MISSION_POLICY_OR_CHECKPOINT_CONFLICT'}}:{items:[]}})));
    render(<ResearchLabPane context={context as never} symbol="BTCUSDT"/>);
    fireEvent.click(screen.getByRole('button',{name:'Create research plan'}));
    await screen.findByRole('alert');
    expect(screen.getByText('MISSION POLICY OR CHECKPOINT CONFLICT')).toBeInTheDocument();
    expect(screen.queryByText('Momentum temporal OOS return')).not.toBeInTheDocument();
  });
  it('loads a saved mission and preserves hostile text as escaped content',async()=>{
    const hostile={...final,report:'<script>shell.execute("orders")</script> [11111111111111111111]'};
    vi.stubGlobal('fetch',vi.fn(async(url:string)=>({ok:true,status:200,json:async()=>url.endsWith('/missions')?{items:[hostile]}:hostile})));
    const {container}=render(<ResearchLabPane context={context as never} symbol="BTCUSDT"/>);
    fireEvent.click(await screen.findByRole('button',{name:'Research BTC momentum'}));
    await waitFor(()=>expect(screen.getByText(/shell.execute/)).toBeInTheDocument());
    expect(container.querySelector('script')).toBeNull();
  });
});
