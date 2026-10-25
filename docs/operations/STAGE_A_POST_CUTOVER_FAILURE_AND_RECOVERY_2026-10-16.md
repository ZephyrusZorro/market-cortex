# Stage A OWNER_MAIN post-cutover verdict and bounded recovery

16 October 2026 — status: **BLOCKED: mandatory performance gate failed; application recovery pending owner-terminal execution.**

The approved cutover was executed. The accepted three-market frontend is running on 3000 and the preserved owner API on 8765. This is not a validated deployment. Original state receipt: `runtime/owner-candidate-cutover-3adbb515bb2e4ff78c279d49a34b7a3e.json`.

## Actual acceptance results

Passed: clean Edge production browser; nine genuine retained historical charts, 27 tooltips / 135 OHLCV values; Binance/NSE/BSE/Alpaca catalogs and pagination; symbol switching; pan/zoom persistence; unavailable uncached HDFCBANK/MSFT and minute timeframe; source timestamps and attribution; no browser errors or warnings; no browser writes or exchange WebSockets.

Navigation-to-chart median 1,040.8 ms (limit 1,500); first sample 1,653.1 ms, subsequent samples 714.1 and 1,040.8 ms. Symbol switch median 301.4 ms, maximum 409.0 ms (each limit 750). JS heap 14,762,444 bytes; idle task CPU 12.32 ms over five seconds. No prior benchmark has been overwritten.

Passed via actual owner API and port-3000 proxy: OWNER_MAIN health; original owner manifest; exact research payload and six replay hashes; five original pinned series of 365 bars each; all 65 owner Parquets match the verified owner restore. All 115 historical rows displayed in the browser match retained source observations. Source cache remains 17,095,626 bytes / 795 manifests / 700 artifacts, unchanged. GET admissions unchanged at history 14, metadata zero, stream authorization one. All prior owner refresh jobs are done. All three capture sockets are disconnected, no collector locks exist, and retained quote observations report STALE. Canonical owner history ends 10 October and is correctly STALE relative to the latest closed session; no refresh was authorized or performed.

**Failed: maximum warm API p95 limit 250 ms.** Alpaca catalog direct p95 267.6171 ms (median 246.4145); port-3000 proxy p95 264.9893 ms (median 244.1272), with ten samples per endpoint/base and nearest-rank p95. Other endpoint groups ranged 117.6–235.8 ms p95. A preceding run also exceeded the limit. The accepted candidate is frozen; no runtime optimization or limit change was deployed. No success verdict is issued.

During diagnostic development, three harness assumptions were corrected: internal policy diagnostics are intentionally not proxied (404 expected); Windows JSON inputs require explicit UTF-8 to preserve the rupee label; and prices use `connected` plus per-item `state`, without a top-level state. These were test-harness corrections, not owner data or application edits. Failed invocations remain in the session tool history. The final API receipt retains the measured performance failure.

The private pre-cutover report passed all 51 table fingerprints, 13 migrations and six research hashes. Current GET replay/data/file checks pass. A complete post-start table fingerprint inventory still requires the private terminal; the existing HTTP API does not expose every table. The recovery block below checks it before and after application recovery using the previously tested read-only guard. It never creates a database or writes records.

## Retained evidence

Under `C:\Users\faris\OneDrive\Documents\MARKET_CORTEX_Phase_1_Completed`:

- `runtime/owner-stage-a-cutover-verdict-355f7caffc3b4941a6c62fcd3a1f61e4.json`
- `runtime/owner-stage-a-browser-acceptance-2026-10-16.json` and nine matching PNGs.
- `runtime/owner-stage-a-api-acceptance-2026-10-16.json`
- `runtime/owner-stage-a-isolation-post-cutover-2026-10-16.json`
- `runtime/owner-cutover-preflight-75748c4b0de1448e88b8ef2758cf11ad.json`
- `runtime/owner-production-verification-68d22cb9251b4671816697b812066b2f.json`

Both retained encrypted owner/source bundles were rehashed successfully. The independently extracted original application recovery copy and receipt remain intact. No recovery, restoration over owner, database reset, migrations, imports, new research, scheduling, provider requests, Track B/B2 merge, release or push occurred.

## Execute the already-authorized bounded application recovery

Use the existing terminal containing the private owner connection. No additional approval is needed. This owner-terminal action is unavoidable because the agent has no owner connection and earlier automatic execution review rejected agent production startup. The agent has verified the exact recorded cutover process tree without stopping it. A failed private inventory stops this block before any process is stopped. The original installation remains available; only the application routing/processes are reversed.

```powershell
Set-Location 'C:\Users\faris\OneDrive\Documents\MARKET_CORTEX_Phase_1_Completed'
$ErrorActionPreference = 'Stop'
if (-not $env:MARKET_CORTEX_DATABASE_URL) { throw 'PRIVATE_OWNER_CONNECTION_REQUIRED; nothing stopped' }
$taskCutoverState = '.\runtime\owner-candidate-cutover-3adbb515bb2e4ff78c279d49a34b7a3e.json'
& .\.venv\Scripts\python.exe -m runtime.verify_owner_post_cutover --state $taskCutoverState
if ($LASTEXITCODE -ne 0) { throw 'OWNER_INTEGRITY_FAILED; preserve report and stop before recovery' }
& .\scripts\Stop-OwnerWorkstationCandidate.ps1 -StateFile $taskCutoverState -VerifyOnly
& .\scripts\Stop-OwnerWorkstationCandidate.ps1 -StateFile $taskCutoverState
if (Get-NetTCPConnection -State Listen -LocalPort 8765,3000 -ErrorAction SilentlyContinue) {
    throw 'OWNER_PORTS_NOT_FREE; preserve state and stop'
}
Remove-Item Env:MARKET_CORTEX_MARKET_DATA_API_URL -ErrorAction SilentlyContinue
& .\scripts\Start-MarketCortex.ps1 -Profile .\config\operations-owner.example.json -ApiPort 8765 -FrontendPort 3000
& .\.venv\Scripts\python.exe -m scripts.verify_owner_production
if ($LASTEXITCODE -ne 0) { throw 'ORIGINAL_OWNER_ACCEPTANCE_FAILED; preserve report and stop' }
& .\.venv\Scripts\python.exe -m runtime.verify_owner_post_cutover --state $taskCutoverState
if ($LASTEXITCODE -ne 0) { throw 'OWNER_POST_RECOVERY_INTEGRITY_FAILED; preserve report and stop' }
```

Return the new original-application state path printed by `Start-MarketCortex.ps1` and the final `owner-post-cutover-integrity-….json` path, or confirm the block completed. The agent will inspect the files directly, check the recovered owner frontend/API, reopen the existing research run and replay its six hashes. Do not manually debug or rerun a failed block. Keep candidate 3019/8678 and all other environments intact.

The final status can become RECOVERED only after actual recovery evidence passes. No new three-market cutover is authorized by this recovery; any future candidate modification and deployment needs its own reviewed acceptance.
