# Authorized Stage A OWNER_MAIN cutover — execution handoff

Authorization: 15 October 2026. Recovery-copy completion: 16 October 2026 (Asia/Kolkata).

## Authorization and current state

The owner explicitly authorized the Stage A application-only cutover and bounded application recovery if acceptance fails. This does not authorize provider requests, owner record writes, migrations, canonical imports, continuous collection, schedules, Track B/B2 deployment, releases or pushes.

**Current state: not deployed; waiting for private owner preflight and owner-terminal startup.** The owner connection is absent from the agent process and Windows user/machine environment. Previous automatic execution review rejected agent production startup; it has not been retried or bypassed.

Candidate ports 3019/8678 remain running. Owner ports 3000/8765 and pilot ports 3002/8001 were not listening during preparation. No existing process needs to be stopped in that inspected state; the launcher refuses occupied owner ports if this changes.

## Completed independent preparation

- All 16 hash-bound final acceptance receipts verified unchanged.
- Latest retained encrypted owner/source backups and isolated restorations revalidated in `runtime/stage-a-authorized-precutover-recovery-2026-10-15.json`.
- Actual isolated owner restore: 51 tables, 13 verified migrations, 1,825 bars, 65 Parquets, five pinned series and all six research evidence hashes match. This is isolated restoration evidence, not a substitute for the pending live owner preflight.
- Added `scripts/verify_owner_cutover_preflight.py`, invoked by the cutover launcher before any process starts. All owner table row fingerprints/schema/history/head must exactly match the retained owner backup inventory. Six research hashes are recalculated; full inventory is compared again afterward.
- Every connection used by the new guard defaults to read-only, including catalog/replay connections. Diagnostics contain whitelisted data and error codes, never raw driver exceptions or connection strings.
- Application startup inspected: creates existing API/frontend processes; no migration, ingestion, job enqueue, research save or provider connection is invoked.
- Twelve hermetic guard/verifier tests passed; PowerShell launcher parser passed. The first test attempt encountered the existing shared pytest temporary-directory ACL issue; the rerun used a new isolated test directory and passed all tests. No owner database was used by these tests.
- Prepared GET-only browser acceptance harness in `runtime/accept_owner_stage_a_browser.py` for the approved 3000/8678 route pair. Import/help validated; actual post-cutover browser execution remains pending.

## Preserved application copy — VERIFIED

The archive and independent extraction passed: 24,678 files; 1,177,757,140 archive bytes. Original and extracted file hashes match the receipt inventory.

Receipt: `runtime/owner-application-recovery-owner-pre-stage-a-b675601c6ac645d19a6f91c8de124a3b.json`.

Retained bundle and independent extraction directory:
`C:\MarketCortexApplicationRecovery\owner-pre-stage-a-b675601c6ac645d19a6f91c8de124a3b`

The copy includes source, configuration, launch/recovery scripts, original production frontend build, node_modules, Python virtual environment, package metadata and saved application process-state files. Database/data roots, source cache, credentials, logs and ephemeral caches are excluded. Original files remain in place. Installed base Python and Node are prerequisites, recorded in the receipt; the copied venv contains original absolute paths, so the extraction is a verified restoration copy, not a relocatable installation to launch directly.

The launcher requires this receipt, rechecks the retained bundle hash, and compares every listed original/extracted file before private acceptance. No restore-over-original operation is required for the normal application recovery procedure.

## Single required owner-terminal launch

Run in the already configured private owner terminal. Do not enter credentials into chat or another test environment. Keep the terminal open.

```powershell
Set-Location 'C:\Users\faris\OneDrive\Documents\MARKET_CORTEX_Phase_1_Completed'
$ErrorActionPreference = 'Stop'
& .\scripts\Start-OwnerWorkstationCandidate.ps1 `
  -BuildReceipt '.\runtime\stage-a-e492731ff5f94ae4942d4e06a52cd765-build-acceptance.json' `
  -AcceptanceReceipt '.\runtime\stage-a-final-acceptance-2026-10-15.json' `
  -ApplicationRecoveryReceipt '.\runtime\owner-application-recovery-owner-pre-stage-a-b675601c6ac645d19a6f91c8de124a3b.json' `
  -FinalCutoverApproved
```

Return the printed `owner-cutover-preflight-….json` and `owner-candidate-cutover-….json` paths. If it stops, preserve the report/state/logs and return their paths; do not rerun blindly or start either application manually. A failed mandatory pre-start gate prevents process startup.

## Autonomous post-cutover acceptance

After the state paths arrive, the agent will inspect actual process identity, logs, health and routing, then exercise the nine approved cached charts, search/switching, source labels, stale/unavailable states and performance. Browser traffic is constrained to local GETs. Check original owner health and the saved research run/replay via read routes. No research submission is permitted.

Expected URLs after successful startup:
- Owner workstation: http://127.0.0.1:3000/markets
- Original owner API health: http://127.0.0.1:8765/api/v1/health
- Cache-only source API: http://127.0.0.1:8678/api/v1/market-data/health

No success/OWNER_READY claim is made until actual post-cutover acceptance passes. A final full private owner inventory can be repeated through the same read-only guard without launching applications.

## Authorized bounded application recovery

On application acceptance failure, retain the exact cutover state/logs. Verify and stop only its recorded process tree using `Stop-OwnerWorkstationCandidate.ps1 -VerifyOnly`, followed by the same command without `-VerifyOnly`. Confirm owner ports free, clear only the sidecar-routing environment override, and launch the preserved original owner application through `Start-MarketCortex.ps1` using the original owner profile on 8765/3000. Run the original read-only owner verifier and reopen/replay the existing saved research ID.

The exact commands are retained in `docs/operations/STAGE_A_FINAL_ACCEPTANCE_AND_CUTOVER_PROPOSAL_2026-10-15.md`. Substitute only the newly printed cutover state file. Never use a PID/port-only kill, restore a database over owner, delete artifacts, rerun migrations or reingest. Stop and report process identity changes, occupied ports, unexpected inventory or recovery failures. Private credentials/startup execution policy may require the owner terminal for the approved recovery command.

## Limitations

The accepted workstation displays the separate cached native-provider universe; this authorization enables no ongoing live service or automatic fetching. Post-capture quotes are stale. IEX is not consolidated SIP; Upstox evidence is LTPC. Canonical mapping/calendar/corporate-action work remains Stage B. Track B/B2 remains isolated. Source-cache DPAPI recovery is tied to the Windows user/profile.
