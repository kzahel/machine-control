[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$Executable,

    [ValidateSet('remote', 'local')]
    [string]$Placement = 'remote',

    [switch]$ExerciseProviderFailure,

    [string]$EvidencePath = (Join-Path $env:TEMP `
        "machine-control-provider-composition-$Placement.json")
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$script:roundTrips = 0

function Invoke-Control {
    param([Parameter(Mandatory = $true)][hashtable]$Request)
    $script:roundTrips++
    $json = $Request | ConvertTo-Json -Compress -Depth 10
    $raw = $json | & $Executable call
    if ($LASTEXITCODE -ne 0) {
        throw "machine-control call exited with $LASTEXITCODE"
    }
    $result = $raw | ConvertFrom-Json
    $result | Add-Member -NotePropertyName '_serializedBytes' `
        -NotePropertyValue ([Text.Encoding]::UTF8.GetByteCount($raw))
    return $result
}

function Assert-Accepted {
    param($Result, [string]$Label)
    if (-not $Result.accepted) {
        throw "$Label failed: $($Result.errorCode) $($Result.message)"
    }
}

function Assert-CuaRoute {
    param($Result, [string]$Label)
    Assert-Accepted $Result $Label
    if ($Result.actualRoute -notmatch '/cua/' -or $Result.fallbackUsed) {
        throw "$Label did not use Cua directly: $($Result.actualRoute)"
    }
}

function Get-Metric {
    param($Result)
    return [ordered]@{
        route = $Result.actualRoute
        provider_attempts = @($Result.providerAttempts)
        payload_bytes = $Result._serializedBytes
        estimated_tokens = [Math]::Max(1, [int]($Result._serializedBytes / 4))
        provider_latency_ms = $Result.providerLatencyMs
        end_to_end_latency_ms = $Result.elapsedMs
        fallback = $Result.fallbackUsed
        retries = $Result.retryCount
        stale_reference_events = $Result.staleReferenceEvents
    }
}

function Stop-CuaDaemon {
    $providerPath = Join-Path (Split-Path -Parent $Executable) `
        'providers\cua\cua-driver.exe'
    $processes = @(Get-CimInstance Win32_Process -Filter "Name='cua-driver.exe'" |
        Where-Object {
            $_.ExecutablePath -eq $providerPath -and
            $_.CommandLine -match '(?i)\sserve\s' -and
            $_.CommandLine -match 'machine-control-cua-'
        })
    if ($processes.Count -ne 1) {
        throw "expected one supervised Cua daemon, found $($processes.Count)"
    }
    $terminated = Invoke-CimMethod -InputObject $processes[0] `
        -MethodName Terminate
    if ($terminated.ReturnValue -ne 0) {
        throw "Cua daemon termination failed with $($terminated.ReturnValue)"
    }
}

$summary = [ordered]@{
    schema = 'machine-control-provider-composition/v0'
    passed = $false
    placement = $Placement
    round_trips = 0
    routes = [ordered]@{}
    effects = [ordered]@{}
    failures = [ordered]@{}
    metrics = [ordered]@{}
    focus_cursor = [ordered]@{}
}
$fixtureHwnd = $null
$fixturePath = Join-Path (Split-Path -Parent $Executable) `
    'fixtures\machine-control-medium-fixture.exe'
$counterPath = Join-Path $env:LOCALAPPDATA `
    'MachineControl\conformance\counter.json'

try {
    Remove-Item -LiteralPath $counterPath -Force -ErrorAction SilentlyContinue
    $beforeStatus = Invoke-Control @{ operation = 'status' }
    Assert-Accepted $beforeStatus 'status before workflow'
    if ($beforeStatus.data.isLocalSystem -or
        $beforeStatus.data.integrityRid -ne 8192) {
        throw 'workflow did not route through the Medium interactive helper'
    }

    $launch = Invoke-Control @{
        operation = 'app.launch'
        executablePath = $fixturePath
    }
    Assert-Accepted $launch 'fixture launch'
    if ($launch.effect -ne 'confirmed') {
        throw 'fixture launch did not independently observe a visible HWND'
    }
    $fixtureWindow = @($launch.data.windows |
        Where-Object { $_.visible -and $_.title -eq 'Machine Control Medium Fixture' } |
        Select-Object -First 1)
    if ($fixtureWindow.Count -ne 1) {
        throw 'fixture launch did not return its expected exact window'
    }
    $fixtureHwnd = [long]$fixtureWindow[0].hwnd
    $fixturePid = [int]$launch.data.processId

    $before = Invoke-Control @{
        operation = 'snapshot'
        hwnd = $fixtureHwnd
        processId = $fixturePid
        query = 'Increment counter'
        maxDepth = 10
        maxElements = 40
    }
    Assert-CuaRoute $before 'Cua fixture snapshot'
    $increment = @($before.data.elements |
        Where-Object { $_.name -eq 'Increment counter' } |
        Select-Object -First 1)
    if ($increment.Count -ne 1 -or -not $increment[0].reference) {
        throw 'Cua snapshot did not return the normalized increment reference'
    }
    $oldReference = $increment[0].reference
    $summary.metrics.snapshot = Get-Metric $before

    $invoke = Invoke-Control @{
        operation = 'invoke'
        reference = $oldReference
        expectedGeneration = $before.generation
    }
    Assert-CuaRoute $invoke 'Cua fixture invoke'
    if ($invoke.effect -ne 'unverifiable' -or
        -not $invoke.evidence.independentEffectRequired) {
        throw 'Cua action improperly treated provider agreement as effect proof'
    }
    $marker = $null
    for ($attempt = 0; $attempt -lt 30 -and -not $marker; $attempt++) {
        Start-Sleep -Milliseconds 100
        if (Test-Path -LiteralPath $counterPath) {
            $candidate = Get-Content -Raw -LiteralPath $counterPath |
                ConvertFrom-Json
            if ($candidate.processId -eq $fixturePid -and
                $candidate.counter -eq 1) {
                $marker = $candidate
            }
        }
    }
    if (-not $marker) {
        throw 'application-owned counter oracle did not confirm the Cua action'
    }
    $summary.effects.counter_transition = 'confirmed_by_application_marker'
    $summary.metrics.invoke = Get-Metric $invoke

    $capture = Invoke-Control @{
        operation = 'screenshot'
        hwnd = $fixtureHwnd
        processId = $fixturePid
    }
    Assert-CuaRoute $capture 'Cua exact-window capture'
    if ($capture.data.bytes -lt 1000 -or -not $capture.data.sha256) {
        throw 'Cua exact-window capture artifact was invalid'
    }
    $summary.metrics.capture = Get-Metric $capture

    $timeoutFallback = Invoke-Control @{
        operation = 'snapshot'
        hwnd = $fixtureHwnd
        processId = $fixturePid
        query = 'Counter value 1'
        maxDepth = 10
        maxElements = 40
        timeoutMs = 1
    }
    Assert-Accepted $timeoutFallback 'bounded observation timeout fallback'
    if (-not $timeoutFallback.fallbackUsed -or
        $timeoutFallback.actualRoute -notmatch 'windows\.native' -or
        @($timeoutFallback.providerAttempts |
            Where-Object { $_.outcome -eq 'provider_timeout' }).Count -ne 1) {
        throw 'bounded Cua timeout did not produce disclosed native fallback'
    }
    $summary.failures.bounded_observation_timeout_fell_back = $true
    $summary.metrics.timeout_fallback = Get-Metric $timeoutFallback

    foreach ($state in @('maximized', 'restored', 'minimized', 'restored')) {
        $stateResult = Invoke-Control @{
            operation = 'window.state'
            hwnd = $fixtureHwnd
            state = $state
        }
        Assert-Accepted $stateResult "fixture $state"
        if ($stateResult.effect -ne 'confirmed' -or
            $stateResult.actualRoute -notmatch 'windows\.native') {
            throw "fixture $state did not use confirmed native state control"
        }
    }
    $summary.routes.window_state = 'windows-native'

    if ($ExerciseProviderFailure) {
        Stop-CuaDaemon
        $staleAfterCrash = Invoke-Control @{
            operation = 'invoke'
            reference = $oldReference
            expectedGeneration = $before.generation
        }
        if ($staleAfterCrash.accepted -or
            $staleAfterCrash.errorCode -ne 'stale_or_unknown_reference') {
            throw 'reference survived a Cua provider-generation restart'
        }
        $summary.failures.provider_restart_invalidated_reference = $true

        $afterRestart = Invoke-Control @{
            operation = 'snapshot'
            hwnd = $fixtureHwnd
            processId = $fixturePid
            query = 'Counter value 1'
            maxDepth = 10
            maxElements = 40
        }
        Assert-CuaRoute $afterRestart 'Cua one-restart recovery'
        $summary.failures.one_restart_recovered = $true
        Stop-CuaDaemon
        $fallback = Invoke-Control @{
            operation = 'snapshot'
            hwnd = $fixtureHwnd
            processId = $fixturePid
            query = 'Counter value 1'
            maxDepth = 10
            maxElements = 40
        }
        Assert-Accepted $fallback 'native fallback after restart exhaustion'
        if (-not $fallback.fallbackUsed -or
            @($fallback.providerAttempts).Count -lt 2 -or
            $fallback.actualRoute -notmatch 'windows\.native') {
            throw 'provider failure did not disclose its native observation fallback'
        }
        $summary.failures.restart_exhaustion_fell_back = $true
        $summary.metrics.failure_fallback = Get-Metric $fallback
    }

    $afterStatus = Invoke-Control @{ operation = 'status' }
    Assert-Accepted $afterStatus 'status after workflow'
    $summary.focus_cursor = [ordered]@{
        foreground_before = $beforeStatus.data.foregroundWindow.hwnd
        foreground_after = $afterStatus.data.foregroundWindow.hwnd
        cursor_before = $beforeStatus.data.cursor
        cursor_after = $afterStatus.data.cursor
        semantic_route_claim = $invoke.focusConsequence
    }

    $close = Invoke-Control @{
        operation = 'window.state'
        hwnd = $fixtureHwnd
        state = 'closed'
    }
    Assert-Accepted $close 'fixture close'
    if ($close.effect -ne 'confirmed') {
        throw 'fixture close did not independently observe the HWND disappear'
    }
    $fixtureHwnd = $null

    if ($Placement -eq 'remote') {
        $revoke = Invoke-Control @{ operation = 'service.revoke' }
        Assert-Accepted $revoke 'service revoke'
        $staleGeneration = Invoke-Control @{
            operation = 'invoke'
            reference = $oldReference
            expectedGeneration = $before.generation
        }
        if ($staleGeneration.accepted -or
            $staleGeneration.errorCode -ne 'stale_generation') {
            throw 'runtime generation revoke did not reject the old reference'
        }
        $recovered = Invoke-Control @{ operation = 'status' }
        Assert-Accepted $recovered 'helper recovery after revoke'
        $summary.failures.runtime_revoke_invalidated_reference = $true
        $summary.failures.helper_recreated = $true
    }
    else {
        # A local caller is a child of the helper generation it is testing.
        # Revocation is proven remotely because it intentionally terminates
        # the local caller's process tree.
        $summary.failures.runtime_revoke = 'remote_only_by_design'
    }

    $summary.routes.snapshot = $before.actualRoute
    $summary.routes.invoke = $invoke.actualRoute
    $summary.routes.capture = $capture.actualRoute
    $summary.round_trips = $script:roundTrips
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
    $summary.round_trips = $script:roundTrips
    $summary | ConvertTo-Json -Depth 20 |
        Set-Content -LiteralPath $EvidencePath
    $summary | ConvertTo-Json -Depth 20
}
