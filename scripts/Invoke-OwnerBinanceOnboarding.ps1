# Explicit owner authorization for this scope was granted in this chat on 2026-10-11.
# Run in Terminal 1, where the private owner database connection already exists.
$ErrorActionPreference = 'Stop'
$taskRepo = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
if (-not $env:MARKET_CORTEX_DATABASE_URL) { throw 'OWNER_CONNECTION_NOT_AVAILABLE_IN_THIS_TERMINAL' }
$taskOldPath = $env:PATH
$taskOldPhrase = $env:MARKET_CORTEX_BACKUP_PASSPHRASE
$taskPhrase = $null; $taskRepeat = $null; $taskPlain = $null; $taskPlainRepeat = $null
try {
    $env:PATH = 'C:\Program Files\PostgreSQL\17\bin;' + $env:PATH
    Write-Output 'The new encrypted pre-ingestion backup will be retained. Retain its passphrase securely outside this repository.'
    if (-not $env:MARKET_CORTEX_BACKUP_PASSPHRASE) {
        $taskPhrase = Read-Host 'Retained backup passphrase (at least 16 characters)' -AsSecureString
        $taskRepeat = Read-Host 'Repeat the backup passphrase' -AsSecureString
        $taskPlain = [Net.NetworkCredential]::new('', $taskPhrase).Password
        $taskPlainRepeat = [Net.NetworkCredential]::new('', $taskRepeat).Password
        if ($taskPlain.Length -lt 16 -or $taskPlain -cne $taskPlainRepeat) { throw 'BACKUP_PASSPHRASE_TOO_SHORT_OR_MISMATCH' }
        $env:MARKET_CORTEX_BACKUP_PASSPHRASE = $taskPlain
    }
    Push-Location $taskRepo
    try {
        & (Join-Path $taskRepo '.venv\Scripts\python.exe') -m market_cortex.owner_onboarding --approved-owner-onboarding
        if ($LASTEXITCODE -ne 0) { throw 'ONBOARDING_STOPPED: inspect the printed safe report; preserve partial state and retained recovery. Do not reset or blindly rerun.' }
    } finally { Pop-Location }
} finally {
    $env:PATH = $taskOldPath
    $env:MARKET_CORTEX_BACKUP_PASSPHRASE = $taskOldPhrase
    $taskPlain = $null; $taskPlainRepeat = $null
    if ($taskPhrase) { $taskPhrase.Dispose() }
    if ($taskRepeat) { $taskRepeat.Dispose() }
}
