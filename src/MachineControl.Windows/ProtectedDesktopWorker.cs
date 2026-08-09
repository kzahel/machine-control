using System.ComponentModel;
using System.Diagnostics;
using System.IO;
using System.Runtime.InteropServices;

namespace MachineControl.Windows;

internal static class ProtectedDesktopWorker
{
    public static async Task<Result> ExecuteAsync(
        Request request,
        string generation,
        string desktopName,
        CancellationToken cancellationToken)
    {
        var pipeName = $"machine-control-desktop-{Guid.NewGuid():n}";
        var processId = Launch(pipeName, generation, desktopName);
        try
        {
            var response = await PipeTransport.CallAsync(
                pipeName,
                Contract.Serialize(request),
                string.Equals(
                    request.Operation,
                    "session.login",
                    StringComparison.OrdinalIgnoreCase)
                    ? TimeSpan.FromSeconds(40)
                    : TimeSpan.FromSeconds(20),
                cancellationToken);
            return Contract.ParseResult(response);
        }
        finally
        {
            try
            {
                var process = Process.GetProcessById(processId);
                if (!process.HasExited)
                {
                    process.Kill(entireProcessTree: true);
                    process.WaitForExit(3000);
                }
            }
            catch { }
        }
    }

    public static async Task RunOneAsync(
        string pipeName,
        string generation,
        CancellationToken cancellationToken)
    {
        await using var server = PipeTransport.CreateSystemServer(pipeName);
        var (requestText, writer) = await PipeTransport.AcceptAsync(
            server,
            cancellationToken);
        await using (writer)
        {
            var request = Contract.ParseRequest(requestText);
            var response = await ProviderRouter.ExecuteAsync(
                request,
                generation,
                cancellationToken);
            await writer.WriteLineAsync(
                Contract.Serialize(response).AsMemory(),
                cancellationToken);
        }
    }

    private static int Launch(
        string pipeName,
        string generation,
        string desktopName)
    {
        var executable = Environment.ProcessPath
            ?? throw new InvalidOperationException(
                "Executable path is unavailable");
        var commandLine = $"\"{executable}\" desktop-worker " +
            $"--pipe {pipeName} --generation {generation}";
        var startup = new NativeMethods.STARTUPINFO
        {
            cb = Marshal.SizeOf<NativeMethods.STARTUPINFO>(),
            lpDesktop = $"winsta0\\{desktopName}",
        };
        if (!NativeMethods.CreateProcess(
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
            throw new Win32Exception(
                Marshal.GetLastWin32Error(),
                $"CreateProcess on desktop '{desktopName}' failed");
        }
        NativeMethods.CloseHandle(processInfo.hThread);
        NativeMethods.CloseHandle(processInfo.hProcess);
        return (int)processInfo.dwProcessId;
    }
}
