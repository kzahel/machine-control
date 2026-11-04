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

/// Native peer/owner authentication and transport. Shared TypeScript owns browser policy.
internal sealed class BrowserRelay : IBrowserPolicy, IDisposable
{
    internal const string Route = BrowserWire.Route;
    private readonly DesktopGrants _grants;
    private readonly SharedBrowserHost _host;
    private readonly ConcurrentDictionary<string, Peer> _peers = new();
    private readonly ConcurrentDictionary<string, Authority> _authorities = new();
    private readonly ConcurrentDictionary<string, Authority> _audits = new();
    private readonly SemaphoreSlim _slots = new(16, 16);
    private readonly ConcurrentDictionary<long, Task> _connections = new();
    private long _nextConnection;
    private int _stopped = 1;
    private int _disposed;
    private (string Generation, bool Readable, bool Writable)? _nativeState;
    private sealed record Authority(Request Request, string Generation);
    private sealed record NativeCheckTiming(string Phase, double ElapsedMs, bool Accepted);
    private NativeCheckTiming _slowestNativeCheck = new("none", 0, false);
    private sealed class Peer(NamedPipeServerStream pipe)
    {
        internal readonly NamedPipeServerStream Pipe = pipe;
        internal readonly SemaphoreSlim Writes = new(1, 1);
        internal readonly string Tag = Guid.NewGuid().ToString("n");
        internal string? ConnectionId;
        internal string? ProfileId;
        internal volatile string? StreamEnd;
        internal volatile string? Problem;
    }

    internal BrowserRelay(DesktopGrants grants)
    {
        _grants = grants;
        _host = new SharedBrowserHost(SharedBrowserHost.Packaged(), Receive, NativeCheck, Failed);
        grants.BrowserPolicy = this;
        grants.Admission.Bind(frame => _host.Call(frame));
    }
    public bool Allows(string scope) => _stopped == 0 && _host.Alive &&
        (_host.State["effectiveScopes"] as JsonArray)?.Any(value => value?.GetValue<string>() == scope) == true;
    public object Profiles => _host.State["profiles"]?.DeepClone() ?? new JsonArray();
    internal bool PolicyAvailable => _host.Alive;
    internal object State => new
    {
        connected = (_host.State["profiles"] as JsonArray)?.Any(value => value?["connected"]?.GetValue<bool>() == true) == true,
        available = _host.Alive,
        route = Route,
        profileSelectionSupported = true,
        profiles = Profiles,
        problems = _peers.Values.Where(peer => peer.Problem is not null).Select(peer => new { reason = peer.Problem }).ToArray(),
        approvedProfiles = _host.State["selectedProfiles"]?.DeepClone() ?? new JsonArray(),
        slowestNativeCheck = Volatile.Read(ref _slowestNativeCheck),
        lastStreamEnds = _peers.Values.Where(peer => peer.StreamEnd is not null).Select(peer => new { profileId = peer.ProfileId, reason = peer.StreamEnd }).ToArray(),
        sharedRuntime = "typescript_node",
        runtimeProblem = _host.Failure,
        runtimeProblemMethod = _host.FailureMethod,
        knownOmissions = new[] { "incognito tabs", "browser chrome UI", "other user sessions", "OS file dialogs" },
        streamingCdp = new { available = _host.Alive, browserLevel = true, binding = "live_devtools_owner", transport = "target_loopback_websocket" },
        fileUpload = new { maximumFiles = BrowserUpload.MaximumFiles, paths = "target_local_drive", osDialog = false },
    };
    public void Configure(string[] scopes, int? durationSeconds, string[] profileIds)
    {
        if (!_host.Alive && !scopes.Any(DesktopGrants.BrowserScope)) return;
        SynchronizeSafety();
        _host.Call(new JsonObject
        {
            ["method"] = "operator.configure",
            ["scopes"] = JsonSerializer.SerializeToNode(scopes),
            ["profileIds"] = JsonSerializer.SerializeToNode(profileIds),
            ["durationMs"] = durationSeconds is int seconds ? seconds * 1000 : null
        });
        EndAudits();
        _authorities.Clear();
        Volatile.Write(ref _stopped, 0);
    }
    public void Stop()
    {
        Volatile.Write(ref _stopped, 1);
        if (_host.Alive) _host.Call(new JsonObject { ["method"] = "operator.stop" });
        EndAudits();
        _authorities.Clear();
    }
    public void Refresh() => SynchronizeSafety();
    internal void SynchronizeSafety()
    {
        if (!_host.Alive) return;
        lock (_grants.Gate)
        {
            var readable = _grants.AuthorizeNative("browser.tabs", controlled: true) is null;
            var writable = _grants.AuthorizeNative("browser.cdp", controlled: true) is null;
            var safety = (_grants.BrowserGeneration, readable, writable);
            if (_nativeState == safety) return;
            try
            {
                _host.Call(new JsonObject
                {
                    ["method"] = "native.state",
                    ["generation"] = safety.Item1,
                    ["readable"] = readable,
                    ["writable"] = writable
                });
                _nativeState = safety;
            }
            catch (Exception ex) when (!_host.Alive && (ex is IOException or TimeoutException or OperationCanceledException))
            {
                // The host has already revoked browser authority. A terminal
                // private transport failure must not end the native monitor.
            }
        }
    }

    internal async Task RunAsync(CancellationToken cancellation)
    {
        var name = RuntimeProfile.UserPipe(RuntimeProfile.Instance, RuntimeProfile.SessionId) + "-browser";
        NamedPipeServerStream? listener = UserHost.CreatePipe(name, first: true, maximumInstances: 17);
        try
        {
            while (!cancellation.IsCancellationRequested)
            {
                await listener.WaitForConnectionAsync(cancellation);
                var accepted = listener;
                listener = UserHost.CreatePipe(name, first: false, maximumInstances: 17);
                if (!Trusted(accepted) || !_slots.Wait(0)) { accepted.Dispose(); continue; }
                var id = Interlocked.Increment(ref _nextConnection);
                var task = ServeAsync(accepted, cancellation);
                _connections[id] = task;
                _ = task.ContinueWith(_ => { _connections.TryRemove(id, out var removed); }, TaskScheduler.Default);
            }
        }
        finally
        {
            listener?.Dispose();
            foreach (var peer in _peers.Values) peer.Pipe.Dispose();
            try { await Task.WhenAll(_connections.Values); } catch (OperationCanceledException) { }
        }
    }
    private async Task ServeAsync(NamedPipeServerStream pipe, CancellationToken cancellation)
    {
        var peer = new Peer(pipe);
        _peers[peer.Tag] = peer;
        try
        {
            using var handshake = CancellationTokenSource.CreateLinkedTokenSource(cancellation);
            handshake.CancelAfter(TimeSpan.FromSeconds(10));
            var registration = await BrowserWire.ReadAsync(pipe, handshake.Token, 4096);
            var origin = registration?["origin"]?.GetValue<string>();
            if (registration?["type"]?.GetValue<string>() != "register" || !BrowserWire.Allowed(origin)) return;
            await BrowserWire.WriteAsync(pipe, new JsonObject { ["type"] = "registered", ["protocolVersion"] = 1 }, handshake.Token);
            var hello = await BrowserWire.ReadAsync(pipe, handshake.Token, 4096);
            if (hello?["type"]?.GetValue<string>() != "hello") return;
            try
            {
                var reply = await _host.CallAsync(new JsonObject
                {
                    ["method"] = "browser.attach",
                    ["extensionId"] = new Uri(origin!).Host,
                    ["hello"] = hello,
                    ["transportTag"] = peer.Tag
                }, handshake.Token);
                peer.ConnectionId = reply["connectionId"]!.GetValue<string>();
                peer.ProfileId = reply["profileId"]!.GetValue<string>();
            }
            catch (InvalidOperationException ex)
            {
                peer.Problem = ex.Message;
                await BrowserWire.WriteAsync(pipe, new JsonObject { ["type"] = "profile.refused", ["protocolVersion"] = 1, ["reason"] = ex.Message }, handshake.Token);
                // Keep incompatible/colliding copies unarmed without a reconnect fight.
                while (await BrowserWire.ReadAsync(pipe, cancellation, 4096) is not null) { }
                return;
            }
            while (await BrowserWire.ReadAsync(pipe, cancellation) is { } frame)
            {
                if (BrowserWire.StreamEnd(frame) is { } ended) peer.StreamEnd = ended;
                await _host.CallAsync(new JsonObject { ["method"] = "provider.frame", ["connectionId"] = peer.ConnectionId, ["frame"] = frame }, cancellation);
            }
        }
        catch (Exception ex) when (ex is IOException or OperationCanceledException or InvalidOperationException or JsonException or ObjectDisposedException or TimeoutException) { }
        finally
        {
            _peers.TryRemove(peer.Tag, out _);
            peer.Pipe.Dispose();
            if (peer.ConnectionId is { } id && _host.Alive)
            {
                try
                {
                    _host.Call(new JsonObject { ["method"] = "provider.disconnect", ["connectionId"] = id });
                    _host.Call(new JsonObject { ["method"] = "provider.retire", ["connectionId"] = id });
                }
                catch (Exception ex) when (ex is IOException or InvalidOperationException or TimeoutException) { }
            }
            _slots.Release();
        }
    }
    private void Receive(JsonObject message)
    {
        if (message["type"]?.GetValue<string>() == "access.event")
        { _grants.Journal?.QueueAdmission(message); return; }
        var peer = message["transportTag"]?.GetValue<string>() is { } tag ? _peers.GetValueOrDefault(tag) :
            _peers.Values.FirstOrDefault(value => value.ConnectionId == message["connectionId"]?.GetValue<string>());
        if (peer is null) return;
        if (message["type"]?.GetValue<string>() == "provider.close") { peer.Pipe.Dispose(); return; }
        var frame = message["frame"]!.AsObject();
        peer.Writes.Wait();
        try
        {
            Task write;
            using var timeout = new CancellationTokenSource(TimeSpan.FromSeconds(3));
            lock (_grants.Gate)
            {
                if (frame["type"]?.GetValue<string>() == "grant" && (frame["browser"]?.GetValue<bool>() == true || frame["devtools"]?.GetValue<bool>() == true))
                {
                    if (_stopped != 0 || !frame["grantGeneration"]!.GetValue<string>().StartsWith("shared:" + _host.State["authorizationGeneration"] + ":", StringComparison.Ordinal)) return;
                }
                if (message["authorityId"]?.GetValue<string>() is { } authority &&
                    (!_authorities.TryGetValue(authority, out var context) || _grants.AuthorizeNative(context.Request, context.Generation) is not null))
                { peer.Pipe.Dispose(); return; }
                write = BrowserWire.WriteAsync(peer.Pipe, frame, timeout.Token);
            }
            write.GetAwaiter().GetResult();
        }
        catch (Exception ex) when (ex is IOException or OperationCanceledException or ObjectDisposedException) { peer.Pipe.Dispose(); }
        finally { peer.Writes.Release(); }
    }
    private bool NativeCheck(JsonObject frame)
    {
        var started = Stopwatch.GetTimestamp();
        var accepted = false;
        try { return accepted = NativeCheckCore(frame); }
        finally
        {
            var phase = frame["phase"]?.GetValue<string>();
            var observed = new NativeCheckTiming(phase is "check" or "begin" or "result" ? phase : "unknown",
                Stopwatch.GetElapsedTime(started).TotalMilliseconds, accepted);
            while (true)
            {
                var previous = Volatile.Read(ref _slowestNativeCheck);
                if (previous.ElapsedMs >= observed.ElapsedMs ||
                    ReferenceEquals(Interlocked.CompareExchange(ref _slowestNativeCheck, observed, previous), previous)) break;
            }
        }
    }
    private bool NativeCheckCore(JsonObject frame)
    {
        var authorityId = frame["authorityId"]?.GetValue<string>() ?? "";
        if (!_authorities.TryGetValue(authorityId, out var authority)) return false;
        lock (_grants.Gate)
        {
            var allowed = _stopped == 0 && _grants.AuthorizeNative(authority.Request, authority.Generation) is null &&
                _grants.AuthorizeNative("browser.cdp", authority.Generation, controlled: true) is null;
            var phase = frame["phase"]?.GetValue<string>();
            var auditId = frame["auditId"]?.GetValue<string>() ?? "";
            if (phase == "check") return allowed;
            if (phase == "begin")
            {
                if (!allowed || _audits.Count >= 256 || !_audits.TryAdd(auditId, authority)) return false;
                if (_grants.Journal?.Begin("browser.cdp", auditId, authority.Generation) != false) return true;
                _audits.TryRemove(auditId, out _); return false;
            }
            if (phase != "result" || !_audits.TryRemove(auditId, out var intent) || intent != authority) return false;
            var confirmed = allowed && frame["delivery"]?.GetValue<string>() == "confirmed";
            return _grants.Journal?.Record(CdpResult(auditId, authority.Generation, confirmed)) != false && allowed;
        }
    }
    private static Result CdpResult(string id, string generation, bool confirmed) => new()
    {
        RequestId = id,
        Operation = "browser.cdp",
        Generation = generation,
        ActualRoute = Route,
        Accepted = true,
        Delivery = confirmed ? "confirmed" : "unknown",
        Effect = "unverifiable",
        Uncertainty = confirmed ? "application_effect_not_independently_observed" : "browser_completion_not_observed",
        RetrySafety = confirmed ? "unsafe_to_replay" : "unsafe_delivery_unknown"
    };
    private string AuthorityFor(Request request, bool retained)
    {
        foreach (var item in _authorities)
        {
            if (_grants.AuthorizeNative(item.Value.Request, item.Value.Generation) is not null) _authorities.TryRemove(item.Key, out _);
            else if (retained && item.Value.Request.Operation == "browser.endpoint" && item.Value.Generation == _grants.BrowserGeneration &&
                item.Value.Request.ControlOwnership?.Owner == request.ControlOwnership?.Owner &&
                item.Value.Request.ControlOwnership?.Intent == request.ControlOwnership?.Intent &&
                item.Value.Request.ControlOwnership?.Session == request.ControlOwnership?.Session) return item.Key;
        }
        if (_authorities.Count >= 128) throw new InvalidOperationException("browser_stream_capacity");
        var id = Guid.NewGuid().ToString("n");
        _authorities[id] = new Authority(request, _grants.BrowserGeneration); return id;
    }
    internal async Task<Result> ExecuteAsync(Request request, Result result, CancellationToken cancellation, bool controlled = false)
    {
        result = result with { ActualRoute = Route, Fidelity = "chromium_tab_cdp", FocusConsequence = "browser_tab_may_activate", CursorConsequence = "unchanged_expected" };
        if (request.TimeoutMs is < 100 or > 45000) return result with { ErrorCode = "invalid_request" };
        string? authorityId = null;
        var id = Guid.NewGuid().ToString("n");
        try
        {
            SynchronizeSafety();
            if (request.Operation != "browser.profiles" && _grants.Authorize(request, request.ExpectedGeneration) is { } denied) return result with { ErrorCode = denied };
            if (request.Operation == "browser.upload")
            {
                var upload = BrowserUpload.Validate(request.Files);
                if (upload.ErrorCode is not null) return result with { ErrorCode = upload.ErrorCode };
                request = request with { Files = upload.Files };
            }
            authorityId = request.Operation == "browser.profiles" ? "metadata" : AuthorityFor(request, request.Operation == "browser.endpoint");
            var generation = _grants.BrowserGeneration;
            var reply = await _host.CallAsync(new JsonObject
            {
                ["method"] = "browser.call",
                ["requestId"] = id,
                ["authorityId"] = authorityId,
                ["ownerSession"] = request.ControlOwnership is { } owner ? owner.Owner + ":" + owner.Session : null,
                ["ownerProfileIds"] = JsonSerializer.SerializeToNode(request.ControlOwnership?.Generations.Keys
                    .Where(resource => resource.StartsWith("browser:", StringComparison.Ordinal)).Select(resource => resource[8..]).ToArray() ?? []),
                ["request"] = JsonSerializer.SerializeToNode(request, Contract.Json)
            }, cancellation, 50000);
            var data = reply["data"]?.DeepClone();
            if (request.Operation == "browser.capture" && reply["accepted"]?.GetValue<bool>() == true)
            {
                var body = data!.AsObject();
                var bytes = Convert.FromBase64String(body["png"]!.GetValue<string>());
                if (bytes.Length < 8 || !bytes.AsSpan(0, 8).SequenceEqual(new byte[] { 137, 80, 78, 71, 13, 10, 26, 10 })) throw new InvalidDataException("Invalid PNG");
                Directory.CreateDirectory(RuntimeProfile.ArtifactRoot);
                var artifact = Guid.NewGuid().ToString("n");
                await File.WriteAllBytesAsync(Path.Combine(RuntimeProfile.ArtifactRoot, artifact + ".png"), bytes, cancellation);
                body.Remove("png"); body["artifactId"] = artifact; body["bytes"] = bytes.Length;
                body["sha256"] = Convert.ToHexString(SHA256.HashData(bytes)).ToLowerInvariant();
            }
            if (data is JsonObject identified && reply["profileId"] is { } profile)
            {
                identified["browserProfileId"] = profile.DeepClone();
                identified["providerGeneration"] = reply["providerGeneration"]?.DeepClone();
            }
            var accepted = reply["accepted"]?.GetValue<bool>() == true;
            var observes = BrowserWire.Observes(request.Operation) || request.Operation is "browser.endpoint" or "browser.profiles" or "browser.release";
            return result with
            {
                Generation = generation,
                Accepted = accepted,
                Data = data,
                ErrorCode = reply["errorCode"]?.GetValue<string>(),
                Message = reply["message"]?.GetValue<string>(),
                Delivery = reply["delivery"]?.GetValue<string>() ?? "refused",
                Effect = accepted && observes ? "not_applicable" : reply["effect"]?.GetValue<string>() ?? "refused",
                Uncertainty = accepted && observes ? "none" : reply["uncertainty"]?.GetValue<string>() ?? "none",
                RetrySafety = accepted && observes ? "safe_observation" : reply["retrySafety"]?.GetValue<string>() ?? "safe_not_dispatched"
            };
        }
        catch (InvalidOperationException ex) { return result with { ErrorCode = System.Text.RegularExpressions.Regex.IsMatch(ex.Message, "^[a-z][a-z0-9_]{0,95}$") ? ex.Message : "browser_invalid_response" }; }
        catch (Exception ex) when (ex is IOException or OperationCanceledException or TimeoutException or FormatException)
        { return result with { ErrorCode = "browser_completion_unavailable", Delivery = "unknown", Effect = "unknown", Uncertainty = "browser_completion_not_observed", RetrySafety = "unsafe_delivery_unknown" }; }
        finally
        {
            if (authorityId is not null && request.Operation != "browser.endpoint") _authorities.TryRemove(authorityId, out _);
            if (cancellation.IsCancellationRequested && _host.Alive)
                try { _host.Call(new JsonObject { ["method"] = "browser.cancel", ["requestId"] = id }); } catch (Exception ex) when (ex is IOException or InvalidOperationException or TimeoutException) { }
        }
    }
    private void Failed()
    {
        // Persist closed diagnostic codes before a fatal transport race can
        // end the supervisor. Never retain provider/page payloads or stderr.
        _grants.Journal?.Diagnostic("browser.runtime." + (_host?.FailureMethod ?? "startup"),
            _host?.Failure ?? "startup_failed");
        Volatile.Write(ref _stopped, 1);
        foreach (var peer in _peers.Values) peer.Pipe.Dispose();
        EndAudits();
        _authorities.Clear();
        if (_disposed == 0) _ = Task.Run(() => { _grants.Admission.Invalidate(); _grants.Stop("resident_policy_disconnected"); });
    }
    private void EndAudits()
    {
        foreach (var audit in _audits) if (_audits.TryRemove(audit.Key, out var authority)) _grants.Journal?.Record(CdpResult(audit.Key, authority.Generation, false));
    }
    private static bool Trusted(NamedPipeServerStream pipe)
    {
        if (!GetNamedPipeClientProcessId(pipe.SafePipeHandle, out var pid)) return false;
        if (!ProcessIdToSessionId(pid, out var session) || session != RuntimeProfile.SessionId ||
            Path.GetFileName(Environment.ProcessPath) != "machine-control-windows.exe") return false;
        using var process = new SafeProcessHandle(NativeMethods.OpenProcess(0x1000, false, pid), ownsHandle: true);
        if (process.IsInvalid) return false;
        var path = new System.Text.StringBuilder(32768);
        var length = (uint)path.Capacity;
        return QueryFullProcessImageName(process, 0, path, ref length) &&
            string.Equals(path.ToString(), Environment.ProcessPath, StringComparison.OrdinalIgnoreCase);
    }
    [DllImport("kernel32.dll", SetLastError = true)]
    private static extern bool ProcessIdToSessionId(uint processId, out uint sessionId);
    [DllImport("kernel32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
    private static extern bool QueryFullProcessImageName(SafeProcessHandle process, uint flags, System.Text.StringBuilder path, ref uint size);
    [DllImport("kernel32.dll", SetLastError = true)]
    private static extern bool GetNamedPipeClientProcessId(SafePipeHandle pipe, out uint pid);
    public void Dispose() { Interlocked.Exchange(ref _disposed, 1); _host.Dispose(); EndAudits(); foreach (var peer in _peers.Values) peer.Pipe.Dispose(); }
}
