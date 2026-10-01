# Registration maintenance has no desktop-control or approval authority.
param([Parameter(Mandatory=$true)][string]$Executable,
 [Parameter(Mandatory=$true)][string]$EvidencePath)
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
$summary=[ordered]@{schema='machine-control-windows-browser-installer/v0';passed=$false;checks=@()}
$registry=[Microsoft.Win32.RegistryKey]::OpenBaseKey([Microsoft.Win32.RegistryHive]::CurrentUser,[Microsoft.Win32.RegistryView]::Registry32)
$keyPath='Software\Google\Chrome\NativeMessagingHosts\org.machine_control.browser'
$manifest=Join-Path $env:LOCALAPPDATA 'MachineControl\packages\desktop\browser-host.json'
$backup=$manifest+'.updating'
$old=$registry.OpenSubKey($keyPath);$oldValue=if($old){$old.GetValue('')}else{$null};if($old){$old.Dispose()}
$oldManifest=if(Test-Path $manifest){[IO.File]::ReadAllBytes($manifest)}else{$null}
$oldBackup=if(Test-Path $backup){[IO.File]::ReadAllBytes($backup)}else{$null}
$root=Join-Path (Split-Path $EvidencePath) ('installer-'+[Guid]::NewGuid().ToString('n'))
$owned=Join-Path $root 'owned';$other=Join-Path $root 'other'
$fake=Join-Path $owned 'runtime\machine-control-windows.exe'
function Assert($Value,[string]$Message){if(-not $Value){throw $Message};$summary.checks+=@($Message)}
function Registered {$key=$registry.OpenSubKey($keyPath);try{if($key){return $key.GetValue('')};return $null}finally{if($key){$key.Dispose()}}}
function Run([string]$Operation,[string]$Installation,[int]$Exit=0){& $Executable $Operation $Installation 2>$null;Assert ($LASTEXITCODE -eq $Exit) ('Installer operation outcome: '+$Operation)}
function WriteManifest([string]$Path,[string]$Origin='chrome-extension://ncbfifkjllmnkkjmomjohinigfgdocjc/'){
 @{name='org.machine_control.browser';description='Fixture';path=$Path;type='stdio';allowed_origins=@($Origin)}|ConvertTo-Json -Compress|Set-Content $manifest -Encoding UTF8
 return (Get-FileHash $manifest -Algorithm SHA256).Hash
}
try{
 New-Item -ItemType Directory (Split-Path $fake) -Force|Out-Null
 New-Item -ItemType Directory (Split-Path $manifest) -Force|Out-Null
 Copy-Item $Executable $fake
 Remove-Item $manifest,$backup -ErrorAction SilentlyContinue
 $key=$registry.CreateSubKey($keyPath);$key.SetValue('',$manifest);$key.Dispose()
 $hash=WriteManifest $fake
 Run 'browser-install-prepare' $owned
 Assert (-not(Test-Path $manifest) -and (Test-Path $backup)) 'Preparation hides only the owned manifest'
 Assert ((Get-FileHash $backup -Algorithm SHA256).Hash -eq $hash -and (Registered) -eq $manifest) 'Preparation preserves exact manifest bytes and registry value'
 Run 'browser-install-prepare' $other;Run 'browser-install-finish' $other
 Assert (-not(Test-Path $manifest) -and (Get-FileHash $backup -Algorithm SHA256).Hash -eq $hash) 'Another installation cannot restore or replace maintenance state'
 Run 'browser-install-finish' $owned
 Assert ((Get-FileHash $manifest -Algorithm SHA256).Hash -eq $hash -and -not(Test-Path $backup)) 'Completion restores exact registration'
 $otherHash=WriteManifest (Join-Path $other 'runtime\machine-control-windows.exe')
 Run 'browser-install-prepare' $owned
 Assert ((Get-FileHash $manifest -Algorithm SHA256).Hash -eq $otherHash -and -not(Test-Path $backup)) 'Scratch maintenance preserves another installation'
 & $fake browser-unregister
 Assert ($LASTEXITCODE -eq 0 -and (Test-Path $manifest) -and (Registered) -eq $manifest) 'Scratch uninstall preserves another installation'
 $hash=WriteManifest $fake
 Run 'browser-install-prepare' $owned
 Copy-Item $backup $manifest
 Run 'browser-install-finish' $owned 1
 Assert ((Get-FileHash $manifest -Algorithm SHA256).Hash -eq $hash -and (Get-FileHash $backup -Algorithm SHA256).Hash -eq $hash) 'Conflicting active manifest refuses restoration without overwrite'
 Remove-Item $manifest;Run 'browser-install-finish' $owned
 Run 'browser-install-prepare' $owned
 & $fake browser-unregister
 Assert ($LASTEXITCODE -eq 0 -and -not(Test-Path $manifest) -and -not(Test-Path $backup) -and $null -eq (Registered)) 'Owned uninstall recovers and removes interrupted maintenance without a desktop'
 $key=$registry.CreateSubKey($keyPath);$key.SetValue('',$manifest);$key.Dispose()
 $hash=WriteManifest $fake 'chrome-extension://invalid/'
 Run 'browser-install-prepare' $owned 1
 Assert ((Get-FileHash $manifest -Algorithm SHA256).Hash -eq $hash -and -not(Test-Path $backup)) 'Invalid owned origin refuses before changing registration'
 $summary.passed=$true
}catch{$summary.error=$_.Exception.Message;$summary.location=$_.ScriptStackTrace;throw}
finally{
 if($oldValue){$key=$registry.CreateSubKey($keyPath);$key.SetValue('',$oldValue);$key.Dispose()}else{$registry.DeleteSubKeyTree($keyPath,$false)}
 if($oldManifest){[IO.File]::WriteAllBytes($manifest,$oldManifest)}else{Remove-Item $manifest -ErrorAction SilentlyContinue}
 if($oldBackup){[IO.File]::WriteAllBytes($backup,$oldBackup)}else{Remove-Item $backup -ErrorAction SilentlyContinue}
 $registry.Dispose();Remove-Item $root -Recurse -Force -ErrorAction SilentlyContinue
 $summary|ConvertTo-Json -Depth 5|Set-Content $EvidencePath -Encoding UTF8
}
