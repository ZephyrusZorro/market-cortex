# Autonomous market workstation validation — 2026-10-14

**Follow-up:** The owner subsequently started the production UI and restarted the optimized independent API. Real production browser/provider/replay/performance acceptance passed; see `PRODUCTION_MARKET_VALIDATION_2026-10-14.md`. The pending startup statements below describe this earlier receipt, not the final production status.

## Assessment

**LIVE-VERIFIED:** independent development workstation, actual Binance historical candles and actual received WebSocket events. **TESTED:** immutable source storage/replay, read-only broker adapters and credential/error boundaries. **BLOCKED:** final production-build runtime measurements and activation of the latest backend fixes require owner server startup/restart because automatic execution review previously rejected agent startup. **DEFERRED_NOT_CONFIGURED:** Upstox authenticated history/stream and Alpaca catalog/history/stream. These are separate from the functioning Binance workstation.

This report supersedes the runtime assessment in the dated October 11 foundation report. It does not promote a release. All changes remain local, uncommitted and unpushed. Protected HEAD and peeled tag remain `cfe696d51b137566c15eebaf734ff7ee0ca95197` / `v1.0.1-operational`.

## Browser errors: evidence and root causes

| Reported message | Finding | Action |
|---|---|---|
| React hydration mismatch with `bis_skin_checked`, `bis_register`, `__processed_*` | The development hydration diff contains attributes injected into client DOM before hydration. These attributes are absent from application source. Both clean Codex browser and fresh nonpersistent headless Edge/Playwright contexts returned no hydration errors. Extension/script injection is the supported cause of this specific mismatch. | No hydration-warning suppression, extension disabling or unrelated application rewrite. |
| `Could not establish connection. Receiving end does not exist.` | Not reproduced in either clean context and absent from the inspected app development log. Consistent with extension messaging to a missing receiver; the responsible extension cannot be identified from available evidence. | No invented attribution or application change to hide it. |
| `[HMR] connected` | Console source is Next development tooling. Playwright network capture observes `/_next/hmr` sockets. | Informational development message; not a Binance subscription. Production runtime has not yet been observed. |

Actual application defects were found separately: no appropriate initial selection, inactive symbols dominating the default list, a history error being hidden by a successful catalog refresh, rolling daily/monthly/weekly ranges, ineffective canvas slider navigation, chart recreation on data updates, and missing closed-candle roll-forward. These have been fixed and functionally exercised.

## Genuine historical data

All data below is in the marker-protected independent archive:

`runtime/multi-market-foundation-0c306424e0eb40148568db23fade99bc`

- BTCUSDT and ETHUSDT each render 30 closed daily candles for September 14 through October 14 exclusive. The archive retains 32 daily bars per primary symbol because earlier ranges also exist.
- BTC daily October 13: O 81850.01, H 84168, L 81033.66, C 83169, volume 14784.0627 BTC.
- ETH daily October 13: O 2447.16, H 2538.52, L 2409.09, C 2497.95, volume 261690.4747 ETH.
- Actual BTC chart observations were tested for every exposed interval: 1m (1,440), 5m (288), 15m (96), 1h (720), 4h (180), 1d (30), 1w (52), 1M (12). These are the selected windows, not claims of complete lifetime history. ETH daily and minute charts were also tested.
- Ten rendered OHLCV/timestamp/volume-unit samples matched fresh public Binance responses exactly. A later corrected rollover also matched all five values, boundaries and units.
- A fresh complete daily comparison across all six locally observed instruments matched 184 stored bars: 0GTRY, ADAUSDT, BTCFDUSD, BTCUSDT, DOTUSDT and ETHUSDT. This is source comparison and API evidence for six instruments; full current browser acceptance focuses on BTC/ETH.
- Search, exact symbol selection, BTC/ETH switching, status filtering, eight BTC timeframes, native zoom/pan/reset and navigation during real price updates passed browser checks. A search can legitimately match wrapped or other native pairs; shortcuts select the exact BTCUSDT/ETHUSDT identity.
- No synthetic fallback candles, mock prices or owner pilot fixtures are used by this route. Upstox/Alpaca source unavailability remains visible.

### Newly discovered immediate-boundary defect

The original BTC 12:50–12:51 UTC minute capture arrived at 12:51:01.584806. It contained close 82963.84 and volume 13.16132; a later direct Binance response contained close 82961.32 and volume 14.98890, with identical declared time boundaries. A boundary timestamp alone was insufficient to classify this immediate REST-mirror sample as finalized.

The source service and UI now wait ten seconds after a Binance close boundary. This is a conservative finalization allowance, not a promise that providers never revise data. Existing captures received within that allowance are reconciled only where a later mature request has not already verified them. Mature request receipts prevent repeated downloads even when values are unchanged. Temporary finalization-related empty results expire at the appropriate boundary rather than hiding the next bar for an hour.

The narrow independent reconciliation used **two provider GETs**, appended **two BTC minute revisions**, performed zero repeated provider requests on replay, and preserved all original before-correction as-of hashes. Original failure evidence is retained. No owner/pilot correction occurred.

The next actual browser rollover, 13:30–13:31 UTC, was received at 13:31:12.485253 and matched a later raw response exactly: O 82661.52, H 82830.01, L 82644, C 82830, V 51.58142 BTC. Forming stream candles remain explicitly display-only.

## Real prices and delivery mechanism

**Provider → backend:** public Binance combined WebSocket, selected BTCUSDT/ETHUSDT mini-ticker and minute-kline channels; one connection, two symbols, four channels. Actual bounded captures received 515 events in 180 seconds, 442 in 150 seconds, and 298 in the final 100-second validation. These are actual observations, not merely successful handshakes.

**Backend → browser:** HTTP GET polling of the local `/api/market-data/prices` route every two seconds. Playwright captured consecutive request intervals of approximately two seconds. The browser itself does not maintain a Binance WebSocket. Its development HMR socket is unrelated.

Two displayed BTC prices (82890.27 and 82806.11), their source-event timestamps and receive timestamps matched unique hash-verified archived Binance ticker events exactly. Chart viewport remained unchanged while those prices updated. Source event time and local received time are displayed separately; mini-ticker event time is not represented as a per-trade execution timestamp.

All validation collectors stopped normally. **Current active live subscriptions: zero.** Retained last quotes correctly become STALE, and stale provisional candles are excluded from the historical display. No persistent collector or schedule was enabled. Historical candles and forming stream display evidence remain distinct; missing tick history is explicitly unrecoverable.

## Current market universe

Fresh provider metadata was captured on October 14, preserving the October 11 snapshots and their lineage. Discovery performs no full-market history ingestion.

| Provider | Current source discovery | Source statuses | Genuine historical instruments locally | Browser history/live acceptance |
|---|---:|---|---:|---|
| Binance spot | 3,689 | 1,380 TRADING; 2,309 BREAK | 6 | BTC/ETH charts, eight BTC timeframes, ETH daily/minute; two live symbols observed in current tests |
| Upstox NSE/BSE cash | 36,255 present; 36,271 retained identities | 22,773 LISTED; 13,481 SUSPENDED; 1 exact series conflict; 16 absent identities retained separately | 0 | Public metadata only; authenticated history/live deferred |
| Alpaca US | No local account catalog | Not configured | 0 | Account discovery/history/live deferred; provider-wide support count unknown |

Indian current-present split is NSE 16,669 / BSE 19,586. These are cash security identities, not a guessed common-equity count. Exact conflict `NSE_EQ|INE058F01019` / ALUFLUOR / BE is flagged and excluded from history fetch, rather than merging listed/suspended series. Absence is not called delisting.

The 1,380 Binance TRADING pairs are metadata candidates for public spot observations, not 1,380 validated active subscriptions. Upstox LISTED status does not establish account entitlements or verified calendars. Alpaca Basic IEX coverage is not consolidated US market volume.

## Performance: measured costs and targeted fixes

No PostgreSQL is involved in the independent explorer. The measured history-read bottleneck was Parquet/JSON processing: one minute request inflated 11,172 JSON records and read 34 files, including the full catalog and unrelated candles.

Changes use exact native-ID lookup through verified catalog scalar columns and skip unrelated candle partitions using hash-verified manifest metadata. Legacy/mixed captures still receive full row filtering; relevant artifacts are rehashed on every read. No integrity cache bypass was introduced.

Five repeated reads of the **same actual archive** before/after the optimization produced identical response hashes:

| Read | Before median | After median | Reduction |
|---|---:|---:|---:|
| BTC daily | 200.79 ms | 42.17 ms | 79.0% |
| BTC minute | 216.55 ms | 71.44 ms | 67.0% |
| ETH daily | 191.07 ms | 38.21 ms | 80.0% |
| Catalog BTC search | 40.58 ms | 40.02 ms | Essentially unchanged |

These are real-data in-process HTTP measurements, not production page-load measurements. They preceded the later source-correction revisions, so unchanged hashes describe that fixed benchmark corpus.

The running API still has its old modules loaded until Terminal 3 restarts. Its measured loopback BTC daily median was 333 ms; the development proxy median was 362 ms. Prices were 5 ms directly / 17 ms through the dev proxy. Cache-hit history returns zero provider requests. Genuine provider paging is separately paced at one GET/second and is not disguised as a local disk delay.

Clean Codex browser development measurements: initial history/canvas readiness 1.59–1.72 seconds; search 441–446 ms including the intentional 250 ms debounce; BTC/ETH switching 888–991 ms. All include automation round trips.

A separate fresh-profile Edge/Playwright run captured first contentful paint at 76–180 ms, document load at 634–669 ms, actual chart data/paint readiness around two seconds with assertion waits, zero errors/warnings, and a stable canvas through local polling. A refined DOM-wait baseline is retained separately for reproducible comparisons. See the JSON receipts for precise methods and per-sample results; development numbers are not labeled production results.

During a 5.26-second loopback request burst, the existing API used 3.92 CPU seconds, and the development Node server used 1.06 CPU seconds. On 20 logical processors these correspond to about 3.7% and 1.0% average whole-machine utilization attributable to those processes during this particular burst. API working set was about 309 MiB; development Node about 1,017 MiB. Cumulative CPU counters were not presented as instantaneous percentages.

The headless test browser's separate ten-second polling window used 0.043 seconds of main-thread task time; JS heap moved from about 63 MiB to 35 MiB after garbage collection. Aggregate browser private bytes were about 495→481 MiB; aggregate RSS includes shared pages and is not unique private memory. The browser was closed afterward. These are development-browser measurements, not owner-application resource use.

Canvas initialization now occurs once per mounted chart. Data updates preserve the chart instance and user viewport; symbol/timeframe changes intentionally remount to reset navigation. This was verified by regression tests and actual live browser navigation.

### Production measurement gate

The latest isolated Webpack production build passed, including TypeScript and static route generation. Its unique directory is named by `runtime/multi-market-production-sandbox-path.txt`; owner and running development `.next` directories are preserved. **Production runtime latency/memory/CPU acceptance is pending**, because no listener exists on 3018 at report preparation. Agent server startup remains subject to the earlier rejection.

Only owner startup is required, not manual diagnostics:

1. In Terminal 3, Ctrl+C the existing independent API and rerun the documented `market_data_cli ... serve --port 8677` command to load the backend fixes.
2. In a new terminal run `scripts/Start-IndependentProductionValidation.ps1` from the repository root. It serves only 3018 with API 8677 and clears owner/pilot connection variables from that terminal.

After startup the agent can run `scripts.benchmark_market_http` and `scripts.benchmark_market_browser` against 3018, perform browser acceptance and record before/after runtime/process metrics. No owner credential or DevTools work is needed.

## Tests and limits

- Latest full Python run: **314 passed, 118 skipped, 13 subtests passed**, one existing Starlette/httpx deprecation warning. All owner/pilot/test connection variables were removed only from the child test process. Skips are separately configured DB/stored-data/restore gates; they are not silently counted as live/owner validation.
- Latest full frontend run: **68 passed across 16 files**. TypeScript and production Webpack build passed.
- Focused source/broker/security tests: **36 passed**, including finalization allowance, early-empty expiry, correction/as-of preservation, exact native lookup, partition pruning and relevant-file tamper rejection.
- Clean browser real-source checks passed. Actual rendered-data comparisons passed, except the retained immediate-boundary mismatch receipt that motivated the implemented fix; its later corrected rollover passed.
- `git diff --check` passed. CRLF conversion notices are not test failures.
- Earlier October 11 isolated PostgreSQL regression (382 passed / 34 skipped) is historical evidence; no current owner database validation is inferred from it.

Outstanding acceptance items: production runtime activation/measurement; Upstox/Alpaca credentialed observations; verified India/US mappings, exchange calendars and corporate-action lineage; separately approved owner import, continuous collection and schedules. No broker account result is fabricated, and no credential request is issued during this independent validation.

## Substantive implementation and files

### Independent foundation implemented earlier in this working tree

- `market_archive.py`: protected independent root, exclusive immutable content-addressed Parquet/manifests, lineage/as-of, integrity, writer lock and partitioned manifest sequencing.
- `market_universe.py`: full native Binance/Upstox/Alpaca catalogs, exact identity/series preservation, lifecycle statuses, safe public streaming gzip parsing, indexed DuckDB search and pinned pagination.
- `market_history.py`: eight source intervals, bounded cache-first GETs, closed bars, source/time/feed/adjustment fields, empty-response expiry, duplicate prevention, corrections and replay.
- `market_stream.py`, `feed_proto/*`: shared selected-symbol feeds, actual Binance events, official Upstox protobuf, Alpaca IEX/explicit delayed feed, auth/subscription diagnostics, capped reconnects, tick gaps, deduplication and immutable checkpoints. Windows checkpoint handling fixed.
- `market_canonical.py`: strict in-memory bridge to existing identity/calendar/Bar contracts; no canonical owner import.
- `market_data_app.py`, `market_data_cli.py`: separately guarded loopback source service and bounded source tools; no PostgreSQL connection, protected ports/roots, read-only source endpoints and cache POST limited to provider GETs.
- `multi_market_probe.py`, `providers.py`: environment credentials, broker GET-only allowlists, secure failure redaction and independent raw-value/feed probes; real authenticated acceptance remains deferred.
- `Set-MarketDataCredentials.ps1`, `Invoke-MultiMarketProbe.ps1`, `Invoke-MarketCatalogSync.ps1`: owner-local DPAPI/ACL/hidden prompts, temporary credential loading, isolated probes and unregistered manual catalog action.
- `pyproject.toml`: optional market-data dependencies. `config/market-data-collection.proposed.json` remains disabled; no collection task registration.
- Workstation `/markets`, dedicated `/api/market-data` proxy, `lib/market-data.ts`, `components/charts.tsx` and focused tests: authentic source candles/volume and separate display-only live evidence. Other workstation research routes are not switched to a fake universe.

### Debugging changes in this validation

- `app/markets/page.tsx`: exact BTC entry, active status default, BTC/ETH switching, separate failures, abort on obsolete selection, retries, actual closed OHLCV/units/timestamps, minute-boundary incremental refresh.
- `lib/market-data.ts`: UTC whole-session/week/month windows, source finalization grace, guarded stream overlay and bounded local-contention retries.
- `components/charts.tsx`: stable canvas lifecycle plus working native zoom/pan/reset.
- `market_universe.py`, `market_data_app.py`, `market_history.py`: profiled read optimization and conservative finalization/reconciliation fix.
- Regression files: `market-data.test.ts`, `markets-page.test.tsx`, `chart-lifecycle.test.tsx`, `test_multi_market_foundation.py`.
- New diagnostics: `review_market_runtime.py`, `verify_browser_market_values.py`, `verify_browser_live_observations.py`, `benchmark_market_reads.py`, `benchmark_market_http.py`, `benchmark_market_browser.py`, `reconcile_independent_candle_boundaries.py` and the isolated production startup script.

Pre-existing owner protection/provider-readiness/refresh changes remain in the working tree and were not deployed or scheduled by this task. No migrations were added or rerun.

## Protected state

No owner/pilot DB was opened, no owner/pilot record was written, no application restart was performed, and no retained backup was deleted or replaced. Owner/pilot ports remained offline after the PC reboot; that is their observed preserved state. The retained backup SHA256 remains `1cb01c848c4fc7ac94d28e533ff506596df917e31518192bdcc5c5ed9c93641a`. The private owner inventory was not refreshed or fabricated. No push, tag change, release or schedule registration occurred.

## Evidence index

- `runtime/market-final-coverage-and-integrity-2026-10-14.json`: fresh catalogs, six complete daily provider comparisons, actual logical bars and integrity.
- `runtime/market-browser-validation-2026-10-14.json`: source chart/timeframe/search/navigation checks.
- `runtime/market-rendered-value-comparison-2026-10-14.json`: ten direct rendered OHLCV comparisons.
- `runtime/market-browser-live-source-match-2026-10-14.json`: retained failed premature-close comparison; genuine live quote matches.
- `runtime/independent-boundary-reconciliation-2026-10-14.json`: narrow correction and preserved as-of receipts.
- `runtime/market-finalization-grace-browser-2026-10-14.json`, `market-browser-live-source-match-final-2026-10-14.json`: corrected actual rollover and exact raw source match.
- `runtime/binance-*-2026-10-14.json`: bounded actual stream receipts, including final 298-event capture.
- `runtime/market-read-performance-before-2026-10-14.json`, `market-read-performance-after-2026-10-14.json`: fixed-corpus optimization results/hashes/profiles.
- `runtime/market-http-api-before-2026-10-14.json`, `market-http-development-2026-10-14.json`, `market-process-burst-2026-10-14.json`: running HTTP/server resource measurements.
- `runtime/market-development-browser-performance-2026-10-14.json`, `market-playwright-development*.json`: independent clean-browser timings, network and CPU/memory.
- `runtime/btcusdt-finalization-verified-2026-10-14.jpg`: corrected actual minute chart, STALE after bounded capture ended.
- `runtime/btcusdt-minute-accepted-live-2026-10-14.jpg`, `ethusdt-daily-accepted-2026-10-14.jpg`: genuine prior live viewport and ETH daily chart screenshots.
- `runtime/market-finalization-python-regression-2026-10-14.log`, `market-finalization-frontend-regression-2026-10-14.log`: latest full regression output.
