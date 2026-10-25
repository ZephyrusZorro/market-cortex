# Stage A candidate — measured progress and remaining gates

Operation: `stage-a-e492731ff5f94ae4942d4e06a52cd765`. This is a conditional candidate acceptance record. **No owner cutover, Stage B import, Stage C collection, scheduler, release, commit or push has been performed.**

## Protection and isolation

The new owner protection receipt is `runtime/owner-protection-2a833c19b082431183e1feb580f6aba7/report.json`. Its retained bundle is `C:\MarketCortexBackups\owner-current-054f0a6eddbe445b9bb6387b07c6d975.mcbackup`. Independent read-only checks of its isolated restore on the existing PostgreSQL 17 recovery cluster verify all **51 table fingerprints, 13 migration checksums, 1,825 bars, 65 Parquets, five pinned 365-session datasets and six saved research evidence hashes**. The owner-terminal receipt verifies that owner inventory remained unchanged during backup/recovery. The agent used no owner connection; it independently queried only the new recovery database.

Owner proof: `runtime/stage-a-e492731ff5f94ae4942d4e06a52cd765-post-operations-recovery-audit.json`. Saved research language is not regenerated deterministically; its stored record and all six numerical evidence hashes are preserved.

The separate source root is `C:\MarketCortexSources\three-market-v1\stage-a-e492731ff5f94ae4942d4e06a52cd765`. Its original independent provenance marker and all imported immutable manifests remain intact; a separate Stage A profile records conditional authorization.

Two NEW source backups and complete isolated restores passed:

- Initial protected snapshot: `runtime/stage-a-source-protection-ea97a39257b6441daa20665345fccec1.json`.
- After the scoped histories and completed US/crypto captures: `runtime/stage-a-source-protection-95948c2cc4a94bc5803b1b58784954aa.json`.

The latter encrypted bundle is **17,059,893 bytes**, covering **1,637 files, 629 manifests and 539 Parquets**; the source root contains **14,534,128 bytes**, approximately **13.86 MiB / 512 MiB**. Byte inventories, parent chains, source profiles and code/config/build inventories match the restored tree. Both encrypted bundles, both recovery roots and both keys are retained.

Source recovery keys are random and protected with current-user Windows DPAPI outside the repository. Plaintext keys are not stored or displayed. The retained `.key-receipt.json` files identify their encrypted key files. **These keys require the same Windows user/profile; they are not portable passphrase backups.** For off-machine recovery, create another retained source bundle using `Protect-StageASource.ps1` without `-GenerateDpapiRecoveryKey`, retain the hidden-prompt passphrase separately, and verify its isolated restore. Retain the candidate directory too: source bundles contain the application inventory, not its installed Node/Python binaries.

## Versioned candidate

Installation: `C:\MarketCortexCandidates\stage-a-e492731ff5f94ae4942d4e06a52cd765`.

Candidate UI/API: **3019 / 8678**. Existing independent UI/API **3018 / 8677** are preserved. Owner/pilot ports and installations were not selected or modified. The candidate has copied frontend dependencies and a separate production build; it uses the existing Python 3.12 dependency runtime with the candidate source package selected explicitly. No package installation or original `.next` rebuild occurred.

The viewer has **no owner/broker connection, no provider-fetch permission, no collector and no scheduler**. Catalog/history/price reads are local. Every history-fetch POST, including an otherwise approved listing/window, is rejected before provider lookup or network access. Credentialed operations run separately with exact scope and current-user DPAPI loading; temporary environment values are restored.

Build/code receipt: `runtime/stage-a-e492731ff5f94ae4942d4e06a52cd765-build-acceptance.json`. The operational tag and HEAD both remain `cfe696d51b137566c15eebaf734ff7ee0ca95197`.

## Coverage and approved history

| Provider | Discoverable snapshot records | Status coverage | Historical browser acceptance |
|---|---:|---|---|
| Binance spot | 3,689 | 1,380 TRADING; 2,309 BREAK | BTCUSDT and ETHUSDT, 30 daily candles each |
| Upstox NSE/BSE cash | 36,255 | 22,773 LISTED; 13,481 SUSPENDED; 1 conflict | RELIANCE and INFY on both NSE and BSE, eight daily candles per listing |
| Alpaca US stocks/ETFs | 33,550 | 14,382 active; 19,168 inactive | AAPL, SPY and QQQ, nine IEX daily candles each |

Counts refer to retained October 14 provider catalogs. They are discovery counts, not functioning chart or feed counts. Thirteen native instruments have some genuine cached history (including six inherited crypto instruments); **nine were exercised in this Stage A browser acceptance**. Uncached HDFCBANK/MSFT selections correctly return zero observations/canvases. Broker one-minute history remains unavailable outside the separately captured stream observations.

Only the seven authorized broker listings were fetched, for **October 1 inclusive through October 14 exclusive in their native market timezones**. All **59 daily observations** matched fresh independent provider OHLCV/start-timestamp comparisons. **42 new source rows** were appended; unchanged RELIANCE/NSE and AAPL observations produced zero duplicate revisions. The viewer adds no rows on repeated reads. No new Binance history or owner bars were downloaded/imported.

Receipt: `runtime/stage-a-history-f6ceaeed8bc04551bbf7e3f8f903a054.json`. Durable GET admissions: **14 history/comparison, 0 metadata, 0 Upstox authorization**, versus limits **42/21/18 and 81 total**. Existing catalog snapshots were reused; no catalog provider requests occurred during this operation. Browser polling is local and does not consume provider GET quotas.

Upstox adjustment basis remains `provider_unspecified`; Alpaca is raw IEX, with IEX-only volume. Native daily windows are not verified regular exchange-session windows. Canonical identity, session/holiday calendars, corporate-action lineage and redistribution rights remain Stage B gates.

## Genuine live evidence

| Bounded capture | Verified observations | Freshness at arrival | Status |
|---|---:|---|---|
| Binance BTC/ETH, 120 seconds | 350 events: 233 price snapshots and 117 stream candles | Fresh changing prices for both; measured event ages approximately 2.49–2.77 seconds | Completed; socket closed |
| IEX AAPL/SPY/QQQ, 120 seconds | 20,899 events: 20,893 price observations and six minute bars | Fresh changing prices for all three; event ages approximately 2.55–3.20 seconds | Completed; socket closed |
| Upstox four Indian listings | Not attempted in the closed Indian session | Fresh Indian-session evidence still required | Pending active session |

Event age includes local/provider clock differences and is not a pure network-latency measurement. Both completed captures authenticated/subscribed, had zero reconnects/out-of-order observations, and explicitly stopped. Currently live subscriptions: **zero**.

Actual delivery: **exchange WebSocket → bounded backend capture/cache → local price endpoint → browser HTTP polling every two seconds**. The browser uses no exchange WebSocket. BTC/ETH live displayed values and source/receipt timestamps exactly matched the responses driving the DOM. Live AAPL was also directly matched. SPY/QQQ fresh backend observations are verified; after shutdown, all three US stale displays match their API responses exactly. The first US browser harness selected a substring ticker instead of exact SPY; no second US capture was silently performed. Supplemental 90-second IEX browser acceptance is now explicitly authorized, awaiting an open session.

The historical browser harness initially assumed no retained price snapshot existed. It now accepts explicitly stale completed-capture snapshots while separately verifying historical candles. Both original failure receipts remain retained; neither was an OHLCV or source-integrity failure.

The owner has explicitly authorized the supplemental **one-time 90-second IEX capture** for AAPL/SPY/QQQ, with no additional REST requests. It has **not started**: the first resumed clock check was October 14 **20:03:30 UTC**, after the US regular session closed. The addendum refuses closed hours before any source write or one-time admission marker. It uses America/New_York timezone rules and a conservative weekday 09:35–15:55 window; that admission does not certify holidays. Actual fresh events remain mandatory. The authorization is retained and no collector or wake-up job has been registered.

## Production browser and performance

Nine actual candlestick/volume charts passed. First/middle/last tooltip samples total **27 source rows / 135 rendered OHLCV values**, plus latest readouts and UTC window labels. Source-to-API comparisons cover all seven broker histories; chart responses match those caches. Search, native symbol switching, source status filters, pinned pagination, pan/zoom across price polls, uncached/unknown selections and missing-timeframe recovery passed.

- Nine-chart page-to-chart median: **379.53 ms**; cached switches **104.65–211.41 ms**.
- Baseline warm API p95 maximum: **137.15 ms**.
- Search medians including debounce: **342.08 ms Binance, 375.24 ms India, 378.85 ms US**.
- Nine-chart clean browser: **zero console messages, uncaught errors, write requests and browser WebSockets**.
- JS heap: **17,199,320 bytes**; idle main-thread work **4.667 ms / 5 seconds**. Browser private memory approximately **381.5 MiB**; RSS includes shared pages and must not be interpreted as private memory.

Receipts: `runtime/stage-a-e492731ff5f94ae4942d4e06a52cd765-browser-expanded-corrected.json` and `...-performance-baseline.json`. Earlier approximately 333→78 ms history improvement was measured in prior runs with different archives; it is not a controlled Stage A before/after experiment.

## Tests and application recovery

Python: **375 passed, 13 subtests passed, 118 skipped** because their independent DB/stored-data/restore fixtures were not configured; skips do not prove those gates. One existing Starlette/httpx deprecation warning remains. Frontend: **68 passed**, TypeScript passed, isolated production Webpack build passed. New tests cover populated authenticated source recovery, tamper/wrong-key rejection, unsafe archive paths, exclusivity, active collectors, durable retry quotas, strict seven-listing windows, replay/idempotence and stop-on-provenance failure.

Candidate startup exposed Windows Python and NVM Node redirectors with child listener processes. The candidate launcher now records verified listener ancestry and both launchers; shutdown validates exact PID creation times, executables and module paths before selecting processes. The owner executed the candidate-only stop/start successfully. New state: `C:\MarketCortexCandidates\stage-a-e492731ff5f94ae4942d4e06a52cd765\launch-7dfa402fe47d4d57921d823620afb41d\application.json`. Actual listeners and launchers passed identity-only verification. No owner application restart occurred.

Post-restart acceptance passed all nine charts and uncached/missing-timeframe cases, with zero browser errors or writes. Seven scoped history hashes and all request counts matched their pre-restart evidence. Page-to-chart median **397.14 ms**, switch median **220.81 ms** (range **127.56–232.01 ms**), maximum warm API/proxy p95 **145.96 ms**. Search medians including debounce: **344.70 / 385.01 / 387.38 ms** for Binance / India / US. JS heap **14,756,580 bytes**, idle main-thread work **8.531 ms / 5 seconds**. All stayed inside the stated gates; these repeated runs measure recovery stability, not a new speed improvement.

Receipts: `runtime/stage-a-e492731ff5f94ae4942d4e06a52cd765-browser-post-restart.json`, `...-performance-post-restart.json`, `...-restart-data-verification.json`. Independent post-restart read-only queries against the isolated owner restore again verified **51 tables, 13 migrations, 1,825 observations, 65 Parquets, five pinned series and six research hashes**. The current source tree exactly matched its authenticated isolated restoration: `...-post-restart-recovery-audit.json`. Existing retained backups were neither overwritten nor deleted.

Supplemental admission regressions: **26 passed**, covering the new eight tests plus existing scope/acceptance tests; one existing Starlette/httpx warning. Closed hours, weekend/DST boundaries, missing original capture and repeated capture refuse source writes/feed startup. All five affected PowerShell operation/launch/stop scripts parsed successfully. Guarded future owner launch/recovery scripts are preparation only and have not been run.

The live observer now selects exact provider/native identity and exchange, including all four Indian listings, so NSE/BSE symbols cannot be confused. It verified exact AAPL/SPY/QQQ stale source/receipt timestamps and bid/ask/last-trade readouts after restart (`...-exact-listing-stale-browser.json`). Observation receipts explicitly avoid claiming that a finite feed remains running. Combined current gate receipt: `runtime/stage-a-e492731ff5f94ae4942d4e06a52cd765-acceptance-progress-post-restart.json`; status `STAGE_A_CANDIDATE_VALIDATED_PENDING_FRESH_SESSION_GATES`. Frozen candidate source/frontend/build and original production frontend build hashes still match; no supplemental admission record exists.

## Remaining gates and exact production boundary

1. Candidate-only shutdown/startup, pinned hashes, durable GET usage, production-browser and performance recovery **passed**.
2. Obtain fresh Upstox observations for all four Indian listings during an active session. The admission window is a conservative weekday **09:20–15:25 Asia/Kolkata**. Actual official feed `marketInfo.segmentStatus` must confirm **NORMAL_OPEN for NSE_EQ and BSE_EQ**, and every listing needs fresh observations with at least two distinct timestamps. A weekday/time window alone cannot prove an exchange is open. No schedule or overnight collector has been registered. Token type/expiry remains unknown; actual next-session authentication must succeed.
3. Execute the now-authorized supplemental IEX live-DOM capture during an open US session; preserve the initial capture and failure receipt. No new REST/historical requests are authorized by this addendum.
4. After any additional authorized capture, create another retained encrypted source backup and verify its complete isolated recovery. Recheck candidate performance and owner recovery evidence.
5. Produce the final combined acceptance report. **Request final owner cutover approval only after mandatory gates pass.**

The later reviewed cutover must keep the original owner API code/profile on **8765**, use the accepted candidate frontend on **3000**, and route only `/api/market-data/*` to the accepted source sidecar on **8678**. The candidate build remains cache-only; cutover grants no broader history fetch or collection. `/api/*` canonical routes must continue to the owner API. Require fresh read-only owner preflight, unchanged tag/build/source inventory, exact process ownership and free approved ports. Use a separate launcher referencing the candidate frontend; the original fixed-path launcher would start the preserved original frontend and is not a candidate deployment command.

The concrete guarded split-launch command and recovery reversal are prepared in `STAGE_A_CUTOVER_RECOVERY_PROCEDURE_2026-10-15.md`. On failure stop only verified new application processes, retain all diagnostics/data/keys/backups, and restore application routing through the preserved original installation. **Do not restore a database over owner, reset data or attempt an unverified data rollback.** Actual owner startup/read-only research replay and controlled recovery remain final deployment acceptance, after explicit cutover authorization. This document does not authorize or perform that cutover.
