"""Real pilot API workflow and timings, never permitted against OWNER_MAIN."""
import argparse
import json
import time
import sys
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID
from urllib.parse import urlsplit
import httpx
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))

from market_cortex.operations import load_profile, catalog_for, status
from market_cortex.database import connect
from market_cortex.cortex import CortexService
from market_cortex.cortex_gateway import LocalOpenAICompatibleGateway
from market_cortex.cortex_contracts import ResearchRequest


def main():
    p=argparse.ArgumentParser(); p.add_argument('--profile',type=Path,required=True); p.add_argument('--api',default='http://127.0.0.1:8001')
    p.add_argument('--output',type=Path,default=Path('docs/operations/OPERATIONAL_PILOT_RESULTS.json'))
    args=p.parse_args(); _,settings=load_profile(args.profile)
    target=urlsplit(args.api)
    if settings.environment=='OWNER_MAIN' or target.scheme!='http' or target.hostname!='127.0.0.1' or target.username or target.password or target.path or target.query:
        raise ValueError('ISOLATED_LOOPBACK_PILOT_REQUIRED')
    root=Path(__file__).resolve().parents[1]; catalog=catalog_for(settings); timings={}
    client=httpx.Client(base_url=args.api,timeout=90)
    def call(label,path,*,body=None,params=None):
        before=time.perf_counter()
        response=client.post('/api/v1/'+path,json=body) if body is not None else client.get('/api/v1/'+path,params=params)
        timings[label]={'elapsed_ms':round((time.perf_counter()-before)*1000,2),'http_status':response.status_code}
        response.raise_for_status(); return response.json()
    health=call('health','health')
    assert health['status']=='ready' and health['settings']['environment']==settings.environment
    assert health['manifest_id']==str(catalog.head())
    now=datetime.now(timezone.utc); ctx=call('research_context','workstation/context',params={'as_of':now.isoformat()})
    pinned={'manifest_id':ctx['source_manifest_id'],'as_of':ctx['as_of']}
    dates={**pinned,'from':ctx['history_start'],'to':ctx['evaluation_date']}
    overview=call('dashboard_composition','workstation/overview',params=pinned)
    member=ctx['members'][0]
    chart=call('chart_and_11_indicators','workstation/instrument/'+member['instrument_id'],params=dates)
    feature=call('indicator_rsi14','features/series',params={**dates,'instrument_id':member['instrument_id'],'name':'rsi','period':14,'provider_id':'binance'})
    state=call('market_state','market-state',params={**pinned,'history_from':ctx['history_start'],'evaluation_date':ctx['evaluation_date']})
    scan=call('opportunity_scan_read_only','opportunities/scan',body={**pinned,'mode':'pinned','symbol':'BTCUSDT','record':False})
    research=call('cortex_research_save','cortex/research',body={**pinned,'mode':'pinned','symbol':'BTCUSDT','depth':'deep',
        'question':'Describe the actual recorded BTC market state, freshness and counter-evidence for this operational pilot.'})
    reopened=call('research_reopen','cortex/runs/'+research['run_id'])
    replay=call('research_replay','cortex/runs/'+research['run_id']+'/replay')
    assert reopened['evidence_hash']==research['evidence_hash'] and replay['evidence_reproducible']
    with connect(settings.database_url) as c:
        portfolio=c.execute("SELECT portfolio_id,version FROM portfolio_versions WHERE payload->>'classification'='SYNTHETIC_TEST_PORTFOLIO' ORDER BY recorded_at DESC LIMIT 1").fetchone()
    assert portfolio
    risk=call('risk_synthetic_pilot_read_only','risk/portfolios/'+str(portfolio[0])+'/calculate',body={**pinned,'portfolio_version':portfolio[1],'persist':False})
    phase12=json.loads((root/'docs/quant/PHASE_12_PILOT_RESULTS.json').read_text(encoding='utf-8'))
    recorded=call('quant_recorded_experiment','experimental/experiments/'+phase12['experiments'][2]['experiment_id']+'/result')
    assert recorded
    profile=call('owner_history_eligibility','personalization/profile')
    assert profile['observed_behavior']['genuine_owner_record_N']==0 and not profile['patterns']
    # Genuine network failure to an absent local endpoint, not a mocked successful LLM.
    before=time.perf_counter()
    fallback=CortexService(catalog,settings,gateway=LocalOpenAICompatibleGateway('http://127.0.0.1:1','unavailable',timeout=1)).research(
        ResearchRequest(question='Describe recorded BTC state with unavailable local model.',symbol='BTCUSDT',mode='pinned',
                        manifest_id=UUID(ctx['source_manifest_id']),as_of=now),persist=False)
    timings['model_unavailable_fallback']={'elapsed_ms':round((time.perf_counter()-before)*1000,2)}
    assert fallback.model_provider=='deterministic' and 'LOCAL_MODEL_UNAVAILABLE_OR_INVALID' in fallback.warnings
    result={'status':'VALIDATED_WITH_LIMITATIONS','validated_at':datetime.now(timezone.utc).isoformat(),
        'environment':settings.environment,'market_head':ctx['source_manifest_id'],'as_of':ctx['as_of'],
        'evaluation_date':ctx['evaluation_date'],'bar_N':sum(x['observed_sessions'] for x in ctx['members']),
        'chart_bar_N':len(chart['bars']),'latest_record':chart['bars'][-1],'freshness':[x['freshness'] for x in overview['items']],
        'state_snapshot_id':state['snapshot_id'],'scan_id':scan['scan_id'],'research_run_id':research['run_id'],
        'research_evidence_hash':research['evidence_hash'],'research_replay':replay,
        'research_model_cost':research['model_cost'],'risk_scope':'SYNTHETIC_TEST_PORTFOLIO; NOT_OWNER_HOLDINGS',
        'risk_snapshot_id':risk['snapshot_id'],'timings':timings,'refresh_status':status(settings,now),
        'model_evaluation':'NO_INSTALLED_RUNTIME_OR_MODEL; ACTUAL_FAILURE_FALLBACK_ONLY',
        'owner_history':profile['observed_behavior'],'owner_main':'UNTOUCHED',
        'prior_momentum_OOS':{'return':-.07817165407921722,'N':82},'conclusion':'NO_SUPPORTED_PROFITABLE_EDGE'}
    args.output.write_text(json.dumps(result,indent=2,default=str),encoding='utf-8')
    print(json.dumps({'status':result['status'],'timings':timings,'research_run_id':research['run_id']}))
    client.close()


if __name__=='__main__': main()
