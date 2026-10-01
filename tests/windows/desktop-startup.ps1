# Run after a real sign-in. This actor never launches the product itself.
param(
 [Parameter(Mandatory=$true)][string]$Install,
 [Parameter(Mandatory=$true)][string]$ExpectedRevision,
 [Parameter(Mandatory=$true)][datetime]$StartedAfterUtc,
 [Parameter(Mandatory=$true)][string]$PreviousGeneration,
 [Parameter(Mandatory=$true)][string]$EvidencePath
)
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
$summary=[ordered]@{schema='machine-control-windows-desktop-startup/v0';passed=$false;checks=@()}
function Assert($Value,[string]$Message){if(-not $Value){throw $Message};$summary.checks+=@($Message)}
try{
 $operator=Join-Path $Install 'machine-control.exe'
 $exe=Join-Path $Install 'runtime\machine-control-windows.exe'
 $session=[Diagnostics.Process]::GetCurrentProcess().SessionId
 $deadline=[DateTime]::UtcNow.AddSeconds(90)
 do{
  $apps=@(Get-Process machine-control -ErrorAction SilentlyContinue|Where-Object {$_.Path -eq $operator -and $_.SessionId -eq $session})
  if($apps.Count -eq 1){break};Start-Sleep -Milliseconds 250
 }while([DateTime]::UtcNow -lt $deadline)
 Assert ($apps.Count -eq 1) 'Real sign-in starts exactly one installed operator'
 $app=$apps[0]
 Assert ($app.StartTime.ToUniversalTime() -ge $StartedAfterUtc.ToUniversalTime()) 'Startup process was created after recovery began'
 $process=Get-CimInstance Win32_Process -Filter ('ProcessId='+$app.Id)
 Assert ($process.CommandLine -match '--background') 'Login startup uses background mode'
 $entry=[Microsoft.Win32.Registry]::GetValue('HKEY_CURRENT_USER\Software\Microsoft\Windows\CurrentVersion\Run','Machine Control',$null)
 Assert ($entry -in @(('"'+$operator+'" --background'),($operator+' --background'))) 'Startup entry names the exact installed operator'
 $metadata=Get-Content (Join-Path $Install 'runtime\desktop-runtime.json') -Raw|ConvertFrom-Json
 Assert ($metadata.sourceRevision -eq $ExpectedRevision) 'Startup preserves exact accepted source'
 $deadline=[DateTime]::UtcNow.AddSeconds(30)
 do{
  $raw=@{operation='grant.status'}|ConvertTo-Json -Compress|& $exe call --profile user --instance desktop --session-id $session
  $reply=if($raw){$raw|ConvertFrom-Json}else{$null}
  if($reply -and $reply.accepted){break};Start-Sleep -Milliseconds 250
 }while([DateTime]::UtcNow -lt $deadline)
 Assert ($reply -and $reply.accepted) 'Login-started resident becomes ready'
 Assert ($reply.generation -ne $PreviousGeneration) 'Sign-in creates a fresh resident generation'
 Assert ($null -eq $reply.data.PSObject.Properties['grant']) 'Login startup leaves access off'
 $browser=@{operation='browser.tabs'}|ConvertTo-Json -Compress|& $exe call --profile user --instance desktop --session-id $session|ConvertFrom-Json
 Assert (-not $browser.accepted -and $browser.errorCode -eq 'approval_required') 'Login startup refuses unapproved browser access'
 $summary.sourceRevision=$ExpectedRevision
 $summary.passed=$true
}catch{$summary.error=$_.Exception.Message;$summary.location=$_.ScriptStackTrace;throw}
finally{$summary|ConvertTo-Json -Depth 5|Set-Content $EvidencePath -Encoding UTF8}
