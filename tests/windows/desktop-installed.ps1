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
$exe=Join-Path $Install 'runtime\machine-control-windows.exe'
$evidence=[ordered]@{schema='machine-control-windows-desktop-installed/v0';passed=$false;checks=@()}
function Assert($condition,$message) {if (-not $condition) {throw $message};$evidence.checks+=@($message)}
function Call([hashtable]$request) {
 $text=$request|ConvertTo-Json -Compress -Depth 10
 $raw=$text|& $exe call --profile user --instance desktop --session-id ([Diagnostics.Process]::GetCurrentProcess().SessionId)
 if ($LASTEXITCODE -ne 0) {throw 'Resident client transport failed'}
 return $raw|ConvertFrom-Json
}
function Granted {$deployment=(Call @{operation='grant.status'}).data.deployment; if ($null -ne $deployment.PSObject.Properties['grant']) {return $deployment.grant};return $null}
function Process {$items=@(Get-Process machine-control -ErrorAction SilentlyContinue|Where-Object {$_.Path -eq (Join-Path $Install 'machine-control.exe')}); if ($items.Count) {return $items[0]};return $null}
function Element([string]$Name,[string]$Type='Button') {
 $deadline=[DateTime]::UtcNow.AddSeconds(12)
 do {
  $p=Process
  if ($null -eq $p -or $p.MainWindowHandle -eq 0) {Start-Sleep -Milliseconds 150;continue}; $root=[Windows.Automation.AutomationElement]::FromHandle($p.MainWindowHandle)
  $conditions=@([Windows.Automation.PropertyCondition]::new([Windows.Automation.AutomationElement]::NameProperty,$Name),[Windows.Automation.PropertyCondition]::new([Windows.Automation.AutomationElement]::ControlTypeProperty,[Windows.Automation.ControlType]::$Type),[Windows.Automation.PropertyCondition]::new([Windows.Automation.AutomationElement]::IsOffscreenProperty,$false))
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
function Request([bool]$Allow,[bool]$Narrow=$false) {
 $start=[Diagnostics.ProcessStartInfo]::new($exe,('call --profile user --instance desktop --session-id '+[Diagnostics.Process]::GetCurrentProcess().SessionId))
 $start.UseShellExecute=$false;$start.CreateNoWindow=$true;$start.RedirectStandardInput=$true;$start.RedirectStandardOutput=$true
 $client=[Diagnostics.Process]::Start($start)
 try {
  $request=@{operation='grant.request';scopes=@('observe','control');durationSeconds=60;timeoutSeconds=15;reason='Installed app fixture acceptance'}|ConvertTo-Json -Compress
  $client.StandardInput.Write($request);$client.StandardInput.Close()
  $null=Element 'Allow access'
  $paused=Call @{operation='click';x=10;y=10}
  Assert (-not $paused.accepted -and $paused.errorCode -eq 'approval_prompt_visible') 'Pending prompt pauses input'
  if ($Narrow) {(Element 'Control apps and input' 'CheckBox').GetCurrentPattern([Windows.Automation.TogglePattern]::Pattern).Toggle()}
  if ($Allow) {Press 'Allow access'} else {Press 'Deny'}
  Assert ($client.WaitForExit(10000)) 'Approval client completes'
  $reply=$client.StandardOutput.ReadToEnd()|ConvertFrom-Json
  Assert ($reply.accepted -eq $Allow) 'Native UI approval outcome matches'
 } finally {if (-not $client.HasExited) {$client.Kill()};$client.Dispose()}
}
$fixtureProcess=$null
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
 Request $true $true
 Assert ((Granted).scopes.Count -eq 1 -and (Granted).scopes[0] -eq 'observe') 'Native dialog narrows scope'
 Assert (-not (Call @{operation='type';text='refuse'}).accepted) 'Narrowed grant refuses input'
 Press 'Stop access';WaitGrant $false
 Request $true
 $status=Call @{operation='status'};$generation=$status.generation
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
 Press 'Stop access';WaitGrant $false
 Press 'Enable access';WaitGrant $true
 $stale=Call @{operation='snapshot';expectedGeneration=$generation}
 Assert (-not $stale.accepted -and $stale.errorCode -eq 'stale_generation') 'Installed Stop invalidates old generation'
 Press 'Settings'
 $null=Element 'Start at login' 'CheckBox'
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
 $p=Process;$operatorId=$p.Id
 $runtime=@(Get-CimInstance Win32_Process|Where-Object {$_.ExecutablePath -eq $exe -and $_.CommandLine -match ' desktop$'})[0]
 Stop-Process -Id $operatorId
 Start-Sleep -Milliseconds 1500
 Assert ($null -eq (Get-Process -Id $runtime.ProcessId -ErrorAction SilentlyContinue)) 'Operator failure cleans resident job'
 Assert ($null -ne (Get-Process -Id $fixtureProcess -ErrorAction SilentlyContinue)) 'User-launched fixture survives operator exit'
 $evidence.passed=$true
} catch {$evidence.error=$_.Exception.ToString();throw}
finally {
 if ($fixtureProcess) {Stop-Process -Id $fixtureProcess -ErrorAction SilentlyContinue}
 $evidence|ConvertTo-Json -Depth 10|Set-Content $EvidencePath -Encoding UTF8
}
