# Run only after schedule/scope approval. Windows current-user DPAPI, outside repo.
$ErrorActionPreference='Stop'
if (-not $env:MARKET_CORTEX_DATABASE_URL) { throw 'OWNER_CONNECTION_NOT_AVAILABLE_IN_THIS_TERMINAL' }
$taskRepo=(Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
Push-Location $taskRepo
try {
    $taskPreflight=& .\.venv\Scripts\python.exe -m market_cortex.operations preflight --profile config/operations-owner.example.json
    if ($LASTEXITCODE -ne 0) { throw 'OWNER_PREFLIGHT_FAILED' }
    $taskReport=$taskPreflight | ConvertFrom-Json
    if ($taskReport.settings.environment -ne 'OWNER_MAIN' -or $taskReport.checks.database_identity.database -ne 'market_cortex' -or $taskReport.checks.database_identity.server_port -ne 5432) { throw 'WRONG_OWNER_DATABASE' }
    $taskDirectory=Join-Path ([Environment]::GetFolderPath('LocalApplicationData')) 'MarketCortex\Secrets'
    New-Item -ItemType Directory -Path $taskDirectory -Force | Out-Null
    $taskFile=Join-Path $taskDirectory ('owner-refresh-'+[guid]::NewGuid().ToString('N')+'.dpapi')
    $taskSecure=ConvertTo-SecureString $env:MARKET_CORTEX_DATABASE_URL -AsPlainText -Force
    try {
        $taskCipher=ConvertFrom-SecureString $taskSecure
        # Exclusive creation; preserve every prior encrypted connection file.
        $taskStream=[IO.File]::Open($taskFile,[IO.FileMode]::CreateNew,[IO.FileAccess]::Write,[IO.FileShare]::None)
        try { $taskBytes=[Text.Encoding]::UTF8.GetBytes($taskCipher); $taskStream.Write($taskBytes,0,$taskBytes.Length); $taskStream.Flush($true) }
        finally { $taskStream.Dispose(); $taskBytes=$null; $taskCipher=$null }
        Write-Output $taskFile
    } finally { $taskSecure.Dispose() }
} finally { Pop-Location }
