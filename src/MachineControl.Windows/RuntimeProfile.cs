using System.ComponentModel;
using System.Runtime.InteropServices;
using System.IO;
using System.Security.Principal;
using System.Text.RegularExpressions;

namespace MachineControl.Windows;

internal static class RuntimeProfile
{
    public static bool IsUser { get; private set; }
    public static string Instance { get; private set; } = "default";
    // A process's session is fixed at launch. Process.SessionId asks .NET for
    // system-wide process information; never do that inside admission/Stop's
    // authority lock on every readiness refresh.
    public static int SessionId { get; } = CurrentSessionId();
    private static int CurrentSessionId()
    {
        if (!ProcessIdToSessionId((uint)Environment.ProcessId, out var session))
            throw new Win32Exception(Marshal.GetLastWin32Error());
        return checked((int)session);
    }
    [DllImport("kernel32.dll", SetLastError = true)]
    private static extern bool ProcessIdToSessionId(uint processId, out uint sessionId);
    public static string StateRoot => IsUser
        ? Path.Combine(Environment.GetFolderPath(
            Environment.SpecialFolder.LocalApplicationData),
            "MachineControl", "workstation", Instance, $"session-{SessionId}")
        : Path.Combine(Environment.GetFolderPath(
            Environment.SpecialFolder.CommonApplicationData), "MachineControl");
    public static string ArtifactRoot => Path.Combine(StateRoot, "artifacts");
    public static string ManagementRoot => Path.Combine(Environment.GetFolderPath(
        Environment.SpecialFolder.LocalApplicationData), "MachineControl", "packages", Instance);

    public static string ValidateInstance(string instance)
    {
        if (!Regex.IsMatch(instance, @"\A[a-z0-9][a-z0-9-]{0,47}\z"))
            throw new ArgumentException("instance must be 1-48 lowercase letters, digits or hyphens");
        return instance;
    }

    public static string UserPipe(string instance, int sessionId)
    {
        ValidateInstance(instance);
        if (sessionId <= 0)
            throw new ArgumentException("user mode requires an explicit interactive session ID outside that session");
        using var identity = WindowsIdentity.GetCurrent();
        var sid = identity.User?.Value
            ?? throw new InvalidOperationException("Current user SID is unavailable");
        return $"machine-control-user-{sid}-{sessionId}-{instance}";
    }

    public static void ConfigureUser(string instance)
    {
        if (DesktopController.GetIntegrityRid() != 8192 || SessionId == 0 ||
            NativeMethods.WTSGetActiveConsoleSessionId() != (uint)SessionId ||
            !string.Equals(DesktopController.GetCurrentDesktopName(), "Default",
                StringComparison.OrdinalIgnoreCase))
            throw new InvalidOperationException(
                "User runtime requires Medium integrity in the active console Default desktop");
        Instance = ValidateInstance(instance);
        IsUser = true;
    }
}
