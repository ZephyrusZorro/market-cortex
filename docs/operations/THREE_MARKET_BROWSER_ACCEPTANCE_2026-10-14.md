# Three-market production-browser acceptance — 2026-10-14

Status: **CACHED_THREE_MARKET_BROWSER_VALIDATED**. This is independent historical-cache acceptance, not owner deployment, live-stream acceptance or canonical equity research acceptance.

## Active environment

- API 8677 / PID 11252 reads the exact `runtime/three-market-capped-review-2026-10-14` directory. Verified against the listener process's root argument and working directory; only whitelisted diagnostics were saved.
- Production UI 3018 / PID 18532 proxies to this API. All three active catalog snapshot hashes match the local immutable manifests.
- Independent marker: `INDEPENDENT_MARKET_DATA_TEST`, retained capacity limit 536,870,912 bytes. OWNER_MAIN/PILOT_TEST ports remain offline and were not restarted.
- Fresh, nonpersistent Edge context, version recorded in the browser receipt. External browser requests and unrelated application API routes were blocked. No owner connection, secret loader, application-server launch, stream collector, SQL operation or scheduled task was used.

## Discovery and identity

| Provider | All present native records | Active/listed | Inactive/suspended |
|---|---:|---:|---:|
| Binance spot | 3,689 | 1,380 | 2,309 |
| Upstox cash securities | 36,255 | 22,773 | 13,481 plus one conflict |
| Alpaca US assets | 33,550 | 14,382 | 19,168 |

All three market selectors, all-status/active/inactive filters, exact native/ticker search and pinned second-page navigation passed in the actual production browser. Second-page snapshot IDs remained pinned and rows did not overlap the first page. An unknown symbol produced no invented instrument. Discovery still does not establish chart or live entitlement for every record; Indian cash records include debt/fund securities, and the US asset catalog includes inactive/OTC records.

## Real rendered candles and provenance

| Chart | Current cached rows in the browser | Source attribution | Verification |
|---|---:|---|---|
| BTCUSDT | 30 daily | Binance spot, raw, BTC volume | Exact browser/API/archive hash; all 30 fresh public raw candles matched |
| ETHUSDT | 30 daily | Binance spot, raw, ETH volume | Exact browser/API/archive hash; all 30 fresh public raw candles matched |
| RELIANCE / NSE | 8 daily | Upstox V3, INR/shares, adjustment unspecified | Exact browser/API/archive hash; original secure probe compared all 8 rows |
| AAPL / NASDAQ listing | 9 daily | Alpaca IEX raw, USD/shares | Exact browser/API/archive hash; original secure probe compared all 9 rows |

For every chart, latest OHLCV readouts and exact source start/end timestamps matched the API response. The actual ECharts candlestick and volume tooltips were exercised at the first, middle and last observations: **12 plotted observations / 60 plotted OHLCV values** matched Decimal source values. This verifies plotted values, not merely text beside a canvas. All displayed row payload hashes match the immutable archive's current cached-candle projection. Source response hashes, knowledge timestamps and the original broker receipts remain available in the associated audit.

The fresh Binance checks made exactly two read-only public GETs and compared **60 bars / 300 OHLCV values** plus all open/close boundaries. No source archive data was changed. New credentialed Upstox/Alpaca requests were not made or claimed: their raw-response comparison happened in the earlier authenticated probes, and original raw bodies remain hash-only.

RELIANCE source windows are explicit UTC representations of native India days, e.g. `2026-10-12T18:30:00Z` is October 13 midnight IST. AAPL's native daily start is `04:00Z` in this sample. These are native-provider windows; authoritative session/auction/extended-hours/corporate-action validation remains a canonical-import gate. IEX volume is not consolidated US volume.

## Unavailable and refresh behavior

- BSE RELIANCE, NSE INFY and SPY had zero cached daily observations. Each rendered `UNAVAILABLE`, zero chart canvases and no leftover previous-symbol OHLCV panel.
- AAPL 1-minute selection returned unavailable, then switching back to daily restored its nine genuine candles.
- Zoom/pan/reset worked on all four historical charts. Existing canvas instances and zoom state survived two-second price polling.
- The API process has **no Upstox/Alpaca credential variables loaded**. Automatic historical refresh attempts therefore returned eight explicit `422 / NOT_CONFIGURED` diagnostics during acceptance. Cached RELIANCE/AAPL charts remained intact. These are expected configuration-boundary responses, not failed authentication, synthetic data or a broken cached chart.
- No uncached history, full broker-universe ingestion, inferred corporate actions or synthetic filler was created.

## Live versus historical

All collector states were unavailable; no collector checkpoint was copied into the review bundle. There were **zero browser WebSockets**. The browser made local HTTP price polls every two seconds and correctly reported live-feed unavailable. No new exchange live event was observed or claimed in this session.

Earlier Alpaca AAPL fresh IEX observations and Upstox's stale after-hours snapshot remain historical probe evidence, described in `THREE_MARKET_PROBE_REVIEW_2026-10-14.md`. They were not displayed as an active feed. Live-session acceptance is still required before an owner live-price claim.

## Browser errors

- Zero uncaught JavaScript errors, React hydration errors or unexpected third-party injected attributes in the clean production context.
- No HMR WebSocket in the production build.
- Eight console resource-error entries correspond exactly to the eight expected `NOT_CONFIGURED` HTTP responses above. No other warning/error was observed. Do not report “zero console errors” or hide these diagnostics.
- The older extension-connection/bis/processed-attribute symptoms were not reproduced in the clean context. No extension or working application code was modified to suppress third-party warnings.
- No reproducible persistent chart or selection defect remained in the completed acceptance cases.

## Actual performance

| Measurement | Result | Context |
|---|---:|---|
| First page to painted chart | 965.38 ms | Fresh browser context |
| Two warm page/chart loads | 395.69 / 401.98 ms | Same fresh context, new pages |
| Initial first-contentful paint | 168 ms | First load |
| Symbol switch median | 251.95 ms | Four real cached charts; range 198.27–306.08 ms |
| Search medians | Binance 336.20; India 372.25; US 381.80 ms | Matching network response + DOM result, three samples each; includes 250 ms debounce |
| Direct API history medians | 77.61–88.35 ms | Ten warm samples per instrument |
| Production proxy history medians | 74.99–82.46 ms | Ten warm samples per instrument |
| Production proxy catalog p95 | ≤136.43 ms | Nearest-rank p95 over ten samples; not a population estimate |
| All measured warm HTTP p95 | ≤136.43 ms | Four selected instruments, catalog/history, direct + proxy |
| Browser JS heap | 13.73 MiB | After five-second idle sample |
| Browser private memory | Approximately 360 MiB | Aggregated browser processes; not a leak measurement |
| Browser idle task CPU | 0.004455 seconds / 5 seconds | DevTools Performance task duration |

This confirms the existing read optimization on the active three-market runtime. Earlier direct daily reads were approximately 333 ms before optimization; current Bitcoin warm reads are approximately 78 ms. These are different runs/archives and not a controlled new before/after experiment. Do not attribute every browser-speed difference to a code change in this turn. No frontend application code was changed or rebuilt during this acceptance.

## Safety and regression preparation

The independent archive was **362 manifests, 308 Parquets, 10,675,413 bytes** at completion of the recorded browser cases. A later on-demand history receipt at `2026-10-14T17:48:42.626121Z` appended **170 genuine BTCUSDT 1-minute bars** (`14:58Z` through `17:48Z`), two manifests and one Parquet. Final inventory became **364 manifests, 309 Parquets, 10,685,773 bytes**. All 170 OHLCV values/windows matched a separate fresh public Binance response; no live collector checkpoint was created. The request's caller identity is not recorded in the archive, so it is not attributed to a specific client. All original manifests/artifacts and the four accepted daily datasets remain unchanged. See `runtime/three-market-independent-append-audit-2026-10-14.json`. Do not claim that the entire independent archive stayed unchanged through the later final inventory.

Original broker archives/receipts, owner/pilot records and retained backups were preserved. The retained owner encrypted backup rehashed to its accepted SHA; no current owner SQL inventory/restore is claimed.

New safe preparation: `market_fetch_scope.py` and the optional independent API `fetch_scope` argument reject unapproved provider/native ID/interval/date windows **before lookup, network or archive writes**. An empty scope denies all fetches. This is tested preparation for a future approved candidate, not an active owner profile or owner approval. The running independent API was not restarted to activate this optional feature.

Focused source/probe/security/scope regression: **81 passed**, one existing Starlette/httpx warning. No owner/PostgreSQL integration was executed. Earlier full-suite evidence remains separately dated. The two new browser tools use the existing dedicated temporary Playwright environment; no package was installed into the operational `.venv`.

## Reproducible evidence

- `runtime/three-market-active-api-2026-10-14.json`
- `runtime/three-market-production-browser-acceptance-2026-10-14.json`
- `runtime/three-market-production-http-search-2026-10-14.json`
- `runtime/three-market-binance-value-comparison-2026-10-14.json`
- Four symbol screenshots: `runtime/three-market-production-browser-acceptance-2026-10-14-{btcusdt,ethusdt,reliance,aapl}.png`
- Repeat tools: `python -m scripts.accept_three_market_browser --output <new-receipt.json>` and `python -m scripts.profile_three_market_runtime --output <new-receipt.json>` using the dedicated browser environment. Reports/screenshots are exclusive; existing evidence is never overwritten.

Final owner decision: `STAGE_A_OWNER_WORKSTATION_APPROVAL_2026-10-14.md`. **Stage A/B/C have not been executed or authorized by this receipt.**
