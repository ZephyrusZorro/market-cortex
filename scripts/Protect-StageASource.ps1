param([Parameter(Mandatory=$true)][string]$CandidateReceipt,[switch]$GenerateDpapiRecoveryKey)
$ErrorActionPreference = 'Stop'
$taskRepo = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
$taskCandidate = Get-Content -LiteralPath $CandidateReceipt -Raw | ConvertFrom-Json
$taskRoot = [IO.Path]::GetFullPath($taskCandidate.source_root)
$taskAllowed = 'C:\MarketCortexSources\three-market-v1\'
if (-not $taskRoot.StartsWith($taskAllowed,[StringComparison]::OrdinalIgnoreCase) -or
    $taskCandidate.owner_cutover_approved -or $taskCandidate.owner_writes -or
    $taskCandidate.authorized_stage -ne 'A_CONDITIONAL_CANDIDATE_ONLY') { throw 'SCOPED_STAGE_A_SOURCE_REQUIRED' }
$taskId = [guid]::NewGuid().ToString('N')
$taskBundle = 'C:\MarketCortexBackups\source-current-'+$taskId+'.mcsourcebackup'
$taskRestore = 'C:\MarketCortexSources\restore-drills\source-current-'+$taskId
$taskReport = Join-Path $taskRepo ('runtime\stage-a-source-protection-'+$taskId+'.json')
$taskNames = @('MARKET_CORTEX_SOURCE_BACKUP_PASSPHRASE','MARKET_CORTEX_DATABASE_URL','MARKET_CORTEX_PILOT_DATABASE_URL')
$taskOld = @{}
foreach($taskName in $taskNames){$taskOld[$taskName]=[Environment]::GetEnvironmentVariable($taskName,'Process')}
$taskSecret=$null; $taskRepeat=$null
try {
    if($GenerateDpapiRecoveryKey){
        if([Environment]::OSVersion.Platform -ne [PlatformID]::Win32NT){throw 'WINDOWS_CURRENT_USER_DPAPI_REQUIRED'}
        $taskKeyRoot=Join-Path ([Environment]::GetFolderPath('LocalApplicationData')) 'MarketCortex\RecoveryKeys'
        New-Item -ItemType Directory -Path $taskKeyRoot -Force | Out-Null
        $taskKeyPath=Join-Path $taskKeyRoot ('source-'+$taskId+'.dpapi')
        $taskMaterial=New-Object byte[] 32
        $taskRng=[Security.Cryptography.RandomNumberGenerator]::Create()
        try {$taskRng.GetBytes($taskMaterial);$taskPlain=[Convert]::ToBase64String($taskMaterial)}
        finally {$taskRng.Dispose();[Array]::Clear($taskMaterial,0,$taskMaterial.Length);$taskMaterial=$null}
        $taskSecret=ConvertTo-SecureString $taskPlain -AsPlainText -Force
        $taskCipher=ConvertFrom-SecureString $taskSecret
        $taskFile=[IO.File]::Open($taskKeyPath,[IO.FileMode]::CreateNew,[IO.FileAccess]::Write,[IO.FileShare]::None)
        try {$taskBytes=[Text.Encoding]::UTF8.GetBytes($taskCipher);$taskFile.Write($taskBytes,0,$taskBytes.Length);$taskFile.Flush($true)}
        finally {$taskFile.Dispose();$taskBytes=$null;$taskCipher=$null}
        $taskAcl=Get-Acl -LiteralPath $taskKeyPath
        $taskAcl.SetAccessRuleProtection($true,$false)
        $taskSid=[Security.Principal.WindowsIdentity]::GetCurrent().User
        $taskAcl.SetAccessRule([Security.AccessControl.FileSystemAccessRule]::new($taskSid,'FullControl','Allow'))
        Set-Acl -LiteralPath $taskKeyPath -AclObject $taskAcl
        $taskAcl=Get-Acl -LiteralPath $taskKeyPath
        if(-not $taskAcl.AreAccessRulesProtected){throw 'RECOVERY_KEY_ACL_NOT_PRIVATE'}
        foreach($taskRule in $taskAcl.GetAccessRules($true,$true,[Security.Principal.SecurityIdentifier])){
            if($taskRule.AccessControlType -eq 'Allow' -and $taskRule.IdentityReference -ne $taskSid){throw 'RECOVERY_KEY_ACL_NOT_PRIVATE'}
        }
        # Test recovery from the retained DPAPI file, rather than using only the
        # in-memory generator value. Never display or serialize the plaintext.
        $taskPlain=$null;$taskSecret.Dispose()
        $taskSecret=ConvertTo-SecureString (Get-Content -LiteralPath $taskKeyPath -Raw)
        $taskPlain=[Net.NetworkCredential]::new('', $taskSecret).Password
    } else {
        $taskSecret=Read-Host 'Retained source-cache backup passphrase (at least 16 characters)' -AsSecureString
        $taskRepeat=Read-Host 'Repeat passphrase' -AsSecureString
        $taskPlain=[Net.NetworkCredential]::new('', $taskSecret).Password
        $taskAgain=[Net.NetworkCredential]::new('', $taskRepeat).Password
        if($taskPlain.Length -lt 16 -or $taskPlain -cne $taskAgain){throw 'SOURCE_BACKUP_PASSPHRASE_TOO_SHORT_OR_MISMATCH'}
    }
    $env:MARKET_CORTEX_SOURCE_BACKUP_PASSPHRASE=$taskPlain
    Remove-Item Env:MARKET_CORTEX_DATABASE_URL -ErrorAction SilentlyContinue
    Remove-Item Env:MARKET_CORTEX_PILOT_DATABASE_URL -ErrorAction SilentlyContinue
    Push-Location $taskRepo
    try {
        & .\.venv\Scripts\python.exe -m market_cortex.market_source_backup --root $taskRoot --backup $taskBundle --restore-root $taskRestore --report $taskReport
        if($LASTEXITCODE -ne 0){throw 'SOURCE_RECOVERY_STOPPED: preserve all outputs and return the report path; do not rerun blindly'}
        if($GenerateDpapiRecoveryKey){
            [pscustomobject]@{status='RETAINED_CURRENT_USER_DPAPI_RECOVERY_KEY';source_protection_report=$taskReport;
                recovery_key_file=$taskKeyPath;recovery_key_cipher_sha256=(Get-FileHash -LiteralPath $taskKeyPath -Algorithm SHA256).Hash.ToLowerInvariant();
                portable_to_other_windows_user=$false;plaintext_stored=$false;owner_writes=$false} |
                ConvertTo-Json | Set-Content -LiteralPath ($taskReport+'.key-receipt.json') -Encoding utf8
        }
    } finally {Pop-Location}
} finally {
    foreach($taskName in $taskNames){[Environment]::SetEnvironmentVariable($taskName,$taskOld[$taskName],'Process')}
    $taskPlain=$null; $taskAgain=$null; $taskOld=$null
    if($taskSecret){$taskSecret.Dispose()}; if($taskRepeat){$taskRepeat.Dispose()}
}
