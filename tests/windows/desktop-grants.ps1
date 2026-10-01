param(
    [Parameter(Mandatory=$true)][string]$Executable,
    [Parameter(Mandatory=$true)][string]$Fixture,
    [Parameter(Mandatory=$true)][string]$EvidencePath
)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
function Assert($Condition, [string]$Message) { if (-not $Condition) { throw $Message } }
$process = $null
$window = $null
$summary = [ordered]@{schema='machine-control-windows-desktop-grants/v0'; passed=$false}
function Operator([hashtable]$Command) {
    $process.StandardInput.WriteLine(($Command | ConvertTo-Json -Compress -Depth 10))
    $line = $process.StandardOutput.ReadLineAsync()
    Assert ($line.Wait(10000)) 'Operator reply timeout'
    $reply = $line.Result | ConvertFrom-Json
    return $reply
}
function Call([hashtable]$Request) {
    $json = $Request | ConvertTo-Json -Compress -Depth 10
    $reply = $json | & $Executable call --profile user --instance desktop --session-id ([Diagnostics.Process]::GetCurrentProcess().SessionId)
    Assert ($LASTEXITCODE -eq 0) 'Resident client failed'
    return $reply | ConvertFrom-Json
}
function Accepted($Reply) { Assert $Reply.accepted "Refused: $($Reply | ConvertTo-Json -Compress -Depth 10)"; return $Reply }
try {
    $start = [Diagnostics.ProcessStartInfo]::new($Executable, 'desktop')
    $start.UseShellExecute = $false
    $start.CreateNoWindow = $true
    $start.RedirectStandardInput = $true
    $start.RedirectStandardOutput = $true
    $process = [Diagnostics.Process]::Start($start)
    Assert (Operator @{method='hello'; processId=$PID}).ok 'Private operator handshake'
    $state = (Operator @{method='state'}).state
    Assert ($state.platform -eq 'windows' -and $state.deployment.policy.grantMode -eq 'approval') 'Wrong desktop profile'
    Assert $state.stopShortcutAvailable 'Native Stop shortcut unavailable'
    $off = Call @{operation='snapshot'}
    Assert (-not $off.accepted -and $off.errorCode -eq 'approval_required') 'Off by default'
    $forged = Call @{operation='operator.decision'; scopes=@('observe','control')}
    Assert (-not $forged.accepted -and $forged.errorCode -eq 'unsupported_operation') 'Public approval endpoint'
    Assert (Operator @{method='arm'; scopes=@('observe','control'); duration=60}).ok 'Local arm'
    $generation = (Accepted (Call @{operation='status'})).generation
    $launch = Accepted (Call @{operation='app.launch'; executablePath=$Fixture})
    $window = @($launch.data.windows | Where-Object {$_.visible -and $_.title -eq 'Machine Control Medium Fixture'})[0]
    $snapshot = Accepted (Call @{operation='snapshot'; hwnd=[long]$window.hwnd; maxDepth=8; maxElements=50})
    $button = @($snapshot.data.elements | Where-Object {$_.name -eq 'Increment counter'})[0]
    $null = Accepted (Call @{operation='invoke'; hwnd=[long]$window.hwnd; reference=$button.reference; expectedGeneration=$generation})
    $marker = Join-Path $env:LOCALAPPDATA 'MachineControl\conformance\counter.json'
    $effect = Get-Content -LiteralPath $marker -Raw | ConvertFrom-Json
    Assert ($effect.counter -eq 1) 'Independent fixture effect'
    $capture = Accepted (Call @{operation='screenshot'; hwnd=[long]$window.hwnd})
    Assert ($capture.delivery -eq 'confirmed') 'Native capture'
    $status = Accepted (Call @{operation='status'})
    $capturePath = Join-Path $status.data.artifactRoot ($capture.data.artifactId + '.png')
    $bytes = [IO.File]::ReadAllBytes($capturePath)
    Assert ($bytes.Length -gt 1000 -and [BitConverter]::ToString($bytes[0..7]) -eq '89-50-4E-47-0D-0A-1A-0A') 'PNG bytes'
    Assert ((Get-FileHash -LiteralPath $capturePath -Algorithm SHA256).Hash.ToLowerInvariant() -eq $capture.data.sha256) 'Capture hash'
    Remove-Item -LiteralPath $capturePath
    if ($capture.actualRoute -match '/cua/') {
        $superseded = Call @{operation='invoke'; reference=$button.reference; expectedGeneration=$generation}
        Assert (-not $superseded.accepted -and $superseded.errorCode -eq 'stale_or_unknown_reference' -and $superseded.delivery -eq 'refused') 'Superseded Cua snapshot reference refused'
        $effect = Get-Content -LiteralPath $marker -Raw | ConvertFrom-Json
        Assert ($effect.counter -eq 1) 'No replay or effect for a superseded reference'
        $summary.captureInvalidatedReference = $true
    }

    $self = Call @{operation='type'; text='must refuse'; processId=$PID}
    Assert (-not $self.accepted -and $self.errorCode -eq 'self_target_refused') 'Own operator targeting'
    Assert (Operator @{method='stop'}).ok 'Stop'
    Assert (-not (Call @{operation='snapshot'}).accepted) 'Stop revokes observation'
    Assert (Operator @{method='arm'; scopes=@('observe'); duration=60}).ok 'View-only arm'
    Assert (-not (Call @{operation='invoke'; reference=$button.reference; hwnd=[long]$window.hwnd}).accepted) 'Narrowed input refused'
    $stale = Call @{operation='snapshot'; expectedGeneration=$generation}
    Assert (-not $stale.accepted -and $stale.errorCode -eq 'stale_generation') 'Stale epoch rejected'
    Assert (-not (Operator @{method='prepare_update'}).ok) 'Active update refused'
    Assert (Operator @{method='stop'}).ok 'Stop for approval'
    # Grant request remains outstanding while a second connection inspects
    # state and operator IPC completes the decision.
    $request = @{operation='grant.request'; scopes=@('observe','control'); reason='Native fixture acceptance'; durationSeconds=300; timeoutSeconds=5} | ConvertTo-Json -Compress
    $clientStart = [Diagnostics.ProcessStartInfo]::new($Executable, "call --profile user --instance desktop --session-id $([Diagnostics.Process]::GetCurrentProcess().SessionId)")
    $clientStart.UseShellExecute=$false; $clientStart.CreateNoWindow=$true
    $clientStart.RedirectStandardInput=$true; $clientStart.RedirectStandardOutput=$true
    $client = [Diagnostics.Process]::Start($clientStart)
    try {
        $client.StandardInput.Write($request); $client.StandardInput.Close()
        $deadline = [DateTime]::UtcNow.AddSeconds(4)
        do { $state=(Operator @{method='state'}).state; if ($null -ne $state.pending) {break}; Start-Sleep -Milliseconds 100 } while ([DateTime]::UtcNow -lt $deadline)
        Assert ($null -ne $state.pending) 'Pending approval missing'
        $paused = Call @{operation='click'; x=10; y=10}
        Assert (-not $paused.accepted -and $paused.errorCode -eq 'approval_prompt_visible') 'Prompt input paused'
        Assert (Operator @{method='decision'; id=$state.pending.id; allow=$true; scopes=@('observe'); duration=60}).ok 'Narrowed decision'
        Assert ($client.WaitForExit(10000)) 'Grant client did not complete'
        Assert ($client.StandardOutput.ReadToEnd() | ConvertFrom-Json).accepted 'Approved grant reply'
    } finally { if (-not $client.HasExited) {$client.Kill()}; $client.Dispose() }
    Assert (-not (Call @{operation='type'; text='refuse'}).accepted) 'View-only decision enforced'
    Assert (Operator @{method='stop'}).ok 'Stop for replacement'
    Assert (Operator @{method='prepare_update'}).ok 'Idle update guard'
    Assert (-not (Operator @{method='arm'; scopes=@('control'); duration=60}).ok) 'Arming during replacement refused'
    Assert (Operator @{method='cancel_update'}).ok 'Cancel replacement'
    $summary.passed=$true
    $summary.profile='ordinary_user_desktop'; $summary.fixtureEffect='independently_confirmed'
    $summary.stopShortcut='native_registered'; $summary.grantBinding='target_wide'
} catch { $summary.error=$_.Exception.Message; throw }
finally {
    if ($null -ne $process) {
        if (-not $process.HasExited) { try {$null=Operator @{method='quit'}} catch {}; if (-not $process.WaitForExit(10000)) {$process.Kill()} }
        $process.Dispose()
    }
    if ($null -ne $window) { Stop-Process -Id ([int]$window.processId) -ErrorAction SilentlyContinue }
    $summary | ConvertTo-Json -Depth 10 | Set-Content -LiteralPath $EvidencePath -Encoding UTF8
}
