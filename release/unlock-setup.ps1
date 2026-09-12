# Embedded into unlock-setup.exe at build time; never executed from the package
# directory by the elevated entry. Expected publisher is compiled in by CI.
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
try {
    $action = $env:MC_UNLOCK_ACTION
    $instance = $env:MC_UNLOCK_INSTANCE
    $proposal = $env:MC_UNLOCK_PROPOSAL
    $self = $env:MC_UNLOCK_SELF
    $development = $env:MC_UNLOCK_DEVELOPMENT -ceq '--allow-unsigned'
    if ($action -cnotin @('Install', 'Arm', 'Revoke', 'Uninstall') -or $instance -cnotmatch '^[a-z0-9][a-z0-9-]{0,47}$') {
        throw 'Invalid setup action or instance'
    }
    $system = [Environment]::GetFolderPath('System')
    $parent = Join-Path ([Environment]::GetFolderPath('ProgramFiles')) 'MachineControlUnlock'
    $stateParent = Join-Path ([Environment]::GetFolderPath('CommonApplicationData')) 'MachineControlUnlock'
    $root = Join-Path $parent $instance
    $state = Join-Path $stateParent $instance
    $serviceName = "MachineControlUnlock_$instance"
    $admin = [Security.Principal.SecurityIdentifier]::new('S-1-5-32-544')
    $systemSid = [Security.Principal.SecurityIdentifier]::new('S-1-5-18')
    function Assert-Protected([string]$Path) {
        $item = Get-Item -LiteralPath $Path -Force
        if ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) { throw 'Reparse point in protected path' }
        $acl = Get-Acl -LiteralPath $Path
        if ($acl.GetOwner([Security.Principal.SecurityIdentifier]).Value -notin @($admin.Value, $systemSid.Value)) { throw 'Untrusted path owner' }
        $writes = [Security.AccessControl.FileSystemRights]'Write,Delete,DeleteSubdirectoriesAndFiles,ChangePermissions,TakeOwnership'
        foreach ($rule in $acl.GetAccessRules($true, $true, [Security.Principal.SecurityIdentifier])) {
            if ($rule.AccessControlType -eq 'Allow' -and ($rule.FileSystemRights -band $writes) -and
                $rule.IdentityReference.Value -notin @($admin.Value, $systemSid.Value)) { throw 'Writable protected path' }
        }
    }
    function New-Protected([string]$Path) {
        $acl = [Security.AccessControl.DirectorySecurity]::new()
        $acl.SetAccessRuleProtection($true, $false)
        $acl.SetOwner($admin)
        foreach ($sid in @($admin, $systemSid)) {
            $acl.AddAccessRule([Security.AccessControl.FileSystemAccessRule]::new($sid, 'FullControl', 'ContainerInherit,ObjectInherit', 'None', 'Allow'))
        }
        [IO.DirectoryInfo]::new($Path).Create($acl)
        Assert-Protected $Path
    }
    function Assert-Signature([string]$Path) {
        if ($development) { return }
        if (-not $expectedPublisher) { throw 'Release publisher was not compiled into this bootstrap' }
        $signature = Get-AuthenticodeSignature -LiteralPath $Path
        if ($signature.Status -ne 'Valid' -or -not $signature.TimeStamperCertificate -or
            $signature.SignerCertificate.GetNameInfo([Security.Cryptography.X509Certificates.X509NameType]::SimpleName, $false) -cne $expectedPublisher) {
            throw 'Package publisher verification failed'
        }
    }
    Assert-Signature $self
    if ($action -eq 'Install') {
        if ((Get-Service -Name $serviceName -ErrorAction SilentlyContinue) -or (Test-Path -LiteralPath $root)) {
            throw 'Already installed. Revoke and uninstall before installing a replacement.'
        }
        New-Protected $parent
        New-Protected $stateParent
        New-Protected $root
        New-Protected $state
        $installed = $false
        try {
            $source = Split-Path -Parent $self
            $manifestPath = Join-Path $source 'package.json'
            if ((Get-Item -LiteralPath $manifestPath).Length -gt 1048576) { throw 'Manifest too large' }
            $manifest = Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json
            if ($manifest.schema -cne 'machine-control-windows-package/v0' -or $manifest.profile -cne 'workstation' -or
                $manifest.packageId -cnotmatch '^[a-f0-9]{64}$') { throw 'Unsupported package' }
            $members = @($manifest.files.PSObject.Properties.Name) + @('package.json')
            if (-not $development) { $members += 'package.cat' }
            if ($members.Count -gt 512) { throw 'Package has too many files' }
            $total = 0L
            foreach ($member in $members) {
                if ($member -cnotmatch '^[a-zA-Z0-9_./-]+$' -or $member -match '(^|/)\.\.?(/|$)' -or $member.StartsWith('/')) { throw 'Invalid member' }
                $inputPath = Join-Path $source $member
                $total += (Get-Item -LiteralPath $inputPath).Length
                if ($total -gt 2GB) { throw 'Package exceeds size bound' }
                $outputPath = Join-Path $root $member
                [IO.Directory]::CreateDirectory((Split-Path -Parent $outputPath)) | Out-Null
                [IO.File]::Copy($inputPath, $outputPath, $false)
            }
            # Verify the protected copy before granting ordinary read access or
            # executing any managed/native payload. Source races cannot activate
            # different bytes from those verified here.
            foreach ($file in $manifest.files.PSObject.Properties) {
                if ((Get-FileHash -LiteralPath (Join-Path $root $file.Name) -Algorithm SHA256).Hash.ToLowerInvariant() -cne $file.Value) { throw 'Copied package hash mismatch' }
            }
            foreach ($name in @('machine-control-windows.exe', 'unlock-setup.exe', 'workstation.ps1', 'providers/cua/cua-driver.exe')) {
                Assert-Signature (Join-Path $root $name)
            }
            if (-not $development) {
                Assert-Signature (Join-Path $root 'package.cat')
                if ((Test-FileCatalog -Path $root -CatalogFilePath (Join-Path $root 'package.cat') -FilesToSkip 'package.cat') -ne 'Valid') { throw 'Catalog mismatch' }
            }
            foreach ($directory in @($root, $state)) {
                $acl = Get-Acl -LiteralPath $directory
                $acl.AddAccessRule([Security.AccessControl.FileSystemAccessRule]::new(
                    [Security.Principal.SecurityIdentifier]::new('S-1-5-32-545'), 'ReadAndExecute', 'ContainerInherit,ObjectInherit', 'None', 'Allow'))
                Set-Acl -LiteralPath $directory -AclObject $acl
            }
            $exe = Join-Path $root 'machine-control-windows.exe'
            New-Service -Name $serviceName -DisplayName "Machine Control optional unlock ($instance)" `
                -BinaryPathName ('"' + $exe + '" unlock-service --instance ' + $instance) -StartupType Automatic | Out-Null
            Start-Service -Name $serviceName
            $installed = $true
            Write-Output 'Unlock component installed and unarmed'
        } finally {
            if (-not $installed) {
                $service = Get-Service -Name $serviceName -ErrorAction SilentlyContinue
                if ($service) { Stop-Service $serviceName -ErrorAction SilentlyContinue; & "$system\sc.exe" delete $serviceName | Out-Null }
                Remove-Item -LiteralPath $root -Recurse -Force
                Remove-Item -LiteralPath $state -Recurse -Force
            }
        }
    } else {
        foreach ($path in @($parent, $root, $stateParent, $state)) { Assert-Protected $path }
        if ($action -eq 'Uninstall' -and $self.StartsWith($root + '\', [StringComparison]::OrdinalIgnoreCase)) {
            throw 'Run Uninstall from the original distribution directory'
        }
        if ($action -eq 'Arm') {
            $exe = Join-Path $root 'machine-control-windows.exe'
            Assert-Protected $exe
            Assert-Signature $exe
            & $exe unlock-arm --instance $instance --proposal $proposal
            exit $LASTEXITCODE
        }
        # Stop before revocation so pending workers lose their trusted service
        # connection. Removing a grant never falls back to appliance authority.
        Stop-Service -Name $serviceName
        Remove-Item -LiteralPath (Join-Path $state 'grant.json') -Force -ErrorAction SilentlyContinue
        if (Test-Path -LiteralPath (Join-Path $state 'grant.json')) { throw 'Grant removal failed; service remains stopped' }
        if ($action -eq 'Revoke') { Start-Service -Name $serviceName; Write-Output 'Unlock approval revoked' }
        if ($action -eq 'Uninstall') {
            & "$system\sc.exe" delete $serviceName | Out-Null
            if ($LASTEXITCODE -ne 0) { throw 'Service removal failed' }
            Remove-Item -LiteralPath $root -Recurse -Force
            Remove-Item -LiteralPath $state -Recurse -Force
            Write-Output 'Unlock component removed'
        }
    }
    exit 0
} catch {
    Write-Error $_
    exit 1
}
