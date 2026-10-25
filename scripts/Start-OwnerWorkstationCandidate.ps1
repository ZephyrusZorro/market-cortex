param([Parameter(Mandatory=$true)][string]$BuildReceipt,
      [Parameter(Mandatory=$true)][string]$AcceptanceReceipt,
      [Parameter(Mandatory=$true)][string]$ApplicationRecoveryReceipt,
      [switch]$FinalCutoverApproved)
# PREPARED ONLY. Conditional Stage A approval does NOT satisfy this guard.
# Uses preserved owner backend + accepted frontend; never migrates/ingests.
$ErrorActionPreference='Stop'
if(-not $FinalCutoverApproved){throw 'SEPARATE_FINAL_OWNER_CUTOVER_APPROVAL_REQUIRED'}
$taskAccepted=Get-Content -LiteralPath $AcceptanceReceipt -Raw | ConvertFrom-Json
if($taskAccepted.status -ne 'STAGE_A_ALL_PRE_CUTOVER_GATES_PASSED' -or
    $taskAccepted.gates.owner_recovery -ne $true -or $taskAccepted.gates.source_recovery -ne $true -or
    $taskAccepted.gates.production_browser -ne $true -or $taskAccepted.gates.performance -ne $true -or
    $taskAccepted.gates.candidate_restart -ne $true -or $taskAccepted.gates.fresh_indian_session -ne $true -or
    $taskAccepted.gates.live_browser -ne $true){throw 'ALL_PRE_CUTOVER_ACCEPTANCE_GATES_REQUIRED'}
if(-not $env:MARKET_CORTEX_DATABASE_URL){throw 'PRIVATE_OWNER_CONNECTION_REQUIRED'}
$taskRepo=(Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
$taskBuild=Get-Content -LiteralPath $BuildReceipt -Raw | ConvertFrom-Json
if((Get-FileHash -LiteralPath $BuildReceipt -Algorithm SHA256).Hash.ToLowerInvariant() -ne $taskAccepted.build_receipt_sha256){throw 'ACCEPTED_BUILD_RECEIPT_CHANGED'}
$taskCandidate=[IO.Path]::GetFullPath($taskBuild.candidate_root)
if(-not $taskCandidate.StartsWith('C:\MarketCortexCandidates\stage-a-',[StringComparison]::OrdinalIgnoreCase)){throw 'ISOLATED_ACCEPTED_FRONTEND_REQUIRED'}
$taskWeb=Join-Path $taskCandidate 'workstation'
foreach($taskProperty in $taskBuild.frontend_hashes.psobject.Properties){
    if((Get-FileHash -LiteralPath (Join-Path $taskWeb $taskProperty.Name) -Algorithm SHA256).Hash.ToLowerInvariant() -ne $taskProperty.Value){throw 'ACCEPTED_FRONTEND_CHANGED'}
}
if(Get-NetTCPConnection -State Listen -LocalPort 3000,8765 -ErrorAction SilentlyContinue){throw 'OWNER_PORTS_IN_USE: approved exact-state shutdown required first; no process replaced'}
$taskSource=Invoke-RestMethod -Uri 'http://127.0.0.1:8678/api/v1/market-data/stage-a-policy' -TimeoutSec 5
if($taskSource.history_fetch_enabled -or $taskSource.continuous_collection -or $taskSource.scheduled_jobs -or
    $taskSource.source_root -ne $taskBuild.source_root){throw 'ACCEPTED_CACHE_ONLY_SIDECAR_REQUIRED'}
$taskProfile=Join-Path $taskRepo 'config\operations-owner.example.json'
$taskPython=Join-Path $taskRepo '.venv\Scripts\python.exe'
Push-Location $taskRepo
try {
    & $taskPython -m scripts.verify_owner_cutover_preflight --snapshot-receipt $ApplicationRecoveryReceipt
    if($LASTEXITCODE -ne 0){throw 'PRIVATE_OWNER_CUTOVER_PREFLIGHT_FAILED: no process started'}
    $taskPreflight=& $taskPython -m market_cortex.operations preflight --profile $taskProfile --integrity
    if($LASTEXITCODE -ne 0){throw 'OWNER_READ_ONLY_PREFLIGHT_FAILED: no process started'}
    $taskCurrent=($taskPreflight -join "`n") | ConvertFrom-Json
    if($taskCurrent.status -ne 'VALIDATED' -or $taskCurrent.settings.environment -ne 'OWNER_MAIN' -or
        $taskCurrent.checks.database_identity.database -ne 'market_cortex' -or
        $taskCurrent.checks.database_identity.server_port -ne 5432){throw 'OWNER_IDENTITY_OR_INTEGRITY_GATE_FAILED'}
    & $taskPython -m scripts.verify_owner_production
    if($LASTEXITCODE -ne 0){throw 'FULL_OWNER_INVENTORY_GATE_FAILED: no process started'}
} finally {Pop-Location}
$taskId=[guid]::NewGuid().ToString('N')
$taskStateFile=Join-Path $taskRepo ('runtime\owner-candidate-cutover-'+$taskId+'.json')
$taskState=@{status='OWNER_CANDIDATE_STARTING_PENDING_ACCEPTANCE';environment='OWNER_MAIN';api_port=8765;frontend_port=3000;
    owner_writes=$false;candidate_root=$taskCandidate;source_root=$taskBuild.source_root;final_cutover_approved=$true;
    original_installation=$taskRepo;processes=@()}
$taskNames=@('MARKET_CORTEX_API_URL','MARKET_CORTEX_MARKET_DATA_API_URL','PYTHONPATH','UPSTOX_ACCESS_TOKEN','APCA_API_KEY_ID','APCA_API_SECRET_KEY','MARKET_CORTEX_ALPACA_ACCOUNT','MARKET_CORTEX_DATABASE_URL','MARKET_CORTEX_PILOT_DATABASE_URL')
$taskOld=@{};foreach($taskName in $taskNames){$taskOld[$taskName]=[Environment]::GetEnvironmentVariable($taskName,'Process')}
try {
    foreach($taskName in $taskNames){[Environment]::SetEnvironmentVariable($taskName,$null,'Process')}
    $env:MARKET_CORTEX_DATABASE_URL=$taskOld['MARKET_CORTEX_DATABASE_URL']
    $taskApi=Start-Process -FilePath $taskPython -ArgumentList @('-m','market_cortex.operations_runtime','--profile',$taskProfile,'--port','8765') -WorkingDirectory $taskRepo -WindowStyle Hidden -PassThru -RedirectStandardOutput ($taskStateFile+'.api.stdout.log') -RedirectStandardError ($taskStateFile+'.api.stderr.log')
    $taskState.processes+=@{pid=$taskApi.Id;started_ticks=$taskApi.StartTime.ToUniversalTime().Ticks;marker='market_cortex.operations_runtime';root=$taskRepo}
    Remove-Item Env:MARKET_CORTEX_DATABASE_URL -ErrorAction SilentlyContinue
    $env:MARKET_CORTEX_API_URL='http://127.0.0.1:8765'
    $env:MARKET_CORTEX_MARKET_DATA_API_URL='http://127.0.0.1:8678'
    $taskNode=(Get-Command node -CommandType Application).Source
    $taskEntry=Join-Path $taskWeb 'node_modules\next\dist\bin\next'
    $taskUi=Start-Process -FilePath $taskNode -ArgumentList @($taskEntry,'start','--hostname','127.0.0.1','--port','3000') -WorkingDirectory $taskWeb -WindowStyle Hidden -PassThru -RedirectStandardOutput ($taskStateFile+'.ui.stdout.log') -RedirectStandardError ($taskStateFile+'.ui.stderr.log')
    $taskState.processes+=@{pid=$taskUi.Id;started_ticks=$taskUi.StartTime.ToUniversalTime().Ticks;marker=$taskEntry;root=$taskCandidate}
    $taskState.status='OWNER_CANDIDATE_STARTED_PENDING_POST_CUTOVER_ACCEPTANCE'
} finally {
    $taskState | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $taskStateFile -Encoding utf8
    foreach($taskName in $taskNames){[Environment]::SetEnvironmentVariable($taskName,$taskOld[$taskName],'Process')}
    $taskOld=$null
    Write-Output $taskStateFile
}
