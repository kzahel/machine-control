# Run as an independent interactive test actor against an installed sender.
# The caller supplies a trusted HTTPS fixture feed; the installed app retains
# its production updater configuration. Operator choices use the real Settings
# UI; no private operator transport or approval hook is used.
#
# -Scenario Resume turns Desktop access on (timed by default) and proves that
# Install and restart stays available, records a one-shot plan, and the
# updated client restores the same mode with the original wall-clock end.
# -Scenario Off proves that access left Off stays Off and records no plan.
param(
 [Parameter(Mandatory=$true)][string]$Install,
 [Parameter(Mandatory=$true)][string]$Fixture,
 [Parameter(Mandatory=$true)][string]$Version,
 [Parameter(Mandatory=$true)][string]$Revision,
 [Parameter(Mandatory=$true)][string]$EvidencePath,
 [ValidateSet('Resume','Off')][string]$Scenario='Resume',
 [ValidateSet('ask','automatic')][string]$DesktopMode='ask',
 [ValidateSet(0,900,3600,28800)][int]$DesktopSeconds=900,
 # Open a waiting agent task first: Install shows Install anyway/Cancel.
 [switch]$ConfirmAgentTask,
 # Caller-owned flag the fixture feed reads to serve modified installer bytes
 # once. Proves a rejected download never stops access.
 [string]$TamperFlag
)
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
$summary=[ordered]@{schema='machine-control-windows-desktop-update/v1';scenario=$Scenario;passed=$false;checks=@();observations=[ordered]@{}}
. (Join-Path $PSScriptRoot 'desktop-update-common.ps1')
$fixtureProcess=$null;$agent=$null
function Now{[DateTimeOffset]::UtcNow.ToUnixTimeSeconds()}
try {
 if($Scenario -eq 'Off' -and ($ConfirmAgentTask -or $TamperFlag)){throw 'Agent confirmation and tamper checks require live access'}
 $from=(Get-Item $McOperator).VersionInfo.ProductVersion
 Observe 'fromVersion' $from;Observe 'toVersion' $Version
 Assert ($from -ne $Version) 'Installed sender differs from the incoming version'
 Assert (-not (Plan-Present)) 'No access-resume plan exists before the run'
 if(-not (Operator)){Start-Process $McOperator -ArgumentList '--settings'|Out-Null}
 $null=Wait-Until {UiRoot} 'Settings window' 60
 $operatorId=(Operator).Id
 Page 'Access'
 Assert (-not (Switch-State 'Agent access')) 'Sender starts with access off'
 if($Scenario -eq 'Resume'){
  Enable-Surface 'desktop' $DesktopMode $DesktopSeconds
  $enabledAt=Now
  Assert (Surface-Live 'desktop') 'Desktop access is live before update'
  $before=Surface-Ui 'desktop';Observe 'desktopBefore' $before
  Assert ($before.on -and $before.beforeStarting -eq $(if($DesktopMode -eq 'ask'){'Wait for my approval'}else{'Give me a heads-up'})) 'Settings shows the chosen Desktop mode'
  if($DesktopSeconds){
   Assert ($before.remainingMinutes -eq [int]($DesktopSeconds/60)) 'Settings shows the full timed lifetime'
   # Cross a displayed minute so a reset lifetime is distinguishable.
   $null=Wait-Until {(Surface-Ui 'desktop').remainingMinutes -lt $before.remainingMinutes} 'one displayed minute elapsed' 100 10000
  } else {Assert ($null -eq $before.remainingMinutes) 'Until-stopped access shows no remaining time'}
 } else {
  Assert ((Refusal 'desktop') -eq 'surface_disabled' -and (Refusal 'browser') -eq 'surface_disabled') 'Desktop and Browser refuse while Off'
 }
 Assert (-not (Switch-State 'Browser access')) 'Browser access remains off in the Desktop harness'
 $fixtureProcess=(Start-Process $Fixture -PassThru).Id
 $status=Call @{operation='status'};$generation=$status.generation
 $button=Check-Update $Version
 Assert $button.Current.IsEnabled $(if($Scenario -eq 'Resume'){'Install and restart is enabled while access is on'}else{'Install and restart is enabled while access is off'})
 $note=Find-Ui '*Access pauses while Machine Control restarts, then turns back on.*' -Like -Seconds 3 -Optional
 if($Scenario -eq 'Resume'){Assert $note 'Settings explains that access pauses and turns back on'}
 else{Assert (-not $note) 'No access-pause note while access is off'}
 if($TamperFlag){
  New-Item -ItemType File -Path $TamperFlag -Force|Out-Null
  Press 'Install and restart'
  $script:sawPlan=$false
  $null=Wait-Until {if(Plan-Present){$script:sawPlan=$true};(Find-Ui 'Install and restart' @('Button')).Current.IsEnabled -and (Update-Diagnostics|Where-Object {$_.operation -eq 'update.install.failed'})} 'rejected download settles' 180 100
  Observe 'tamperMessages' @((UiRoot).FindAll([Windows.Automation.TreeScope]::Descendants,[Windows.Automation.Condition]::TrueCondition)|ForEach-Object {$_.Current.Name}|Where-Object {$_ -match 'signature|failed|error|invalid'}|Select-Object -Unique)
  Assert (-not $script:sawPlan -and -not (Plan-Present)) 'Rejected download records no access-resume plan'
  Assert ((Operator).Id -eq $operatorId -and (Get-Item $McOperator).VersionInfo.ProductVersion -eq $from) 'Rejected download leaves the sender running'
  Assert (Surface-Live 'desktop') 'Rejected download never stops access'
  Assert (-not (Update-Diagnostics|Where-Object {$_.operation -like 'update.access.*'})) 'Rejected download records no access stop'
  Remove-Item -LiteralPath $TamperFlag
 }
 $confirm=$null
 if($ConfirmAgentTask){
  $agent=Open-Channel @('desktop') -Reason 'Update confirmation fixture task' -Wait 600 -Duration 300
  # An unaccepted Automatic offer expires; accept it so the task stays live.
  # Ask mode keeps a task waiting for a person, which never arrives here.
  $waiting=if($DesktopMode -eq 'automatic'){Channel-WaitActive $agent 120}
   else{Wait-Until {$v=Channel-Status $agent;if($v.state -eq 'waiting_for_approval'){$v}} 'agent task waiting' 30}
  Observe 'agentTaskBefore' $waiting.state
  # Settings polls operator state each second; let it observe the task.
  Start-Sleep -Seconds 3
  Page 'Settings'
  Press 'Install and restart'
  $null=Find-Ui 'Install anyway' @('Button')
  Assert (Find-Ui '*An agent task is running or waiting*' -Like -Seconds 5) 'Install with an agent task asks for confirmation'
  Press 'Cancel'
  Start-Sleep -Seconds 2
  Assert (-not (Find-Ui 'Install anyway' @('Button') -Seconds 1 -Optional) -and -not (Plan-Present) -and (Operator).Id -eq $operatorId) 'Cancel keeps the sender and records no plan'
  Assert ((Surface-Live 'desktop') -and (Channel-Status $agent).state -eq $waiting.state) 'Cancel keeps access and the agent task'
  # Install-Update presses Install and restart once; then confirm.
  $confirm={$null=Find-Ui 'Install anyway' @('Button');$summary.checks+=@('Install asks again after Cancel');Press 'Install anyway'}
 }
 $replacement=Install-Update $Version $operatorId $confirm
 $installedAt=Now
 $null=Wait-Until {UiRoot} 'updated Settings window' 60
 $metadata=Get-Content (Join-Path $Install 'runtime\desktop-runtime.json') -Raw|ConvertFrom-Json
 Assert ($metadata.sourceRevision -eq $Revision) 'Updated companion matches exact candidate source'
 $null=Wait-Until {-not (Plan-Present)} 'plan consumed' 30
 Assert $true $(if($Scenario -eq 'Resume'){'Updated client consumes the one-shot plan file'}else{'No access-resume plan file remains after relaunch'})
 $plan=$summary.observations.plan
 if($agent){
  $ended=try{(Channel-Status $agent).state -eq 'ended'}catch{$true}
  Assert $ended 'Install anyway ends the waiting agent task'
 }
 if($Scenario -eq 'Resume'){
  Assert ($null -ne $plan -and $plan.targetVersion -eq $Version -and @($plan.surfaces).Count -eq 1) 'Sender records a version-bound plan for live access'
  $entry=@($plan.surfaces)[0]
  Assert ($entry.surface -eq 'desktop' -and $entry.mode -eq $DesktopMode) 'Plan records the live Desktop mode'
  if($DesktopSeconds){
   $expectedEnd=$enabledAt+$DesktopSeconds
   Observe 'expectedEndUnix' $expectedEnd;Observe 'planEndUnix' $entry.expiresAt
   Assert ([Math]::Abs([long]$entry.expiresAt-$expectedEnd) -le 5) 'Plan keeps the original wall-clock end'
  } else {Assert ($null -eq $entry.expiresAt) 'Plan keeps until-stopped access without an end'}
  Page 'Settings'
  Assert (Find-Ui 'Access was turned back on after the update.' -Seconds 150) 'Settings reports that access was turned back on'
  Page 'Access'
  $after=Surface-Ui 'desktop';$afterAt=Now;Observe 'desktopAfter' $after;Observe 'desktopAfterAtUnix' $afterAt
  Assert ($after.on -and $after.beforeStarting -eq $before.beforeStarting) 'Updated client restores the same Desktop mode'
  Assert (Surface-Live 'desktop') 'Restored Desktop access is live'
  if($DesktopSeconds){
   $expected=[int][Math]::Ceiling(([long]$entry.expiresAt-$afterAt)/60)
   Observe 'expectedRemainingMinutes' $expected
   Assert ([Math]::Abs($after.remainingMinutes-$expected) -le 1 -and $after.remainingMinutes -lt [int]($DesktopSeconds/60)) 'Restored timed access keeps its remaining time, not a reset'
  } else {Assert ($null -eq $after.remainingMinutes) 'Restored until-stopped access has no end'}
  Assert (-not (Switch-State 'Browser access') -and (Refusal 'browser') -eq 'surface_disabled') 'Restoration enables no extra surface'
  $codes=@(Update-Diagnostics|ForEach-Object {$_.operation})
  Assert ($codes -contains 'update.access.stopped' -and $codes -contains 'update.access.restored' -and $codes -notcontains 'update.access.restore_failed') 'Diagnostics record access stop and restoration'
 } else {
  Assert ($null -eq $plan) 'No plan is recorded while access is off'
  Page 'Access'
  Assert (-not (Switch-State 'Agent access') -and (Refusal 'desktop') -eq 'surface_disabled' -and (Refusal 'browser') -eq 'surface_disabled') 'Update relaunches with access still off'
  Page 'Settings'
  Assert (-not (Find-Ui 'Access was turned back on after the update.' -Seconds 3 -Optional)) 'No restoration is reported while access was off'
  Assert (-not (Update-Diagnostics|Where-Object {$_.operation -like 'update.access.*'})) 'Diagnostics record no access stop or restoration'
 }
 Observe 'updateDiagnostics' @(Update-Diagnostics)
 $after=Call @{operation='status'}
 Assert ($after.generation -ne $generation) 'Update invalidates previous runtime generation'
 $stale=Call @{operation='snapshot';expectedGeneration=$generation}
 Assert (-not $stale.accepted -and $stale.errorCode -eq 'stale_generation') 'Updated runtime refuses the old generation'
 Assert ($null -ne (Get-Process -Id $fixtureProcess -ErrorAction SilentlyContinue)) 'User fixture survives update handoff'
 $summary.sourceRevision=$Revision;$summary.version=$Version;$summary.passed=$true
} catch {$summary.error=$_.Exception.ToString();$summary.location=$_.ScriptStackTrace;throw}
finally {
 Close-Channel $agent
 if($TamperFlag){Remove-Item -LiteralPath $TamperFlag -ErrorAction SilentlyContinue}
 try{if(UiRoot){Page 'Access';if(Switch-State 'Agent access'){Set-Switch 'Agent access' $false}}}catch{$summary.cleanupError=$_.Exception.Message}
 if($fixtureProcess){Stop-Process -Id $fixtureProcess -ErrorAction SilentlyContinue}
 $summary|ConvertTo-Json -Depth 10|Set-Content -LiteralPath $EvidencePath -Encoding utf8
}
