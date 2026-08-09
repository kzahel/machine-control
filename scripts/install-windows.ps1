[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$SourceDirectory
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$serviceName = 'MachineControlRuntime'
$installRoot = Join-Path $env:ProgramData 'MachineControl\runtime'
$executable = Join-Path $installRoot 'machine-control-windows.exe'

if (-not (Test-Path -LiteralPath $SourceDirectory)) {
    throw "SourceDirectory does not exist"
}
if (-not (Test-Path -LiteralPath (Join-Path $SourceDirectory 'machine-control-windows.exe'))) {
    throw "Published machine-control-windows.exe was not found"
}

$existing = Get-Service -Name $serviceName -ErrorAction SilentlyContinue
if ($existing) {
    Stop-Service -Name $serviceName -Force -ErrorAction SilentlyContinue
    & sc.exe delete $serviceName | Out-Null
    if ($LASTEXITCODE -ne 0) {
        throw "sc.exe delete failed with $LASTEXITCODE"
    }
    $deleteDeadline = [DateTime]::UtcNow.AddSeconds(15)
    while ((Get-Service -Name $serviceName -ErrorAction SilentlyContinue) -and
        [DateTime]::UtcNow -lt $deleteDeadline) {
        Start-Sleep -Milliseconds 250
    }
    if (Get-Service -Name $serviceName -ErrorAction SilentlyContinue) {
        throw 'the previous service remained pending deletion'
    }
}

New-Item -ItemType Directory -Force -Path $installRoot | Out-Null
Copy-Item -Path (Join-Path $SourceDirectory '*') `
    -Destination $installRoot `
    -Recurse `
    -Force

$binaryPath = '"{0}" service' -f $executable
& sc.exe create $serviceName `
    binPath= $binaryPath `
    start= auto `
    obj= LocalSystem `
    DisplayName= 'Machine Control Runtime' | Out-Null
if ($LASTEXITCODE -ne 0) {
    throw "sc.exe create failed with $LASTEXITCODE"
}
& sc.exe description $serviceName `
    'Target-resident typed Windows desktop/session controller' | Out-Null
& sc.exe failure $serviceName `
    reset= 86400 `
    actions= restart/2000/restart/5000/restart/10000 | Out-Null
Start-Service -Name $serviceName

$service = Get-CimInstance Win32_Service -Filter "Name='$serviceName'"
[pscustomobject]@{
    name = $service.Name
    state = $service.State
    start_mode = $service.StartMode
    start_name = $service.StartName
    path = $service.PathName
} | ConvertTo-Json -Compress
