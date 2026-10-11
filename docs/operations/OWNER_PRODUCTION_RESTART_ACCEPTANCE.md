# Final owner inventory and application restart — 2026-10-11

The single owner research record was explicitly approved, saved once and replayed successfully before restart: `f329f8c9-1274-4be5-8f8d-0e695cdd7e7c`, evidence hash `f6c96904277c739b8c6cf2977c6fe23c08672c30c0cd23d5033d182f1ae6c2e7`. All six tool evidence hashes matched. Do not submit the question again.

Run the following once in the existing private Terminal 1. No new credential or backup key is requested. The inventory uses read-only owner queries, preserves the complete UTC migration-row check including applied_at, and requires the schema/head/storage and all table counts to match the validated baseline except the one approved research row. It also checks the exact saved payload and retained backup SHA.

**Invocation correction:** use `python -m scripts.verify_owner_production` from the repository root. Direct file execution adds `scripts` to the front of the import path, where `scripts/market_cortex.py` shadows the package. The old invocation now fails before imports/configuration with a clear module-command instruction. Three focused tests cover package resolution, read-only query ordering and exact approved count enforcement.

The owner stopped immediately at the import failure; no owner application stop/restart occurred. The corrected module invocation subsequently passed in the private owner terminal. Its inspected receipt is `runtime/owner-production-verification-1f9cecacc5ba4d48b0d4ad4b4adaf133.json`: unchanged full migration rows/schema/head/storage and exactly the approved one research row, payload hash matching. The inventory gate is satisfied. Proceed with the existing Stop/Start block below, then repeat the read-only module inventory and return both new paths. Do not submit research again.

```powershell
Set-Location 'C:\Users\faris\OneDrive\Documents\MARKET_CORTEX_Phase_1_Completed'
$ErrorActionPreference = 'Stop'
& .\.venv\Scripts\python.exe -m scripts.verify_owner_production
if ($LASTEXITCODE -ne 0) { throw 'OWNER_READ_ONLY_ACCEPTANCE_FAILED; preserve the printed report and stop' }
$taskStateFile = 'C:\Users\faris\OneDrive\Documents\MARKET_CORTEX_Phase_1_Completed\runtime\application-6898cdce55e34ef1ac077e05bdd55b35.json'
& .\scripts\Stop-MarketCortex.ps1 -StateFile $taskStateFile
if (Get-NetTCPConnection -State Listen -LocalPort 8765,3000 -ErrorAction SilentlyContinue) {
    throw 'OWNER_APPLICATION_PORTS_NOT_FREE; stop and report'
}
[pscustomobject]@{
    observed_at = (Get-Date).ToUniversalTime().ToString('o')
    stopped_state_file = $taskStateFile
    application_ports_free = $true
} | ConvertTo-Json | Set-Content -LiteralPath runtime/owner-production-stop.json -Encoding utf8
& .\scripts\Start-MarketCortex.ps1 -Profile .\config\operations-owner.example.json -ApiPort 8765 -FrontendPort 3000
& .\.venv\Scripts\python.exe -m scripts.verify_owner_production
if ($LASTEXITCODE -ne 0) { throw 'OWNER_POST_RESTART_INVENTORY_FAILED; preserve the printed report and stop' }
```

Preserve Terminal 2's pilot on 8001/3002. This stops only the processes owned by the exact owner state file and verifies both owner ports become free before restarting production. It performs no database reset, migration, ingestion, job enqueue, backup restore or additional research write. The existing Stop script validates process creation times and command markers. PostgreSQL remains running.

Return the printed `runtime/owner-production-verification-<UUID>.json` report path and new `runtime/application-<UUID>.json` state-file path. Keep the restarted owner application running. The agent will inspect the actual inventory, reconnect through read-only API/browser actions, reopen and replay the same saved ID, compare its context/payload/evidence hashes and verify both owner/pilot environments remain isolated.

If verification or shutdown fails, stop and preserve the report/partial state. Do not retry the initial onboarding, modify migration rows, delete Parquets or attempt rollback. The private connection is confined to Terminal 1; the earlier agent production launch was rejected by automatic execution review, so this procedure is owner-executed. OWNER_READY and the operational tag remain pending actual restart acceptance.
