# Installer-owned payload maintenance. Never touch user state or registrations.
param(
    [Parameter(Mandatory=$true)][ValidateSet('prepare','protect','unprotect')][string]$Action,
    [Parameter(Mandatory=$true)][string]$Directory,
    [string]$RegisteredDirectory = ''
)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
# A native installer started from PowerShell 7 can pass its module path to
# Windows PowerShell. Load inbox cmdlets from the running host's own modules.
Import-Module "$PSHOME\Modules\Microsoft.PowerShell.Management"
Import-Module "$PSHOME\Modules\Microsoft.PowerShell.Security"
Import-Module "$PSHOME\Modules\Microsoft.PowerShell.Utility"
$root = [IO.Path]::GetFullPath($Directory)
if (-not (Test-Path -LiteralPath $root)) { return }
if ((Get-Item -LiteralPath $root -Force).Attributes -band [IO.FileAttributes]::ReparsePoint) {
    throw 'Installation directory must not be a link'
}
$cli = Join-Path $root 'mc-cli'
$runtime = Join-Path $root 'runtime'
$payloads = @($cli, $runtime)
# Inspect before changing anything, including junctions below owned directories.
function Inspect([string]$Path) {
    $item = Get-Item -LiteralPath $Path -Force
    if ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) {
        throw 'Installed payload must not contain links'
    }
    $item
    if ($item.PSIsContainer) {
        foreach ($child in Get-ChildItem -LiteralPath $Path -Force) { Inspect $child.FullName }
    }
}
$cliItems = @(if (Test-Path -LiteralPath $cli) { Inspect $cli })
if (Test-Path -LiteralPath $runtime) { Inspect $runtime | Out-Null }
if ($Action -eq 'prepare') {
    # An old uninstaller can remove receipts while leaving obsolete files.
    # In that case the installer's registered directory must establish ownership.
    $registered = $RegisteredDirectory -and ([IO.Path]::GetFullPath($RegisteredDirectory) -eq $root)
    foreach ($pair in @(@('mc-cli','client-runtime.json','machine-control-client-identity/v1'),
                        @('runtime','desktop-runtime.json','machine-control-desktop-runtime/v0'))) {
        $path = Join-Path $root $pair[0]
        if (Test-Path -LiteralPath $path) {
            $receipt = Join-Path $path $pair[1]
            if (Test-Path -LiteralPath $receipt) {
                $identity = Get-Content -LiteralPath $receipt -Raw | ConvertFrom-Json
                if ($identity.schema -cne $pair[2]) { throw 'Unrecognized existing payload; refusing cleanup' }
            } elseif (-not $registered) {
                throw 'Unrecognized existing payload; refusing cleanup'
            }
        }
    }
}
if ($Action -ne 'prepare' -and $cliItems.Count -gt 0) {
    $sid = [Security.Principal.WindowsIdentity]::GetCurrent().User
    $rights = [Security.AccessControl.FileSystemRights]'WriteData,AppendData'
    $deny = [Security.AccessControl.AccessControlType]::Deny
    # Existing explicit grants take precedence over a deny inherited from the
    # CLI root. Deny writes on each installed item without removing grants or
    # denying deletion or ACL changes.
    $rule = [Security.AccessControl.FileSystemAccessRule]::new($sid, $rights, $deny)
    $oldRule = [Security.AccessControl.FileSystemAccessRule]::new($sid, $rights,
        [Security.AccessControl.InheritanceFlags]'ContainerInherit,ObjectInherit',
        [Security.AccessControl.PropagationFlags]::None, $deny)
    foreach ($item in $cliItems) {
        $acl = Get-Acl -LiteralPath $item.FullName
        if ($item.FullName -eq $cliItems[0].FullName) { $acl.RemoveAccessRuleSpecific($oldRule) }
        $acl.RemoveAccessRuleSpecific($rule)
        if ($Action -eq 'protect') { $acl.AddAccessRule($rule) }
        Set-Acl -LiteralPath $item.FullName -AclObject $acl
    }
}
if ($Action -eq 'prepare') {
    # These directories are immutable product resources, not a user-data store.
    foreach ($path in $payloads) {
        if (Test-Path -LiteralPath $path) { Remove-Item -LiteralPath $path -Recurse -Force }
    }
}
