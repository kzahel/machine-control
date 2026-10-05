using System.Collections.Concurrent;
using System.IO;
using System.Net;
using System.Net.Sockets;
using System.Net.WebSockets;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using System.Text.Json.Nodes;
using System.Text.RegularExpressions;
using System.Threading.Channels;

namespace MachineControl.Windows;

internal interface IBrowserDevToolsProvider
{
    bool Connected { get; }
    string Generation { get; }
    Task OpenAsync(string id, int tabId, Request authority, string generation, string providerGeneration,
        Action<JsonObject> receive, CancellationToken cancellation);
    Task CommandAsync(string id, JsonObject command, Request authority, string generation,
        string providerGeneration, CancellationToken cancellation);
    Task CloseAsync(string id, string providerGeneration);
}

/// Target-loopback transport over an existing owner, never a second admission
/// channel. Tokens, commands, page data and events do not enter the journal.
internal sealed class BrowserDevToolsBridge : IDisposable
{
    private readonly DesktopGrants _grants;
    private readonly IBrowserDevToolsProvider _provider;
    private readonly TcpListener _listener = new(IPAddress.Loopback, 0);
    private readonly object _gate = new();
    private readonly Dictionary<string, Binding> _tokens = new(StringComparer.Ordinal);
    private readonly ConcurrentDictionary<int, byte> _tabs = new();
    private readonly SemaphoreSlim _slots = new(8, 8);
    private readonly ConcurrentDictionary<long, Task> _connections = new();
    private long _nextConnection;
    internal int Port { get; }

    internal BrowserDevToolsBridge(DesktopGrants grants, IBrowserDevToolsProvider provider)
    {
        _grants = grants; _provider = provider;
        _listener.Start(8);
        Port = ((IPEndPoint)_listener.LocalEndpoint).Port;
    }

    private bool Authorized(Binding binding)
    {
        if (Volatile.Read(ref binding.Revoked) != 0) return false;
        if (_provider.Connected && binding.Provider == _provider.Generation &&
            _grants.Authorize(binding.Authority, binding.Generation) is null) return true;
        Interlocked.Exchange(ref binding.Revoked, 1);
        return false;
    }

    internal Result Endpoint(Request request, Result result)
    {
        var binding = new Binding(request with { Operation = "browser.cdp" }, _grants.Generation, _provider.Generation);
        if (_grants.Authorize(request, request.ExpectedGeneration) is { } denied) return result with { ErrorCode = denied };
        if (!Authorized(binding)) return result with { ErrorCode = "browser_provider_unavailable" };
        if (_grants.Journal?.Begin("browser.endpoint", request.RequestId, binding.Generation) == false)
            return result with { ErrorCode = "audit_storage_unavailable" };
        string token;
        lock (_gate)
        {
            foreach (var entry in _tokens.Where(entry => !Authorized(entry.Value)).ToArray()) _tokens.Remove(entry.Key);
            token = _tokens.FirstOrDefault(entry => entry.Value.Authority.ControlOwnership?.Owner == request.ControlOwnership?.Owner &&
                entry.Value.Authority.ControlOwnership?.Intent == request.ControlOwnership?.Intent &&
                entry.Value.Authority.ControlOwnership?.Session == request.ControlOwnership?.Session &&
                entry.Value.Generation == binding.Generation && entry.Value.Provider == binding.Provider).Key;
            if (token is null)
            {
                if (_tokens.Count >= 16) return result with { ErrorCode = "browser_stream_capacity" };
                token = Convert.ToHexString(RandomNumberGenerator.GetBytes(32)).ToLowerInvariant();
                _tokens.Add(token, binding);
            }
        }
        return result with
        {
            Accepted = true,
            Generation = binding.Generation,
            Delivery = "confirmed",
            Effect = "not_applicable",
            Uncertainty = "none",
            RetrySafety = "safe_observation",
            Data = new
            {
                devtoolsEndpoint = $"ws://127.0.0.1:{Port}/devtools/page/<tabId>?token={token}",
                binding = "live_devtools_owner",
                retainedOwnerRequired = true,
                maximumConnections = 8,
                maximumCommandBytes = BrowserWire.MaximumOutput,
                maximumOutstandingCommands = 16,
                commandTimeoutMs = 45000,
                applicationEffect = "not_independently_observed"
            }
        };
    }

    internal async Task RunAsync(CancellationToken cancellation)
    {
        try
        {
            while (!cancellation.IsCancellationRequested)
            {
                var client = await _listener.AcceptTcpClientAsync(cancellation);
                if (!_slots.Wait(0)) { client.Dispose(); continue; }
                var id = Interlocked.Increment(ref _nextConnection);
                var task = ServeAsync(client, cancellation);
                _connections[id] = task;
                _ = task.ContinueWith(_ => { _connections.TryRemove(id, out var removed); }, TaskScheduler.Default);
            }
        }
        catch (OperationCanceledException) when (cancellation.IsCancellationRequested) { }
        finally
        {
            _listener.Stop();
            await Task.WhenAll(_connections.Values);
            lock (_gate) _tokens.Clear();
        }
    }

    // No URL ACL, HTTP framework or browser debug port is needed. Read only the
    // bounded upgrade header; never overread bytes belonging to the WebSocket.
    private async Task<(Binding Binding, int Tab)?> UpgradeAsync(NetworkStream stream, CancellationToken cancellation)
    {
        var bytes = new byte[8192];
        var count = 0;
        while (count < bytes.Length)
        {
            if (await stream.ReadAsync(bytes.AsMemory(count, 1), cancellation) == 0) return null;
            count++;
            if (count >= 4 && bytes.AsSpan(count - 4, 4).SequenceEqual("\r\n\r\n"u8)) break;
        }
        if (count == bytes.Length || bytes.AsSpan(0, count).ContainsAnyExceptInRange((byte)9, (byte)126)) return null;
        var lines = Encoding.ASCII.GetString(bytes, 0, count).Split("\r\n");
        var request = lines[0].Split(' ');
        if (request.Length != 3 || request[0] != "GET" || request[2] != "HTTP/1.1") return null;
        var match = Regex.Match(request[1], @"\A/devtools/page/([1-9][0-9]*)\?token=([a-f0-9]{64})\z");
        if (!match.Success || !int.TryParse(match.Groups[1].Value, out var tab)) return null;
        var headers = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);
        foreach (var line in lines.Skip(1).Where(line => line.Length > 0))
        {
            var colon = line.IndexOf(':');
            if (colon <= 0 || !Regex.IsMatch(line[..colon], @"\A[A-Za-z0-9-]+\z") ||
                !headers.TryAdd(line[..colon], line[(colon + 1)..].Trim())) return null;
        }
        if (headers.ContainsKey("Origin") || headers.ContainsKey("Content-Length") || headers.ContainsKey("Transfer-Encoding") ||
            !headers.TryGetValue("Host", out var host) || host != $"127.0.0.1:{Port}" ||
            !headers.TryGetValue("Upgrade", out var upgrade) || !upgrade.Equals("websocket", StringComparison.OrdinalIgnoreCase) ||
            !headers.TryGetValue("Connection", out var connection) || !connection.Split(',').Any(value => value.Trim().Equals("Upgrade", StringComparison.OrdinalIgnoreCase)) ||
            !headers.TryGetValue("Sec-WebSocket-Version", out var version) || version != "13" ||
            !headers.TryGetValue("Sec-WebSocket-Key", out var key) || !ValidKey(key)) return null;
        Binding? binding;
        lock (_gate) _tokens.TryGetValue(match.Groups[2].Value, out binding);
        if (binding is null || !Authorized(binding) || !_tabs.TryAdd(tab, 0)) return null;
        try
        {
            var accept = Convert.ToBase64String(SHA1.HashData(Encoding.ASCII.GetBytes(key + "258EAFA5-E914-47DA-95CA-C5AB0DC85B11")));
            await stream.WriteAsync(Encoding.ASCII.GetBytes("HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Accept: " + accept + "\r\n\r\n"), cancellation);
            return (binding, tab);
        }
        catch { _tabs.TryRemove(tab, out _); throw; }
    }

    private static bool ValidKey(string key)
    {
        try { return Convert.FromBase64String(key).Length == 16; }
        catch (FormatException) { return false; }
    }

    private async Task ServeAsync(TcpClient client, CancellationToken cancellation)
    {
        int? tab = null;
        try
        {
            using (client)
            {
                client.NoDelay = true;
                using var handshake = CancellationTokenSource.CreateLinkedTokenSource(cancellation);
                handshake.CancelAfter(TimeSpan.FromSeconds(5));
                var stream = client.GetStream();
                var upgrade = await UpgradeAsync(stream, handshake.Token);
                if (upgrade is null) return;
                tab = upgrade.Value.Tab;
                using var socket = WebSocket.CreateFromStream(stream, isServer: true, subProtocol: null, keepAliveInterval: TimeSpan.FromSeconds(20));
                await SessionAsync(socket, upgrade.Value.Binding, tab.Value, cancellation);
            }
        }
        catch (Exception ex) when (ex is IOException or SocketException or WebSocketException or OperationCanceledException or JsonException or InvalidOperationException or ArgumentException or TimeoutException) { }
        finally
        {
            if (tab is int ownedTab) _tabs.TryRemove(ownedTab, out _);
            _slots.Release();
        }
    }

    private async Task SessionAsync(WebSocket socket, Binding binding, int tab, CancellationToken cancellation)
    {
        using var stop = CancellationTokenSource.CreateLinkedTokenSource(cancellation);
        var id = Guid.NewGuid().ToString("n");
        var opened = new TaskCompletionSource(TaskCreationOptions.RunContinuationsAsynchronously);
        var output = Channel.CreateBounded<byte[]>(new BoundedChannelOptions(64) { SingleReader = true, FullMode = BoundedChannelFullMode.Wait });
        long queuedBytes = 0;
        var pending = new ConcurrentDictionary<int, Pending>();
        void Abort()
        {
            // A provider reader can already hold this callback when CloseAsync
            // removes its registration. Teardown must remain idempotent.
            try { stop.Cancel(); } catch (ObjectDisposedException) { }
            try { socket.Abort(); } catch (ObjectDisposedException) { }
        }
        void Queue(JsonObject frame)
        {
            var bytes = JsonSerializer.SerializeToUtf8Bytes(frame, Contract.Json);
            if (Interlocked.Add(ref queuedBytes, bytes.Length) > BrowserWire.MaximumInput || !output.Writer.TryWrite(bytes))
            {
                Interlocked.Add(ref queuedBytes, -bytes.Length); Abort();
            }
        }
        bool Audit(Pending command, bool confirmed) => _grants.Journal?.Record(new Result
        {
            RequestId = command.Id,
            Operation = "browser.cdp",
            Accepted = true,
            Generation = binding.Generation,
            ActualRoute = BrowserWire.Route,
            Delivery = confirmed ? "confirmed" : "unknown",
            Effect = "unverifiable",
            Uncertainty = confirmed ? "application_effect_not_independently_observed" : "browser_completion_not_observed",
            RetrySafety = confirmed ? "unsafe_to_replay" : "unsafe_delivery_unknown"
        }) != false;
        void Receive(JsonObject frame)
        {
            if (stop.IsCancellationRequested) return;
            try
            {
                if (!Authorized(binding)) { Abort(); return; }
                switch (frame["type"]?.GetValue<string>())
                {
                    case "session.opened": opened.TrySetResult(); return;
                    case "session.failed":
                    case "session.closed": opened.TrySetCanceled(); Abort(); return;
                    case "session.result":
                        var cmdId = frame["cmdId"]!.GetValue<int>();
                        if (!pending.TryRemove(cmdId, out var command)) { Abort(); return; }
                        if (!Audit(command, true)) { Abort(); return; }
                        var reply = new JsonObject { ["id"] = cmdId };
                        if (frame["error"] is { } error) reply["error"] = error.DeepClone();
                        else reply["result"] = frame["result"]?.DeepClone() ?? new JsonObject();
                        Queue(reply);
                        return;
                    case "session.event":
                        Queue(new JsonObject
                        {
                            ["method"] = frame["method"]!.DeepClone(),
                            ["params"] = frame["params"]?.DeepClone() ?? new JsonObject()
                        });
                        return;
                }
            }
            catch (Exception ex) when (ex is InvalidOperationException or FormatException) { Abort(); }
        }
        async Task Monitor()
        {
            while (!stop.IsCancellationRequested)
            {
                if (!Authorized(binding) || pending.Values.Any(command => Environment.TickCount64 - command.Started > 45000)) { Abort(); return; }
                await Task.Delay(50, stop.Token);
            }
        }
        async Task Write()
        {
            await foreach (var bytes in output.Reader.ReadAllAsync(stop.Token))
            {
                if (!Authorized(binding)) { Abort(); return; }
                using var timeout = CancellationTokenSource.CreateLinkedTokenSource(stop.Token);
                timeout.CancelAfter(TimeSpan.FromSeconds(3));
                await socket.SendAsync(bytes.AsMemory(), WebSocketMessageType.Text, true, timeout.Token);
                Interlocked.Add(ref queuedBytes, -bytes.Length);
            }
        }
        async Task Read()
        {
            var bytes = new byte[BrowserWire.MaximumOutput];
            while (!stop.IsCancellationRequested)
            {
                var count = 0;
                ValueWebSocketReceiveResult received;
                do
                {
                    received = await socket.ReceiveAsync(bytes.AsMemory(count), stop.Token);
                    if (received.MessageType != WebSocketMessageType.Text) return;
                    count += received.Count;
                    if (count >= bytes.Length) return;
                } while (!received.EndOfMessage);
                var command = JsonNode.Parse(bytes.AsSpan(0, count))?.AsObject();
                if (command is null || !ValidCommand(command) || pending.Count >= 16 || !Authorized(binding)) return;
                var commandId = command["id"]!.GetValue<int>();
                var audit = new Pending(Guid.NewGuid().ToString("n"), Environment.TickCount64);
                if (!pending.TryAdd(commandId, audit)) return;
                if (_grants.Journal?.Begin("browser.cdp", audit.Id, binding.Generation) == false) return;
                await _provider.CommandAsync(id, command, binding.Authority, binding.Generation, binding.Provider, stop.Token);
            }
        }
        Task[] tasks = [];
        var openIntent = false;
        var openRecorded = false;
        var attachment = new Pending(id, Environment.TickCount64);
        try
        {
            if (_grants.Journal?.Begin("browser.cdp", id, binding.Generation) == false) return;
            openIntent = true;
            await _provider.OpenAsync(id, tab, binding.Authority, binding.Generation, binding.Provider, Receive, stop.Token);
            tasks = [Monitor(), Write()];
            await opened.Task.WaitAsync(TimeSpan.FromSeconds(5), stop.Token);
            openRecorded = true;
            if (!Audit(attachment, true)) return;
            tasks = [.. tasks, Read()];
            await Task.WhenAny(tasks);
        }
        finally
        {
            Abort();
            await _provider.CloseAsync(id, binding.Provider);
            try { await Task.WhenAll(tasks); }
            catch (Exception ex) when (ex is IOException or WebSocketException or OperationCanceledException or JsonException or InvalidOperationException or ArgumentException) { }
            foreach (var command in pending.Values) Audit(command, false);
            if (openIntent && !openRecorded) Audit(attachment, false);
            _grants.Journal?.Event("browser.stream.closed");
        }
    }

    internal static bool ValidCommand(JsonObject command) => command.Count is 2 or 3 &&
        command.All(entry => entry.Key is "id" or "method" or "params") &&
        command["id"] is JsonValue id && id.TryGetValue<int>(out var value) && value >= 0 &&
        command["method"] is JsonValue method && method.TryGetValue<string>(out var name) &&
        name.Length <= 160 && Regex.IsMatch(name, @"\A[A-Za-z][A-Za-z0-9_]*\.[A-Za-z][A-Za-z0-9_]*\z") &&
        (!command.ContainsKey("params") || command["params"] is JsonObject);

    public void Dispose() => _listener.Stop();
    private sealed record Binding(Request Authority, string Generation, string Provider)
    {
        internal int Revoked;
    }
    private sealed record Pending(string Id, long Started);
}
