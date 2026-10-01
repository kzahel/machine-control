# Run in the interactive session, using only a separately identified test browser.
param([Parameter(Mandatory=$true)][string]$Executable,
 [Parameter(Mandatory=$true)][string]$Chrome,
 [Parameter(Mandatory=$true)][string]$Fixture,
 [Parameter(Mandatory=$true)][string]$EvidencePath)
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
$summary=[ordered]@{schema='machine-control-windows-browser-probe/v0';passed=$false}
$runtime=$null;$browser=$null;$server=$null;$profile=$null
$root=Join-Path (Split-Path $EvidencePath) ('browser-'+[Guid]::NewGuid().ToString('n'))
New-Item -ItemType Directory $root|Out-Null
$registry=[Microsoft.Win32.RegistryKey]::OpenBaseKey([Microsoft.Win32.RegistryHive]::CurrentUser,[Microsoft.Win32.RegistryView]::Registry32)
$keyPath='Software\Google\Chrome\NativeMessagingHosts\org.machine_control.browser'
$old=$registry.OpenSubKey($keyPath);$oldValue=if($old){$old.GetValue('')}else{$null};if($old){$old.Dispose()}
$manifest=Join-Path $env:LOCALAPPDATA 'MachineControl\packages\desktop\browser-host.json'
$oldManifest=if(Test-Path $manifest){[IO.File]::ReadAllBytes($manifest)}else{$null}
function Assert($Value,[string]$Message){if(-not $Value){throw $Message};$summary[$Message]=$true}
function Operator($Value){$runtime.StandardInput.WriteLine(($Value|ConvertTo-Json -Depth 20 -Compress));$runtime.StandardInput.Flush();$line=$runtime.StandardOutput.ReadLineAsync();if(-not $line.Wait(10000)){throw 'Operator reply timeout'};if($null -eq $line.Result){throw ('Operator exited: '+$runtime.StandardError.ReadToEnd())};$line.Result|ConvertFrom-Json}
function Call($Value){$Value|ConvertTo-Json -Depth 20 -Compress|& $Executable call --profile user --instance desktop --session-id ([Diagnostics.Process]::GetCurrentProcess().SessionId)|ConvertFrom-Json}
function BeginCall($Value){
 $start=[Diagnostics.ProcessStartInfo]::new($Executable,('call --profile user --instance desktop --session-id '+[Diagnostics.Process]::GetCurrentProcess().SessionId))
 $start.UseShellExecute=$false;$start.CreateNoWindow=$true;$start.RedirectStandardInput=$true;$start.RedirectStandardOutput=$true;$start.RedirectStandardError=$true
 $p=[Diagnostics.Process]::Start($start);$p.StandardInput.WriteLine(($Value|ConvertTo-Json -Depth 20 -Compress));$p.StandardInput.Close();return $p
}
function FinishCall($Process){if(-not $Process.WaitForExit(20000)){$Process.Kill();throw 'Call completion timeout'};$Process.StandardOutput.ReadToEnd()|ConvertFrom-Json}
function Pending(){ $deadline=[DateTime]::UtcNow.AddSeconds(5);do{$state=(Operator @{method='state'}).state;if($state.pending){return $state.pending};Start-Sleep -Milliseconds 100}while([DateTime]::UtcNow -lt $deadline);throw 'Approval request unavailable' }
function Accepted($Value){if(-not $Value.accepted){throw ('Browser operation refused: '+$Value.errorCode)};return $Value}
function Snapshot([int]$Tab){Accepted (Call @{operation='browser.snapshot';tabId=$Tab;interactiveOnly=$true})}
function Ref($Snapshot,[string]$Name){@($Snapshot.data.elements|Where-Object {$_.name -eq $Name})[0].reference}
function Effect([string]$Field,$Expected){$deadline=[DateTime]::UtcNow.AddSeconds(8);do{$v=Get-Content (Join-Path $root 'effect.json') -Raw|ConvertFrom-Json;if($v.$Field -eq $Expected){return};Start-Sleep -Milliseconds 100}while([DateTime]::UtcNow -lt $deadline);throw 'Independent fixture effect absent'}
try {
 $start=[Diagnostics.ProcessStartInfo]::new($Executable,'desktop');$start.UseShellExecute=$false;$start.CreateNoWindow=$true;$start.RedirectStandardInput=$true;$start.RedirectStandardOutput=$true;$start.RedirectStandardError=$true
 $runtime=[Diagnostics.Process]::Start($start)
 $runtime.StandardInput.WriteLine((@{method='hello';processId=$PID}|ConvertTo-Json -Compress));$runtime.StandardInput.Flush()
 $hello=$runtime.StandardOutput.ReadLineAsync()
 Assert ($hello.Wait(10000) -and ($hello.Result|ConvertFrom-Json).ok) 'Private operator handshake'
 Assert ((Call @{operation='browser.tabs'}).errorCode -eq 'approval_required') 'Browser off-state refusal'
 # An arbitrary same-user executable is not a trusted provider.
 $status=Accepted (Call @{operation='status'})
 $sid=[Security.Principal.WindowsIdentity]::GetCurrent().User.Value
 $pipe=[IO.Pipes.NamedPipeClientStream]::new('.','machine-control-user-'+$sid+'-'+[Diagnostics.Process]::GetCurrentProcess().SessionId+'-desktop-browser',[IO.Pipes.PipeDirection]::InOut)
 try {$pipe.Connect(3000);$buffer=[byte[]]::new(4);$read=$pipe.ReadAsync($buffer,0,4);Assert ($read.Wait(6000) -and $read.Result -eq 0) 'Untrusted provider rejected before frame read'}finally{$pipe.Dispose()}
 Assert (Operator @{method='browser.setup'}).ok 'Native messaging registration'
 $p=Start-Process $Executable -ArgumentList 'chrome-extension://aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa/' -Wait -PassThru -WindowStyle Hidden
 Assert ($p.ExitCode -ne 0) 'Wrong extension origin refused'
 $server=Start-Process (Get-Command python.exe).Source -ArgumentList @(('"'+$Fixture+'"'),'--marker',('"'+(Join-Path $root 'effect.json')+'"'),'--port-file',('"'+(Join-Path $root 'port.txt')+'"')) -PassThru -WindowStyle Hidden
 $deadline=[DateTime]::UtcNow.AddSeconds(10);while(-not(Test-Path (Join-Path $root 'port.txt'))){if([DateTime]::UtcNow -gt $deadline){throw 'Fixture server unavailable'};Start-Sleep -Milliseconds 100}
 $url='http://127.0.0.1:'+(Get-Content (Join-Path $root 'port.txt'))+'/'
 $extension=Join-Path (Split-Path $Executable) 'browser-extension'
 $profile=Join-Path $root 'profile'
 $browser=Start-Process $Chrome -ArgumentList @('--no-first-run','--no-default-browser-check',('--user-data-dir="'+$profile+'"'),('--load-extension="'+$extension+'"'),$url) -PassThru
 $deadline=[DateTime]::UtcNow.AddSeconds(30)
 do{$state=(Operator @{method='state'}).state;if($state.browser.connected){break};Start-Sleep -Milliseconds 250}while([DateTime]::UtcNow -lt $deadline)
 Assert $state.browser.connected 'Chrome native provider connected'
 Assert (Operator @{method='arm';scopes=@('browser');duration=900}).ok 'Browser-only grant'
 $summary.initialTabs=(Accepted (Call @{operation='browser.tabs'})).data.tabs
 Accepted (Call @{operation='browser.navigate';url=$url;newTab=$true})|Out-Null
 $deadline=[DateTime]::UtcNow.AddSeconds(15)
 do{$tabs=Accepted (Call @{operation='browser.tabs'});$matches=@($tabs.data.tabs|Where-Object {$_.url -eq $url});if($matches.Count){break};Start-Sleep -Milliseconds 200}while([DateTime]::UtcNow -lt $deadline)
 if(-not $matches.Count){$summary.fixtureUrl=$url;$summary.tabs=$tabs.data.tabs;throw 'Fixture tab did not settle'}
 $tab=$matches[0].tabId
 Accepted (Call @{operation='browser.wait';tabId=$tab})|Out-Null
 Assert ((Call @{operation='browser.eval';tabId=$tab;expression='document.title'}).errorCode -eq 'approval_required') 'Browser scope refuses raw evaluation'
 $snap=Snapshot $tab
 Accepted (Call @{operation='browser.click';reference=(Ref $snap 'Increment browser counter')})|Out-Null
 Effect counter 1;Assert $true 'Independent browser counter effect'
 $text='fixture-'+[Guid]::NewGuid().ToString('n')
 Accepted (Call @{operation='browser.type';reference=(Ref $snap 'Message');text=$text})|Out-Null
 Accepted (Call @{operation='browser.click';reference=(Ref $snap 'Save message')})|Out-Null
 Effect message $text;Assert $true 'Independent browser text effect'
 $capture=Accepted (Call @{operation='browser.capture';tabId=$tab})
 $path=Join-Path $status.data.artifactRoot ($capture.data.artifactId+'.png')
 Assert ((Get-FileHash $path -Algorithm SHA256).Hash.ToLowerInvariant() -eq $capture.data.sha256) 'Browser capture artifact hash'
 Remove-Item $path
 $fresh=Snapshot $tab
 Assert ((Call @{operation='browser.click';reference=(Ref $snap 'Increment browser counter')}).errorCode -eq 'stale_reference') 'Snapshot superseded reference refusal'
 Assert ((Call @{operation='browser.navigate';url='file:///C:/Windows/win.ini';tabId=$tab}).errorCode -eq 'url_not_permitted') 'File URL refused'
 $pendingCall=BeginCall @{operation='grant.request';scopes=@('browser','devtools');durationSeconds=900;timeoutSeconds=15;reason='Browser fixture DevTools request'}
 $pending=Pending
 Assert ((Call @{operation='browser.click';reference=(Ref $fresh 'Increment browser counter')}).errorCode -eq 'approval_prompt_visible') 'Approval prompt pauses browser writes'
 Assert (Call @{operation='browser.tabs'}).accepted 'Browser observation during prompt'
 Effect counter 1
 Assert (Operator @{method='decision';id=$pending.id;allow=$false}).ok 'Browser grant denied'
 Assert ((FinishCall $pendingCall).errorCode -eq 'approval_denied') 'Browser requester observes denial'
 $pendingCall=BeginCall @{operation='grant.request';scopes=@('browser','devtools');durationSeconds=900;timeoutSeconds=15;reason='Browser fixture narrow approval'}
 $pending=Pending
 Assert (Operator @{method='decision';id=$pending.id;allow=$true;scopes=@('browser');duration=60}).ok 'Browser approval narrows authority'
 Assert (FinishCall $pendingCall).accepted 'Browser requester observes narrowed approval'
 Assert ((Call @{operation='browser.eval';tabId=$tab;expression='document.title'}).errorCode -eq 'approval_required') 'Narrowed approval excludes DevTools'
 $pendingCall=BeginCall @{operation='grant.request';scopes=@('devtools');durationSeconds=60;timeoutSeconds=5;reason='Browser fixture timeout'}
 Pending|Out-Null
 Assert ((FinishCall $pendingCall).errorCode -eq 'approval_timeout') 'Live browser approval timeout'
 Assert (Operator @{method='stop'}).ok 'Browser Stop'
 Assert ((Call @{operation='browser.tabs'}).errorCode -eq 'approval_required') 'Stop revokes browser authority'
 Assert (Operator @{method='arm';scopes=@('devtools');duration=300}).ok 'Separate raw DevTools grant'
 Assert ((Call @{operation='browser.click';reference=(Ref $fresh 'Increment browser counter')}).errorCode -eq 'stale_reference') 'Old grant reference refusal'
 $title=Accepted (Call @{operation='browser.eval';tabId=$tab;expression='document.title'})
 Assert ($title.data.value -eq 'Machine Control Browser Fixture') 'Raw evaluation reaches page main world'
 $loaded=Accepted (Call @{operation='browser.navigate';tabId=$tab;url=($url+'next')})
 Assert ($loaded.data.loaded) 'Navigation load observed'
 Assert ((Accepted (Call @{operation='browser.eval';tabId=$tab;expression='document.title'})).data.value -eq 'Next fixture page') 'Navigation independent page title'
 $timeout=Call @{operation='browser.eval';tabId=$tab;expression='new Promise(()=>{})';timeoutMs=1000}
 Assert (-not $timeout.accepted -and $timeout.delivery -eq 'unknown' -and $timeout.retrySafety -eq 'unsafe_delivery_unknown') 'Browser timeout reports uncertain delivery without replay'
 # Close only the dedicated browser, then test provider reconnect within the
 # same native grant. Provider epochs must invalidate references independently.
 $before=Accepted (Call @{operation='browser.snapshot';tabId=$tab;interactiveOnly=$false})
 $owned=@(Get-CimInstance Win32_Process|Where-Object {$_.Name -eq 'chrome.exe' -and $_.CommandLine -like ('*'+(Split-Path $root -Leaf)+'*')})
 foreach($p in $owned){Stop-Process -Id $p.ProcessId -Force -ErrorAction SilentlyContinue}
 foreach($p in $owned){$process=Get-Process -Id $p.ProcessId -ErrorAction SilentlyContinue;if($process){$null=$process.WaitForExit(10000)}}
 $deadline=[DateTime]::UtcNow.AddSeconds(10);do{$state=(Operator @{method='state'}).state;if(-not $state.browser.connected){break};Start-Sleep -Milliseconds 100}while([DateTime]::UtcNow -lt $deadline)
 Assert ((Call @{operation='browser.tabs'}).errorCode -eq 'browser_provider_unavailable') 'Browser disconnect refuses without fallback'
 $profile=Join-Path $root 'profile-restart'
 $browser=Start-Process $Chrome -ArgumentList @('--no-first-run','--no-default-browser-check',('--user-data-dir="'+$profile+'"'),('--load-extension="'+$extension+'"')) -PassThru
 $deadline=[DateTime]::UtcNow.AddSeconds(30);do{$state=(Operator @{method='state'}).state;if($state.browser.connected){break};Start-Sleep -Milliseconds 200}while([DateTime]::UtcNow -lt $deadline)
 if(-not $state.browser.connected){$summary.reconnectState=$state.browser}
 Assert $state.browser.connected 'Browser provider reconnects'
 # Navigation changed the fixture page, so no assumption about element names.
 $oldReference=@($before.data.elements)[0].reference
 Assert ((Call @{operation='browser.click';reference=$oldReference}).errorCode -eq 'stale_reference') 'Provider restart invalidates references'
 Assert (Operator @{method='stop'}).ok 'Stop before expiry probe'
 Assert (Operator @{method='arm';scopes=@('devtools');duration=60}).ok 'Bounded expiry grant'
 Start-Sleep -Seconds 61
 Assert ((Call @{operation='browser.eval';tabId=$tab;expression='document.title'}).errorCode -eq 'approval_required') 'Live DevTools grant expiry'
 $summary.passed=$true
} catch {$summary.error=$_.Exception.Message;$summary.location=$_.ScriptStackTrace;throw}
finally {
 if($runtime -and -not $runtime.HasExited){try{Operator @{method='quit'}|Out-Null}catch{};if(-not $runtime.WaitForExit(10000)){$runtime.Kill()}}
 # The native host must exit on app shutdown even while Chrome stays alive.
 $deadline=[DateTime]::UtcNow.AddSeconds(8)
 do{$hosts=@(Get-CimInstance Win32_Process|Where-Object {$_.Name -eq 'machine-control-windows.exe' -and $_.CommandLine -like '*chrome-extension://*' -and $_.ExecutablePath -eq $Executable});if(-not $hosts.Count){break};Start-Sleep -Milliseconds 100}while([DateTime]::UtcNow -lt $deadline)
 if($hosts.Count){$summary.nativeHostCleanupError=$true;$summary.passed=$false}

 # Chrome's launcher PID can exit while its browser process survives.
 $owned=if($profile){@(Get-CimInstance Win32_Process|Where-Object {$_.Name -eq 'chrome.exe' -and $_.CommandLine -like ('*'+(Split-Path $root -Leaf)+'*')})}else{@()}
 foreach($p in $owned){Stop-Process -Id $p.ProcessId -Force -ErrorAction SilentlyContinue}
 foreach($p in $owned){$process=Get-Process -Id $p.ProcessId -ErrorAction SilentlyContinue;if($process){$null=$process.WaitForExit(10000)}}
 if($server -and -not $server.HasExited){$server.Kill();$server.WaitForExit()}
 if($oldValue){$k=$registry.CreateSubKey($keyPath);$k.SetValue('',$oldValue);$k.Dispose()}else{$registry.DeleteSubKeyTree($keyPath,$false)}
 if($oldManifest){[IO.File]::WriteAllBytes($manifest,$oldManifest)}elseif(Test-Path $manifest){Remove-Item $manifest}
 $registry.Dispose()
 $summary|ConvertTo-Json -Depth 10|Set-Content $EvidencePath -Encoding UTF8
 if(Test-Path $root){
  $deadline=[DateTime]::UtcNow.AddSeconds(30)
  do{try{Remove-Item $root -Recurse -Force;break}catch{Start-Sleep -Milliseconds 250}}while([DateTime]::UtcNow -lt $deadline)
  if(Test-Path $root){$summary.cleanupError='Owned browser profile could not be removed';$summary.passed=$false}
 }
 $summary|ConvertTo-Json -Depth 10|Set-Content $EvidencePath -Encoding UTF8
}
