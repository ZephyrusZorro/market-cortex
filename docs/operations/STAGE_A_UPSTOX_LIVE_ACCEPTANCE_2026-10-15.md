# Stage A Upstox fresh-session acceptance — 15 October 2026

**Verdict: PASSED for all four authorized native listings. Overall Stage A remains pending supplemental IEX acceptance.**

Capture price observations: 2026-10-15T11:09:15.182259+05:30 through 2026-10-15T11:11:13.536433+05:30.
Official Upstox feed segment state reported NORMAL_OPEN for NSE_EQ and BSE_EQ before the first price record. Current authentication and all four subscriptions were proved by actual feed observations, not by local token expiry claims.

| Listing | Fresh source observations | Distinct prices | Browser/source matches | Verdict |
|---|---:|---:|---:|---|
| RELIANCE NSE | 211 | 16 | 3 | PASSED |
| RELIANCE BSE | 72 | 25 | 3 | PASSED |
| INFY NSE | 114 | 17 | 3 | PASSED |
| INFY BSE | 47 | 13 | 4 | PASSED |

All 444 accepted observations were fresh at arrival (30-second threshold), with advancing exchange timestamps and changing prices. All provider millisecond timestamps matched stored UTC timestamps. Thirteen actual candidate DOM observations matched captured native identity, symbol, kind, price/bid/ask, source and receipt timestamps, feed and raw payload hash exactly. No fixtures, synthetic prices or provider REST price comparisons were used.

Capture: authorized 120 seconds, one socket, 324 messages, 444 accepted events, 88 duplicates suppressed, 14 out-of-order events retained, zero reconnects/errors. The final latest snapshot for each listing equals its maximum captured exchange timestamp, so out-of-order arrivals did not regress the display. All sockets stopped; live subscriptions now zero. Completed snapshots are stale, not an ongoing live service.

Actual path: Upstox V3 LTPC WebSocket → finite backend capture/cache → local candidate API → candidate browser HTTP polling. LTPC supplies last-trade snapshots; bid/ask/depth and separate execution venue codes are unavailable. Listing exchange is attributed through the explicit NSE/BSE native identity. Source age includes clock differences and is not a transport-latency measurement.

Source cache: 14,750,289 bytes / 536,870,912 ceiling; 216,161 bytes added. Provider GET usage: history/comparison 14, metadata 0, stream authorization 1 (15 total / 81). Category headroom: history 28, metadata 21, authorization 17. No historical/metadata GETs or extra status endpoint calls occurred.

## Retained evidence

- Capture receipt: `C:\Users\faris\OneDrive\Documents\MARKET_CORTEX_Phase_1_Completed\runtime\stage-a-upstox-32ed1099d519478c98d054f1524d66e3.json`
- Browser receipt: `C:\Users\faris\OneDrive\Documents\MARKET_CORTEX_Phase_1_Completed\runtime\stage-a-e492731ff5f94ae4942d4e06a52cd765-upstox-fresh-browser-2026-10-15.json`
- Combined source-comparison acceptance: `C:\Users\faris\OneDrive\Documents\MARKET_CORTEX_Phase_1_Completed\runtime\stage-a-upstox-live-acceptance-255a8b73d76b4441a72ed0eb0420e05f.json`

Old receipts/backups remain retained. The candidate was neither restarted nor rebuilt; owner/pilot databases were not accessed or written. Main/tag remain cfe696d, and engineering b721573 remains isolated and unmerged. No completed historical, full-browser or recovery suite was rerun; the browser work was the previously pending fresh Upstox acceptance only.

## Remaining release gates

1. Already-authorized supplemental IEX capture: one socket, AAPL/SPY/QQQ, at most 90 seconds/200,000 additional events, 64 MiB reserve within 512 MiB, zero additional REST/history/metadata GETs. Do not start before an eligible US session is confirmed. The existing conservative admission begins at 19:05 IST today; no capture or scheduled wake-up has been started.
2. After the remaining capture, create a new retained encrypted source-cache backup and verify isolated recovery of the final expanded evidence. The earlier source backup predates this capture and cannot be described as protecting these new observations. Preserve the owner backup/recovery receipts without repeating completed owner drills unnecessarily.
3. Assemble final acceptance, source budget/resource and isolation evidence; request separate final OWNER_MAIN cutover approval. No automatic cutover, Stage B/C, imports, continuous collection, schedules, push or release tag.

The existing historical proof remains valid and separate. Canonical identities, exchange calendars/corporate actions and broad universe entitlement are not established by this four-listing LTPC acceptance.
