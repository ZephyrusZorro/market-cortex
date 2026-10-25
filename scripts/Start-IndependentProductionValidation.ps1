$ErrorActionPreference = 'Stop'
$taskRepository = Split-Path -Parent $PSScriptRoot
$taskSandbox = (Get-Content -LiteralPath (Join-Path $taskRepository 'runtime\multi-market-production-sandbox-path.txt') -Raw).Trim()
$taskTempRoot = [IO.Path]::GetFullPath([IO.Path]::GetTempPath())
$taskResolved = [IO.Path]::GetFullPath($taskSandbox)
if (-not $taskResolved.StartsWith($taskTempRoot, [StringComparison]::OrdinalIgnoreCase) -or
    -not (Split-Path -Leaf $taskResolved).StartsWith('mc-market-production-') -or
    -not (Test-Path -LiteralPath (Join-Path $taskResolved '.next\BUILD_ID'))) {
    throw 'VALIDATED_PRODUCTION_SANDBOX_REQUIRED'
}
if (Get-NetTCPConnection -State Listen -LocalPort 3018 -ErrorAction SilentlyContinue) {
    throw 'INDEPENDENT_PRODUCTION_PORT_IN_USE'
}
Remove-Item Env:MARKET_CORTEX_DATABASE_URL -ErrorAction SilentlyContinue
Remove-Item Env:MARKET_CORTEX_PILOT_DATABASE_URL -ErrorAction SilentlyContinue
$env:MARKET_CORTEX_MARKET_DATA_API_URL = 'http://127.0.0.1:8677'
$env:MARKET_CORTEX_API_URL = 'http://127.0.0.1:8677'
Set-Location -LiteralPath $taskResolved
Write-Output 'Independent production validation: http://127.0.0.1:3018/markets; API 8677; no owner/pilot connection.'
node .\node_modules\next\dist\bin\next start --hostname 127.0.0.1 --port 3018
