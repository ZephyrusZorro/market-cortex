# Stage A final acceptance and OWNER_MAIN cutover proposal — 15 October 2026

**Status: STAGE_A_ALL_PRE_CUTOVER_GATES_PASSED. Cutover NOT approved or executed.**

## Final IEX result

The previously authorized supplemental allowance has now been consumed. Do not run it again.

- AAPL / NASDAQ, SPY / ARCA, QQQ / NASDAQ only; Alpaca IEX feed.
- One WebSocket connection, zero reconnects, configured 90-second capture; 14,047 accepted events, 137 duplicates rejected, zero out-of-order events and no feed errors.
- Observed event arrival span: 88.061682 seconds. Socket teardown and subsequent integrity processing occur after acquisition; the whole command is not a 90-second wall-clock operation.
- Authentication and subscription were confirmed. Exchange activity was established by advancing, changing, fresh observations, beyond calendar/socket admission.
- Official admission reference: https://www.iex.io/resources/trading/trading-hours-holidays — regular equity session 09:30–16:00 ET; 15 October is not a listed 2026 holiday. Capture was during the 12:15–12:17 EDT period.
- No historical, metadata or other provider REST GETs added.

| Listing | Fresh quote/trade events | Trades | Exact fresh browser/source matches | Median arrival age |
|---|---:|---:|---:|---:|
| AAPL | 3,146 | 41 | 2 | 256 ms |
| SPY | 5,449 | 52 | 6 | 189 ms |
| QQQ | 5,446 | 16 | 3 | 169 ms |

Six additional minute-bar events complete the 14,047 total. Bar-window timestamps are excluded from quote/trade arrival-age calculations. Arrival age includes clock differences; it is not pure network latency.

All 11 browser observations matched retained normalized source rows exactly: native identity, price/bid/ask, event/arrival timestamps, feed and payload hash. IEX exchange code V was verified for every trade and both quote sides. All provider timestamps matched parsed event timestamps; original nanosecond timestamp strings remain retained alongside microsecond parsed values. Raw WebSocket payload bodies are not retained; SHA256 lineage and normalized observations are retained.

Browser timestamps advanced for all three listings. Across 142 capture checkpoints, latest timestamps never regressed. The earlier Upstox acceptance also exercised 14 out-of-order observations without regressing latest snapshots. Clean-browser diagnostics recorded no uncaught errors, write requests or browser exchange sockets.

Delivery is **exchange WebSocket → bounded backend capture → immutable cache/checkpoints → browser local HTTP polling**. All collector checkpoints are disconnected, collector locks absent, capture process exited. Active subscriptions: **zero**. A separate post-stop browser check verified STALE for all three instruments. No ongoing live service is claimed.

## Recovery and isolation

New retained encrypted source bundle:
`C:\MarketCortexBackups\source-current-7eba69bb83074accae3c04d4ce261f2e.mcsourcebackup`

SHA256: `0a6f87e4be2c0205894bbbbaf22bd64897965c8542f3252fd51f01e2c6630053`

- Source: 17,095,626 bytes (16.304 MiB), 2,300 files, 795 manifests, 700 unique Parquet artifacts.
- Supplemental growth: 2,345,337 bytes (2.237 MiB), below the 64 MiB supplemental reservation and 512 MiB total cap.
- Encrypted bundle: 20,623,413 bytes. Authenticated restoration to a new isolated directory passed full inventory/hash/lineage equality.
- Current-user DPAPI recovery key retained separately; its path and cipher hash are in the protection key receipt. It is tied to this Windows user/profile, not portable disaster recovery. No secret was printed.
- Previous source and owner encrypted backups remain retained and verified by the recovery checks.
- Actual isolated owner restore rechecked read-only: 51 tables, 13 verified migrations, 1,825 bars, 65 Parquets, one saved research record, five pinned series and all six research replay hashes match.
- Current owner Parquet files compared directly against the verified restore: all 65 unchanged. No connection was made to the owner database; a fresh private owner database inventory is enforced before future cutover.
- Frozen candidate verified: 103 backend and 138 frontend/build hashes unchanged; original frontend build and operational Git commit/tag unchanged.
- Candidate processes remain on 3019/8678. Owner/pilot ports were offline at final inspection and were not started. No owner/pilot writes, migrations, imports, schedules, Stage B/C execution, Track B/B2 merge, release or push occurred.

## Reconciled acceptance

Previously completed historical/browser/performance/restart tests were preserved and hash-verified, not needlessly repeated.

- Binance BTC/ETH genuine history and bounded fresh observations passed.
- All four Upstox RELIANCE/INFY NSE/BSE listings passed the fresh Indian-session gate earlier today: 444 fresh observations and 13 exact browser/source matches.
- Nine historical charts passed; 27 tooltips / 135 OHLCV values matched. Uncached and unsupported timeframe states were correctly unavailable.
- Seven approved broker-history operations retained 59 compared daily observations, including 42 new source rows. No canonical owner import.
- GET usage remains 14 history/comparison, zero metadata, one Upstox stream authorization: **15 of 81 category-bounded admissions**, unchanged by this supplemental run. Unused allowance is not authority to extend scope.
- Searchable catalogs: Binance 3,689; Upstox 36,255 (NSE 16,669 / BSE 19,586); Alpaca 33,550. Catalogs include inactive/suspended/non-equity records; discovery does not prove entitlement or chart coverage. History exists for 13 native instruments; nine were browser-tested.
- Retained 14 October production measurements: chart navigation median 397 ms; symbol switch median 221 ms; maximum warm API p95 146 ms; search medians 345–387 ms. These meet the established gates; they are not new measurements from today's capture.
- The only capture-tooling change today restricts retries from five to zero and records one maximum connection. All nine hermetic supplemental admission/connection-limit tests passed. The frozen candidate was not changed.
- Earlier failed browser-selector receipts remain retained; the corrected supplemental browser gate now passes all three exact listings.

## Evidence paths

All relative paths below are under `C:\Users\faris\OneDrive\Documents\MARKET_CORTEX_Phase_1_Completed`.

- Final hash-bound acceptance: `runtime\stage-a-final-acceptance-2026-10-15.json`
- Reproducible read-only reconciliation: `runtime\reconcile_stage_a_final_2026_10_15.py` (exclusive output: do not rerun against an existing final receipt).
- IEX capture: `runtime\stage-a-alpaca-ui-90-c4c3691592ac4dae98d478699375c815.json`
- Fresh browser: `runtime\stage-a-iex-supplement-browser-2026-10-15-final.json`
- Source/browser audit: `runtime\stage-a-iex-final-source-browser-audit-2026-10-15.json`
- Post-stop stale browser: `runtime\stage-a-iex-supplement-stopped-browser-2026-10-15-final.json`
- Source protection: `runtime\stage-a-source-protection-7eba69bb83074accae3c04d4ce261f2e.json`
- DPAPI key receipt: same protection path plus `.key-receipt.json`.
- Final both-recovery audit: `runtime\stage-a-final-recovery-audit-2026-10-15.json`
- Upstox gate: `runtime\stage-a-upstox-live-acceptance-255a8b73d76b4441a72ed0eb0420e05f.json`

## Exact proposed cutover — requires separate explicit approval

Approve only the accepted candidate frontend on OWNER_MAIN port 3000, the preserved original owner API/profile on 8765, and the existing cache-only sidecar on 8678. The separate candidate UI on 3019 remains available. No ingestion, provider fetch, feed collection, canonical imports, migrations or scheduled jobs are included.

**Do not run this block until final cutover approval is given.** The private owner connection must already be available in the owner terminal. If owner ports become occupied, stop and verify the exact existing application's state before any approved process stop; never kill processes by port.

```powershell
Set-Location 'C:\Users\faris\OneDrive\Documents\MARKET_CORTEX_Phase_1_Completed'
$ErrorActionPreference = 'Stop'
& .\scripts\Start-OwnerWorkstationCandidate.ps1 `
  -BuildReceipt '.\runtime\stage-a-e492731ff5f94ae4942d4e06a52cd765-build-acceptance.json' `
  -AcceptanceReceipt '.\runtime\stage-a-final-acceptance-2026-10-15.json' `
  -FinalCutoverApproved
```

The launcher performs read-only owner identity, full inventory, migration/schema/storage and saved research verification before startup. It checks the final acceptance receipt, candidate hashes, cache-only policy and free ports. Broker credentials are removed; the owner connection is supplied only to the original backend, not the frontend. The printed state file identifies only the newly launched processes.

After approved startup, validate actual OWNER_MAIN routing, nine charts, unavailable/stale states, performance, original owner reads and the same six research replay hashes. Only then can three-market owner workstation readiness be declared. No new research submission is included.

## Application recovery procedure

Candidate-only stop/restart recovery has already passed actual browser/data/performance acceptance. The new split OWNER_MAIN cutover and reversal have **not** yet been executed; do not describe them as already tested in production.

If approved cutover acceptance fails: preserve logs/state; verify and stop only the exact new cutover process tree; confirm ports free; start the preserved original owner application; run its read-only verifier and saved research replay. No database rollback, database restore-over-owner, deletion or reingestion.

```powershell
# Only after approved cutover and with its exact printed new state-file path:
& .\scripts\Stop-OwnerWorkstationCandidate.ps1 -StateFile 'EXACT_NEW_CUTOVER_STATE_FILE' -VerifyOnly
& .\scripts\Stop-OwnerWorkstationCandidate.ps1 -StateFile 'EXACT_NEW_CUTOVER_STATE_FILE'
if (Get-NetTCPConnection -State Listen -LocalPort 8765,3000 -ErrorAction SilentlyContinue) {
    throw 'OWNER_PORTS_NOT_FREE; preserve state and stop'
}
Remove-Item Env:MARKET_CORTEX_MARKET_DATA_API_URL -ErrorAction SilentlyContinue
& .\scripts\Start-MarketCortex.ps1 -Profile .\config\operations-owner.example.json -ApiPort 8765 -FrontendPort 3000
& .\.venv\Scripts\python.exe -m scripts.verify_owner_production
if ($LASTEXITCODE -ne 0) { throw 'RESTORED_APPLICATION_READ_ONLY_ACCEPTANCE_FAILED' }
```

## Remaining limitations and approval boundary

No failed mandatory pre-cutover Stage A gate remains. Final human cutover approval, private owner pre-start inventory and actual post-cutover validation remain required.

This approval proposal provides cached native-provider observations, not continuous three-market streaming or unrestricted on-demand downloads. Alpaca is IEX-only, not SIP. Upstox supplies LTPC snapshots here. Canonical calendars/mappings/corporate-action adjustment gates remain deferred to separately authorized Stage B. Source recovery DPAPI portability remains limited. Stage C collection, scheduling, hardening branch merges and releases remain unauthorized.
