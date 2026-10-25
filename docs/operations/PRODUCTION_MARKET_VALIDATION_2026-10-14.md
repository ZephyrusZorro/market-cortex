# Independent production market workstation — acceptance, 2026-10-14

## Result

**BINANCE_INDEPENDENT_PRODUCTION_VALIDATED.** The owner started the compiled frontend on `127.0.0.1:3018` and restarted the optimized independent API on `127.0.0.1:8677`. Actual browser, HTTP, provider-value, live-event, replay and resource checks passed. The production-startup gate in the earlier autonomous report is now closed. No additional owner action is required for this independent Binance acceptance.

This is acceptance of the independent market explorer, not a new release or three-market OWNER_MAIN deployment. Upstox/Alpaca authenticated data and canonical mapping/calendar gates remain deferred. No owner or pilot application was started/stopped or connected by this validation. Their ports remained offline at inspection after the earlier PC reboot.

## Actual build and browser

- Production build ID: `DtQIrwong0xKe8a4j0Wzg`.
- The compiled sandbox's market page, chart component, data helper and proxy source hashes match the verified repository implementation.
- Fresh nonpersistent headless Edge/Playwright profile and the Codex in-app browser both exercised the real production page. No synthetic requests, mocked prices or seeded broker data were used.
- Zero JavaScript errors, console warnings and hydration errors in the clean production profile. No HMR messages or HMR WebSockets in production.
- Earlier extension-injected `bis_skin_checked`, `bis_register` and `__processed_*` hydration attributes remain absent from source and clean browsers. The receiving-end messaging warning was not reproduced; an extension origin remains the likely explanation, but the exact extension is unidentified. No warning suppression or extension/security setting changes occurred.

## Historical charts and genuine provider comparison

BTCUSDT passed production chart requests for all eight exposed timeframes: 1m, 5m, 15m, 1h, 4h, 1d, 1w and 1M. The requested windows rendered 1,440, 288, 96, 720, 180, 30, 52 and 12 closed candles respectively. ETHUSDT minute and daily switching also passed.

**All 11 rendered OHLCV samples matched fresh public Binance responses exactly**, including start/end timestamps and native volume units. This includes eight BTC timeframe samples, the initial BTC daily chart, ETH daily and ETH minute. The earlier 184-bar, six-instrument daily comparison remains valid; fresh post-startup BTC and ETH comparisons each matched all 32 retained daily observations.

The fixed finalization allowance was present in the actual production build. Its BTC minute 14:56–14:57 UTC sample was received at 14:57:16.955461 and matched the raw source: open 81818.01, high 81840, low 81782, close 81820, volume 21.16457 BTC. ETH 14:57–14:58 was received at 14:58:17.893200 and also matched. The earlier premature-close failure receipt and correction revisions are retained; no historical evidence was overwritten.

Source history is raw and explicitly closed; forming stream candles are displayed separately and excluded from pinned research. Provider responses can still be revised later: the ten-second allowance is a conservative finalization policy, not a claim that a provider can never correct its history.

## Live prices: observed, not inferred from a handshake

- A real 180-second production validation capture received **533 events**, with zero reconnects, duplicates or out-of-order observations. Its bounded recovery fetched only the interrupted 13:31–14:51 UTC minute range, using two provider GETs; tick history remained explicitly unavailable.
- A subsequent 240-second capture received **710 real events**. Both stopped normally with `connected=false` afterward. No persistent/background collector or scheduler was enabled.
- Selected symbols were BTCUSDT and ETHUSDT: one public Binance combined connection with mini-ticker and minute-kline channels, four channels in total.
- Production UI displayed BTC prices **81834.54 → 81834.55** at distinct source/receive times and ETH **2425.79**. All three price, symbol, source-event and receive-time combinations matched unique hash-verified archived ticker events exactly.
- The 720-of-1,441 BTC zoom viewport was preserved through actual price changes. Symbol/timeframe changes intentionally reset navigation.
- Actual delivery is **Binance WebSocket → backend checkpoint/API → browser HTTP GET every two seconds**. Production browser network capture contained no WebSockets; the browser is polling the local API, not connecting directly to Binance. Source-event time is distinct from receive time and is not mislabeled as a per-trade execution timestamp.
- Current active subscriptions after capture: **zero**. Retained quotes correctly show STALE after disconnection. No fake continuing LIVE state is presented.

## Search, catalog and broker deferral

Actual production search, exact BTC/ETH shortcuts, native symbol switching, status filtering and 50-row pinned catalog pagination passed. Second-page records were observed after the response arrived, rather than treating an offset change as proof that data loaded.

| Provider/market | Current source discovery | Local history | Account/live acceptance |
|---|---:|---:|---|
| Binance spot | 3,689: 1,380 TRADING, 2,309 BREAK | Six instruments | BTC/ETH charts and real events validated |
| Upstox NSE/BSE cash | 36,255 present, plus 16 absent identities retained | Zero | Public catalog only; authenticated history/live deferred |
| Alpaca US | No local authenticated catalog | Zero | DEFERRED_NOT_CONFIGURED; provider-wide count unknown |

Counts refer to the fresh October 14 provider snapshots, not thousands of validated live charts. Indian present records comprise NSE 16,669 / BSE 19,586: 22,773 LISTED, 13,481 SUSPENDED and one exact listed/suspended-series conflict. These are cash security identities, not a guessed count of common equities. `NSE_EQ|INE058F01019` / ALUFLUOR / BE remains flagged and blocked from history fetch.

INFY was discovered separately on NSE and BSE. Selecting NSE INFY produced `History: NOT_CONFIGURED`, zero chart canvases and explicit source unavailability. The US AAPL search produced no authenticated local catalog and zero chart canvases. Neither selection reused Binance prices or generated dummy candles. No broker credential request or trading endpoint call was made.

## Actual runtime performance

Three browser samples and five HTTP samples per endpoint were retained. Browser action/readiness measurements include automation and two animation frames after the ready signal; they are not pure network TTFB. The development/production comparison also includes switching to the optimized API. It is not a controlled attribution of every gain to Next production mode alone. The earlier fixed-archive in-process benchmark isolates the read optimization separately.

| Measurement | Earlier development / old API | Actual production / optimized API |
|---|---:|---:|
| Navigation to real chart readiness, median | 2,080 ms | **936 ms** |
| BTC/ETH symbol change to chart readiness, median | 991 ms | **380 ms** |
| Search, median, including 250 ms debounce and automation | 809 ms | **797 ms** |
| Daily history direct loopback HTTP, median | 333 ms | **80 ms** |
| Daily history frontend proxy HTTP, median | 362 ms | **76 ms** |
| Document HTML response, median | 33 ms | **2.9 ms** |
| Headless browser JS heap after observation | 43.0 MiB | **16.7 MiB** |
| Headless browser aggregate private bytes | 474 MiB | **319 MiB** |
| Browser main-thread task CPU during ten seconds of polling | 0.026 s | **0.008 s** |

Production document load events were 76–96 ms. First contentful paint was 44–172 ms; actual chart readiness was 906–956 ms. These are local-machine samples, not promises for other machines, cold disk caches or missing provider history.

Search has intentionally retained its bounded debounce; no claim of a substantial search optimization is made. Direct catalog median was 65 ms and price reads 4.6 ms; production proxy prices were 9 ms. Cold/missing history is separate: production Cua tests needed about 0.9–2.0 seconds for missing intraday provider ranges, versus about 0.22–0.33 seconds for fully cached daily/week/month/4h windows. Provider paging remains paced, rather than downloading full history on every selection.

The profiled implementation changes eliminate full catalog JSON inflation per history request and prune unrelated candle partitions through verified metadata. Relevant files are still rehashed on read; legacy/mixed captures, corrections and as-of behavior are preserved. Fixed-corpus before/after medians were BTC daily 201→42 ms, BTC minute 217→71 ms and ETH daily 191→38 ms with unchanged response hashes.

Production Node working set during normal existing-tab polling was about **111 MiB**; optimized API about **115 MiB**. Over a measured 15-second polling window, their CPU deltas were **0.031 s** and **0.203 s** respectively. The earlier development Node was about 1,017 MiB. Process working sets are not JavaScript heaps; aggregate browser RSS includes shared pages and is not private memory. The resource receipt explicitly distinguishes the separate benchmark burst with concurrent browser work from the normal polling window.

The stable chart instance and viewport were verified during actual live updates; the resource/performance results do not justify further speculative chart rewrites. No PostgreSQL is on this independent request path, so no SQL bottleneck or database optimization is invented.

## Persistence, replay and cache acceptance

The actual optimized API, production proxy and immutable archive returned matching item hashes at all three knowledge points for the selected daily range:

| Knowledge point | Actual rows |
|---|---:|
| Immediately before the first BTC capture | 0 |
| At the first BTC capture | 28 |
| Current observed state | 30 |

Reopening the known daily range through the production cache POST returned `cache_hit=true`, **zero provider calls** and **zero new revisions**. This is a genuine cache/idempotence result, not a mocked response.

Final archive inspection validated 352 manifests and 300 unique Parquet artifacts, about 12.4 MiB including metadata/checkpoints. These are independent source artifacts, not the owner's 65 protected Phase 1 Parquets. Logical history remains six instruments; immutable revision/event artifacts are not counted as additional instruments.

## Regression and release protection

The market runtime loaded by production matches the verified source hashes and passed the actual integration checks above. The final full regression after secure-provider preparation passed **320 Python tests, 13 subtests and 68 frontend tests**, plus TypeScript and the isolated Webpack build. The 118 Python skips require separately configured DB/stored-data/restore fixtures. They do not stand in for current owner database validation. PostgreSQL 5432 was reachable, but no dedicated test DSN was available and the separate 55432 test cluster was offline. No owner connection was borrowed, test schemas created in protected databases, or database instance restarted. The existing Starlette/httpx deprecation warning remains nonfunctional.

No further market-runtime rewrite was needed after this production run. The standalone broker credential probe was tightened during next-stage preparation: exact historical comparison, authentication, confirmed subscriptions and an error-free capture are all required to pass. Authentication alone or an unconfirmed optional delayed feed cannot report success. Six additional synthetic acceptance tests passed; these are not live broker evidence. The focused broker/source/security/readiness suite passed 55 tests, including the Windows synthetic DPAPI/ACL roundtrip. The full regression was repeated because of this concrete acceptance-guard change.

Additional actual runtime gates passed: eleven direct provider value comparisons, three live-event matches, production errors/HMR absence, navigation/pagination, broker-missing-credential behavior, direct/proxy as-of equality, cache idempotence, compiled source hashes and independent storage integrity.

The execution-review startup restriction was respected; the owner launched/restarted the two independent servers. The agent started only bounded validation collectors and temporary headless test browsers, never an alternate app server to bypass the rejection.

Owner/pilot databases and research records were not opened or written; no migration, reset, owner ingestion, schedule registration, order endpoint, backup deletion, push or release creation occurred. HEAD and peeled protected tag remain `cfe696d51b137566c15eebaf734ff7ee0ca95197`. The retained encrypted backup remains byte-identical with SHA256 `1cb01c848c4fc7ac94d28e533ff506596df917e31518192bdcc5c5ed9c93641a`.

## Remaining gates and personal action

**No personal action is needed to complete the independent Binance validation.** The independent production frontend and API are left running. Bounded collectors are stopped.

- Upstox: owner-local Analytics Token, actual authenticated history/feed observations, verified exchange sessions/mappings, and the identified series conflict remain future gates. Public metadata is proven; authenticated candles are not claimed. The next-stage commands and scope are prepared in `MULTI_MARKET_SECURE_ONBOARDING.md`.
- Alpaca: eligible account keys, actual catalog/history/IEX feed probe, source entitlements, verified asset mapping/session calendars and corporate-action lineage remain future gates.
- Continuous collection, daily schedules, full-universe historical coverage, owner imports and any release/deployment beyond this independent environment need separately approved scopes. A validated selected-symbol feed is not a validated full-market service.
- Source revisions and unrecoverable tick gaps remain explicit limitations. No independent Binance browser or production-startup blocker remains in the tested scope.

## Evidence

- `runtime/market-playwright-production-2026-10-14.json` and `.png`: clean production browser, navigation/paint/action timings, actual network requests, errors, JS heap and process resources.
- `runtime/market-http-api-after-2026-10-14.json`, `market-http-production-2026-10-14.json`: actual server/proxy HTTP samples.
- `runtime/market-production-process-burst-2026-10-14.json`, `market-production-normal-polling-resources-2026-10-14.json`: attributed process CPU/working set and workload notes.
- `runtime/market-production-browser-validation-2026-10-14.json`: actual eight BTC timeframes, ETH minute/daily and live panels.
- `runtime/market-production-rendered-source-comparison-2026-10-14.json`: eleven exact raw-provider comparisons.
- `runtime/market-production-live-source-comparison-2026-10-14.json`: three exact archived live-event matches, preserved viewport and correct closed minute OHLCV.
- `runtime/binance-production-browser-stream-2026-10-14.json`, `binance-production-live-viewport-2026-10-14.json`: 533/710 genuine bounded stream events and recovery.
- `runtime/market-production-broker-deferred-ui-2026-10-14.json`, `market-production-catalog-verified-2026-10-14.json`: missing-credential handling, no dummy candles, completed pagination and current status totals.
- `runtime/market-production-replay-and-cache-2026-10-14.json`: actual API/proxy/archive knowledge-time hashes, zero-fetch replay and compiled-source equality.
- `runtime/market-production-final-inventory-2026-10-14.json`: current independent history, fresh daily comparison and storage integrity; owner/pilot ports preserved offline.
- `runtime/market-production-final-python-regression-2026-10-14.log`: final 320-pass regression after broker acceptance guards were tightened; the frontend 68-pass receipt is unchanged because its implementation was unchanged.
- `runtime/btcusdt-production-live-2026-10-14.jpg`, `ethusdt-production-live-2026-10-14.jpg`: real production live chart captures. Their LIVE labels describe the capture time; current quotes are correctly STALE after the bounded feed stopped.

See the earlier `AUTONOMOUS_MARKET_VALIDATION_2026-10-14.md` for the substantive foundation/file inventory, root-cause investigation and preserved source-correction evidence. This follow-up closes its production runtime gate without replacing the earlier receipts.
