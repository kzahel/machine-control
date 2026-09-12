[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidateSet('Install', 'Start', 'Status', 'Stop', 'Rollback', 'Uninstall')]
    [string]$Action,
    [ValidatePattern('^[a-z0-9][a-z0-9-]{0,47}$')]
    [string]$Instance = 'default',
    [string]$Package = $PSScriptRoot,
    [int]$SessionId = [Diagnostics.Process]::GetCurrentProcess().SessionId,
    [string]$ExpectedPublisher,
    [switch]$AllowUnsigned
)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$root = Join-Path $env:LOCALAPPDATA "MachineControl\packages\$Instance"
$statePath = Join-Path $root 'active.json'

function Assert-NoLink([string]$Path) {
    $item = Get-Item -LiteralPath $Path -Force
    if ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) {
        throw 'Installation paths must not contain reparse points'
    }
}
function Assert-Package([string]$Directory) {
    Assert-NoLink $Directory
    $manifestPath = Join-Path $Directory 'package.json'
    Assert-NoLink $manifestPath
    $manifest = Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json
    if ($manifest.schema -ne 'machine-control-windows-package/v0' -or
        $manifest.packageId -notmatch '^[a-f0-9]{64}$' -or
        $manifest.profile -ne 'workstation' -or $manifest.protocol -ne 'machine-control/v0') {
        throw 'Unsupported workstation package'
    }
    foreach ($file in $manifest.files.PSObject.Properties) {
        if ($file.Name -notmatch '^[a-zA-Z0-9_./-]+$' -or
            $file.Name -match '(^|/)\.\.?(/|$)' -or $file.Name.StartsWith('/')) {
            throw 'Invalid package member'
        }
        $path = Join-Path $Directory $file.Name
        $cursor = $path
        while ($cursor.Length -ge $Directory.Length) {
            Assert-NoLink $cursor
            $cursor = Split-Path -Parent $cursor
        }
        if ((Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant() -cne $file.Value) {
            throw "Package hash mismatch: $($file.Name)"
        }
    }
    foreach ($member in Get-ChildItem -LiteralPath $Directory -Recurse -Force) {
        Assert-NoLink $member.FullName
    }
    $actual = @(Get-ChildItem -LiteralPath $Directory -Recurse -File -Force)
    $catalogPath = Join-Path $Directory 'package.cat'
    $catalogCount = [int](Test-Path -LiteralPath $catalogPath)
    if ($actual.Count -ne @($manifest.files.PSObject.Properties).Count + 1 + $catalogCount) {
        throw 'Package contains unlisted files'
    }
    foreach ($required in @('machine-control-windows.exe', 'workstation.ps1', 'providers/cua/cua-driver.exe')) {
        if ($required -notin @($manifest.files.PSObject.Properties.Name)) { throw "Missing $required" }
    }
    if (-not $AllowUnsigned) {
        if (-not $ExpectedPublisher) { throw 'Pass the trusted ExpectedPublisher, or explicitly AllowUnsigned for development' }
        foreach ($name in @('machine-control-windows.exe', 'providers/cua/cua-driver.exe', 'workstation.ps1', 'package.cat')) {
            $signature = Get-AuthenticodeSignature -LiteralPath (Join-Path $Directory $name)
            if ($signature.Status -ne 'Valid' -or $null -eq $signature.TimeStamperCertificate -or
                $signature.SignerCertificate.GetNameInfo([Security.Cryptography.X509Certificates.X509NameType]::SimpleName, $false) -cne $ExpectedPublisher) {
                throw "Invalid publisher signature: $name"
            }
        }
        if ((Test-FileCatalog -Path $Directory -CatalogFilePath $catalogPath -FilesToSkip 'package.cat') -ne 'Valid') {
            throw 'Signed catalog does not authenticate the complete package'
        }
    }
    return $manifest
}
function Read-State {
    if (-not (Test-Path -LiteralPath $statePath)) { throw 'Instance is not installed' }
    Assert-NoLink $statePath
    $value = Get-Content -LiteralPath $statePath -Raw | ConvertFrom-Json
    foreach ($id in @($value.active, $value.previous)) {
        if ($null -ne $id -and $id -notmatch '^[a-f0-9]{64}$') { throw 'Invalid installation state' }
    }
    return $value
}
function Write-State($Value) {
    $temporary = Join-Path $root ([Guid]::NewGuid().ToString('n') + '.tmp')
    $backup = Join-Path $root ([Guid]::NewGuid().ToString('n') + '.backup')
    [IO.File]::WriteAllText($temporary, ($Value | ConvertTo-Json -Compress))
    try {
        # Windows PowerShell's binder can turn a null string argument into an
        # empty path. Use a real backup filename for portable atomic replacement.
        if (Test-Path -LiteralPath $statePath) { [IO.File]::Replace($temporary, $statePath, $backup) }
        else { [IO.File]::Move($temporary, $statePath) }
    } finally {
        foreach ($path in @($temporary, $backup)) {
            if (Test-Path -LiteralPath $path) { Remove-Item -LiteralPath $path -Force }
        }
    }
}
function Invoke-Resident([string]$Executable, [hashtable]$Request, [int]$Timeout = 3000) {
    if ($SessionId -le 0) { throw 'Specify the interactive SessionId when calling from SSH/session 0' }
    $text = $Request | ConvertTo-Json -Compress
    $result = $text | & $Executable call --profile user --instance $Instance --session-id $SessionId --timeout-ms $Timeout 2>$null
    if ($LASTEXITCODE -ne 0) { throw 'Resident is unavailable' }
    return $result | ConvertFrom-Json
}
function Assert-Stopped {
    # The user runtime holds this exact lock throughout its lifetime. Check all
    # sessions before upgrade/removal; do not kill an unrelated or reused PID.
    $stateRoot = Join-Path $env:LOCALAPPDATA "MachineControl\workstation\$Instance"
    if (Test-Path -LiteralPath $stateRoot) {
        foreach ($lock in Get-ChildItem -LiteralPath $stateRoot -Filter resident.lock -Recurse) {
            $stream = [IO.File]::Open($lock.FullName, 'Open', 'ReadWrite', 'None')
            $stream.Dispose()
        }
    }
}

# Serialize lifecycle mutations for an instance. Runtime ownership has a
# separate lock, so a second manager cannot race an upgrade or uninstall.
[IO.Directory]::CreateDirectory($root) | Out-Null
$cursor = $root
while ($cursor -and $cursor.Length -ge $env:LOCALAPPDATA.Length) {
    Assert-NoLink $cursor
    $cursor = Split-Path -Parent $cursor
}
$managerLock = [IO.File]::Open((Join-Path $root 'manager.lock'), 'OpenOrCreate', 'ReadWrite', 'None')
$activationLock = $null
try {
    if ($Action -in @('Install', 'Rollback', 'Uninstall')) {
        # Hold across validation, staging and activation. Directly supervised
        # residents hold a shared handle, preventing start-versus-upgrade races.
        $activationLock = [IO.File]::Open((Join-Path $root 'activation.lock'), 'OpenOrCreate', 'ReadWrite', 'None')
    }
    if ($Action -eq 'Install') {
        Assert-Stopped
        $source = (Resolve-Path -LiteralPath $Package).Path
        $manifest = Assert-Package $source
        $versions = Join-Path $root 'versions'
        [IO.Directory]::CreateDirectory($versions) | Out-Null
        Assert-NoLink $versions
        $destination = Join-Path $versions $manifest.packageId
        if (-not (Test-Path -LiteralPath $destination)) {
            $stage = Join-Path $versions ([Guid]::NewGuid().ToString('n') + '.staging')
            try {
                Copy-Item -LiteralPath $source -Destination $stage -Recurse
                $null = Assert-Package $stage
                Move-Item -LiteralPath $stage -Destination $destination
            } finally { if (Test-Path -LiteralPath $stage) { Remove-Item -LiteralPath $stage -Recurse -Force } }
        }
        $null = Assert-Package $destination
        $previous = $null
        if (Test-Path -LiteralPath $statePath) { $previous = (Read-State).active }
        if ($previous -ne $manifest.packageId) {
            Write-State @{ active = $manifest.packageId; previous = $previous }
        }
        @{ installed = $true; instance = $Instance; packageId = $manifest.packageId } | ConvertTo-Json -Compress
        return
    }
    $state = Read-State
    $directory = Join-Path $root "versions\$($state.active)"
    $executable = Join-Path $directory 'machine-control-windows.exe'
    if ($Action -eq 'Start') {
        $null = Assert-Package $directory
        if ($SessionId -ne [Diagnostics.Process]::GetCurrentProcess().SessionId) {
            throw 'Start must run inside the selected interactive session'
        }
        Assert-Stopped
        $process = Start-Process -FilePath $executable -ArgumentList @('user', '--instance', $Instance) -WindowStyle Hidden -PassThru
        try {
            $status = Invoke-Resident $executable @{ operation = 'status' } 10000
            if (-not $status.accepted -or -not $status.data.ready -or $status.data.processId -ne $process.Id) {
                throw 'Started runtime did not attest the selected instance and process'
            }
            $status | ConvertTo-Json -Depth 16 -Compress
        } catch {
            if (-not $process.HasExited) { $process.Kill() }
            throw
        }
    } elseif ($Action -eq 'Status') {
        Invoke-Resident $executable @{ operation = 'status' } | ConvertTo-Json -Depth 16 -Compress
    } elseif ($Action -eq 'Stop') {
        $status = Invoke-Resident $executable @{ operation = 'status' }
        $result = Invoke-Resident $executable @{ operation = 'runtime.stop'; expectedGeneration = $status.generation }
        if (-not $result.accepted) { throw 'Runtime refused stop' }
        $deadline = [DateTime]::UtcNow.AddSeconds(10)
        do {
            try { Assert-Stopped; $stopped = $true } catch { $stopped = $false }
            if (-not $stopped) { Start-Sleep -Milliseconds 100 }
        } while (-not $stopped -and [DateTime]::UtcNow -lt $deadline)
        if (-not $stopped) { throw 'Runtime did not release ownership after stop' }
        @{ stopped = $true; instance = $Instance } | ConvertTo-Json -Compress
    } elseif ($Action -eq 'Rollback') {
        Assert-Stopped
        if (-not $state.previous) { throw 'No previous package' }
        $null = Assert-Package (Join-Path $root "versions\$($state.previous)")
        Write-State @{ active = $state.previous; previous = $state.active }
        @{ active = $state.previous } | ConvertTo-Json -Compress
    } elseif ($Action -eq 'Uninstall') {
        Assert-Stopped
        # Retain the manager lock directory to serialize future installers;
        # remove only this instance's validated package store and runtime state.
        foreach ($path in @((Join-Path $root 'versions'),
                (Join-Path $env:LOCALAPPDATA "MachineControl\workstation\$Instance"))) {
            if (Test-Path -LiteralPath $path) {
                Assert-NoLink $path
                foreach ($child in Get-ChildItem -LiteralPath $path -Recurse -Force) { Assert-NoLink $child.FullName }
                Remove-Item -LiteralPath $path -Recurse -Force
            }
        }
        Remove-Item -LiteralPath $statePath
        @{ uninstalled = $true; instance = $Instance } | ConvertTo-Json -Compress
    }
} finally {
    if ($null -ne $activationLock) { $activationLock.Dispose() }
    $managerLock.Dispose()
}
