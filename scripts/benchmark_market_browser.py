"""Clean-profile Playwright measurement against an already running independent UI.

Starts a temporary headless browser, never an application server. No account
profile, broker credentials, DB connection, migration or persistent collector.
"""
from __future__ import annotations

if not __package__:
    raise SystemExit('Use python -m scripts.benchmark_market_browser')

import argparse
import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

import psutil
from playwright.sync_api import sync_playwright, expect


def resources():
    processes=[]
    for process in psutil.Process().children(recursive=True):
        try:
            if process.name().lower() not in {'msedge.exe','chrome.exe'}:continue
            memory=process.memory_info();cpu=process.cpu_times()
            processes.append({'pid':process.pid,'rss':memory.rss,
                              'private_bytes':getattr(memory,'private',memory.vms),
                              'cpu_seconds':cpu.user+cpu.system})
        except (psutil.NoSuchProcess,psutil.AccessDenied):pass
    return {'processes':processes,'aggregate_rss_bytes':sum(p['rss'] for p in processes),
            'aggregate_private_bytes':sum(p['private_bytes'] for p in processes),
            'cpu_seconds':sum(p['cpu_seconds'] for p in processes),
            'rss_includes_shared_pages':True}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port',type=int,required=True,choices=(3017,3018))
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();base=f'http://127.0.0.1:{args.port}'
    result={'observed_at':datetime.now(timezone.utc).isoformat(),'port':args.port,'profile':'FRESH_NONPERSISTENT_NO_EXTENSIONS',
            'pages':[],'errors':[],'console_warnings':[],'http_requests':[],'websockets':[],
            'owner_writes':False,'database_access':False,'app_server_started':False}
    with sync_playwright() as engine:
        browser=engine.chromium.launch(channel='msedge',headless=True)
        try:
            context=browser.new_context(viewport={'width':1440,'height':1000})
            # Only local page assets/data routes are allowed in this benchmark.
            context.route('**/*',lambda route:route.continue_() if urlparse(route.request.url).netloc==urlparse(base).netloc else route.abort())
            for _ in range(3):
                page=context.new_page()
                page.on('pageerror',lambda error:result['errors'].append(str(error)))
                page.on('console',lambda message:result['console_warnings'].append(message.text) if message.type in {'error','warning'} else None)
                page.on('request',lambda request:result['http_requests'].append({'at':time.time(),'method':request.method,
                    'path':urlparse(request.url).path}) if '/api/market-data/' in request.url else None)
                page.on('websocket',lambda socket:result['websockets'].append({'path':urlparse(socket.url).path,
                    'host':urlparse(socket.url).netloc}))
                start=time.perf_counter();page.goto(base+'/markets',wait_until='load')
                ready=page.locator('[aria-label="Latest closed OHLCV"][data-source-interval="P1D"][data-history-ready="true"]')
                ready.wait_for(state='visible',timeout=20_000)
                page.locator('canvas').wait_for(state='visible')
                page.evaluate('() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)))')
                result['pages'].append({'navigation_to_chart_painted_ms':round((time.perf_counter()-start)*1000,2),
                    'navigation':page.evaluate('() => performance.getEntriesByType("navigation")[0].toJSON()'),
                    'paint':page.evaluate('() => performance.getEntriesByType("paint").map(p=>({name:p.name,ms:p.startTime}))')})
                if len(result['pages'])<3:page.close()
            result['search_ms']=[]
            for _ in range(3):
                page.get_by_label('Search instruments').fill('')
                page.get_by_role('button',name=re.compile(r'^0GTRY ·')).wait_for(state='visible')
                start=time.perf_counter();page.get_by_label('Search instruments').fill('ETHUSDT')
                page.get_by_role('button',name=re.compile(r'^ETHUSDT ·')).wait_for(state='visible')
                result['search_ms'].append(round((time.perf_counter()-start)*1000,2))
            result['switches']=[]
            for symbol in ('ETHUSDT','BTCUSDT','ETHUSDT'):
                start=time.perf_counter();page.get_by_role('button',name=symbol+' chart',exact=True).click()
                page.get_by_role('heading',name=symbol,exact=True).wait_for(state='visible')
                ready.wait_for(state='visible')
                page.evaluate('() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)))')
                result['switches'].append({'symbol':symbol,'chart_ready_ms':round((time.perf_counter()-start)*1000,2),
                                          'ohlcv':ready.inner_text()})
            cdp=context.new_cdp_session(page);cdp.send('Performance.enable')
            before={r['name']:r['value'] for r in cdp.send('Performance.getMetrics')['metrics']}
            result['resources_before_idle']=resources();canvas=page.locator('canvas').element_handle()
            start=time.perf_counter();page.wait_for_timeout(10_000)
            result['idle_seconds']=time.perf_counter()-start
            result['resources_after_idle']=resources()
            after={r['name']:r['value'] for r in cdp.send('Performance.getMetrics')['metrics']}
            result['browser_metrics']={'js_heap_used_before':before['JSHeapUsedSize'],'js_heap_used_after':after['JSHeapUsedSize'],
                'task_cpu_seconds_during_idle':after['TaskDuration']-before['TaskDuration'],
                'same_chart_canvas_after_polling':canvas.evaluate('(canvas)=>canvas.isConnected')}
            result['final_panel']=page.get_by_role('heading',name='ETHUSDT',exact=True).locator('..').inner_text()
            screenshot=args.output.with_suffix('.png')
            if screenshot.exists():raise FileExistsError('SCREENSHOT_ALREADY_EXISTS')
            page.screenshot(path=str(screenshot),full_page=True)
            result['screenshot']=str(screenshot.resolve())
            result['browser_version']=browser.version
            result['status']='VERIFIED' if not result['errors'] and not result['console_warnings'] else 'BROWSER_ERRORS_OBSERVED'
        finally:browser.close()
    with args.output.open('x',encoding='utf-8') as stream:json.dump(result,stream,indent=2)
    print(json.dumps({'status':result['status'],'report':str(args.output.resolve()),'chart_load_ms':[p['navigation_to_chart_painted_ms'] for p in result['pages']],
                      'search_ms':result['search_ms'],'switch_ms':[p['chart_ready_ms'] for p in result['switches']],
                      'errors':len(result['errors']),'warnings':len(result['console_warnings']),'browser_metrics':result['browser_metrics']},indent=2))
    return 0 if result['status']=='VERIFIED' else 1


if __name__=='__main__':raise SystemExit(main())
