param([Parameter(Mandatory=$true)][string]$BuildReceipt)
# Owner-executed startup after the earlier agent startup rejection. Candidate
# ports only; no deployment, credentials, DB connection, jobs or provider GETs.
$ErrorActionPreference='Stop'
$taskReceipt=Get-Content -LiteralPath $BuildReceipt -Raw | ConvertFrom-Json
if($taskReceipt.status -ne 'CANDIDATE_BUILT_OFFLINE_VERIFIED_NOT_DEPLOYED' -or $taskReceipt.cutover_performed){throw 'OFFLINE_VERIFIED_CANDIDATE_REQUIRED'}
$taskRoot=[IO.Path]::GetFullPath($taskReceipt.candidate_root)
$taskSource=[IO.Path]::GetFullPath($taskReceipt.source_root)
if(-not $taskRoot.StartsWith('C:\MarketCortexCandidates\stage-a-',[StringComparison]::OrdinalIgnoreCase) -or
   -not $taskSource.StartsWith('C:\MarketCortexSources\three-market-v1\stage-a-',[StringComparison]::OrdinalIgnoreCase)){throw 'ISOLATED_STAGE_A_PATHS_REQUIRED'}
foreach($taskProperty in $taskReceipt.backend_hashes.psobject.Properties){
    $taskCode=Join-Path $taskRoot $taskProperty.Name
    if((Get-FileHash -LiteralPath $taskCode -Algorithm SHA256).Hash.ToLowerInvariant() -ne $taskProperty.Value){throw 'CANDIDATE_BACKEND_CHANGED'}
}
$taskFrontend=Join-Path $taskRoot 'workstation'
if((Get-Content -LiteralPath (Join-Path $taskFrontend '.next\BUILD_ID') -Raw).Trim() -ne $taskReceipt.build_id){throw 'CANDIDATE_BUILD_CHANGED'}
foreach($taskProperty in $taskReceipt.frontend_hashes.psobject.Properties){
    if((Get-FileHash -LiteralPath (Join-Path $taskFrontend $taskProperty.Name) -Algorithm SHA256).Hash.ToLowerInvariant() -ne $taskProperty.Value){throw 'CANDIDATE_FRONTEND_CHANGED'}
}
if(Get-NetTCPConnection -State Listen -LocalPort 8678,3019 -ErrorAction SilentlyContinue){throw 'CANDIDATE_PORT_IN_USE; stop without replacing it'}
$taskRepo=(Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
$taskId=[guid]::NewGuid().ToString('N')
$taskRuntime=Join-Path $taskRoot ('launch-'+$taskId)
New-Item -ItemType Directory -Path $taskRuntime | Out-Null
$taskNames=@('MARKET_CORTEX_DATABASE_URL','MARKET_CORTEX_PILOT_DATABASE_URL','UPSTOX_ACCESS_TOKEN',
    'APCA_API_KEY_ID','APCA_API_SECRET_KEY','MARKET_CORTEX_ALPACA_ACCOUNT','PYTHONPATH',
    'MARKET_CORTEX_MARKET_DATA_API_URL','MARKET_CORTEX_API_URL')
$taskOld=@{}
foreach($taskName in $taskNames){$taskOld[$taskName]=[Environment]::GetEnvironmentVariable($taskName,'Process')}
$taskState=@{status='STARTING_CANDIDATE';candidate_root=$taskRoot;source_root=$taskSource;api_port=8678;frontend_port=3019;owner_writes=$false;cutover_performed=$false}
$taskStateFile=Join-Path $taskRuntime 'application.json'
try {
    foreach($taskName in $taskNames){[Environment]::SetEnvironmentVariable($taskName,$null,'Process')}
    $env:PYTHONPATH=Join-Path $taskRoot 'src'
    $env:MARKET_CORTEX_MARKET_DATA_API_URL='http://127.0.0.1:8678'
    $env:MARKET_CORTEX_API_URL='http://127.0.0.1:8678'
    $taskPython=Join-Path $taskRepo '.venv\Scripts\python.exe'
    $taskApi=Start-Process -FilePath $taskPython -ArgumentList @('-m','market_cortex.market_stage_a','--root',$taskSource,'--port','8678') -WorkingDirectory $taskRoot -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $taskRuntime 'api.stdout.log') -RedirectStandardError (Join-Path $taskRuntime 'api.stderr.log')
    $taskState.api_pid=$taskApi.Id
    $taskState.api_started_ticks=$taskApi.StartTime.ToUniversalTime().Ticks
    $taskState.python_executable=$taskPython
    $taskState.api_launcher_pid=$taskApi.Id
    $taskState.api_launcher_started_ticks=$taskApi.StartTime.ToUniversalTime().Ticks
    $taskState.api_launcher_executable=$taskPython
    $taskNode=(Get-Command node -CommandType Application).Source
    $taskNodeEntry=Join-Path $taskFrontend 'node_modules\next\dist\bin\next'
    $taskUi=Start-Process -FilePath $taskNode -ArgumentList @($taskNodeEntry,'start','--hostname','127.0.0.1','--port','3019') -WorkingDirectory $taskFrontend -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $taskRuntime 'ui.stdout.log') -RedirectStandardError (Join-Path $taskRuntime 'ui.stderr.log')
    $taskState.frontend_pid=$taskUi.Id
    $taskState.frontend_started_ticks=$taskUi.StartTime.ToUniversalTime().Ticks
    $taskState.node_executable=$taskNode
    $taskState.frontend_launcher_pid=$taskUi.Id
    $taskState.frontend_launcher_started_ticks=$taskUi.StartTime.ToUniversalTime().Ticks
    $taskState.frontend_launcher_executable=$taskNode
    $taskState.node_entry=$taskNodeEntry
    $taskReady=$false
    for($taskTry=0;$taskTry -lt 60;$taskTry++){
        try {
            $taskHealth=Invoke-RestMethod -Uri 'http://127.0.0.1:8678/api/v1/market-data/stage-a-policy' -TimeoutSec 2
            $taskPage=Invoke-WebRequest -Uri 'http://127.0.0.1:3019/markets' -TimeoutSec 2
            if($taskHealth.mode -eq 'STAGE_A_CANDIDATE_CACHE_ONLY' -and -not $taskHealth.history_fetch_enabled -and
                $taskHealth.source_root -eq $taskSource -and $taskPage.StatusCode -eq 200){$taskReady=$true;break}
        } catch {}
        Start-Sleep -Milliseconds 250
    }
    if(-not $taskReady){throw 'CANDIDATE_READINESS_FAILED; preserve logs and state'}
    # Windows venv python.exe can be a redirector with a child interpreter.
    # Retain the actual listener and the verified launcher, so recovery cannot
    # leave an orphaned API or stop an unrelated process based on a port alone.
    $taskListener=Get-NetTCPConnection -State Listen -LocalPort 8678 | Select-Object -First 1
    $taskActual=Get-CimInstance Win32_Process -Filter ('ProcessId='+$taskListener.OwningProcess)
    $taskAncestor=$taskActual
    $taskOwned=$false
    for($taskDepth=0;$taskDepth -lt 8 -and $taskAncestor;$taskDepth++){
        if($taskAncestor.ProcessId -eq $taskApi.Id){$taskOwned=$true;break}
        $taskAncestor=Get-CimInstance Win32_Process -Filter ('ProcessId='+$taskAncestor.ParentProcessId)
    }
    if(-not $taskOwned -or -not $taskActual.CommandLine.Contains('market_cortex.market_stage_a')){throw 'CANDIDATE_API_LISTENER_NOT_OWNED'}
    $taskState.api_pid=$taskActual.ProcessId
    $taskState.api_started_ticks=(Get-Process -Id $taskActual.ProcessId).StartTime.ToUniversalTime().Ticks
    $taskState.python_executable=$taskActual.ExecutablePath
    $taskUiListener=Get-NetTCPConnection -State Listen -LocalPort 3019 | Select-Object -First 1
    $taskUiActual=Get-CimInstance Win32_Process -Filter ('ProcessId='+$taskUiListener.OwningProcess)
    $taskAncestor=$taskUiActual;$taskOwned=$false
    for($taskDepth=0;$taskDepth -lt 8 -and $taskAncestor;$taskDepth++){
        if($taskAncestor.ProcessId -eq $taskUi.Id){$taskOwned=$true;break}
        $taskAncestor=Get-CimInstance Win32_Process -Filter ('ProcessId='+$taskAncestor.ParentProcessId)
    }
    if(-not $taskOwned -or -not $taskUiActual.CommandLine.Contains($taskNodeEntry)){throw 'CANDIDATE_UI_LISTENER_NOT_OWNED'}
    $taskState.frontend_pid=$taskUiActual.ProcessId
    $taskState.frontend_started_ticks=(Get-Process -Id $taskUiActual.ProcessId).StartTime.ToUniversalTime().Ticks
    $taskState.node_executable=$taskUiActual.ExecutablePath
    $taskState.status='CANDIDATE_RUNNING_PENDING_BROWSER_ACCEPTANCE'
} catch {
    $taskState.status='CANDIDATE_START_STOPPED_PRESERVE_PARTIAL_PROCESSES'
    throw
} finally {
    $taskState | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $taskStateFile -Encoding utf8
    foreach($taskName in $taskNames){[Environment]::SetEnvironmentVariable($taskName,$taskOld[$taskName],'Process')}
    $taskOld=$null
    Write-Output $taskStateFile
}
