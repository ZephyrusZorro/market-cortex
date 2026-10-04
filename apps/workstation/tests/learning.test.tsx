import { fireEvent,render,screen,waitFor } from '@testing-library/react';
import { describe,expect,it,vi } from 'vitest';
import LearningPane from '../components/LearningPane';

const id='aaaaaaaa-aaaa-4aaa-aaaa-aaaaaaaaaaaa';
const manifest='0624ecba-b711-4fbe-86ca-7fc666ec6f41';
const context={source_manifest_id:manifest,as_of:'2026-10-04T10:00:00Z',
  members:['BTCUSDT','ETHUSDT','SOLUSDT','BNBUSDT','XRPUSDT'].map(symbol=>({symbol,instrument_id:id}))};
const entry={entry_id:id,revision:1,category:'research_note',title:'Original expectation note',notes:'Original belief',
  tags:['research'],as_of:context.as_of,recorded_at:context.as_of,classification:'OWNER_RESEARCH',author:'owner',
  structured_content:{},failure_category:null,links:{}};
const prediction={prediction_id:id,title:'BTC forward return expectation',symbol:'BTCUSDT',detector_id:'momentum',
  detector_version:'1.0.0',registration:'RETROSPECTIVE_EVALUATION',classification:'SYNTHETIC_TEST',status:'OPEN',
  horizon_sessions:5,due_session:'2026-09-25',created_at:context.as_of,evidence_strength:'weak',baseline_session:'2026-09-20',
  manifest_id:manifest,original_context_hash:'frozen-hash',original_context:{baseline_price:'100'},
  prediction_type:'forward_return',comparator:'gt',threshold:'0'};
const group={detector_id:'momentum',detector_version:'1.0.0',registration:'RETROSPECTIVE_EVALUATION',
  classification:'SYNTHETIC_TEST',prediction_type:'forward_return',horizon_sessions:5,N:1,usable_N:1,
  missing_inconclusive_N:0,excluded_quality_N:0,outcomes:{CONFIRMED:1},forward_return:{N:1,mean:'0.1',median:'0.1'},
  hypothetical_r_expectancy:{N:0,mean:null},evidence_strength:{weak:{N:1,confirmed_N:1}},
  regime:{unavailable:{N:1,confirmed_N:1}},warnings:['SMALL_SAMPLE_NO_EDGE_CLAIM']};
const report={prediction_N:1,usable_N:1,candidate_ledger_N:2,report_id:'report',minimum_descriptive_N:30,groups:[group],
  warnings:['PRE_REGISTERED_AND_RETROSPECTIVE_GROUPS_ARE_SEPARATE'],
  candidate_ledger:[{detector_id:'momentum',detector_version:'1.0.0',outcome:'rejected',status:'NO_EDGE',N:2}]};

function mockApi(initialEntries= [entry]) {
  let entries=initialEntries;
  let evaluations:unknown[]=[];
  const fetcher=vi.fn(async(url:string,options?:RequestInit)=>{
    const path=new URL(url,'http://local').pathname;
    let payload:unknown={};
    if(path.endsWith('/learning/journal')) {
      if(options?.method==='POST') { const body=JSON.parse(String(options.body));entries=[{...entry,...body}];payload=entries[0]; }
      else payload={items:entries};
    } else if(path.endsWith('/revisions')) {
      if(options?.method==='POST') { const body=JSON.parse(String(options.body));entries=[{...entry,...body.draft,revision:2}];payload=entries[0]; }
      else payload={items:[{entry,reason:'Original creation'}]};
    } else if(path.endsWith('/learning/predictions')) payload=options?.method==='POST'?prediction:{items:[prediction]};
    else if(path.endsWith('/evaluate')) { evaluations=[{evaluation_id:id,status:'INCONCLUSIVE',metric_value:null,
      forward_return:null,evaluation_manifest_id:manifest,source_manifest_id:manifest,observed_sessions:4,expected_sessions:5,
      prediction_freshness:'stale',evaluation_quality:'gaps_or_uncertain',warnings:['EXPECTED_SESSION_GAP'],evaluated_at:context.as_of}];payload=evaluations[0]; }
    else if(path.endsWith('/predictions/'+id)) payload={prediction,evaluations,revisions:[{revision:1,status:'OPEN',reason:'EXPLICIT_CREATION'}]};
    else if(path.endsWith('/postmortem')) payload={...entry,classification:'SYNTHETIC_TEST',author:'cortex_template',
      category:'outcome_review',title:'Review: BTC expectation',links:{prediction_id:id},
      structured_content:{actual_outcome:'INCONCLUSIVE; metric unavailable'}};
    else if(path.endsWith('/performance')) payload=report;
    else if(path.endsWith('/review-queue')) payload={open_N:1,due_N:1,due:[prediction],recent_outcomes:[]};
    else if(path.endsWith('/edges')) payload={items:[]};
    return {ok:true,status:200,json:async()=>payload};
  });
  vi.stubGlobal('fetch',fetcher);
  return fetcher;
}

describe('Phase 7 private journal and learning workspace',()=>{
  it('records notes and appends revisions with explicit reasons',async()=>{
    const fetcher=mockApi([]);
    render(<LearningPane context={context as never}/>);
    fireEvent.change(screen.getByLabelText('Journal title'),{target:{value:entry.title}});
    fireEvent.change(screen.getByLabelText('Journal notes'),{target:{value:entry.notes}});
    fireEvent.click(screen.getByRole('button',{name:'Save journal entry'}));
    const timeline=await screen.findByRole('button',{name:/Original expectation note · research_note/});
    fireEvent.click(timeline);
    expect(await screen.findByText(/Revision 1:/)).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText('Journal notes'),{target:{value:'Later review preserves original revision'}});
    fireEvent.change(screen.getByLabelText('Journal revision reason'),{target:{value:'Clarify the original assumption'}});
    fireEvent.click(screen.getByRole('button',{name:'Save revision'}));
    await waitFor(()=>expect(fetcher.mock.calls.some(([url,options])=>String(url).endsWith('/revisions')&&options?.method==='POST')).toBe(true));
    const call=fetcher.mock.calls.find(([url,options])=>String(url).endsWith('/revisions')&&options?.method==='POST')!;
    expect(JSON.parse(String(call[1]?.body))).toMatchObject({expected_revision:1,reason:'Clarify the original assumption'});
  });
  it('keeps retrospective labels, missing-session outcomes and accepted post-mortem drafts visible',async()=>{
    const fetcher=mockApi();
    render(<LearningPane context={context as never}/>);
    fireEvent.click(screen.getByRole('button',{name:'Prediction Ledger'}));
    fireEvent.change(screen.getByLabelText('Prediction title'),{target:{value:prediction.title}});
    fireEvent.change(screen.getByLabelText('Prediction registration'),{target:{value:'RETROSPECTIVE_EVALUATION'}});
    fireEvent.change(screen.getByLabelText('Prediction baseline session'),{target:{value:'2026-09-20'}});
    fireEvent.click(screen.getByRole('button',{name:'Record expectation'}));
    await waitFor(()=>expect(fetcher.mock.calls.some(([url,options])=>String(url).endsWith('/predictions')&&options?.method==='POST')).toBe(true));
    const request=fetcher.mock.calls.find(([url,options])=>String(url).endsWith('/predictions')&&options?.method==='POST')!;
    expect(JSON.parse(String(request[1]?.body))).toMatchObject({registration:'RETROSPECTIVE_EVALUATION',baseline_session:'2026-09-20',manifest_id:manifest});
    fireEvent.click(await screen.findByRole('button',{name:prediction.title}));
    expect(await screen.findByText(/Frozen context/)).toBeInTheDocument();
    await waitFor(()=>expect(screen.getByRole('button',{name:'Evaluate with active manifest'})).not.toBeDisabled());
    fireEvent.click(screen.getByRole('button',{name:'Evaluate with active manifest'}));
    expect(await screen.findByText(/EXPECTED_SESSION_GAP/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button',{name:'Draft post-mortem'}));
    expect(await screen.findByDisplayValue('Review: BTC expectation')).toBeInTheDocument();
    expect(screen.getByText(/Author: cortex_template/)).toBeInTheDocument();
  });
  it('shows review due counts, sample sizes, rejection coverage and no edge claims',async()=>{
    mockApi();render(<LearningPane context={context as never}/>);
    fireEvent.click(screen.getByRole('button',{name:'Review Queue'}));
    expect(await screen.findByText(/due N=1/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button',{name:'Performance'}));
    expect(await screen.findByText(/Prediction N=1/)).toBeInTheDocument();
    expect(screen.getByText(/SMALL_SAMPLE_NO_EDGE_CLAIM/)).toBeInTheDocument();
    expect(screen.getByText('rejected')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button',{name:'Lessons & Edges'}));
    expect(screen.getByText(/No edge is proven/)).toBeInTheDocument();
  });
});
