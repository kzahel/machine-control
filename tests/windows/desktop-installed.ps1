# Run in the interactive user session through the accepted appliance relay.
# This independent test actor operates the person-facing UI; agent requests
# still use the installed product endpoint. No product test/approval hook.
param(
 [Parameter(Mandatory=$true)][string]$Install,
 [Parameter(Mandatory=$true)][string]$Fixture,
 [Parameter(Mandatory=$true)][string]$EvidencePath,
 [Parameter(Mandatory=$true)][string]$ExpectedRevision,
 [string]$ExpectedPublisher,
 [switch]$AllowUnsigned
)
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
Add-Type -AssemblyName UIAutomationClient,UIAutomationTypes
Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;
public static class DesktopFixtureInput {
 [DllImport("user32.dll")] public static extern bool SetCursorPos(int x,int y);
 [DllImport("user32.dll")] public static extern void mouse_event(uint flags,uint x,uint y,uint data,UIntPtr extra);
 [DllImport("user32.dll")] public static extern void keybd_event(byte key,byte scan,uint flags,UIntPtr extra);
 [DllImport("user32.dll")] public static extern IntPtr SendMessage(IntPtr hwnd,uint message,IntPtr wParam,IntPtr lParam);
 [DllImport("user32.dll")] public static extern bool IsWindowVisible(IntPtr hwnd);
}
'@
$exe=Join-Path $Install 'runtime\machine-control-windows.exe'
$evidence=[ordered]@{schema='machine-control-windows-desktop-installed/v0';passed=$false;checks=@()}
function Assert($condition,$message) {if (-not $condition) {throw $message};$evidence.checks+=@($message)}
function Call([hashtable]$request) {
 $text=$request|ConvertTo-Json -Compress -Depth 10
 $raw=$text|& $exe call --profile user --instance desktop --session-id ([Diagnostics.Process]::GetCurrentProcess().SessionId)
 if ($LASTEXITCODE -ne 0) {throw 'Resident client transport failed'}
 return $raw|ConvertFrom-Json
}
function Granted {$deployment=(Call @{operation='grant.status'}).data; if ($null -ne $deployment.PSObject.Properties['grant']) {return $deployment.grant};return $null}
function Process {$items=@(Get-Process machine-control -ErrorAction SilentlyContinue|Where-Object {$_.Path -eq (Join-Path $Install 'machine-control.exe')}); if ($items.Count) {return $items[0]};return $null}
function Element([string]$Name,[string]$Type='Button') {
 $deadline=[DateTime]::UtcNow.AddSeconds(12)
 do {
  $p=Process
  if ($null -eq $p -or $p.MainWindowHandle -eq 0) {Start-Sleep -Milliseconds 150;continue}; $root=[Windows.Automation.AutomationElement]::FromHandle($p.MainWindowHandle)
  $conditions=@([Windows.Automation.PropertyCondition]::new([Windows.Automation.AutomationElement]::NameProperty,$Name),[Windows.Automation.PropertyCondition]::new([Windows.Automation.AutomationElement]::ControlTypeProperty,[Windows.Automation.ControlType]::$Type),[Windows.Automation.PropertyCondition]::new([Windows.Automation.AutomationElement]::IsOffscreenProperty,$false),[Windows.Automation.PropertyCondition]::new([Windows.Automation.AutomationElement]::IsEnabledProperty,$true))
  $condition=[Windows.Automation.AndCondition]::new([Windows.Automation.Condition[]]$conditions)
  $element=$root.FindFirst([Windows.Automation.TreeScope]::Descendants,$condition)
  if ($null -ne $element) {return $element}
  Start-Sleep -Milliseconds 150
 } while ([DateTime]::UtcNow -lt $deadline)
 throw "UI element unavailable: $Name"
}
function Press([string]$Name) {
 $element=Element $Name
 $pattern=$element.GetCurrentPattern([Windows.Automation.InvokePattern]::Pattern)
 $pattern.Invoke()
 Start-Sleep -Milliseconds 450
}
function WaitGrant([bool]$active) {
 $deadline=[DateTime]::UtcNow.AddSeconds(8)
 do {$grant=Granted;if (($null -ne $grant) -eq $active) {return};Start-Sleep -Milliseconds 100} while ([DateTime]::UtcNow -lt $deadline)
 throw 'Grant transition timeout'
}
function Request([bool]$Allow,[bool]$Narrow=$false,[bool]$Timeout=$false) {
 $start=[Diagnostics.ProcessStartInfo]::new($exe,('call --profile user --instance desktop --session-id '+[Diagnostics.Process]::GetCurrentProcess().SessionId))
 $start.UseShellExecute=$false;$start.CreateNoWindow=$true;$start.RedirectStandardInput=$true;$start.RedirectStandardOutput=$true
 $client=[Diagnostics.Process]::Start($start)
 try {
  $request=@{operation='grant.request';scopes=@('observe','control');durationSeconds=60;timeoutSeconds=$(if($Timeout){8}else{15});reason='Installed app fixture acceptance'}|ConvertTo-Json -Compress
  $client.StandardInput.Write($request);$client.StandardInput.Close()
  $null=Element 'Allow access'
  $paused=Call @{operation='click';x=10;y=10}
  Assert (-not $paused.accepted -and $paused.errorCode -eq 'approval_prompt_visible') 'Pending prompt pauses input'
  if ($Narrow) {(Element 'Control apps and input' 'CheckBox').GetCurrentPattern([Windows.Automation.TogglePattern]::Pattern).Toggle()}
  if (-not $Timeout) {if ($Allow) {Press 'Allow access'} else {Press 'Deny'}}
  Assert ($client.WaitForExit(15000)) 'Approval client completes'
  $reply=$client.StandardOutput.ReadToEnd()|ConvertFrom-Json
  Assert ($reply.accepted -eq $Allow) 'Native UI approval outcome matches'
  if ($Timeout) {Assert ($reply.errorCode -eq 'approval_timeout') 'Native approval times out'}
 } finally {if (-not $client.HasExited) {$client.Kill()};$client.Dispose()}
}
function ClickElement($Element,[bool]$Right=$false) {
 $b=$Element.Current.BoundingRectangle
 $null=[DesktopFixtureInput]::SetCursorPos([int]($b.X+$b.Width/2),[int]($b.Y+$b.Height/2))
 $down=if($Right){8}else{2};$up=if($Right){16}else{4}
 try {[DesktopFixtureInput]::mouse_event($down,0,0,0,[UIntPtr]::Zero)}
 finally {[DesktopFixtureInput]::mouse_event($up,0,0,0,[UIntPtr]::Zero)}
 Start-Sleep -Milliseconds 300
}
function RootClass([string]$Class) {
 return [Windows.Automation.AutomationElement]::RootElement.FindFirst([Windows.Automation.TreeScope]::Children,[Windows.Automation.PropertyCondition]::new([Windows.Automation.AutomationElement]::ClassNameProperty,$Class))
}
function Tray([string]$Name) {
 $overflow=RootClass 'TopLevelWindowForOverflowXamlIsland'
 if ($null -eq $overflow -or $overflow.Current.IsOffscreen) {
  $taskbar=RootClass 'Shell_TrayWnd'
  $expand=$taskbar.FindFirst([Windows.Automation.TreeScope]::Descendants,[Windows.Automation.PropertyCondition]::new([Windows.Automation.AutomationElement]::NameProperty,'Show Hidden Icons'))
  ClickElement $expand
  $overflow=RootClass 'TopLevelWindowForOverflowXamlIsland'
 }
 $buttons=$overflow.FindAll([Windows.Automation.TreeScope]::Descendants,[Windows.Automation.PropertyCondition]::new([Windows.Automation.AutomationElement]::ControlTypeProperty,[Windows.Automation.ControlType]::Button))
 $icon=@($buttons|Where-Object {$_.Current.Name.StartsWith('Machine Control ') -and -not $_.Current.IsOffscreen})[0]
 ClickElement $icon $true
 $menu=RootClass '#32768'
 $item=$menu.FindFirst([Windows.Automation.TreeScope]::Descendants,[Windows.Automation.PropertyCondition]::new([Windows.Automation.AutomationElement]::NameProperty,$Name))
 ClickElement $item
}
function Shortcut {
 # Independent native fixture input; never route this through the gated app.
 $keys=@([byte]0x11,[byte]0x12,[byte]0x10,[byte]0xbe)
 try {foreach($key in $keys){[DesktopFixtureInput]::keybd_event($key,0,0,[UIntPtr]::Zero)}}
 finally {foreach($key in ($keys[3..0])){[DesktopFixtureInput]::keybd_event($key,0,2,[UIntPtr]::Zero)}}
}
$fixtureProcess=$null
$startupKey='HKCU:\Software\Microsoft\Windows\CurrentVersion\Run'
$startupBefore=Get-ItemPropertyValue $startupKey 'Machine Control' -ErrorAction SilentlyContinue
try {
 $metadata=Get-Content (Join-Path $Install 'runtime\desktop-runtime.json') -Raw|ConvertFrom-Json
 Assert ($metadata.schema -eq 'machine-control-desktop-runtime/v0' -and $metadata.profile -eq 'ordinary_user_desktop' -and $metadata.instance -eq 'desktop') 'Installed desktop product identity'
 Assert ($metadata.sourceRevision -eq $ExpectedRevision) 'Installed source matches candidate'
 $evidence.sourceRevision=$ExpectedRevision
 $evidence.runtime=$metadata.runtime
 $evidence.unsignedDeveloperBuild=[bool]$AllowUnsigned
 if (-not $AllowUnsigned) {
  Assert (-not [string]::IsNullOrWhiteSpace($ExpectedPublisher)) 'Publisher expectation supplied'
  foreach ($binary in @((Join-Path $Install 'machine-control.exe'),$exe)) {
   $signature=Get-AuthenticodeSignature -LiteralPath $binary
   Assert ($signature.Status -eq 'Valid' -and $signature.SignerCertificate.GetNameInfo('SimpleName',$false) -eq $ExpectedPublisher -and $null -ne $signature.TimeStamperCertificate) 'Installed publisher signature and timestamp'
  }
 }
 # Clean a manually armed developer session, using the independent operator UI.
 if ($null -ne (Granted)) {Press 'Stop access';WaitGrant $false}
 $off=Call @{operation='snapshot'}
 Assert (-not $off.accepted -and $off.errorCode -eq 'approval_required') 'Installed resident is off by default'
 Request $false
 Request $false $false $true
 Request $true $true
 Assert ((Granted).scopes.Count -eq 1 -and (Granted).scopes[0] -eq 'observe') 'Native dialog narrows scope'
 Assert (-not (Call @{operation='type';text='refuse'}).accepted) 'Narrowed grant refuses input'
 Press 'Stop access';WaitGrant $false
 Request $true
 $status=Call @{operation='status'};$generation=$status.generation
 $taskbar=Call @{operation='snapshot';target='taskbar';scope='system';query='Machine Control';maxDepth=8;maxElements=100}
 $own=@($taskbar.data.elements|Where-Object {$_.automationId -eq 'Appid: org.machine-control.app'})[0]
 $self=Call @{operation='invoke';scope='system';reference=$own.reference;expectedGeneration=$generation}
 Assert (-not $self.accepted -and $self.errorCode -eq 'self_target_refused') 'Own taskbar semantics refused'
 $self=Call @{operation='click';x=[int]($own.bounds.x+$own.bounds.width/2);y=[int]($own.bounds.y+$own.bounds.height/2)}
 Assert (-not $self.accepted -and $self.errorCode -eq 'self_target_refused') 'Own taskbar coordinates refused'
 $launch=Call @{operation='app.launch';executablePath=$Fixture}
 Assert $launch.accepted 'Installed resident launches fixture'
 $fixtureProcess=$launch.data.processId
 $window=@($launch.data.windows|Where-Object {$_.title -eq 'Machine Control Medium Fixture' -and $_.visible})[0]
 $snapshot=Call @{operation='snapshot';hwnd=[long]$window.hwnd;maxDepth=8;maxElements=100}
 Assert $snapshot.accepted 'Installed resident observes fixture'
 $button=@($snapshot.data.elements|Where-Object {$_.name -eq 'Increment counter'})[0]
 $invoke=Call @{operation='invoke';hwnd=[long]$window.hwnd;reference=$button.reference;expectedGeneration=$generation}
 Assert $invoke.accepted 'Installed resident invokes fixture'
 $marker=Get-Content (Join-Path $env:LOCALAPPDATA 'MachineControl\conformance\counter.json') -Raw|ConvertFrom-Json
 Assert ($marker.counter -eq 1) 'Independent installed fixture effect'
 $capture=Call @{operation='screenshot';hwnd=[long]$window.hwnd}
 Assert $capture.accepted 'Installed resident captures fixture'
 $capturePath=Join-Path $status.data.artifactRoot ($capture.data.artifactId+'.png')
 Assert ((Get-FileHash $capturePath -Algorithm SHA256).Hash.ToLowerInvariant() -eq $capture.data.sha256) 'Installed capture bytes match hash'
 Remove-Item $capturePath
 Shortcut;WaitGrant $false
 Assert ($null -eq (Granted)) 'Native emergency Stop shortcut revokes access'
 Request $true
 $expiryGeneration=(Call @{operation='status'}).generation
 $deadline=[DateTime]::UtcNow.AddSeconds(65)
 do {Start-Sleep -Milliseconds 500;$grant=Granted} while ($null -ne $grant -and [DateTime]::UtcNow -lt $deadline)
 Assert ($null -eq $grant -and (Call @{operation='status'}).generation -ne $expiryGeneration) 'Installed grant expires and invalidates generation'
 Press 'Enable access';WaitGrant $true
 Press 'Stop access';WaitGrant $false
 Press 'Enable access';WaitGrant $true
 $stale=Call @{operation='snapshot';expectedGeneration=$generation}
 Assert (-not $stale.accepted -and $stale.errorCode -eq 'stale_generation') 'Installed Stop invalidates old generation'
 Press 'Settings'
 $startup=Element 'Start at login' 'CheckBox'
 $toggle=$startup.GetCurrentPattern([Windows.Automation.TogglePattern]::Pattern)
 if ($toggle.Current.ToggleState -eq 'On') {$toggle.Toggle();Start-Sleep -Milliseconds 400}
 $toggle.Toggle();Start-Sleep -Milliseconds 600
 Assert ((Get-ItemPropertyValue $startupKey 'Machine Control') -match '--background') 'Startup preference registers background launch'
 $toggle.Toggle();Start-Sleep -Milliseconds 600
 Assert ($null -eq (Get-ItemPropertyValue $startupKey 'Machine Control' -ErrorAction SilentlyContinue)) 'Startup preference removes login entry'
 $windowHandle=(Process).MainWindowHandle
 $null=[DesktopFixtureInput]::SendMessage($windowHandle,0x10,[IntPtr]::Zero,[IntPtr]::Zero)
 Start-Sleep -Milliseconds 300
 Assert (-not [DesktopFixtureInput]::IsWindowVisible($windowHandle) -and $null -ne (Process)) 'Close hides to tray and keeps resident'
 Tray 'Open Machine Control';$null=Element 'Enable access'
 Assert ([DesktopFixtureInput]::IsWindowVisible((Process).MainWindowHandle)) 'Tray Open restores settings window'
 Tray 'Settings…';$null=Element 'Start at login' 'CheckBox'
 Tray 'Check for Updates…';$null=Element 'Check for updates'
 $p=Process;$priorId=$p.Id
 Press 'Restart'
 $deadline=[DateTime]::UtcNow.AddSeconds(15)
 do {Start-Sleep -Milliseconds 200;$p=Process} while (($null -eq $p -or $p.Id -eq $priorId) -and [DateTime]::UtcNow -lt $deadline)
 Assert ($p.Id -ne $priorId) 'Native Restart replaces operator process'
 WaitGrant $false
 Assert ($null -eq (Granted)) 'Restart leaves access off'
 Press 'Settings'
 $runtime=@(Get-CimInstance Win32_Process|Where-Object {$_.ExecutablePath -eq $exe -and $_.CommandLine -match ' desktop$'})[0]
 Stop-Process -Id $runtime.ProcessId
 Start-Sleep -Milliseconds 1600
 Press 'Restart'
 WaitGrant $false
 Assert ((Call @{operation='status'}).accepted) 'Restart recovers after companion failure'
 Press 'Enable access';WaitGrant $true
 Tray 'Stop access';WaitGrant $false
 Assert ($null -eq (Granted)) 'Tray Stop revokes access'
 $quitRuntime=(Call @{operation='status'}).data.processId
 Tray 'Quit Machine Control'
 Start-Sleep -Milliseconds 800
 Assert ($null -eq (Process) -and $null -eq (Get-Process -Id $quitRuntime -ErrorAction SilentlyContinue)) 'Tray Quit cleans operator and resident'
 $null=Start-Process (Join-Path $Install 'machine-control.exe')
 WaitGrant $false
 $p=Process;$operatorId=$p.Id
 $runtime=@(Get-CimInstance Win32_Process|Where-Object {$_.ExecutablePath -eq $exe -and $_.CommandLine -match ' desktop$'})[0]
 Stop-Process -Id $operatorId
 Start-Sleep -Milliseconds 1500
 Assert ($null -eq (Get-Process -Id $runtime.ProcessId -ErrorAction SilentlyContinue)) 'Operator failure cleans resident job'
 Assert ($null -ne (Get-Process -Id $fixtureProcess -ErrorAction SilentlyContinue)) 'User-launched fixture survives operator exit'
 $evidence.passed=$true
} catch {$evidence.error=$_.Exception.ToString();throw}
finally {
 if ($null -ne $startupBefore) {Set-ItemProperty $startupKey 'Machine Control' $startupBefore}
 else {Remove-ItemProperty $startupKey 'Machine Control' -ErrorAction SilentlyContinue}
 if ($fixtureProcess) {Stop-Process -Id $fixtureProcess -ErrorAction SilentlyContinue}
 $evidence|ConvertTo-Json -Depth 10|Set-Content $EvidencePath -Encoding UTF8
}
