"""Observe real candidate price responses/DOM during an approved finite capture.

Starts only a clean browser. No collectors, exchange requests or data writes.
"""
import argparse
import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from playwright.sync_api import sync_playwright, expect


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--provider', choices=['binance', 'alpaca', 'upstox'], required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--verify-stopped-snapshots',action='store_true')
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError('NEW_LIVE_BROWSER_RECEIPT_REQUIRED')
    result = {'observed_at': datetime.now(timezone.utc).isoformat(), 'provider': args.provider,
              'delivery': 'LOCAL_HTTP_PRICE_POLLING_FROM_BOUNDED_BACKEND_EXCHANGE_WEBSOCKET',
              'symbols': [], 'browser_websockets': [], 'uncaught_errors': [], 'write_requests': [],
              'owner_writes': False, 'provider_requests': 0, 'collector_started_by_browser_test': False}
    latest = {}
    base = 'http://127.0.0.1:3019'
    with sync_playwright() as engine:
        browser = engine.chromium.launch(channel='msedge', headless=True)
        try:
            context = browser.new_context(viewport={'width': 1440, 'height': 1200})
            context.route('**/*', lambda route: route.continue_() if urlparse(route.request.url).netloc == '127.0.0.1:3019'
                          else route.abort())
            page = context.new_page()
            page.on('pageerror', lambda error: result['uncaught_errors'].append(str(error)))
            page.on('websocket', lambda socket: result['browser_websockets'].append(socket.url))
            page.on('request', lambda request: result['write_requests'].append(urlparse(request.url).path)
                    if request.method != 'GET' else None)
            def response_seen(response):
                parsed = urlparse(response.url)
                if response.ok and parsed.path.endswith('/prices'):
                    params = parse_qs(parsed.query)
                    if params.get('native_id'):
                        latest[params['native_id'][0]] = response.json()
            page.on('response', response_seen)
            page.goto(base + '/markets')
            targets = {
                'binance': [('BTCUSDT', 'BINANCE_SPOT', 'BTCUSDT'),
                            ('ETHUSDT', 'BINANCE_SPOT', 'ETHUSDT')],
                'alpaca': [('AAPL', 'NASDAQ', 'b0b6dd9d-8b9b-48a9-ba46-b9d54906e415'),
                           ('SPY', 'ARCA', 'b28f4066-5c6d-479b-a2af-85dc1a8f16fb'),
                           ('QQQ', 'NASDAQ', '2d9e926c-e17c-47c3-ad8c-26c7a594e48f')],
                'upstox': [('RELIANCE', 'NSE', 'NSE_EQ|INE002A01018'),
                           ('RELIANCE', 'BSE', 'BSE_EQ|INE002A01018'),
                           ('INFY', 'NSE', 'NSE_EQ|INE009A01021'),
                           ('INFY', 'BSE', 'BSE_EQ|INE009A01021')],
            }[args.provider]
            page.get_by_label('Market', exact=True).select_option(args.provider)
            for symbol, exchange, selected_native in targets:
                page.get_by_label('Search instruments', exact=True).fill(selected_native if args.provider == 'upstox' else symbol)
                button = page.get_by_label('Instrument catalog', exact=True).get_by_role('button',
                    name=re.compile('^'+re.escape(symbol)+' · '+re.escape(exchange)+r'(?:\s|$)'))
                expect(button).to_be_visible()
                button.click()
                expect(page.get_by_role('heading', name=symbol, exact=True)).to_be_visible()
                observations, seen = [], set()
                deadline = time.monotonic() + (4 if args.verify_stopped_snapshots else 16)
                while time.monotonic() < deadline:
                    page.wait_for_timeout(500)
                    candidates = [(native, value) for native, value in latest.items()
                                  if native == selected_native and any(r['native_id'] == selected_native
                                      and r['symbol'] == symbol for r in value.get('items', []))]
                    if not candidates:
                        continue
                    native, payload = candidates[-1]
                    ordered = sorted(payload['items'], key=lambda r: r['event_at'], reverse=True)
                    preferred = next((r for r in ordered if r.get('price') is not None and not r.get('candle')),
                                     ordered[0] if ordered else None)
                    expected_state='STALE' if args.verify_stopped_snapshots else 'LIVE'
                    if not preferred or preferred['state'] != expected_state:
                        continue
                    key = (preferred['event_at'], preferred['received_at'])
                    if key in seen:
                        continue
                    visible = page.locator('main').inner_text()
                    # Compare the exact response that drove the UI, not a later
                    # independently polled response whose trade may differ.
                    if f'Source timestamp {preferred["event_at"]} · received {preferred["received_at"]}' not in visible:
                        continue
                    expected = f'Last trade: {preferred["price"] if preferred["price"] is not None else "unavailable"}'
                    assert expected in visible
                    assert f'bid {preferred["bid"] if preferred["bid"] is not None else "unavailable"}' in visible
                    assert f'ask {preferred["ask"] if preferred["ask"] is not None else "unavailable"}' in visible
                    seen.add(key)
                    observations.append({k: preferred.get(k) for k in (
                        'native_id', 'symbol', 'kind', 'price', 'bid', 'ask', 'event_at', 'received_at',
                        'feed', 'state', 'source_hash', 'source_exchange', 'bid_exchange', 'ask_exchange')})
                assert observations, 'NO_REAL_MATCHING_PRICE_RENDERED_FOR_' + symbol
                result['symbols'].append({'symbol': symbol, 'exchange': exchange, 'native_id': selected_native,
                                          'matched_observations': observations,
                                          'exact_response_to_dom_verified': True})
            assert not result['uncaught_errors'] and not result['write_requests'] and not result['browser_websockets']
            result['status'] = ('STOPPED_STALE_SNAPSHOTS_HTTP_TO_BROWSER_VERIFIED' if args.verify_stopped_snapshots
                                else 'LIVE_HTTP_POLL_TO_BROWSER_VALUES_VERIFIED')
            result['fresh_price_observed_during_capture']=not args.verify_stopped_snapshots
            # This observer does not control the finite worker or certify that
            # a feed continues after the observation window/receipt is written.
            result['ongoing_live_feed_claimed']=False
        except Exception as error:
            result.update(status='LIVE_BROWSER_NOT_VALIDATED', failure={'type': type(error).__name__, 'reason': str(error)[:1200]})
        finally:
            browser.close()
    with args.output.open('x', encoding='utf-8') as stream:
        json.dump(result, stream, indent=2)
    print(json.dumps({'status': result['status'], 'report': str(args.output.resolve()),
                      'matched_symbols': [r['symbol'] for r in result['symbols']]}))
    return 0 if result['status'].endswith('_VERIFIED') else 1


if __name__ == '__main__':
    raise SystemExit(main())
