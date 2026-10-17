# Disposable/dedicated appliance experiment, not an installed unlock provider.
# The claimed controller owns lock, launch, independent readback and relock.
# Never supply a password, install an authentication package or switch users.
param(
    [Parameter(Mandatory=$true)][uint32]$ExpectedSession,
    [Parameter(Mandatory=$true)][string]$Output,
    [ValidateSet('wts-connect','tscon')][string]$Operation='wts-connect'
)
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
Add-Type -TypeDefinition @'
using System;
using System.ComponentModel;
using System.Diagnostics;
using System.Runtime.InteropServices;
using System.Security.Principal;
public static class SessionReconnectProbe {
    [DllImport("kernel32.dll")] public static extern uint WTSGetActiveConsoleSessionId();
    [DllImport("wtsapi32.dll", SetLastError=true)] static extern bool WTSQueryUserToken(uint session, out IntPtr token);
    [DllImport("wtsapi32.dll", SetLastError=true)] static extern bool WTSQuerySessionInformationW(IntPtr server, uint session, int info, out IntPtr buffer, out uint length);
    [DllImport("wtsapi32.dll")] static extern void WTSFreeMemory(IntPtr buffer);
    [DllImport("wtsapi32.dll", CharSet=CharSet.Unicode, SetLastError=true)]
    public static extern bool WTSConnectSessionW(uint source, uint destination, string password, bool wait);
    [DllImport("advapi32.dll", SetLastError=true)] static extern bool OpenProcessToken(IntPtr process, uint access, out IntPtr token);
    [DllImport("advapi32.dll", SetLastError=true)] static extern bool GetTokenInformation(IntPtr token, int info, byte[] buffer, int length, out int needed);
    [DllImport("advapi32.dll", CharSet=CharSet.Unicode, SetLastError=true)] static extern bool LookupPrivilegeValue(string system, string name, out long luid);
    [StructLayout(LayoutKind.Sequential,Pack=4)] struct Privileges { public uint Count; public long Luid; public uint Attributes; }
    [DllImport("advapi32.dll", SetLastError=true)] static extern bool AdjustTokenPrivileges(IntPtr token, bool disable, ref Privileges state, uint length, IntPtr previous, IntPtr needed);
    [DllImport("kernel32.dll")] static extern bool CloseHandle(IntPtr handle);
    public static bool Locked(uint session) {
        IntPtr buffer; uint length;
        if (!WTSQuerySessionInformationW(IntPtr.Zero, session, 25, out buffer, out length)) throw new Win32Exception();
        try {
            if (length < 20 || Marshal.ReadInt32(buffer) != 1) throw new InvalidOperationException("Unknown WTS observation");
            int flags=Marshal.ReadInt32(buffer,16);
            if (flags != 0 && flags != 1) throw new InvalidOperationException("Unknown lock flags");
            return flags == 0;
        } finally { WTSFreeMemory(buffer); }
    }
    public static string Logon(uint session) {
        IntPtr token=IntPtr.Zero;
        try {
            if (WindowsIdentity.GetCurrent().IsSystem) {
                if (!OpenProcessToken(Process.GetCurrentProcess().Handle, 0x28, out token)) throw new Win32Exception();
                long luid;
                if (!LookupPrivilegeValue(null,"SeTcbPrivilege",out luid)) throw new Win32Exception();
                var state=new Privileges { Count=1,Luid=luid,Attributes=2 };
                if (!AdjustTokenPrivileges(token,false,ref state,0,IntPtr.Zero,IntPtr.Zero) || Marshal.GetLastWin32Error()!=0) throw new Win32Exception();
                CloseHandle(token);token=IntPtr.Zero;
                if (!WTSQueryUserToken(session,out token)) throw new Win32Exception();
            } else {
                if (Process.GetCurrentProcess().SessionId != session) throw new InvalidOperationException("Wrong user session");
                if (!OpenProcessToken(Process.GetCurrentProcess().Handle,8,out token)) throw new Win32Exception();
            }
            byte[] value=new byte[128];int needed;
            if (!GetTokenInformation(token,10,value,value.Length,out needed) || needed<16) throw new Win32Exception();
            return BitConverter.ToString(value,8,8);
        } finally { if(token!=IntPtr.Zero) CloseHandle(token); }
    }
}
'@
$result=[ordered]@{
    schema='machine-control-session-reconnect-probe/v0'
    operation=$Operation
    caller=if([Security.Principal.WindowsIdentity]::GetCurrent().IsSystem){'LocalSystem'}else{'interactive_user'}
    sourceEqualsDestination=$true
    passwordSupplied=$false
    delivered=$false
    nativeError=$null
    unlocked=$false
    sameSessionAndLogon=$false
}
try {
    $session=[SessionReconnectProbe]::WTSGetActiveConsoleSessionId()
    if($session -ne $ExpectedSession -or $session -eq [uint32]::MaxValue){throw 'Console changed'}
    if(-not [SessionReconnectProbe]::Locked($session)){throw 'Experiment requires an already locked console'}
    $logon=[SessionReconnectProbe]::Logon($session)
    if($Operation -eq 'wts-connect') {
        $result.delivered=[SessionReconnectProbe]::WTSConnectSessionW($session,$session,'',$true)
        $result.nativeError=if($result.delivered){0}else{[Runtime.InteropServices.Marshal]::GetLastWin32Error()}
    } else {
        $child=Start-Process "$env:WINDIR\System32\tscon.exe" -ArgumentList @($session,'/dest:console') -Wait -PassThru -WindowStyle Hidden
        $result.nativeError=$child.ExitCode
        $result.delivered=$child.ExitCode -eq 0
    }
    Start-Sleep -Seconds 2
    $result.sameSessionAndLogon=[SessionReconnectProbe]::WTSGetActiveConsoleSessionId() -eq $session -and [SessionReconnectProbe]::Logon($session) -eq $logon
    $result.unlocked=-not [SessionReconnectProbe]::Locked($session)
} catch {
    $result['failure']=$_.Exception.Message
} finally {
    $result | ConvertTo-Json | Set-Content -LiteralPath $Output -Encoding UTF8
}
