[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$SourceDirectory
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$serviceName = 'MachineControlRuntime'
$installBase = Join-Path $env:ProgramData 'MachineControl'
$installRoot = Join-Path $installBase 'runtime'
$transactionId = [Guid]::NewGuid().ToString('n')
$stagedRoot = Join-Path $installBase "runtime.next-$transactionId"
$backupRoot = Join-Path $installBase "runtime.previous-$transactionId"
$executable = Join-Path $installRoot 'machine-control-windows.exe'

if (-not (Test-Path -LiteralPath $SourceDirectory)) {
    throw "SourceDirectory does not exist"
}
if (-not (Test-Path -LiteralPath `
        (Join-Path $SourceDirectory 'machine-control-windows.exe'))) {
    throw "Published machine-control-windows.exe was not found"
}

function Remove-RuntimeService {
    $existing = Get-Service -Name $serviceName -ErrorAction SilentlyContinue
    if (-not $existing) { return }
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

function Add-RuntimeService {
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
}

New-Item -ItemType Directory -Force -Path $installBase | Out-Null
New-Item -ItemType Directory -Path $stagedRoot | Out-Null
$committed = $false
$previousPresent = Test-Path -LiteralPath $installRoot
try {
    Copy-Item -Path (Join-Path $SourceDirectory '*') `
        -Destination $stagedRoot `
        -Recurse `
        -Force
    if (-not (Test-Path -LiteralPath `
            (Join-Path $stagedRoot 'machine-control-windows.exe'))) {
        throw 'the staged runtime is incomplete'
    }

    Remove-RuntimeService
    if ($previousPresent) {
        Move-Item -LiteralPath $installRoot -Destination $backupRoot
    }
    Move-Item -LiteralPath $stagedRoot -Destination $installRoot
    try {
        Add-RuntimeService
    }
    catch {
        Remove-RuntimeService
        Remove-Item -LiteralPath $installRoot -Recurse -Force `
            -ErrorAction SilentlyContinue
        if ($previousPresent -and (Test-Path -LiteralPath $backupRoot)) {
            Move-Item -LiteralPath $backupRoot -Destination $installRoot
            Add-RuntimeService
        }
        throw
    }
    $committed = $true
}
finally {
    Remove-Item -LiteralPath $stagedRoot -Recurse -Force `
        -ErrorAction SilentlyContinue
    if ($committed) {
        Remove-Item -LiteralPath $backupRoot -Recurse -Force `
            -ErrorAction SilentlyContinue
    }
}

$service = Get-CimInstance Win32_Service -Filter "Name='$serviceName'"
[pscustomobject]@{
    name = $service.Name
    state = $service.State
    start_mode = $service.StartMode
    start_name = $service.StartName
    path = $service.PathName
    previous_installation_replaced = $previousPresent
    transaction_committed = $committed
} | ConvertTo-Json -Compress
