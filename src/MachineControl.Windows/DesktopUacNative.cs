using System.ComponentModel;
using System.Diagnostics;
using System.IO;
using System.IO.Pipes;
using System.Runtime.InteropServices;
using System.Security.AccessControl;
using System.Security.Principal;
using System.Text;
using Microsoft.Win32.SafeHandles;

namespace MachineControl.Windows;

internal static class DesktopUacNative
{
    internal const string Service = "MachineControlDesktopUac";
    internal const string Pipe = "machine-control-desktop-uac";
    internal static string Root => Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.ProgramFiles), Service);
    internal static string Executable => Path.Combine(Root, "machine-control-windows.exe");

    internal static NamedPipeServerStream Server(string name, bool systemOnly = false)
    {
        var security = new PipeSecurity();
        security.SetAccessRuleProtection(true, false);
        security.AddAccessRule(new PipeAccessRule(new SecurityIdentifier(WellKnownSidType.LocalSystemSid, null), PipeAccessRights.FullControl, AccessControlType.Allow));
        using var identity = WindowsIdentity.GetCurrent();
        security.AddAccessRule(new PipeAccessRule(identity.User!, PipeAccessRights.FullControl, AccessControlType.Allow));
        if (!systemOnly)
            security.AddAccessRule(new PipeAccessRule(new SecurityIdentifier(WellKnownSidType.AuthenticatedUserSid, null), PipeAccessRights.ReadWrite, AccessControlType.Allow));
        return NamedPipeServerStreamAcl.Create(name, PipeDirection.InOut, 1, PipeTransmissionMode.Byte,
            PipeOptions.Asynchronous | PipeOptions.FirstPipeInstance, 65536, 65536, security);
    }

    internal static uint ClientPid(NamedPipeServerStream pipe)
    {
        if (!GetNamedPipeClientProcessId(pipe.SafePipeHandle, out var pid) || pid == 0)
            throw new UnauthorizedAccessException("uac_peer_unknown");
        return pid;
    }
    internal static void RequireServer(NamedPipeClientStream pipe, uint expectedPid)
    {
        if (!GetNamedPipeServerProcessId(pipe.SafePipeHandle, out var pid) || pid != expectedPid || pid == 0)
            throw new UnauthorizedAccessException("uac_server_identity_mismatch");
    }
    internal static void RequireSystem(NamedPipeServerStream pipe)
    {
        var system = false;
        pipe.RunAsClient(() => { using var identity = WindowsIdentity.GetCurrent(); system = identity.IsSystem; });
        if (!system) throw new UnauthorizedAccessException("uac_system_peer_required");
    }
    internal static async Task<string> ReadAsync(StreamReader reader, CancellationToken cancellation, int limit = 1024 * 1024)
    {
        var text = new StringBuilder();
        var character = new char[1];
        while (await reader.ReadAsync(character.AsMemory(), cancellation) != 0)
        {
            if (character[0] == '\n') return text.ToString();
            if (text.Length >= limit) throw new InvalidDataException("UAC frame exceeds limit");
            text.Append(character[0]);
        }
        throw new IOException("UAC peer disconnected");
    }
    internal static bool Installed()
    {
        try { UnlockAdmin.RequireProtectedPath(Executable, Root); return ServicePid() > 0; }
        catch (Exception ex) when (ex is IOException or UnauthorizedAccessException or Win32Exception or InvalidDataException) { return false; }
    }
    internal static uint ServicePid() => UnlockNative.NamedServiceProcessId(Service);

    internal static async Task<string> CallWorkerAsync(string name, uint workerPid, string frame, CancellationToken cancellation)
    {
        using var pipe = new NamedPipeClientStream(".", name, PipeDirection.InOut, PipeOptions.Asynchronous, TokenImpersonationLevel.Identification);
        await pipe.ConnectAsync(10000, cancellation);
        RequireServer(pipe, workerPid);
        using var writer = new StreamWriter(pipe, new UTF8Encoding(false), 4096, true) { AutoFlush = true };
        using var reader = new StreamReader(pipe, Encoding.UTF8, false, 4096, true);
        await writer.WriteLineAsync(frame.AsMemory(), cancellation);
        return await ReadAsync(reader, cancellation, 24 * 1024 * 1024);
    }

    internal static async Task<(uint Pid, uint Session)> RequireResidentAsync(NamedPipeServerStream pipe, CancellationToken cancellation, uint? residentPid = null)
    {
        var pid = residentPid ?? ClientPid(pipe);
        using var process = Process.GetProcessById((int)pid);
        if (!string.Equals(process.MainModule?.FileName, Executable, StringComparison.OrdinalIgnoreCase))
            throw new UnauthorizedAccessException("uac_resident_image_refused");
        UnlockAdmin.RequireProtectedPath(Executable, Root);
        if (!NativeMethods.OpenProcessToken(process.Handle, NativeMethods.TOKEN_QUERY, out var token))
            throw new Win32Exception(Marshal.GetLastWin32Error());
        using var tokenHandle = new NativeHandle(token);
        using var identity = new WindowsIdentity(token);
        var session = (uint)process.SessionId;
        if (TokenInspector.GetIntegrityRid(token) != 8192 || session == 0 ||
            session != NativeMethods.WTSGetActiveConsoleSessionId() ||
            identity.User?.Value != UnlockNative.ConsoleUserSid(session))
            throw new UnauthorizedAccessException("uac_console_identity_refused");
        string? callerSid = null;
        pipe.RunAsClient(() => { using var caller = WindowsIdentity.GetCurrent(); callerSid = caller.User?.Value; });
        if (callerSid != identity.User?.Value) throw new UnauthorizedAccessException("uac_caller_sid_refused");
        // A shared signed executable is not sufficient: require the actual
        // desktop resident to own its already-running ordinary endpoint.
        var name = $"machine-control-user-{callerSid}-{session}-desktop";
        using var resident = new NamedPipeClientStream(".", name, PipeDirection.InOut, PipeOptions.Asynchronous);
        await resident.ConnectAsync(2000, cancellation);
        RequireServer(resident, pid);
        using var output = new StreamWriter(resident, new UTF8Encoding(false), 4096, true) { AutoFlush = true };
        using var input = new StreamReader(resident, Encoding.UTF8, false, 4096, true);
        await output.WriteLineAsync("{\"operation\":\"status\"}".AsMemory(), cancellation);
        var status = Contract.ParseResult(await ReadAsync(input, cancellation));
        var state = System.Text.Json.JsonSerializer.SerializeToElement(status.Data, Contract.Json);
        if (!status.Accepted || !state.GetProperty("desktopProduct").GetBoolean() || state.GetProperty("processId").GetInt32() != pid)
            throw new UnauthorizedAccessException("uac_resident_endpoint_refused");
        return (pid, session);
    }

    [DllImport("kernel32.dll", SetLastError = true)]
    private static extern bool GetNamedPipeClientProcessId(SafePipeHandle pipe, out uint pid);
    [DllImport("kernel32.dll", SetLastError = true)]
    private static extern bool GetNamedPipeServerProcessId(SafePipeHandle pipe, out uint pid);
}
