# Production launch validation using PILOT_TEST — 2026-10-11

The owner requests production validation through an authorized Windows terminal because Codex's process-creation review rejected production startup. This procedure uses the **existing** scripts and argument names inspected in the canonical repository. The agent has not retried the rejected operation or launched an alternative production process. Database migrations are already complete and are not part of these commands.

## Owner terminal: prerequisites and launch

Use PowerShell in Terminal 2. Keep that terminal available for shutdown/restart. The selected profile reads **MARKET_CORTEX_PILOT_DATABASE_URL**, not MARKET_CORTEX_DATABASE_URL. Its existing isolated database is **market_cortex_pilot_test**, role **cortex_test**, at **127.0.0.1:55432**. The cluster is already running; these commands do not start/recreate it or migrate either database. Preserve Terminal 1's private owner connection.

The existing pilot cluster uses loopback **trust** authentication. No pilot password is currently required or validated. The requested hidden prompt accepts Enter if no separate pilot password exists; never enter the owner password. These commands do not change PostgreSQL authentication.

```powershell
Set-Location 'C:\Users\faris\OneDrive\Documents\MARKET_CORTEX_Phase_1_Completed'
$ErrorActionPreference = 'Stop'
$env:PATH = 'C:\Program Files\PostgreSQL\17\bin;' + $env:PATH
if (-not (Test-NetConnection -ComputerName 127.0.0.1 -Port 55432 -InformationLevel Quiet -WarningAction SilentlyContinue)) {
    throw 'EXISTING_PILOT_CLUSTER_UNREACHABLE; stop and report'
}
$taskSecret = Read-Host 'Pilot cortex_test password (Enter if not set; never use owner password)' -AsSecureString
try {
    $taskPlain = [System.Net.NetworkCredential]::new('', $taskSecret).Password
    $taskEscaped = $taskPlain.Replace('\', '\\').Replace("'", "\'")
    $env:MARKET_CORTEX_PILOT_DATABASE_URL = "host=127.0.0.1 port=55432 dbname=market_cortex_pilot_test user=cortex_test password='$taskEscaped' connect_timeout=10"
} finally {
    $taskPlain = $null
    $taskEscaped = $null
    $taskSecret.Dispose()
}
if (-not (Test-Path -LiteralPath .\.venv\Scripts\python.exe)) { throw 'PYTHON_VENV_MISSING' }
if (-not (Get-Command node -ErrorAction SilentlyContinue)) { throw 'NODE_MISSING' }
if (-not (Test-Path -LiteralPath .\apps\workstation\.next\BUILD_ID)) { throw 'PRODUCTION_BUILD_REQUIRED' }
$taskCheck = & .\.venv\Scripts\python.exe -m market_cortex.operations preflight --profile config/operations-pilot.example.json --integrity
if ($LASTEXITCODE -ne 0) { throw 'PILOT_PREFLIGHT_FAILED' }
$taskReport = ($taskCheck -join "`n") | ConvertFrom-Json
if ($taskReport.status -ne 'VALIDATED' -or $taskReport.settings.environment -ne 'PILOT_TEST' -or
    $taskReport.checks.database_identity.database -ne 'market_cortex_pilot_test' -or
    $taskReport.checks.database_identity.database -eq 'market_cortex' -or
    $taskReport.checks.database_identity.server_port -ne 55432 -or
    $taskReport.checks.database_identity.transaction_read_only -ne 'on') { throw 'WRONG_OR_UNVALIDATED_PILOT_DATABASE' }
$taskCheck | Set-Content -LiteralPath runtime/production-pilot-preflight.json -Encoding utf8
Write-Output 'Verified PILOT_TEST: market_cortex_pilot_test on port 55432; read-only preflight passed.'
$taskBefore = @(Get-ChildItem -LiteralPath runtime -Filter 'application-*.json' | Select-Object -ExpandProperty FullName)
& .\scripts\Start-MarketCortex.ps1 -Profile .\config\operations-pilot.example.json -ApiPort 8001 -FrontendPort 3002 | Tee-Object -FilePath runtime/production-pilot-start.log
$taskNew = @(Get-ChildItem -LiteralPath runtime -Filter 'application-*.json' | Where-Object { $_.FullName -notin $taskBefore })
if ($taskNew.Count -ne 1) { throw 'EXPECTED_ONE_NEW_APPLICATION_STATE' }
$taskStateFile = $taskNew[0].FullName
$taskStateFile | Set-Content -LiteralPath runtime/production-pilot-state-path.txt -Encoding utf8
Write-Output "Production state file: $taskStateFile"
```

**Do not add `-Development`.** The existing script verifies free ports, selected-profile preflight, the production BUILD_ID, API environment/readiness and frontend HTTP status. It launches only loopback app processes, keeps stdout/stderr under runtime, and prints an exact shutdown command. It does not migrate, bootstrap, schedule, seed owner records or start/stop owner PostgreSQL services.

If startup is rejected or exits, preserve its safe runtime logs and report the failure. Do not disable security controls or substitute another execution mechanism to evade a rejection. A build or partial process-state file is not a production runtime pass.

## Owner terminal: health and production-mode evidence

After startup succeeds, run in that same terminal:

```powershell
$taskApi = Invoke-RestMethod -Uri 'http://127.0.0.1:8001/api/v1/health' -TimeoutSec 10
$taskProxy = Invoke-RestMethod -Uri 'http://127.0.0.1:3002/api/v1/health' -TimeoutSec 10
$taskDiagnostics = Invoke-RestMethod -Uri 'http://127.0.0.1:3002/api/v1/operations/preflight' -TimeoutSec 10
$taskState = Get-Content -LiteralPath $taskStateFile -Raw | ConvertFrom-Json
if ($taskState.mode -ne 'production' -or $taskState.environment -ne 'PILOT_TEST') { throw 'WRONG_APPLICATION_MODE_OR_ENVIRONMENT' }
if ($taskApi.status -ne 'ready' -or $taskProxy.status -ne 'ready') { throw 'BACKEND_OR_PROXY_NOT_READY' }
if ($taskApi.settings.environment -ne 'PILOT_TEST' -or $taskProxy.settings.environment -ne 'PILOT_TEST') { throw 'WRONG_DATA_ENVIRONMENT' }
if ($taskApi.manifest_id -ne $taskProxy.manifest_id) { throw 'PROXY_MANIFEST_MISMATCH' }
if ($taskDiagnostics.checks.database_identity.database -ne 'market_cortex_pilot_test' -or $taskDiagnostics.checks.database_identity.server_port -ne 55432) { throw 'WRONG_DATABASE_IDENTITY' }
$taskFrontProcess = Get-CimInstance Win32_Process -Filter "ProcessId=$($taskState.frontend.pid)"
$taskUsesNextStart = [bool]($taskFrontProcess.CommandLine -match '\sstart\s')
if (-not $taskUsesNextStart) { throw 'PRODUCTION_NEXT_START_NOT_CONFIRMED' }
[pscustomobject]@{
    observed_at = (Get-Date).ToUniversalTime().ToString('o')
    mode = $taskState.mode
    environment = $taskState.environment
    next_start_process_confirmed = $taskUsesNextStart
    build_id = (Get-Content -LiteralPath apps/workstation/.next/BUILD_ID -Raw).Trim()
    state_file = $taskStateFile
    backend_health = $taskApi
    proxied_health = $taskProxy
    profile_preflight = $taskDiagnostics
} | ConvertTo-Json -Depth 10 | Set-Content -LiteralPath runtime/production-pilot-health.json -Encoding utf8
Write-Output 'Open http://127.0.0.1:3002; keep both application processes running for browser validation.'
```

Give Codex the **printed state-file path**, or say that runtime/production-pilot-health.json has been created. Neither contains the owner database URL. Codex can then inspect process/log/build evidence and test the real browser against this running production application.

## Browser acceptance and restart/shutdown

Verify every pane: Overview/Markets, Charts, Features, Market State, CORTEX, Opportunities, Portfolio & Risk, Journal/Prediction Ledger, Quant Lab, Intelligence, Research Lab, Personalized Intelligence and Experimental Quant. Check PILOT_TEST, correct manifests/as-of and source gaps. Use explicit synthetic pilot records; actual owner records are outside this stage. CORTEX numeric evidence must remain deterministic; an absent LLM must show the supported fallback.

After Codex records browser acceptance and saved artifact IDs, stop using the **existing** command:

```powershell
& .\scripts\Stop-MarketCortex.ps1 -StateFile $taskStateFile
Get-NetTCPConnection -State Listen -LocalPort 8001,3002 -ErrorAction SilentlyContinue | Select-Object LocalAddress,LocalPort,OwningProcess
```

The stop script checks process creation time, repo and command marker, stops only verified owned app processes/descendants, and removes its state file. It leaves PostgreSQL and retained backups/recovery databases intact. This is controlled process termination; it does not guarantee an in-flight request finishes. Shut down while research/workers are idle. Direct terminal Ctrl+C graceful API shutdown was previously validated separately.

Repeat the launch and health blocks to obtain a new state path, reopen the same saved artifact IDs, replay pinned evidence, and verify the same environment. After restart/recovery acceptance, stop with the **new** state path. Do not reuse a removed state file or kill unrelated listeners.

## Gates that remain separate

Owner schema migration/recovery is already verified. Initial owner Binance data writes need an explicit, reviewed authorization and production pilot validation first. Upstox/Alpaca and a local LLM are optional/deferred. No production runtime pass, owner-ready status or operational release tag is established by these prepared instructions.
