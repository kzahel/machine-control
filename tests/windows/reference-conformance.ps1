param(
    [Parameter(Mandatory = $true)][string]$Executable,
    [Parameter(Mandatory = $true)][string]$Instance,
    [Parameter(Mandatory = $true)][string]$EvidencePath,
    [int]$SessionId = 1
)
$ErrorActionPreference = 'Stop'
function Call-Control($request) {
    $request.scope = 'system'
    $text = $request | ConvertTo-Json -Compress -Depth 8
    return ($text | & $Executable call --profile user --instance $Instance --session-id $SessionId) | ConvertFrom-Json
}
function Assert($condition, $label) { if (!$condition) { throw $label } }
function State { Get-Content $EvidencePath -Raw | ConvertFrom-Json }
$windows = Call-Control @{ operation = 'windows' }
$window = @($windows.data.windows | Where-Object title -eq 'Machine Control Reference Fixture')
Assert ($window.Count -eq 1) 'Expected exactly one owned reference fixture'
$snapshot = Call-Control @{ operation = 'snapshot'; hwnd = $window[0].hwnd; maxDepth = 8; maxElements = 50 }
Assert $snapshot.accepted 'Fixture snapshot refused'
$buttons = @($snapshot.data.elements | Where-Object { $_.name -eq 'Start' } | Sort-Object { $_.bounds.x })
$edits = @($snapshot.data.elements | Where-Object { $_.name -eq 'Shared entry' } | Sort-Object { $_.bounds.x })
Assert ($buttons.Count -eq 2 -and $edits.Count -eq 2) 'Duplicate fixture controls missing'
# Deliberately omit HWND/target, as the common reference-action CLI does.
# A contradictory query must not override the observed reference identity.
$changed = Call-Control @{ operation = 'set.value'; reference = $edits[1].reference; query = 'Start'; text = 'right-only' }
Assert $changed.accepted 'Exact value reference refused'
$state = State
Assert ($state.right -eq 'right-only' -and $state.left -eq '') 'Value retargeted duplicate label'
$invoked = Call-Control @{ operation = 'invoke'; reference = $buttons[1].reference }
Assert $invoked.accepted 'Exact button reference refused'
$state = State
Assert ($state.second -eq 1 -and $state.first -eq 0) 'Button retargeted duplicate label or shell'
$stale = Call-Control @{ operation = 'invoke'; reference = $buttons[1].reference }
Assert (!$stale.accepted -and $stale.errorCode -eq 'stale_or_unknown_reference') 'Removed element was retargeted'
$generation = Call-Control @{ operation = 'invoke'; reference = $buttons[0].reference; expectedGeneration = 'wrong-generation' }
Assert (!$generation.accepted -and $generation.errorCode -eq 'stale_generation') 'Generation fencing failed'
$query = Call-Control @{ operation = 'invoke'; hwnd = $window[0].hwnd; query = 'Start' }
Assert $query.accepted 'Query-only lookup regressed'
$state = State
Assert ($state.first -eq 1 -and $state.second -eq 1) 'Query-only effect missing'
Write-Output 'Exact button/value references, removed-element refusal, generation fencing and query-only effect passed'
