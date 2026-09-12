[CmdletBinding()]
param([Parameter(Mandatory=$true)][string]$Package)
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
$setup=Join-Path (Resolve-Path $Package).Path 'unlock-setup.exe'
$instance='ci-unlock-smoke'
$service="MachineControlUnlock_$instance"
$root=Join-Path $env:ProgramFiles "MachineControlUnlock\$instance"
$state=Join-Path $env:ProgramData "MachineControlUnlock\$instance"
if ((Get-Service $service -ErrorAction SilentlyContinue) -or (Test-Path $root)) {throw 'Smoke instance already exists'}
function Setup([string]$Action) {
    $process=Start-Process $setup -ArgumentList "$Action $instance" -PassThru
    if (-not $process.WaitForExit(120000)) { $process.Kill(); throw "Setup $Action timed out" }
    if ($process.ExitCode -ne 0) {throw "Setup $Action failed: $($process.ExitCode)"}
}
try {
    Setup 'Install'
    if ((Get-Service $service).Status -ne 'Running' -or (Test-Path (Join-Path $state 'grant.json'))) {throw 'Installation must start unarmed'}
    $status=& (Join-Path $root 'machine-control-windows.exe') unlock --status --instance $instance | ConvertFrom-Json
    if ($LASTEXITCODE -ne 0 -or $status.stage -ne 'status') {throw 'Unarmed service status was refused'}
    if ($status.state -ne 'unarmed_or_invalid') {throw 'Unarmed service status failed'}
} finally {
    if (Test-Path $root) { Setup 'Uninstall' }
}
if ((Get-Service $service -ErrorAction SilentlyContinue) -or (Test-Path $root) -or (Test-Path $state)) {throw 'Uninstall left instance state'}
Write-Output 'Signed native install, unarmed service and uninstall passed'
