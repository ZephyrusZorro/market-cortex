# Creates a NEW retained encrypted populated backup and isolated restore.
# No migrations, owner record writes, scheduling, app startup or backup deletion.
$ErrorActionPreference = 'Stop'
$taskRepo = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
if (-not $env:MARKET_CORTEX_DATABASE_URL) { throw 'OWNER_CONNECTION_NOT_AVAILABLE_IN_THIS_TERMINAL' }
$taskOldPath = $env:PATH
$taskOldPhrase = $env:MARKET_CORTEX_BACKUP_PASSPHRASE
$taskPhrase = $null; $taskRepeat = $null; $taskPlain = $null; $taskPlainRepeat = $null
try {
    $env:PATH = 'C:\Program Files\PostgreSQL\17\bin;' + $env:PATH
    Write-Output 'Retain the backup passphrase securely outside the repository. Existing backups and applications are preserved.'
    if (-not $env:MARKET_CORTEX_BACKUP_PASSPHRASE) {
        $taskPhrase = Read-Host 'Current-state retained backup passphrase (at least 16 characters)' -AsSecureString
        $taskRepeat = Read-Host 'Repeat passphrase' -AsSecureString
        $taskPlain = [Net.NetworkCredential]::new('', $taskPhrase).Password
        $taskPlainRepeat = [Net.NetworkCredential]::new('', $taskRepeat).Password
        if ($taskPlain.Length -lt 16 -or $taskPlain -cne $taskPlainRepeat) { throw 'BACKUP_PASSPHRASE_TOO_SHORT_OR_MISMATCH' }
        $env:MARKET_CORTEX_BACKUP_PASSPHRASE = $taskPlain
    }
    Push-Location $taskRepo
    try {
        & (Join-Path $taskRepo '.venv\Scripts\python.exe') -m market_cortex.owner_protection
        if ($LASTEXITCODE -ne 0) { throw 'PROTECTION_STOPPED: preserve the printed receipt, backup and isolated restore. Do not rerun blindly.' }
    } finally { Pop-Location }
} finally {
    $env:PATH = $taskOldPath
    $env:MARKET_CORTEX_BACKUP_PASSPHRASE = $taskOldPhrase
    $taskPlain = $null; $taskPlainRepeat = $null
    if ($taskPhrase) { $taskPhrase.Dispose() }
    if ($taskRepeat) { $taskRepeat.Dispose() }
}
