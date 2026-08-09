#Requires -RunAsAdministrator

[CmdletBinding()]
param(
    [switch]$CheckOnly,
    [switch]$DecryptOsVolume,
    [switch]$ConfirmGeneralize,
    [string]$TaskName,
    [ValidateRange(0, 30)]
    [int]$StartDelaySeconds = 0
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$receiptRoot = Join-Path $env:ProgramData 'WinVM-Factory'
$receiptPath = Join-Path $receiptRoot 'generalization-receipt.json'
$winlogonPath = 'HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Winlogon'

function Remove-LsaPrivateData {
    param(
        [Parameter(Mandatory = $true)][string]$Name,
        [switch]$ValidateOnly
    )
    if (-not ('WinVM.Factory.Lsa' -as [type])) {
        Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;
namespace WinVM.Factory {
    public static class Lsa {
        [StructLayout(LayoutKind.Sequential)]
        private struct LSA_OBJECT_ATTRIBUTES {
            public uint Length;
            public IntPtr RootDirectory;
            public IntPtr ObjectName;
            public uint Attributes;
            public IntPtr SecurityDescriptor;
            public IntPtr SecurityQualityOfService;
        }
        [StructLayout(LayoutKind.Sequential)]
        private struct LSA_UNICODE_STRING {
            public ushort Length;
            public ushort MaximumLength;
            public IntPtr Buffer;
        }
        [DllImport("advapi32.dll")]
        private static extern uint LsaOpenPolicy(
            IntPtr systemName,
            ref LSA_OBJECT_ATTRIBUTES attributes,
            uint access,
            out IntPtr policy);
        [DllImport("advapi32.dll")]
        private static extern uint LsaStorePrivateData(
            IntPtr policy,
            ref LSA_UNICODE_STRING key,
            IntPtr value);
        [DllImport("advapi32.dll")]
        private static extern uint LsaNtStatusToWinError(uint status);
        [DllImport("advapi32.dll")]
        private static extern uint LsaClose(IntPtr handle);

        public static void RemovePrivateData(string name) {
            var attributes = new LSA_OBJECT_ATTRIBUTES();
            attributes.Length = (uint)Marshal.SizeOf(attributes);
            IntPtr policy;
            var status = LsaOpenPolicy(
                IntPtr.Zero,
                ref attributes,
                0x00000020,
                out policy);
            if (status != 0) {
                throw new InvalidOperationException(
                    "LsaOpenPolicy failed: " + LsaNtStatusToWinError(status));
            }
            var key = new LSA_UNICODE_STRING();
            key.Buffer = Marshal.StringToHGlobalUni(name);
            key.Length = (ushort)(name.Length * 2);
            key.MaximumLength = (ushort)((name.Length + 1) * 2);
            try {
                status = LsaStorePrivateData(policy, ref key, IntPtr.Zero);
                var error = LsaNtStatusToWinError(status);
                if (status != 0 && error != 2) {
                    throw new InvalidOperationException(
                        "LsaStorePrivateData failed: " + error);
                }
            }
            finally {
                Marshal.FreeHGlobal(key.Buffer);
                LsaClose(policy);
            }
        }
    }
}
'@
    }
    if ($ValidateOnly) { return }
    [WinVM.Factory.Lsa]::RemovePrivateData($Name)
}

$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$administrator = [Security.Principal.WindowsPrincipal]::new($identity).
    IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
$service = Get-Service -Name MachineControlRuntime -ErrorAction SilentlyContinue
$sysprep = Join-Path $env:WINDIR 'System32\Sysprep\Sysprep.exe'
$pendingReboot = @(@(
        'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Component Based Servicing\RebootPending',
        'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\WindowsUpdate\Auto Update\RebootRequired'
    ) | Where-Object { Test-Path -LiteralPath $_ })
Remove-LsaPrivateData -Name 'DefaultPassword' -ValidateOnly
$bitLocker = Get-BitLockerVolume -MountPoint $env:SystemDrive -ErrorAction Stop
$storageReady = $bitLocker.VolumeStatus.ToString() -eq 'FullyDecrypted'
$preflight = [ordered]@{
    schema = 'winvm-image-generalization/v0'
    administrator = $administrator
    sysprep_present = (Test-Path -LiteralPath $sysprep)
    runtime_installed = [bool]$service
    runtime_state = if ($service) { $service.Status.ToString() } else { $null }
    pending_reboot_markers = $pendingReboot.Count
    bitlocker_volume_status = $bitLocker.VolumeStatus.ToString()
    bitlocker_protection_status = $bitLocker.ProtectionStatus.ToString()
    bitlocker_encryption_percentage = $bitLocker.EncryptionPercentage
    sysprep_storage_ready = $storageReady
    profile = 'same-controller-utm-appliance'
    retained_controller_public_key = $true
    removes_ssh_host_identity = $true
    removes_autologon_secret = $true
    mode = 'generalize-oobe-shutdown-mode-vm'
}
if ($DecryptOsVolume) {
    if (-not $administrator) {
        throw 'OS-volume decryption requires an administrator'
    }
    if (-not $storageReady) {
        Disable-BitLocker -MountPoint $env:SystemDrive
        $deadline = [DateTime]::UtcNow.AddMinutes(30)
        do {
            Start-Sleep -Seconds 2
            $bitLocker = Get-BitLockerVolume -MountPoint $env:SystemDrive
            $storageReady = (
                $bitLocker.VolumeStatus.ToString() -eq 'FullyDecrypted')
        } while (-not $storageReady -and [DateTime]::UtcNow -lt $deadline)
    }
    [ordered]@{
        schema = 'winvm-image-storage-preparation/v0'
        volume_status = $bitLocker.VolumeStatus.ToString()
        protection_status = $bitLocker.ProtectionStatus.ToString()
        encryption_percentage = $bitLocker.EncryptionPercentage
        sysprep_storage_ready = $storageReady
    } | ConvertTo-Json -Compress
    exit $(if ($storageReady) { 0 } else { 1 })
}
if ($CheckOnly) {
    $preflight | ConvertTo-Json -Compress
    exit $(if ($administrator -and (Test-Path -LiteralPath $sysprep) -and
        $pendingReboot.Count -eq 0 -and $storageReady) { 0 } else { 1 })
}
Remove-Item -LiteralPath $receiptPath -Force -ErrorAction SilentlyContinue
trap {
    $failure = $_
    try {
        New-Item -ItemType Directory -Force -Path $receiptRoot | Out-Null
        [ordered]@{
            schema = 'winvm-image-generalization/v0'
            state = 'failed'
            error_type = $failure.Exception.GetType().FullName
            message = $failure.Exception.Message
            line = $failure.InvocationInfo.ScriptLineNumber
        } | ConvertTo-Json | Set-Content -LiteralPath `
            $receiptPath -Encoding utf8
    }
    catch { }
    throw $failure.Exception
}
if (-not $ConfirmGeneralize) {
    throw 'Generalization requires -ConfirmGeneralize'
}
if (-not $administrator -or -not (Test-Path -LiteralPath $sysprep)) {
    throw 'Generalization preflight failed'
}
if ($pendingReboot.Count -ne 0) {
    throw 'Generalization refuses a target with pending reboot markers'
}
if (-not $storageReady) {
    throw 'Generalization requires a fully decrypted OS volume'
}
if ($TaskName) {
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false `
        -ErrorAction SilentlyContinue
}
if ($StartDelaySeconds -gt 0) {
    Start-Sleep -Seconds $StartDelaySeconds
}

New-Item -ItemType Directory -Force -Path $receiptRoot | Out-Null
Remove-Item -Force -Recurse -ErrorAction SilentlyContinue -Path @(
    (Join-Path $env:ProgramData 'MachineControl\artifacts\*'),
    (Join-Path $env:LOCALAPPDATA 'MachineControl\workflow\*')
)
Remove-Item -Force -ErrorAction SilentlyContinue -LiteralPath @(
    'C:\Users\Public\machine-control-t006-remote.json',
    'C:\Users\Public\machine-control-t006-local.json',
    'C:\Users\Public\machine-control-t006-inbox.ps1'
)

Set-ItemProperty -LiteralPath $winlogonPath -Name AutoAdminLogon -Value '0'
Remove-ItemProperty -LiteralPath $winlogonPath -ErrorAction SilentlyContinue `
    -Name DefaultPassword,DefaultUserName,DefaultDomainName,AutoLogonCount
Remove-LsaPrivateData -Name 'DefaultPassword'

Stop-Service -Name sshd -Force -ErrorAction SilentlyContinue
Remove-Item -Force -ErrorAction SilentlyContinue `
    -Path (Join-Path $env:ProgramData 'ssh\ssh_host_*')
Set-Service -Name sshd -StartupType Automatic

[ordered]@{
    schema = 'winvm-image-generalization/v0'
    state = 'sysprep_requested'
    profile = 'same-controller-utm-appliance'
    generalized = $false
    next_boot = 'oobe'
    controller_public_key_retained = $true
    ssh_host_identity_removed = $true
    autologon_disabled = $true
    plaintext_default_password_present = [bool](
        (Get-ItemProperty -LiteralPath $winlogonPath).
            PSObject.Properties.Name -contains 'DefaultPassword')
} | ConvertTo-Json | Set-Content -LiteralPath $receiptPath -Encoding utf8

Remove-Item -Force -ErrorAction SilentlyContinue -LiteralPath $PSCommandPath
$process = Start-Process -FilePath $sysprep -ArgumentList @(
    '/generalize', '/oobe', '/shutdown', '/mode:vm', '/quiet'
) -Wait -PassThru
if ($process.ExitCode -ne 0) {
    throw "Sysprep exited with $($process.ExitCode)"
}
