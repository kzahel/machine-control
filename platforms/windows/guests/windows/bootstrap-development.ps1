#Requires -RunAsAdministrator

[CmdletBinding()]
param(
    [string]$ReportPath
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'

function Update-ProcessPath {
    $machine = [Environment]::GetEnvironmentVariable('Path', 'Machine')
    $user = [Environment]::GetEnvironmentVariable('Path', 'User')
    $env:Path = "$machine;$user"
}

function Test-Python3 {
    Update-ProcessPath
    $launcher = Get-Command py.exe -ErrorAction SilentlyContinue
    if ($launcher) {
        & $launcher.Source -3 --version 2>$null | Out-Null
        return $LASTEXITCODE -eq 0
    }
    $python = Get-Command python.exe -ErrorAction SilentlyContinue
    if (-not $python) { return $false }
    if ($python.Source -like '*\Microsoft\WindowsApps\*') {
        return $false
    }
    & $python.Source -c `
        'import sys; raise SystemExit(sys.version_info.major != 3)' 2>$null
    return $LASTEXITCODE -eq 0
}

function Test-DotNet8Sdk {
    Update-ProcessPath
    $dotnet = Get-Command dotnet.exe -ErrorAction SilentlyContinue
    if (-not $dotnet) { return $false }
    $sdks = @(& $dotnet.Source --list-sdks 2>$null)
    return $LASTEXITCODE -eq 0 -and
        @($sdks | Where-Object { $_ -match '^8\.' }).Count -gt 0
}

function Install-WinGetPackage {
    param([Parameter(Mandatory = $true)][string]$Identifier)

    $winget = Get-Command winget.exe -ErrorAction SilentlyContinue
    if (-not $winget) {
        throw 'winget.exe is required for the development profile'
    }
    $wingetOutput = @(& $winget.Source install --id $Identifier --exact --silent `
        --disable-interactivity --accept-source-agreements `
        --accept-package-agreements 2>&1)
    $wingetExitCode = $LASTEXITCODE
    if ($wingetExitCode -ne 0) {
        throw "winget package installation failed with $wingetExitCode"
    }
}

$pythonBefore = Test-Python3
$dotnetBefore = Test-DotNet8Sdk
if (-not $pythonBefore) {
    Install-WinGetPackage -Identifier 'Python.Python.3.13'
}
if (-not $dotnetBefore) {
    Install-WinGetPackage -Identifier 'Microsoft.DotNet.SDK.8'
}

$pythonReady = Test-Python3
$dotnetReady = Test-DotNet8Sdk
$result = [ordered]@{
    schema = 'machine-control-windows-development-bootstrap/v0'
    healthy = $pythonReady -and $dotnetReady
    python_3 = $(if ($pythonReady) { 'available' } else { 'absent' })
    python_installed = -not $pythonBefore -and $pythonReady
    dotnet_8_sdk = $(if ($dotnetReady) { 'available' } else { 'absent' })
    dotnet_installed = -not $dotnetBefore -and $dotnetReady
}
$json = $result | ConvertTo-Json -Compress
if ($ReportPath) {
    $directory = Split-Path -Parent $ReportPath
    New-Item -ItemType Directory -Force -Path $directory | Out-Null
    Set-Content -LiteralPath $ReportPath -Encoding ascii -Value $json
}
$json
if (-not $result.healthy) { exit 1 }
