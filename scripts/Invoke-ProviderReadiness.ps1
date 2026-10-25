param([Parameter(Mandatory=$true)][ValidateSet('upstox','alpaca')][string]$Provider,[switch]$Configure,[string]$Bundle)
$ErrorActionPreference='Stop'
$taskRepo=(Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
$taskNames=if($Provider -eq 'upstox'){@('UPSTOX_ACCESS_TOKEN')}else{@('APCA_API_KEY_ID','APCA_API_SECRET_KEY')}
$taskOld=@{}
foreach($taskName in $taskNames){$taskOld[$taskName]=[Environment]::GetEnvironmentVariable($taskName,'Process')}
Push-Location $taskRepo
try {
    if ($Configure) {
        foreach($taskName in $taskNames) {
            $taskSecret=Read-Host "Private $taskName (never paste into chat)" -AsSecureString
            try {
                $taskPlain=[Net.NetworkCredential]::new('', $taskSecret).Password
                if (-not $taskPlain) { throw 'EMPTY_PROVIDER_CREDENTIAL' }
                [Environment]::SetEnvironmentVariable($taskName,$taskPlain,'Process')
            } finally { $taskPlain=$null; $taskSecret.Dispose() }
        }
    }
    $taskOutput=Join-Path $taskRepo ('runtime\provider-'+$Provider+'-'+[guid]::NewGuid().ToString('N')+'.json')
    $taskArgs=@('--provider',$Provider,'--output',$taskOutput)
    if ($Bundle) { $taskArgs+=@('--bundle',(Resolve-Path -LiteralPath $Bundle).Path) }
    & .\.venv\Scripts\python.exe -m market_cortex.provider_readiness @taskArgs
    $taskExit=$LASTEXITCODE
    Write-Output "Provider receipt: $taskOutput"
    if($taskExit -ne 0){throw 'PROVIDER_PROBE_FAILED: inspect safe receipt; no owner ingestion occurred'}
} finally {
    foreach($taskName in $taskNames){[Environment]::SetEnvironmentVariable($taskName,$taskOld[$taskName],'Process')}
    $taskOld=$null
    Pop-Location
}
