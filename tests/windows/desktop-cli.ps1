# Run in the interactive user session. Coordination is released in finally.
param(
 [Parameter(Mandatory=$true)][string]$Install,
 [string]$Source,
 [string]$Client,
 [Parameter(Mandatory=$true)][string]$EvidencePath,
 [string]$Fixture,
 [switch]$KeepFixture
)
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
if ([string]::IsNullOrWhiteSpace($Source) -eq [string]::IsNullOrWhiteSpace($Client)) {
 throw 'Select exactly one source checkout or installed CLI command'
}
$env:MACHINE_CONTROL_DESKTOP_INSTALL_DIR=$Install
$registry=Join-Path (Split-Path $EvidencePath) 'cli-targets.json'
'{"schema":"machine-control-targets/v0","includeDefaults":true,"targets":{}}'|Set-Content $registry -Encoding ascii
$claimId=$null
$fixtureProcess=$null
$capturePath=$null
$summary=[ordered]@{schema='machine-control-windows-desktop-cli/v0';passed=$false}
function InvokeCommon([string[]]$Arguments) {
 # Windows PowerShell 5.1 uses legacy native argument quoting.
 if ($PSVersionTable.PSVersion.Major -lt 7) {$Arguments=@($Arguments|ForEach-Object {if ($_.StartsWith('{')) {$_.Replace('"','\"')} else {$_}})}
 if ($Client) {
  $raw=& $Client --registry $registry --target host @Arguments
 } else {
  $raw=& python.exe (Join-Path $Source 'bin\machine-control') --registry $registry --target host @Arguments
 }
 $result=$raw|ConvertFrom-Json
 return $result
}
try {
 $doctor=InvokeCommon @('target','doctor'); if (-not $doctor.ready) {throw 'Local doctor unavailable'}
 $acquired=InvokeCommon @('claim','acquire','--claimant-authority','codex','--claimant-id','windows-desktop-acceptance','--reason','Native local desktop CLI acceptance')
 if (-not $acquired.accepted) {throw 'Local coordination claim unavailable'}
 $claimId=$acquired.data.claim.claimId
 $status=InvokeCommon @('--claim',$claimId,'grant','status')
 if (-not $status.accepted) {throw 'Common grant status failed'}
 $local=InvokeCommon @('--claim',$claimId,'desktop','raw-local','{"operation":"status"}')
 if (-not $local.accepted -or -not $local.data.desktopProduct) {throw 'Local resident profile mismatch'}
 if ($Fixture) {
  if ($null -eq $status.data.PSObject.Properties['grant']) {throw 'Active local/outside probe requires an independently armed native grant'}
  $launch=InvokeCommon @('--claim',$claimId,'desktop','raw',(@{operation='app.launch';executablePath=$Fixture;expectedGeneration=$local.generation}|ConvertTo-Json -Compress))
  if (-not $launch.accepted) {throw 'Local common CLI fixture launch failed'}
  $fixtureProcess=$launch.data.processId
  $window=@($launch.data.windows|Where-Object {$_.visible -and $_.title -eq 'Machine Control Medium Fixture'})[0]
  $snapshot=InvokeCommon @('--claim',$claimId,'desktop','raw',(@{operation='snapshot';hwnd=[long]$window.hwnd;maxDepth=8;maxElements=100}|ConvertTo-Json -Compress))
  if (-not $snapshot.accepted -or $snapshot.fallbackUsed -or $snapshot.actualRoute -notmatch '/cua/') {throw 'Local common CLI packaged observation failed'}
  $button=@($snapshot.data.elements|Where-Object {$_.name -eq 'Increment counter'})[0]
  $action=InvokeCommon @('--claim',$claimId,'desktop','raw',(@{operation='invoke';reference=$button.reference;expectedGeneration=$local.generation}|ConvertTo-Json -Compress))
  if (-not $action.accepted) {throw 'Local common CLI fixture action failed'}
  $marker=Get-Content (Join-Path $env:LOCALAPPDATA 'MachineControl\conformance\counter.json') -Raw|ConvertFrom-Json
  if ($marker.processId -ne $fixtureProcess -or $marker.counter -ne 1) {throw 'Local CLI effect was not independently confirmed'}
  $capture=InvokeCommon @('--claim',$claimId,'desktop','raw',(@{operation='screenshot';hwnd=[long]$window.hwnd}|ConvertTo-Json -Compress))
  if (-not $capture.accepted -or $capture.fallbackUsed -or $capture.actualRoute -notmatch '/cua/') {throw 'Local common CLI packaged capture failed'}
  $capturePath=Join-Path (Split-Path $EvidencePath) ('local-capture-'+[Guid]::NewGuid().ToString('n')+'.png')
  $null=InvokeCommon @('--claim',$claimId,'desktop','artifact',$capture.data.artifactId,$capturePath)
  if ($LASTEXITCODE -ne 0 -or (Get-FileHash $capturePath -Algorithm SHA256).Hash.ToLowerInvariant() -ne $capture.data.sha256) {throw 'Local CLI artifact bytes mismatch'}
  $superseded=InvokeCommon @('--claim',$claimId,'desktop','raw',(@{operation='invoke';reference=$button.reference;expectedGeneration=$local.generation}|ConvertTo-Json -Compress))
  if ($superseded.accepted -or $superseded.errorCode -ne 'stale_or_unknown_reference' -or $superseded.delivery -ne 'refused') {throw 'Capture-superseded Cua reference was not refused'}
  $marker=Get-Content (Join-Path $env:LOCALAPPDATA 'MachineControl\conformance\counter.json') -Raw|ConvertFrom-Json
  if ($marker.counter -ne 1 -or $marker.processId -ne $fixtureProcess) {throw 'Superseded action changed the independent fixture'}
  $summary.captureInvalidatedReference=$true
  $summary.independentCounterEffect=$true;$summary.artifactHashVerified=$true
  $summary.fixtureProcessId=$fixtureProcess;$summary.fixtureHwnd=[long]$window.hwnd;$summary.fixtureReference=$button.reference
 } else {
  $off=InvokeCommon @('--claim',$claimId,'desktop','raw','{"operation":"snapshot"}')
  if ($off.accepted -or $off.errorCode -ne 'approval_required') {throw 'Common CLI bypassed native grant'}
 }
 $summary.passed=$true;$summary.grantGeneration=$status.generation;$summary.runtimeGeneration=$local.generation
} catch {$summary.error=$_.Exception.ToString();throw}
finally {
 if ($capturePath -and (Test-Path $capturePath)) {Remove-Item $capturePath}
 if ($fixtureProcess -and -not $KeepFixture) {Stop-Process -Id $fixtureProcess -ErrorAction SilentlyContinue}
 if ($claimId) {$released=InvokeCommon @('claim','release',$claimId);$summary.claimReleased=$released.accepted}
 $summary|ConvertTo-Json -Depth 10|Set-Content $EvidencePath -Encoding UTF8
}
