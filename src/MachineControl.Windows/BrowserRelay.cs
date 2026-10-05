using System.Collections.Concurrent;
using System.Diagnostics;
using System.IO;
using System.IO.Pipes;
using System.Runtime.InteropServices;
using System.Security.Cryptography;
using System.Text.Json;
using System.Text.Json.Nodes;
using Microsoft.Win32.SafeHandles;

namespace MachineControl.Windows;

/// Only the bundled apphost can register as provider. Browser messages never
/// enter the public agent pipe or operator approval channel.
internal sealed class BrowserRelay(DesktopGrants grants) : IBrowserDevToolsProvider
{
    internal const string Route = BrowserWire.Route;
    private readonly SemaphoreSlim _writes = new(1, 1);
    private readonly ConcurrentDictionary<string, TaskCompletionSource<JsonObject>> _pending = new();
    private readonly ConcurrentDictionary<string, Action<JsonObject>> _sessions = new();
    internal BrowserDevToolsBridge? DevTools { get; set; }
    private NamedPipeServerStream? _provider;
    private JsonObject? _hello;
    private string? _publishedState;
    private string _providerGeneration = Guid.NewGuid().ToString("n");
    internal bool Connected => _provider?.IsConnected == true && _hello is not null;
    bool IBrowserDevToolsProvider.Connected => Connected;
    string IBrowserDevToolsProvider.Generation => _providerGeneration;
    internal object State => new
    {
        connected = Connected,
        available = true,
        route = Route,
        extensionVersion = _hello?["extensionVersion"]?.GetValue<string>(),
        knownOmissions = new[] { "isolated browser contexts", "browser-wide downloads and shutdown", "restricted pages and CDP domains" },
        streamingCdp = new { available = DevTools is not null, browserLevel = true, context = "existing_default_profile", binding = "live_devtools_owner", transport = "target_loopback_websocket" },
        fileUpload = new { maximumFiles = BrowserUpload.MaximumFiles, paths = "target_local_drive", osDialog = false }
    };

    internal async Task RunAsync(CancellationToken cancellation)
    {
        using var pipe = UserHost.CreatePipe(RuntimeProfile.UserPipe("desktop-browser", RuntimeProfile.SessionId), first: true);
        while (!cancellation.IsCancellationRequested)
        {
            try
            {
                await pipe.WaitForConnectionAsync(cancellation);
                using var handshake = CancellationTokenSource.CreateLinkedTokenSource(cancellation);
                handshake.CancelAfter(TimeSpan.FromSeconds(5));
                // Authenticate before allocating or reading the caller's frame.
                if (!Trusted(pipe)) continue;
                var register = await BrowserWire.ReadAsync(pipe, handshake.Token);
                if (register?["type"]?.GetValue<string>() != "register" || register["origin"]?.GetValue<string>() != BrowserWire.Origin) continue;
                await BrowserWire.WriteAsync(pipe, new JsonObject { ["type"] = "registered", ["protocolVersion"] = 1 }, handshake.Token);
                _provider = pipe;
                _publishedState = null;
                _providerGeneration = Guid.NewGuid().ToString("n");
                using var connected = CancellationTokenSource.CreateLinkedTokenSource(cancellation);
                var reader = ReadProviderAsync(pipe, connected.Token);
                var monitor = MonitorAsync(connected.Token);
                await Task.WhenAny(reader, monitor);
                connected.Cancel(); pipe.Disconnect();
                try { await Task.WhenAll(reader, monitor); }
                catch (Exception ex) when (ex is IOException or OperationCanceledException or JsonException or InvalidOperationException) { }
            }
            catch (Exception ex) when (ex is IOException or OperationCanceledException or JsonException or InvalidOperationException) { }
            finally
            {
                if (pipe.IsConnected) pipe.Disconnect();
                _provider = null; _hello = null;
                _providerGeneration = Guid.NewGuid().ToString("n");
                foreach (var entry in _pending.Values) entry.TrySetCanceled();
                foreach (var entry in _sessions.Values) entry(new JsonObject { ["type"] = "session.closed" });
            }
        }
    }

    private static bool Trusted(NamedPipeServerStream pipe)
    {
        if (!GetNamedPipeClientProcessId(pipe.SafePipeHandle, out var pid)) return false;
        try
        {
            using var caller = Process.GetProcessById((int)pid);
            var own = Environment.ProcessPath;
            return caller.SessionId == RuntimeProfile.SessionId &&
                Path.GetFileName(own) == "machine-control-windows.exe" &&
                string.Equals(caller.MainModule?.FileName, own, StringComparison.OrdinalIgnoreCase);
        }
        catch (Exception ex) when (ex is ArgumentException or InvalidOperationException or System.ComponentModel.Win32Exception) { return false; }
    }
    [DllImport("kernel32.dll", SetLastError = true)]
    private static extern bool GetNamedPipeClientProcessId(SafePipeHandle pipe, out uint pid);

    private async Task ReadProviderAsync(Stream pipe, CancellationToken cancellation)
    {
        while (await BrowserWire.ReadAsync(pipe, cancellation) is { } frame)
        {
            if (frame["type"]?.GetValue<string>() == "hello")
            {
                if (frame["protocolVersion"]?.GetValue<int>() != 1) throw new InvalidDataException("Browser protocol mismatch");
                _hello = frame;
            }
            else if (frame["type"]?.GetValue<string>() == "response" &&
                frame["id"]?.GetValue<string>() is { } id && _pending.TryGetValue(id, out var completion))
                completion.TrySetResult(frame);
            else if (frame["type"]?.GetValue<string>() is { } type && type.StartsWith("session.", StringComparison.Ordinal) &&
                frame["id"]?.GetValue<string>() is { } session && _sessions.TryGetValue(session, out var receiver))
                receiver(frame);
        }
    }

    private async Task MonitorAsync(CancellationToken cancellation)
    {
        while (!cancellation.IsCancellationRequested)
        {
            await SendAsync(null, cancellation);
            await Task.Delay(100, cancellation);
        }
    }

    private async Task SendAsync(JsonObject? frame, CancellationToken cancellation, bool controlled = false,
        Request? authority = null, string? providerGeneration = null)
    {
        await _writes.WaitAsync(cancellation);
        try
        {
            var provider = _provider ?? throw new IOException("Browser disconnected");
            using var timeout = CancellationTokenSource.CreateLinkedTokenSource(cancellation);
            timeout.CancelAfter(TimeSpan.FromSeconds(3));
            var generation = grants.Generation;
            var browser = grants.Authorize("browser.tabs", controlled: true) is null;
            var devtools = grants.Authorize("browser.eval", controlled: true) is null;
            var state = generation + browser + devtools;
            if (state != _publishedState)
            {
                // Ordered with every request, not a delayed UI notification.
                await BrowserWire.WriteAsync(provider, new JsonObject { ["type"] = "grant", ["browser"] = false, ["devtools"] = false, ["grantGeneration"] = generation }, timeout.Token);
                await BrowserWire.WriteAsync(provider, new JsonObject { ["type"] = "grant", ["browser"] = browser, ["devtools"] = devtools, ["grantGeneration"] = generation }, timeout.Token);
                _publishedState = state;
            }
            if (frame is not null)
            {
                if (providerGeneration is not null && providerGeneration != _providerGeneration ||
                    authority is not null && grants.Authorize(authority, frame["grantGeneration"]?.GetValue<string>()) is not null)
                    throw new OperationCanceledException("Browser owner or provider changed before dispatch");
                var operation = frame["operation"]?.GetValue<string>();
                if (operation is not null && grants.Authorize(operation, frame["grantGeneration"]?.GetValue<string>(), controlled) is not null)
                    throw new OperationCanceledException("Browser authority changed before dispatch");
                frame.Remove("grantGeneration");
                await BrowserWire.WriteAsync(provider, frame, timeout.Token);
            }
        }
        finally { _writes.Release(); }
    }

    internal async Task<Result> ExecuteAsync(Request request, Result envelope, CancellationToken cancellation, bool controlled = false)
    {
        if (request.TimeoutMs is < 100 or > 45000)
            return envelope with { ErrorCode = "invalid_request", Message = "Browser timeout must be 100-45000 ms" };
        var generation = grants.Generation;
        var providerGeneration = _providerGeneration;
        var result = envelope with
        {
            ActualRoute = Route,
            Generation = generation,
            Fidelity = "chromium_tab_cdp",
            FocusConsequence = "browser_tab_may_activate",
            CursorConsequence = "unchanged_expected"
        };
        var refusal = grants.Authorize(request, request.ExpectedGeneration);
        if (refusal is not null) return result with { ErrorCode = refusal };
        if (!Connected) return result with { ErrorCode = "browser_provider_unavailable" };
        if (request.Operation == "browser.endpoint")
            return DevTools?.Endpoint(request, result) ?? result with { ErrorCode = "browser_stream_unavailable" };
        var parameters = JsonSerializer.SerializeToNode(request, Contract.Json)!.AsObject();
        foreach (var key in new[] { "operation", "requestId", "expectedGeneration", "scopes", "reason" }) parameters.Remove(key);
        if (request.Reference is { } reference)
        {
            var prefix = generation + ":" + providerGeneration + ":";
            if (!reference.StartsWith(prefix, StringComparison.Ordinal))
                return result with { ErrorCode = "stale_reference" };
            parameters["reference"] = reference[prefix.Length..];
        }
        if (request.Operation == "browser.upload")
        {
            if (string.IsNullOrWhiteSpace(request.Reference))
                return result with { ErrorCode = "invalid_request", Message = "A file input or upload button reference is required" };
            var upload = BrowserUpload.Validate(request.Files);
            if (upload.ErrorCode is not null) return result with { ErrorCode = upload.ErrorCode };
            parameters["files"] = JsonSerializer.SerializeToNode(upload.Files, Contract.Json);
        }
        var id = Guid.NewGuid().ToString("n");
        var completion = new TaskCompletionSource<JsonObject>(TaskCreationOptions.RunContinuationsAsynchronously);
        _pending[id] = completion;
        var dispatched = false;
        try
        {
            // Recheck after asynchronous scheduling and before dispatch.
            refusal = grants.Authorize(request, generation);
            if (refusal is not null) return result with { ErrorCode = refusal };
            await SendAsync(new JsonObject
            {
                ["type"] = "request",
                ["id"] = id,
                ["operation"] = request.Operation,
                ["grantGeneration"] = generation,
                ["params"] = parameters
            }, cancellation, controlled, request, providerGeneration);
            dispatched = true;
            var response = await completion.Task.WaitAsync(TimeSpan.FromMilliseconds(request.TimeoutMs ?? 45000), cancellation);
            refusal = grants.Authorize(request, generation);
            if (refusal is not null || providerGeneration != _providerGeneration)
                return Uncertain(result, refusal ?? "browser_provider_changed");
            if (response["ok"]?.GetValue<bool>() != true)
                return result with
                {
                    ErrorCode = response["errorCode"]?.GetValue<string>() ?? "browser_operation_failed",
                    Delivery = "unknown",
                    Effect = "unknown",
                    Uncertainty = "provider_refusal_may_follow_partial_delivery",
                    RetrySafety = "unsafe_delivery_unknown"
                };
            var data = response["data"]?.AsObject() ?? new JsonObject();
            if (request.Operation == "browser.snapshot" && data["elements"] is JsonArray elements)
                foreach (var element in elements.OfType<JsonObject>())
                    if (element["reference"]?.GetValue<string>() is { } token)
                        element["reference"] = generation + ":" + providerGeneration + ":" + token;
            if (request.Operation == "browser.capture")
            {
                var encoded = data["png"]?.GetValue<string>() ?? throw new InvalidDataException("PNG missing");
                var bytes = Convert.FromBase64String(encoded);
                if (bytes.Length < 8 || !bytes.AsSpan(0, 8).SequenceEqual(new byte[] { 137, 80, 78, 71, 13, 10, 26, 10 }))
                    throw new InvalidDataException("Invalid PNG");
                var artifact = Guid.NewGuid().ToString("n");
                Directory.CreateDirectory(RuntimeProfile.ArtifactRoot);
                await File.WriteAllBytesAsync(Path.Combine(RuntimeProfile.ArtifactRoot, artifact + ".png"), bytes, cancellation);
                data.Remove("png"); data["artifactId"] = artifact; data["bytes"] = bytes.Length;
                data["sha256"] = Convert.ToHexString(SHA256.HashData(bytes)).ToLowerInvariant();
            }
            var observes = BrowserWire.Observes(request.Operation) || request.Operation == "browser.release";
            return result with
            {
                Accepted = true,
                Delivery = "confirmed",
                Effect = observes ? "not_applicable" : "unverifiable",
                Uncertainty = observes ? "none" : "application_effect_not_independently_observed",
                RetrySafety = observes ? "safe_observation" : "unsafe_to_replay",
                Data = data
            };
        }
        catch (Exception ex) when (ex is IOException or OperationCanceledException or TimeoutException or FormatException or InvalidOperationException)
        {
            return dispatched ? Uncertain(result, "browser_completion_unavailable") : result with { ErrorCode = "browser_provider_unavailable" };
        }
        finally { _pending.TryRemove(id, out _); }
    }

    async Task IBrowserDevToolsProvider.OpenAsync(string id, int tabId, Request authority, string generation,
        string providerGeneration, Action<JsonObject> receive, CancellationToken cancellation)
    {
        if (!_sessions.TryAdd(id, receive)) throw new InvalidOperationException("Duplicate session");
        try
        {
            await SendAsync(new JsonObject
            {
                ["type"] = "session.open",
                ["id"] = id,
                ["tabId"] = tabId,
                ["operation"] = "browser.cdp",
                ["grantGeneration"] = generation
            }, cancellation, true, authority, providerGeneration);
        }
        catch { _sessions.TryRemove(id, out _); throw; }
    }

    Task IBrowserDevToolsProvider.CommandAsync(string id, JsonObject command, Request authority, string generation,
        string providerGeneration, CancellationToken cancellation) => SendAsync(new JsonObject
        {
            ["type"] = "session.command",
            ["id"] = id,
            ["cmdId"] = command["id"]!.DeepClone(),
            ["method"] = command["method"]!.DeepClone(),
            ["params"] = command["params"]?.DeepClone() ?? new JsonObject(),
            ["sessionId"] = command["sessionId"]?.DeepClone(),
            ["operation"] = "browser.cdp",
            ["grantGeneration"] = generation
        }, cancellation, true, authority, providerGeneration);

    async Task IBrowserDevToolsProvider.CloseAsync(string id, string providerGeneration)
    {
        _sessions.TryRemove(id, out _);
        if (!Connected || providerGeneration != _providerGeneration) return;
        try
        {
            using var timeout = new CancellationTokenSource(TimeSpan.FromSeconds(3));
            await SendAsync(new JsonObject { ["type"] = "session.close", ["id"] = id }, timeout.Token,
                providerGeneration: providerGeneration);
        }
        catch (Exception ex) when (ex is IOException or OperationCanceledException or InvalidOperationException) { }
    }

    private static Result Uncertain(Result result, string code) => result with
    {
        ErrorCode = code,
        Delivery = "unknown",
        Effect = "unknown",
        Uncertainty = "browser_completion_not_observed",
        RetrySafety = "unsafe_delivery_unknown"
    };
}
