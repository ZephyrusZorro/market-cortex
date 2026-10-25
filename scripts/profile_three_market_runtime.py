"""Measure existing independent HTTP/search runtime; no servers or SQL."""
import argparse
import json
import math
import time
from datetime import datetime,timezone
from pathlib import Path
from statistics import median
from urllib.parse import urlencode,urlparse,parse_qs
from urllib.request import urlopen

from playwright.sync_api import sync_playwright,expect


def get(url):
    with urlopen(url,timeout=20) as response:return json.load(response)


def timings(call):
    samples=[]
    for _ in range(10):
        start=time.perf_counter();call();samples.append((time.perf_counter()-start)*1000)
    return {'samples_ms':samples,'median_ms':median(samples),'p95_nearest_rank_ms':sorted(samples)[math.ceil(.95*len(samples))-1]}


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--frontend-port',type=int,choices=[3018,3019],default=3018)
    parser.add_argument('--api-port',type=int,choices=[8677,8678],default=8677)
    args=parser.parse_args(argv)
    if (args.frontend_port,args.api_port) not in {(3018,8677),(3019,8678)}:
        raise ValueError('MATCHING_ISOLATED_RUNTIME_PORTS_REQUIRED')
    ui=f'http://127.0.0.1:{args.frontend_port}'
    if args.output.exists():raise FileExistsError('NEW_REPORT_REQUIRED')
    result={'observed_at':datetime.now(timezone.utc).isoformat(),'http':[],'browser_search':[],
            'owner_writes':False,'database_access':False,'app_server_started':False}
    cases=[('binance','BTCUSDT','BTCUSDT'),('binance','ETHUSDT','ETHUSDT'),
           ('upstox','NSE_EQ|INE002A01018','NSE_EQ|INE002A01018'),
           ('alpaca','AAPL','b0b6dd9d-8b9b-48a9-ba46-b9d54906e415')]
    for base in [f'http://127.0.0.1:{args.api_port}/api/v1/market-data',ui+'/api/market-data']:
        health=get(base+'/health');assert not health['owner_connected'] and all(health['snapshots'].values())
        for provider,query,native in cases:
            urls={'catalog':base+'/catalog?'+urlencode({'provider':provider,'query':query,'limit':50}),
                  'history':base+'/history?'+urlencode({'provider':provider,'native_id':native,'interval':'1d',
                    'start':'2026-09-14T00:00:00Z','end':'2026-10-14T00:00:00Z'})}
            for endpoint,url in urls.items():
                data=get(url);assert data['items']
                result['http'].append({'base':base,'provider':provider,'endpoint':endpoint,'rows':len(data['items']),**timings(lambda:get(url))})
    with sync_playwright() as engine:
        browser=engine.chromium.launch(channel='msedge',headless=True)
        try:
            context=browser.new_context(viewport={'width':1440,'height':1200})
            context.route('**/*',lambda route:route.continue_() if urlparse(route.request.url).netloc==urlparse(ui).netloc else route.abort())
            page=context.new_page();page.goto(ui+'/markets')
            page.locator('[data-history-ready="true"]').wait_for()
            def response_matches(provider,query):
                def matches(response):
                    parsed=urlparse(response.url);params=parse_qs(parsed.query,keep_blank_values=True)
                    return parsed.path=='/api/market-data/catalog' and params.get('provider')==[provider] and params.get('query')==[query]
                return matches
            for provider,query,_ in [cases[0],cases[2],cases[3]]:
                page.get_by_label('Market',exact=True).select_option(provider)
                measurements=[]
                for _ in range(3):
                    # Ensure the input actually changes and wait on the matching
                    # network response, even when AAPL already exists on page 1.
                    page.get_by_label('Search instruments',exact=True).fill('RESET_QUERY_WITH_NO_MATCHES')
                    expect(page.get_by_text('Catalog unavailable or no matches. No prices have been substituted.',exact=True)).to_be_visible()
                    with page.expect_response(response_matches(provider,query)) as pending:
                        start=time.perf_counter();page.get_by_label('Search instruments',exact=True).fill(query)
                    data=pending.value.json()
                    label='Independent provider evidence · '+format(data['total'],',')+' matching catalog records'
                    expect(page.get_by_text(label,exact=False)).to_be_visible()
                    measurements.append((time.perf_counter()-start)*1000)
                result['browser_search'].append({'provider':provider,'query':query,'samples_ms':measurements,'median_ms':median(measurements),
                    'includes_input_debounce':True,'response_verified':True})
            result['extension_injected_attributes']=page.evaluate("() => [...document.querySelectorAll('*')].flatMap(e => [...e.attributes].map(a=>a.name).filter(n=>n.startsWith('bis_')||n.startsWith('__processed_')))")
            result['status']='THREE_MARKET_REAL_HTTP_AND_SEARCH_PROFILED'
            if args.frontend_port==3019:
                assert all(r['p95_nearest_rank_ms']<=250 for r in result['http']), 'WARM_API_PERFORMANCE_GATE'
                assert all(r['median_ms']<=1000 for r in result['browser_search']), 'SEARCH_PERFORMANCE_GATE'
                result['candidate_performance_gates_passed']=True
        finally:browser.close()
    with args.output.open('x',encoding='utf-8') as stream:json.dump(result,stream,indent=2)
    print(json.dumps({'status':result['status'],'report':str(args.output.resolve()),'search_medians':result['browser_search']}))
    return 0


if __name__=='__main__':raise SystemExit(main())
