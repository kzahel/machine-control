# Run in the interactive session of a claimed dedicated Windows VM.
param([Parameter(Mandatory=$true)][string]$Executable,
      [Parameter(Mandatory=$true)][string]$EvidencePath)
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
$process=$null
$checks=[Collections.Generic.List[object]]::new()
function Check([string]$Name,$Value) { $checks.Add(@{name=$Name;passed=[bool]$Value}); if (-not $Value) {throw $Name} }
function Operator([hashtable]$Command) {
 $process.StandardInput.WriteLine(($Command|ConvertTo-Json -Compress))
 $line=$process.StandardOutput.ReadLineAsync()
 Check 'operator responds' ($line.Wait(10000))
 $value=$line.Result|ConvertFrom-Json
 Check ('operator accepted '+$Command.method) $value.ok
 return $value
}
function StartResident {
 $start=[Diagnostics.ProcessStartInfo]::new($Executable,'desktop')
 $start.UseShellExecute=$false; $start.CreateNoWindow=$true
 $start.RedirectStandardInput=$true; $start.RedirectStandardOutput=$true
 $script:process=[Diagnostics.Process]::Start($start)
 $null=Operator @{method='hello';processId=$PID}
 Check 'logging ready' (Operator @{method='state'}).state.logging.available
}
function StopResident {
 $null=Operator @{method='quit'}
 Check 'resident exits' ($process.WaitForExit(10000))
 $process.Dispose(); $script:process=$null
}
function Call([hashtable]$Request) {
 $value=$Request|ConvertTo-Json -Compress
 $raw=$value|& $Executable call --profile user --instance desktop --session-id ([Diagnostics.Process]::GetCurrentProcess().SessionId)
 return $raw|ConvertFrom-Json
}
try {
 StartResident
 $sentinel='SENTINEL-audit-payload'
 $clock=[Diagnostics.Stopwatch]::StartNew()
 $reply=Call @{operation='type';text=$sentinel;requestId=$sentinel}
 $clock.Stop()
 Check 'off refuses input' ($reply.errorCode -eq 'approval_required')
 $rows=@((Operator @{method='logs.query';operation='type'}).history.entries)
 Check 'intent and result stored' (($rows.phase -contains 'intent') -and ($rows.phase -contains 'result'))
 Check 'kernel caller metadata' (@($rows|Where-Object {$_.phase -eq 'intent' -and $_.PSObject.Properties['callerPid'] -and $_.callerPid -gt 0}).Count -gt 0)
 $ids=@($rows.eventId)
 $null=Operator @{method='logs.debug';enabled=$true}
 Check 'debug bounded' ((Operator @{method='state'}).state.logging.debugRemainingSeconds -le 900)
 $preview=(Operator @{method='logs.preview'}).preview|ConvertTo-Json -Depth 20
 Check 'payload excluded' (-not $preview.Contains($sentinel))
 $path=(Operator @{method='logs.export'}).path
 Check 'export persisted' (Test-Path $path)
 Check 'export payload excluded' (-not (Get-Content $path -Raw).Contains($sentinel))
 StopResident; StartResident
 $rows=@((Operator @{method='logs.query';operation='type'}).history.entries)
 foreach ($id in $ids) { Check 'restart retains history' ($rows.eventId -contains $id) }
 $state=(Operator @{method='state'}).state
 Check 'restart has access off' (-not $state.deployment.PSObject.Properties['grant'])
 $root=(Operator @{method='logs.location'}).path
 $directory=Join-Path $root 'audit'; $backup=Join-Path $root ('audit-fixture-'+[Guid]::NewGuid().ToString('n'))
 Move-Item $directory $backup
 try {
  [IO.File]::WriteAllText($directory,'fixture blocks the audit directory')
  Check 'failed intent blocks provider' ((Call @{operation='click';x=1;y=1}).errorCode -eq 'audit_storage_unavailable')
  $null=Operator @{method='stop'}
  Check 'stop works without audit storage' (-not (Operator @{method='state'}).state.deployment.PSObject.Properties['grant'])
 } finally {Remove-Item $directory -ErrorAction SilentlyContinue; Move-Item $backup $directory}
 $null=Call @{operation='snapshot'}
 Check 'storage recovers' (Operator @{method='state'}).state.logging.available
 StopResident
 @{passed=$true;checks=$checks;refusedInputElapsedMs=$clock.ElapsedMilliseconds}|ConvertTo-Json -Depth 5|Set-Content $EvidencePath
} catch {
 @{passed=$false;checks=$checks;error=$_.Exception.Message}|ConvertTo-Json -Depth 5|Set-Content $EvidencePath
 throw
} finally {
 if ($process -and -not $process.HasExited) {try {$null=Operator @{method='quit'}} catch {}; if (-not $process.WaitForExit(10000)) {$process.Kill()}}
 if ($process) {$process.Dispose()}
}
