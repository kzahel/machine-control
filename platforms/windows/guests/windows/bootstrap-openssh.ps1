#Requires -RunAsAdministrator

[CmdletBinding()]
param(
    [string]$PublicKeyPath = 'C:\Users\Public\winvm-host.pub',
    [string]$ReportPath = 'C:\Users\Public\winvm-openssh-report.json',
    [string]$FirewallRuleName = 'WinVM-Testbed-OpenSSH-In-TCP'
)

$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'

$powerShellVersion = '7.6.5'
$powerShellInstallDirectory = Join-Path $env:ProgramFiles 'PowerShell\7'
$powerShellExecutable = Join-Path $powerShellInstallDirectory 'pwsh.exe'

function Get-PowerShellArchive {
    $nativeArchitecture = if ($env:PROCESSOR_ARCHITEW6432) {
        $env:PROCESSOR_ARCHITEW6432
    }
    else {
        $env:PROCESSOR_ARCHITECTURE
    }
    switch ($nativeArchitecture) {
        'ARM64' {
            return [ordered]@{
                Name = "PowerShell-$powerShellVersion-win-arm64.zip"
                Sha256 = '20514a755d16428dc4355c85e0883c859531e71cc3e122670aa1fccdbf96ba7e'
            }
        }
        'AMD64' {
            return [ordered]@{
                Name = "PowerShell-$powerShellVersion-win-x64.zip"
                Sha256 = '32eb8f6cdce08f86e987d625a2733e54ac3e289ae7e1621b14c0b5bcec2434ea'
            }
        }
        default {
            throw "Unsupported PowerShell target architecture: $nativeArchitecture"
        }
    }
}

function Test-PowerShellRuntime {
    if (-not (Test-Path -LiteralPath $powerShellExecutable -PathType Leaf)) {
        return $false
    }
    try {
        $installedVersion = & $powerShellExecutable -NoLogo -NoProfile `
            -NonInteractive -Command `
            '[System.Management.Automation.PSVersionInfo]::PSVersion.ToString()'
        return $LASTEXITCODE -eq 0 -and
            "$installedVersion" -eq $powerShellVersion
    }
    catch {
        return $false
    }
}

function Install-PowerShellRuntime {
    if (Test-PowerShellRuntime) { return }

    $package = Get-PowerShellArchive
    $archive = Join-Path $env:TEMP $package.Name
    $staging = Join-Path $env:TEMP `
        "machine-control-powershell-$powerShellVersion"
    $uri = "https://github.com/PowerShell/PowerShell/releases/download/" +
        "v$powerShellVersion/$($package.Name)"
    try {
        Invoke-WebRequest -UseBasicParsing -Uri $uri -OutFile $archive
        $actualDigest = (Get-FileHash -Algorithm SHA256 `
            -LiteralPath $archive).Hash.ToLowerInvariant()
        if ($actualDigest -ne $package.Sha256) {
            throw 'PowerShell archive digest mismatch'
        }
        Remove-Item -LiteralPath $staging -Recurse -Force `
            -ErrorAction SilentlyContinue
        New-Item -ItemType Directory -Force -Path $staging | Out-Null
        Expand-Archive -LiteralPath $archive -DestinationPath $staging -Force
        $stagedExecutable = Join-Path $staging 'pwsh.exe'
        $stagedVersion = & $stagedExecutable -NoLogo -NoProfile `
            -NonInteractive -Command `
            '[System.Management.Automation.PSVersionInfo]::PSVersion.ToString()'
        if ($LASTEXITCODE -ne 0 -or "$stagedVersion" -ne $powerShellVersion) {
            throw 'Staged PowerShell runtime failed validation'
        }
        Remove-Item -LiteralPath $powerShellInstallDirectory -Recurse -Force `
            -ErrorAction SilentlyContinue
        New-Item -ItemType Directory -Force `
            -Path (Split-Path -Parent $powerShellInstallDirectory) | Out-Null
        Move-Item -LiteralPath $staging `
            -Destination $powerShellInstallDirectory
    }
    finally {
        Remove-Item -LiteralPath $archive -Force -ErrorAction SilentlyContinue
        Remove-Item -LiteralPath $staging -Recurse -Force `
            -ErrorAction SilentlyContinue
    }

    if (-not (Test-PowerShellRuntime)) {
        throw 'PowerShell runtime installation did not become healthy'
    }
}

if (-not (Test-Path -LiteralPath $PublicKeyPath)) {
    throw "Staged public key not found at $PublicKeyPath"
}

$capabilityName = 'OpenSSH.Server~~~~0.0.1.0'
$capability = Get-WindowsCapability -Online -Name $capabilityName
if ($capability.State -ne 'Installed') {
    Add-WindowsCapability -Online -Name $capabilityName | Out-Null
}
Install-PowerShellRuntime

$isAdministrator = [Security.Principal.WindowsPrincipal]::new(
    [Security.Principal.WindowsIdentity]::GetCurrent()
).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)

$publicKey = (Get-Content -LiteralPath $PublicKeyPath -Raw).Trim()
if ($isAdministrator) {
    $authorizedKeysPath = Join-Path $env:ProgramData 'ssh\administrators_authorized_keys'
} else {
    $sshDirectory = Join-Path $HOME '.ssh'
    New-Item -ItemType Directory -Force -Path $sshDirectory | Out-Null
    $authorizedKeysPath = Join-Path $sshDirectory 'authorized_keys'
}

$existingKeys = if (Test-Path -LiteralPath $authorizedKeysPath) {
    Get-Content -LiteralPath $authorizedKeysPath
} else {
    @()
}

if ($publicKey -notin $existingKeys) {
    Add-Content -LiteralPath $authorizedKeysPath -Encoding ascii -Value $publicKey
}

if ($isAdministrator) {
    & icacls.exe $authorizedKeysPath /inheritance:r /grant:r '*S-1-5-32-544:F' '*S-1-5-18:F' | Out-Null
}

$sshdDirectory = Join-Path $env:ProgramData 'ssh'
New-Item -ItemType Directory -Force -Path $sshdDirectory | Out-Null
$sshdConfigPath = Join-Path $sshdDirectory 'sshd_config'
if (-not (Test-Path -LiteralPath $sshdConfigPath)) {
    $defaultSshdConfig = Join-Path $env:WINDIR `
        'System32\OpenSSH\sshd_config_default'
    if (-not (Test-Path -LiteralPath $defaultSshdConfig)) {
        throw 'OpenSSH installed without sshd_config or sshd_config_default'
    }
    Copy-Item -LiteralPath $defaultSshdConfig -Destination $sshdConfigPath
}
$sshdConfig = Get-Content -LiteralPath $sshdConfigPath -Raw
$matchStart = [regex]::Match($sshdConfig, '(?im)^\s*Match\s+')
if ($matchStart.Success) {
    $globalConfig = $sshdConfig.Substring(0, $matchStart.Index)
    $matchConfig = $sshdConfig.Substring($matchStart.Index)
} else {
    $globalConfig = $sshdConfig
    $matchConfig = ''
}

foreach ($option in @(
    @{ Name = 'PubkeyAuthentication'; Value = 'yes' },
    @{ Name = 'PasswordAuthentication'; Value = 'no' },
    @{ Name = 'KbdInteractiveAuthentication'; Value = 'no' }
)) {
    $pattern = '(?im)^\s*#?\s*' + [regex]::Escape($option.Name) + '\s+\S+.*$'
    $replacement = $option.Name + ' ' + $option.Value
    if ([regex]::IsMatch($globalConfig, $pattern)) {
        $globalConfig = [regex]::Replace($globalConfig, $pattern, $replacement, 1)
    } else {
        $globalConfig = $globalConfig.TrimEnd() + "`r`n" + $replacement + "`r`n"
    }
}

Set-Content -LiteralPath $sshdConfigPath -Encoding ascii -Value ($globalConfig + $matchConfig)
$sshKeygen = Join-Path $env:WINDIR 'System32\OpenSSH\ssh-keygen.exe'
& $sshKeygen -A
if ($LASTEXITCODE -ne 0) {
    throw "OpenSSH host-key initialization failed with exit code $LASTEXITCODE"
}

# On a fresh local-account installation, ssh-keygen can leave explicit access
# for the setup administrator on newly generated host private keys. Current
# OpenSSH for Windows rejects those keys and the sshd service exits with 1067.
# Build the private-key ACL from well-known SIDs so this is independent of the
# account name and the Windows display language.
$system = [Security.Principal.SecurityIdentifier]::new('S-1-5-18')
$administrators = [Security.Principal.SecurityIdentifier]::new(
    'S-1-5-32-544')
$hostPrivateKeys = @(Get-ChildItem -LiteralPath $sshdDirectory -File |
    Where-Object Name -Match '^ssh_host_.*_key$')
if ($hostPrivateKeys.Count -eq 0) {
    throw 'OpenSSH host-key initialization produced no private keys'
}
foreach ($hostPrivateKey in $hostPrivateKeys) {
    $hostKeyAcl = [Security.AccessControl.FileSecurity]::new()
    $hostKeyAcl.SetOwner($system)
    $hostKeyAcl.SetAccessRuleProtection($true, $false)
    foreach ($identity in @($system, $administrators)) {
        $rule = [Security.AccessControl.FileSystemAccessRule]::new(
            $identity,
            [Security.AccessControl.FileSystemRights]::FullControl,
            [Security.AccessControl.AccessControlType]::Allow)
        [void]$hostKeyAcl.AddAccessRule($rule)
    }
    Set-Acl -LiteralPath $hostPrivateKey.FullName -AclObject $hostKeyAcl
}
& (Join-Path $env:WINDIR 'System32\OpenSSH\sshd.exe') -t
if ($LASTEXITCODE -ne 0) {
    throw "sshd configuration validation failed with exit code $LASTEXITCODE"
}

$openSshRegistry = 'HKLM:\SOFTWARE\OpenSSH'
New-Item -Path $openSshRegistry -Force | Out-Null
New-ItemProperty `
    -Path $openSshRegistry `
    -Name DefaultShell `
    -Value $powerShellExecutable `
    -PropertyType String `
    -Force | Out-Null
New-ItemProperty `
    -Path $openSshRegistry `
    -Name DefaultShellCommandOption `
    -Value '-c' `
    -PropertyType String `
    -Force | Out-Null

$firewallRule = Get-NetFirewallRule -Name 'OpenSSH-Server-In-TCP' -ErrorAction SilentlyContinue
if (-not $firewallRule) {
    New-NetFirewallRule `
        -Name 'OpenSSH-Server-In-TCP' `
        -DisplayName 'OpenSSH Server (sshd)' `
        -Enabled True `
        -Direction Inbound `
        -Protocol TCP `
        -Action Allow `
        -LocalPort 22 | Out-Null
} else {
    Enable-NetFirewallRule -Name 'OpenSSH-Server-In-TCP' | Out-Null
}

# Some Windows images ship an OpenSSH rule whose hidden service or profile
# filters do not admit traffic from UTM's shared network. Keep a simple,
# explicit rule for this local VM path.
if (Get-NetFirewallRule -Name $FirewallRuleName -ErrorAction SilentlyContinue) {
    Set-NetFirewallRule `
        -Name $FirewallRuleName `
        -Enabled True `
        -Profile Any `
        -Direction Inbound `
        -Action Allow | Out-Null
} else {
    New-NetFirewallRule `
        -Name $FirewallRuleName `
        -DisplayName 'WinVM Testbed OpenSSH Server (sshd)' `
        -Enabled True `
        -Profile Any `
        -Direction Inbound `
        -Protocol TCP `
        -Action Allow `
        -LocalPort 22 | Out-Null
}

Set-Service -Name sshd -StartupType Automatic
$sshdService = Get-Service -Name sshd
if ($sshdService.Status -eq 'Running') {
    Restart-Service -Name sshd -Force
} else {
    Start-Service -Name sshd
}

$listener = Get-NetTCPConnection -State Listen -LocalPort 22 -ErrorAction SilentlyContinue |
    Select-Object -First 1

$os = Get-CimInstance Win32_OperatingSystem
$report = [ordered]@{
    generated_at = (Get-Date).ToString('o')
    hostname = $env:COMPUTERNAME
    username = $env:USERNAME
    os = $os.Caption
    os_version = $os.Version
    architecture = $env:PROCESSOR_ARCHITECTURE
    administrator = $isAdministrator
    authorized_keys_path = $authorizedKeysPath
    password_authentication = 'disabled'
    keyboard_interactive_authentication = 'disabled'
    powershell_version = $powerShellVersion
    powershell_path = $powerShellExecutable
    sshd_status = (Get-Service sshd).Status.ToString()
    sshd_start_type = (Get-CimInstance Win32_Service -Filter "Name='sshd'").StartMode
    sshd_listen_address = $listener.LocalAddress
    sshd_listen_port = $listener.LocalPort
    localhost_port_22 = (Test-NetConnection -ComputerName 127.0.0.1 -Port 22 -WarningAction SilentlyContinue).TcpTestSucceeded
    ip_addresses = @(Get-NetIPAddress -AddressFamily IPv4 | Where-Object {
        $_.IPAddress -notlike '127.*'
    } | Select-Object -ExpandProperty IPAddress)
}

$reportJson = $report | ConvertTo-Json
$reportJson | Set-Content -LiteralPath $ReportPath -Encoding ascii
$reportJson
