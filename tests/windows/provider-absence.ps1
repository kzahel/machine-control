[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$Executable,

    [Parameter(Mandatory = $true)]
    [switch]$ConfirmWithholdCua,

    [string]$EvidencePath = (Join-Path $env:TEMP `
        'machine-control-provider-absence.json')
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Invoke-Control {
    param([Parameter(Mandatory = $true)][hashtable]$Request)
    $json = $Request | ConvertTo-Json -Compress -Depth 10
    $raw = $json | & $Executable call
    if ($LASTEXITCODE -ne 0) {
        throw "machine-control call exited with $LASTEXITCODE"
    }
    return $raw | ConvertFrom-Json
}

function Assert-Accepted {
    param($Result, [string]$Label)
    if (-not $Result.accepted) {
        throw "$Label failed: $($Result.errorCode) $($Result.message)"
    }
}

if (-not $ConfirmWithholdCua) {
    throw 'ConfirmWithholdCua is required for this reversible package test'
}

$providerPath = Join-Path (Split-Path -Parent $Executable) `
    'providers\cua\cua-driver.exe'
$withheldPath = "$providerPath.withheld"
$fixturePath = Join-Path (Split-Path -Parent $Executable) `
    'fixtures\machine-control-medium-fixture.exe'
$fixtureHwnd = $null
$withheld = $false
$summary = [ordered]@{
    schema = 'machine-control-provider-absence/v0'
    passed = $false
    provider_state = $null
    attempts = @()
    fallback_route = $null
    package_restored = $false
}

try {
    if (-not (Test-Path -LiteralPath $providerPath)) {
        throw 'the installed pinned Cua executable is already absent'
    }
    Assert-Accepted (Invoke-Control @{ operation = 'service.revoke' }) `
        'pre-withhold revoke'
    Move-Item -LiteralPath $providerPath -Destination $withheldPath
    $withheld = $true

    $launch = Invoke-Control @{
        operation = 'app.launch'
        executablePath = $fixturePath
    }
    Assert-Accepted $launch 'fixture launch without Cua'
    $window = @($launch.data.windows |
        Where-Object { $_.visible -and $_.title -eq 'Machine Control Medium Fixture' } |
        Select-Object -First 1)
    if ($window.Count -ne 1) {
        throw 'fixture did not expose one visible exact window'
    }
    $fixtureHwnd = [long]$window[0].hwnd
    $snapshot = Invoke-Control @{
        operation = 'snapshot'
        hwnd = $fixtureHwnd
        processId = [int]$launch.data.processId
        query = 'Increment counter'
        maxDepth = 10
        maxElements = 40
    }
    Assert-Accepted $snapshot 'native snapshot with Cua withheld'
    if (-not $snapshot.fallbackUsed -or
        $snapshot.actualRoute -notmatch 'windows\.native' -or
        @($snapshot.providerAttempts |
            Where-Object { $_.outcome -eq 'provider_unavailable' }).Count -ne 1) {
        throw 'Cua absence did not produce a disclosed native fallback'
    }
    $capabilities = Invoke-Control @{ operation = 'capabilities' }
    $cua = @($capabilities.data.providers |
        Where-Object { $_.id -eq 'cua' })
    if ($cua.Count -ne 1 -or $cua[0].state -ne 'unavailable') {
        throw 'capabilities did not report the withheld Cua provider unavailable'
    }
    $summary.provider_state = $cua[0].state
    $summary.attempts = @($snapshot.providerAttempts)
    $summary.fallback_route = $snapshot.actualRoute
    $summary.passed = $true
}
finally {
    if ($fixtureHwnd) {
        try {
            Invoke-Control @{
                operation = 'window.state'
                hwnd = $fixtureHwnd
                state = 'closed'
            } | Out-Null
        }
        catch { }
    }
    if ($withheld -and (Test-Path -LiteralPath $withheldPath)) {
        Move-Item -LiteralPath $withheldPath -Destination $providerPath
        $summary.package_restored = $true
    }
    try { Invoke-Control @{ operation = 'service.revoke' } | Out-Null }
    catch { }
    $summary | ConvertTo-Json -Depth 15 |
        Set-Content -LiteralPath $EvidencePath
    $summary | ConvertTo-Json -Depth 15
}
