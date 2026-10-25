"""Clean production-browser acceptance using actual loopback source responses.

Runs only against existing independent ports 3018/8677. Starts a disposable
browser, no application server, collector, database or credential loader.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import time
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from statistics import median
from urllib.parse import urlparse, parse_qs, urlencode
from urllib.request import urlopen

from playwright.sync_api import sync_playwright, expect

from .benchmark_market_browser import resources


def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest()


def tooltip_values(text, kind):
    lines=[line.strip() for line in text.splitlines() if line.strip()]
    if kind=='ohlc':
        return {key:Decimal(lines[lines.index(label)+1].replace(',',''))
                for key,label in [('open','open'),('close','close'),('low','lowest'),('high','highest')]}
    return {'volume':Decimal(lines[lines.index('Source volume')+1].replace(',',''))}


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--frontend-port',type=int,choices=[3018,3019],default=3018)
    parser.add_argument('--api-port',type=int,choices=[8677,8678],default=8677)
    parser.add_argument('--expanded-scoped-history',action='store_true')
    args=parser.parse_args(argv)
    if args.output.exists():raise FileExistsError('NEW_RECEIPT_REQUIRED')
    if (args.frontend_port,args.api_port) not in {(3018,8677),(3019,8678)}:
        raise ValueError('MATCHING_ISOLATED_RUNTIME_PORTS_REQUIRED')
    base=f'http://127.0.0.1:{args.frontend_port}'
    with urlopen(base+'/api/market-data/health',timeout=10) as response:
        health=json.load(response)
    assert health['status']=='INDEPENDENT_TEST' and not health['owner_connected'] and not health['database_access']
    assert all(health['snapshots'].values())
    result={'observed_at':datetime.now(timezone.utc).isoformat(),'health':health,
        'profile':'FRESH_NONPERSISTENT_EDGE_NO_EXTENSIONS','production_port':args.frontend_port,'api_port':args.api_port,
        'historical_charts':[],'unavailable_cases':[],'catalogs':[], 'navigation_samples':[],
        'uncaught_errors':[],'console_messages':[],'requests':[],'responses':[],'websockets':[],
        'owner_writes':False,'owner_database_access':False,'server_start':False,'collectors_started':False}
    latest_history={}
    latest_catalog={}
    with sync_playwright() as engine:
        browser=engine.chromium.launch(channel='msedge',headless=True)
        try:
            context=browser.new_context(viewport={'width':1440,'height':1200})
            # Browser assets and market-data proxy only. Other application routes
            # and all external requests are blocked in this acceptance context.
            def allow(route):
                parsed=urlparse(route.request.url)
                if parsed.netloc!=urlparse(base).netloc or (parsed.path.startswith('/api/') and
                        not parsed.path.startswith('/api/market-data/')):
                    route.abort()
                else:route.continue_()
            context.route('**/*',allow)
            def observe_response(response):
                parsed=urlparse(response.url)
                if not parsed.path.startswith('/api/market-data/'):return
                try:
                    payload=response.json()
                    result['responses'].append({'path':parsed.path,'status':response.status,
                        'code':payload.get('code'), 'state':payload.get('state'),
                        'rows':len(payload.get('items',[])),'elapsed_ms':response.request.timing['responseEnd']})
                    if response.ok and parsed.path.endswith('/history'):
                        params=parse_qs(parsed.query)
                        latest_history[(params['provider'][0],params['native_id'][0],params['interval'][0])]=payload
                    if response.ok and parsed.path.endswith('/catalog'):
                        latest_catalog['value']=payload
                except Exception as error:
                    result.setdefault('observer_errors',[]).append(type(error).__name__)
            for index in range(3):
                page=context.new_page()
                page.on('pageerror',lambda error:result['uncaught_errors'].append(str(error)))
                page.on('console',lambda message:result['console_messages'].append({'level':message.type,'text':message.text})
                        if message.type in {'error','warning'} else None)
                page.on('websocket',lambda socket:result['websockets'].append(socket.url))
                page.on('response',observe_response)
                page.on('request',lambda request:result['requests'].append({'at':time.time(),'method':request.method,
                        'path':urlparse(request.url).path}) if '/api/market-data/' in request.url else None)
                start=time.perf_counter();page.goto(base+'/markets',wait_until='load')
                page.locator('[aria-label="Latest closed OHLCV"][data-history-ready="true"]').wait_for(timeout=30_000)
                page.locator('canvas').wait_for()
                page.evaluate('() => new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)))')
                result['navigation_samples'].append({'sample':index,'navigation_to_chart_ms':(time.perf_counter()-start)*1000,
                    'paint':page.evaluate('() => performance.getEntriesByType("paint").map(p=>({name:p.name,ms:p.startTime}))')})
                if index<2:page.close()
            chart=page.locator('[aria-label="Provider OHLC candlesticks and volume with pan and zoom"]')
            ready=page.locator('[aria-label="Latest closed OHLCV"][data-history-ready="true"]')
            catalog=page.get_by_label('Instrument catalog',exact=True)

            def select(provider,query,symbol,exchange):
                page.get_by_label('Market',exact=True).select_option(provider)
                page.get_by_label('Search instruments',exact=True).fill(query)
                button=page.get_by_role('button',name=re.compile('^'+re.escape(symbol)+' · '+re.escape(exchange)))
                button.wait_for(timeout=15_000)
                started=time.perf_counter();button.click()
                page.get_by_role('heading',name=symbol,exact=True).wait_for()
                return started

            for provider,listed_count,total_count,inactive_count in [('binance',1380,3689,2309),
                    ('upstox',22773,36255,13481),('alpaca',14382,33550,19168)]:
                page.get_by_label('Market',exact=True).select_option(provider)
                page.get_by_label('Search instruments',exact=True).fill('')
                page.get_by_label('Instrument status',exact=True).select_option({'binance':'TRADING','upstox':'LISTED','alpaca':'active'}[provider])
                expect(page.get_by_text(re.compile(r'Independent provider evidence · '+f'{listed_count:,}'.replace(',','[,]')+r' matching'))).to_be_visible()
                first=latest_catalog['value'];assert first['total']==listed_count
                first_ids=[r['native_id'] for r in first['items']]
                page.get_by_role('button',name='Next',exact=True).click()
                expect(page.get_by_role('button',name='Previous',exact=True)).to_be_enabled()
                expect(catalog.get_by_role('button').first).not_to_have_text(re.compile(re.escape(first['items'][0]['name'])))
                second=latest_catalog['value']
                assert second['offset']==50 and second['snapshots']==first['snapshots']
                assert not set(first_ids)&{r['native_id'] for r in second['items']}
                page.get_by_label('Instrument status',exact=True).select_option('')
                expect(page.get_by_text(re.compile(r'Independent provider evidence · '+f'{total_count:,}'.replace(',','[,]')+r' matching'))).to_be_visible()
                page.get_by_label('Instrument status',exact=True).select_option({'binance':'BREAK','upstox':'SUSPENDED','alpaca':'inactive'}[provider])
                expect(page.get_by_text(re.compile(r'Independent provider evidence · '+f'{inactive_count:,}'.replace(',','[,]')+r' matching'))).to_be_visible()
                result['catalogs'].append({'provider':provider,'listed_count':listed_count,'all_count':total_count,
                    'inactive_count':inactive_count,'pinned_second_page':True})
                page.get_by_label('Instrument status',exact=True).select_option({'binance':'TRADING','upstox':'LISTED','alpaca':'active'}[provider])

            chart_cases=[
                    ('binance','BTCUSDT','BTCUSDT','BINANCE_SPOT','BTCUSDT'),
                    ('binance','ETHUSDT','ETHUSDT','BINANCE_SPOT','ETHUSDT'),
                    ('upstox','NSE_EQ|INE002A01018','RELIANCE','NSE','NSE_EQ|INE002A01018'),
                    ('alpaca','AAPL','AAPL','NASDAQ','b0b6dd9d-8b9b-48a9-ba46-b9d54906e415')]
            if args.expanded_scoped_history:
                chart_cases += [
                    ('upstox','BSE_EQ|INE002A01018','RELIANCE','BSE','BSE_EQ|INE002A01018'),
                    ('upstox','NSE_EQ|INE009A01021','INFY','NSE','NSE_EQ|INE009A01021'),
                    ('upstox','BSE_EQ|INE009A01021','INFY','BSE','BSE_EQ|INE009A01021'),
                    ('alpaca','SPY','SPY','ARCA','b28f4066-5c6d-479b-a2af-85dc1a8f16fb'),
                    ('alpaca','QQQ','QQQ','NASDAQ','2d9e926c-e17c-47c3-ad8c-26c7a594e48f')]
            for provider,query,symbol,exchange,native in chart_cases:
                start=select(provider,query,symbol,exchange)
                ready.wait_for(timeout=30_000);chart.locator('canvas').wait_for()
                page.evaluate('() => new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)))')
                chart_ms=(time.perf_counter()-start)*1000
                history=latest_history[(provider,native,'1d')]
                assert history['items'] and history['state']=='HISTORICAL'
                text=ready.inner_text();row=history['items'][-1]
                labels=re.search(r'Open ([\d.]+) · high ([\d.]+) · low ([\d.]+) · close ([\d.]+)',text)
                volume=re.search(r'Volume ([\d.]+)',text)
                assert labels and volume
                assert [Decimal(v) for v in (*labels.groups(),volume[1])]==[Decimal(row[k]) for k in ('open','high','low','close','volume')]
                assert row['start_at'] in text and row['end_at'] in text
                # A completed bounded capture can retain a truthful STALE
                # price snapshot. It does not invalidate the separate daily
                # historical chart or imply a currently connected collector.
                assert 'Historical close:' in page.locator('main').inner_text()
                rendered=[]
                for index in sorted({0,len(history['items'])//2,len(history['items'])-1}):
                    box=chart.bounding_box();x=box['x']+45+(box['width']-120)*(index+.5)/len(history['items'])
                    sample=history['items'][index]
                    page.mouse.move(x,box['y']+160)
                    expect(chart).to_contain_text('Source OHLC')
                    expect(chart).to_contain_text(sample['start_at'])
                    plotted=tooltip_values(chart.inner_text(),'ohlc')
                    assert all(plotted[k]==Decimal(sample[k]) for k in ('open','close','low','high'))
                    page.mouse.move(x,box['y']+470)
                    expect(chart).to_contain_text('Source volume')
                    expect(chart).to_contain_text(sample['start_at'])
                    plotted_volume=tooltip_values(chart.inner_text(),'volume')['volume']
                    assert plotted_volume==Decimal(sample['volume'])
                    rendered.append({'start_at':sample['start_at'],'open':sample['open'],'high':sample['high'],
                        'low':sample['low'],'close':sample['close'],'volume':sample['volume'],'tooltip_exact':True})
                page.mouse.move(15,15)
                label=(provider+'-'+exchange+'-'+symbol if args.expanded_scoped_history else symbol).lower()
                image=args.output.parent/(args.output.stem+'-'+label+'.png')
                if image.exists():raise FileExistsError('NEW_SCREENSHOT_REQUIRED')
                page.screenshot(path=str(image),full_page=True)
                result['historical_charts'].append({'provider':provider,'native_id':native,'symbol':symbol,'exchange':exchange,
                    'rows':len(history['items']),'api_items_hash':digest(history['items']),'api_items':history['items'],
                    'chart_ready_ms':chart_ms,'visible_ohlcv':text,'plotted_samples':rendered,'screenshot':str(image.resolve()),
                    'history_error':page.get_by_role('alert').all_text_contents()})
                # Observe stable chart instance and navigation across HTTP polls.
                canvas=chart.locator('canvas').element_handle()
                page.get_by_role('button',name='Zoom in',exact=True).click()
                viewport=page.get_by_label('Chart viewport').inner_text()
                page.wait_for_timeout(2200)
                assert canvas.evaluate('(c)=>c.isConnected')
                assert page.get_by_label('Chart viewport').inner_text()==viewport
                page.get_by_role('button',name='Pan earlier',exact=True).click()
                earlier=page.get_by_label('Chart viewport').inner_text();assert earlier!=viewport
                page.get_by_role('button',name='Pan later',exact=True).click()
                assert page.get_by_label('Chart viewport').inner_text()==viewport
                page.get_by_role('button',name='Reset view',exact=True).click()
                result['historical_charts'][-1]['pan_zoom_stable_during_polling']=True

            unavailable_cases=[
                    ('upstox','BSE_EQ|INE002A01018','RELIANCE','BSE','BSE_EQ|INE002A01018'),
                    ('upstox','NSE_EQ|INE009A01021','INFY','NSE','NSE_EQ|INE009A01021'),
                    ('alpaca','SPY','SPY','ARCA','b28f4066-5c6d-479b-a2af-85dc1a8f16fb')]
            if args.expanded_scoped_history:
                unavailable_cases=[]
                for provider,query in [('upstox','NSE_EQ|INE040A01034'),('alpaca','MSFT')]:
                    with urlopen(base+'/api/market-data/catalog?'+urlencode(
                            {'provider':provider,'query':query,'limit':50}),timeout=10) as response:
                        discovered=json.load(response)['items']
                    matching=[r for r in discovered if r['native_id']==query or r['symbol']==query]
                    assert len(matching)==1
                    item=matching[0]
                    unavailable_cases.append((provider,query,item['symbol'],item['exchange'],item['native_id']))
            for provider,query,symbol,exchange,native in unavailable_cases:
                start=select(provider,query,symbol,exchange)
                expect(page.get_by_text('UNAVAILABLE — no genuine candles returned for this selection.',exact=True)).to_be_visible(timeout=20_000)
                assert page.locator('canvas').count()==0 and ready.count()==0
                history=latest_history[(provider,native,'1d')]
                assert not history['items'] and history['state']=='UNAVAILABLE'
                result['unavailable_cases'].append({'provider':provider,'native_id':native,'symbol':symbol,
                    'elapsed_ms':(time.perf_counter()-start)*1000,'api_rows':0,'canvas_count':0,
                    'visible_state':'UNAVAILABLE','refresh_diagnostic':page.get_by_role('alert').all_text_contents()})

            start=select('alpaca','AAPL','AAPL','NASDAQ');ready.wait_for()
            page.get_by_label('Timeframe',exact=True).select_option('1m')
            expect(page.get_by_text('UNAVAILABLE — no genuine candles returned for this selection.',exact=True)).to_be_visible()
            assert page.locator('canvas').count()==0
            page.get_by_label('Timeframe',exact=True).select_option('1d');ready.wait_for()
            assert latest_history[('alpaca','b0b6dd9d-8b9b-48a9-ba46-b9d54906e415','1d')]['total']==9
            result['broker_timeframe_missing_then_daily_recovered']=True
            page.get_by_label('Search instruments',exact=True).fill('NO_SUCH_MARKET_CORTEX_SYMBOL')
            expect(page.get_by_text('Catalog unavailable or no matches. No prices have been substituted.',exact=True)).to_be_visible()
            result['unknown_search_returns_no_invented_instrument']=True

            cdp=context.new_cdp_session(page);cdp.send('Performance.enable')
            metrics_before={r['name']:r['value'] for r in cdp.send('Performance.getMetrics')['metrics']}
            result['resources_before_idle']=resources();page.wait_for_timeout(5000)
            metrics_after={r['name']:r['value'] for r in cdp.send('Performance.getMetrics')['metrics']}
            result['resources_after_idle']=resources()
            result['browser_metrics']={'js_heap_used_bytes':metrics_after['JSHeapUsedSize'],
                'idle_task_cpu_seconds':metrics_after['TaskDuration']-metrics_before['TaskDuration'],'idle_seconds':5}
            result['browser_version']=browser.version
            result['chart_navigation_median_ms']=median(r['navigation_to_chart_ms'] for r in result['navigation_samples'])
            result['symbol_switch_median_ms']=median(r['chart_ready_ms'] for r in result['historical_charts'])
            if args.frontend_port==3019:
                assert not any(r['method']!='GET' for r in result['requests']), 'CANDIDATE_BROWSER_MUST_NOT_REQUEST_SOURCE_WRITES'
                assert not result['websockets'], 'BOUNDED_BACKEND_CAPTURES_ARE_SEPARATE_FROM_BROWSER_HTTP_POLLING'
                assert not result['console_messages'], 'CANDIDATE_CONSOLE_ERRORS_OR_WARNINGS'
                assert result['chart_navigation_median_ms']<=1500, 'INITIAL_CHART_PERFORMANCE_GATE'
                assert all(r['chart_ready_ms']<=750 for r in result['historical_charts']), 'SYMBOL_SWITCH_PERFORMANCE_GATE'
                result['cache_only_browser_requests_verified']=True
            result['status']='CACHED_THREE_MARKET_BROWSER_VALIDATED' if not result['uncaught_errors'] and not result.get('observer_errors') else 'BROWSER_ERRORS_REQUIRE_REVIEW'
        except Exception as error:
            result['status']='BROWSER_ACCEPTANCE_FAILED'
            result['failure']={'type':type(error).__name__,'reason':str(error)[:1600]}
            if 'page' in locals() and not page.is_closed():
                result['failure']['visible_page']=page.locator('main').inner_text()[:6000]
        finally:browser.close()
    with args.output.open('x',encoding='utf-8') as stream:json.dump(result,stream,indent=2)
    print(json.dumps({'status':result['status'],'report':str(args.output.resolve()),
        'historical_symbols':[r['symbol'] for r in result['historical_charts']],
        'uncaught_errors':len(result['uncaught_errors']),'websockets':len(result['websockets']),
        'chart_navigation_median_ms':result.get('chart_navigation_median_ms'),'symbol_switch_median_ms':result.get('symbol_switch_median_ms'),
        'failure':result.get('failure')}))
    return 0 if result['status']=='CACHED_THREE_MARKET_BROWSER_VALIDATED' else 1


if __name__=='__main__':raise SystemExit(main())
