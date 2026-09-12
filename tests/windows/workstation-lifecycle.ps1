[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$PackageA,
    [Parameter(Mandatory = $true)][string]$PackageB,
    [string]$ExpectedPublisher,
    [switch]$AllowUnsigned,
    [string]$EvidencePath = (Join-Path $env:TEMP 'workstation-lifecycle.json')
)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$first = 'lifecycle-' + [Guid]::NewGuid().ToString('n')
$second = 'lifecycle-' + [Guid]::NewGuid().ToString('n')
$manager = Join-Path $PackageB 'workstation.ps1'
$trust = @{ ExpectedPublisher = $ExpectedPublisher; AllowUnsigned = $AllowUnsigned }
$installed = [Collections.Generic.List[string]]::new()
$running = [Collections.Generic.List[string]]::new()
$summary = [ordered]@{ schema = 'machine-control-workstation-lifecycle/v0'; passed = $false }
function Manage([string]$Action, [string]$Instance, [string]$Package = $PackageB) {
    $raw = & $manager -Action $Action -Instance $Instance -Package $Package @trust
    return $raw | ConvertFrom-Json
}
try {
    $summary.step = 'install first package'
    $a = Manage Install $first $PackageA
    $installed.Add($first)
    $summary.step = 'start first package'
    $statusA = Manage Start $first
    $running.Add($first)
    $summary.step = 'refuse running upgrade'
    $refused = $false
    try { $null = Manage Install $first $PackageB } catch { $refused = $true }
    if (-not $refused) { throw 'Upgrade while running was accepted' }
    $null = Manage Stop $first
    $null = $running.Remove($first)
    $summary.step = 'install second package'
    $b = Manage Install $first $PackageB
    if ($a.packageId -eq $b.packageId) { throw 'Lifecycle test needs different packages' }
    $statusB = Manage Start $first
    $running.Add($first)
    if ($statusA.generation -eq $statusB.generation) { throw 'Restart reused generation' }
    $root = Join-Path $env:LOCALAPPDATA "MachineControl\packages\$first"
    $exe = Join-Path $root ("versions\" + $b.packageId + '\machine-control-windows.exe')
    $request = @{ operation = 'key'; key = 'A'; expectedGeneration = $statusA.generation } | ConvertTo-Json -Compress
    $stale = $request | & $exe call --profile user --instance $first | ConvertFrom-Json
    if ($stale.accepted -or $stale.errorCode -ne 'stale_generation') { throw 'Old generation crossed upgrade' }
    $null = Manage Stop $first
    $null = $running.Remove($first)
    $rollback = Manage Rollback $first
    if ($rollback.active -ne $a.packageId) { throw 'Rollback selected wrong version' }
    $null = Manage Start $first
    $running.Add($first)
    $null = Manage Install $second $PackageB
    $installed.Add($second)
    $other = Manage Start $second
    $running.Add($second)
    if ($other.data.instance -ne $second) { throw 'Second instance resolved wrong endpoint' }
    $null = Manage Stop $first
    $null = $running.Remove($first)
    $null = Manage Uninstall $first
    $null = $installed.Remove($first)
    $stillRunning = Manage Status $second
    if ($stillRunning.generation -ne $other.generation) { throw 'First removal affected second instance' }
    if (Test-Path (Join-Path $root 'active.json')) { throw 'Uninstall retained active selection' }
    $summary.upgrade = $true
    $summary.rollback = $true
    $summary.staleGenerationRefused = $true
    $summary.instanceIsolation = $true
    $summary.passed = $true
} catch {
    $summary.error = $_.Exception.Message
    throw
} finally {
    foreach ($instance in @($running)) { $null = Manage Stop $instance }
    foreach ($instance in @($installed)) { $null = Manage Uninstall $instance }
    $summary | ConvertTo-Json | Set-Content -LiteralPath $EvidencePath
    $summary | ConvertTo-Json
}
