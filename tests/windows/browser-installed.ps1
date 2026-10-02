# Independent UI actor: no approval hook or private operator transport.
param([Parameter(Mandatory=$true)][string]$Install,
 [Parameter(Mandatory=$true)][string]$Chrome,
 [Parameter(Mandatory=$true)][string]$Fixture,
 [Parameter(Mandatory=$true)][string]$Payload,
 [Parameter(Mandatory=$true)][string]$ExpectedPublisher,
 [Parameter(Mandatory=$true)][string]$EvidencePath,
 [switch]$Lock,
 [switch]$StartupRecovery,
 [switch]$RemoteProbe,
 [string]$UpdateVersion,
 [string]$UpdateRevision,
 [string]$UpdatePayload)
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
Add-Type -AssemblyName UIAutomationClient,UIAutomationTypes,System.Windows.Forms
$exe=Join-Path $Install 'runtime\machine-control-windows.exe'
$operator=Join-Path $Install 'machine-control.exe'
$summary=[ordered]@{schema='machine-control-windows-browser-installed/v0';passed=$false;checks=@()}
$app=$null;$server=$null;$profile=$null
$root=Join-Path (Split-Path $EvidencePath) ('browser-'+[Guid]::NewGuid().ToString('n'))
New-Item -ItemType Directory $root|Out-Null
$registry=[Microsoft.Win32.RegistryKey]::OpenBaseKey([Microsoft.Win32.RegistryHive]::CurrentUser,[Microsoft.Win32.RegistryView]::Registry32)
$keyPath='Software\Google\Chrome\NativeMessagingHosts\org.machine_control.browser'
$old=$registry.OpenSubKey($keyPath);$oldValue=if($old){$old.GetValue('')}else{$null};if($old){$old.Dispose()}
$manifest=Join-Path $env:LOCALAPPDATA 'MachineControl\packages\desktop\browser-host.json'
$oldManifest=if(Test-Path $manifest){[IO.File]::ReadAllBytes($manifest)}else{$null}
function Assert($Value,[string]$Message){if(-not $Value){throw $Message};$summary.checks+=@($Message)}
function Call($Value){$Value|ConvertTo-Json -Depth 20 -Compress|& $exe call --profile user --instance desktop --session-id ([Diagnostics.Process]::GetCurrentProcess().SessionId)|ConvertFrom-Json}
function Accepted($Value){if(-not $Value.accepted){throw ('Browser operation refused: '+$Value.errorCode)};return $Value}
function Element([string]$Name,[string]$Type='Button',[bool]$Enabled=$true){
 $deadline=[DateTime]::UtcNow.AddSeconds(12)
 do{
  $app.Refresh()
  if($app.MainWindowHandle -ne [IntPtr]::Zero){
   $ui=[Windows.Automation.AutomationElement]::FromHandle($app.MainWindowHandle)
   $conditions=[Windows.Automation.Condition[]]@(
    [Windows.Automation.PropertyCondition]::new([Windows.Automation.AutomationElement]::NameProperty,$Name),
    [Windows.Automation.PropertyCondition]::new([Windows.Automation.AutomationElement]::ControlTypeProperty,[Windows.Automation.ControlType]::$Type),
    [Windows.Automation.PropertyCondition]::new([Windows.Automation.AutomationElement]::IsOffscreenProperty,$false),
    [Windows.Automation.PropertyCondition]::new([Windows.Automation.AutomationElement]::IsEnabledProperty,$Enabled))
   $item=$ui.FindFirst([Windows.Automation.TreeScope]::Descendants,[Windows.Automation.AndCondition]::new($conditions))
   if($item){return $item}
  }
  Start-Sleep -Milliseconds 100
 }while([DateTime]::UtcNow -lt $deadline)
 throw "Installed browser UI unavailable: $Name"
}
function Press([string]$Name){(Element $Name).GetCurrentPattern([Windows.Automation.InvokePattern]::Pattern).Invoke();Start-Sleep -Milliseconds 400}
function Grant([string[]]$Scopes,[bool]$Allow=$true){
 $start=[Diagnostics.ProcessStartInfo]::new($exe,('call --profile user --instance desktop --session-id '+[Diagnostics.Process]::GetCurrentProcess().SessionId))
 $start.UseShellExecute=$false;$start.CreateNoWindow=$true;$start.RedirectStandardInput=$true;$start.RedirectStandardOutput=$true
 $client=[Diagnostics.Process]::Start($start)
 try{
  $reason='Installed browser fixture '+[Guid]::NewGuid().ToString('n')
  $client.StandardInput.WriteLine((@{operation='grant.request';scopes=$Scopes;durationSeconds=300;timeoutSeconds=30;reason=$reason}|ConvertTo-Json -Compress));$client.StandardInput.Close()
  Element $reason 'Text'|Out-Null
  if($Allow){Press 'Allow access'}else{Press 'Deny'}
  Assert ($client.WaitForExit(10000)) 'Installed browser approval completes'
  $reply=$client.StandardOutput.ReadToEnd()|ConvertFrom-Json
  Assert ($reply.accepted -eq $Allow) 'Installed browser UI approval outcome'
 }finally{if(-not $client.HasExited){$client.Kill()};$client.Dispose()}
}
function Effect([string]$Field,$Expected){
 $deadline=[DateTime]::UtcNow.AddSeconds(8)
 do{$v=Get-Content (Join-Path $root 'effect.json') -Raw|ConvertFrom-Json;if($v.$Field -eq $Expected){return};Start-Sleep -Milliseconds 100}while([DateTime]::UtcNow -lt $deadline)
 throw 'Independent installed browser effect absent'
}
try{
 $inventory=Get-Content $Payload -Raw|ConvertFrom-Json
 $metadata=Get-Content (Join-Path $Install 'runtime\desktop-runtime.json') -Raw|ConvertFrom-Json
 Assert ($metadata.sourceRevision -eq $inventory.sourceRevision) 'Browser package source identity'
 Assert ((Get-Item $operator).VersionInfo.ProductVersion -eq $inventory.version) 'Browser package version'
 Assert (@(Get-ChildItem $Install -Recurse -File).Count -eq $inventory.files.Count) 'Exact browser installed file set'
 foreach($file in $inventory.files){Assert ((Get-FileHash (Join-Path $Install $file.name) -Algorithm SHA256).Hash.ToLowerInvariant() -eq $file.sha256) ('Exact browser payload: '+$file.name)}
 foreach($binary in @($operator,$exe)){$signature=Get-AuthenticodeSignature $binary;Assert ($signature.Status -eq 'Valid' -and $signature.SignerCertificate.GetNameInfo('SimpleName',$false) -eq $ExpectedPublisher -and $signature.TimeStamperCertificate) 'Browser package publisher and timestamp'}
 $app=Start-Process $operator -PassThru
 Press 'Access'
 Assert ((Call @{operation='browser.tabs'}).errorCode -eq 'approval_required') 'Installed browser access starts off'
 Press 'Permissions';Press 'Set up'
 Assert ([Threading.Thread]::CurrentThread.GetApartmentState() -eq 'STA') 'Installed UI actor uses STA clipboard'
 $extension=[Windows.Forms.Clipboard]::GetText()
 Assert (Test-Path (Join-Path $extension 'manifest.json')) 'Installed setup copies bundled extension path'
 $hostManifest=Get-Content $manifest -Raw|ConvertFrom-Json
 Assert ($hostManifest.path -eq $exe -and $hostManifest.allowed_origins.Count -eq 1 -and $hostManifest.allowed_origins[0] -eq 'chrome-extension://ncbfifkjllmnkkjmomjohinigfgdocjc/') 'Installed setup registers exact host and origin'
 $server=Start-Process (Get-Command python.exe).Source -ArgumentList @(('"'+$Fixture+'"'),'--marker',('"'+(Join-Path $root 'effect.json')+'"'),'--port-file',('"'+(Join-Path $root 'port.txt')+'"')) -PassThru -WindowStyle Hidden
 $deadline=[DateTime]::UtcNow.AddSeconds(10);while(-not(Test-Path (Join-Path $root 'port.txt'))){if([DateTime]::UtcNow -gt $deadline){throw 'Browser fixture unavailable'};Start-Sleep -Milliseconds 100}
 $url='http://127.0.0.1:'+(Get-Content (Join-Path $root 'port.txt'))+'/'
 $profile=Join-Path $root 'profile'
 Start-Process $Chrome -ArgumentList @('--no-first-run','--no-default-browser-check',('--user-data-dir="'+$profile+'"'),('--load-extension="'+$extension+'"'))|Out-Null
 $deadline=[DateTime]::UtcNow.AddSeconds(30)
 do{$connected=(Call @{operation='capabilities'}).data.browser.connected;if($connected){break};Start-Sleep -Milliseconds 200}while([DateTime]::UtcNow -lt $deadline)
 Assert $connected 'Installed native messaging connects'
 Press 'Access'
 Grant @('browser') $false
 Assert ((Call @{operation='browser.tabs'}).errorCode -eq 'approval_required') 'Installed browser denial keeps access off'
 Grant @('browser')
 $page=Accepted (Call @{operation='browser.navigate';url=$url;newTab=$true});$tab=$page.data.tab.tabId
 $snap=Accepted (Call @{operation='browser.snapshot';tabId=$tab;interactiveOnly=$true})
 $button=@($snap.data.elements|Where-Object {$_.name -eq 'Increment browser counter'})[0].reference
 Accepted (Call @{operation='browser.click';reference=$button})|Out-Null
 Effect counter 1;Assert $true 'Independent installed browser counter effect'
 $counter=1
 $text='signed-'+[Guid]::NewGuid().ToString('n')
 Accepted (Call @{operation='browser.type';reference=@($snap.data.elements|Where-Object {$_.name -eq 'Message'})[0].reference;text=$text})|Out-Null
 Accepted (Call @{operation='browser.click';reference=@($snap.data.elements|Where-Object {$_.name -eq 'Save message'})[0].reference})|Out-Null
 Effect message $text;Assert $true 'Independent installed browser text effect'
 Assert ((Call @{operation='browser.eval';tabId=$tab;expression='document.title'}).errorCode -eq 'approval_required') 'Installed browser grant excludes raw evaluation'
 $capture=Accepted (Call @{operation='browser.capture';tabId=$tab})
 $capturePath=Join-Path (Call @{operation='status'}).data.artifactRoot ($capture.data.artifactId+'.png')
 Assert ((Get-FileHash $capturePath -Algorithm SHA256).Hash.ToLowerInvariant() -eq $capture.data.sha256) 'Installed browser PNG bytes and hash'
 Remove-Item $capturePath
 Press 'Stop access'
 Assert ((Call @{operation='browser.tabs'}).errorCode -eq 'approval_required') 'Installed UI Stop revokes browser'
 Grant @('devtools')
 Assert ((Call @{operation='browser.click';reference=$button}).errorCode -eq 'stale_reference') 'Installed browser old grant reference refused'
 Assert ((Accepted (Call @{operation='browser.eval';tabId=$tab;expression='document.title'})).data.value -eq 'Machine Control Browser Fixture') 'Installed DevTools grant reaches page main world'
 $cdp=Accepted (Call @{operation='browser.cdp';tabId=$tab;method='Runtime.evaluate';params=@{expression='document.title';returnByValue=$true}})
 Assert ($cdp.data.result.result.value -eq 'Machine Control Browser Fixture') 'Installed raw CDP method and parameters reach page'
 if($RemoteProbe){
  $ready=$EvidencePath+'.remote-ready.json';$done=$EvidencePath+'.remote-done.json'
  Remove-Item $done -ErrorAction SilentlyContinue
  @{generation=(Call @{operation='status'}).generation;tabId=$tab}|ConvertTo-Json|Set-Content $ready -Encoding UTF8
  $deadline=[DateTime]::UtcNow.AddSeconds(150)
  while(-not(Test-Path $done)){if([DateTime]::UtcNow -gt $deadline){throw 'Outside browser probe did not complete'};Start-Sleep -Milliseconds 200}
  $outside=Get-Content $done -Raw|ConvertFrom-Json
  Assert $outside.passed 'Outside common browser CLI and artifact verification complete'
  Effect counter 2;$counter=2
  Assert $true 'Independent browser effect from outside common CLI'
 }
 Press 'Stop access'
 Press 'Settings';Press 'Restart'
 $deadline=[DateTime]::UtcNow.AddSeconds(15)
 do{$replacement=@(Get-Process machine-control -ErrorAction SilentlyContinue|Where-Object {$_.Path -eq $operator -and $_.Id -ne $app.Id});if($replacement.Count){break};Start-Sleep -Milliseconds 100}while([DateTime]::UtcNow -lt $deadline)
 Assert ($replacement.Count -eq 1) 'Browser operator restarts'
 $app=$replacement[0];Press 'Access'
 Assert ((Call @{operation='browser.tabs'}).errorCode -eq 'approval_required') 'Browser restart retains off-state'
 $deadline=[DateTime]::UtcNow.AddSeconds(30)
 do{$connected=(Call @{operation='capabilities'}).data.browser.connected;if($connected){break};Start-Sleep -Milliseconds 200}while([DateTime]::UtcNow -lt $deadline)
 Assert $connected 'Browser extension reconnects after operator restart'
 if($UpdateVersion){
  Assert ($UpdateRevision -and $UpdatePayload) 'Browser update identity supplied'
  Press 'Settings'
  $startup=(Element 'Start at login' 'CheckBox').GetCurrentPattern([Windows.Automation.TogglePattern]::Pattern)
  if($startup.Current.ToggleState -ne 'On'){$startup.Toggle();Start-Sleep -Milliseconds 500}
  $startupBefore=[Microsoft.Win32.Registry]::GetValue('HKEY_CURRENT_USER\Software\Microsoft\Windows\CurrentVersion\Run','Machine Control',$null)
  Assert ($startupBefore -match '--background') 'Browser update begins with startup enabled'
  $hostBefore=[IO.File]::ReadAllText($manifest)
  $key=$registry.OpenSubKey($keyPath);try{$registrationBefore=$key.GetValue('')}finally{$key.Dispose()}
  $chromeBefore=@(Get-CimInstance Win32_Process|Where-Object {$_.Name -eq 'chrome.exe' -and $_.CommandLine -like ('*'+(Split-Path $root -Leaf)+'*') -and $_.CommandLine -notmatch '--type='})[0].ProcessId
  Press 'Access';Grant @('devtools')
  $epoch=(Call @{operation='status'}).generation
  $beforeUpdate=Accepted (Call @{operation='browser.snapshot';tabId=$tab;interactiveOnly=$true})
  $oldReference=@($beforeUpdate.data.elements|Where-Object {$_.name -eq 'Increment browser counter'})[0].reference
  Press 'Settings';Press 'Check for updates'
  Assert (-not (Element 'Install and restart' 'Button' $false).Current.IsEnabled) 'Browser update blocked during active access'
  Press 'Access';Press 'Stop access';Press 'Settings'
  Press 'Install and restart'
  $deadline=[DateTime]::UtcNow.AddSeconds(120)
  $summary.updateObservations=@();$lastObservation=$null
  do{
   $replacement=@(Get-Process machine-control -ErrorAction SilentlyContinue|Where-Object {$_.Path -eq $operator -and $_.Id -ne $app.Id})
   $version=try{(Get-Item $operator).VersionInfo.ProductVersion}catch{$null}
   $observation=(@{version=$version;replacementIds=@($replacement|ForEach-Object Id)}|ConvertTo-Json -Compress)
   if($observation -ne $lastObservation){$summary.updateObservations+=@(@{at=[DateTime]::UtcNow.ToString('o');state=$observation});$lastObservation=$observation}
   if($replacement.Count -eq 1 -and $version -eq $UpdateVersion){break};Start-Sleep -Milliseconds 200
  }while([DateTime]::UtcNow -lt $deadline)
  Assert ($replacement.Count -eq 1 -and $version -eq $UpdateVersion) 'Browser signed update automatically relaunches operator'
  $app=$replacement[0];Press 'Access'
  $metadata=Get-Content (Join-Path $Install 'runtime\desktop-runtime.json') -Raw|ConvertFrom-Json
  Assert ($metadata.sourceRevision -eq $UpdateRevision) 'Browser update matches exact new source'
  $updatedInventory=Get-Content $UpdatePayload -Raw|ConvertFrom-Json
  Assert ($updatedInventory.sourceRevision -eq $UpdateRevision -and $updatedInventory.version -eq $UpdateVersion) 'Browser update inventory binds source and version'
  Assert (@(Get-ChildItem $Install -Recurse -File).Count -eq $updatedInventory.files.Count) 'Exact browser updated file set'
  foreach($file in $updatedInventory.files){Assert ((Get-FileHash (Join-Path $Install $file.name) -Algorithm SHA256).Hash.ToLowerInvariant() -eq $file.sha256) ('Exact updated browser payload: '+$file.name)}
  Assert ((Call @{operation='browser.tabs'}).errorCode -eq 'approval_required') 'Browser update relaunches with access off'
  Assert ((Call @{operation='status'}).generation -ne $epoch) 'Browser update invalidates old generation'
  Assert ([Microsoft.Win32.Registry]::GetValue('HKEY_CURRENT_USER\Software\Microsoft\Windows\CurrentVersion\Run','Machine Control',$null) -eq $startupBefore) 'Signed update preserves exact startup entry'
  $key=$registry.OpenSubKey($keyPath);try{Assert ($key.GetValue('') -eq $registrationBefore) 'Signed update preserves browser registration'}finally{$key.Dispose()}
  Assert ([IO.File]::ReadAllText($manifest) -ceq $hostBefore) 'Signed update preserves exact browser manifest'
  Assert ($null -ne (Get-Process -Id $chromeBefore -ErrorAction SilentlyContinue)) 'User browser survives signed update'
  $deadline=[DateTime]::UtcNow.AddSeconds(30)
  do{$connected=(Call @{operation='capabilities'}).data.browser.connected;if($connected){break};Start-Sleep -Milliseconds 200}while([DateTime]::UtcNow -lt $deadline)
  Assert $connected 'Extension reconnects after signed update'
  Grant @('devtools')
  Assert ((Call @{operation='browser.click';reference=$oldReference}).errorCode -eq 'stale_reference') 'Updated browser refuses pre-update reference'
  Effect counter $counter
  Assert ((Accepted (Call @{operation='browser.eval';tabId=$tab;expression='document.title'})).data.value -eq 'Machine Control Browser Fixture') 'Updated browser retains original page'
  $fresh=Accepted (Call @{operation='browser.snapshot';tabId=$tab;interactiveOnly=$true})
  Accepted (Call @{operation='browser.click';reference=@($fresh.data.elements|Where-Object {$_.name -eq 'Increment browser counter'})[0].reference})|Out-Null
  Effect counter ($counter+1);Assert $true 'Independent browser effect after signed replacement'
  Press 'Stop access'
 }
 if($StartupRecovery){
  Press 'Settings'
  $startup=(Element 'Start at login' 'CheckBox').GetCurrentPattern([Windows.Automation.TogglePattern]::Pattern)
  if($startup.Current.ToggleState -ne 'On'){$startup.Toggle();Start-Sleep -Milliseconds 500}
  Assert ([Microsoft.Win32.Registry]::GetValue('HKEY_CURRENT_USER\Software\Microsoft\Windows\CurrentVersion\Run','Machine Control',$null) -match '--background') 'Startup recovery entry enabled'
  $summary.startupRecoveryPending=$true
  Press 'Access'
 }
 & $exe browser-unregister
 $key=$registry.OpenSubKey($keyPath)
 try{Assert ($null -eq $key -and -not(Test-Path $manifest)) 'Owned browser unregister removes registry and manifest'}finally{if($key){$key.Dispose()}}
 if($Lock){
  Grant @('devtools')
  $beforeLock=(Call @{operation='status'}).generation
  $summary.preLockGeneration=$beforeLock
  $summary.recoveryStartedUtc=[DateTime]::UtcNow.ToString('o')
  Add-Type -TypeDefinition 'public static class BrowserFixtureLock { [System.Runtime.InteropServices.DllImport("user32.dll")] public static extern bool LockWorkStation(); }'
  Assert ([BrowserFixtureLock]::LockWorkStation()) 'Browser lock request delivered'
  $deadline=[DateTime]::UtcNow.AddSeconds(10)
  do{$after=Call @{operation='grant.status'};if($after.generation -ne $beforeLock){break};Start-Sleep -Milliseconds 200}while([DateTime]::UtcNow -lt $deadline)
  Assert ($after.generation -ne $beforeLock -and $null -eq $after.data.PSObject.Properties['grant']) 'Lock revokes browser grant and generation'
  Assert ((Call @{operation='browser.tabs'}).errorCode -in @('desktop_unavailable','approval_required')) 'Locked desktop refuses browser operations'
 }
 $summary.passed=$true
}catch{$summary.error=$_.Exception.Message;$summary.location=$_.ScriptStackTrace;throw}
finally{
 if($app -and -not $app.HasExited){Stop-Process -Id $app.Id -ErrorAction SilentlyContinue}
 if($profile){Get-CimInstance Win32_Process|Where-Object {$_.Name -eq 'chrome.exe' -and $_.CommandLine -like ('*'+(Split-Path $root -Leaf)+'*')}|ForEach-Object {Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue}}
 if($server -and -not $server.HasExited){$server.Kill();$server.WaitForExit()}
 if($oldValue){$key=$registry.CreateSubKey($keyPath);$key.SetValue('',$oldValue);$key.Dispose()}else{$registry.DeleteSubKeyTree($keyPath,$false)}
 if($oldManifest){[IO.File]::WriteAllBytes($manifest,$oldManifest)}elseif(Test-Path $manifest){Remove-Item $manifest}
 $registry.Dispose()
 $deadline=[DateTime]::UtcNow.AddSeconds(30)
 do{try{Remove-Item $root -Recurse -Force;break}catch{Start-Sleep -Milliseconds 250}}while([DateTime]::UtcNow -lt $deadline)
 if(Test-Path $root){$summary.cleanupError=$true;$summary.passed=$false}
 $summary|ConvertTo-Json -Depth 5|Set-Content $EvidencePath -Encoding UTF8
}
