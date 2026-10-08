import {render,screen,fireEvent,waitFor} from '@testing-library/react';
import {describe,it,expect,vi} from 'vitest';
import ExperimentalPane from '../components/ExperimentalPane';
const id='aaaaaaaa-aaaa-4aaa-aaaa-aaaaaaaaaaaa',id2='bbbbbbbb-bbbb-4bbb-bbbb-bbbbbbbbbbbb';
const context={history_start:'2024-01-01',evaluation_date:'2026-10-03',source_manifest_id:id,as_of:'2026-10-08T10:00:00Z',members:[{symbol:'BTCUSDT'}]};
const definition={hypothesis_id:id,dataset:{start:'2024-01-01',end:'2026-10-03',manifest_id:id,source_as_of:context.as_of},model:{registry_id:'ridge'},validation:{},configuration:{}};
const record={experiment_id:id,status:'COMPLETED',content_hash:'hash',hypothesis_hash:'hh',recorded_at:context.as_of,definition,event:{}};
const reports={metrics:{N:100,rmse:.1,mae:.07,baseline_skill:-.2},folds:[{fold:1,train_N:200,test_N:100,training_window:['2024-01-01','2024-06-01'],test_window:['2024-08-01','2024-10-01'],metrics:{rmse:.1},mean_baseline:{rmse:.08},probability_status:'PROBABILITY_UNAVAILABLE'}],search:[{alpha:1,objective:.1}],feature_importance:[],regime_research:[],drift:[],calibration:{status:'PROBABILITY_UNAVAILABLE',bins:[]}};
const result={study_id:id,result:{experiment_id:id,manifest:{holdout_status:'PREVIOUSLY_EXAMINED'},dataset_ref:{artifact_id:id,content_hash:'dh'},model_refs:[{artifact_id:id}],result_hash:'rh',result:{status:'COMPLETED',conclusion:'HYPOTHESIS_FALSIFIED',warnings:['NO_SUPPORTED_EDGE'],reports}}};
function mock(empty=false,hostile=false){
  const f=vi.fn(async(url:string,options?:RequestInit)=>{
    let body:unknown={items:[]};
    if(url.endsWith('/registry'))body={models:[{registry_id:'ridge'},{registry_id:'ensemble'}],features:['momentum_5','momentum_20','trend_persistence','volatility_20','relative_strength','volume_ratio']};
    if(url.endsWith('/experiments'))body=options?.method==='POST'?record:{items:empty?[]:[record,{...record,experiment_id:id2}]};
    if(url.endsWith('/hypotheses')&&options?.method==='POST')body={hypothesis_id:id};
    if(url.endsWith('/result'))body=hostile?{...result,result:{...result.result,result:{...result.result.result,warnings:['<script>orders()</script>']}}}:result;
    if(url.endsWith('/jobs'))body={job_id:id,status:'queued'};
    if(url.endsWith('/query'))body={answer:'No supported edge exists.'};
    if(url.endsWith('/replay'))body={status:'MATCH'};
    if(url.endsWith('/dataset'))body={result:{row_N:200,missingness:{funding:200},rows:[]}};
    if(url.endsWith('/analogues')||url.endsWith('/compare'))body={artifact_id:id};
    if(url.includes('/artifacts/'))body={result:{matches:[{session:'2024-05-01',distance:.2,historical_outcome:{value:-.03}}]}};
    return new Response(JSON.stringify(body),{status:200});
  });vi.stubGlobal('fetch',f);return f;
}
async function select(){await screen.findAllByRole('option',{name:/ridge · COMPLETED/});fireEvent.change(screen.getByLabelText('Recorded experiment'),{target:{value:id}});await screen.findByText('HYPOTHESIS FALSIFIED');}
describe('Advanced experimental Quant Lab',()=>{
  it('shows empty state and preserves negative prior evidence',async()=>{mock(true);render(<ExperimentalPane context={context as never}/>);expect(await screen.findByText(/No experiments registered/)).toBeInTheDocument();expect(screen.getByText(/−7.82%/)).toBeInTheDocument();});
  it('registers frozen hypothesis and pinned definition before job execution',async()=>{const f=mock(true);render(<ExperimentalPane context={context as never}/>);fireEvent.click(await screen.findByRole('tab',{name:'Hypotheses'}));fireEvent.click(screen.getByRole('button',{name:'Freeze hypothesis and register experiment'}));await waitFor(()=>expect(f.mock.calls.some(([u,o])=>u.endsWith('/experiments')&&o?.method==='POST')).toBe(true));const call=f.mock.calls.find(([u,o])=>u.endsWith('/experiments')&&o?.method==='POST')!;expect(JSON.parse(call[1]!.body as string).dataset.manifest_id).toBe(id);expect(f.mock.calls.some(([u])=>u.endsWith('/jobs'))).toBe(false);});
  it('renders recorded model metrics, temporal windows and baseline chart',async()=>{mock();render(<ExperimentalPane context={context as never}/>);await select();fireEvent.click(screen.getByRole('tab',{name:'Models'}));expect(screen.getByRole('img',{name:/Recorded temporal test RMSE/})).toBeInTheDocument();expect(screen.getAllByText(/2024-08-01/).length).toBeGreaterThan(0);expect(screen.getByText('-0.20000')).toBeInTheDocument();});
  it('loads actual dataset and labels with missingness',async()=>{const f=mock();render(<ExperimentalPane context={context as never}/>);await select();fireEvent.click(screen.getByRole('tab',{name:'Dataset'}));fireEvent.click(screen.getByRole('button',{name:'Inspect derived dataset'}));await waitFor(()=>expect(f.mock.calls.some(([u])=>u.endsWith('/dataset'))).toBe(true));expect(await screen.findByText('row N')).toBeInTheDocument();});
  it('analogue search uses explicit reference date and stored outcomes',async()=>{const f=mock();render(<ExperimentalPane context={context as never}/>);await select();fireEvent.click(screen.getByRole('tab',{name:'Analogues'}));fireEvent.change(screen.getByLabelText('Reference date'),{target:{value:'2026-09-01'}});fireEvent.click(screen.getByRole('button',{name:'Find historical analogues'}));expect(await screen.findByText('2024-05-01')).toBeInTheDocument();const call=f.mock.calls.find(([u])=>u.endsWith('/analogues'))!;expect(JSON.parse(call[1]!.body as string).reference_date).toBe('2026-09-01');});
  it('pilot cannot approve owner research baseline',async()=>{mock();render(<ExperimentalPane context={context as never} environment="PILOT_TEST"/>);await select();fireEvent.click(screen.getByRole('tab',{name:'Governance'}));fireEvent.change(screen.getByLabelText('Decision'),{target:{value:'HUMAN_APPROVED_RESEARCH_BASELINE'}});expect(screen.getByRole('button',{name:'Record human review'})).toBeDisabled();});
  it('freezes a bounded new proposal while preserving source and validation scope',async()=>{const f=mock();render(<ExperimentalPane context={context as never} environment="PILOT_TEST"/>);await select();fireEvent.click(screen.getByRole('tab',{name:'Governance'}));fireEvent.change(screen.getByLabelText('Proposal regularization'),{target:{value:'2'}});fireEvent.click(screen.getByRole('button',{name:'Propose registered model revision'}));await waitFor(()=>expect(f.mock.calls.some(([u])=>u.endsWith('/proposals'))).toBe(true));const c=f.mock.calls.find(([u])=>u.endsWith('/proposals'))!;const body=JSON.parse(c[1]!.body as string);expect(body.definition.dataset.manifest_id).toBe(id);expect(body.definition.model.alphas).toEqual([2]);expect(f.mock.calls.some(([u])=>u.endsWith('/jobs'))).toBe(false);});
  it('escapes hostile research text and displays probability unavailable',async()=>{mock(false,true);const {container}=render(<ExperimentalPane context={context as never}/>);await select();fireEvent.click(screen.getByRole('tab',{name:'Calibration'}));expect(screen.getByText('PROBABILITY_UNAVAILABLE')).toBeInTheDocument();expect(container.querySelector('script')).toBeNull();});
  it('shows recoverable backend errors',async()=>{vi.stubGlobal('fetch',vi.fn(async()=>new Response('{}',{status:503})));render(<ExperimentalPane context={context as never}/>);expect(await screen.findByRole('alert')).toBeInTheDocument();});
});
