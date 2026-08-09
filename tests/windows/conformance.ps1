[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$Executable,

    [string]$EvidencePath = (Join-Path $env:TEMP 'machine-control-conformance.json')
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Invoke-Control {
    param([Parameter(Mandatory = $true)][hashtable]$Request)
    $json = $Request | ConvertTo-Json -Compress -Depth 8
    $text = $json | & $Executable call
    if ($LASTEXITCODE -ne 0) {
        throw "machine-control call exited with $LASTEXITCODE"
    }
    return $text | ConvertFrom-Json
}

function Assert-Accepted {
    param($Result, [string]$Label)
    if (-not $Result.accepted) {
        throw "$Label failed: $($Result.errorCode) $($Result.message)"
    }
}

function Assert-Elements {
    param($Result, [string]$Label)
    Assert-Accepted $Result $Label
    if (@($Result.data.elements).Count -lt 1) {
        throw "$Label returned no semantic elements"
    }
}

function Metric {
    param($Result)
    return [ordered]@{
        elements = $Result.data.count
        visited = $Result.data.visited
        bytes = $Result.data.serializedBytes
        estimated_tokens = $Result.data.estimatedTokens
        latency_ms = $Result.elapsedMs
    }
}

$summary = [ordered]@{
    schema = 'machine-control-conformance/v0'
    passed = $false
    ordinary_integrity_rid = $null
    shell = [ordered]@{}
    metrics = [ordered]@{}
    lifecycle = [ordered]@{}
}
$baselineWindowHandles = @()
$createdWindowHandles = [System.Collections.Generic.List[long]]::new()

try {
    $capabilities = Invoke-Control @{ operation = 'capabilities' }
    Assert-Accepted $capabilities 'capabilities'

    $status = Invoke-Control @{ operation = 'status' }
    Assert-Accepted $status 'ordinary status'
    if ($status.desktop -ne 'Default' -or $status.data.isLocalSystem) {
        throw 'ordinary status did not use the Medium user-session plane'
    }
    $summary.ordinary_integrity_rid = $status.data.integrityRid

    $baselineWindows = Invoke-Control @{
        operation = 'windows'
        scope = 'system'
        maxElements = 1000
    }
    Assert-Accepted $baselineWindows 'baseline window inventory'
    $baselineWindowHandles = @($baselineWindows.data.windows | ForEach-Object {
        [long]$_.hwnd
    })

    $start = Invoke-Control @{
        operation = 'snapshot'
        scope = 'system'
        target = 'taskbar'
        query = 'Start'
        maxDepth = 10
        maxElements = 40
    }
    Assert-Elements $start 'Start projection'
    $summary.metrics.start = Metric $start
    $startAction = @($start.data.elements |
        Where-Object {
            $_.name -eq 'Start' -and
            ($_.patterns -join ' ') -match 'InvokePattern|TogglePattern'
        } |
        Select-Object -First 1)
    if ($startAction.Count -ne 1) {
        throw 'Start projection did not expose an actionable semantic element'
    }
    $startRef = $startAction[0].reference
    $openedStart = Invoke-Control @{
        operation = 'invoke'
        scope = 'system'
        target = 'taskbar'
        reference = $startRef
        expectedGeneration = $start.generation
    }
    Assert-Accepted $openedStart 'Start reference invoke'
    Start-Sleep -Milliseconds 500
    $startMenu = Invoke-Control @{
        operation = 'snapshot'
        scope = 'system'
        target = 'foreground'
        query = 'Search box'
        maxDepth = 12
        maxElements = 50
    }
    if (@($startMenu.data.elements).Count -eq 0) {
        $openedStart = Invoke-Control @{
            operation = 'invoke'
            scope = 'system'
            target = 'taskbar'
            reference = $startRef
            expectedGeneration = $start.generation
        }
        Assert-Accepted $openedStart 'retoggle Start reference invoke'
        Start-Sleep -Milliseconds 500
        $startMenu = Invoke-Control @{
            operation = 'snapshot'
            scope = 'system'
            target = 'foreground'
            query = 'Search box'
            maxDepth = 12
            maxElements = 50
        }
    }
    Assert-Elements $startMenu 'Start menu effect'
    $summary.metrics.start_menu = Metric $startMenu
    Invoke-Control @{ operation = 'key'; scope = 'system'; key = 'escape' } |
        Out-Null
    $summary.shell.start = $true

    $search = Invoke-Control @{
        operation = 'snapshot'
        scope = 'system'
        target = 'taskbar'
        query = 'Search'
        maxDepth = 10
        maxElements = 40
    }
    Assert-Accepted $search 'Search taskbar projection'
    if (@($search.data.elements).Count -gt 0) {
        $summary.metrics.search = Metric $search
        $summary.shell.search = [ordered]@{
            controlled = $true
            taskbar_entry = $true
            fallback = 'none'
        }
    }
    else {
        Invoke-Control @{
            operation = 'key'
            scope = 'system'
            key = 'win+s'
        } | Out-Null
        Start-Sleep -Milliseconds 500
        $searchSurface = Invoke-Control @{
            operation = 'snapshot'
            scope = 'system'
            target = 'foreground'
            query = 'Search'
            maxDepth = 12
            maxElements = 40
        }
        Assert-Elements $searchSurface 'Search keyboard fallback effect'
        $summary.metrics.search = Metric $searchSurface
        $summary.shell.search = [ordered]@{
            controlled = $true
            taskbar_entry = $false
            fallback = 'target-local keyboard'
        }
        Invoke-Control @{
            operation = 'key'
            scope = 'system'
            key = 'escape'
        } | Out-Null
    }

    $network = Invoke-Control @{
        operation = 'snapshot'
        scope = 'system'
        target = 'taskbar'
        query = 'Internet access'
        maxDepth = 10
        maxElements = 40
    }
    Assert-Elements $network 'Quick Settings taskbar entry'
    $quickOpen = Invoke-Control @{
        operation = 'invoke'
        scope = 'system'
        target = 'taskbar'
        query = 'Internet access'
    }
    Assert-Accepted $quickOpen 'open Quick Settings'
    Start-Sleep -Milliseconds 500
    $quickCapture = Invoke-Control @{ operation = 'screenshot'; scope = 'system' }
    Assert-Accepted $quickCapture 'Quick Settings capture'
    $quickSemantic = Invoke-Control @{
        operation = 'snapshot'
        scope = 'system'
        target = 'foreground'
        query = 'Accessibility'
        maxDepth = 12
        maxElements = 40
    }
    $summary.shell.quick_settings = [ordered]@{
        controlled = $true
        semantic_elements = @($quickSemantic.data.elements).Count
        fallback = if (@($quickSemantic.data.elements).Count -gt 0) {
            'none'
        } else {
            'target-local pixels and input'
        }
    }
    Invoke-Control @{ operation = 'key'; scope = 'system'; key = 'escape' } |
        Out-Null

    $overflowOpen = Invoke-Control @{
        operation = 'invoke'
        scope = 'system'
        target = 'taskbar'
        query = 'Show Hidden Icons'
    }
    Assert-Accepted $overflowOpen 'open notification overflow'
    Start-Sleep -Milliseconds 350
    $overflow = Invoke-Control @{
        operation = 'snapshot'
        scope = 'system'
        query = 'System tray overflow'
        maxDepth = 12
        maxElements = 40
    }
    if (@($overflow.data.elements).Count -eq 0) {
        $overflowOpen = Invoke-Control @{
            operation = 'invoke'
            scope = 'system'
            target = 'taskbar'
            query = 'Show Hidden Icons'
        }
        Assert-Accepted $overflowOpen 'retoggle notification overflow'
        Start-Sleep -Milliseconds 350
        $overflow = Invoke-Control @{
            operation = 'snapshot'
            scope = 'system'
            query = 'System tray overflow'
            maxDepth = 12
            maxElements = 40
        }
    }
    Assert-Elements $overflow 'notification overflow effect'
    $summary.metrics.notification_overflow = Metric $overflow
    Invoke-Control @{ operation = 'key'; scope = 'system'; key = 'escape' } |
        Out-Null
    $summary.shell.notification_overflow = $true

    Invoke-Control @{ operation = 'key'; scope = 'system'; key = 'win+n' } |
        Out-Null
    Start-Sleep -Milliseconds 500
    $notificationCapture = Invoke-Control @{
        operation = 'screenshot'
        scope = 'system'
    }
    Assert-Accepted $notificationCapture 'notification center capture'
    $summary.shell.notification_center = [ordered]@{
        controlled = $true
        fallback = 'target-local pixels and input'
    }
    Invoke-Control @{ operation = 'key'; scope = 'system'; key = 'escape' } |
        Out-Null

    Invoke-Control @{ operation = 'key'; scope = 'system'; key = 'win+i' } |
        Out-Null
    Start-Sleep -Seconds 1
    $settings = Invoke-Control @{
        operation = 'snapshot'
        scope = 'system'
        target = 'foreground'
        query = 'Settings'
        maxDepth = 12
        maxElements = 60
    }
    Assert-Elements $settings 'Settings'
    $summary.metrics.settings = Metric $settings
    $summary.shell.settings = $true
    $settingsStatus = Invoke-Control @{ operation = 'status' }
    if ($settingsStatus.data.foregroundWindow.hwnd -and
        $baselineWindowHandles -notcontains
            [long]$settingsStatus.data.foregroundWindow.hwnd) {
        $createdWindowHandles.Add(
            [long]$settingsStatus.data.foregroundWindow.hwnd)
    }

    Invoke-Control @{ operation = 'key'; scope = 'system'; key = 'win+e' } |
        Out-Null
    Start-Sleep -Seconds 1
    $explorer = Invoke-Control @{
        operation = 'snapshot'
        scope = 'system'
        target = 'foreground'
        query = 'File Explorer'
        maxDepth = 12
        maxElements = 60
    }
    Assert-Elements $explorer 'File Explorer'
    $summary.metrics.explorer = Metric $explorer
    $summary.shell.explorer = $true
    $explorerStatus = Invoke-Control @{ operation = 'status' }
    if ($explorerStatus.data.foregroundWindow.hwnd -and
        $baselineWindowHandles -notcontains
            [long]$explorerStatus.data.foregroundWindow.hwnd) {
        $createdWindowHandles.Add(
            [long]$explorerStatus.data.foregroundWindow.hwnd)
    }

    Invoke-Control @{ operation = 'key'; scope = 'system'; key = 'win+d' } |
        Out-Null
    Start-Sleep -Milliseconds 300
    $screen = $status.data.virtualScreen
    Invoke-Control @{
        operation = 'click'
        scope = 'system'
        x = [int]($screen.x + ($screen.width / 2))
        y = [int]($screen.y + ($screen.height / 2))
        button = 'right'
    } | Out-Null
    Start-Sleep -Milliseconds 350
    $context = Invoke-Control @{
        operation = 'snapshot'
        scope = 'system'
        query = 'View'
        maxDepth = 12
        maxElements = 10
    }
    Assert-Elements $context 'desktop context menu'
    $summary.metrics.context_menu = Metric $context
    Invoke-Control @{ operation = 'key'; scope = 'system'; key = 'escape' } |
        Out-Null
    Invoke-Control @{ operation = 'key'; scope = 'system'; key = 'win+d' } |
        Out-Null
    $summary.shell.context_menu = $true

    $fixtureExecutable = Join-Path (Split-Path -Parent $Executable) `
        'fixtures\machine-control-medium-fixture.exe'
    Invoke-Control @{ operation = 'key'; scope = 'system'; key = 'win+r' } |
        Out-Null
    Start-Sleep -Milliseconds 350
    Invoke-Control @{
        operation = 'type'
        scope = 'system'
        text = $fixtureExecutable
    } |
        Out-Null
    Invoke-Control @{ operation = 'key'; scope = 'system'; key = 'enter' } |
        Out-Null
    $fixtureWindow = @()
    for ($attempt = 0; $attempt -lt 10 -and $fixtureWindow.Count -eq 0; $attempt++) {
        Start-Sleep -Milliseconds 500
        $fixture = Invoke-Control @{
            operation = 'windows'
            scope = 'system'
            query = 'Machine Control Medium Fixture'
            maxElements = 20
        }
        Assert-Accepted $fixture 'fixture inventory'
        $fixtureWindow = @($fixture.data.windows |
            Where-Object {
                $_.visible -and $_.title -eq 'Machine Control Medium Fixture'
            } |
            Select-Object -First 1)
    }
    if ($fixtureWindow.Count -ne 1) {
        throw 'the lifecycle fixture did not create a visible window'
    }
    $hwnd = $fixtureWindow[0].hwnd
    foreach ($state in @('minimized', 'maximized', 'restored')) {
        $stateResult = Invoke-Control @{
            operation = 'window.state'
            scope = 'system'
            hwnd = $hwnd
            state = $state
        }
        Assert-Accepted $stateResult "fixture $state"
        if ($stateResult.effect -ne 'confirmed') {
            throw "fixture $state was not independently confirmed"
        }
    }
    $windowCapture = Invoke-Control @{
        operation = 'screenshot'
        hwnd = $hwnd
    }
    Assert-Accepted $windowCapture 'exact fixture capture'
    if ($windowCapture.actualRoute -ne 'windows.native/print_window') {
        throw 'fixture capture did not use the exact-window route'
    }
    $close = Invoke-Control @{
        operation = 'window.state'
        scope = 'system'
        hwnd = $hwnd
        state = 'closed'
    }
    Assert-Accepted $close 'close fixture'
    if ($close.effect -ne 'confirmed') {
        throw 'fixture close was not independently confirmed'
    }
    $summary.shell.window_lifecycle = $true
    $summary.shell.exact_window_capture = $true

    $beforeSwitch = Invoke-Control @{ operation = 'status' }
    Invoke-Control @{ operation = 'key'; key = 'alt+tab' } | Out-Null
    Start-Sleep -Milliseconds 500
    $afterSwitch = Invoke-Control @{ operation = 'status' }
    $summary.shell.application_switching =
        $beforeSwitch.data.foregroundWindow.hwnd -ne
        $afterSwitch.data.foregroundWindow.hwnd

    $invalid = Invoke-Control @{ operation = 'not.an.operation' }
    if ($invalid.accepted -or $invalid.errorCode -ne 'unsupported_operation') {
        throw 'unsupported-operation failure semantics were not deterministic'
    }
    $summary.lifecycle.unsupported_operation = $true

    $revoke = Invoke-Control @{ operation = 'service.revoke' }
    Assert-Accepted $revoke 'service revoke'
    $stale = Invoke-Control @{
        operation = 'invoke'
        scope = 'system'
        reference = $startRef
        expectedGeneration = $start.generation
    }
    if ($stale.accepted -or $stale.errorCode -ne 'stale_generation') {
        throw 'stale generation was not rejected after revoke'
    }
    $recovered = Invoke-Control @{ operation = 'status' }
    Assert-Accepted $recovered 'helper recreation after revoke'
    $summary.lifecycle.revoke_and_recreate = $true
    $summary.lifecycle.stale_generation_rejected = $true

    $summary.passed = $true
}
finally {
    foreach ($hwnd in @($createdWindowHandles | Select-Object -Unique)) {
        try {
            Invoke-Control @{
                operation = 'window.state'
                scope = 'system'
                hwnd = $hwnd
                state = 'closed'
            } | Out-Null
        }
        catch { }
    }
    try {
        Invoke-Control @{
            operation = 'key'
            scope = 'system'
            key = 'escape'
        } | Out-Null
    }
    catch { }
    $summary | ConvertTo-Json -Depth 20 | Set-Content -LiteralPath $EvidencePath
    $summary | ConvertTo-Json -Depth 20
}
