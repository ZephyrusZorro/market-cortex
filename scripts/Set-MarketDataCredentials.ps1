param([Parameter(Mandatory=$true)][ValidateSet('upstox','alpaca')][string]$Provider,
      [ValidateSet('paper','live')][string]$AlpacaAccount='paper')
$ErrorActionPreference='Stop'
if ([Environment]::OSVersion.Platform -ne [PlatformID]::Win32NT) { throw 'WINDOWS_CURRENT_USER_DPAPI_REQUIRED' }
$taskNames=if($Provider -eq 'upstox'){@('UPSTOX_ACCESS_TOKEN')}else{@('APCA_API_KEY_ID','APCA_API_SECRET_KEY')}
$taskValues=@{}
try {
    foreach($taskName in $taskNames) {
        $taskSecret=Read-Host "Private $taskName (hidden; never paste into chat)" -AsSecureString
        try {
            $taskPlain=[Net.NetworkCredential]::new('', $taskSecret).Password
            if (-not $taskPlain) { throw 'EMPTY_CREDENTIAL' }
            $taskValues[$taskName]=$taskPlain
        } finally { $taskPlain=$null; $taskSecret.Dispose() }
    }
    if ($Provider -eq 'alpaca') { $taskValues['MARKET_CORTEX_ALPACA_ACCOUNT']=$AlpacaAccount }
    $taskDirectory=Join-Path ([Environment]::GetFolderPath('LocalApplicationData')) 'MarketCortex\Secrets'
    New-Item -ItemType Directory -Path $taskDirectory -Force | Out-Null
    $taskPath=Join-Path $taskDirectory ($Provider+'-'+[guid]::NewGuid().ToString('N')+'.dpapi')
    $taskJson=$taskValues | ConvertTo-Json -Compress
    $taskSecure=ConvertTo-SecureString $taskJson -AsPlainText -Force
    try {
        $taskCipher=ConvertFrom-SecureString $taskSecure
        $taskStream=[IO.File]::Open($taskPath,[IO.FileMode]::CreateNew,[IO.FileAccess]::Write,[IO.FileShare]::None)
        try {
            $taskBytes=[Text.Encoding]::UTF8.GetBytes($taskCipher)
            $taskStream.Write($taskBytes,0,$taskBytes.Length)
            $taskStream.Flush($true)
        } finally { $taskStream.Dispose() }
        $taskAcl=Get-Acl -LiteralPath $taskPath
        $taskAcl.SetAccessRuleProtection($true,$false)
        $taskIdentity=[Security.Principal.WindowsIdentity]::GetCurrent().User
        $taskAcl.SetAccessRule([Security.AccessControl.FileSystemAccessRule]::new($taskIdentity,'FullControl','Allow'))
        Set-Acl -LiteralPath $taskPath -AclObject $taskAcl
    } finally { $taskSecure.Dispose() }
    Write-Host 'Encrypted for this Windows user. Credentials are unverified; no owner import or scheduler was enabled.'
    Write-Output $taskPath
} finally { $taskValues.Clear(); $taskJson=$null; $taskCipher=$null; $taskBytes=$null }
