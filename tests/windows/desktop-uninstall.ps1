# Independent actor for ordinary uninstall with Chrome and a user app open.
param([Parameter(Mandatory=$true)][string]$Install,
 [Parameter(Mandatory=$true)][string]$Chrome,
 [Parameter(Mandatory=$true)][string]$Fixture,
 [Parameter(Mandatory=$true)][string]$ExpectedRevision,
 [Parameter(Mandatory=$true)][string]$EvidencePath)
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
Add-Type -AssemblyName UIAutomationClient,UIAutomationTypes
$summary=[ordered]@{schema='machine-control-windows-desktop-uninstall/v0';passed=$false;checks=@()}
$operator=Join-Path $Install 'machine-control.exe'
$exe=Join-Path $Install 'runtime\machine-control-windows.exe'
$root=Join-Path (Split-Path $EvidencePath) ('uninstall-'+[Guid]::NewGuid().ToString('n'))
$app=$null;$fixtureApp=$null;$uninstaller=$null
$manifest=Join-Path $env:LOCALAPPDATA 'MachineControl\packages\desktop\browser-host.json'
$registry=[Microsoft.Win32.RegistryKey]::OpenBaseKey([Microsoft.Win32.RegistryHive]::CurrentUser,[Microsoft.Win32.RegistryView]::Registry32)
$keyPath='Software\Google\Chrome\NativeMessagingHosts\org.machine_control.browser'
function Assert($Value,[string]$Message){if(-not $Value){throw $Message};$summary.checks+=@($Message)}
function Call($Value){$Value|ConvertTo-Json -Compress|& $exe call --profile user --instance desktop --session-id ([Diagnostics.Process]::GetCurrentProcess().SessionId)|ConvertFrom-Json}
function Element([string]$Name,[string]$Type='Button'){
 $deadline=[DateTime]::UtcNow.AddSeconds(12)
 do{
  $app.Refresh()
  if($app.MainWindowHandle -ne [IntPtr]::Zero){
   $ui=[Windows.Automation.AutomationElement]::FromHandle($app.MainWindowHandle)
   $conditions=[Windows.Automation.Condition[]]@(
    [Windows.Automation.PropertyCondition]::new([Windows.Automation.AutomationElement]::NameProperty,$Name),
    [Windows.Automation.PropertyCondition]::new([Windows.Automation.AutomationElement]::ControlTypeProperty,[Windows.Automation.ControlType]::$Type),
    [Windows.Automation.PropertyCondition]::new([Windows.Automation.AutomationElement]::IsOffscreenProperty,$false))
   $item=$ui.FindFirst([Windows.Automation.TreeScope]::Descendants,[Windows.Automation.AndCondition]::new($conditions))
   if($item){return $item}
  };Start-Sleep -Milliseconds 100
 }while([DateTime]::UtcNow -lt $deadline)
 throw ('Uninstall setup UI unavailable: '+$Name)
}
function Press([string]$Name){(Element $Name).GetCurrentPattern([Windows.Automation.InvokePattern]::Pattern).Invoke();Start-Sleep -Milliseconds 400}
try{
 $metadata=Get-Content (Join-Path $Install 'runtime\desktop-runtime.json') -Raw|ConvertFrom-Json
 Assert ($metadata.sourceRevision -eq $ExpectedRevision) 'Uninstall binds exact accepted source'
 $key=$registry.OpenSubKey($keyPath)
 try{Assert ($null -eq $key -and -not(Test-Path $manifest) -and -not(Test-Path ($manifest+'.updating'))) 'Uninstall fixture starts without another browser registration'}finally{if($key){$key.Dispose()}}
 New-Item -ItemType Directory $root|Out-Null
 $app=Start-Process $operator -PassThru
 Press 'Permissions';Press 'Set up'
 Assert ((Get-Content $manifest -Raw|ConvertFrom-Json).path -eq $exe) 'Uninstall begins with owned browser registration'
 Press 'Settings'
 $startup=(Element 'Start at login' 'CheckBox').GetCurrentPattern([Windows.Automation.TogglePattern]::Pattern)
 if($startup.Current.ToggleState -ne 'On'){$startup.Toggle();Start-Sleep -Milliseconds 500}
 $profile=Join-Path $root 'profile';$extension=Join-Path $Install 'runtime\browser-extension'
 Start-Process $Chrome -ArgumentList @('--no-first-run','--no-default-browser-check',('--user-data-dir="'+$profile+'"'),('--load-extension="'+$extension+'"'))|Out-Null
 $deadline=[DateTime]::UtcNow.AddSeconds(30)
 do{$connected=(Call @{operation='capabilities'}).data.browser.connected;if($connected){break};Start-Sleep -Milliseconds 200}while([DateTime]::UtcNow -lt $deadline)
 Assert $connected 'Chrome native host is connected before ordinary uninstall'
 $browser=@(Get-CimInstance Win32_Process|Where-Object {$_.Name -eq 'chrome.exe' -and $_.CommandLine -like ('*'+(Split-Path $root -Leaf)+'*') -and $_.CommandLine -notmatch '--type='})[0].ProcessId
 $fixtureApp=Start-Process $Fixture -PassThru
 $uninstaller=Start-Process (Join-Path $Install 'uninstall.exe') -ArgumentList '/S' -PassThru
 # The NSIS temporary-copy bootstrap's exit alone is not completion evidence.
 # Independently check payload, registration and process effects below.
 Assert ($uninstaller.WaitForExit(60000) -and $uninstaller.ExitCode -eq 0) 'Ordinary signed uninstaller process exits with connected Chrome'
 $deadline=[DateTime]::UtcNow.AddSeconds(10)
 do{
  $files=@(if(Test-Path $Install){Get-ChildItem $Install -Recurse -File})
  if(-not $files.Count){break};Start-Sleep -Milliseconds 200
 }while([DateTime]::UtcNow -lt $deadline)
 Assert (-not $files.Count) 'Ordinary uninstall removes all owned payload files'
 # Chrome can keep a directory watcher open for its unpacked extension even
 # after every file is gone. Report that separately from leftover payload.
 $summary.emptyInstallationDirectoriesRemain=Test-Path $Install
 # The bootstrap can finish before its relocated child reaches POSTUNINSTALL.
 # Wait for the independent registration/startup/process effects as well.
 $deadline=[DateTime]::UtcNow.AddSeconds(15)
 do{
  $key=$registry.OpenSubKey($keyPath);$registered=$null -ne $key;if($key){$key.Dispose()}
  $entry=[Microsoft.Win32.Registry]::GetValue('HKEY_CURRENT_USER\Software\Microsoft\Windows\CurrentVersion\Run','Machine Control',$null)
  $running=$null -ne (Get-Process -Id $app.Id -ErrorAction SilentlyContinue)
  if(-not $registered -and -not(Test-Path $manifest) -and -not(Test-Path ($manifest+'.updating')) -and $null -eq $entry -and -not $running){break}
  Start-Sleep -Milliseconds 200
 }while([DateTime]::UtcNow -lt $deadline)
 $key=$registry.OpenSubKey($keyPath)
 try{Assert ($null -eq $key -and -not(Test-Path $manifest) -and -not(Test-Path ($manifest+'.updating'))) 'Ordinary uninstall removes owned browser registration'}finally{if($key){$key.Dispose()}}
 $entry=[Microsoft.Win32.Registry]::GetValue('HKEY_CURRENT_USER\Software\Microsoft\Windows\CurrentVersion\Run','Machine Control',$null)
 Assert ($null -eq $entry) 'Ordinary uninstall removes owned login startup'
 Assert ($null -eq (Get-Process -Id $app.Id -ErrorAction SilentlyContinue)) 'Uninstall stops the owned operator'
 Assert ($null -ne (Get-Process -Id $browser -ErrorAction SilentlyContinue)) 'User browser survives ordinary uninstall'
 Assert (-not $fixtureApp.HasExited) 'Independent user application survives ordinary uninstall'
 $summary.sourceRevision=$ExpectedRevision;$summary.passed=$true
}catch{$summary.error=$_.Exception.Message;$summary.location=$_.ScriptStackTrace;throw}
finally{
 if($app -and -not $app.HasExited){Stop-Process -Id $app.Id -ErrorAction SilentlyContinue}
 if($fixtureApp -and -not $fixtureApp.HasExited){Stop-Process -Id $fixtureApp.Id -ErrorAction SilentlyContinue}
 if(Test-Path $root){
  Get-CimInstance Win32_Process|Where-Object {$_.Name -eq 'chrome.exe' -and $_.CommandLine -like ('*'+(Split-Path $root -Leaf)+'*')}|ForEach-Object {Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue}
  $deadline=[DateTime]::UtcNow.AddSeconds(30)
  do{try{Remove-Item $root -Recurse -Force;break}catch{Start-Sleep -Milliseconds 250}}while([DateTime]::UtcNow -lt $deadline)
  if(Test-Path $root){$summary.cleanupError=$true;$summary.passed=$false}
 }
 $registry.Dispose();$summary|ConvertTo-Json -Depth 5|Set-Content $EvidencePath -Encoding UTF8
}
