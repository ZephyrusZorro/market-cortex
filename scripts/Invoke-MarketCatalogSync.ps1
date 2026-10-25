# Manual or future approved Task Scheduler action. This script never registers a task.
param([Parameter(Mandatory=$true)][string]$ArchiveRoot,
      [ValidateSet('binance','upstox')][string[]]$Providers=@('binance','upstox'))
$ErrorActionPreference='Stop'
$taskRepo=(Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
$taskRoot=(Resolve-Path -LiteralPath $ArchiveRoot).Path
Push-Location $taskRepo
try {
    foreach($taskProvider in $Providers) {
        $taskReport=Join-Path $taskRepo ('runtime\catalog-sync-'+$taskProvider+'-'+[guid]::NewGuid().ToString('N')+'.json')
        & .\.venv\Scripts\python.exe -m market_cortex.market_data_cli --root $taskRoot --output $taskReport sync --provider $taskProvider
        if($LASTEXITCODE -ne 0){throw 'PUBLIC_CATALOG_SYNC_FAILED: preserve the safe receipt'}
    }
} finally { Pop-Location }
