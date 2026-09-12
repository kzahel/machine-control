[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$Package,
    [Parameter(Mandatory = $true)][string]$ExpectedPublisher,
    [string]$EvidencePath = (Join-Path $env:TEMP 'workstation-package-trust.json')
)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$instance = 'trust-' + [Guid]::NewGuid().ToString('n')
$copy = Join-Path $env:TEMP $instance
$management = Join-Path $env:LOCALAPPDATA "MachineControl\packages\$instance"
if ((Test-Path $copy) -or (Test-Path $management)) { throw 'Trust fixture already exists' }
$summary = [ordered]@{ schema = 'machine-control-workstation-package-trust/v0'; passed = $false }
try {
    Copy-Item -LiteralPath $Package -Destination $copy -Recurse
    $readme = Join-Path $copy 'README.md'
    [IO.File]::AppendAllText($readme, "`ncontrolled-tamper-marker`n")
    # Forge the ordinary hash inventory too: only the signed catalog should
    # prevent this otherwise internally consistent payload from activating.
    $manifestPath = Join-Path $copy 'package.json'
    $manifest = Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json
    $manifest.files.'README.md' = (Get-FileHash -LiteralPath $readme -Algorithm SHA256).Hash.ToLowerInvariant()
    $manifest | ConvertTo-Json -Depth 30 | Set-Content -LiteralPath $manifestPath
    $refused = $false
    try {
        & (Join-Path $Package 'workstation.ps1') -Action Install -Instance $instance -Package $copy -ExpectedPublisher $ExpectedPublisher | Out-Null
    } catch {
        if ($_.Exception.Message -notmatch 'Signed catalog does not authenticate') { throw }
        $refused = $true
    }
    if (-not $refused -or (Test-Path (Join-Path $management 'active.json'))) {
        throw 'Forged inventory activated a tampered package'
    }
    $summary.catalogRejectedForgedInventory = $true
    $summary.passed = $true
} finally {
    if (Test-Path $copy) { Remove-Item -LiteralPath $copy -Recurse -Force }
    if (Test-Path $management) { Remove-Item -LiteralPath $management -Recurse -Force }
    $summary | ConvertTo-Json | Set-Content -LiteralPath $EvidencePath
    $summary | ConvertTo-Json
}
