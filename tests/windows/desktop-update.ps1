# Run as an independent interactive test actor. The caller supplies a trusted
# HTTPS fixture feed; the installed app retains its production updater config.
param(
 [Parameter(Mandatory=$true)][string]$Install,
 [Parameter(Mandatory=$true)][string]$Fixture,
 [Parameter(Mandatory=$true)][string]$Version,
 [Parameter(Mandatory=$true)][string]$Revision,
 [Parameter(Mandatory=$true)][string]$EvidencePath
)
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
Add-Type -AssemblyName UIAutomationClient,UIAutomationTypes
Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;
public static class UpdateFixtureWindow {
 [DllImport("user32.dll",CharSet=CharSet.Unicode)] public static extern IntPtr FindWindow(string className,string title);
 [DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(IntPtr hwnd,out uint processId);
}
'@
$exe=Join-Path $Install 'runtime\machine-control-windows.exe'
$summary=[ordered]@{schema='machine-control-windows-desktop-update/v0';passed=$false;checks=@()}
$fixtureProcess=$null
function Assert($condition,$message) {if(-not $condition){throw $message};$summary.checks+=@($message)}
function Process {return Get-Process machine-control -ErrorAction SilentlyContinue|Where-Object {$_.Path -eq (Join-Path $Install 'machine-control.exe')}|Select-Object -First 1}
function Element([string]$Name) {
 $deadline=[DateTime]::UtcNow.AddSeconds(30)
 do {
  $hwnd=[UpdateFixtureWindow]::FindWindow('Tauri Window','Machine Control');$owner=[uint32]0
  $null=[UpdateFixtureWindow]::GetWindowThreadProcessId($hwnd,[ref]$owner);$p=Process
  if($null -ne $p -and $owner -eq $p.Id) {
   $root=[Windows.Automation.AutomationElement]::FromHandle($hwnd)
   $condition=[Windows.Automation.AndCondition]::new([Windows.Automation.Condition[]]@(
    [Windows.Automation.PropertyCondition]::new([Windows.Automation.AutomationElement]::NameProperty,$Name),
    [Windows.Automation.PropertyCondition]::new([Windows.Automation.AutomationElement]::ControlTypeProperty,[Windows.Automation.ControlType]::Button),
    [Windows.Automation.PropertyCondition]::new([Windows.Automation.AutomationElement]::IsOffscreenProperty,$false)))
   $e=$root.FindFirst([Windows.Automation.TreeScope]::Descendants,$condition)
   if($null -ne $e){return $e}
  }
  Start-Sleep -Milliseconds 200
 } while([DateTime]::UtcNow -lt $deadline)
 throw "Update UI element unavailable: $Name"
}
function Press([string]$Name) {(Element $Name).GetCurrentPattern([Windows.Automation.InvokePattern]::Pattern).Invoke();Start-Sleep -Milliseconds 600}
function Call([hashtable]$Request) {
 $raw=($Request|ConvertTo-Json -Compress -Depth 10)|& $exe call --profile user --instance desktop --session-id ([Diagnostics.Process]::GetCurrentProcess().SessionId)
 if($LASTEXITCODE -ne 0){throw 'Update resident transport failed'}
 return $raw|ConvertFrom-Json
}
try {
 Press 'Access';Press 'Enable access'
 $status=Call @{operation='status'};$generation=$status.generation;$operator=(Process).Id
 $launch=Call @{operation='app.launch';executablePath=$Fixture}
 Assert $launch.accepted 'Baseline launches independent user fixture'
 $fixtureProcess=$launch.data.processId
 Press 'Settings';Press 'Check for updates'
 Assert (-not (Element 'Install and restart').Current.IsEnabled) 'Update is disabled during active access'
 Press 'Access';Press 'Stop access';Press 'Settings'
 $deadline=[DateTime]::UtcNow.AddSeconds(10)
 do {Start-Sleep -Milliseconds 200;$enabled=(Element 'Install and restart').Current.IsEnabled} while(-not $enabled -and [DateTime]::UtcNow -lt $deadline)
 Assert $enabled 'Update becomes available after Stop'
 Press 'Install and restart'
 $deadline=[DateTime]::UtcNow.AddSeconds(120)
 do {
  Start-Sleep -Milliseconds 500;$p=Process
  $installed=(Get-Item (Join-Path $Install 'machine-control.exe')).VersionInfo.ProductVersion
 } while(($null -eq $p -or $p.Id -eq $operator -or $installed -ne $Version) -and [DateTime]::UtcNow -lt $deadline)
 Assert ($null -ne $p -and $p.Id -ne $operator -and $installed -eq $Version) 'Signed update replaces and automatically relaunches operator'
 $null=Element 'Enable access'
 $metadata=Get-Content (Join-Path $Install 'runtime\desktop-runtime.json') -Raw|ConvertFrom-Json
 Assert ($metadata.sourceRevision -eq $Revision) 'Updated companion matches exact candidate source'
 $off=Call @{operation='snapshot'}
 Assert (-not $off.accepted -and $off.errorCode -eq 'approval_required') 'Update relaunches with access off'
 $after=Call @{operation='status'}
 Assert ($after.generation -ne $generation) 'Update invalidates previous runtime generation'
 Press 'Enable access'
 $stale=Call @{operation='snapshot';expectedGeneration=$generation}
 Assert (-not $stale.accepted -and $stale.errorCode -eq 'stale_generation') 'Updated runtime refuses old generation after new arming'
 Press 'Stop access'
 Assert ($null -ne (Get-Process -Id $fixtureProcess -ErrorAction SilentlyContinue)) 'User fixture survives update handoff'
 $summary.sourceRevision=$Revision;$summary.version=$Version;$summary.passed=$true
} catch {$summary.error=$_.Exception.ToString();throw}
finally {
 if($null -ne (Process)){try{$null=Call @{operation='grant.revoke'}}catch{}}
 if($fixtureProcess){Stop-Process -Id $fixtureProcess -ErrorAction SilentlyContinue}
 $summary|ConvertTo-Json -Depth 10|Set-Content -LiteralPath $EvidencePath -Encoding utf8
}
