[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string]$ApplianceExecutable,
    [ValidatePattern('^[a-z0-9][a-z0-9-]{0,47}$')][string]$Instance='unlock-conformance',
    [string]$EvidencePath=(Join-Path $env:TEMP 'unlock-access-conformance.json')
)
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
$root=Join-Path $env:ProgramFiles "MachineControlUnlock\$Instance"
$grant=Join-Path $env:ProgramData "MachineControlUnlock\$Instance\grant.json"
if (-not (Test-Path -LiteralPath $grant)) { throw 'An armed conformance instance is required' }
$marker=Join-Path $env:TEMP ('mc-unlock-access-'+[Guid]::NewGuid().ToString('n')+'.json')
$script=Join-Path $env:TEMP ('mc-unlock-access-'+[Guid]::NewGuid().ToString('n')+'.ps1')
# The script is intentionally ordinary same-user code, launched by the existing
# appliance's Medium helper. Only that independent harness may launch it.
$body=@'
param([string]$Root,[string]$Grant,[string]$Instance,[string]$Marker)
$ErrorActionPreference='Stop'
$identity=[Security.Principal.WindowsIdentity]::GetCurrent()
$result=[ordered]@{schema='machine-control-unlock-access-conformance/v0'; passed=$false}
try {
    if ([Security.Principal.WindowsPrincipal]::new($identity).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {throw 'Test process is elevated'}
    $result.ordinaryCaller=$true
    $denied=0
    foreach ($path in @($Grant,(Join-Path $Root 'README.md'))) {
        try {
            $acl=Get-Acl -LiteralPath $path
            $acl.AddAccessRule([Security.AccessControl.FileSystemAccessRule]::new($identity.User,'FullControl','Allow'))
            Set-Acl -LiteralPath $path -AclObject $acl
        } catch [UnauthorizedAccessException] { $denied++; continue }
        catch [System.Security.SecurityException] { $denied++; continue }
        throw 'Ordinary owner could change the protected DACL'
    }
    $result.daclChangesDenied=$denied
    $denied=0
    foreach ($path in @($Grant,(Join-Path $Root 'README.md'))) {
        try { $stream=[IO.File]::Open($path,'Open','Write','ReadWrite'); $stream.Dispose() }
        catch [UnauthorizedAccessException] { $denied++; continue }
        throw 'Ordinary caller obtained protected file write access'
    }
    $result.fileWritesDenied=$denied
    try { Stop-Service -Name "MachineControlUnlock_$Instance"; throw 'Ordinary caller stopped the unlock service' }
    catch [Microsoft.PowerShell.Commands.ServiceCommandException] { $result.serviceStopDenied=$true }
    if ($result.daclChangesDenied -ne 2 -or $result.fileWritesDenied -ne 2 -or -not $result.serviceStopDenied) {throw 'Missing denial'}
    $result.passed=$true
} finally { $result | ConvertTo-Json | Set-Content -LiteralPath $Marker }
'@
[IO.File]::WriteAllText($script,$body)
try {
    $request=@{operation='app.launch'; executablePath=(Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe'); arguments="-NoProfile -ExecutionPolicy Bypass -File `"$script`" -Root `"$root`" -Grant `"$grant`" -Instance $Instance -Marker `"$marker`""}
    $launch=($request|ConvertTo-Json -Compress|& $ApplianceExecutable call)|ConvertFrom-Json
    if (-not $launch.accepted) {throw 'Could not launch ordinary access probe'}
    $deadline=[DateTime]::UtcNow.AddSeconds(30)
    while (-not (Test-Path -LiteralPath $marker) -and [DateTime]::UtcNow -lt $deadline) {Start-Sleep -Milliseconds 200}
    $result=Get-Content -LiteralPath $marker -Raw|ConvertFrom-Json
    if (-not $result.passed) {throw 'Ordinary access probe failed'}
    $result|ConvertTo-Json|Set-Content -LiteralPath $EvidencePath
    $result|ConvertTo-Json
} finally {
    Remove-Item -LiteralPath $script,$marker -Force -ErrorAction SilentlyContinue
}
