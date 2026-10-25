param([Parameter(Mandatory=$true)][string]$StateFile,[switch]$VerifyOnly)
# Recovery of the separate split launcher only. Never restores/resets data.
$ErrorActionPreference='Stop'
$taskRepo=(Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
if(-not ([IO.Path]::GetFullPath($StateFile)).StartsWith((Join-Path $taskRepo 'runtime')+[IO.Path]::DirectorySeparatorChar,[StringComparison]::OrdinalIgnoreCase)){throw 'EXACT_CUTOVER_STATE_REQUIRED'}
$taskState=Get-Content -LiteralPath $StateFile -Raw | ConvertFrom-Json
if($taskState.environment -ne 'OWNER_MAIN' -or -not $taskState.final_cutover_approved -or
    $taskState.api_port -ne 8765 -or $taskState.frontend_port -ne 3000){throw 'EXACT_APPROVED_CUTOVER_STATE_REQUIRED'}
$taskOwned=[Collections.Generic.List[int]]::new()
foreach($taskSaved in $taskState.processes){
    $taskProcess=Get-Process -Id $taskSaved.pid -ErrorAction SilentlyContinue
    if(-not $taskProcess){continue}
    $taskCim=Get-CimInstance Win32_Process -Filter ('ProcessId='+$taskSaved.pid)
    if($taskProcess.StartTime.ToUniversalTime().Ticks -ne $taskSaved.started_ticks -or
        -not $taskCim.CommandLine.Contains($taskSaved.marker) -or
        -not $taskCim.CommandLine.Contains($taskSaved.root)){throw 'CUTOVER_PROCESS_IDENTITY_CHANGED: nothing stopped'}
    if(-not $taskOwned.Contains([int]$taskSaved.pid)){$taskOwned.Add([int]$taskSaved.pid)}
}
# Traverse only children of verified parents, including Python/NVM redirectors.
for($taskIndex=0;$taskIndex -lt $taskOwned.Count;$taskIndex++){
    foreach($taskChild in @(Get-CimInstance Win32_Process -Filter ('ParentProcessId='+$taskOwned[$taskIndex]))){
        if(-not $taskOwned.Contains([int]$taskChild.ProcessId)){$taskOwned.Add([int]$taskChild.ProcessId)}
    }
}
if($VerifyOnly){Write-Output 'Verified cutover process tree; no processes stopped.';return}
for($taskIndex=$taskOwned.Count-1;$taskIndex -ge 0;$taskIndex--){Stop-Process -Id $taskOwned[$taskIndex] -ErrorAction SilentlyContinue}
Write-Output 'Stopped only the verified split-launch application. Source cache, databases, state file, backups and original installation retained.'
