param([Parameter(Mandatory=$true)][string]$CandidateReceipt,
      [Parameter(Mandatory=$true)][string]$OwnerProtectionReport,
      [Parameter(Mandatory=$true)][string]$SourceProtectionReport,
      [Parameter(Mandatory=$true)][ValidateSet('history','binance','upstox','alpaca','alpaca-ui-90')][string]$Operation,
      [string]$UpstoxCredentialFile,[string]$AlpacaCredentialFile)
# Explicit finite acceptance only; no app startup or continuous collection.
$ErrorActionPreference='Stop'
$taskRepo=(Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
$taskCandidate=Get-Content -LiteralPath $CandidateReceipt -Raw | ConvertFrom-Json
if ($taskCandidate.authorized_stage -ne 'A_CONDITIONAL_CANDIDATE_ONLY' -or $taskCandidate.owner_cutover_approved -or
    $taskCandidate.owner_writes) {throw 'SCOPED_CANDIDATE_RECEIPT_REQUIRED'}
$taskNames=@('UPSTOX_ACCESS_TOKEN','APCA_API_KEY_ID','APCA_API_SECRET_KEY','MARKET_CORTEX_ALPACA_ACCOUNT',
    'MARKET_CORTEX_DATABASE_URL','MARKET_CORTEX_PILOT_DATABASE_URL','PYTHONPATH')
$taskOld=@{}
foreach($taskName in $taskNames){$taskOld[$taskName]=[Environment]::GetEnvironmentVariable($taskName,'Process')}
function Set-TaskPrivateProvider([string]$Provider,[string]$CredentialFile) {
    $taskSecretsRoot=[IO.Path]::GetFullPath((Join-Path ([Environment]::GetFolderPath('LocalApplicationData')) 'MarketCortex\Secrets'))
    if(-not $CredentialFile) {
        $taskFiles=@(Get-ChildItem -LiteralPath $taskSecretsRoot -Filter ($Provider+'-*.dpapi') -File)
        if($taskFiles.Count -eq 1){$CredentialFile=$taskFiles[0].FullName}
        else { $CredentialFile=Read-Host ('Path of the existing '+$Provider+' current-user DPAPI file (not the secret)') }
    }
    $taskPath=(Resolve-Path -LiteralPath $CredentialFile).Path
    if(-not $taskPath.StartsWith($taskSecretsRoot+[IO.Path]::DirectorySeparatorChar,[StringComparison]::OrdinalIgnoreCase) -or
        [IO.Path]::GetExtension($taskPath) -ne '.dpapi' -or
        ((Get-Item -LiteralPath $taskPath).Attributes -band [IO.FileAttributes]::ReparsePoint)) {throw 'CURRENT_USER_DPAPI_FILE_REQUIRED'}
    $taskAcl=Get-Acl -LiteralPath $taskPath
    $taskSid=[Security.Principal.WindowsIdentity]::GetCurrent().User
    if(-not $taskAcl.AreAccessRulesProtected){throw 'SECRET_ACL_NOT_PRIVATE'}
    foreach($taskRule in $taskAcl.GetAccessRules($true,$true,[Security.Principal.SecurityIdentifier])) {
        if($taskRule.AccessControlType -eq 'Allow' -and $taskRule.IdentityReference -ne $taskSid){throw 'SECRET_ACL_NOT_PRIVATE'}
    }
    $taskSecure=ConvertTo-SecureString (Get-Content -LiteralPath $taskPath -Raw)
    try {
        $taskJson=[Net.NetworkCredential]::new('', $taskSecure).Password
        $taskValues=$taskJson | ConvertFrom-Json
        $taskProviderNames=if($Provider -eq 'upstox'){@('UPSTOX_ACCESS_TOKEN')}else{@('APCA_API_KEY_ID','APCA_API_SECRET_KEY','MARKET_CORTEX_ALPACA_ACCOUNT')}
        foreach($taskName in $taskProviderNames){
            $taskValue=$taskValues.$taskName
            if(-not $taskValue){throw 'CREDENTIAL_FILE_PROVIDER_MISMATCH'}
            [Environment]::SetEnvironmentVariable($taskName,$taskValue,'Process')
        }
    } finally {$taskSecure.Dispose();$taskJson=$null;$taskValues=$null;$taskValue=$null}
}
try {
    foreach($taskName in $taskNames){[Environment]::SetEnvironmentVariable($taskName,$null,'Process')}
    $taskCodeRoot=[IO.Path]::GetFullPath($taskCandidate.candidate_root)
    if(-not $taskCodeRoot.StartsWith('C:\MarketCortexCandidates\stage-a-',[StringComparison]::OrdinalIgnoreCase)) {throw 'VERSIONED_CANDIDATE_CODE_REQUIRED'}
    $env:PYTHONPATH=Join-Path $taskCodeRoot 'src'
    if($Operation -in @('history','upstox')){Set-TaskPrivateProvider 'upstox' $UpstoxCredentialFile}
    if($Operation -in @('history','alpaca','alpaca-ui-90')){Set-TaskPrivateProvider 'alpaca' $AlpacaCredentialFile}
    $taskReport=Join-Path $taskRepo ('runtime\stage-a-'+$Operation+'-'+[guid]::NewGuid().ToString('N')+'.json')
    Push-Location $taskRepo
    try {
        if($Operation -eq 'alpaca-ui-90'){
            # Separately authorized addendum code; the frozen viewer package and
            # original capture scope are not overwritten or relaxed.
            $env:PYTHONPATH=$null
            & .\.venv\Scripts\python.exe -m market_cortex.market_stage_a_supplement --root $taskCandidate.source_root --owner-protection $OwnerProtectionReport --source-protection $SourceProtectionReport --report $taskReport
        } else {
            & .\.venv\Scripts\python.exe -m market_cortex.market_stage_a_acceptance --root $taskCandidate.source_root --owner-protection $OwnerProtectionReport --source-protection $SourceProtectionReport --operation $Operation --report $taskReport
        }
        if($LASTEXITCODE -ne 0){throw 'STAGE_A_GATE_STOPPED: preserve the receipt and partial source state; do not rerun blindly'}
    } finally {Pop-Location}
} finally {
    foreach($taskName in $taskNames){[Environment]::SetEnvironmentVariable($taskName,$taskOld[$taskName],'Process')}
    $taskOld=$null
}
