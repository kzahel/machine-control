# Hold an owned payload image and independently verify uninstall refusal.
param([Parameter(Mandatory=$true)][string]$Install,
 [Parameter(Mandatory=$true)][string]$Payload,
 [Parameter(Mandatory=$true)][string]$ExpectedRevision,
 [Parameter(Mandatory=$true)][string]$EvidencePath)
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
$summary=[ordered]@{schema='machine-control-windows-uninstall-refusal/v0';passed=$false;checks=@()}
$held=$null;$uninstaller=$null
function Assert($Value,[string]$Message){if(-not $Value){throw $Message};$summary.checks+=@($Message)}
try{
 $inventory=Get-Content $Payload -Raw|ConvertFrom-Json
 Assert ($inventory.sourceRevision -eq $ExpectedRevision) 'Uninstall refusal binds accepted inventory'
 $operator=Join-Path $Install 'machine-control.exe'
 Assert (@(Get-Process machine-control -ErrorAction SilentlyContinue|Where-Object {$_.Path -eq $operator}).Count -eq 0) 'Refusal fixture begins with operator stopped'
 $run='HKEY_CURRENT_USER\Software\Microsoft\Windows\CurrentVersion\Run'
 $startup=[Microsoft.Win32.Registry]::GetValue($run,'Machine Control',$null)
 $held=[IO.File]::Open((Join-Path $Install 'runtime\machine-control-windows.exe'),[IO.FileMode]::Open,[IO.FileAccess]::Read,[IO.FileShare]::Read)
 $timer=[Diagnostics.Stopwatch]::StartNew()
 # Run directly so NSIS's temporary-copy bootstrap cannot mask the child's
 # error status. _?= is deliberately last and consumes the remaining path.
 $uninstaller=Start-Process (Join-Path $Install 'uninstall.exe') -ArgumentList @('/S',('_?='+$Install)) -PassThru
 Assert ($uninstaller.WaitForExit(30000)) 'Held-image refusal is bounded'
 Assert ($uninstaller.ExitCode -ne 0 -and $timer.Elapsed.TotalSeconds -ge 9) 'Actual uninstaller reports held-image failure'
 Assert (@(Get-ChildItem $Install -Recurse -File).Count -eq $inventory.files.Count) 'Refused uninstall preserves the exact file set'
 foreach($file in $inventory.files){
  Assert ($file.name -notmatch '(^/|\\|(^|/)\.\.?(/|$)|:)') 'Refusal inventory path is relative and safe'
  Assert ((Get-FileHash (Join-Path $Install $file.name) -Algorithm SHA256).Hash.ToLowerInvariant() -eq $file.sha256) ('Refused uninstall preserves bytes: '+$file.name)
 }
 Assert ([Microsoft.Win32.Registry]::GetValue($run,'Machine Control',$null) -eq $startup) 'Refused uninstall preserves login startup'
 $summary.sourceRevision=$ExpectedRevision;$summary.passed=$true
}catch{$summary.error=$_.Exception.Message;$summary.location=$_.ScriptStackTrace;throw}
finally{
 if($held){$held.Dispose()}
 if($uninstaller -and -not $uninstaller.HasExited){Stop-Process -Id $uninstaller.Id -Force -ErrorAction SilentlyContinue}
 $summary|ConvertTo-Json -Depth 5|Set-Content $EvidencePath -Encoding UTF8
}
