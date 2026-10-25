param([Parameter(Mandatory=$true)][ValidateSet('upstox','alpaca')][string]$Provider,
      [Parameter(Mandatory=$true)][string]$CredentialFile,[switch]$DelayedSip)
$ErrorActionPreference='Stop'
$taskRepo=(Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
$taskNames=if($Provider -eq 'upstox'){@('UPSTOX_ACCESS_TOKEN')}else{@('APCA_API_KEY_ID','APCA_API_SECRET_KEY','MARKET_CORTEX_ALPACA_ACCOUNT')}
$taskOld=@{}
foreach($taskName in $taskNames){$taskOld[$taskName]=[Environment]::GetEnvironmentVariable($taskName,'Process')}
$taskId=[guid]::NewGuid().ToString('N')
Push-Location $taskRepo
try {
    $taskPath=(Resolve-Path -LiteralPath $CredentialFile).Path
    $taskSecretsRoot=[IO.Path]::GetFullPath((Join-Path ([Environment]::GetFolderPath('LocalApplicationData')) 'MarketCortex\Secrets'))
    if (-not $taskPath.StartsWith($taskSecretsRoot+[IO.Path]::DirectorySeparatorChar,[StringComparison]::OrdinalIgnoreCase) -or
        [IO.Path]::GetExtension($taskPath) -ne '.dpapi') { throw 'CURRENT_USER_SECRET_FILE_REQUIRED' }
    $taskSecure=ConvertTo-SecureString (Get-Content -LiteralPath $taskPath -Raw)
    try {
        $taskJson=[Net.NetworkCredential]::new('', $taskSecure).Password
        $taskValues=$taskJson | ConvertFrom-Json
        foreach($taskName in $taskNames) {
            $taskValue=$taskValues.$taskName
            if (-not $taskValue) { throw 'CREDENTIAL_FILE_PROVIDER_MISMATCH' }
            [Environment]::SetEnvironmentVariable($taskName,$taskValue,'Process')
        }
    } finally { $taskSecure.Dispose(); $taskJson=$null; $taskValues=$null; $taskValue=$null }
    $taskRoot=Join-Path $taskRepo ('runtime\multi-market-probe-'+$taskId)
    $taskReport=Join-Path $taskRepo ('runtime\multi-market-probe-'+$taskId+'.json')
    $taskArgs=@('--provider',$Provider,'--root',$taskRoot,'--output',$taskReport,'--seconds','30')
    if($DelayedSip){$taskArgs+='--delayed-sip'}
    & .\.venv\Scripts\python.exe -m market_cortex.multi_market_probe @taskArgs
    if($LASTEXITCODE -ne 0){throw 'PROBE_NOT_VALIDATED: inspect the safe receipt; no owner import occurred'}
} finally {
    foreach($taskName in $taskNames){[Environment]::SetEnvironmentVariable($taskName,$taskOld[$taskName],'Process')}
    $taskOld=$null
    Pop-Location
}
