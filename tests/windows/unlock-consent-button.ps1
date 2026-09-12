[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][long]$WindowHandle,
    [Parameter(Mandatory=$true)][int]$ExpectedProcessId,
    [Parameter(Mandatory=$true)][ValidateSet('Yes','No')][string]$Button
)
# Independent appliance fixture: SSH administration schedules a bounded,
# elevated Win32 dialog action in the already interactive account. The unlock product
# never registers this task or exposes this automation path.
$ErrorActionPreference='Stop'
$name='MachineControlConsentFixture-'+[Guid]::NewGuid().ToString('n')
$script=Join-Path $env:TEMP ($name+'.ps1')
$marker=Join-Path $env:TEMP ($name+'.json')
$body=@'
param([long]$WindowHandle,[int]$ExpectedProcessId,[string]$Button,[string]$Marker)
$ErrorActionPreference='Stop'
$result=@{passed=$false}
try {
    Add-Type -TypeDefinition @"
using System;
using System.Runtime.InteropServices;
using System.Text;
public static class ConsentFixture {
 [DllImport("user32.dll")] public static extern IntPtr GetDlgItem(IntPtr window, int id);
 [DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(IntPtr window, out uint process);
 [DllImport("user32.dll", CharSet=CharSet.Unicode)] public static extern int GetWindowText(IntPtr window, StringBuilder text, int capacity);
 [DllImport("user32.dll")] public static extern bool IsWindow(IntPtr window);
 [DllImport("user32.dll")] public static extern bool IsWindowEnabled(IntPtr window);
 [DllImport("user32.dll")] public static extern bool IsWindowVisible(IntPtr window);
 [DllImport("user32.dll", SetLastError=true)] public static extern IntPtr SendMessageTimeout(IntPtr window, uint message, IntPtr wparam, IntPtr lparam, uint flags, uint timeout, out IntPtr result);
}
"@
    $window=[IntPtr]$WindowHandle
    [uint32]$ownerProcess=0
    [void][ConsentFixture]::GetWindowThreadProcessId($window,[ref]$ownerProcess)
    $title=[Text.StringBuilder]::new(256)
    [void][ConsentFixture]::GetWindowText($window,$title,256)
    if ($ownerProcess -ne $ExpectedProcessId -or $title.ToString() -notlike 'Machine Control *approve unattended unlock') {throw 'Consent window changed'}
    $id=if ($Button -eq 'Yes') {6} else {7}
    $buttonWindow=[ConsentFixture]::GetDlgItem($window,$id)
    $label=[Text.StringBuilder]::new(32)
    [void][ConsentFixture]::GetWindowText($buttonWindow,$label,32)
    if ($buttonWindow -eq [IntPtr]::Zero -or $label.ToString().Replace('&','') -cne $Button -or
        -not [ConsentFixture]::IsWindowEnabled($buttonWindow) -or -not [ConsentFixture]::IsWindowVisible($buttonWindow)) {throw 'Consent button uncertain'}
    # Deliver the observed button's BN_CLICKED notification without relying on
    # foreground activation by a scheduled test process.
    $reply=[IntPtr]::Zero
    if ([ConsentFixture]::SendMessageTimeout($window,0x111,[IntPtr]$id,$buttonWindow,2,5000,[ref]$reply) -eq [IntPtr]::Zero) {throw 'Consent click was not delivered'}
    $deadline=[DateTime]::UtcNow.AddSeconds(5)
    while ([ConsentFixture]::IsWindow($window) -and [DateTime]::UtcNow -lt $deadline) {Start-Sleep -Milliseconds 100}
    if ([ConsentFixture]::IsWindow($window)) {throw 'Consent dialog did not close'}
    $result.passed=$true
} catch {$result.error=$_.Exception.Message} finally {$result|ConvertTo-Json|Set-Content -LiteralPath $Marker}
'@
[IO.File]::WriteAllText($script,$body)
try {
    $process=Get-CimInstance Win32_Process -Filter "ProcessId=$ExpectedProcessId"
    $owner=Invoke-CimMethod -InputObject $process -MethodName GetOwnerSid
    if ($owner.ReturnValue -ne 0 -or $process.SessionId -eq 0) {throw 'Interactive consent owner unavailable'}
    $action=New-ScheduledTaskAction -Execute "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe" -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$script`" -WindowHandle $WindowHandle -ExpectedProcessId $ExpectedProcessId -Button $Button -Marker `"$marker`""
    $principal=New-ScheduledTaskPrincipal -UserId $owner.Sid -LogonType Interactive -RunLevel Highest
    Register-ScheduledTask -TaskName $name -Action $action -Principal $principal | Out-Null
    Start-ScheduledTask -TaskName $name
    $deadline=[DateTime]::UtcNow.AddSeconds(20)
    while (-not (Test-Path $marker) -and [DateTime]::UtcNow -lt $deadline) {Start-Sleep -Milliseconds 200}
    $result=Get-Content $marker -Raw|ConvertFrom-Json
    if (-not $result.passed) {throw "Elevated consent fixture failed: $($result.error)"}
} finally {
    Stop-ScheduledTask -TaskName $name -ErrorAction SilentlyContinue
    Unregister-ScheduledTask -TaskName $name -Confirm:$false -ErrorAction SilentlyContinue
    Remove-Item -LiteralPath $script,$marker -Force -ErrorAction SilentlyContinue
}
