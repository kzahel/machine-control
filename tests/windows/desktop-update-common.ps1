# Shared independent-actor helpers for the installed desktop update and
# browser harnesses. Dot-source after setting $Install and $summary. Operator
# actions use the real Settings UI through UI Automation; agent work uses the
# ordinary admission channel. No private operator transport is used.
Add-Type -AssemblyName UIAutomationClient,UIAutomationTypes,System.Windows.Forms
$script:McOperator=Join-Path $Install 'machine-control.exe'
$script:McExe=Join-Path $Install 'runtime\machine-control-windows.exe'
$script:McSession=[Diagnostics.Process]::GetCurrentProcess().SessionId
$script:McPlan=Join-Path $env:LOCALAPPDATA 'org.machine-control.app\update-access-resume.json'
$script:McDiagnostics=Join-Path $env:LOCALAPPDATA 'MachineControl\logs\diagnostics'
$script:McStartedUnixMs=[DateTimeOffset]::UtcNow.ToUnixTimeMilliseconds()
$UIA=[Windows.Automation.AutomationElement]
function Assert($Value,[string]$Message){if(-not $Value){throw $Message};$summary.checks+=@($Message)}
function Observe([string]$Name,$Value){$summary.observations[$Name]=$Value}
function Operator {
 return @(Get-Process machine-control -ErrorAction SilentlyContinue|Where-Object {$_.Path -eq $script:McOperator})|Select-Object -First 1
}
function Call([hashtable]$Request){
 $raw=($Request|ConvertTo-Json -Compress -Depth 20)|& $script:McExe call --profile user --instance desktop --session-id $script:McSession
 if(-not $raw){throw 'Resident transport returned no JSON'}
 return ($raw|Out-String)|ConvertFrom-Json
}
# Parameter names avoid capture by callers' scriptblocks (dynamic scope).
function Wait-Until([scriptblock]$WaitCondition,[string]$WaitLabel,[int]$WaitSeconds=30,[int]$WaitMilliseconds=200){
 $waitDeadline=[DateTime]::UtcNow.AddSeconds($WaitSeconds)
 do{$waitValue=& $WaitCondition;if($waitValue){return $waitValue};Start-Sleep -Milliseconds $WaitMilliseconds}while([DateTime]::UtcNow -lt $waitDeadline)
 throw "Timed out: $WaitLabel"
}
function UiRoot {
 $p=Operator
 if($null -eq $p){return $null}
 $condition=[Windows.Automation.AndCondition]::new([Windows.Automation.Condition[]]@(
  [Windows.Automation.PropertyCondition]::new($UIA::ProcessIdProperty,$p.Id),
  [Windows.Automation.PropertyCondition]::new($UIA::NameProperty,'Machine Control')))
 return $UIA::RootElement.FindFirst([Windows.Automation.TreeScope]::Children,$condition)
}
# Find a rendered element by exact name or wildcard; optional control types.
# Settings scrolls, so offscreen elements are included; actions scroll first.
# One cached FindAll per attempt keeps cross-process UIA traffic low: heavy
# per-property polling of WebView2 has starved the resident's 5-second
# operator deadline on small guests.
$script:McCache=[Windows.Automation.CacheRequest]::new()
$script:McCache.Add($UIA::NameProperty);$script:McCache.Add($UIA::ControlTypeProperty)
function Find-Ui([string]$Name,[string[]]$Types=@(),[switch]$Like,$Within,[int]$Seconds=20,[switch]$Optional){
 $deadline=[DateTime]::UtcNow.AddSeconds($Seconds)
 do{
  $root=if($Within){$Within}else{UiRoot}
  if($root){
   try{
    $scope=$script:McCache.Activate()
    try{$items=$root.FindAll([Windows.Automation.TreeScope]::Descendants,[Windows.Automation.Condition]::TrueCondition)}finally{$scope.Dispose()}
    foreach($item in $items){
     $cached=$item.Cached
     if($Like){if($cached.Name -notlike $Name){continue}}elseif($cached.Name -cne $Name){continue}
     if($Types.Count -and $Types -notcontains $cached.ControlType.ProgrammaticName.Replace('ControlType.','')){continue}
     return $item
    }
   }catch [Windows.Automation.ElementNotAvailableException]{}
  }
  if($Optional -and [DateTime]::UtcNow -ge $deadline){return $null}
  Start-Sleep -Milliseconds 750
 }while([DateTime]::UtcNow -lt $deadline)
 if($Optional){return $null}
 throw "Settings UI element unavailable: $Name"
}
function Reveal($Element){
 try{$Element.GetCurrentPattern([Windows.Automation.ScrollItemPattern]::Pattern).ScrollIntoView();Start-Sleep -Milliseconds 150}catch{}
 return $Element
}
function Press([string]$Name,$Within){
 $e=Reveal (Find-Ui $Name @('Button','Hyperlink','MenuItem','TabItem') -Within $Within)
 if(-not $e.Current.IsEnabled){throw "Settings control disabled: $Name"}
 # Disclosure buttons (aria-expanded) expose ExpandCollapse instead of Invoke.
 $pattern=$null
 if($e.TryGetCurrentPattern([Windows.Automation.InvokePattern]::Pattern,[ref]$pattern)){$pattern.Invoke()}
 else{$x=$e.GetCurrentPattern([Windows.Automation.ExpandCollapsePattern]::Pattern);if($x.Current.ExpandCollapseState.ToString() -eq 'Expanded'){$x.Collapse()}else{$x.Expand()}}
 Start-Sleep -Milliseconds 500
}
function Page([string]$Name){Press $Name}
function Switch-Element([string]$Label){
 return Find-Ui $Label @('Button','CheckBox') |Where-Object {$_}|Select-Object -First 1
}
function Switch-State([string]$Label){
 $e=Switch-Element $Label
 return $e.GetCurrentPattern([Windows.Automation.TogglePattern]::Pattern).Current.ToggleState.ToString() -eq 'On'
}
function Set-Switch([string]$Label,[bool]$On){
 $e=Reveal (Switch-Element $Label)
 $toggle=$e.GetCurrentPattern([Windows.Automation.TogglePattern]::Pattern)
 if(($toggle.Current.ToggleState.ToString() -eq 'On') -ne $On){
  if(-not $e.Current.IsEnabled){throw "Switch disabled: $Label"}
  $toggle.Toggle()
 }
 $null=Wait-Until {(Switch-State $Label) -eq $On} "$Label switch $On" 20
}
function Expand-Ui([string]$Name){
 $e=Reveal (Find-Ui $Name @('Button','Group','ListItem','TreeItem'))
 try{$p=$e.GetCurrentPattern([Windows.Automation.ExpandCollapsePattern]::Pattern);if($p.Current.ExpandCollapseState.ToString() -ne 'Expanded'){$p.Expand()}}
 catch [InvalidOperationException]{$e.GetCurrentPattern([Windows.Automation.InvokePattern]::Pattern).Invoke()}
 Start-Sleep -Milliseconds 400
}
function Combo-Value([string]$Label){
 $e=Find-Ui $Label @('ComboBox')
 try{return $e.GetCurrentPattern([Windows.Automation.ValuePattern]::Pattern).Current.Value}
 catch [InvalidOperationException]{
  $selected=$e.GetCurrentPattern([Windows.Automation.SelectionPattern]::Pattern).Current.GetSelection()
  if($selected.Count){return $selected[0].Current.Name};return $null
 }
}
# WebView2 exposes collapsed <select> elements without options and ignores
# ValuePattern.SetValue. Use target-local keyboard selection on the focused
# control; expanding the native popup is avoided.
function Set-Combo([string]$Label,[string]$Option){
 if((Combo-Value $Label) -eq $Option){return}
 $e=Reveal (Find-Ui $Label @('ComboBox'))
 $e.SetFocus();Start-Sleep -Milliseconds 300
 [Windows.Forms.SendKeys]::SendWait(($Option -split ' ')[0]);Start-Sleep -Milliseconds 600
 if((Combo-Value $Label) -ne $Option){
  $e.SetFocus();[Windows.Forms.SendKeys]::SendWait('{HOME}');Start-Sleep -Milliseconds 300
  for($i=0;$i -lt 6 -and (Combo-Value $Label) -ne $Option;$i++){[Windows.Forms.SendKeys]::SendWait('{DOWN}');Start-Sleep -Milliseconds 300}
 }
 $null=Wait-Until {(Combo-Value $Label) -eq $Option} "$Label = $Option" 5
}
# Visible operator state for one surface; remaining minutes are UI-rounded up.
function Surface-Ui([string]$Surface){
 $label=if($Surface -eq 'desktop'){'Desktop'}else{'Browser'}
 $on=Switch-State "$label access"
 $group=Find-Ui "$label access" @('Group')
 # React renders "{minutes} min remaining" as two adjacent text nodes.
 $scope=$script:McCache.Activate()
 try{$texts=@($group.FindAll([Windows.Automation.TreeScope]::Descendants,[Windows.Automation.PropertyCondition]::new($UIA::ControlTypeProperty,[Windows.Automation.ControlType]::Text))|ForEach-Object {$_.Cached.Name})}finally{$scope.Dispose()}
 $minutes=$null
 for($i=0;$i -lt $texts.Count;$i++){
  if($texts[$i] -match '^(\d+) min remaining$'){$minutes=[int]$Matches[1]}
  elseif($i -gt 0 -and $texts[$i] -eq ' min remaining' -and $texts[$i-1] -match '^\d+$'){$minutes=[int]$texts[$i-1]}
 }
 return [ordered]@{surface=$Surface;on=$on;beforeStarting=(Combo-Value "$label before starting");remainingMinutes=$minutes}
}
function Discard-Draft{
 $discard=Find-Ui 'Discard' @('Button') -Seconds 1 -Optional
 if($discard){$discard.GetCurrentPattern([Windows.Automation.InvokePattern]::Pattern).Invoke();Start-Sleep -Milliseconds 400}
}
# Turn one surface on through the Access page with an exact mode and lifetime.
function Enable-Surface([string]$Surface,[string]$Mode,[int]$Seconds,[string[]]$ProfileNames=@()){
 Page 'Access'
 $label=if($Surface -eq 'desktop'){'Desktop'}else{'Browser'}
 Expand-Ui 'More options'
 Set-Combo 'Access lifetime' $(switch($Seconds){0{'Until I turn it off'}900{'15 minutes'}3600{'1 hour'}28800{'8 hours'}default{throw 'Unsupported lifetime'}})
 Set-Combo "$label before starting" $(if($Mode -eq 'ask'){'Wait for my approval'}else{'Give me a heads-up'})
 foreach($name in $ProfileNames){
  $box=Reveal (Find-Ui "Allow profile $name" @('CheckBox'))
  $toggle=$box.GetCurrentPattern([Windows.Automation.TogglePattern]::Pattern)
  if($toggle.Current.ToggleState.ToString() -ne 'On'){$toggle.Toggle();Start-Sleep -Milliseconds 300}
 }
 Set-Switch "$label access" $true
 # A shared lifetime draft can leave the other live surface "unsaved"; never
 # apply it, which would renew that surface.
 Discard-Draft
}
function Refusal([string]$Surface){
 $operation=if($Surface -eq 'desktop'){'snapshot'}else{'browser.tabs'}
 return (Call @{operation=$operation}).errorCode
}
# Enabled surfaces contribute their scopes, independent of task ownership.
function Surface-Live([string]$Surface){
 $scope=if($Surface -eq 'desktop'){'control'}else{'browser'}
 return @((Call @{operation='grant.status'}).data.effectiveScopes) -contains $scope
}
function Plan-Present{Test-Path -LiteralPath $script:McPlan}
function Update-Diagnostics{
 if(-not(Test-Path $script:McDiagnostics)){return @()}
 return @(Get-ChildItem $script:McDiagnostics -Filter *.jsonl|Get-Content|ForEach-Object {try{$_|ConvertFrom-Json}catch{}}|
  Where-Object {$_.PSObject.Properties['atUnixMs'] -and $_.operation -like 'update.*' -and $_.atUnixMs -ge $script:McStartedUnixMs}|
  ForEach-Object {[ordered]@{operation=$_.operation;version=$_.version;atUnixMs=$_.atUnixMs}})
}
function Check-Update([string]$Version){
 Page 'Settings'
 Press 'Check for updates'
 $button=Find-Ui 'Install and restart' @('Button') -Seconds 60
 # "Version {version} available." is split into text nodes.
 $null=Find-Ui $Version @('Text') -Seconds 5
 return $button
}
# Press Install, capture the one-shot plan while it exists, and wait for the
# signed replacement to relaunch. Returns the replacement process.
function Install-Update([string]$Version,[int]$OperatorId,[scriptblock]$BeforeInstall){
 Press 'Install and restart'
 if($BeforeInstall){& $BeforeInstall}
 # Passive NSIS replacement plus relaunch can take minutes on ARM64 guests.
 $deadline=[DateTime]::UtcNow.AddSeconds(420)
 $plan=$null;$observations=@();$last=$null
 # Never open the installed executables while NSIS replaces them: even a
 # version read can make the passive installer stop on a write error.
 $installed=$null
 do{
  if(-not $plan -and (Plan-Present)){try{$plan=Get-Content -LiteralPath $script:McPlan -Raw|ConvertFrom-Json;Observe 'planObservedAtUnix' ([DateTimeOffset]::UtcNow.ToUnixTimeSeconds())}catch{}}
  $p=Operator
  $state=(@{operator=$(if($p){$p.Id}else{$null});plan=(Plan-Present)}|ConvertTo-Json -Compress)
  if($state -ne $last){$observations+=@(@{at=[DateTime]::UtcNow.ToString('o');state=$state});$last=$state}
  if($p -and $p.Id -ne $OperatorId){Start-Sleep -Seconds 2;$installed=(Get-Item $script:McOperator).VersionInfo.ProductVersion;break}
  Start-Sleep -Milliseconds 100
 }while([DateTime]::UtcNow -lt $deadline)
 $summary.updateObservations=$observations
 Observe 'plan' $plan
 Assert ($p -and $p.Id -ne $OperatorId -and $installed -eq $Version) 'Signed update replaces and automatically relaunches operator'
 return $p
}
# Minimal ordinary admission-channel owner. One request is outstanding at a time.
function Open-Channel([string[]]$Surfaces,[string[]]$ProfileIds=@(),[string]$Reason,[int]$Wait=120,[int]$Duration=300){
 $start=[Diagnostics.ProcessStartInfo]::new($script:McExe,('channel --profile user --instance desktop --session-id '+$script:McSession))
 $start.UseShellExecute=$false;$start.CreateNoWindow=$true;$start.RedirectStandardInput=$true;$start.RedirectStandardOutput=$true
 $start.StandardOutputEncoding=[Text.UTF8Encoding]::new($false)
 $channel=[pscustomobject]@{Process=[Diagnostics.Process]::Start($start);Sequenced=$false;Sequence=0;View=$null}
 $channel.Process.StandardInput.AutoFlush=$true
 $channel.View=Channel-Rpc $channel @{operation='control.open';schema='machine-control-admission/v2';reason=$Reason;surfaces=$Surfaces;profileIds=$ProfileIds;waitSeconds=$Wait;durationSeconds=$Duration}
 $channel.Sequenced=$channel.View.requestSequencing -eq 'strict'
 return $channel
}
function Channel-Rpc($Channel,[hashtable]$Request,[int]$Seconds=60){
 $Request.requestId=[Guid]::NewGuid().ToString('n')
 if($Channel.Sequenced){$Channel.Sequence++;$Request.requestSequence=$Channel.Sequence}
 $Channel.Process.StandardInput.WriteLine(($Request|ConvertTo-Json -Compress -Depth 20))
 $read=$Channel.Process.StandardOutput.ReadLineAsync()
 if(-not $read.Wait($Seconds*1000) -or $null -eq $read.Result){throw 'Admission channel closed or timed out'}
 $reply=$read.Result|ConvertFrom-Json
 if($reply.requestId -ne $Request.requestId){throw 'Unexpected admission reply'}
 if(-not $reply.accepted){throw ('Admission refused: '+$reply.errorCode)}
 return $reply.data
}
# Heartbeat keeps a live owner; an unaccepted offer still expires.
function Channel-Status($Channel){$Channel.View=Channel-Rpc $Channel @{operation='control.heartbeat'};return $Channel.View}
function Channel-WaitActive($Channel,[int]$Seconds=90){
 $deadline=[DateTime]::UtcNow.AddSeconds($Seconds)
 do{
  $view=Channel-Status $Channel
  if($view.state -eq 'active'){return $view}
  if($view.state -eq 'ended'){throw ('Control ended: '+$view.terminalReason)}
  if($view.state -eq 'offered'){
   try{$Channel.View=Channel-Rpc $Channel @{operation='control.accept';offerGeneration=$view.offerGeneration};if($Channel.View.state -eq 'active'){return $Channel.View}}
   catch{if($_.Exception.Message -notmatch 'stale_activation_offer|admission_changed'){throw}}
  }
  Start-Sleep -Milliseconds 250
 }while([DateTime]::UtcNow -lt $deadline)
 throw 'Control did not become active'
}
function Channel-Call($Channel,[hashtable]$Request){
 $view=Channel-Status $Channel
 if($view.state -ne 'active'){throw 'Control is not active'}
 return Channel-Rpc $Channel @{operation='control.dispatch';sessionId=$view.sessionId;resourceGenerations=$view.resourceGenerations;request=$Request}
}
function Close-Channel($Channel){
 if(-not $Channel){return}
 try{if(-not $Channel.Process.HasExited){$null=Channel-Rpc $Channel @{operation='control.cancel'} 2}}catch{}
 try{$Channel.Process.StandardInput.Close()}catch{}
 if(-not $Channel.Process.WaitForExit(3000)){try{$Channel.Process.Kill()}catch{}}
 $Channel.Process.Dispose()
}
