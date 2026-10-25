# Multi-market independent foundation — 2026-10-11

**Dated implementation baseline.** See `AUTONOMOUS_MARKET_VALIDATION_2026-10-14.md` for the fresh catalog counts, actual BTC/ETH browser acceptance, finalization correction, performance evidence and remaining production startup gate. Runtime readiness/port statements below describe the October 11 inspection, not the current post-reboot environment.

## Status

**Independent foundation implemented and publicly validated; full three-provider acceptance remains open.**

The protected release remains `v1.0.1-operational`, peeled commit `cfe696d51b137566c15eebaf734ff7ee0ca95197`. Changes are local and unreleased. No push, tag change, owner import, migration, application restart or task registration was performed.

## Implemented

- Full provider-native catalog normalization: Binance spot; Upstox NSE/BSE cash and suspended variants; Alpaca active/inactive supported US assets. Immutable Parquet snapshots, source hashes, lifecycle diffs, search columns, DuckDB filtering/pagination and pinned snapshots. Missing entries are not falsely called delisted. Discovery downloads no candles.
- Bounded cache-first history for eight implemented intervals. Source timestamps/timezones/feeds/adjustments are retained; empty/unavailable results remain explicit. Closed bars only, call/page/row budgets, deduplication, corrections and as-of reads. REST request coverage cannot hide an in-progress last candle.
- A strict in-memory bridge to existing canonical Bar/identity/calendar contracts. It preserves existing daily native record keys, requires verified mapping/knowledge/currency/session coverage, and performs no database writes.
- Shared bounded provider feeds: Binance public mini-ticker/kline, Upstox V3 LTPC/full using the pinned official Protobuf schema, Alpaca IEX with separate delayed-SIP selection. Authentication/subscription diagnostics, ping/pong, reconnect/backoff, out-of-order handling, logical deduplication, immutable evidence/checkpoints and explicit tick gaps. Consumer references share one provider union.
- Browser-independent bounded collector and optional continuous independent-test mode, event budget and recovery planner. No persistent owner collector is enabled. Windows catalog-sync action/profile is prepared, not registered.
- Independent loopback FastAPI catalog/history/prices service; GETs do not fetch history. A separate bounded source-cache POST performs provider GETs only. Owner/pilot lake roots and ports are refused.
- `/markets` workstation route, dedicated disabled-by-default proxy, authentic candlesticks/volume, pan/zoom, timeframes, separate live-price and forming-candle displays, provenance and LIVE/DELAYED/HISTORICAL/STALE/UNAVAILABLE states. No synthetic fallback series. Running workstation builds were not changed.
- Current-user Windows DPAPI credential files, exclusive creation/restricted ACLs, hidden prompts and temporary environment loading. Independent read-only probes before any owner import; daily OHLCV is compared against a fresh raw provider GET independently of the history normalizer. Failed accuracy or optional delayed-feed authentication cannot pass acceptance.

## Genuine public evidence

Archive: `runtime/multi-market-foundation-0c306424e0eb40148568db23fade99bc`.

| Check | Actual result |
|---|---|
| Binance discovery | 3,684 spot identities: 1,375 TRADING, 2,309 BREAK |
| Upstox discovery | 36,219 cash identities: 22,881 LISTED, 13,338 SUSPENDED; NSE 16,667 / BSE 19,552 |
| Outside-five search | ADAUSDT, DOTUSDT, RELIANCE and INFY found; RELIANCE full-text matches include multiple native securities/series, not all the single Reliance equity |
| Daily history | ADAUSDT and DOTUSDT: 30 closed daily rows each; all OHLCV values matched a fresh independent provider response |
| Cache and time travel | Repeat fixed history used zero provider requests; before-observation as-of returned no bars; after-observation returned all 30 |
| Minute history | Real ADAUSDT minute bars observed and persisted; incomplete minute excluded |
| Streaming | Actual ADAUSDT market updates received over bounded public WebSocket captures; latest refinement received 7 events in 15 seconds |
| Restart recovery | New worker resumed checkpoint, recorded tick gap and fetched provider-available missing/interrupted bars; dedup retained prior evidence |
| API reads | Actual public archive exercised through FastAPI TestClient; discovery/history returned real records; stopped collector returned STALE |
| Resource measurement | Full validation harness peak working set 630,841,344 bytes (about 602 MiB), including complete snapshot/integrity inspection; measured indexed searches about 31–80 ms |
| Current archive integrity | 38 manifests, 31 unique artifacts, 6,656,389 bytes at final storage measurement; validated |

Discovery totals do not mean free live coverage, verified canonical classifications, full historical delisting knowledge or complete corporate-action lineage.

Receipts:

- `runtime/multi-market-foundation-validation-final-0c306424e0eb40148568db23fade99bc.json`
- `runtime/multi-market-final-stream-refinement.json`
- `runtime/multi-market-api-validation.json`
- `runtime/multi-market-storage-measurement-final.json`

The initial resource receipt reported unavailable zero counters due to an incorrect Windows HANDLE signature; the corrected final receipt contains actual nonzero measurements. Earlier discovery/Windows-checkpoint failures and partial evidence were preserved, and their causes received regression coverage.

## Regression evidence

- Full isolated PostgreSQL suite: **382 passed, 34 skipped, 13 subtests passed**, one existing Starlette/httpx deprecation warning; `runtime/multi-market-full-regression-isolated.log`.
- Final focused foundation/security/provider suite after follow-up fixes: **70 passed, 13 subtests passed**, same warning; `runtime/multi-market-focused-final.log`. These overlap the full suite and must not be added together.
- Subsequent credential-probe accuracy/entitlement refinement: **22 passed**, same warning; `runtime/multi-market-probe-regression.log`, including nine new acceptance guards. These are synthetic broker responses, not account validation. The earlier full suite preceded this small probe-only refinement.
- Frontend: **60 passed**; TypeScript passed; copied-workstation Webpack production build passed. Original owner `.next` remains untouched.
- Three new PowerShell scripts parse; synthetic current-user DPAPI encryption/decryption and restricted ACL check passed. This is not proof of real provider credentials.
- `git diff --check` passed.

The first full run against the populated pilot database encountered the intentional uninspected-schema backup guard. A new disposable UTF8 regression database on port 55432 resolved test isolation without changing either operational database. The 34 skips are separately configured stored-data pilot/restore-target gates. They are not authenticated provider or owner-data validation results.

## Protected owner state

Owner and pilot APIs still return ready. Retained current-state backup SHA256 remains `1cb01c848c4fc7ac94d28e533ff506596df917e31518192bdcc5c5ed9c93641a`; the protection receipt hash is unchanged. Owner run `f329f8c9-1274-4be5-8f8d-0e695cdd7e7c` remains readable with evidence hash `f6c96904277c739b8c6cf2977c6fe23c08672c30c0cd23d5033d182f1ae6c2e7`.

Receipt: `runtime/multi-market-release-protection-read-only.json`. No new owner table inventory was claimed: the private owner connection remains confined to the owner's terminal. The independent data path opens no database connection; PostgreSQL regressions used disposable databases/schemas.

## Remaining acceptance gates

1. **Upstox/Alpaca — DEFERRED_NOT_CONFIGURED.** Public Upstox metadata is genuine. Authenticated broker history/live access has not been observed. Alpaca discovery is implemented/tested but not account validated. See `MULTI_MARKET_SECURE_ONBOARDING.md` for exact credential entry/probe commands.
2. **Browser acceptance — EXECUTION_APPROVAL_BLOCKER.** Automatic execution review rejected starting the independent API on 8677 and copied development UI on 3017. No retry/bypass occurred. See `MULTI_MARKET_INDEPENDENT_LAUNCH.md` for the owner-terminal blocks. Successful compilation and API TestClient checks do not replace browser acceptance.
3. **Canonical India/US mapping/calendar and import proposal — pending actual probes.** See `MULTI_MARKET_OWNER_IMPORT_GATES.md`. No extra owner writes are authorized.
4. **Persistent collection/catalog schedule — PROPOSED_DISABLED.** The candidate profile is `config/market-data-collection.proposed.json`; no MARKET CORTEX scheduled task is registered. Current background collection remains off.

The existing owner release retains its Binance daily OWNER_READY baseline. This new work is not a three-market production release and makes no claim of all-market real-time coverage.
