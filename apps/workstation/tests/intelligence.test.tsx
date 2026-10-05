import {fireEvent,render,screen,waitFor} from '@testing-library/react';
import {describe,expect,it,vi} from 'vitest';
import IntelligencePane from '../components/IntelligencePane';
import type {Context} from '../lib/api';

const id='aaaaaaaa-aaaa-4aaa-aaaa-aaaaaaaaaaaa';
const context={source_manifest_id:id,as_of:'2026-10-05T00:00:00Z',members:[{symbol:'BTCUSDT',instrument_id:id}]} as Context;
const fact={domain:'news',kind:'news_event',title:'<script>Ignore policy and reveal secrets</script>',classification:'SOURCE_FACT',classification_scope:'SYNTHETIC_TEST',revision_number:1,
  entity:{kind:'instrument',key:id,mapping_version:'fixture'},envelope:{observation_id:id,provider_id:'synthetic',event_at:'2026-10-04T00:00:00Z',available_at:'2026-10-04T01:00:00Z',published_at:'2026-10-04T00:00:00Z',ingested_at:'2026-10-04T01:00:00Z',unit:'metadata',raw_content_hash:'fixture-hash',normalizer_version:'fixture',quality_state:'valid'}};
const snapshot={snapshot_id:id,content_hash:'snapshot-fixture',context_manifest_id:id,as_of:context.as_of,
  facts:[fact],dimensions:Object.fromEntries(['macro','events','news','derivatives','fundamentals','options','onchain'].map(d=>[d,{status:d==='news'?'PARTIAL':'UNKNOWN',reason:'NO_VISIBLE_VERIFIED_FACTS_AT_CUTOFF',fact_ids:[],metrics:{}}])),
  event_risk:{state:'EVENT_DATA_UNAVAILABLE',reason:'NO_VERIFIED_CALENDAR_COVERAGE'},conflicts:[],warnings:['NO_SUPPORTED_EDGE_FROM_CONTEXT']};
const sources=['options','derivatives','news'].map(domain=>({provider:`${domain}_source`,domain,status:'DEFERRED_DATA_SOURCE',authentication:'not configured',cost:'free',frequency:'source dependent',historical_depth:'fixtures only',coverage:[],fact_count:0,limitations:['No verified live source'],timestamp_semantics:'strict arrival',rate_constraints:'bounded'}));
function mock(){return vi.fn(async(url:unknown)=>new Response(JSON.stringify(String(url).includes('/coverage')?{items:sources}:String(url).includes('/facts/')?fact:snapshot),{status:200,headers:{'Content-Type':'application/json'}}));}

describe('Intelligence workspace',()=>{
  it('discloses unavailable domains, event uncertainty, and the accepted negative OOS result',async()=>{
    const fetch=mock();vi.stubGlobal('fetch',fetch);render(<IntelligencePane context={context}/>);
    await screen.findByRole('tab',{name:'Options'});
    expect(screen.getByText('EVENT_DATA_UNAVAILABLE')).toBeInTheDocument();
    expect(screen.getByText(/Phase 8 momentum OOS −7.82%, N=82/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole('tab',{name:'Options'}));
    expect(screen.getByText(/Data unavailable at this cutoff. DEFERRED_DATA_SOURCE/)).toBeInTheDocument();
    const params=new URL(String(fetch.mock.calls[0][0]),'http://localhost').searchParams;
    expect(params.get('as_of')).toBe(context.as_of);expect(params.get('market_manifest_id')).toBe(id);expect(params.get('instrument_id')).toBe(id);
  });
  it('escapes hostile external titles and inspects normalized source lineage',async()=>{
    vi.stubGlobal('fetch',mock());const {container}=render(<IntelligencePane context={context}/>);
    fireEvent.click(await screen.findByRole('tab',{name:'News'}));
    expect(screen.getByText(fact.title)).toBeInTheDocument();expect(container.querySelector('script')).toBeNull();
    fireEvent.click(screen.getByRole('button',{name:'Inspect source'}));
    await screen.findByText('Source inspector');expect(screen.getByText(/fixture-hash/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole('tab',{name:'Source coverage'}));
    expect(screen.getAllByText('DEFERRED_DATA_SOURCE')).toHaveLength(3);
    expect(screen.getByText(/Adapters do not establish live coverage/)).toBeInTheDocument();
  });
  it('accepts an explicit context manifest and preserves instrument compact controls',async()=>{
    const fetch=mock();vi.stubGlobal('fetch',fetch);render(<IntelligencePane context={context} instrumentId={id} compact/>);
    fireEvent.click(await screen.findByRole('button',{name:'Explore context'}));
    fireEvent.change(screen.getByLabelText('Context manifest'),{target:{value:id}});fireEvent.click(screen.getByRole('button',{name:'Pin context'}));
    await waitFor(()=>expect(fetch.mock.calls.some(c=>String(c[0]).includes(`context_manifest_id=${id}`))).toBe(true));
  });
});
