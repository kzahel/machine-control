using System.Collections.Concurrent;
using System.Diagnostics;
using System.IO;
using System.Text.Json.Nodes;
using System.Threading.Channels;

namespace MachineControl.Windows;

/// Owned child and inherited framed IPC. No listener and no public approval API.
internal sealed class SharedBrowserHost : IDisposable
{
    private readonly Process _process;
    private readonly SemaphoreSlim _writes = new(1, 1);
    private readonly BlockingCollection<(JsonObject Frame, TaskCompletionSource<bool> Completion)> _outbound = new(1);
    private readonly CancellationTokenSource _stop = new();
    private readonly ConcurrentDictionary<string, TaskCompletionSource<JsonObject>> _pending = new();
    private readonly Channel<JsonObject> _events = Channel.CreateBounded<JsonObject>(512);
    private readonly Action _failed;
    private readonly Action<JsonObject> _receive;
    private readonly Func<JsonObject, bool> _native;
    private JsonObject _state = new();
    private int _disposed;
    private int _faulted;
    private long _sequence;
    private long _queuedBytes;
    private string? _failure;
    private string? _failureMethod;
    internal string? FailureMethod => Volatile.Read(ref _failureMethod);
    internal string? Failure => Volatile.Read(ref _failure);
    internal bool Alive => _faulted == 0 && _disposed == 0 && !_process.HasExited;
    internal JsonObject State => (JsonObject)Volatile.Read(ref _state).DeepClone();

    internal SharedBrowserHost(ProcessStartInfo start, Action<JsonObject> receive, Func<JsonObject, bool> native, Action failed)
    {
        _receive = receive; _native = native; _failed = failed;
        start.UseShellExecute = false; start.CreateNoWindow = true;
        start.RedirectStandardInput = true; start.RedirectStandardOutput = true; start.RedirectStandardError = true;
        start.Environment.Clear();
        // Windows OpenSSL entropy acquisition loads system providers through
        // SystemRoot. Retain only this OS-owned location, never Node options,
        // module search paths, caller credentials or arbitrary inherited env.
        if (OperatingSystem.IsWindows())
            start.Environment["SystemRoot"] = Environment.GetFolderPath(Environment.SpecialFolder.Windows);
        _process = Process.Start(start) ?? throw new IOException("Shared browser runtime did not start");
        // Windows anonymous pipe handles do not support overlapped I/O.
        // Async-over-sync reads can occupy the pool that must run writes and
        // their deadline continuations. Own the three blocking directions.
        StartIo(Read, "MachineControlPolicyRead");
        StartIo(Write, "MachineControlPolicyWrite");
        StartIo(() =>
        {
            try
            {
                var discard = new char[4096];
                while (_process.StandardError.Read(discard, 0, discard.Length) != 0) { }
            }
            catch (Exception ex) when (ex is IOException or ObjectDisposedException) { }
        }, "MachineControlPolicyError");
        _ = Task.Run(EventsAsync);
        try { _ = Call(new JsonObject { ["method"] = "hello", ["protocolVersion"] = 2 }, 15000); }
        catch { Dispose(); throw; }
    }

    internal static ProcessStartInfo Packaged()
    {
        var root = Path.Combine(AppContext.BaseDirectory, "shared-policy");
        var executable = Path.Combine(root, "node.exe");
        var entry = Path.Combine(root, "policy", "node", "main.ts");
        if (!File.Exists(executable) || !File.Exists(entry)) throw new IOException("Packaged shared browser runtime is missing");
        var start = new ProcessStartInfo(executable) { WorkingDirectory = root };
        start.ArgumentList.Add(entry);
        return start;
    }

    // Safety/metadata calls also run on STAs and occupied pool workers. Wait
    // directly for the owned I/O threads; async continuations need pool capacity
    // even with ConfigureAwait(false), and cannot implement this sync boundary.
    internal JsonObject Call(JsonObject frame, int timeoutMs = 5000)
    {
        var completion = Begin(frame);
        try
        {
            WriteSync(frame);
            return Reply(WaitSync(completion.Task, timeoutMs, _stop.Token));
        }
        catch (TimeoutException ex) { throw ReplyTimeout(frame, ex); }
    }
    internal async Task<JsonObject> CallAsync(JsonObject frame, CancellationToken cancellation, int timeoutMs = 5000)
    {
        var completion = Begin(frame);
        try
        {
            await WriteAsync(frame).ConfigureAwait(false);
            return Reply(await completion.Task.WaitAsync(TimeSpan.FromMilliseconds(timeoutMs), cancellation).ConfigureAwait(false));
        }
        catch (TimeoutException ex) { throw ReplyTimeout(frame, ex); }
    }
    private TaskCompletionSource<JsonObject> Begin(JsonObject frame)
    {
        if (!Alive) throw new IOException("Shared browser runtime unavailable");
        if (_pending.Count >= 128) throw new InvalidOperationException("browser_runtime_busy");
        var id = Interlocked.Increment(ref _sequence).ToString(System.Globalization.CultureInfo.InvariantCulture);
        var completion = new TaskCompletionSource<JsonObject>(TaskCreationOptions.RunContinuationsAsynchronously);
        if (!_pending.TryAdd(id, completion)) throw new IOException("Duplicate runtime correlation");
        frame["id"] = id;
        return completion;
    }
    private static JsonObject Reply(JsonObject reply)
    {
        if (reply["ok"]?.GetValue<bool>() != true)
            throw new InvalidOperationException(reply["errorCode"]?.GetValue<string>() ?? "browser_runtime_refused");
        return reply["data"] as JsonObject ?? new JsonObject();
    }
    private TimeoutException ReplyTimeout(JsonObject frame, TimeoutException error)
    {
        var method = frame["method"]?.GetValue<string>();
        Fault("ipc_reply_timeout", method);
        return new TimeoutException($"Shared browser runtime reply timed out ({method})", error);
    }
    private static T WaitSync<T>(Task<T> task, int milliseconds, CancellationToken cancellation)
    {
        try
        {
            if (!task.Wait(milliseconds, cancellation)) throw new TimeoutException();
        }
        catch (AggregateException) when (task.IsCompleted) { return task.GetAwaiter().GetResult(); }
        return task.GetAwaiter().GetResult();
    }

    private static void StartIo(ThreadStart action, string name) =>
        new Thread(action) { IsBackground = true, Name = name }.Start();

    private void Write()
    {
        foreach (var item in _outbound.GetConsumingEnumerable())
        {
            try
            {
                BrowserWire.Write(_process.StandardInput.BaseStream, item.Frame, BrowserWire.MaximumInput);
                item.Completion.TrySetResult(true);
            }
            catch (Exception ex)
            {
                item.Completion.TrySetException(ex);
                Fault(ex is IOException or ObjectDisposedException ? "ipc_write_failed" : "ipc_write_invalid",
                    item.Frame["method"]?.GetValue<string>());
            }
        }
    }

    private async Task WriteAsync(JsonObject frame)
    {
        await _writes.WaitAsync(_stop.Token).ConfigureAwait(false);
        try
        {
            await QueueWrite(frame).WaitAsync(TimeSpan.FromSeconds(3), _stop.Token).ConfigureAwait(false);
        }
        catch (Exception ex)
        {
            Fault(ex is TimeoutException or OperationCanceledException ? "ipc_write_timeout" :
                ex is IOException ? "ipc_write_failed" : "ipc_write_invalid", frame["method"]?.GetValue<string>());
            throw new IOException("Shared browser runtime write failed; delivery unknown", ex);
        }
        finally { _writes.Release(); }
    }
    private Task<bool> QueueWrite(JsonObject frame)
    {
        var written = new TaskCompletionSource<bool>(TaskCreationOptions.RunContinuationsAsynchronously);
        if (!_outbound.TryAdd((frame, written))) throw new IOException("Shared browser writer unavailable");
        return written.Task;
    }
    private void WriteSync(JsonObject frame)
    {
        var entered = false;
        try
        {
            entered = _writes.Wait(3000, _stop.Token);
            if (!entered) throw new TimeoutException();
            WaitSync(QueueWrite(frame), 3000, _stop.Token);
        }
        catch (Exception ex)
        {
            Fault(ex is TimeoutException or OperationCanceledException ? "ipc_write_timeout" :
                ex is IOException ? "ipc_write_failed" : "ipc_write_invalid", frame["method"]?.GetValue<string>());
            throw new IOException("Shared browser runtime write failed; delivery unknown", ex);
        }
        finally { if (entered) _writes.Release(); }
    }

    private void Read()
    {
        try
        {
            while (BrowserWire.Read(_process.StandardOutput.BaseStream) is { } frame)
            {
                var type = frame["type"]?.GetValue<string>();
                if (type == "reply")
                {
                    var id = frame["id"]?.GetValue<string>() ?? "";
                    if (_pending.TryRemove(id, out var pending)) pending.TrySetResult(frame);
                    else if (!id.StartsWith("native-reply:", StringComparison.Ordinal)) throw new IOException("Unknown shared runtime reply");
                }
                else if (type == "browser.state")
                    Volatile.Write(ref _state, frame["state"]!.AsObject());
                else if (type == "native.check")
                {
                    _ = Task.Run(async () =>
                    {
                        var accepted = false;
                        try { accepted = _native(frame); } catch (InvalidOperationException) { }
                        try
                        {
                            await WriteAsync(new JsonObject
                            {
                                ["id"] = "native-reply:" + frame["nativeId"]!.GetValue<string>(),
                                ["method"] = "native.reply",
                                ["nativeId"] = frame["nativeId"]!.DeepClone(),
                                ["accepted"] = accepted
                            });
                        }
                        catch (Exception ex) when (ex is IOException or OperationCanceledException or ObjectDisposedException) { }
                    });
                }
                else if (type == "provider.send" || type == "provider.close")
                {
                    var bytes = (long)frame.ToJsonString().Length * 3;
                    frame["queueBytes"] = bytes;
                    if (Interlocked.Add(ref _queuedBytes, bytes) > 32 * 1024 * 1024 || !_events.Writer.TryWrite(frame)) throw new IOException("Shared runtime output capacity");
                }
                else if (type != "request.finished") throw new IOException("Unknown shared runtime event");
            }
        }
        catch (Exception ex) when (ex is IOException or OperationCanceledException or System.Text.Json.JsonException or InvalidOperationException or ObjectDisposedException)
        { Fault(ex is System.Text.Json.JsonException ? "ipc_invalid_json" : ex is IOException ? "ipc_read_failed" : "ipc_invalid_frame"); }
        finally { Fault("ipc_closed"); }
    }

    private async Task EventsAsync()
    {
        try
        {
            await foreach (var frame in _events.Reader.ReadAllAsync(_stop.Token))
            {
                try { _receive(frame); }
                finally { Interlocked.Add(ref _queuedBytes, -frame["queueBytes"]!.GetValue<long>()); }
            }
        }
        catch (Exception ex) when (ex is IOException or OperationCanceledException or InvalidOperationException or ObjectDisposedException) { Fault("provider_output_failed"); }
    }
    private void Fault(string reason, string? method = null)
    {
        if (Interlocked.Exchange(ref _faulted, 1) != 0) return;
        Volatile.Write(ref _failure, reason);
        Volatile.Write(ref _failureMethod, method);
        foreach (var pending in _pending.Values) pending.TrySetException(new IOException("Shared browser runtime disconnected; delivery unknown"));
        _pending.Clear();
        Volatile.Write(ref _state, new JsonObject());
        _outbound.CompleteAdding();
        if (_disposed == 0) _failed();
        try { if (!_process.HasExited) _process.Kill(entireProcessTree: true); } catch (InvalidOperationException) { }
    }
    public void Dispose()
    {
        if (Interlocked.Exchange(ref _disposed, 1) != 0) return;
        _outbound.CompleteAdding();
        try
        {
            // A blocked synchronous writer is released by terminating our
            // exact child before closing its stream; disposal cannot queue
            // behind that write's stream lock.
            if (_writes.Wait(0))
            {
                try { _process.StandardInput.Close(); }
                finally { _writes.Release(); }
            }
            else if (!_process.HasExited) _process.Kill(entireProcessTree: true);
            if (!_process.WaitForExit(3000)) _process.Kill(entireProcessTree: true);
        }
        catch (Exception ex) when (ex is InvalidOperationException or IOException) { }
        _stop.Cancel(); _events.Writer.TryComplete();
        Fault("host_disposed"); _process.Dispose();
    }
}
