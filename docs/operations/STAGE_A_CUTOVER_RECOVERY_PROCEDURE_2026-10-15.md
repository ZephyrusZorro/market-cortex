# Stage A cutover and application recovery procedure

**PREPARED — NOT AUTHORIZED — NOT EXECUTED.** Conditional Stage A authorization permits candidate preparation only. Mandatory fresh Indian-session and supplemental US browser gates remain open. No all-gates-passed acceptance receipt exists; the guarded launcher rejects an incomplete receipt. Request final human cutover approval only after those gates and a new post-capture source recovery drill pass.

## Preserved installations and boundaries

- Original operational installation: `C:\Users\faris\OneDrive\Documents\MARKET_CORTEX_Phase_1_Completed`; tag/HEAD `cfe696d51b137566c15eebaf734ff7ee0ca95197`.
- Accepted candidate: `C:\MarketCortexCandidates\stage-a-e492731ff5f94ae4942d4e06a52cd765`; build `QwXzCmanOChHrnjc4MLxn`.
- Source sidecar: cache-only API 8678 and separate source root. No broker credentials, provider fetching, collectors or schedules in this runtime.
- Future approved owner layout: original owner API/profile on 8765, candidate frontend on 3000. Canonical `/api/*` routes use 8765; only `/api/market-data/*` routes use 8678. Candidate-only environment banner and source-origin purpose remain explicit.
- Existing independent 3018/8677 and candidate 3019/8678 remain isolated. No changes to PILOT_TEST.

## Required before asking for cutover approval

1. Completed nine-chart production browser, source OHLCV comparisons, explicit unavailable states, no browser errors or write requests.
2. Fresh official Indian session states and fresh events for both RELIANCE/INFY NSE/BSE listings; exact live browser values. Supplemental 90-second IEX exact AAPL/SPY/QQQ live browser observations. All sockets explicitly stopped; no running subscription claimed afterward.
3. Provider GET ledger within 42 history/comparison + 21 metadata + 18 stream authorization, 81 total. Supplemental IEX adds zero REST requests. Seven-listing history remains 59 observations / 42 newly appended source rows; any change requires reviewed explanation.
4. Source cache below 512 MiB and another retained encrypted backup of the final source state, successfully restored into a new isolated directory with byte/hash/manifest/lineage equality.
5. Retained current owner backup and actual isolated restore inventory, 13 checksum-verified migrations, five pinned Binance series, 65 owner Parquets and six saved research hashes. Fresh owner read-only inventory must still match before any process starts.
6. Verified frozen candidate backend/frontend/build hashes and unchanged operational tag. Candidate real stop/restart and nine-chart/performance recovery already passed.
7. Final combined receipt binds these artifacts with hashes and has status `STAGE_A_ALL_PRE_CUTOVER_GATES_PASSED`. Produce the report, limitations and precise process plan, then obtain separate human cutover approval.

## Future owner-terminal command — only after final approval

The following command is a reviewable template, **not an instruction to run now**. The private owner connection must already exist in the configured terminal. `FINAL_ACCEPTANCE_RECEIPT` is deliberately unresolved until all gates pass. Do not substitute a progress receipt or change its status.

```powershell
Set-Location 'C:\Users\faris\OneDrive\Documents\MARKET_CORTEX_Phase_1_Completed'
$ErrorActionPreference = 'Stop'
# Only after separate final human cutover approval and an actual passed receipt:
& .\scripts\Start-OwnerWorkstationCandidate.ps1 `
  -BuildReceipt '.\runtime\stage-a-e492731ff5f94ae4942d4e06a52cd765-build-acceptance.json' `
  -AcceptanceReceipt 'FINAL_ACCEPTANCE_RECEIPT' `
  -FinalCutoverApproved
```

This launcher rejects occupied 3000/8765; it never replaces processes automatically. If the original owner application is running at approval time, prepare its exact verified state-file stop command and record free ports first. Never kill processes merely by port. The launcher checks all required receipt gates and candidate frontend hashes, source policy/root, owner identity (5432 / market_cortex), read-only integrity/preflight and the existing full owner production verifier. It starts no migrations, ingestion, research submissions or jobs. It passes the private connection only to the preserved owner API, removes it before starting Node, clears broker/pilot/PYTHONPATH values and restores the caller environment. Logs and a new `runtime\owner-candidate-cutover-….json` process state are retained.

## Post-cutover acceptance — future authorized stage

The launcher reports pending post-cutover acceptance, not OWNER_READY. Independently inspect process identity/readiness and production logs, then perform only GETs:

- `/markets`: same nine charts, histories, source attribution, unavailable and stale states, performance gates (page-to-chart median <= 1,500 ms; each switch <= 750 ms; warm HTTP p95 <= 250 ms; search <= 1,000 ms).
- Original owner read API: owner identity, instrument/catalog counts and same pinned evidence; reopen/replay research `f329f8c9-1274-4be5-8f8d-0e695cdd7e7c` with all six hashes matching. No new research question or personal record.
- Repeat the read-only production verifier and compare all counts, complete migration rows/checksums, schema and storage. Routing checks must show owner reads on 8765 and separate source reads on 8678.
- Verify no collector locks/running subscriptions or scheduled jobs were created. Preserve existing backup and isolated-restoration receipts.

## Application recovery — future authorized stage

Candidate-only application recovery is **actually verified** by the owner-executed stop/start, post-restart browser/performance and unchanged seven-history hashes/request ledger. New split owner deployment/reversal remains **unexecuted**, and must be verified at the approved deployment acceptance stage.

On a startup/acceptance failure, retain the new state/logs and stop only its verified process tree. The state path below must be the exact printed new path, not an older owner or candidate state:

```powershell
# Only if cutover occurred and application recovery is authorized:
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

Then autonomously check original owner UI/API readiness and the same saved research replay. This reverses application routing only. Do not restore a database over owner, reset data, rerun migrations, reingest, remove source files or delete backups. If process identity or owner inventory differs, stop and report; do not improvise a rollback.

## Remaining limitations

Only nine native listings have passed this browser gate, despite 73,494 catalog records. Existing cache contains some history for 13 native instruments. No unrestricted on-demand fetch or always-on live service is approved. Stock daily timestamps describe native source windows; verified exchange-session/holiday calendars, corporate-action basis and canonical identity are later Stage B gates. Alpaca feed/volume is IEX only; Upstox adjustment basis is provider-unspecified. Current snapshot age is shown, never relabeled live.

Source recovery keys retained with DPAPI are bound to the current Windows user/profile and are not portable disaster-recovery keys. Keep that profile/key files secure; a portable passphrase-backed source bundle can be created through the existing hidden-prompt procedure without overwriting any bundle. Owner backup passphrase remains owner-retained outside the repository. The source bundle preserves data and code/configuration inventory, while the versioned candidate installation is separately retained.
