param([Parameter(Mandatory=$true)][string]$StateFile)
$ErrorActionPreference='Stop'
$taskRepo=(Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
$taskState=(Resolve-Path -LiteralPath $StateFile).Path
$taskRuntime=Join-Path $taskRepo 'runtime'
if (-not $taskState.StartsWith($taskRuntime+[IO.Path]::DirectorySeparatorChar,[StringComparison]::OrdinalIgnoreCase)) { throw 'STATE_OUTSIDE_RUNTIME' }
$taskInfo=Get-Content -LiteralPath $taskState -Raw | ConvertFrom-Json
foreach ($taskServer in @($taskInfo.frontend,$taskInfo.backend)) {
    if (-not $taskServer) { continue }
    $taskProcess=Get-Process -Id $taskServer.pid -ErrorAction SilentlyContinue
    if (-not $taskProcess) { continue }
    $taskDetails=Get-CimInstance Win32_Process -Filter "ProcessId=$($taskServer.pid)"
    if ($taskProcess.StartTime.ToUniversalTime().Ticks -ne ([datetime]$taskServer.started_at).ToUniversalTime().Ticks -or
        -not $taskDetails.CommandLine.Contains($taskRepo) -or
        -not $taskDetails.CommandLine.Contains($taskServer.marker)) { throw 'PROCESS_OWNERSHIP_MISMATCH' }
    # Next development mode can spawn a server child. Include only descendants of this verified process.
    $taskAll=@(Get-CimInstance Win32_Process)
    $taskOwned=[Collections.Generic.List[int]]::new(); $taskOwned.Add([int]$taskServer.pid)
    for ($taskIndex=0; $taskIndex -lt $taskOwned.Count; $taskIndex++) {
        foreach ($taskChild in $taskAll) {
            if ($taskChild.ParentProcessId -eq $taskOwned[$taskIndex] -and -not $taskOwned.Contains([int]$taskChild.ProcessId)) { $taskOwned.Add([int]$taskChild.ProcessId) }
        }
    }
    for ($taskIndex=$taskOwned.Count-1; $taskIndex -ge 0; $taskIndex--) { Stop-Process -Id $taskOwned[$taskIndex] -ErrorAction SilentlyContinue }
}
Remove-Item -LiteralPath $taskState
Write-Output 'STOPPED_OWNED_APPLICATION_PROCESSES'
