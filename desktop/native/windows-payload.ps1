# Installer-owned payload maintenance. Never touch user state or registrations.
param(
    [Parameter(Mandatory=$true)][ValidateSet('prepare','protect','unprotect')][string]$Action,
    [Parameter(Mandatory=$true)][string]$Directory,
    [string]$RegisteredDirectory = ''
)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$root = [IO.Path]::GetFullPath($Directory)
if (-not (Test-Path -LiteralPath $root)) { return }
if ((Get-Item -LiteralPath $root -Force).Attributes -band [IO.FileAttributes]::ReparsePoint) {
    throw 'Installation directory must not be a link'
}
$payloads = @('mc-cli', 'runtime') | ForEach-Object { Join-Path $root $_ }
# Inspect before changing anything, including junctions below owned directories.
function Inspect([string]$Path) {
    $item = Get-Item -LiteralPath $Path -Force
    if ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) {
        throw 'Installed payload must not contain links'
    }
    if ($item.PSIsContainer) {
        foreach ($child in Get-ChildItem -LiteralPath $Path -Force) { Inspect $child.FullName }
    }
}
foreach ($path in $payloads) {
    if (Test-Path -LiteralPath $path) { Inspect $path }
}
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
$cli = Join-Path $root 'mc-cli'
if (Test-Path -LiteralPath $cli) {
    $sid = [Security.Principal.WindowsIdentity]::GetCurrent().User
    # Only deny creating/writing files and directories. Preserve delete and
    # change-permissions rights so the installer can replace the owned tree.
    $rule = [Security.AccessControl.FileSystemAccessRule]::new(
        $sid, [Security.AccessControl.FileSystemRights]'WriteData,AppendData',
        [Security.AccessControl.InheritanceFlags]'ContainerInherit,ObjectInherit',
        [Security.AccessControl.PropagationFlags]::None,
        [Security.AccessControl.AccessControlType]::Deny)
    $acl = Get-Acl -LiteralPath $cli
    $acl.RemoveAccessRuleSpecific($rule)
    if ($Action -eq 'protect') { $acl.AddAccessRule($rule) }
    Set-Acl -LiteralPath $cli -AclObject $acl
}
if ($Action -eq 'prepare') {
    # These directories are immutable product resources, not a user-data store.
    foreach ($path in $payloads) {
        if (Test-Path -LiteralPath $path) { Remove-Item -LiteralPath $path -Recurse -Force }
    }
}
