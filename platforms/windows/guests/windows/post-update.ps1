#Requires -RunAsAdministrator

[CmdletBinding()]
param(
    [ValidateSet('Audit', 'Repair')]
    [string]$Mode = 'Audit',

    [ValidateSet('Development', 'Runtime')]
    [string]$Profile = 'Development',

    [ValidatePattern('^[A-Za-z0-9-]{8,64}$')]
    [string]$Nonce = 'local-audit',

    [string]$ReportPath,

    [string]$FirewallRuleName = 'WinVM-Testbed-OpenSSH-In-TCP',

    [string]$RelayTaskName = 'WinVM UI Relay'
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'

$sshDirectory = Join-Path $env:ProgramData 'ssh'
$sshConfigPath = Join-Path $sshDirectory 'sshd_config'
$authorizedKeysPath = Join-Path $sshDirectory `
    'administrators_authorized_keys'
$runtimeExecutable = Join-Path $env:ProgramData `
    'MachineControl\runtime\machine-control-windows.exe'

function Get-ServiceObservation {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Name,
        [string]$RequiredIdentity
    )

    $service = Get-CimInstance Win32_Service -Filter "Name='$Name'" `
        -ErrorAction SilentlyContinue
    if (-not $service) {
        return [ordered]@{ Healthy = $false; State = 'absent' }
    }
    $healthy = $service.State -eq 'Running' -and
        $service.StartMode -eq 'Auto'
    if ($RequiredIdentity) {
        $healthy = $healthy -and $service.StartName -eq $RequiredIdentity
    }
    $state = if ($healthy) {
        'running_automatic'
    }
    elseif ($service.State -eq 'Running') {
        'running_not_automatic'
    }
    elseif ($service.StartMode -eq 'Auto') {
        'stopped_automatic'
    }
    else {
        'stopped_not_automatic'
    }
    [ordered]@{ Healthy = $healthy; State = $state }
}

function Test-RestrictedAcl {
    param([Parameter(Mandatory = $true)][string]$Path)

    if (-not (Test-Path -LiteralPath $Path)) { return $false }
    $allowed = @('S-1-5-18', 'S-1-5-32-544')
    $acl = Get-Acl -LiteralPath $Path
    if (-not $acl.AreAccessRulesProtected) { return $false }
    foreach ($entry in $acl.Access) {
        $sid = $entry.IdentityReference.Translate(
            [Security.Principal.SecurityIdentifier]).Value
        if ($entry.IsInherited -or $sid -notin $allowed -or
            $entry.AccessControlType -ne 'Allow' -or
            ($entry.FileSystemRights -band
                [Security.AccessControl.FileSystemRights]::FullControl) -ne
                [Security.AccessControl.FileSystemRights]::FullControl) {
            return $false
        }
    }
    return $true
}

function Set-RestrictedAcl {
    param([Parameter(Mandatory = $true)][string]$Path)

    $system = [Security.Principal.SecurityIdentifier]::new('S-1-5-18')
    $administrators = [Security.Principal.SecurityIdentifier]::new(
        'S-1-5-32-544')
    $acl = [Security.AccessControl.FileSecurity]::new()
    $acl.SetOwner($system)
    $acl.SetAccessRuleProtection($true, $false)
    foreach ($identity in @($system, $administrators)) {
        $rule = [Security.AccessControl.FileSystemAccessRule]::new(
            $identity,
            [Security.AccessControl.FileSystemRights]::FullControl,
            [Security.AccessControl.AccessControlType]::Allow)
        [void]$acl.AddAccessRule($rule)
    }
    Set-Acl -LiteralPath $Path -AclObject $acl
}

function Get-SshGlobalConfig {
    if (-not (Test-Path -LiteralPath $sshConfigPath)) { return $null }
    $content = Get-Content -LiteralPath $sshConfigPath -Raw
    $match = [regex]::Match($content, '(?im)^\s*Match\s+')
    if ($match.Success) { return $content.Substring(0, $match.Index) }
    return $content
}

function Test-SshPolicy {
    $global = Get-SshGlobalConfig
    if ($null -eq $global) { return $false }
    foreach ($option in @(
        @{ Name = 'PubkeyAuthentication'; Value = 'yes' },
        @{ Name = 'PasswordAuthentication'; Value = 'no' },
        @{ Name = 'KbdInteractiveAuthentication'; Value = 'no' }
    )) {
        $pattern = '(?im)^\s*' + [regex]::Escape($option.Name) +
            '\s+' + [regex]::Escape($option.Value) + '\s*(?:#.*)?$'
        if (-not [regex]::IsMatch($global, $pattern)) { return $false }
    }
    return $true
}

function Set-SshPolicy {
    if (-not (Test-Path -LiteralPath $sshConfigPath)) {
        throw 'sshd_config is absent'
    }
    $content = Get-Content -LiteralPath $sshConfigPath -Raw
    $match = [regex]::Match($content, '(?im)^\s*Match\s+')
    if ($match.Success) {
        $global = $content.Substring(0, $match.Index)
        $matchConfig = $content.Substring($match.Index)
    }
    else {
        $global = $content
        $matchConfig = ''
    }
    foreach ($name in @(
        'PubkeyAuthentication',
        'PasswordAuthentication',
        'KbdInteractiveAuthentication')) {
        $pattern = '(?im)^\s*#?\s*' + [regex]::Escape($name) +
            '\s+\S+.*(?:\r?\n|$)'
        $global = [regex]::Replace($global, $pattern, '')
    }
    $global = $global.TrimEnd() + "`r`n" +
        "PubkeyAuthentication yes`r`n" +
        "PasswordAuthentication no`r`n" +
        "KbdInteractiveAuthentication no`r`n"
    Set-Content -LiteralPath $sshConfigPath -Encoding ascii `
        -Value ($global + $matchConfig)
}

function Test-SshConfiguration {
    $sshd = Join-Path $env:WINDIR 'System32\OpenSSH\sshd.exe'
    if (-not (Test-Path -LiteralPath $sshd)) { return $false }
    & $sshd -t 2>$null
    return $LASTEXITCODE -eq 0
}

function Test-SshMaterial {
    if (-not (Test-Path -LiteralPath $authorizedKeysPath)) {
        return $false
    }
    $keyLines = @(Get-Content -LiteralPath $authorizedKeysPath |
        Where-Object { -not [string]::IsNullOrWhiteSpace($_) })
    if ($keyLines.Count -eq 0 -or
        -not (Test-RestrictedAcl -Path $authorizedKeysPath)) {
        return $false
    }
    $privateKeys = @(Get-ChildItem -LiteralPath $sshDirectory -File `
        -ErrorAction SilentlyContinue |
        Where-Object Name -Match '^ssh_host_.*_key$')
    if ($privateKeys.Count -eq 0) { return $false }
    foreach ($privateKey in $privateKeys) {
        if (-not (Test-RestrictedAcl -Path $privateKey.FullName)) {
            return $false
        }
    }
    return $true
}

function Test-SshFirewall {
    $rule = Get-NetFirewallRule -Name $FirewallRuleName `
        -ErrorAction SilentlyContinue
    if (-not $rule -or "$($rule.Enabled)" -ne 'True' -or
        "$($rule.Direction)" -ne 'Inbound' -or
        "$($rule.Action)" -ne 'Allow' -or
        "$($rule.Profile)" -ne 'Any') {
        return $false
    }
    $port = $rule | Get-NetFirewallPortFilter -ErrorAction SilentlyContinue
    return $null -ne $port -and "$($port.Protocol)" -eq 'TCP' -and
        "$($port.LocalPort)" -eq '22'
}

function Set-SshFirewall {
    if (Get-NetFirewallRule -Name $FirewallRuleName `
            -ErrorAction SilentlyContinue) {
        Remove-NetFirewallRule -Name $FirewallRuleName
    }
    New-NetFirewallRule -Name $FirewallRuleName `
        -DisplayName 'WinVM Testbed OpenSSH Server (sshd)' `
        -Enabled True -Profile Any -Direction Inbound -Protocol TCP `
        -Action Allow -LocalPort 22 | Out-Null
}

function Test-ResidentProbe {
    if (-not (Test-Path -LiteralPath $runtimeExecutable)) { return $false }
    try {
        $text = '{"operation":"status"}' | & $runtimeExecutable call `
            2>$null | Out-String
        $status = $text | ConvertFrom-Json
        return $status.accepted -eq $true -and
            $status.desktop -eq 'Default' -and
            $status.data.isLocalSystem -eq $false -and
            [int]$status.data.integrityRid -eq 8192
    }
    catch { return $false }
}

function Test-Python3 {
    try {
        $launcher = Get-Command py.exe -ErrorAction SilentlyContinue
        if ($launcher) {
            & $launcher.Source -3 --version 2>$null | Out-Null
            return $LASTEXITCODE -eq 0
        }
        $python = Get-Command python.exe -ErrorAction SilentlyContinue
        if ($python) {
            & $python.Source -c 'import sys; raise SystemExit(sys.version_info.major != 3)'
            return $LASTEXITCODE -eq 0
        }
    }
    catch { return $false }
    return $false
}

function Test-DotNet8Sdk {
    try {
        $dotnet = Get-Command dotnet.exe -ErrorAction SilentlyContinue
        if (-not $dotnet) { return $false }
        $sdks = @(& $dotnet.Source --list-sdks 2>$null)
        return $LASTEXITCODE -eq 0 -and
            @($sdks | Where-Object { $_ -match '^8\.' }).Count -gt 0
    }
    catch { return $false }
}

function Test-PendingReboot {
    if (Test-Path -LiteralPath `
            'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Component Based Servicing\RebootPending') {
        return $true
    }
    if (Test-Path -LiteralPath `
            'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\WindowsUpdate\Auto Update\RebootRequired') {
        return $true
    }
    $sessionManager = Get-ItemProperty -LiteralPath `
        'HKLM:\SYSTEM\CurrentControlSet\Control\Session Manager' `
        -ErrorAction SilentlyContinue
    if ($sessionManager) {
        $pendingRename = $sessionManager.PSObject.Properties[
            'PendingFileRenameOperations']
        if ($pendingRename -and $pendingRename.Value) { return $true }
    }
    $update = Get-ItemProperty -LiteralPath `
        'HKLM:\SOFTWARE\Microsoft\Updates' -ErrorAction SilentlyContinue
    if ($null -eq $update) { return $false }
    $volatile = $update.PSObject.Properties['UpdateExeVolatile']
    return $null -ne $volatile -and $volatile.Value -notin @($null, 0)
}

function Get-Audit {
    $checks = [System.Collections.Generic.List[object]]::new()
    function Add-AuditCheck {
        param(
            [string]$Id,
            [bool]$Required,
            [bool]$Healthy,
            [string]$State
        )
        $checks.Add([ordered]@{
            id = $Id
            required = $Required
            healthy = $Healthy
            state = $State
        })
    }

    $qemu = Get-ServiceObservation -Name 'qemu-ga'
    Add-AuditCheck 'qemu_guest_agent' $true $qemu.Healthy $qemu.State

    $sshd = Get-ServiceObservation -Name 'sshd'
    Add-AuditCheck 'openssh_service' $true $sshd.Healthy $sshd.State
    $sshPolicy = Test-SshPolicy
    Add-AuditCheck 'openssh_key_only_policy' $true $sshPolicy `
        $(if ($sshPolicy) { 'configured' } else { 'invalid' })
    $sshConfig = Test-SshConfiguration
    Add-AuditCheck 'openssh_configuration' $true $sshConfig `
        $(if ($sshConfig) { 'valid' } else { 'invalid' })
    $sshMaterial = Test-SshMaterial
    Add-AuditCheck 'openssh_key_material' $true $sshMaterial `
        $(if ($sshMaterial) { 'restricted' } else { 'invalid' })
    $sshFirewall = Test-SshFirewall
    Add-AuditCheck 'openssh_firewall' $true $sshFirewall `
        $(if ($sshFirewall) { 'enabled_tcp_22_any' } else { 'invalid' })

    $runtime = Get-ServiceObservation -Name 'MachineControlRuntime' `
        -RequiredIdentity 'LocalSystem'
    Add-AuditCheck 'resident_service' $true $runtime.Healthy $runtime.State
    $residentProbe = Test-ResidentProbe
    Add-AuditCheck 'resident_interactive_probe' $true $residentProbe `
        $(if ($residentProbe) { 'ready' } else { 'unavailable' })

    $relay = Get-ScheduledTask -TaskName $RelayTaskName `
        -ErrorAction SilentlyContinue
    if ($relay) {
        $relayHealthy = "$($relay.State)" -eq 'Running'
        Add-AuditCheck 'legacy_winapp_relay' $false $relayHealthy `
            $(if ($relayHealthy) { 'running' } else { 'installed_not_running' })
    }
    else {
        Add-AuditCheck 'legacy_winapp_relay' $false $true 'not_installed'
    }

    $development = $Profile -eq 'Development'
    $python = Test-Python3
    Add-AuditCheck 'python_3' $development $python `
        $(if ($python) { 'available' } else { 'absent' })
    $dotnet = Test-DotNet8Sdk
    Add-AuditCheck 'dotnet_8_sdk' $development $dotnet `
        $(if ($dotnet) { 'available' } else { 'absent' })

    $pendingReboot = Test-PendingReboot
    Add-AuditCheck 'pending_reboot' $true (-not $pendingReboot) `
        $(if ($pendingReboot) { 'required' } else { 'clear' })

    $requiredFailures = @($checks | Where-Object {
        $_.required -and -not $_.healthy
    })
    $os = Get-CimInstance Win32_OperatingSystem
    [ordered]@{
        healthy = $requiredFailures.Count -eq 0
        reboot_required = $pendingReboot
        boot_epoch_utc = $os.LastBootUpTime.ToUniversalTime().ToString('o')
        checks = @($checks)
    }
}

function Invoke-RepairAction {
    param(
        [Parameter(Mandatory = $true)][string]$Id,
        [Parameter(Mandatory = $true)][scriptblock]$Action,
        [Parameter(Mandatory = $true)]
        [AllowEmptyCollection()]
        [System.Collections.Generic.List[object]]$Results
    )
    try {
        & $Action
        $Results.Add([ordered]@{ id = $Id; outcome = 'applied' })
    }
    catch {
        $Results.Add([ordered]@{ id = $Id; outcome = 'failed' })
    }
}

$initial = Get-Audit
$repairs = [System.Collections.Generic.List[object]]::new()
if ($Mode -eq 'Repair') {
    Invoke-RepairAction 'qemu_guest_agent' {
        if (-not (Get-Service -Name qemu-ga -ErrorAction SilentlyContinue)) {
            throw 'qemu-ga is absent'
        }
        Set-Service -Name qemu-ga -StartupType Automatic
        if ((Get-Service -Name qemu-ga).Status -ne 'Running') {
            Start-Service -Name qemu-ga
        }
    } $repairs

    Invoke-RepairAction 'openssh_policy' {
        if (-not (Get-Service -Name sshd -ErrorAction SilentlyContinue)) {
            throw 'sshd is absent'
        }
        if (-not (Test-Path -LiteralPath $authorizedKeysPath) -or
            @(Get-Content -LiteralPath $authorizedKeysPath |
                Where-Object { -not [string]::IsNullOrWhiteSpace($_) }).Count -eq 0) {
            throw 'authorized key material is absent'
        }
        Set-SshPolicy
        Set-RestrictedAcl -Path $authorizedKeysPath
        $sshKeygen = Join-Path $env:WINDIR `
            'System32\OpenSSH\ssh-keygen.exe'
        & $sshKeygen -A
        if ($LASTEXITCODE -ne 0) { throw 'host-key initialization failed' }
        Get-ChildItem -LiteralPath $sshDirectory -File |
            Where-Object Name -Match '^ssh_host_.*_key$' |
            ForEach-Object { Set-RestrictedAcl -Path $_.FullName }
        if (-not (Test-SshConfiguration)) {
            throw 'sshd configuration validation failed'
        }
        $openSshRegistry = 'HKLM:\SOFTWARE\OpenSSH'
        New-Item -Path $openSshRegistry -Force | Out-Null
        New-ItemProperty -Path $openSshRegistry -Name DefaultShell `
            -Value 'C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe' `
            -PropertyType String -Force | Out-Null
        Set-SshFirewall
        Set-Service -Name sshd -StartupType Automatic
        if ((Get-Service -Name sshd).Status -ne 'Running') {
            Start-Service -Name sshd
        }
        elseif (@($initial.checks | Where-Object {
                $_.id -like 'openssh_*' -and -not $_.healthy
            }).Count -gt 0) {
            Restart-Service -Name sshd -Force
        }
    } $repairs

    Invoke-RepairAction 'resident_service' {
        if (-not (Get-Service -Name MachineControlRuntime `
                -ErrorAction SilentlyContinue) -or
            -not (Test-Path -LiteralPath $runtimeExecutable)) {
            throw 'resident installation is absent'
        }
        Set-Service -Name MachineControlRuntime -StartupType Automatic
        if ((Get-Service -Name MachineControlRuntime).Status -ne 'Running') {
            Start-Service -Name MachineControlRuntime
        }
        elseif (-not (Test-ResidentProbe)) {
            Restart-Service -Name MachineControlRuntime -Force
        }
    } $repairs

    Invoke-RepairAction 'legacy_winapp_relay' {
        $relay = Get-ScheduledTask -TaskName $RelayTaskName `
            -ErrorAction SilentlyContinue
        if ($relay -and "$($relay.State)" -ne 'Running') {
            Start-ScheduledTask -TaskName $RelayTaskName
        }
    } $repairs
}

$final = if ($Mode -eq 'Repair') { Get-Audit } else { $initial }
$result = [ordered]@{
    schema = 'machine-control-windows-post-update/v0'
    nonce = $Nonce
    mode = $Mode.ToLowerInvariant()
    profile = $Profile.ToLowerInvariant()
    healthy = $final.healthy
    reboot_required = $final.reboot_required
    boot_epoch_utc = $final.boot_epoch_utc
    initial_healthy = $initial.healthy
    checks = $final.checks
    repairs = @($repairs)
}
$json = $result | ConvertTo-Json -Compress -Depth 8
if ($ReportPath) {
    $reportDirectory = Split-Path -Parent $ReportPath
    New-Item -ItemType Directory -Force -Path $reportDirectory | Out-Null
    $temporaryReport = "$ReportPath.$Nonce.tmp"
    Set-Content -LiteralPath $temporaryReport -Encoding ascii -Value $json
    Move-Item -LiteralPath $temporaryReport -Destination $ReportPath -Force
}
$json
if (-not $final.healthy) { exit 1 }
