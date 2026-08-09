[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$Executable,

    [Parameter(Mandatory = $true)]
    [ValidateSet('lock', 'logoff', 'inspect')]
    [string]$Action,

    [string]$EvidencePath = (Join-Path $env:TEMP `
        "machine-control-lifecycle-$Action.json")
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

function Inspect-State {
    $service = Invoke-Control @{ operation = 'service.status' }
    Assert-Accepted $service 'service status'
    $status = Invoke-Control @{ operation = 'status'; scope = 'system' }
    Assert-Accepted $status 'protected status'
    $capture = Invoke-Control @{ operation = 'screenshot'; scope = 'system' }
    Assert-Accepted $capture 'protected capture'
    $semantics = Invoke-Control @{
        operation = 'snapshot'
        scope = 'system'
        query = 'Windows sign-in'
        maxDepth = 12
        maxElements = 20
    }
    Assert-Accepted $semantics 'protected semantic projection'
    return [ordered]@{
        interactive_user_present = $service.data.interactiveUserPresent
        session_locked = $service.data.sessionLocked
        desktop = $status.desktop
        status_route = $status.actualRoute
        status_integrity_rid = $status.data.integrityRid
        capture_route = $capture.actualRoute
        capture_fidelity = $capture.fidelity
        semantic_elements = @($semantics.data.elements).Count
        semantic_bytes = $semantics.data.serializedBytes
    }
}

$summary = [ordered]@{
    schema = 'machine-control-lifecycle-conformance/v0'
    action = $Action
    passed = $false
    delivery = $null
    effect = $null
    state = $null
}

try {
    if ($Action -eq 'lock') {
        $result = Invoke-Control @{
            operation = 'session.lock'
            scope = 'system'
        }
        Assert-Accepted $result 'session lock'
        $summary.delivery = $result.delivery
        $summary.effect = $result.effect
        $summary.state = Inspect-State
        if ($result.effect -ne 'confirmed' -or
            -not $summary.state.session_locked) {
            throw 'lock did not produce an independently locked session'
        }
    }
    elseif ($Action -eq 'logoff') {
        $result = Invoke-Control @{ operation = 'session.logoff' }
        Assert-Accepted $result 'session logoff'
        $summary.delivery = $result.delivery
        $summary.effect = $result.effect
        $summary.state = Inspect-State
        if ($result.effect -ne 'confirmed' -or
            $summary.state.interactive_user_present -or
            $summary.state.desktop -ne 'Winlogon') {
            throw 'logout did not produce the confirmed no-user sign-in state'
        }
    }
    else {
        $summary.delivery = 'not_applicable'
        $summary.effect = 'not_applicable'
        $summary.state = Inspect-State
    }
    $summary.passed = $true
}
finally {
    $summary | ConvertTo-Json -Depth 20 | Set-Content -LiteralPath $EvidencePath
    $summary | ConvertTo-Json -Depth 20
}
