using System.Diagnostics;
using System.IO;
using System.IO.Pipes;
using System.Text.Json;
using System.Text.RegularExpressions;

namespace MachineControl.Windows;

internal sealed class DesktopUnlockControl(string guardPipe, uint residentPid, uint session) : IAsyncDisposable
{
    private readonly CancellationTokenSource _end = new();
    private readonly CancellationTokenSource _watchStop = new();
    private NamedPipeServerStream? _guardian;
    private Process? _process;
    private Task? _watch;
    internal CancellationToken Interrupted => _end.Token;
    internal string Binding => Convert.ToHexString(System.Security.Cryptography.SHA256.HashData(
        System.Text.Encoding.UTF8.GetBytes(guardPipe + ":" + residentPid.ToString(System.Globalization.CultureInfo.InvariantCulture)))).ToLowerInvariant();

    internal static async Task<DesktopUnlockControl> CreateAsync(NamedPipeServerStream caller, UnlockHello hello, CancellationToken stop)
    {
        if (hello.ResidentPid is not > 0 || hello.GuardPipe is null ||
            !Regex.IsMatch(hello.GuardPipe, "\\Amachine-control-locked-guard-[a-f0-9]{32}\\z"))
            throw new UnauthorizedAccessException("desktop_unlock_preparation_required");
        var peer = await DesktopUacNative.RequireResidentAsync(caller, stop, hello.ResidentPid);
        var control = new DesktopUnlockControl(hello.GuardPipe, peer.Pid, peer.Session);
        try { if (!await control.QueryAsync(stop, attemptStarted: true)) throw new UnauthorizedAccessException("desktop_unlock_authority_refused"); }
        catch { await control.DisposeAsync(); throw; }
        return control;
    }

    private async Task<bool> QueryAsync(CancellationToken stop, bool physicalTakeover = false, bool complete = false, bool attemptStarted = false)
    {
        using var timeout = CancellationTokenSource.CreateLinkedTokenSource(stop);
        timeout.CancelAfter(TimeSpan.FromSeconds(2));
        using var pipe = new NamedPipeClientStream(".", guardPipe, PipeDirection.InOut, PipeOptions.Asynchronous,
            System.Security.Principal.TokenImpersonationLevel.Identification);
        await pipe.ConnectAsync(timeout.Token);
        DesktopUacNative.RequireServer(pipe, residentPid);
        await UnlockWire.WriteAsync(pipe, new { physicalTakeover, complete, attemptStarted }, timeout.Token);
        using var reply = JsonDocument.Parse(await UnlockWire.ReadLineAsync(pipe, timeout.Token));
        return reply.RootElement.GetProperty("allowed").GetBoolean();
    }

    internal void Check()
    {
        _end.Token.ThrowIfCancellationRequested();
        if (!QueryAsync(_end.Token).GetAwaiter().GetResult())
            throw new UnauthorizedAccessException("desktop_unlock_authority_changed");
    }

    internal async Task StartAsync(UnlockChallenge challenge, CancellationToken stop)
    {
        var name = "machine-control-relock-" + Guid.NewGuid().ToString("n");
        _guardian = PipeTransport.CreateSystemOnlyServer(name);
        var child = SessionLauncher.LaunchSystem(session, name, challenge.ServiceGeneration, relockGuardian: true);
        _process = Process.GetProcessById(child.ProcessId);
        _ = _process.Handle;
        using var timeout = CancellationTokenSource.CreateLinkedTokenSource(stop);
        timeout.CancelAfter(TimeSpan.FromSeconds(5));
        await _guardian.WaitForConnectionAsync(timeout.Token);
        DesktopUacNative.RequireSystem(_guardian);
        if (DesktopUacNative.ClientPid(_guardian) != child.ProcessId) throw new UnauthorizedAccessException("relock_guardian_identity_mismatch");
        await UnlockWire.WriteAsync(_guardian, new RelockStart(session, challenge.TargetUserSid, challenge.SessionLogonId), timeout.Token);
        using var ready = JsonDocument.Parse(await UnlockWire.ReadLineAsync(_guardian, timeout.Token));
        if (ready.RootElement.GetProperty("stage").GetString() != "ready") throw new IOException("relock_guardian_unavailable");
        _watch = WatchAsync();
    }

    private async Task WatchAsync()
    {
        var clock = Stopwatch.StartNew();
        try
        {
            while (!_watchStop.IsCancellationRequested && clock.Elapsed < TimeSpan.FromSeconds(900))
            {
                var allowed = await QueryAsync(_watchStop.Token);
                using var deadline = CancellationTokenSource.CreateLinkedTokenSource(_watchStop.Token);
                deadline.CancelAfter(TimeSpan.FromSeconds(2));
                await UnlockWire.WriteAsync(_guardian!, new { allowed }, deadline.Token);
                using var pulse = JsonDocument.Parse(await UnlockWire.ReadLineAsync(_guardian!, deadline.Token));
                if (pulse.RootElement.GetProperty("physicalTakeover").GetBoolean())
                {
                    _ = await QueryAsync(deadline.Token, physicalTakeover: true);
                    break;
                }
                if (!allowed) break;
                await Task.Delay(200, _watchStop.Token);
            }
        }
        catch (Exception error) when (error is IOException or UnauthorizedAccessException or OperationCanceledException or JsonException or InvalidOperationException) { }
        finally { _end.Cancel(); }
    }

    internal async Task WaitForEndAsync(CancellationToken stop)
    {
        if (_watch is not null) await _watch.WaitAsync(stop);
    }

    public async ValueTask DisposeAsync()
    {
        _watchStop.Cancel();
        _end.Cancel();
        if (_watch is not null) await _watch;
        // Closing the heartbeat pipe requests relock in the independent worker.
        // Never terminate that worker while its console is still unlocked.
        if (_guardian is not null) await _guardian.DisposeAsync();
        if (_process is not null)
        {
            try
            {
                using var wait = new CancellationTokenSource(TimeSpan.FromSeconds(12));
                await _process.WaitForExitAsync(wait.Token);
                if (_process.ExitCode == 0) _ = await QueryAsync(CancellationToken.None, complete: true);
            }
            catch (Exception error) when (error is OperationCanceledException or IOException or UnauthorizedAccessException or InvalidOperationException) { }
            _process.Dispose();
        }
        else
        {
            // No guardian means no credential worker could have been started.
            try { _ = await QueryAsync(CancellationToken.None, complete: true); }
            catch (Exception error) when (error is IOException or UnauthorizedAccessException or OperationCanceledException) { }
        }
        _end.Dispose(); _watchStop.Dispose();
    }
}

internal sealed record RelockStart(uint SessionId, string UserSid, string LogonId);
