[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$Executable,

    [string]$EvidencePath = (Join-Path $env:LOCALAPPDATA `
        'MachineControl\conformance\local-probe.json')
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Invoke-Control {
    param([hashtable]$Request)
    $json = $Request | ConvertTo-Json -Compress
    return ($json | & $Executable call) | ConvertFrom-Json
}

$status = Invoke-Control @{ operation = 'status' }
$start = Invoke-Control @{
    operation = 'snapshot'
    scope = 'system'
    target = 'taskbar'
    query = 'Start'
    maxDepth = 10
    maxElements = 40
}

$result = [ordered]@{
    schema = 'machine-control-local-probe/v0'
    passed = $status.accepted -and $start.accepted -and
        @($start.data.elements).Count -gt 0
    caller_process_integrity_expected = 'Medium'
    routed_status_integrity_rid = $status.data.integrityRid
    status_route = $status.actualRoute
    system_projection_route = $start.actualRoute
    system_projection_elements = $start.data.count
    system_projection_bytes = $start.data.serializedBytes
    generation = $status.generation
}
New-Item -ItemType Directory -Force -Path (Split-Path -Parent $EvidencePath) |
    Out-Null
$result | ConvertTo-Json -Depth 10 | Set-Content -LiteralPath $EvidencePath
