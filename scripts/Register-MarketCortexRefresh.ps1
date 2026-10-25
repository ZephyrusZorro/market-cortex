[CmdletBinding(SupportsShouldProcess=$true,ConfirmImpact='High')]
param([Parameter(Mandatory=$true)][string]$Profile,[switch]$Enable,[switch]$ConfirmOwnerWrites,[string]$ConnectionFile,
      [string]$TaskName='MarketCortex-ExplicitDailyRefresh')
$ErrorActionPreference='Stop'
if (-not $Enable) { throw 'SCHEDULE_DISABLED: use -Enable only after reviewing the profile and task' }
$taskRepo=(Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
$taskProfile=(Resolve-Path -LiteralPath $Profile).Path
$taskConfig=Get-Content -LiteralPath $taskProfile -Raw | ConvertFrom-Json
if ($taskConfig.environment -eq 'OWNER_MAIN' -and -not $ConfirmOwnerWrites) { throw 'OWNER_WRITE_AUTHORIZATION_REQUIRED' }
if ($taskConfig.environment -eq 'OWNER_MAIN' -and -not $ConnectionFile) { throw 'OWNER_SCHEDULE_REQUIRES_PRIVATE_DPAPI_CONNECTION_FILE' }
if ($ConnectionFile) {
    $taskConnection=(Resolve-Path -LiteralPath $ConnectionFile).Path
    if ($taskConnection.Contains('"')) { throw 'INVALID_PATH' }
}
if ($taskProfile.Contains('"') -or $taskRepo.Contains('"')) { throw 'INVALID_PATH' }
if ($taskConfig.timezone -ne 'Asia/Kolkata' -or (Get-TimeZone).Id -ne 'India Standard Time') { throw 'SCHEDULE_REQUIRES_MATCHING_INDIA_TIMEZONE' }
if ($TaskName -notmatch '^MarketCortex-[A-Za-z0-9_-]{1,64}$') { throw 'INVALID_TASK_NAME' }
if (Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue) { throw 'TASK_ALREADY_EXISTS: inspect it before replacing' }
# OWNER_MAIN credentials are decrypted from a current-user DPAPI file by the runner.
# The task stores a file path only; a private terminal environment is not inherited.
$taskExtra=if($ConfirmOwnerWrites){' -ConfirmOwnerWrites'}else{''}
if ($ConnectionFile) { $taskExtra+=' -ConnectionFile "'+$taskConnection+'"' }
$taskShell=(Get-Process -Id $PID).Path
$taskAction=New-ScheduledTaskAction -Execute $taskShell -Argument "-NoProfile -WindowStyle Hidden -File `"$PSScriptRoot\Refresh-MarketCortex.ps1`" -Profile `"$taskProfile`"$taskExtra" -WorkingDirectory $taskRepo
# A daily trigger plus logon catches missed runs. Ten-minute repetition retries durable backoff jobs.
$taskTrigger=New-ScheduledTaskTrigger -Daily -At $taskConfig.refresh_time
$taskRepeat=New-ScheduledTaskTrigger -Once -At (Get-Date) -RepetitionInterval (New-TimeSpan -Minutes 10) -RepetitionDuration (New-TimeSpan -Days 1)
$taskTrigger.Repetition=$taskRepeat.Repetition
$taskLogon=New-ScheduledTaskTrigger -AtLogOn -User ([Security.Principal.WindowsIdentity]::GetCurrent().Name)
$taskSettings=New-ScheduledTaskSettingsSet -StartWhenAvailable -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Minutes 30)
$taskPrincipal=New-ScheduledTaskPrincipal -UserId ([Security.Principal.WindowsIdentity]::GetCurrent().Name) -LogonType Interactive -RunLevel Limited
Write-Output "Visible optional task: $TaskName; daily $($taskConfig.refresh_time) Asia/Kolkata + logon; repeat 10m; current user; no API/frontend service."
if ($PSCmdlet.ShouldProcess($TaskName,'Register explicit local refresh schedule')) {
    Register-ScheduledTask -TaskName $TaskName -Action $taskAction -Trigger @($taskTrigger,$taskLogon) -Settings $taskSettings -Principal $taskPrincipal -Description "Explicit MARKET CORTEX $($taskConfig.environment) daily read-only-source refresh; profile $taskProfile" | Select-Object TaskName,State
}
