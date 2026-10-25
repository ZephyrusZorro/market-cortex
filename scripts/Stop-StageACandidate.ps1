param([Parameter(Mandatory=$true)][string]$StateFile,[switch]$VerifyOnly)
$ErrorActionPreference='Stop'
$taskState=Get-Content -LiteralPath $StateFile -Raw | ConvertFrom-Json
if($taskState.api_port -ne 8678 -or $taskState.frontend_port -ne 3019 -or $taskState.cutover_performed -or
    -not ([IO.Path]::GetFullPath($StateFile)).StartsWith('C:\MarketCortexCandidates\stage-a-',[StringComparison]::OrdinalIgnoreCase)) {throw 'EXACT_CANDIDATE_STATE_REQUIRED'}
# Validate BOTH identities before stopping either; reject PID reuse or changed
# command lines. No owner/pilot/independent process is selected by port/name.
$taskOwned=@()
$taskPinned=$StateFile+'.listeners.json'
if(Test-Path -LiteralPath $taskPinned){
    $taskObservation=Get-Content -LiteralPath $taskPinned -Raw | ConvertFrom-Json
    if($taskObservation.state_file -ne ([IO.Path]::GetFullPath($StateFile))){throw 'CANDIDATE_LISTENER_RECEIPT_MISMATCH'}
    $taskState | Add-Member -NotePropertyName frontend_observed_pid -NotePropertyValue $taskObservation.frontend_pid
    $taskState | Add-Member -NotePropertyName frontend_observed_started_ticks -NotePropertyValue $taskObservation.frontend_started_ticks
    $taskState | Add-Member -NotePropertyName frontend_observed_executable -NotePropertyValue $taskObservation.frontend_executable
}
foreach($taskRole in @('frontend_observed','frontend','frontend_launcher','api','api_launcher')){
    $taskPid=$taskState.($taskRole+'_pid')
    if(-not $taskPid){continue}
    $taskProcess=Get-Process -Id $taskPid -ErrorAction SilentlyContinue
    if(-not $taskProcess){continue}
    $taskExpectedTicks=$taskState.($taskRole+'_started_ticks')
    $taskCim=Get-CimInstance Win32_Process -Filter ('ProcessId='+$taskPid)
    $taskExe=if($taskRole -eq 'api'){$taskState.python_executable}elseif($taskRole -eq 'api_launcher'){$taskState.api_launcher_executable}elseif($taskRole -eq 'frontend_observed'){$taskState.frontend_observed_executable}elseif($taskRole -eq 'frontend_launcher'){$taskState.frontend_launcher_executable}else{$taskState.node_executable}
    $taskNeedle=if($taskRole -in @('api','api_launcher')){'market_cortex.market_stage_a'}else{$taskState.node_entry}
    if($taskProcess.StartTime.ToUniversalTime().Ticks -ne $taskExpectedTicks -or
        $taskCim.ExecutablePath -ne $taskExe -or -not $taskCim.CommandLine.Contains($taskNeedle)){throw 'CANDIDATE_PROCESS_IDENTITY_CHANGED; nothing stopped'}
    if($taskOwned -notcontains $taskPid){$taskOwned+=$taskPid}
}
if($VerifyOnly){Write-Output 'Verified all exact candidate process identities; no processes stopped.';return}
foreach($taskPid in $taskOwned){if(Get-Process -Id $taskPid -ErrorAction SilentlyContinue){Stop-Process -Id $taskPid}}
Write-Output 'Only verified Stage A candidate processes were stopped. Existing owner, pilot and independent processes were not selected.'
