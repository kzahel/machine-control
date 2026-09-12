[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$Executable,
    [Parameter(Mandatory = $true)][string]$Fixture,
    [string]$Instance = 'candidate',
    [int]$SessionId = 1,
    [ValidateRange(0, 120)][int]$IdleSeconds = 0,
    [switch]$ExerciseProviderFailure,
    [switch]$KeepCapture,
    [string]$EvidencePath = (Join-Path $env:TEMP 'workstation-conformance.json')
)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
function Call([hashtable]$Request) {
    $text = $Request | ConvertTo-Json -Compress -Depth 10
    $raw = $text | & $Executable call --profile user --instance $Instance --session-id $SessionId
    if ($LASTEXITCODE -ne 0) { throw "User client failed for $($Request.operation), exit $LASTEXITCODE" }
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
    if ($snapshot.actualRoute -notmatch '/cua/' -or $snapshot.fallbackUsed) {
        throw "The packaged Cua provider did not supply the fixture snapshot: $($snapshot.providerAttempts | ConvertTo-Json -Compress -Depth 10)"
    }
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
    if ($capture.actualRoute -notmatch '/cua/' -or $capture.fallbackUsed) {
        throw 'The packaged Cua provider did not supply the fixture capture'
    }
    $capturePath = Join-Path $status.data.artifactRoot ($capture.data.artifactId + '.png')
    $bytes = [IO.File]::ReadAllBytes($capturePath)
    if ($bytes.Length -lt 1000 -or [BitConverter]::ToString($bytes[0..7]) -ne '89-50-4E-47-0D-0A-1A-0A') { throw 'Invalid PNG artifact' }
    if ((Get-FileHash -LiteralPath $capturePath -Algorithm SHA256).Hash.ToLowerInvariant() -ne $capture.data.sha256) { throw 'Artifact digest mismatch' }
    if ($IdleSeconds -gt 0) {
        # The launcher must set CUA_DRIVER_RS_SESSION_IDLE_TTL_SECS below
        # this interval. Upstream's maintenance sweep runs every 30 seconds.
        Start-Sleep -Seconds $IdleSeconds
        $expired = Call @{ operation = 'invoke'; reference = $button[0].reference; expectedGeneration = $status.generation }
        if ($expired.accepted -or $expired.errorCode -ne 'stale_or_unknown_reference') {
            throw 'Expired session action was not refused without replay'
        }
        $fresh = Accepted (Call @{ operation = 'snapshot'; hwnd = $hwnd; processId = $fixtureProcess; maxDepth = 10; maxElements = 40 })
        if ($fresh.actualRoute -notmatch '/cua/' -or $fresh.fallbackUsed) { throw 'Fresh observation did not recover the idle session' }
        $old = Call @{ operation = 'invoke'; reference = $button[0].reference; expectedGeneration = $status.generation }
        if ($old.accepted -or $old.errorCode -ne 'stale_or_unknown_reference') { throw 'Revived session accepted an old reference' }
        $button = @($fresh.data.elements | Where-Object name -eq 'Increment counter' | Select-Object -First 1)
        if ($button.Count -ne 1) { throw 'Revived session lost fixture semantics' }
        $null = Accepted (Call @{ operation = 'invoke'; reference = $button[0].reference; expectedGeneration = $status.generation })
        $marker = Get-Content -LiteralPath $markerPath -Raw | ConvertFrom-Json
        if ($marker.processId -ne $fixtureProcess -or $marker.counter -ne 2) { throw 'Revived session did not produce exactly one new effect' }
        $summary.idleActionRefusedWithoutReplay = $true
        $summary.idleObservationRecovered = $true
        $summary.revivedSessionInvalidatedReferences = $true
    }
    if ($ExerciseProviderFailure) {
        $providerPath = Join-Path (Split-Path -Parent $Executable) 'providers\cua\cua-driver.exe'
        $withheldPath = $providerPath + '.withheld'
        if (Test-Path -LiteralPath $withheldPath) { throw 'Provider withholding fixture already exists' }
        $daemon = @(Get-CimInstance Win32_Process | Where-Object {
            $_.Name -eq 'cua-driver.exe' -and $_.ExecutablePath -eq $providerPath -and
            $_.CommandLine -match 'machine-control-cua-'
        })
        if ($daemon.Count -ne 1) { throw 'Expected the selected instance to own one Cua daemon' }
        $terminated = Invoke-CimMethod -InputObject $daemon[0] -MethodName Terminate
        if ($terminated.ReturnValue -ne 0) { throw 'Could not terminate the selected Cua daemon' }
        $staleProvider = Call @{ operation = 'invoke'; reference = $button[0].reference; expectedGeneration = $status.generation }
        if ($staleProvider.accepted -or $staleProvider.errorCode -ne 'stale_or_unknown_reference') {
            throw 'Crashed provider retained an actionable reference'
        }
        $recovered = Accepted (Call @{ operation = 'snapshot'; hwnd = $hwnd; processId = $fixtureProcess; maxDepth = 10; maxElements = 40 })
        if ($recovered.actualRoute -notmatch '/cua/' -or $recovered.fallbackUsed) { throw 'Provider did not recover once' }
        $daemon = @(Get-CimInstance Win32_Process | Where-Object {
            $_.Name -eq 'cua-driver.exe' -and $_.ExecutablePath -eq $providerPath -and
            $_.CommandLine -match 'machine-control-cua-'
        })
        if ($daemon.Count -ne 1) { throw 'Expected one recovered Cua daemon' }
        $terminated = Invoke-CimMethod -InputObject $daemon[0] -MethodName Terminate
        if ($terminated.ReturnValue -ne 0) { throw 'Could not terminate recovered Cua daemon' }
        try {
            Move-Item -LiteralPath $providerPath -Destination $withheldPath
            $fallback = Accepted (Call @{ operation = 'snapshot'; hwnd = $hwnd; processId = $fixtureProcess; maxDepth = 10; maxElements = 40 })
            if (-not $fallback.fallbackUsed -or $fallback.actualRoute -notmatch 'windows\.native') {
                throw 'Unavailable provider did not disclose native fallback'
            }
            $unavailable = Accepted (Call @{ operation = 'capabilities' })
            $cua = @($unavailable.data.providers | Where-Object id -eq 'cua')
            if ($cua.Count -ne 1 -or $cua[0].state -ne 'unavailable') { throw 'Absent provider capability was inaccurate' }
        } finally {
            if (Test-Path -LiteralPath $withheldPath) { Move-Item -LiteralPath $withheldPath -Destination $providerPath }
        }
        $summary.providerCrashInvalidatedReference = $true
        $summary.providerRecoveredOnce = $true
        $summary.missingProviderDisclosedFallback = $true
    }
    # Exercise disconnected and malformed clients on the real user endpoint.
    $sid = [Security.Principal.WindowsIdentity]::GetCurrent().User.Value
    $pipeName = "machine-control-user-$sid-$SessionId-$Instance"
    foreach ($payload in @('', "{invalid-json}`n")) {
        $pipe = [IO.Pipes.NamedPipeClientStream]::new('.', $pipeName, [IO.Pipes.PipeDirection]::InOut)
        try {
            $pipe.Connect(3000)
            if ($payload) {
                $bytes = [Text.Encoding]::UTF8.GetBytes($payload)
                $pipe.Write($bytes, 0, $bytes.Length)
                $pipe.Flush()
            }
        } finally { $pipe.Dispose() }
        $afterDisconnect = Accepted (Call @{ operation = 'status' })
        if ($afterDisconnect.generation -ne $status.generation) { throw 'Interrupted IPC restarted the resident' }
    }
    $summary.interruptedIpcPreservedGeneration = $true
    $summary.profile = $status.data.profile
    $summary.generation = $status.generation
    $summary.snapshotRoute = $snapshot.actualRoute
    $summary.captureRoute = $capture.actualRoute
    $summary.captureArtifactId = $capture.data.artifactId
    $summary.independentCounterEffect = $effect
    $summary.protectedRefusals = $true
    $summary.passed = $true
} finally {
    if ($window) { $null = Call @{ operation = 'window.state'; hwnd = [long]$window[0].hwnd; state = 'closed' } }
    if (-not $KeepCapture -and $capturePath -and (Test-Path -LiteralPath $capturePath)) { Remove-Item -LiteralPath $capturePath }
    $summary | ConvertTo-Json -Depth 10 | Set-Content -LiteralPath $EvidencePath
    $summary | ConvertTo-Json -Depth 10
}
