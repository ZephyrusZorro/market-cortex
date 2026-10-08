param([Parameter(Mandatory=$true)][string]$Profile,[switch]$ConfirmOwnerWrites)
$ErrorActionPreference='Stop'
$taskRepo=(Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
$taskPython=Join-Path $taskRepo '.venv\Scripts\python.exe'
$taskProfile=(Resolve-Path -LiteralPath $Profile).Path
$taskExtra=@(); if($ConfirmOwnerWrites){$taskExtra=@('--confirm-owner-writes')}
Push-Location $taskRepo
try {
    & $taskPython -m market_cortex.operations schedule --profile $taskProfile @taskExtra
    if ($LASTEXITCODE -ne 0) { throw 'REFRESH_ENQUEUE_FAILED' }
    # Bounded one-shot worker batch. Backoff and expired leases survive process restart.
    for ($taskCount=0; $taskCount -lt 50; $taskCount++) {
        $taskOutput=& $taskPython -m market_cortex.operations worker --profile $taskProfile @taskExtra
        $taskExit=$LASTEXITCODE; Write-Output $taskOutput
        if ($taskExit -ne 0) { throw 'REFRESH_WORKER_FAILED: inspect operations status' }
        if (($taskOutput | ConvertFrom-Json).status -eq 'IDLE') { break }
        Start-Sleep -Milliseconds 250
    }
} finally { Pop-Location }
