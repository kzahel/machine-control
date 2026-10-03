# Run through the appliance's independent interactive-session runner.
# Owns only an initially absent candidate app; the controller owns outer claim.
param(
 [Parameter(Mandatory=$true)][string]$Install,
 [Parameter(Mandatory=$true)][string]$Source,
 [Parameter(Mandatory=$true)][string]$EvidencePath,
 [Parameter(Mandatory=$true)][string]$Fixture,
 [switch]$LeaveRunning
)
$ErrorActionPreference='Stop'
Set-StrictMode -Version Latest
Add-Type -AssemblyName UIAutomationClient,UIAutomationTypes
$exe=Join-Path $Install 'machine-control.exe'
$evidence=[ordered]@{passed=$false;unsignedDeveloperBuild=$true}
$owned=$null
$attempted=$false
function Candidate {
 return ,@(Get-Process machine-control -ErrorAction SilentlyContinue | Where-Object {$_.Path -eq $exe})
}
function Press([string]$name) {
 $deadline=[DateTime]::UtcNow.AddSeconds(15)
 do {
  $condition=[Windows.Automation.PropertyCondition]::new([Windows.Automation.AutomationElement]::ProcessIdProperty,$owned.Id)
  $window=[Windows.Automation.AutomationElement]::RootElement.FindFirst([Windows.Automation.TreeScope]::Children,$condition)
  if($window){
   $buttonCondition=[Windows.Automation.AndCondition]::new(
    [Windows.Automation.PropertyCondition]::new([Windows.Automation.AutomationElement]::NameProperty,$name),
    [Windows.Automation.PropertyCondition]::new([Windows.Automation.AutomationElement]::ControlTypeProperty,[Windows.Automation.ControlType]::Button))
   $button=$window.FindFirst([Windows.Automation.TreeScope]::Descendants,$buttonCondition)
   if($button -and $button.Current.IsEnabled -and -not $button.Current.IsOffscreen){
    $button.GetCurrentPattern([Windows.Automation.InvokePattern]::Pattern).Invoke()
    Start-Sleep -Milliseconds 500
    return
   }
  }
  Start-Sleep -Milliseconds 100
 } while([DateTime]::UtcNow -lt $deadline)
 throw "Candidate UI control unavailable: $name"
}
try {
 if((Candidate).Count){throw 'Candidate already running; refusing to adopt another process'}
 $attempted=$true
 $start=[Diagnostics.ProcessStartInfo]::new((Get-Command python).Source)
 $start.UseShellExecute=$false
 $start.RedirectStandardOutput=$true
 $start.RedirectStandardError=$true
 $start.Arguments='"'+(Join-Path $Source 'tests/windows/discovery.py')+'" --install "'+$Install+'" --launch'
 $probe=[Diagnostics.Process]::Start($start)
 $output=$probe.StandardOutput.ReadToEndAsync()
 $errors=$probe.StandardError.ReadToEndAsync()
 if(-not $probe.WaitForExit(120000)){$probe.Kill();throw 'Discovery subprocess timed out'}
 $raw=$output.Result
 if($probe.ExitCode){throw ($errors.Result+$raw)}
 $evidence.discovery=$raw|ConvertFrom-Json
 $items=Candidate
 if($items.Count -ne 1){throw 'Expected one detached candidate operator'}
 $owned=$items[0]
 $evidence.operatorProcessId=$owned.Id
 # The Python actor and all command launchers have exited; the app stays alive.
 Start-Sleep -Seconds 1
 if($owned.HasExited){throw 'Operator ended with the launching command'}
 $off=Join-Path (Split-Path $EvidencePath) 'discovery-off.json'
 & (Join-Path $Source 'tests/windows/desktop-cli.ps1') -Install $Install -Client $exe -EvidencePath $off
 if(-not (Get-Content $off -Raw|ConvertFrom-Json).passed){throw 'Off-state CLI failed'}
 $evidence.offStateRefusal=$true
 $open=Start-Process $exe -ArgumentList '--gui' -PassThru
 if(-not $open.WaitForExit(15000)){throw 'Graphical single-instance launch did not exit'}
 Press 'Access'
 Press 'Enable access'
 $active=Join-Path (Split-Path $EvidencePath) 'discovery-active.json'
 try {
  & (Join-Path $Source 'tests/windows/desktop-cli.ps1') -Install $Install -Client $exe -EvidencePath $active -Fixture $Fixture
  $effect=Get-Content $active -Raw|ConvertFrom-Json
  if(-not $effect.passed -or -not $effect.independentCounterEffect){throw 'CLI fixture effect failed'}
  $evidence.independentCounterEffect=$true
  $evidence.artifactHashVerified=$effect.artifactHashVerified
 } finally {Press 'Stop access'}
 $evidence.passed=$true
} catch {$evidence.error=$_.Exception.ToString();throw}
finally {
 if($attempted -and $null -eq $owned){$items=Candidate;if($items.Count -eq 1){$owned=$items[0]}}
 if($owned -and (-not $LeaveRunning -or -not $evidence.passed)) {
  Stop-Process -Id $owned.Id -ErrorAction SilentlyContinue
  $evidence.operatorRemoved=$true
 }
 $evidence|ConvertTo-Json -Depth 12|Set-Content $EvidencePath -Encoding UTF8
}
