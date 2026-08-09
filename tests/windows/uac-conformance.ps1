[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$Executable,

    [string]$EvidencePath = (Join-Path $env:LOCALAPPDATA `
        'MachineControl\conformance\uac.json')
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

function Wait-ForDesktop {
    param([string]$Name, [int]$Seconds = 15)
    $deadline = [DateTime]::UtcNow.AddSeconds($Seconds)
    do {
        $status = Invoke-Control @{ operation = 'status' }
        if ($status.accepted -and $status.desktop -eq $Name) {
            return $status
        }
        Start-Sleep -Milliseconds 200
    } while ([DateTime]::UtcNow -lt $deadline)
    throw "input desktop did not become $Name"
}

function Wait-ForWindow {
    param([string]$Title, [int]$Seconds = 15)
    $deadline = [DateTime]::UtcNow.AddSeconds($Seconds)
    do {
        $inventory = Invoke-Control @{
            operation = 'windows'
            scope = 'system'
            query = $Title
            maxElements = 20
        }
        Assert-Accepted $inventory "$Title inventory"
        $window = @($inventory.data.windows | Where-Object {
            $_.visible -and $_.title -eq $Title
        } | Select-Object -First 1)
        if ($window.Count -eq 1) {
            return $window[0]
        }
        Start-Sleep -Milliseconds 250
    } while ([DateTime]::UtcNow -lt $deadline)
    throw "window did not appear: $Title"
}

function Wait-ForSemanticText {
    param([string]$Text, [int]$Seconds = 10)
    $deadline = [DateTime]::UtcNow.AddSeconds($Seconds)
    do {
        $snapshot = Invoke-Control @{
            operation = 'snapshot'
            scope = 'system'
            query = $Text
            maxDepth = 14
            maxElements = 20
        }
        if ($snapshot.accepted -and
            @($snapshot.data.elements).Count -gt 0) {
            return $snapshot
        }
        Start-Sleep -Milliseconds 250
    } while ([DateTime]::UtcNow -lt $deadline)
    throw "semantic text did not appear: $Text"
}

function Invoke-SemanticName {
    param([string]$Name, [switch]$AllowVisualFallback)
    $request = @{
        operation = 'invoke'
        scope = 'system'
        query = $Name
    }
    if ($AllowVisualFallback) {
        $request.allowVisualFallback = $true
    }
    $result = Invoke-Control $request
    Assert-Accepted $result "invoke $Name"
    return $result
}

function Close-TestWindow {
    param([string]$Title)
    try {
        $inventory = Invoke-Control @{
            operation = 'windows'
            scope = 'system'
            query = $Title
            maxElements = 20
        }
        foreach ($window in @($inventory.data.windows | Where-Object {
            $_.visible -and $_.title -eq $Title
        })) {
            Invoke-Control @{
                operation = 'window.state'
                scope = 'system'
                hwnd = [long]$window.hwnd
                state = 'closed'
            } | Out-Null
        }
    }
    catch { }
}

$fixtureExecutable = Join-Path (Split-Path -Parent $Executable) `
    'fixtures\machine-control-medium-fixture.exe'
$marker = Join-Path $env:LOCALAPPDATA `
    'MachineControl\conformance\elevation-approved.json'
$summary = [ordered]@{
    schema = 'machine-control-uac-conformance/v0'
    passed = $false
    policy = [ordered]@{}
    medium_requester = [ordered]@{}
    cancel = [ordered]@{}
    approve = [ordered]@{}
}

try {
    $policy = Get-ItemProperty `
        'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\System'
    $summary.policy.enable_lua = $policy.EnableLUA
    $summary.policy.consent_prompt_behavior_admin = `
        $policy.ConsentPromptBehaviorAdmin
    $summary.policy.prompt_on_secure_desktop = $policy.PromptOnSecureDesktop
    if ($policy.EnableLUA -ne 1 -or
        $policy.PromptOnSecureDesktop -ne 1 -or
        $policy.ConsentPromptBehaviorAdmin -eq 0) {
        throw 'UAC consent on the secure desktop is not enabled'
    }

    $ordinaryStatus = Invoke-Control @{ operation = 'status' }
    Assert-Accepted $ordinaryStatus 'ordinary status'
    if ($ordinaryStatus.desktop -ne 'Default' -or
        $ordinaryStatus.data.integrityRid -ne 8192 -or
        $ordinaryStatus.data.isLocalSystem) {
        throw 'ordinary request plane is not a Medium user-session process'
    }
    $summary.medium_requester.integrity_rid = `
        $ordinaryStatus.data.integrityRid

    Invoke-Control @{
        operation = 'key'
        scope = 'system'
        key = 'win+r'
    } | Out-Null
    Start-Sleep -Milliseconds 350
    Invoke-Control @{
        operation = 'type'
        scope = 'system'
        text = $fixtureExecutable
    } | Out-Null
    Invoke-Control @{
        operation = 'key'
        scope = 'system'
        key = 'enter'
    } | Out-Null
    $mediumWindow = Wait-ForWindow 'Machine Control Medium Fixture'
    $mediumIdentity = Wait-ForSemanticText 'Requester integrity RID 8192'
    $summary.medium_requester.semantic_identity = `
        @($mediumIdentity.data.elements).Count -gt 0

    Invoke-SemanticName 'Request elevation' | Out-Null
    $cancelDesktop = Wait-ForDesktop 'Winlogon'
    $cancelCapture = Invoke-Control @{
        operation = 'screenshot'
        scope = 'system'
    }
    Assert-Accepted $cancelCapture 'cancel UAC secure-desktop capture'
    $cancelSemantics = Wait-ForSemanticText 'No'
    Invoke-SemanticName 'No' -AllowVisualFallback | Out-Null
    Wait-ForDesktop 'Default' | Out-Null
    Wait-ForSemanticText 'Elevation request cancelled' | Out-Null
    $summary.cancel.desktop = $cancelDesktop.desktop
    $summary.cancel.capture_route = $cancelCapture.actualRoute
    $summary.cancel.semantic_elements = `
        @($cancelSemantics.data.elements).Count
    $summary.cancel.effect = 'confirmed'

    Invoke-SemanticName 'Request elevation' | Out-Null
    $approveDesktop = Wait-ForDesktop 'Winlogon'
    $approveCapture = Invoke-Control @{
        operation = 'screenshot'
        scope = 'system'
    }
    Assert-Accepted $approveCapture 'approve UAC secure-desktop capture'
    $approveSemantics = Wait-ForSemanticText 'Yes'
    Invoke-SemanticName 'Yes' -AllowVisualFallback | Out-Null
    Wait-ForDesktop 'Default' | Out-Null
    $elevatedWindow = Wait-ForWindow 'Machine Control Elevated Fixture'
    $elevatedControl = Wait-ForSemanticText 'Increment elevated counter'
    Invoke-SemanticName 'Increment elevated counter' | Out-Null

    $markerDeadline = [DateTime]::UtcNow.AddSeconds(10)
    do {
        $markerConfirmed = (Test-Path -LiteralPath $marker) -and
            ((Get-Content -LiteralPath $marker -Raw) -match 'counter=1')
        if ($markerConfirmed) { break }
        Start-Sleep -Milliseconds 250
    } while ([DateTime]::UtcNow -lt $markerDeadline)
    if (-not $markerConfirmed) {
        throw 'elevated fixture did not independently record counter=1'
    }
    $summary.approve.desktop = $approveDesktop.desktop
    $summary.approve.capture_route = $approveCapture.actualRoute
    $summary.approve.semantic_elements = `
        @($approveSemantics.data.elements).Count
    $summary.approve.elevated_semantic_elements = `
        @($elevatedControl.data.elements).Count
    $summary.approve.elevated_effect = 'confirmed'
    $summary.passed = $true
}
finally {
    try {
        $status = Invoke-Control @{ operation = 'status' }
        if ($status.desktop -eq 'Winlogon') {
            Invoke-Control @{
                operation = 'key'
                scope = 'system'
                key = 'escape'
            } | Out-Null
            Wait-ForDesktop 'Default' | Out-Null
        }
    }
    catch { }
    Close-TestWindow 'Machine Control Elevated Fixture'
    Close-TestWindow 'Machine Control Medium Fixture'
    Remove-Item -LiteralPath $marker -Force -ErrorAction SilentlyContinue
    New-Item -ItemType Directory -Force `
        -Path (Split-Path -Parent $EvidencePath) | Out-Null
    $summary | ConvertTo-Json -Depth 20 | Set-Content -LiteralPath $EvidencePath
    $summary | ConvertTo-Json -Depth 20
}
