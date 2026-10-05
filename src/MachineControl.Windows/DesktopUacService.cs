using System.Diagnostics;
using System.IO;
using System.IO.Pipes;
using System.ServiceProcess;
using System.Text;
using System.Text.Json;

namespace MachineControl.Windows;

internal sealed record DesktopUacFrame(Request Request, string Generation, string GuardPipe, uint ResidentPid, int OperatorPid);
internal sealed record DesktopUacReply(Result Result, byte[]? Capture = null);

internal sealed class DesktopUacWindowsService : ServiceBase
{
    private readonly CancellationTokenSource _stop = new();
    private Task? _run;
    internal DesktopUacWindowsService() { ServiceName = DesktopUacNative.Service; CanStop = true; CanShutdown = true; }
    protected override void OnStart(string[] args) => _run = new DesktopUacService().RunAsync(_stop.Token);
    protected override void OnStop() { _stop.Cancel(); try { _run?.Wait(TimeSpan.FromSeconds(10)); } catch (AggregateException) { } }
    protected override void OnShutdown() => OnStop();
}

internal sealed class DesktopUacService
{
    private SessionProcess? _worker;
    private Process? _workerProcess;
    private uint _residentPid;

    internal async Task RunAsync(CancellationToken cancellation)
    {
        UnlockAdmin.RequireProtectedPath(Environment.ProcessPath!, DesktopUacNative.Root);
        try
        {
            while (!cancellation.IsCancellationRequested)
            {
                using var pipe = DesktopUacNative.Server(DesktopUacNative.Pipe);
                await pipe.WaitForConnectionAsync(cancellation);
                using var deadline = CancellationTokenSource.CreateLinkedTokenSource(cancellation);
                deadline.CancelAfter(TimeSpan.FromSeconds(35));
                try
                {
                    using var reader = new StreamReader(pipe, Encoding.UTF8, false, 4096, true);
                    var frame = JsonSerializer.Deserialize<DesktopUacFrame>(await DesktopUacNative.ReadAsync(reader, deadline.Token), Contract.Json)
                        ?? throw new InvalidDataException("UAC frame required");
                    var peer = await DesktopUacNative.RequireResidentAsync(pipe, deadline.Token);
                    if (frame.ResidentPid != peer.Pid || !System.Text.RegularExpressions.Regex.IsMatch(frame.GuardPipe, "\\Amachine-control-uac-guard-[a-f0-9]{32}\\z") ||
                        !DesktopUacPolicy.Operations.Contains(frame.Request.Operation, StringComparer.Ordinal))
                        throw new UnauthorizedAccessException("uac_frame_refused");
                    if (_worker?.SessionId != peer.Session || _residentPid != peer.Pid || _workerProcess?.HasExited != false)
                    {
                        StopWorker();
                        _residentPid = peer.Pid;
                        _worker = SessionLauncher.LaunchSystem(peer.Session, $"machine-control-uac-worker-{Guid.NewGuid():n}", Guid.NewGuid().ToString("n"), desktopUac: true);
                        _workerProcess = Process.GetProcessById(_worker.ProcessId);
                        _ = _workerProcess.Handle;
                    }
                    // Only this dedicated service can access the worker pipe.
                    var response = await DesktopUacNative.CallWorkerAsync(_worker.PipeName, (uint)_worker.ProcessId, Contract.Serialize(frame), deadline.Token);
                    await using var writer = new StreamWriter(pipe, new UTF8Encoding(false), 4096, true) { AutoFlush = true };
                    await writer.WriteLineAsync(response.AsMemory(), deadline.Token);
                }
                catch (Exception ex) when (ex is IOException or UnauthorizedAccessException or System.ComponentModel.Win32Exception or
                    JsonException or ArgumentException or InvalidOperationException or OperationCanceledException)
                {
                    // Uncertain operations are never replayed. Dropping a failed
                    // worker also invalidates all of its native references.
                    try { EventLog.WriteEntry(DesktopUacNative.Service, "Protected channel ended: " + ex.GetType().Name, EventLogEntryType.Warning); }
                    catch (Exception logError) when (logError is InvalidOperationException or System.ComponentModel.Win32Exception or System.Security.SecurityException) { }
                    StopWorker();
                }
            }
        }
        finally { StopWorker(); }
    }
    private void StopWorker()
    {
        if (_worker is null) return;
        try { if (_workerProcess?.HasExited == false) { _workerProcess.Kill(true); _workerProcess.WaitForExit(3000); } }
        catch (InvalidOperationException) { }
        finally { _workerProcess?.Dispose(); _workerProcess = null; }
        _worker = null;
    }
}
