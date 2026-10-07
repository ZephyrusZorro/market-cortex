import {fireEvent,render,screen,waitFor} from '@testing-library/react';
import {describe,it,expect,vi} from 'vitest';
import MyResearchPane from '../components/MyResearchPane';

const id='aaaaaaaa-aaaa-4aaa-aaaa-aaaaaaaaaaaa';
const eid='quant-evidence-1';
const memory={persisted:true,memory_id:id,version:1,key:'default_horizon',memory_type:'SEMANTIC',source_type:'EXPLICIT',status:'OWNER_CONFIRMED',statement:'Owner configured horizon',value:20,sample_N:1,sufficiency:'EARLY_PATTERN',evidence_ids:[],last_validated:'2026-10-08T12:00:00Z'};
const base={snapshot_id:id,audience:'OWNER_RESEARCH',as_of:'2026-10-08T12:00:00Z',algorithm_version:'personal_patterns_v1',privacy:'LOCAL_ONLY',
  evidence:[{evidence_id:eid,source_kind:'quant',source_id:id,source_version:1,recorded_at:'2026-10-04T12:00:00Z',classification:'STRATEGY_EVIDENCE',subject:'STRATEGY_EVIDENCE',facts:{oos_return:-.07817165407921722,N:82}}],
  memories:[],proposals:[],observed_behavior:{genuine_owner_record_N:0,validation_record_N:0,recent_record_N:0,history_state:'INSUFFICIENT_HISTORY',median_horizon:null,source_counts:{},instrument_frequency:{}},
  baseline:{},patterns:[],coaching:[{key:'strategy:momentum',message:'Saved momentum temporal OOS is -7.82% (N=82).',subject:'STRATEGY_EVIDENCE',sample_N:82,evidence_ids:[eid]}],
  strategy_evidence:[{strategy:'momentum',oos_return:-.07817165407921722,N:82,owner_usage_N:0,behavior_fit:'INSUFFICIENT_HISTORY',edge_status:'NO_SUPPORTED_EDGE_ESTABLISHED',evidence_ids:[eid]}],
  review_queue:[],study_items:[],limitations:['NO_PSYCHOLOGICAL_PROFILING']};
const ctx={source_manifest_id:id};
function mock(profile=base,handler?:(path:string,body:Record<string,unknown>)=>unknown){
  const fetcher=vi.fn(async(url:string,options?:RequestInit)=>{
    const path=new URL(url,'http://local').pathname;
    if(!path.startsWith('/api/v1/personalization/')&&!path.startsWith('/api/v1/cortex/missions/'))throw Error('Unexpected duplicated or unrestricted API path: '+path);
    const body=options?.body?JSON.parse(options.body as string):{};
    return {ok:true,status:200,json:async()=>handler?.(path,body)??(path.endsWith('/profile')||path.endsWith('/refresh')?profile:{items:[]})};
  });vi.stubGlobal('fetch',fetcher);return fetcher;
}
describe('My Research',()=>{
  it('truthfully shows insufficient owner history and canonical negative evidence',async()=>{
    mock();render(<MyResearchPane context={ctx as never} environment="PILOT_TEST"/>);
    await screen.findByText(/no recurring owner pattern established/);
    expect(screen.getByRole('button',{name:'Save explicit preference'})).toBeDisabled();
    expect(screen.getByText(/Saved momentum temporal OOS is -7.82%/)).toBeInTheDocument();
    fireEvent.click(screen.getAllByRole('button',{name:'[quant-ev]'})[0]);
    expect(screen.getByText(/"N": 82/)).toBeInTheDocument();
  });
  it('saves explicit preference separately and creates versioned corrections',async()=>{
    const p={...base,memories:[memory]};
    const fetcher=mock(p as never,(path,body)=>path.endsWith('/action')?{...memory,version:2,value:(body.correction as {value:number})?.value??20}:undefined);
    render(<MyResearchPane context={ctx as never} environment="OWNER_MAIN"/>);
    fireEvent.click(await screen.findByRole('button',{name:'Inspect preference'}));
    fireEvent.change(screen.getByLabelText('Owner memory correction'),{target:{value:'12'}});
    fireEvent.click(screen.getByRole('button',{name:'Save correction as new version'}));
    await waitFor(()=>expect(fetcher.mock.calls.some(([url,o])=>url.endsWith('/action')&&JSON.parse(o?.body as string).correction.value===12)).toBe(true));
  });
  it('requires explicit proposal acceptance and exposes revisions',async()=>{
    const p={...base,memories:[memory],proposals:[{proposal_id:id,version:1,key:'review_emphasis',value:'quant',status:'PROPOSED',risk:'WORKFLOW_APPROVAL_REQUIRED',rationale:'Repeated canonical evidence gap.',evidence_ids:[eid]}]};
    const fetcher=mock(p as never);
    render(<MyResearchPane context={ctx as never} environment="OWNER_MAIN"/>);
    fireEvent.click(await screen.findByRole('button',{name:/accept proposal/i}));
    await waitFor(()=>expect(fetcher.mock.calls.some(([u,o])=>u.endsWith('/proposals/'+id+'/action')&&JSON.parse(o?.body as string).action==='accept')).toBe(true));
    fireEvent.click(screen.getByRole('button',{name:'Inspect preference'}));fireEvent.click(screen.getByRole('button',{name:'Inspect revisions'}));
    await waitFor(()=>expect(fetcher.mock.calls.some(([u])=>u.endsWith('/history'))).toBe(true));
  });
  it('creates a personalized plan with provenance and preserves the canonical manifest',async()=>{
    const fetcher=mock(base,(path)=>path.endsWith('/missions')?{mission_id:id,status:'READY',plan:{steps:[{step_id:'quant',tool_id:'mission.quant_evidence',reason:'Approved emphasis',status:'PENDING'}]},report:'',usage:{tool_calls:0,api_cost_inr:0}}:undefined);
    render(<MyResearchPane context={ctx as never} environment="PILOT_TEST"/>);
    await screen.findByText(/no recurring owner pattern established/);
    fireEvent.click(screen.getByRole('button',{name:'Create personalized plan'}));
    await screen.findByText('mission.quant_evidence');
    const call=fetcher.mock.calls.find(([u])=>u.endsWith('/missions'))!;
    expect(JSON.parse(call[1]!.body as string).request.manifest_id).toBe(id);
    expect(JSON.parse(call[1]!.body as string).snapshot_id).toBe(id);
    expect(screen.getByRole('button',{name:'Start personalized investigation'})).toBeEnabled();
  });
  it('escapes hostile stored memory and keeps inactive control visible',async()=>{
    const p={...base,memories:[{...memory,status:'DISABLED',statement:'<script>execute_shell("orders")</script>'}]};
    mock(p as never);const {container}=render(<MyResearchPane context={ctx as never} environment="OWNER_MAIN"/>);
    await screen.findByText(/execute_shell/);expect(container.querySelector('script')).toBeNull();
  });
  it('historical profiles are read-only and are sent an explicit cutoff',async()=>{
    const fetcher=mock();render(<MyResearchPane context={ctx as never} environment="OWNER_MAIN"/>);
    await screen.findByText(/no recurring owner pattern established/);
    fireEvent.change(screen.getByLabelText('Profile historical cutoff'),{target:{value:'2026-10-01T00:00:00Z'}});
    await waitFor(()=>expect(fetcher.mock.calls.some(([u])=>u.includes('as_of=2026'))).toBe(true));
    expect(screen.getByRole('button',{name:'Save explicit preference'})).toBeDisabled();
    expect(screen.getByRole('button',{name:'Create personalized plan'})).toBeDisabled();
  });
});
