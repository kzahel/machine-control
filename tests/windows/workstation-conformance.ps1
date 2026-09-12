[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$Executable,
    [Parameter(Mandatory = $true)][string]$Fixture,
    [string]$Instance = 'candidate',
    [int]$SessionId = 1,
    [string]$EvidencePath = (Join-Path $env:TEMP 'workstation-conformance.json')
)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
function Call([hashtable]$Request) {
    $text = $Request | ConvertTo-Json -Compress -Depth 10
    $raw = $text | & $Executable call --profile user --instance $Instance --session-id $SessionId
    if ($LASTEXITCODE -ne 0) { throw 'User client failed' }
    return $raw | ConvertFrom-Json
}
function Accepted($Result) {
    if (-not $Result.accepted) { throw "$($Result.operation): $($Result.errorCode) $($Result.message)" }
    return $Result
}
$window = $null
$capturePath = $null
$summary = [ordered]@{ schema = 'machine-control-workstation-conformance/v0'; passed = $false }
try {
    $status = Accepted (Call @{ operation = 'status' })
    if ($status.data.profile -ne 'workstation' -or $status.data.instance -ne $Instance -or
        $status.data.integrityRid -ne 8192 -or -not $status.data.ready) { throw 'Wrong runtime/profile/privilege' }
    $cap = Accepted (Call @{ operation = 'capabilities' })
    if ($cap.data.protectedDesktop.available -or @($cap.data.serviceOperations).Count) { throw 'Protected capability leak' }
    foreach ($provider in $cap.data.providers) {
        foreach ($operation in $provider.operations) {
            if ('Winlogon' -in $operation.desktops -or 'Consent' -in $operation.desktops) { throw 'Protected provider capability leak' }
        }
    }
    foreach ($operation in @('service.status', 'service.revoke', 'session.login', 'session.logoff', 'session.lock')) {
        $refusal = Call @{ operation = $operation }
        if ($refusal.accepted -or $refusal.errorCode -ne 'unsupported_operation' -or $refusal.delivery -ne 'refused') {
            throw "Protected operation was not refused: $operation"
        }
    }
    $stale = Call @{ operation = 'key'; key = 'A'; expectedGeneration = 'expired-generation' }
    if ($stale.accepted -or $stale.errorCode -ne 'stale_generation') { throw 'Stale mutation was not fenced' }
    $stop = Call @{ operation = 'runtime.stop' }
    if ($stop.accepted -or $stop.errorCode -ne 'generation_required') { throw 'Unfenced stop was accepted' }
    $launch = Accepted (Call @{ operation = 'app.launch'; executablePath = $Fixture; expectedGeneration = $status.generation })
    $window = @($launch.data.windows | Where-Object { $_.visible -and $_.title -eq 'Machine Control Medium Fixture' } | Select-Object -First 1)
    if ($window.Count -ne 1) { throw 'Expected one fixture window' }
    $hwnd = [long]$window[0].hwnd
    $fixtureProcess = [int]$launch.data.processId
    $snapshot = Accepted (Call @{ operation = 'snapshot'; hwnd = $hwnd; processId = $fixtureProcess; maxDepth = 10; maxElements = 40 })
    $button = @($snapshot.data.elements | Where-Object { $_.name -eq 'Increment counter' } | Select-Object -First 1)
    if ($button.Count -ne 1) { throw 'Missing fixture button' }
    $null = Accepted (Call @{ operation = 'invoke'; reference = $button[0].reference; expectedGeneration = $status.generation })
    $markerPath = Join-Path $env:LOCALAPPDATA 'MachineControl\conformance\counter.json'
    $effect = $false
    for ($i = 0; $i -lt 30; $i++) {
        if (Test-Path -LiteralPath $markerPath) {
            $marker = Get-Content -LiteralPath $markerPath -Raw | ConvertFrom-Json
            if ($marker.processId -eq $fixtureProcess -and $marker.counter -eq 1) { $effect = $true; break }
        }
        Start-Sleep -Milliseconds 100
    }
    if (-not $effect) { throw 'Independent application marker did not confirm effect' }
    $capture = Accepted (Call @{ operation = 'screenshot'; hwnd = $hwnd; processId = $fixtureProcess })
    $capturePath = Join-Path $status.data.artifactRoot ($capture.data.artifactId + '.png')
    $bytes = [IO.File]::ReadAllBytes($capturePath)
    if ($bytes.Length -lt 1000 -or [BitConverter]::ToString($bytes[0..7]) -ne '89-50-4E-47-0D-0A-1A-0A') { throw 'Invalid PNG artifact' }
    if ((Get-FileHash -LiteralPath $capturePath -Algorithm SHA256).Hash.ToLowerInvariant() -ne $capture.data.sha256) { throw 'Artifact digest mismatch' }
    $summary.profile = $status.data.profile
    $summary.generation = $status.generation
    $summary.snapshotRoute = $snapshot.actualRoute
    $summary.captureRoute = $capture.actualRoute
    $summary.independentCounterEffect = $effect
    $summary.protectedRefusals = $true
    $summary.passed = $true
} finally {
    if ($window) { $null = Call @{ operation = 'window.state'; hwnd = [long]$window[0].hwnd; state = 'closed' } }
    if ($capturePath -and (Test-Path -LiteralPath $capturePath)) { Remove-Item -LiteralPath $capturePath }
    $summary | ConvertTo-Json -Depth 10 | Set-Content -LiteralPath $EvidencePath
    $summary | ConvertTo-Json -Depth 10
}
