param([Parameter(Mandatory=$true)][string]$Profile,[switch]$ConfirmOwnerWrites,[string]$ConnectionFile)
$ErrorActionPreference='Stop'
$taskRepo=(Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
$taskPython=Join-Path $taskRepo '.venv\Scripts\python.exe'
$taskProfile=(Resolve-Path -LiteralPath $Profile).Path
$taskConfig=Get-Content -LiteralPath $taskProfile -Raw | ConvertFrom-Json
$taskOldConnection=[Environment]::GetEnvironmentVariable($taskConfig.database_env,'Process')
$taskExtra=@(); if($ConfirmOwnerWrites){$taskExtra=@('--confirm-owner-writes')}
Push-Location $taskRepo
try {
    if ($ConnectionFile) {
        $taskSecure=Get-Content -LiteralPath $ConnectionFile -Raw | ConvertTo-SecureString
        try { [Environment]::SetEnvironmentVariable($taskConfig.database_env,[Net.NetworkCredential]::new('', $taskSecure).Password,'Process') }
        finally { $taskSecure.Dispose() }
    }
    $taskPreflight=& $taskPython -m market_cortex.operations preflight --profile $taskProfile
    if ($LASTEXITCODE -ne 0) { throw 'REFRESH_PREFLIGHT_FAILED' }
    $taskChecked=$taskPreflight | ConvertFrom-Json
    if ($taskConfig.environment -eq 'OWNER_MAIN' -and
        ($taskChecked.checks.database_identity.database -ne 'market_cortex' -or $taskChecked.checks.database_identity.server_port -ne 5432)) { throw 'WRONG_OWNER_DATABASE' }
    Write-Output $taskPreflight
    & $taskPython -m market_cortex.operations schedule --profile $taskProfile @taskExtra
    if ($LASTEXITCODE -ne 0) { throw 'REFRESH_ENQUEUE_FAILED' }
    # Bounded one-shot worker batch. Backoff and expired leases survive process restart.
    $taskFailures=@(); $taskDeadline=(Get-Date).AddMinutes(20)
    for ($taskCount=0; $taskCount -lt 50 -and (Get-Date) -lt $taskDeadline; $taskCount++) {
        $taskOutput=& $taskPython -m market_cortex.operations worker --profile $taskProfile @taskExtra
        $taskExit=$LASTEXITCODE; Write-Output $taskOutput
        $taskResult=$taskOutput | ConvertFrom-Json
        if ($taskExit -ne 0 -and $taskResult.status -notin @('READY','DEAD')) { throw 'REFRESH_WORKER_FAILED: inspect operations status' }
        if ($taskResult.status -in @('READY','DEAD')) { $taskFailures+=$taskResult }
        if ($taskResult.status -eq 'IDLE') { break }
        Start-Sleep -Milliseconds 250
    }
    $taskFreshness=& $taskPython -m market_cortex.operations status --profile $taskProfile
    if ($LASTEXITCODE -ne 0) { throw 'REFRESH_STATUS_FAILED' }
    $taskReport=@{observed_at=(Get-Date).ToUniversalTime().ToString('o');freshness=($taskFreshness | ConvertFrom-Json);failures=$taskFailures}
    $taskReportPath=Join-Path $taskRepo ('runtime\refresh-'+[guid]::NewGuid().ToString('N')+'.json')
    $taskReport | ConvertTo-Json -Depth 12 | Set-Content -LiteralPath $taskReportPath -Encoding utf8
    Write-Output "Refresh receipt: $taskReportPath"
    if ($taskFailures.Count -or -not $taskReport.freshness.all_fresh -or $taskCount -ge 50 -or (Get-Date) -ge $taskDeadline) { throw 'REFRESH_INCOMPLETE: inspect retained receipt; durable retries remain bounded' }
} finally {
    [Environment]::SetEnvironmentVariable($taskConfig.database_env,$taskOldConnection,'Process')
    $taskOldConnection=$null
    Pop-Location
}
