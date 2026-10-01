# Run in the interactive user session through the accepted appliance relay.
# This independent test actor operates the person-facing UI; agent requests
# still use the installed product endpoint. No product test/approval hook.
param(
 [Parameter(Mandatory=$true)][string]$Install,
 [Parameter(Mandatory=$true)][string]$Fixture,
 [Parameter(Mandatory=$true)][string]$EvidencePath,
 [Parameter(Mandatory=$true)][string]$ExpectedRevision,
 [string]$ExpectedPublisher,
 [string]$Payload,
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
 [DllImport("user32.dll",CharSet=CharSet.Unicode)] public static extern IntPtr FindWindow(string className,string title);
 [DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(IntPtr hwnd,out uint processId);
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
function MainWindow {
 $process=Process
 $hwnd=[DesktopFixtureInput]::FindWindow('Tauri Window','Machine Control')
 $owner=[uint32]0
 $null=[DesktopFixtureInput]::GetWindowThreadProcessId($hwnd,[ref]$owner)
 if ($null -ne $process -and $owner -eq $process.Id) {return $hwnd}
 return [IntPtr]::Zero
}
function Element([string]$Name,[string]$Type='Button') {
 $deadline=[DateTime]::UtcNow.AddSeconds(12)
 do {
  $hwnd=MainWindow
  if ($hwnd -eq [IntPtr]::Zero -or -not [DesktopFixtureInput]::IsWindowVisible($hwnd)) {Start-Sleep -Milliseconds 150;continue}; $root=[Windows.Automation.AutomationElement]::FromHandle($hwnd)
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
  $reason='Installed app fixture '+[Guid]::NewGuid().ToString('n')
  $request=@{operation='grant.request';scopes=@('observe','control');durationSeconds=60;timeoutSeconds=$(if($Timeout){8}else{15});reason=$reason}|ConvertTo-Json -Compress
  $client.StandardInput.Write($request);$client.StandardInput.Close()
  # Match this request, rather than a prior prompt awaiting UI refresh.
  $null=Element $reason 'Text'
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
 $hwnd=[DesktopFixtureInput]::FindWindow($Class,$null)
 if ($hwnd -ne [IntPtr]::Zero -and [DesktopFixtureInput]::IsWindowVisible($hwnd)) {return [Windows.Automation.AutomationElement]::FromHandle($hwnd)}
 return $null
}
function RawNamed($Root,[string]$Name) {
 $walker=[Windows.Automation.TreeWalker]::RawViewWalker
 $element=$walker.GetFirstChild($Root)
 for ($i=0;$null -ne $element -and $i -lt 100;$i++) {
  if ($element.Current.Name -eq $Name) {return $element}
  $element=$walker.GetNextSibling($element)
 }
 return $null
}
function Tray([string]$Name) {
 $overflow=RootClass 'TopLevelWindowForOverflowXamlIsland'
 if ($null -eq $overflow) {
  $taskbar=RootClass 'Shell_TrayWnd'
  $items=$taskbar.FindAll([Windows.Automation.TreeScope]::Descendants,[Windows.Automation.PropertyCondition]::new([Windows.Automation.AutomationElement]::ControlTypeProperty,[Windows.Automation.ControlType]::Button))
  $expand=@($items|Where-Object {$_.Current.Name.StartsWith('Show Hidden Icons')})[0]
  $expand.GetCurrentPattern([Windows.Automation.InvokePattern]::Pattern).Invoke()
  $deadline=[DateTime]::UtcNow.AddSeconds(5)
  do {$overflow=RootClass 'TopLevelWindowForOverflowXamlIsland';if($null -ne $overflow){break};Start-Sleep -Milliseconds 100} while([DateTime]::UtcNow -lt $deadline)
 }
 if ($null -eq $overflow) {throw 'Tray overflow did not become visible'}
 $buttons=$overflow.FindAll([Windows.Automation.TreeScope]::Descendants,[Windows.Automation.PropertyCondition]::new([Windows.Automation.AutomationElement]::ControlTypeProperty,[Windows.Automation.ControlType]::Button))
 $icon=@($buttons|Where-Object {$_.Current.Name.StartsWith('Machine Control ') -and -not $_.Current.IsOffscreen})[0]
 ClickElement $icon $true
 $deadline=[DateTime]::UtcNow.AddSeconds(5)
 $item=$null
 do {
  $menu=RootClass '#32768'
  if ($null -ne $menu) {$item=RawNamed $menu $Name}
  if ($null -ne $item) {break};Start-Sleep -Milliseconds 100
 } while ([DateTime]::UtcNow -lt $deadline)
 if ($null -eq $item) {throw "Tray command unavailable: $Name"}
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
$startupRegistry='HKEY_CURRENT_USER\Software\Microsoft\Windows\CurrentVersion\Run'
function Startup {return [Microsoft.Win32.Registry]::GetValue($startupRegistry,'Machine Control',$null)}
$startupBefore=Startup
try {
 $metadata=Get-Content (Join-Path $Install 'runtime\desktop-runtime.json') -Raw|ConvertFrom-Json
 Assert ($metadata.schema -eq 'machine-control-desktop-runtime/v0' -and $metadata.profile -eq 'ordinary_user_desktop' -and $metadata.instance -eq 'desktop') 'Installed desktop product identity'
 Assert ($metadata.sourceRevision -eq $ExpectedRevision) 'Installed source matches candidate'
 $evidence.sourceRevision=$ExpectedRevision
 $evidence.runtime=$metadata.runtime
 $evidence.unsignedDeveloperBuild=[bool]$AllowUnsigned
 if (-not $AllowUnsigned) {
  Assert (-not [string]::IsNullOrWhiteSpace($ExpectedPublisher) -and -not [string]::IsNullOrWhiteSpace($Payload)) 'Publisher and exact installed inventory supplied'
  $inventory=Get-Content -LiteralPath $Payload -Raw|ConvertFrom-Json
  Assert ($inventory.sourceRevision -eq $ExpectedRevision -and $inventory.target -eq 'x86_64-pc-windows-msvc') 'Installed inventory binds source and native architecture'
  Assert ((Get-Item (Join-Path $Install 'machine-control.exe')).VersionInfo.ProductVersion -eq $inventory.version) 'Installed version matches signed candidate'
  $files=@(Get-ChildItem -LiteralPath $Install -Recurse -File)
  Assert ($files.Count -eq $inventory.files.Count) 'Installed payload has exactly the candidate file set'
  foreach ($file in $inventory.files) {
   Assert ($file.name -notmatch '(^/|\\|(^|/)\.\.?(/|$)|:)') 'Inventory contains a safe relative path'
   $path=Join-Path $Install $file.name
   Assert ((Get-Item -LiteralPath $path).Length -eq $file.size -and (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant() -eq $file.sha256) ('Installed candidate bytes: '+$file.name)
  }
  foreach ($binary in @((Join-Path $Install 'machine-control.exe'),$exe)) {
   $signature=Get-AuthenticodeSignature -LiteralPath $binary
   Assert ($signature.Status -eq 'Valid' -and $signature.SignerCertificate.GetNameInfo('SimpleName',$false) -eq $ExpectedPublisher -and $null -ne $signature.TimeStamperCertificate) 'Installed publisher signature and timestamp'
  }
 }
 # A prior tray action may have left Settings selected.
 Press 'Access'
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
 if (-not $AllowUnsigned) {Assert ($snapshot.actualRoute -match '/cua/' -and -not $snapshot.fallbackUsed) 'Signed packaged provider supplies fixture observation'}
 $button=@($snapshot.data.elements|Where-Object {$_.name -eq 'Increment counter'})[0]
 $invoke=Call @{operation='invoke';hwnd=[long]$window.hwnd;reference=$button.reference;expectedGeneration=$generation}
 Assert $invoke.accepted 'Installed resident invokes fixture'
 $marker=Get-Content (Join-Path $env:LOCALAPPDATA 'MachineControl\conformance\counter.json') -Raw|ConvertFrom-Json
 Assert ($marker.counter -eq 1) 'Independent installed fixture effect'
 $capture=Call @{operation='screenshot';hwnd=[long]$window.hwnd}
 Assert $capture.accepted 'Installed resident captures fixture'
 if (-not $AllowUnsigned) {Assert ($capture.actualRoute -match '/cua/' -and -not $capture.fallbackUsed) 'Signed packaged provider supplies fixture capture'}
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
 Assert ((Startup) -match '--background') 'Startup preference registers background launch'
 $toggle.Toggle();Start-Sleep -Milliseconds 600
 Assert ($null -eq (Startup)) 'Startup preference removes login entry'
 $windowHandle=MainWindow
 $null=[DesktopFixtureInput]::SendMessage($windowHandle,0x10,[IntPtr]::Zero,[IntPtr]::Zero)
 Start-Sleep -Milliseconds 300
 Assert (-not [DesktopFixtureInput]::IsWindowVisible($windowHandle) -and $null -ne (Process)) 'Close hides to tray and keeps resident'
 Tray 'Open Machine Control';$null=Element 'Enable access'
 Assert ([DesktopFixtureInput]::IsWindowVisible((MainWindow))) 'Tray Open restores settings window'
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
 if ($null -ne (Process)) {
  try {'{"operation":"grant.revoke"}' | & $exe call --profile user --instance desktop --session-id ([Diagnostics.Process]::GetCurrentProcess().SessionId) --timeout-ms 1000 | Out-Null} catch {}
 }
 if ($null -ne $startupBefore) {Set-ItemProperty $startupKey 'Machine Control' $startupBefore}
 else {
  $key=[Microsoft.Win32.Registry]::CurrentUser.OpenSubKey('Software\Microsoft\Windows\CurrentVersion\Run',$true)
  if ($null -ne $key) {try {$key.DeleteValue('Machine Control',$false)} finally {$key.Dispose()}}
 }
 if ($fixtureProcess) {Stop-Process -Id $fixtureProcess -ErrorAction SilentlyContinue}
 $evidence|ConvertTo-Json -Depth 10|Set-Content $EvidencePath -Encoding UTF8
}
