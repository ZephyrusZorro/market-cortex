# Stage A gate only: existing owner read-only inventory, new encrypted backup,
# new isolated recovery. Never starts a cluster, app, collector or scheduler.
$ErrorActionPreference = 'Stop'
if (-not (Get-NetTCPConnection -State Listen -LocalPort 55432 -ErrorAction SilentlyContinue)) {
    throw 'EXISTING_RECOVERY_CLUSTER_OFFLINE: stop; no backup or restore has been attempted'
}
& (Join-Path $PSScriptRoot 'Invoke-OwnerProtection.ps1')
