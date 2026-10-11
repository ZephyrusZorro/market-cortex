# Run in the already configured owner PowerShell terminal. Human authorization
# for this exact procedure was granted in the MARKET CORTEX chat on 2026-10-11.
$ErrorActionPreference='Stop'
$taskRepo=(Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
if (-not $env:MARKET_CORTEX_DATABASE_URL) { throw 'OWNER_CONNECTION_NOT_AVAILABLE_IN_THIS_TERMINAL' }
$taskOldPath=$env:PATH
$taskOldPhrase=$env:MARKET_CORTEX_BACKUP_PASSPHRASE
$taskPhrase=$null; $taskRepeat=$null; $taskPlain=$null; $taskPlainRepeat=$null
try {
    $env:PATH='C:\Program Files\PostgreSQL\17\bin;'+$env:PATH
    $taskCluster='C:\Users\faris\Downloads\MARKET_CORTEX_Phase_1_Foundation_2026-09-30\market-cortex\runtime\pg_phase1'
    $taskPgCtl='C:\Program Files\PostgreSQL\17\bin\pg_ctl.exe'
    & $taskPgCtl -D $taskCluster status | Out-Null
    if ($LASTEXITCODE -ne 0) {
        if (Get-NetTCPConnection -State Listen -LocalPort 55432 -ErrorAction SilentlyContinue) { throw 'ISOLATED_PORT_IN_USE: inspect the existing listener' }
        & $taskPgCtl -D $taskCluster -o '-p 55432 -h 127.0.0.1' -l (Join-Path $taskCluster 'owner-migration-validation.log') -w start
        if ($LASTEXITCODE -ne 0) { throw 'ISOLATED_CLUSTER_START_FAILED' }
    }
    if (-not $env:MARKET_CORTEX_BACKUP_PASSPHRASE) {
        Write-Output 'Choose a backup passphrase of at least 16 characters and retain it securely outside this repository, separately from the backup.'
        $taskPhrase=Read-Host 'Retained backup passphrase' -AsSecureString
        $taskRepeat=Read-Host 'Repeat the same passphrase' -AsSecureString
        $taskPlain=[Net.NetworkCredential]::new('', $taskPhrase).Password
        $taskPlainRepeat=[Net.NetworkCredential]::new('', $taskRepeat).Password
        if ($taskPlain.Length -lt 16 -or $taskPlain -cne $taskPlainRepeat) { throw 'BACKUP_PASSPHRASE_TOO_SHORT_OR_MISMATCH' }
        $env:MARKET_CORTEX_BACKUP_PASSPHRASE=$taskPlain
    }
    Push-Location $taskRepo
    try {
        & (Join-Path $taskRepo '.venv\Scripts\python.exe') -m market_cortex.owner_migration --authorized-owner-migration
        if ($LASTEXITCODE -ne 0) { throw 'PROCEDURE_STOPPED: inspect the safe report path printed above; do not reset, retry migrations blindly, or restore over owner state.' }
    } finally { Pop-Location }
} finally {
    $env:PATH=$taskOldPath
    $env:MARKET_CORTEX_BACKUP_PASSPHRASE=$taskOldPhrase
    $taskPlain=$null; $taskPlainRepeat=$null
    if ($taskPhrase) { $taskPhrase.Dispose() }; if ($taskRepeat) { $taskRepeat.Dispose() }
}
