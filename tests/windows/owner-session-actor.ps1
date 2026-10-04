# Independent interactive-session test actor. It operates the real operator UI;
# agent requests never receive access to its command mailbox or authority.
param(
 [Parameter(Mandatory=$true)][string]$Install,
 [Parameter(Mandatory=$true)][string]$Mailbox,
 [Parameter(Mandatory=$true)][string]$Chrome,
 [Parameter(Mandatory=$true)][string]$BrowserFixture
)
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
Add-Type -AssemblyName UIAutomationClient,UIAutomationTypes
$app=$null;$browser=$null;$server=$null;$setup=$false
New-Item -ItemType Directory $Mailbox -Force|Out-Null
$registry=[Microsoft.Win32.RegistryKey]::OpenBaseKey([Microsoft.Win32.RegistryHive]::CurrentUser,[Microsoft.Win32.RegistryView]::Registry32)
$keyPath='Software\Google\Chrome\NativeMessagingHosts\org.machine_control.browser'
$old=$registry.OpenSubKey($keyPath);$oldValue=if($old){$old.GetValue('')}else{$null};if($old){$old.Dispose()}
$manifest=Join-Path $env:LOCALAPPDATA 'MachineControl\packages\desktop\browser-host.json'
$oldManifest=if(Test-Path $manifest){[IO.File]::ReadAllBytes($manifest)}else{$null}
function Element([string]$Name,[string]$Type='Button') {
 $deadline=[DateTime]::UtcNow.AddSeconds(12)
 do {
  $app.Refresh()
  if($app.MainWindowHandle -ne [IntPtr]::Zero){
   $root=[Windows.Automation.AutomationElement]::FromHandle($app.MainWindowHandle)
   $conditions=[Windows.Automation.Condition[]]@(
    [Windows.Automation.PropertyCondition]::new([Windows.Automation.AutomationElement]::NameProperty,$Name),
    [Windows.Automation.PropertyCondition]::new([Windows.Automation.AutomationElement]::ControlTypeProperty,[Windows.Automation.ControlType]::$Type),
    [Windows.Automation.PropertyCondition]::new([Windows.Automation.AutomationElement]::IsOffscreenProperty,$false),
    [Windows.Automation.PropertyCondition]::new([Windows.Automation.AutomationElement]::IsEnabledProperty,$true))
   $item=$root.FindFirst([Windows.Automation.TreeScope]::Descendants,[Windows.Automation.AndCondition]::new($conditions))
   if($item){return $item}
  }
  Start-Sleep -Milliseconds 100
 }while([DateTime]::UtcNow -lt $deadline)
 throw "Operator UI unavailable: $Name"
}
function Press([string]$Name){(Element $Name).GetCurrentPattern([Windows.Automation.InvokePattern]::Pattern).Invoke();Start-Sleep -Milliseconds 400}
function Reply($value){
 $temp=Join-Path $Mailbox 'reply.tmp'
 [IO.File]::WriteAllText($temp,($value|ConvertTo-Json -Depth 20 -Compress))
 Move-Item $temp (Join-Path $Mailbox 'reply.json') -Force
}
try {
 if(@(Get-Process machine-control -ErrorAction SilentlyContinue).Count){throw 'Close the existing desktop app before this isolated acceptance run'}
 if((Get-Item $Chrome).VersionInfo.ProductName -notmatch 'Chrome for Testing|Chromium'){throw 'A separately identified test browser is required'}
 New-Item -ItemType Directory $Mailbox -Force|Out-Null
 $env:WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS='--force-renderer-accessibility'
 $app=Start-Process (Join-Path $Install 'machine-control.exe') -ArgumentList '--gui' -WindowStyle Maximized -PassThru
 Press 'Access'
 Reply @{id='ready';ok=$true;processId=$PID;appProcessId=$app.Id}
 $deadline=[DateTime]::UtcNow.AddMinutes(30)
 $quit=$false
 while(-not $quit -and [DateTime]::UtcNow -lt $deadline){
  $path=Join-Path $Mailbox 'request.json'
  if(-not(Test-Path $path)){Start-Sleep -Milliseconds 100;continue}
  $request=Get-Content $path -Raw|ConvertFrom-Json
  Remove-Item $path
  $reply=@{id=$request.id;ok=$true}
  try {
   switch($request.action){
    'arm' {
     Press 'Access'
     foreach($name in @('View desktop','Control apps and input','Browser tabs','Browser scripts and DevTools')){
      $pattern=(Element $name 'CheckBox').GetCurrentPattern([Windows.Automation.TogglePattern]::Pattern)
      if($pattern.Current.ToggleState -ne [Windows.Automation.ToggleState]::On){$pattern.Toggle()}
     }
     Press 'Enable access'
    }
    'pause' {Press 'Access';Press 'Pause access'}
    'resume' {Press 'Access';Press 'Resume access'}
    'stop' {Press 'Access';Press 'Stop access'}
    'browser' {
     Press 'Permissions';$setup=$true;Press 'Set up browser extension'
     $extension=Join-Path $Install 'runtime\browser-extension'
     $server=Start-Process (Get-Command python.exe).Source -ArgumentList @(('"'+$BrowserFixture+'"'),'--marker',('"'+(Join-Path $Mailbox 'browser-effect.json')+'"'),'--port-file',('"'+(Join-Path $Mailbox 'browser-port.txt')+'"')) -PassThru -WindowStyle Hidden
     $ready=[DateTime]::UtcNow.AddSeconds(15)
     while(-not(Test-Path (Join-Path $Mailbox 'browser-port.txt'))){if([DateTime]::UtcNow -gt $ready){throw 'Browser fixture start timed out'};Start-Sleep -Milliseconds 100}
     $url='http://127.0.0.1:'+(Get-Content (Join-Path $Mailbox 'browser-port.txt'))+'/'
     $profile=Join-Path $Mailbox 'browser-profile'
     $browser=Start-Process $Chrome -ArgumentList @('--no-first-run','--no-default-browser-check',('--user-data-dir="'+$profile+'"'),('--load-extension="'+$extension+'"'),$url) -PassThru
     $reply.url=$url
     Press 'Access'
    }
    'quit' {$quit=$true}
    default {throw 'Unsupported test actor action'}
   }
  } catch {$reply.ok=$false;$reply.error=$_.Exception.Message}
  Reply $reply
 }
} catch {Reply @{id='ready';ok=$false;error=$_.Exception.ToString()}}
finally {
 if($app -and -not $app.HasExited){try{Press 'Access';Press 'Stop access'}catch{};Stop-Process -Id $app.Id -ErrorAction SilentlyContinue}
 if($browser){Get-CimInstance Win32_Process|Where-Object {$_.ExecutablePath -eq $Chrome -and $_.CommandLine -like ('*'+$Mailbox+'*')}|ForEach-Object {Stop-Process -Id $_.ProcessId -ErrorAction SilentlyContinue}}
 if($server -and -not $server.HasExited){Stop-Process -Id $server.Id -ErrorAction SilentlyContinue}
 if($setup){
  if($null -ne $oldValue){$key=$registry.CreateSubKey($keyPath);$key.SetValue('',$oldValue);$key.Dispose()}else{$registry.DeleteSubKeyTree($keyPath,$false)}
  if($null -ne $oldManifest){[IO.File]::WriteAllBytes($manifest,$oldManifest)}elseif(Test-Path $manifest){Remove-Item $manifest}
 }
 $registry.Dispose()
 [IO.File]::WriteAllText((Join-Path $Mailbox 'closed.json'),'{"closed":true}')
}
