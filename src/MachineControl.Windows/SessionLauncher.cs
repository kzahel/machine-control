using System.ComponentModel;
using System.Diagnostics;
using System.IO;
using System.Runtime.InteropServices;

namespace MachineControl.Windows;

internal sealed record SessionProcess(
    uint SessionId,
    int ProcessId,
    string PipeName,
    string Authority);

internal static class SessionLauncher
{
    public static SessionProcess LaunchSystem(
        uint sessionId,
        string pipeName,
        string generation)
    {
        EnablePrivilege("SeAssignPrimaryTokenPrivilege");
        EnablePrivilege("SeIncreaseQuotaPrivilege");
        EnablePrivilege("SeTcbPrivilege");

        if (!NativeMethods.OpenProcessToken(
                Process.GetCurrentProcess().Handle,
                NativeMethods.TOKEN_ALL_NEEDED,
                out var processToken))
        {
            throw new Win32Exception(Marshal.GetLastWin32Error());
        }

        using var processTokenHandle = new NativeHandle(processToken);
        if (!NativeMethods.DuplicateTokenEx(
                processToken,
                NativeMethods.MAXIMUM_ALLOWED,
                IntPtr.Zero,
                NativeMethods.SecurityImpersonation,
                NativeMethods.TokenPrimary,
                out var sessionToken))
        {
            throw new Win32Exception(Marshal.GetLastWin32Error());
        }

        using var sessionTokenHandle = new NativeHandle(sessionToken);
        var sessionValue = sessionId;
        if (!NativeMethods.SetTokenInformation(
                sessionToken,
                NativeMethods.TokenSessionId,
                ref sessionValue,
                sizeof(uint)))
        {
            throw new Win32Exception(Marshal.GetLastWin32Error());
        }

        return LaunchWithToken(
            sessionToken,
            sessionId,
            pipeName,
            generation,
            "LocalSystem");
    }

    public static SessionProcess LaunchUser(
        uint sessionId,
        string pipeName,
        string generation)
    {
        EnablePrivilege("SeAssignPrimaryTokenPrivilege");
        EnablePrivilege("SeIncreaseQuotaPrivilege");
        EnablePrivilege("SeTcbPrivilege");
        if (!NativeMethods.WTSQueryUserToken(sessionId, out var userToken))
        {
            throw new Win32Exception(Marshal.GetLastWin32Error());
        }
        using var userTokenHandle = new NativeHandle(userToken);
        return LaunchWithToken(
            userToken,
            sessionId,
            pipeName,
            generation,
            "interactive-user");
    }

    private static SessionProcess LaunchWithToken(
        IntPtr token,
        uint sessionId,
        string pipeName,
        string generation,
        string authority)
    {
        var executable = Environment.ProcessPath
            ?? throw new InvalidOperationException("Executable path is unavailable");
        var commandLine = $"\"{executable}\" session --pipe {pipeName} " +
            $"--generation {generation}";
        var startup = new NativeMethods.STARTUPINFO
        {
            cb = Marshal.SizeOf<NativeMethods.STARTUPINFO>(),
            lpDesktop = "winsta0\\default",
        };

        if (!NativeMethods.CreateProcessAsUser(
                token,
                null,
                commandLine,
                IntPtr.Zero,
                IntPtr.Zero,
                false,
                NativeMethods.CREATE_UNICODE_ENVIRONMENT |
                NativeMethods.CREATE_NO_WINDOW,
                IntPtr.Zero,
                Path.GetDirectoryName(executable),
                ref startup,
                out var processInfo))
        {
            throw new Win32Exception(Marshal.GetLastWin32Error());
        }

        NativeMethods.CloseHandle(processInfo.hThread);
        NativeMethods.CloseHandle(processInfo.hProcess);
        return new SessionProcess(
            sessionId,
            (int)processInfo.dwProcessId,
            pipeName,
            authority);
    }

    private static void EnablePrivilege(string privilege)
    {
        if (!NativeMethods.OpenProcessToken(
                Process.GetCurrentProcess().Handle,
                NativeMethods.TOKEN_ADJUST_PRIVILEGES | NativeMethods.TOKEN_QUERY,
                out var token))
        {
            throw new Win32Exception(Marshal.GetLastWin32Error());
        }
        using var tokenHandle = new NativeHandle(token);
        if (!NativeMethods.LookupPrivilegeValue(null, privilege, out var luid))
        {
            throw new Win32Exception(Marshal.GetLastWin32Error());
        }
        var privileges = new NativeMethods.TOKEN_PRIVILEGES
        {
            PrivilegeCount = 1,
            Privileges = new NativeMethods.LUID_AND_ATTRIBUTES
            {
                Luid = luid,
                Attributes = NativeMethods.SE_PRIVILEGE_ENABLED,
            },
        };
        if (!NativeMethods.AdjustTokenPrivileges(
                token,
                false,
                ref privileges,
                0,
                IntPtr.Zero,
                IntPtr.Zero))
        {
            throw new Win32Exception(Marshal.GetLastWin32Error());
        }
    }
}

internal sealed class NativeHandle(IntPtr handle) : IDisposable
{
    public IntPtr Value { get; } = handle;
    public void Dispose()
    {
        if (Value != IntPtr.Zero && Value != new IntPtr(-1))
        {
            NativeMethods.CloseHandle(Value);
        }
    }
}
