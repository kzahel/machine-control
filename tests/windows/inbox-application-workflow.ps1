[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$Executable,

    [ValidateSet('remote', 'local')]
    [string]$Placement = 'remote',

    [string]$EvidencePath = (Join-Path $env:TEMP `
        "machine-control-inbox-workflow-$Placement.json")
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$script:roundTrips = 0

function Invoke-Control {
    param([Parameter(Mandatory = $true)][hashtable]$Request)
    $script:roundTrips++
    $json = $Request | ConvertTo-Json -Compress -Depth 10
    $started = [Diagnostics.Stopwatch]::StartNew()
    $raw = $json | & $Executable call
    $started.Stop()
    if ($LASTEXITCODE -ne 0) {
        throw "machine-control call exited with $LASTEXITCODE"
    }
    $result = $raw | ConvertFrom-Json
    $result | Add-Member -NotePropertyName '_serializedBytes' `
        -NotePropertyValue ([Text.Encoding]::UTF8.GetByteCount($raw))
    $result | Add-Member -NotePropertyName '_roundTripMs' `
        -NotePropertyValue $started.ElapsedMilliseconds
    return $result
}

function Assert-Accepted {
    param($Result, [string]$Label)
    if (-not $Result.accepted) {
        throw "$Label failed: $($Result.errorCode) $($Result.message)"
    }
}

function Get-Metric {
    param($Result)
    return [ordered]@{
        route = $Result.actualRoute
        payload_bytes = $Result._serializedBytes
        estimated_tokens = [Math]::Max(1, [int]($Result._serializedBytes / 4))
        provider_latency_ms = $Result.providerLatencyMs
        end_to_end_latency_ms = $Result.elapsedMs
        observed_round_trip_ms = $Result._roundTripMs
        fallback = $Result.fallbackUsed
        retries = $Result.retryCount
        delivery = $Result.delivery
        effect = $Result.effect
        focus = $Result.focusConsequence
        cursor = $Result.cursorConsequence
    }
}

function Get-Windows {
    $result = Invoke-Control @{ operation = 'windows' }
    Assert-Accepted $result 'window inventory'
    return @($result.data.windows)
}

function Start-ThroughRun {
    param(
        [Parameter(Mandatory = $true)][string]$CommandLine,
        [Parameter(Mandatory = $true)][string]$Label
    )
    $open = Invoke-Control @{ operation = 'key'; key = 'win+r' }
    Assert-Accepted $open "$Label Run-dialog open"
    Start-Sleep -Milliseconds 250
    $type = Invoke-Control @{ operation = 'type'; text = $CommandLine }
    Assert-Accepted $type "$Label Run command"
    $submit = Invoke-Control @{ operation = 'key'; key = 'enter' }
    Assert-Accepted $submit "$Label Run submit"
    return [pscustomobject]@{
        open = $open
        type = $type
        submit = $submit
    }
}

function Wait-Window {
    param(
        [Parameter(Mandatory = $true)][scriptblock]$Predicate,
        [Parameter(Mandatory = $true)][string]$Label,
        [int]$TimeoutSeconds = 15
    )
    $deadline = [DateTime]::UtcNow.AddSeconds($TimeoutSeconds)
    do {
        $match = @(Get-Windows | Where-Object $Predicate |
            Select-Object -First 1)
        if ($match.Count -eq 1) { return $match[0] }
        Start-Sleep -Milliseconds 250
    } while ([DateTime]::UtcNow -lt $deadline)
    throw "$Label did not expose a visible window within $TimeoutSeconds seconds"
}

function Wait-WindowGone {
    param([long]$Hwnd, [string]$Label, [int]$TimeoutSeconds = 10)
    $deadline = [DateTime]::UtcNow.AddSeconds($TimeoutSeconds)
    do {
        if (@(Get-Windows | Where-Object { $_.hwnd -eq $Hwnd }).Count -eq 0) {
            return
        }
        Start-Sleep -Milliseconds 200
    } while ([DateTime]::UtcNow -lt $deadline)
    throw "$Label HWND remained after close"
}

function Wait-NoMatchingWindow {
    param(
        [Parameter(Mandatory = $true)][scriptblock]$Predicate,
        [Parameter(Mandatory = $true)][string]$Label,
        [int]$TimeoutSeconds = 10
    )
    $deadline = [DateTime]::UtcNow.AddSeconds($TimeoutSeconds)
    $quietObservations = 0
    do {
        $matches = @(Get-Windows | Where-Object $Predicate)
        if ($matches.Count -eq 0) {
            $quietObservations++
            if ($quietObservations -ge 3) { return }
        }
        else {
            $quietObservations = 0
        }
        Start-Sleep -Milliseconds 250
    } while ([DateTime]::UtcNow -lt $deadline)
    throw "$Label remained present; refusing to disturb pre-existing state"
}

function Get-Element {
    param(
        [Parameter(Mandatory = $true)]$Window,
        [Parameter(Mandatory = $true)][string]$Query,
        [Parameter(Mandatory = $true)][string]$Name
    )
    $deadline = [DateTime]::UtcNow.AddSeconds(10)
    do {
        $snapshot = Invoke-Control @{
            operation = 'snapshot'
            hwnd = [long]$Window.hwnd
            processId = [int]$Window.processId
            query = $Query
            maxDepth = 12
            maxElements = 30
        }
        if ($snapshot.accepted -and $snapshot.actualRoute -match '/cua/') {
            $element = @($snapshot.data.elements |
                Where-Object { $_.name -eq $Name } | Select-Object -First 1)
            if ($element.Count -eq 1 -and $element[0].reference) {
                return [pscustomobject]@{
                    snapshot = $snapshot
                    element = $element[0]
                }
            }
        }
        Start-Sleep -Milliseconds 250
    } while ([DateTime]::UtcNow -lt $deadline)
    if (-not $snapshot.accepted) {
        Assert-Accepted $snapshot "snapshot $Name"
    }
    if ($snapshot.actualRoute -notmatch '/cua/') {
        throw "snapshot $Name did not use Cua: $($snapshot.actualRoute)"
    }
    throw "snapshot did not return $Name with a generation-scoped reference"
}

function Invoke-Element {
    param(
        [Parameter(Mandatory = $true)]$Window,
        [Parameter(Mandatory = $true)][string]$Name
    )
    $semantic = Get-Element -Window $Window -Query $Name -Name $Name
    $result = Invoke-Control @{
        operation = 'invoke'
        reference = $semantic.element.reference
        expectedGeneration = $semantic.snapshot.generation
    }
    Assert-Accepted $result "invoke $Name"
    if ($result.actualRoute -notmatch '/cua/' -or $result.fallbackUsed) {
        throw "invoke $Name did not use Cua directly"
    }
    return $result
}

function Get-NamedElements {
    param(
        [Parameter(Mandatory = $true)]$Window,
        [Parameter(Mandatory = $true)][string[]]$Names
    )
    $deadline = [DateTime]::UtcNow.AddSeconds(10)
    do {
        $snapshot = Invoke-Control @{
            operation = 'snapshot'
            hwnd = [long]$Window.hwnd
            processId = [int]$Window.processId
            maxDepth = 16
            maxElements = 180
        }
        if ($snapshot.accepted -and $snapshot.actualRoute -match '/cua/') {
            $missing = @($Names | Where-Object {
                $name = $_
                @($snapshot.data.elements |
                    Where-Object { $_.name -eq $name -and $_.reference }).Count -ne 1
            })
            if ($missing.Count -eq 0) { return $snapshot }
        }
        Start-Sleep -Milliseconds 250
    } while ([DateTime]::UtcNow -lt $deadline)
    throw "Cua snapshot did not expose all required controls: $($Names -join ', ')"
}

function Wait-FileContent {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [Parameter(Mandatory = $true)][string]$Expected,
        [string]$Label,
        [int]$TimeoutSeconds = 10
    )
    $deadline = [DateTime]::UtcNow.AddSeconds($TimeoutSeconds)
    do {
        if (Test-Path -LiteralPath $Path) {
            $actual = Get-Content -Raw -LiteralPath $Path
            if ($actual -eq $Expected) { return }
        }
        Start-Sleep -Milliseconds 200
    } while ([DateTime]::UtcNow -lt $deadline)
    [byte[]]$actualBytes = if (Test-Path -LiteralPath $Path) {
        [IO.File]::ReadAllBytes($Path)
    }
    else { [byte[]]@() }
    $actualDigest = if (Test-Path -LiteralPath $Path) {
        (Get-FileHash -Algorithm SHA256 -LiteralPath $Path).Hash.ToLowerInvariant()
    }
    else { 'absent' }
    throw "$Label did not produce the expected file bytes " +
        "(expected_bytes=$([Text.Encoding]::UTF8.GetByteCount([string]$Expected)), " +
        "actual_bytes=$(@($actualBytes).Count), " +
        "actual_sha256=$actualDigest)"
}

function Normalize-Text {
    param([AllowEmptyString()][string]$Value)
    return ($Value -replace "`r`n", "`n") -replace "`r", "`n"
}

function Close-Window {
    param($Window, [string]$Label)
    if (-not $Window) { return }
    $result = Invoke-Control @{
        operation = 'window.state'
        hwnd = [long]$Window.hwnd
        state = 'closed'
    }
    Assert-Accepted $result "$Label close"
    Wait-WindowGone -Hwnd ([long]$Window.hwnd) -Label $Label
}

$summary = [ordered]@{
    schema = 'machine-control-inbox-application-workflow/v0'
    passed = $false
    placement = $Placement
    round_trips = 0
    applications = [ordered]@{}
    metrics = [ordered]@{}
    cleanup = [ordered]@{}
    error = $null
}
$workflowError = $null
$calculator = $null
$notepad = $null
$capturePaths = [Collections.Generic.List[string]]::new()
$workflowRoot = Join-Path $env:LOCALAPPDATA 'MachineControl\workflow'
$documentName = "machine-control-inbox-$Placement.txt"
$documentPath = Join-Path $workflowRoot $documentName
$firstContent = "MachineControl inbox workflow $Placement`r`nphase one"
$secondContent = "MachineControl inbox workflow $Placement`r`nphase two"

try {
    Wait-NoMatchingWindow `
        -Predicate { $_.visible -and $_.title -eq 'Calculator' } `
        -Label 'a pre-existing Calculator window'
    if (Test-Path -LiteralPath $documentPath) {
        throw 'workflow document already exists; refusing to overwrite it'
    }

    New-Item -ItemType Directory -Force -Path $workflowRoot | Out-Null
    New-Item -ItemType File -Path $documentPath | Out-Null

    $calcLaunch = Start-ThroughRun -CommandLine 'calc' -Label 'Calculator'
    $calculator = Wait-Window `
        -Predicate { $_.visible -and $_.title -eq 'Calculator' } `
        -Label 'Calculator'
    $calcMetrics = [ordered]@{
        launch = Get-Metric $calcLaunch.submit
        launch_route = 'Windows Run via target-local facade input'
    }
    $calculatorControlNames = @('Seven', 'Multiply by', 'Eight', 'Equals')
    $calculatorControls = Get-NamedElements `
        -Window $calculator -Names $calculatorControlNames
    $calcMetrics.semantic_snapshot = Get-Metric $calculatorControls
    foreach ($name in $calculatorControlNames) {
        $element = @($calculatorControls.data.elements |
            Where-Object { $_.name -eq $name } | Select-Object -First 1)[0]
        $action = Invoke-Control @{
            operation = 'invoke'
            reference = $element.reference
            expectedGeneration = $calculatorControls.generation
        }
        Assert-Accepted $action "invoke $name"
        if ($action.actualRoute -notmatch '/cua/' -or $action.fallbackUsed) {
            throw "invoke $name did not use Cua directly"
        }
        $calcMetrics[$name.ToLowerInvariant().Replace(' ', '_')] =
            Get-Metric $action
        Start-Sleep -Milliseconds 100
    }

    $display = Invoke-Control @{
        operation = 'snapshot'
        scope = 'system'
        hwnd = [long]$calculator.hwnd
        processId = [int]$calculator.processId
        query = 'Display is 56'
        maxDepth = 12
        maxElements = 20
    }
    Assert-Accepted $display 'independent Calculator display observation'
    if ($display.actualRoute -notmatch 'windows\.native' -or
        @($display.data.elements |
            Where-Object { $_.name -eq 'Display is 56' }).Count -ne 1) {
        throw 'native UIA did not independently observe Calculator display 56'
    }
    $calcMetrics.display = Get-Metric $display

    $calcCapture = Invoke-Control @{
        operation = 'screenshot'
        hwnd = [long]$calculator.hwnd
        processId = [int]$calculator.processId
    }
    Assert-Accepted $calcCapture 'Calculator exact-window capture'
    if ($calcCapture.data.bytes -lt 1000 -or -not $calcCapture.data.sha256) {
        throw 'Calculator exact-window capture was invalid'
    }
    if ($calcCapture.data.targetLocalPath) {
        $capturePaths.Add($calcCapture.data.targetLocalPath)
    }
    $calcMetrics.capture = Get-Metric $calcCapture
    foreach ($state in @('maximized', 'restored', 'minimized', 'restored')) {
        $stateResult = Invoke-Control @{
            operation = 'window.state'
            hwnd = [long]$calculator.hwnd
            state = $state
        }
        Assert-Accepted $stateResult "Calculator $state"
        if ($stateResult.effect -ne 'confirmed') {
            throw "Calculator $state lacked an independent state readback"
        }
    }
    $summary.applications.calculator = [ordered]@{
        effect = '56 observed through independent native UIA'
        transitions = 4
        exact_window_capture = $true
        window_lifecycle = 'confirmed'
    }
    $summary.metrics.calculator = $calcMetrics
    Close-Window -Window $calculator -Label 'Calculator'
    $calculator = $null

    $notepadLaunch = Start-ThroughRun `
        -CommandLine ('notepad.exe "{0}"' -f $documentPath) `
        -Label 'Notepad'
    $notepad = Wait-Window `
        -Predicate { $_.visible -and $_.title -like "*$documentName*" } `
        -Label 'workflow Notepad tab'
    $notepadMetrics = [ordered]@{
        launch = Get-Metric $notepadLaunch.submit
        launch_route = 'Windows Run via target-local facade input'
    }

    $setFirst = Invoke-Control @{
        operation = 'set.value'
        scope = 'system'
        hwnd = [long]$notepad.hwnd
        processId = [int]$notepad.processId
        query = 'Text editor'
        text = $firstContent
    }
    Assert-Accepted $setFirst 'set first Notepad content'
    if ($setFirst.actualRoute -notmatch 'windows\.native/uia_value_pattern' -or
        $setFirst.effect -ne 'confirmed') {
        throw 'Notepad first semantic value did not confirm exact readback'
    }
    $save = Invoke-Control @{ operation = 'key'; key = 'ctrl+s' }
    Assert-Accepted $save 'save first Notepad content'
    Wait-FileContent -Path $documentPath -Expected $firstContent `
        -Label 'first Notepad save'
    $notepadMetrics.first_set = Get-Metric $setFirst
    $notepadMetrics.first_save = Get-Metric $save

    $notepadCapture = Invoke-Control @{
        operation = 'screenshot'
        hwnd = [long]$notepad.hwnd
        processId = [int]$notepad.processId
    }
    Assert-Accepted $notepadCapture 'Notepad exact-window capture'
    if ($notepadCapture.data.bytes -lt 1000 -or
        -not $notepadCapture.data.sha256) {
        throw 'Notepad exact-window capture was invalid'
    }
    if ($notepadCapture.data.targetLocalPath) {
        $capturePaths.Add($notepadCapture.data.targetLocalPath)
    }
    $notepadMetrics.capture = Get-Metric $notepadCapture
    Close-Window -Window $notepad -Label 'Notepad first instance'
    $notepad = $null

    $reopen = Start-ThroughRun `
        -CommandLine ('notepad.exe "{0}"' -f $documentPath) `
        -Label 'Notepad reopen'
    $notepad = Wait-Window `
        -Predicate { $_.visible -and $_.title -like "*$documentName*" } `
        -Label 'reopened workflow Notepad tab'
    $readback = Get-Element -Window $notepad `
        -Query 'Text editor' -Name 'Text editor'
    if ((Normalize-Text $readback.element.value) -ne
        (Normalize-Text $firstContent)) {
        throw 'Notepad semantic readback did not match the saved first content'
    }
    $setSecond = Invoke-Control @{
        operation = 'set.value'
        scope = 'system'
        hwnd = [long]$notepad.hwnd
        processId = [int]$notepad.processId
        query = 'Text editor'
        text = $secondContent
    }
    Assert-Accepted $setSecond 'set second Notepad content'
    if ($setSecond.effect -ne 'confirmed') {
        throw 'Notepad second semantic value did not confirm exact readback'
    }
    $resave = Invoke-Control @{ operation = 'key'; key = 'ctrl+s' }
    Assert-Accepted $resave 'save second Notepad content'
    Wait-FileContent -Path $documentPath -Expected $secondContent `
        -Label 'second Notepad save'
    $notepadMetrics.reopen = Get-Metric $reopen.submit
    $notepadMetrics.second_set = Get-Metric $setSecond
    $notepadMetrics.second_save = Get-Metric $resave
    $summary.applications.notepad = [ordered]@{
        first_save = 'confirmed by exact filesystem bytes'
        reopen_readback = 'confirmed by Cua document value'
        second_save = 'confirmed by changed exact filesystem bytes'
        exact_window_capture = $true
        window_lifecycle = 'confirmed'
    }
    $summary.metrics.notepad = $notepadMetrics
    Close-Window -Window $notepad -Label 'Notepad reopened instance'
    $notepad = $null

    $summary.passed = $true
}
catch {
    $workflowError = $_
    $summary.error = $_.Exception.Message
}
finally {
    if ($calculator) {
        try {
            Close-Window -Window $calculator -Label 'Calculator cleanup'
            $calculator = $null
        }
        catch { }
    }
    if ($notepad) {
        try {
            Close-Window -Window $notepad -Label 'Notepad cleanup'
            $notepad = $null
        }
        catch { }
    }
    foreach ($capturePath in $capturePaths) {
        Remove-Item -LiteralPath $capturePath -Force -ErrorAction SilentlyContinue
    }
    Remove-Item -LiteralPath $documentPath -Force -ErrorAction SilentlyContinue
    if ((Test-Path -LiteralPath $workflowRoot) -and
        @(Get-ChildItem -LiteralPath $workflowRoot -Force).Count -eq 0) {
        Remove-Item -LiteralPath $workflowRoot -Force -ErrorAction SilentlyContinue
    }
    $summary.round_trips = $script:roundTrips
    $summary.cleanup = [ordered]@{
        application_windows_closed = (-not $calculator -and -not $notepad)
        document_removed = (-not (Test-Path -LiteralPath $documentPath))
        captures_removed = @($capturePaths |
            Where-Object { Test-Path -LiteralPath $_ }).Count -eq 0
    }
    $summary | ConvertTo-Json -Depth 20 |
        Set-Content -LiteralPath $EvidencePath
    $summary | ConvertTo-Json -Depth 20
}
if ($workflowError) { throw $workflowError }
