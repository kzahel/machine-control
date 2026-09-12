using System.ComponentModel;
using System.IO;
using System.IO.Pipes;
using System.Runtime.InteropServices;
using System.Security.Principal;
using Microsoft.Win32.SafeHandles;

namespace MachineControl.Windows;

internal static class UnlockNative
{
    public static void RequireServicePeer(NamedPipeClientStream pipe, string instance)
    {
        if (!GetNamedPipeServerProcessId(pipe.SafePipeHandle, out var peer) ||
            peer == 0 || peer != ServiceProcessId(instance))
            throw new UnauthorizedAccessException("unlock_service_identity_mismatch");
    }

    public static uint ServiceProcessId(string instance)
    {
        var manager = OpenSCManager(null, null, 1); // SC_MANAGER_CONNECT
        if (manager == IntPtr.Zero) throw new Win32Exception(Marshal.GetLastWin32Error());
        try
        {
            var service = OpenService(manager, UnlockPolicy.Service(instance), 4); // QUERY_STATUS
            if (service == IntPtr.Zero) throw new InvalidDataException("unlock_not_installed");
            try
            {
                if (!QueryServiceStatusEx(service, 0, out var status,
                        Marshal.SizeOf<ServiceStatus>(), out _) || status.State != 4 || status.ProcessId == 0)
                    throw new InvalidDataException("unlock_service_not_running");
                return status.ProcessId;
            }
            finally { CloseServiceHandle(service); }
        }
        finally { CloseServiceHandle(manager); }
    }

    public static string ConsoleUserSid(uint sessionId)
    {
        SessionLauncher.EnablePrivilege("SeTcbPrivilege");
        if (sessionId == uint.MaxValue || sessionId != NativeMethods.WTSGetActiveConsoleSessionId() ||
            !NativeMethods.WTSQueryUserToken(sessionId, out var token))
            throw new InvalidDataException("console_account_unavailable");
        using var handle = new NativeHandle(token);
        using var identity = new WindowsIdentity(token);
        return identity.User?.Value ?? throw new InvalidDataException("console_account_unavailable");
    }

    public static void RequireLockedAccount(uint sessionId, string sid)
    {
        if (ConsoleUserSid(sessionId) != sid || SessionStateInspector.IsLocked(sessionId) != true)
            throw new InvalidDataException("locked_account_changed");
    }

    public static string ConsoleLogonId(uint sessionId)
    {
        SessionLauncher.EnablePrivilege("SeTcbPrivilege");
        if (!NativeMethods.WTSQueryUserToken(sessionId, out var token))
            throw new InvalidDataException("console_logon_unavailable");
        using var handle = new NativeHandle(token);
        var statistics = new byte[128];
        // TOKEN_STATISTICS begins with TokenId, then AuthenticationId (LUIDs).
        if (!GetTokenInformation(token, 10, statistics, statistics.Length, out var length) || length < 16)
            throw new InvalidDataException("console_logon_unavailable");
        return Convert.ToHexString(statistics.AsSpan(8, 8));
    }

    [DllImport("advapi32.dll", SetLastError = true)]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static extern bool GetTokenInformation(IntPtr token, int informationClass,
        [Out] byte[] information, int length, out int returnedLength);

    public static void RequireReleasedModifiers()
    {
        foreach (var key in new[] { 0x10, 0x11, 0x12, 0x5B, 0x5C })
            if ((GetAsyncKeyState(key) & 0x8000) != 0)
                throw new InvalidDataException("keyboard_modifier_held");
    }

    [DllImport("user32.dll")]
    private static extern short GetAsyncKeyState(int key);

    [StructLayout(LayoutKind.Sequential)]
    private struct ServiceStatus
    {
        public uint Type, State, Controls, ExitCode, ServiceExitCode, CheckPoint, WaitHint, ProcessId, Flags;
    }

    [DllImport("kernel32.dll", SetLastError = true)]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static extern bool GetNamedPipeServerProcessId(SafePipeHandle pipe, out uint processId);
    [DllImport("advapi32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
    private static extern IntPtr OpenSCManager(string? machine, string? database, uint access);
    [DllImport("advapi32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
    private static extern IntPtr OpenService(IntPtr manager, string name, uint access);
    [DllImport("advapi32.dll", SetLastError = true)]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static extern bool QueryServiceStatusEx(IntPtr service, int level, out ServiceStatus status,
        int size, out int needed);
    [DllImport("advapi32.dll")]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static extern bool CloseServiceHandle(IntPtr handle);
}
