param(
    [Parameter(Mandatory=$true)][string]$Profile,
    [ValidateRange(1024,65535)][int]$ApiPort=8765,
    [ValidateRange(1024,65535)][int]$FrontendPort=3000,
    [switch]$Development
)
$ErrorActionPreference='Stop'
$taskRepo=(Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
$taskProfile=(Resolve-Path -LiteralPath $Profile).Path
$taskPython=Join-Path $taskRepo '.venv\Scripts\python.exe'
$taskWeb=Join-Path $taskRepo 'apps\workstation'
$taskNext=Join-Path $taskWeb 'node_modules\next\dist\bin\next'
$taskNode=(Get-Command node -ErrorAction Stop).Source
if ($taskProfile.Contains('"') -or $taskRepo.Contains('"')) { throw 'INVALID_PATH' }
Push-Location $taskRepo
try {
    $taskCheck=& $taskPython -m market_cortex.operations preflight --profile $taskProfile
    if ($LASTEXITCODE -ne 0) { throw $taskCheck }
    $taskReport=$taskCheck | ConvertFrom-Json
    Write-Output $taskCheck
    if ($ApiPort -eq $FrontendPort) { throw 'PORTS_MUST_DIFFER' }
    foreach ($taskPort in @($ApiPort,$FrontendPort)) {
        if (Get-NetTCPConnection -State Listen -LocalPort $taskPort -ErrorAction SilentlyContinue) { throw "PORT_IN_USE:$taskPort" }
    }
    if (-not $Development -and -not (Test-Path -LiteralPath (Join-Path $taskWeb '.next\BUILD_ID'))) { throw 'PRODUCTION_BUILD_REQUIRED: npm run build in apps/workstation' }
    $taskRuntime=Join-Path $taskRepo 'runtime'; New-Item -ItemType Directory -Path $taskRuntime -Force | Out-Null
    $taskId=[guid]::NewGuid().ToString('N')
    $taskState=Join-Path $taskRuntime "application-$taskId.json"
    $taskInfo=@{ environment=$taskReport.settings.environment; url="http://127.0.0.1:$FrontendPort"; backend=$null; frontend=$null; mode=$(if($Development){'development'}else{'production'}) }
    $taskOldApi=$env:MARKET_CORTEX_API_URL
    try {
        $taskApiArgs="-m market_cortex.operations_runtime --profile `"$taskProfile`" --port $ApiPort"
        $taskApi=Start-Process -FilePath $taskPython -ArgumentList $taskApiArgs -WorkingDirectory $taskRepo -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $taskRuntime "$taskId-api.out.log") -RedirectStandardError (Join-Path $taskRuntime "$taskId-api.err.log")
        $taskInfo.backend=@{ pid=$taskApi.Id; started_at=$taskApi.StartTime.ToUniversalTime().ToString('o'); marker='market_cortex.operations_runtime' }
        $taskInfo | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath $taskState -Encoding utf8
        $env:MARKET_CORTEX_API_URL="http://127.0.0.1:$ApiPort"
        $taskMode=if($Development){'dev'}else{'start'}
        $taskWebArgs="`"$taskNext`" $taskMode --hostname 127.0.0.1 --port $FrontendPort"
        $taskFront=Start-Process -FilePath $taskNode -ArgumentList $taskWebArgs -WorkingDirectory $taskWeb -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $taskRuntime "$taskId-web.out.log") -RedirectStandardError (Join-Path $taskRuntime "$taskId-web.err.log")
        $taskInfo.frontend=@{ pid=$taskFront.Id; started_at=$taskFront.StartTime.ToUniversalTime().ToString('o'); marker=$taskNext }
        $taskInfo | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath $taskState -Encoding utf8
        $taskDeadline=(Get-Date).AddSeconds(120)
        $taskReady=$false
        while ((Get-Date) -lt $taskDeadline) {
            if ($taskApi.HasExited -or $taskFront.HasExited) { throw 'SERVER_EXITED: inspect local runtime logs' }
            try {
                $taskHealth=Invoke-RestMethod -Uri "http://127.0.0.1:$ApiPort/api/v1/health" -TimeoutSec 3
                $taskPage=Invoke-WebRequest -Uri $taskInfo.url -TimeoutSec 5
                if ($taskHealth.status -eq 'ready' -and $taskHealth.settings.environment -eq $taskInfo.environment -and $taskPage.StatusCode -eq 200) { $taskReady=$true; break }
            } catch { }
            Start-Sleep -Seconds 1
        }
        if (-not $taskReady) { throw 'STARTUP_HEALTH_TIMEOUT' }
        $taskInfo | ConvertTo-Json -Depth 4
        Write-Output "Shutdown: & '$PSScriptRoot\Stop-MarketCortex.ps1' -StateFile '$taskState'"
    } catch {
        if (Test-Path -LiteralPath $taskState) { & (Join-Path $PSScriptRoot 'Stop-MarketCortex.ps1') -StateFile $taskState }
        throw
    } finally { $env:MARKET_CORTEX_API_URL=$taskOldApi }
} finally { Pop-Location }
