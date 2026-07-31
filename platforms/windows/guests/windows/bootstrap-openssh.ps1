#Requires -RunAsAdministrator

[CmdletBinding()]
param(
    [string]$PublicKeyPath = 'C:\Users\Public\winvm-host.pub',
    [string]$ReportPath = 'C:\Users\Public\winvm-openssh-report.json',
    [string]$FirewallRuleName = 'WinVM-Testbed-OpenSSH-In-TCP'
)

$ErrorActionPreference = 'Stop'

if (-not (Test-Path -LiteralPath $PublicKeyPath)) {
    throw "Staged public key not found at $PublicKeyPath"
}

$capabilityName = 'OpenSSH.Server~~~~0.0.1.0'
$capability = Get-WindowsCapability -Online -Name $capabilityName
if ($capability.State -ne 'Installed') {
    Add-WindowsCapability -Online -Name $capabilityName | Out-Null
}

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

$sshdConfigPath = Join-Path $env:ProgramData 'ssh\sshd_config'
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
& (Join-Path $env:WINDIR 'System32\OpenSSH\sshd.exe') -t
if ($LASTEXITCODE -ne 0) {
    throw "sshd configuration validation failed with exit code $LASTEXITCODE"
}

$openSshRegistry = 'HKLM:\SOFTWARE\OpenSSH'
New-Item -Path $openSshRegistry -Force | Out-Null
New-ItemProperty `
    -Path $openSshRegistry `
    -Name DefaultShell `
    -Value 'C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe' `
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
