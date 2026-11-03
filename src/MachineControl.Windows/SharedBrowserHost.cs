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
    internal bool Alive => _faulted == 0 && _disposed == 0 && !_process.HasExited;
    internal JsonObject State => (JsonObject)Volatile.Read(ref _state).DeepClone();

    internal SharedBrowserHost(ProcessStartInfo start, Action<JsonObject> receive, Func<JsonObject, bool> native, Action failed)
    {
        _receive = receive; _native = native; _failed = failed;
        start.UseShellExecute = false; start.CreateNoWindow = true;
        start.RedirectStandardInput = true; start.RedirectStandardOutput = true; start.RedirectStandardError = true;
        start.Environment.Clear();
        _process = Process.Start(start) ?? throw new IOException("Shared browser runtime did not start");
        _ = Task.Run(ReadAsync);
        _ = Task.Run(EventsAsync);
        _ = Task.Run(async () =>
        {
            var discard = new char[4096];
            while (await _process.StandardError.ReadAsync(discard.AsMemory(), _stop.Token) != 0) { }
        });
        try { _ = Call(new JsonObject { ["method"] = "hello", ["protocolVersion"] = 1 }, 15000); }
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

    internal JsonObject Call(JsonObject frame, int timeoutMs = 5000) => CallAsync(frame, CancellationToken.None, timeoutMs).GetAwaiter().GetResult();
    internal async Task<JsonObject> CallAsync(JsonObject frame, CancellationToken cancellation, int timeoutMs = 5000)
    {
        if (!Alive || _pending.Count >= 128) throw new IOException("Shared browser runtime unavailable");
        var id = Interlocked.Increment(ref _sequence).ToString(System.Globalization.CultureInfo.InvariantCulture);
        var completion = new TaskCompletionSource<JsonObject>(TaskCreationOptions.RunContinuationsAsynchronously);
        if (!_pending.TryAdd(id, completion)) throw new IOException("Duplicate runtime correlation");
        frame["id"] = id;
        try
        {
            await WriteAsync(frame);
            var reply = await completion.Task.WaitAsync(TimeSpan.FromMilliseconds(timeoutMs), cancellation);
            if (reply["ok"]?.GetValue<bool>() != true)
                throw new InvalidOperationException(reply["errorCode"]?.GetValue<string>() ?? "browser_runtime_refused");
            return reply["data"] as JsonObject ?? new JsonObject();
        }
        catch (TimeoutException) { Fault(); throw; }
    }

    private async Task WriteAsync(JsonObject frame)
    {
        await _writes.WaitAsync(_stop.Token);
        try
        {
            using var timeout = CancellationTokenSource.CreateLinkedTokenSource(_stop.Token);
            timeout.CancelAfter(TimeSpan.FromSeconds(3));
            await BrowserWire.WriteAsync(_process.StandardInput.BaseStream, frame, timeout.Token, BrowserWire.MaximumInput);
        }
        catch { Fault(); throw; }
        finally { _writes.Release(); }
    }

    private async Task ReadAsync()
    {
        try
        {
            while (await BrowserWire.ReadAsync(_process.StandardOutput.BaseStream, _stop.Token) is { } frame)
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
        catch (Exception ex) when (ex is IOException or OperationCanceledException or System.Text.Json.JsonException or InvalidOperationException or ObjectDisposedException) { }
        finally { Fault(); }
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
        catch (Exception ex) when (ex is IOException or OperationCanceledException or InvalidOperationException or ObjectDisposedException) { Fault(); }
    }
    private void Fault()
    {
        if (Interlocked.Exchange(ref _faulted, 1) != 0) return;
        foreach (var pending in _pending.Values) pending.TrySetException(new IOException("Shared browser runtime disconnected; delivery unknown"));
        _pending.Clear();
        Volatile.Write(ref _state, new JsonObject());
        if (_disposed == 0) _failed();
        try { if (!_process.HasExited) _process.Kill(entireProcessTree: true); } catch (InvalidOperationException) { }
    }
    public void Dispose()
    {
        if (Interlocked.Exchange(ref _disposed, 1) != 0) return;
        try { _process.StandardInput.Close(); if (!_process.WaitForExit(3000)) _process.Kill(entireProcessTree: true); }
        catch (InvalidOperationException) { }
        _stop.Cancel(); _events.Writer.TryComplete();
        Fault(); _process.Dispose();
    }
}
