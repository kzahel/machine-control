# Independent UI actor for an exact installed desktop package and a separately
# identified test browser. Operator choices use the real Settings UI; agent
# work uses the ordinary admission channel. No approval hook or private
# operator transport is used. The caller owns claims, the update feed and
# cleanup verification.
param([Parameter(Mandatory=$true)][string]$Install,
 [Parameter(Mandatory=$true)][string]$Chrome,
 [Parameter(Mandatory=$true)][string]$Fixture,
 [Parameter(Mandatory=$true)][string]$Payload,
 [Parameter(Mandatory=$true)][string]$ExpectedPublisher,
 [Parameter(Mandatory=$true)][string]$EvidencePath,
 [string]$Python='python.exe',
 [string]$ProfileName='Acceptance',
 [switch]$StartupRecovery,
 [string]$UpdateVersion,
 [string]$UpdateRevision,
 [string]$UpdatePayload,
 # Also turn Desktop on for the update; 'none' updates with Browser only.
 [ValidateSet('none','ask','automatic')][string]$UpdateDesktopMode='ask',
 [ValidateSet(0,900,3600,28800)][int]$UpdateDesktopSeconds=900)
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
Add-Type -AssemblyName System.Windows.Forms
$summary=[ordered]@{schema='machine-control-windows-browser-installed/v1';passed=$false;checks=@();observations=[ordered]@{}}
. (Join-Path $PSScriptRoot 'desktop-update-common.ps1')
$exe=$McExe;$operator=$McOperator
$server=$null;$profile=$null;$agent=$null;$chromeProcess=$null
$root=Join-Path (Split-Path $EvidencePath) ('browser-'+[Guid]::NewGuid().ToString('n'))
New-Item -ItemType Directory $root|Out-Null
$registry=[Microsoft.Win32.RegistryKey]::OpenBaseKey([Microsoft.Win32.RegistryHive]::CurrentUser,[Microsoft.Win32.RegistryView]::Registry32)
$keyPath='Software\Google\Chrome\NativeMessagingHosts\org.machine_control.browser'
$old=$registry.OpenSubKey($keyPath);$oldValue=if($old){$old.GetValue('')}else{$null};if($old){$old.Dispose()}
$manifest=Join-Path $env:LOCALAPPDATA 'MachineControl\packages\desktop\browser-host.json'
$oldManifest=if(Test-Path $manifest){[IO.File]::ReadAllBytes($manifest)}else{$null}
function Accepted($Value){if(-not $Value.accepted){throw ('Browser operation refused: '+$Value.errorCode)};return $Value}
function Browser-State{(Call @{operation='capabilities'}).data.browser}
# The CI inventory is taken after its installed-CLI smoke runs, so it also
# lists bundled-Python bytecode caches the installer never writes. Those are
# optional here; every other entry and every installed file must match.
function Verify-Payload($Inventory,[string]$Label){
 $expected=@{};foreach($file in $Inventory.files){$expected[$file.name]=$file.sha256}
 $actual=@(Get-ChildItem $Install -Recurse -File|ForEach-Object {$_.FullName.Substring($Install.TrimEnd('\').Length+1).Replace('\','/')})
 $cache='^mc-cli/python/(.+/)?__pycache__/[^/]+\.pyc$'
 $missing=@($expected.Keys|Where-Object {$actual -notcontains $_ -and $_ -notmatch $cache})
 $extra=@($actual|Where-Object {-not $expected.ContainsKey($_)})
 $summary.observations[$Label+'OptionalBytecodeAbsent']=@($expected.Keys|Where-Object {$actual -notcontains $_ -and $_ -match $cache}).Count
 Assert ($missing.Count -eq 0 -and $extra.Count -eq 0) ('Exact '+$Label+' installed file set')
 foreach($name in $actual){Assert ((Get-FileHash (Join-Path $Install $name) -Algorithm SHA256).Hash.ToLowerInvariant() -eq $expected[$name]) ('Exact '+$Label+' payload: '+$name)}
}
function Effect([string]$Field,$Expected){
 $null=Wait-Until {$v=Get-Content (Join-Path $root 'effect.json') -Raw|ConvertFrom-Json;$v.$Field -eq $Expected} 'Independent installed browser effect' 8 100
}
function Agent-Browser([hashtable]$Request){$Request.browserProfileId=$script:profileId;return Channel-Call $agent $Request}
function Open-BrowserAgent([string]$Reason){
 $value=Open-Channel @('browser') @($script:profileId) $Reason 120 600
 $null=Channel-WaitActive $value 120
 return $value
}
function Element-Reference($Snapshot,[string]$Name){@($Snapshot.data.elements|Where-Object {$_.name -eq $Name})[0].reference}
# Minimal DevTools client for the actor-owned test browser only.
function Cdp-Open([string]$Url){
 $socket=[Net.WebSockets.ClientWebSocket]::new()
 if(-not $socket.ConnectAsync([Uri]$Url,[Threading.CancellationToken]::None).Wait(15000)){throw 'DevTools connection timed out'}
 return [pscustomobject]@{Socket=$socket;Id=0}
}
function Cdp-Call($Client,[string]$Method,[hashtable]$Params=@{}){
 $Client.Id++
 $bytes=[Text.Encoding]::UTF8.GetBytes((@{id=$Client.Id;method=$Method;params=$Params}|ConvertTo-Json -Compress -Depth 10))
 $none=[Threading.CancellationToken]::None
 if(-not $Client.Socket.SendAsync([ArraySegment[byte]]::new($bytes),[Net.WebSockets.WebSocketMessageType]::Text,$true,$none).Wait(15000)){throw 'DevTools send timed out'}
 $buffer=New-Object byte[] 65536
 $deadline=[DateTime]::UtcNow.AddSeconds(60)
 while([DateTime]::UtcNow -lt $deadline){
  $stream=[IO.MemoryStream]::new()
  do{
   $read=$Client.Socket.ReceiveAsync([ArraySegment[byte]]::new($buffer),$none)
   if(-not $read.Wait(60000)){throw 'DevTools receive timed out'}
   $stream.Write($buffer,0,$read.Result.Count)
  }while(-not $read.Result.EndOfMessage)
  $value=[Text.Encoding]::UTF8.GetString($stream.ToArray())|ConvertFrom-Json
  if($value.PSObject.Properties['id'] -and $value.id -eq $Client.Id){
   if($value.PSObject.Properties['error']){throw ('DevTools '+$Method+' failed: '+($value.error|ConvertTo-Json -Compress))}
   return $value.result
  }
 }
 throw 'DevTools reply timed out'
}
function Cdp-Eval($Client,[string]$Expression){(Cdp-Call $Client 'Runtime.evaluate' @{expression=$Expression;returnByValue=$true;awaitPromise=$true}).result.value}
try{
 $inventory=Get-Content $Payload -Raw|ConvertFrom-Json
 $metadata=Get-Content (Join-Path $Install 'runtime\desktop-runtime.json') -Raw|ConvertFrom-Json
 Assert ($metadata.sourceRevision -eq $inventory.sourceRevision) 'Browser package source identity'
 Assert ((Get-Item $operator).VersionInfo.ProductVersion -eq $inventory.version) 'Browser package version'
 Verify-Payload $inventory 'browser'
 foreach($binary in @($operator,$exe)){$signature=Get-AuthenticodeSignature $binary;Assert ($signature.Status -eq 'Valid' -and $signature.SignerCertificate.GetNameInfo('SimpleName',$false) -eq $ExpectedPublisher -and $signature.TimeStamperCertificate) 'Browser package publisher and timestamp'}
 Assert ((Get-Item $Chrome).VersionInfo.ProductName -match 'for Testing|Chromium') 'Separately identified test browser'
 if(-not (Operator)){Start-Process $operator -ArgumentList '--settings'|Out-Null}
 $null=Wait-Until {UiRoot} 'Settings window' 60
 Page 'Access'
 Assert (-not (Switch-State 'Agent access') -and (Refusal 'browser') -eq 'surface_disabled') 'Installed browser access starts off'
 Page 'Permissions'
 Press 'Use bundled extension (Developer mode)';Press 'Copy folder path'
 Assert ([Threading.Thread]::CurrentThread.GetApartmentState() -eq 'STA') 'Installed UI actor uses STA clipboard'
 $extension=Wait-Until {$t=[Windows.Forms.Clipboard]::GetText();if($t -and (Test-Path (Join-Path $t 'manifest.json'))){$t}} 'clipboard extension path' 10
 Assert ($extension -eq (Join-Path $Install 'runtime\browser-extension')) 'Installed setup copies bundled extension path'
 $hostManifest=Get-Content $manifest -Raw|ConvertFrom-Json
 Assert ($hostManifest.path -eq $exe -and $hostManifest.allowed_origins.Count -eq 2 -and $hostManifest.allowed_origins[0] -eq 'chrome-extension://ncbfifkjllmnkkjmomjohinigfgdocjc/' -and $hostManifest.allowed_origins[1] -eq 'chrome-extension://epejchbeajneooefnklikkfhbaeadkpc/') 'Installed setup registers exact host and origins'
 $server=Start-Process $Python -ArgumentList @('-I',('"'+$Fixture+'"'),'--marker',('"'+(Join-Path $root 'effect.json')+'"'),'--port-file',('"'+(Join-Path $root 'port.txt')+'"')) -PassThru -WindowStyle Hidden
 $null=Wait-Until {Test-Path (Join-Path $root 'port.txt')} 'Browser fixture' 10 100
 $url='http://127.0.0.1:'+(Get-Content (Join-Path $root 'port.txt'))+'/'
 $profile=Join-Path $root 'profile'
 $reservation=[Net.Sockets.TcpListener]::new([Net.IPAddress]::Loopback,0);$reservation.Start();$debugPort=$reservation.LocalEndpoint.Port;$reservation.Stop()
 $chromeProcess=Start-Process $Chrome -PassThru -ArgumentList @('--no-first-run','--no-default-browser-check','--disable-background-networking','--disable-component-update',
  ('--remote-debugging-port='+$debugPort),'--remote-allow-origins=*',('--user-data-dir="'+$profile+'"'),('--disable-extensions-except="'+$extension+'"'),('--load-extension="'+$extension+'"'),$url)
 $null=Wait-Until {(Browser-State).connected} 'native messaging connection' 60
 Assert $true 'Installed native messaging connects'
 # Set only extension-local profile availability in the owned test profile.
 $null=Wait-Until {try{Invoke-RestMethod "http://127.0.0.1:$debugPort/json/version" -TimeoutSec 2}catch{$null}} 'test browser DevTools' 60
 $target=Invoke-RestMethod -Method Put "http://127.0.0.1:$debugPort/json/new?about:blank"
 $panel=Cdp-Open $target.webSocketDebuggerUrl
 try{
  $null=Cdp-Call $panel 'Page.navigate' @{url='chrome://extensions/'}
  $null=Wait-Until {(Cdp-Eval $panel "typeof chrome.developerPrivate?.updateProfileConfiguration === 'function'") -eq $true} 'extensions page' 30
  $null=Cdp-Eval $panel 'new Promise(r=>chrome.developerPrivate.updateProfileConfiguration({inDeveloperMode:true},()=>r(true)))'
  $null=Cdp-Call $panel 'Page.navigate' @{url='chrome-extension://ncbfifkjllmnkkjmomjohinigfgdocjc/panel.html'}
  $null=Wait-Until {(Cdp-Eval $panel "!!document.querySelector('#profile-card') && !document.querySelector('#profile-card').hidden") -eq $true} 'extension profile panel' 60
  $null=Cdp-Eval $panel ("document.querySelector('#profile-name').value="+($ProfileName|ConvertTo-Json)+";document.querySelector('#profile-name').dispatchEvent(new Event('change'));document.querySelector('#profile-enabled').checked=true;document.querySelector('#profile-enabled').dispatchEvent(new Event('change'));true")
 }finally{$panel.Socket.Dispose();try{Invoke-RestMethod "http://127.0.0.1:$debugPort/json/close/$($target.id)"|Out-Null}catch{}}
 $entry=Wait-Until {@((Browser-State).profiles|Where-Object {$_.name -eq $ProfileName -and $_.enabled -and $_.connected})[0]} 'enabled extension profile' 60
 $script:profileId=$entry.profileId
 Assert ((Refusal 'browser') -eq 'surface_disabled') 'Extension availability alone grants no browser access'
 Enable-Surface 'browser' 'automatic' 0 @($ProfileName)
 Assert ((@((Browser-State).approvedProfiles) -join ',') -eq $script:profileId) 'Settings approves exactly the chosen profile'
 Assert ((Surface-Live 'browser') -and (Refusal 'browser') -eq 'control_session_required') 'Browser access requires an owned agent task once on'
 $agent=Open-BrowserAgent 'Installed browser acceptance'
 $page=Accepted (Agent-Browser @{operation='browser.navigate';url=$url;newTab=$true});$tab=$page.data.tab.tabId
 $snap=Accepted (Agent-Browser @{operation='browser.snapshot';tabId=$tab;interactiveOnly=$true})
 $button=Element-Reference $snap 'Increment browser counter'
 Accepted (Agent-Browser @{operation='browser.click';reference=$button})|Out-Null
 Effect counter 1;Assert $true 'Independent installed browser counter effect'
 $counter=1
 $text='signed-'+[Guid]::NewGuid().ToString('n')
 Accepted (Agent-Browser @{operation='browser.type';reference=(Element-Reference $snap 'Message');text=$text})|Out-Null
 Accepted (Agent-Browser @{operation='browser.click';reference=(Element-Reference $snap 'Save message')})|Out-Null
 Effect message $text;Assert $true 'Independent installed browser text effect'
 $capture=Accepted (Agent-Browser @{operation='browser.capture';tabId=$tab})
 $capturePath=Join-Path (Call @{operation='status'}).data.artifactRoot ($capture.data.artifactId+'.png')
 Assert ((Get-FileHash $capturePath -Algorithm SHA256).Hash.ToLowerInvariant() -eq $capture.data.sha256) 'Installed browser PNG bytes and hash'
 Remove-Item $capturePath
 Assert ((Accepted (Agent-Browser @{operation='browser.eval';tabId=$tab;expression='document.title'})).data.value -eq 'Machine Control Browser Fixture') 'Browser surface reaches page main world'
 $cdp=Accepted (Agent-Browser @{operation='browser.cdp';tabId=$tab;method='Runtime.evaluate';params=@{expression='document.title';returnByValue=$true}})
 Assert ($cdp.data.result.result.value -eq 'Machine Control Browser Fixture') 'Installed raw CDP method and parameters reach page'
 Page 'Access';Set-Switch 'Agent access' $false
 Assert ((Refusal 'browser') -eq 'surface_disabled') 'Installed UI Stop revokes browser'
 $ended=try{(Channel-Status $agent).state -eq 'ended'}catch{$true}
 Assert $ended 'Installed UI Stop ends the agent task'
 Close-Channel $agent;$agent=$null
 Enable-Surface 'browser' 'automatic' 0 @($ProfileName)
 $agent=Open-BrowserAgent 'Installed browser stale reference'
 Assert ((Agent-Browser @{operation='browser.click';reference=$button}).errorCode -eq 'stale_reference') 'Installed browser old task reference refused'
 Close-Channel $agent;$agent=$null
 Page 'Access';Set-Switch 'Agent access' $false
 $app=Operator
 Page 'Settings';Press 'Restart'
 $replacement=Wait-Until {$p=Operator;if($p -and $p.Id -ne $app.Id){$p}} 'Browser operator restart' 30 100
 Assert $replacement 'Browser operator restarts'
 $null=Wait-Until {UiRoot} 'restarted Settings' 60
 Page 'Access'
 Assert (-not (Switch-State 'Agent access') -and (Refusal 'browser') -eq 'surface_disabled') 'Browser restart retains off-state'
 $null=Wait-Until {(Browser-State).connected} 'extension reconnect after restart' 30
 Assert $true 'Browser extension reconnects after operator restart'
 if($UpdateVersion){
  Assert ($UpdateRevision -and $UpdatePayload) 'Browser update identity supplied'
  Page 'Settings'
  $startup=(Find-Ui 'Start at login' @('CheckBox')).GetCurrentPattern([Windows.Automation.TogglePattern]::Pattern)
  if($startup.Current.ToggleState -ne 'On'){$startup.Toggle();Start-Sleep -Milliseconds 500}
  $startupBefore=[Microsoft.Win32.Registry]::GetValue('HKEY_CURRENT_USER\Software\Microsoft\Windows\CurrentVersion\Run','Machine Control',$null)
  Assert ($startupBefore -match '--background') 'Browser update begins with startup enabled'
  $hostBefore=[IO.File]::ReadAllText($manifest)
  $key=$registry.OpenSubKey($keyPath);try{$registrationBefore=$key.GetValue('')}finally{$key.Dispose()}
  Assert (-not (Plan-Present)) 'No access-resume plan exists before the browser update'
  Enable-Surface 'browser' 'automatic' 0 @($ProfileName)
  $desktopEnabledAt=$null
  if($UpdateDesktopMode -ne 'none'){Enable-Surface 'desktop' $UpdateDesktopMode $UpdateDesktopSeconds;$desktopEnabledAt=[DateTimeOffset]::UtcNow.ToUnixTimeSeconds()}
  Page 'Access'
  $browserBefore=Surface-Ui 'browser';Observe 'browserBefore' $browserBefore
  $desktopBefore=$null
  if($UpdateDesktopMode -ne 'none'){
   $desktopBefore=Surface-Ui 'desktop';Observe 'desktopBefore' $desktopBefore
   if($UpdateDesktopSeconds){$null=Wait-Until {(Surface-Ui 'desktop').remainingMinutes -lt $desktopBefore.remainingMinutes} 'one displayed minute elapsed' 100 10000}
  }
  Assert ($browserBefore.on -and $null -eq $browserBefore.remainingMinutes) 'Browser is on until stopped before update'
  $approvedBefore=@((Browser-State).approvedProfiles)
  # Open the task after the wait: an owner without heartbeats loses its lease.
  $agent=Open-BrowserAgent 'Installed browser update task'
  $epoch=(Call @{operation='status'}).generation
  $beforeUpdate=Accepted (Agent-Browser @{operation='browser.snapshot';tabId=$tab;interactiveOnly=$true})
  $oldReference=Element-Reference $beforeUpdate 'Increment browser counter'
  $button=Check-Update $UpdateVersion
  Assert $button.Current.IsEnabled 'Install and restart is enabled while Browser access is on'
  Assert (Find-Ui '*Access pauses while Machine Control restarts, then turns back on.*' -Like -Seconds 3) 'Settings explains that access pauses and turns back on'
  # Settings polls operator state each second; let it observe the task.
  Start-Sleep -Seconds 3
  $installer={
   $null=Find-Ui 'Install anyway' @('Button')
   $summary.checks+=@('Install with an active agent task asks for confirmation')
   Press 'Install anyway'
  }
  $app=Install-Update $UpdateVersion (Operator).Id $installer
  $null=Wait-Until {UiRoot} 'updated Settings window' 60
  $metadata=Get-Content (Join-Path $Install 'runtime\desktop-runtime.json') -Raw|ConvertFrom-Json
  Assert ($metadata.sourceRevision -eq $UpdateRevision) 'Browser update matches exact new source'
  $updatedInventory=Get-Content $UpdatePayload -Raw|ConvertFrom-Json
  Assert ($updatedInventory.sourceRevision -eq $UpdateRevision -and $updatedInventory.version -eq $UpdateVersion) 'Browser update inventory binds source and version'
  Verify-Payload $updatedInventory 'updated browser'
  $null=Wait-Until {-not (Plan-Present)} 'plan consumed' 30
  Assert $true 'Updated client consumes the one-shot plan file'
  $plan=$summary.observations.plan
  $planBrowser=@($plan.surfaces|Where-Object {$_.surface -eq 'browser'})
  Assert ($plan.targetVersion -eq $UpdateVersion -and $planBrowser.Count -eq 1 -and $planBrowser[0].mode -eq 'automatic' -and $null -eq $planBrowser[0].expiresAt -and (@($planBrowser[0].profileIds) -join ',') -eq $script:profileId) 'Plan records until-stopped Browser access and its exact profile'
  $ended=try{(Channel-Status $agent).state -eq 'ended'}catch{$true}
  Assert $ended 'Install anyway ends the running agent task'
  Close-Channel $agent;$agent=$null
  Page 'Settings'
  Assert (Find-Ui 'Access was turned back on after the update.' -Seconds 150) 'Settings reports that access was turned back on'
  Page 'Access'
  $browserAfter=Surface-Ui 'browser';Observe 'browserAfter' $browserAfter
  Assert ($browserAfter.on -and $browserAfter.beforeStarting -eq $browserBefore.beforeStarting -and $null -eq $browserAfter.remainingMinutes) 'Updated client restores until-stopped Browser access in the same mode'
  Assert ((@((Browser-State).approvedProfiles) -join ',') -eq ($approvedBefore -join ',')) 'Restored Browser approves the same exact profile'
  if($UpdateDesktopMode -ne 'none'){
   $planDesktop=@($plan.surfaces|Where-Object {$_.surface -eq 'desktop'})
   Assert ($planDesktop.Count -eq 1 -and $planDesktop[0].mode -eq $UpdateDesktopMode) 'Plan records the live Desktop mode'
   $desktopAfter=Surface-Ui 'desktop';$afterAt=[DateTimeOffset]::UtcNow.ToUnixTimeSeconds()
   Observe 'desktopAfter' $desktopAfter;Observe 'desktopAfterAtUnix' $afterAt
   Assert ($desktopAfter.on -and $desktopAfter.beforeStarting -eq $desktopBefore.beforeStarting -and (Surface-Live 'desktop')) 'Updated client restores the same Desktop mode'
   if($UpdateDesktopSeconds){
    Observe 'desktopExpectedEndUnix' ($desktopEnabledAt+$UpdateDesktopSeconds);Observe 'desktopPlanEndUnix' $planDesktop[0].expiresAt
    Assert ([Math]::Abs([long]$planDesktop[0].expiresAt-($desktopEnabledAt+$UpdateDesktopSeconds)) -le 5) 'Plan keeps the original Desktop wall-clock end'
    $expected=[int][Math]::Ceiling(([long]$planDesktop[0].expiresAt-$afterAt)/60);Observe 'desktopExpectedRemainingMinutes' $expected
    Assert ([Math]::Abs($desktopAfter.remainingMinutes-$expected) -le 1 -and $desktopAfter.remainingMinutes -lt [int]($UpdateDesktopSeconds/60)) 'Restored timed Desktop access keeps its remaining time, not a reset'
   }
  }
  $codes=@(Update-Diagnostics|ForEach-Object {$_.operation});Observe 'updateDiagnostics' @(Update-Diagnostics)
  Assert ($codes -contains 'update.access.stopped' -and $codes -contains 'update.access.restored' -and $codes -notcontains 'update.access.restore_failed') 'Diagnostics record access stop and restoration'
  Assert ((Call @{operation='status'}).generation -ne $epoch) 'Browser update invalidates old generation'
  Assert ([Microsoft.Win32.Registry]::GetValue('HKEY_CURRENT_USER\Software\Microsoft\Windows\CurrentVersion\Run','Machine Control',$null) -eq $startupBefore) 'Signed update preserves exact startup entry'
  $key=$registry.OpenSubKey($keyPath);try{Assert ($key.GetValue('') -eq $registrationBefore) 'Signed update preserves browser registration'}finally{$key.Dispose()}
  Assert ([IO.File]::ReadAllText($manifest) -ceq $hostBefore) 'Signed update preserves exact browser manifest'
  Assert ($null -ne (Get-Process -Id $chromeProcess.Id -ErrorAction SilentlyContinue)) 'User browser survives signed update'
  $null=Wait-Until {(Browser-State).connected} 'extension reconnect after update' 30
  Assert $true 'Extension reconnects after signed update'
  $agent=Open-BrowserAgent 'Installed browser after update'
  Assert ((Agent-Browser @{operation='browser.click';reference=$oldReference}).errorCode -eq 'stale_reference') 'Updated browser refuses pre-update reference'
  Effect counter $counter
  Assert ((Accepted (Agent-Browser @{operation='browser.eval';tabId=$tab;expression='document.title'})).data.value -eq 'Machine Control Browser Fixture') 'Updated browser retains original page'
  $fresh=Accepted (Agent-Browser @{operation='browser.snapshot';tabId=$tab;interactiveOnly=$true})
  Accepted (Agent-Browser @{operation='browser.click';reference=(Element-Reference $fresh 'Increment browser counter')})|Out-Null
  Effect counter ($counter+1);Assert $true 'Independent browser effect after signed replacement'
  Close-Channel $agent;$agent=$null
  Page 'Access';Set-Switch 'Agent access' $false
 }
 if($StartupRecovery){
  Page 'Settings'
  $startup=(Find-Ui 'Start at login' @('CheckBox')).GetCurrentPattern([Windows.Automation.TogglePattern]::Pattern)
  if($startup.Current.ToggleState -ne 'On'){$startup.Toggle();Start-Sleep -Milliseconds 500}
  Assert ([Microsoft.Win32.Registry]::GetValue('HKEY_CURRENT_USER\Software\Microsoft\Windows\CurrentVersion\Run','Machine Control',$null) -match '--background') 'Startup recovery entry enabled'
  $summary.startupRecoveryPending=$true
  Page 'Access'
 }
 & $exe browser-unregister
 $key=$registry.OpenSubKey($keyPath)
 try{Assert ($null -eq $key -and -not(Test-Path $manifest)) 'Owned browser unregister removes registry and manifest'}finally{if($key){$key.Dispose()}}
 $summary.passed=$true
}catch{$summary.error=$_.Exception.Message;$summary.location=$_.ScriptStackTrace;throw}
finally{
 Close-Channel $agent
 try{if(UiRoot){Page 'Access';if(Switch-State 'Agent access'){Set-Switch 'Agent access' $false}}}catch{$summary.cleanupError=$_.Exception.Message}
 $app=Operator;if($app){Stop-Process -Id $app.Id -ErrorAction SilentlyContinue}
 if($profile){Get-CimInstance Win32_Process|Where-Object {$_.Name -eq 'chrome.exe' -and $_.CommandLine -like ('*'+(Split-Path $root -Leaf)+'*')}|ForEach-Object {Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue}}
 if($server -and -not $server.HasExited){$server.Kill();$server.WaitForExit()}
 if($oldValue){$key=$registry.CreateSubKey($keyPath);$key.SetValue('',$oldValue);$key.Dispose()}else{$registry.DeleteSubKeyTree($keyPath,$false)}
 if($oldManifest){[IO.File]::WriteAllBytes($manifest,$oldManifest)}elseif(Test-Path $manifest){Remove-Item $manifest}
 $registry.Dispose()
 $deadline=[DateTime]::UtcNow.AddSeconds(30)
 do{try{Remove-Item $root -Recurse -Force;break}catch{Start-Sleep -Milliseconds 250}}while([DateTime]::UtcNow -lt $deadline)
 if(Test-Path $root){$summary.cleanupError=$true;$summary.passed=$false}
 $summary|ConvertTo-Json -Depth 10|Set-Content $EvidencePath -Encoding UTF8
}
