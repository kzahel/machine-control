# Independent interactive actor for an unsigned source or installed candidate.
# The controller owns UAC approval and the separate native credential fixture;
# this WebView actor never receives a credential or approves agent access.
param(
 [Parameter(Mandatory=$true)][string]$Install,
 [Parameter(Mandatory=$true)][string]$EvidencePath,
 [ValidateSet('inspect','update','enabled')][string]$Action='inspect'
)
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
Add-Type -AssemblyName UIAutomationClient,UIAutomationTypes
$report=[ordered]@{passed=$false;action=$Action;checks=@()}
function Assert($value,[string]$message){if(!$value){throw $message};$report.checks+=@($message)}
function Element([string]$name,[string]$type='Button'){
 $deadline=[DateTime]::UtcNow.AddSeconds(60)
 do{
  $apps=@(Get-Process machine-control -ErrorAction SilentlyContinue|Where-Object {$_.Path -eq (Join-Path $Install 'machine-control.exe')})
  if($apps.Count -eq 1){
   $windows=[Windows.Automation.AutomationElement]::RootElement.FindAll([Windows.Automation.TreeScope]::Children,
    [Windows.Automation.PropertyCondition]::new([Windows.Automation.AutomationElement]::ProcessIdProperty,$apps[0].Id))
   foreach($window in $windows){
    $condition=[Windows.Automation.AndCondition]::new([Windows.Automation.Condition[]]@(
     [Windows.Automation.PropertyCondition]::new([Windows.Automation.AutomationElement]::NameProperty,$name),
     [Windows.Automation.PropertyCondition]::new([Windows.Automation.AutomationElement]::ControlTypeProperty,[Windows.Automation.ControlType]::$type)))
    $value=$window.FindFirst([Windows.Automation.TreeScope]::Descendants,$condition)
    if($null -ne $value){
     if($value.Current.IsOffscreen){try{$value.GetCurrentPattern([Windows.Automation.ScrollItemPattern]::Pattern).ScrollIntoView()}catch{}}
     if(!$value.Current.IsOffscreen){return $value}
    }
   }
  }
  Start-Sleep -Milliseconds 200
 }while([DateTime]::UtcNow -lt $deadline)
 throw "Source operator element unavailable: $name"
}
function Press([string]$name){
 $element=Element $name
 Assert $element.Current.IsEnabled ('Enabled UI action: '+$name)
 $element.GetCurrentPattern([Windows.Automation.InvokePattern]::Pattern).Invoke()
}
function Call([string]$operation){
 $raw=@{operation=$operation}|ConvertTo-Json -Compress|& (Join-Path $Install 'runtime\machine-control-windows.exe') call --profile user --instance desktop
 if($LASTEXITCODE -ne 0){throw 'Native readback transport failed'}
 return $raw|ConvertFrom-Json
}
try{
 Press 'Access'
 $covered=Element 'Covered desktop access while locked' 'CheckBox'
 Assert $covered.Current.IsEnabled 'Covered-desktop option is available after native enrollment'
 if($Action -eq 'update'){
  Press 'Update saved password…'
  $report.nativeSetupRequested=$true
 }else{
  $deadline=[DateTime]::UtcNow.AddSeconds(60)
  do{
   $covered=Element 'Covered desktop access while locked' 'CheckBox'
   $enabled=$covered.GetCurrentPattern([Windows.Automation.TogglePattern]::Pattern).Current.ToggleState -eq [Windows.Automation.ToggleState]::On
   if($enabled){break};Start-Sleep -Milliseconds 200
  }while([DateTime]::UtcNow -lt $deadline)
  Assert $enabled 'Successful setup automatically enables the visible covered-desktop option'
  $state=(Call 'capabilities').data.lockedUse
  Assert ($state.permissionReady -and $state.enabled -and $state.credentialSource -eq 'service_enrolled_password') 'Independent resident readback confirms enrolled and enabled state'
  $grant=(Call 'grant.status').data
  Assert ($null -eq $grant.PSObject.Properties['grant']) 'Native setup grants no ordinary agent access'
  Assert ((Element 'Update saved password…').Current.IsEnabled -and (Element 'Remove unlock setup…').Current.IsEnabled) 'Native repair and removal actions are available'
  Press 'Settings'
  Assert ((Element 'Allow approved browser access while locked' 'CheckBox').Current.IsEnabled) 'Browser access while locked has a separate visible option'
 }
 $report.passed=$true
}catch{$report.error=$_.Exception.Message;throw}
finally{$report|ConvertTo-Json -Depth 5|Set-Content -LiteralPath $EvidencePath -Encoding UTF8}
