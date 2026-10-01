# Run in the interactive user session. Coordination is released in finally.
param(
 [Parameter(Mandatory=$true)][string]$Install,
 [Parameter(Mandatory=$true)][string]$Source,
 [Parameter(Mandatory=$true)][string]$EvidencePath
)
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
$env:MACHINE_CONTROL_DESKTOP_INSTALL_DIR=$Install
$registry=Join-Path (Split-Path $EvidencePath) 'cli-targets.json'
'{"schema":"machine-control-targets/v0","includeDefaults":true,"targets":{}}'|Set-Content $registry -Encoding ascii
$claimId=$null
$summary=[ordered]@{schema='machine-control-windows-desktop-cli/v0';passed=$false}
function InvokeCommon([string[]]$Arguments) {
 # Windows PowerShell 5.1 uses legacy native argument quoting.
 if ($PSVersionTable.PSVersion.Major -lt 7) {$Arguments=@($Arguments|ForEach-Object {if ($_.StartsWith('{')) {$_.Replace('"','\"')} else {$_}})}
 $raw=& python.exe (Join-Path $Source 'bin\machine-control') --registry $registry --target host @Arguments
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
 $off=InvokeCommon @('--claim',$claimId,'desktop','raw','{"operation":"snapshot"}')
 if ($off.accepted -or $off.errorCode -ne 'approval_required') {throw 'Common CLI bypassed native grant'}
 $summary.passed=$true;$summary.grantGeneration=$status.generation;$summary.runtimeGeneration=$local.generation
} catch {$summary.error=$_.Exception.ToString();throw}
finally {
 if ($claimId) {$released=InvokeCommon @('claim','release',$claimId);$summary.claimReleased=$released.accepted}
 $summary|ConvertTo-Json -Depth 10|Set-Content $EvidencePath -Encoding UTF8
}
