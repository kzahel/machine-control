using System.Text.Json;
using System.Text.Json.Nodes;
using System.IO;

namespace MachineControl.Windows;

/// Native channel/OS facts adapter. Queue, consent, countdown and ownership
/// decisions run in the shared resident process; this is not another arbiter.
internal sealed class AccessAdmission(object? gate = null)
{
    internal const string Schema = "machine-control-admission/v2";
    internal readonly object Gate = gate ?? new();
    private Func<JsonObject, JsonObject>? _invoke;
    private readonly Dictionary<string, (bool Ready, bool NoticeVisible)> _ready = new(StringComparer.Ordinal);
    private readonly Dictionary<(string, string), double?> _pauses = new();
    private readonly HashSet<string> _owners = [];
    // Intents this adapter submitted, so a platform failure can end them.
    private readonly Dictionary<string, string> _intentOwners = new(StringComparer.Ordinal);
    private bool _refreshing;
    private bool _inputReady;
    internal Action? RefreshAvailability { get; set; }
    internal event Action<string[]>? OwnershipChanged;
    private readonly Dictionary<string, (string Session, string[] Surfaces)> _sessions = new();
    internal void Invalidate()
    {
        lock (Gate)
        {
            _invoke = null; _owners.Clear(); _intentOwners.Clear();
            foreach (var item in _sessions.Values) OwnershipChanged?.Invoke(item.Surfaces);
            _sessions.Clear();
        }
    }

    internal void Bind(Func<JsonObject, JsonObject> invoke)
    {
        lock (Gate)
        {
            if (_invoke is not null) throw new InvalidOperationException("control_policy_already_bound");
            _invoke = invoke;
            Call("input-ready", new() { ["ready"] = _inputReady });
            foreach (var (surface, ready) in _ready) Call("ready", new() { ["surface"] = surface, ["ready"] = ready.Ready, ["noticeVisible"] = ready.NoticeVisible });
            foreach (var ((surface, reason), seconds) in _pauses) SendPause(surface, reason, seconds);
        }
    }
    internal void Register(string resource, bool ready = true, bool? noticeVisible = null) => SetReady(resource, ready, noticeVisible);
    internal void SetReady(string surface, bool ready, bool? noticeVisible = null)
    {
        lock (Gate)
        {
            var value = (ready, noticeVisible ?? ready);
            if (_ready.TryGetValue(surface, out var previous) && previous == value) return;
            _ready[surface] = value;
            if (_invoke is not null) Call("ready", new() { ["surface"] = surface, ["ready"] = ready, ["noticeVisible"] = value.Item2 });
        }
    }
    internal JsonObject Configure(string surface, string mode, int? durationSeconds, string[] profiles) =>
        Call("configure", new()
        {
            ["surface"] = surface,
            ["configuration"] = new JsonObject
            {
                ["mode"] = mode,
                ["durationMs"] = durationSeconds is int seconds ? seconds * 1000 : null,
                ["profileIds"] = JsonSerializer.SerializeToNode(profiles)
            }
        });
    internal void SetInputReady(bool ready)
    {
        lock (Gate)
        {
            if (_inputReady == ready) return;
            _inputReady = ready;
            if (_invoke is not null) Call("input-ready", new() { ["ready"] = ready });
        }
    }
    internal void Notice(int seconds) => Call("notice", new() { ["milliseconds"] = seconds * 1000 });
    internal void Input(string surface, string kind) { lock (Gate) { if (_invoke is not null) Call("input", new() { ["surface"] = surface, ["kind"] = kind }); } }
    internal void Pause(string surface, string reason, double? seconds = null)
    {
        if (seconds is <= 0 or > 28800 || seconds is { } value && !double.IsFinite(value)) throw new ArgumentException("Invalid pause");
        lock (Gate)
        {
            _pauses[(surface, reason)] = seconds;
            if (_invoke is not null) SendPause(surface, reason, seconds);
        }
    }
    private void SendPause(string surface, string reason, double? seconds) => Call("pause", new()
    { ["surface"] = surface, ["reason"] = reason, ["milliseconds"] = seconds is { } value ? (int)(value * 1000) : null });
    internal void Resume(string surface, string reason)
    {
        lock (Gate)
        {
            _pauses.Remove((surface, reason));
            if (_invoke is not null) Call("resume", new() { ["surface"] = surface, ["reason"] = reason });
        }
    }
    internal string[] Blocks(string surface)
    {
        lock (Gate)
        {
            Refresh();
            if (_invoke is null) return ["control_policy_unavailable"];
            var state = Query()["surfaces"]?[surface];
            var pauses = (state?["pauses"] as JsonArray)?.Select(value => value!["reason"]!.GetValue<string>()) ?? [];
            return pauses.Concat(state?["ready"]?.GetValue<bool>() == true ? [] : new[] { "resource_unavailable" }).Order().ToArray();
        }
    }
    internal JsonObject Surface(string surface) => (JsonObject)Query()["surfaces"]![surface]!.DeepClone();
    internal bool Enabled(string surface)
    {
        lock (Gate)
        {
            if (_invoke is null) return false;
            var state = Surface(surface);
            return state["mode"]?.GetValue<string>() != "off" && state["expired"]?.GetValue<bool>() != true;
        }
    }
    internal object Submit(string owner, string requestId, string[] surfaces, double waitSeconds,
        double durationSeconds, string reason,
        string[]? profileIds = null, string[]? operations = null)
    {
        lock (Gate)
        {
            Refresh();
            if (!_owners.Contains(owner)) { Call("open", new() { ["owner"] = owner }); _owners.Add(owner); }
            var submitted = Call("submit", new()
            {
                ["owner"] = owner,
                ["request"] = new JsonObject
                {
                    ["requestId"] = requestId,
                    ["surfaces"] = JsonSerializer.SerializeToNode(surfaces),
                    ["profileIds"] = JsonSerializer.SerializeToNode(profileIds ?? []),
                    ["operations"] = JsonSerializer.SerializeToNode(operations),
                    ["reason"] = reason,
                    ["waitMs"] = (int)(waitSeconds * 1000),
                    ["durationMs"] = (int)(durationSeconds * 1000)
                }
            });
            if (submitted["intentId"]?.GetValue<string>() is { } intent) _intentOwners[intent] = owner;
            return submitted;
        }
    }
    internal object Inspect(string owner, string id, bool heartbeat = false)
    {
        lock (Gate) { Refresh(); return Call("inspect", new() { ["owner"] = owner, ["intentId"] = id, ["heartbeat"] = heartbeat }); }
    }
    internal object Accept(string owner, string id, long offerGeneration)
    {
        lock (Gate)
        {
            Refresh();
            return Call("accept", new() { ["owner"] = owner, ["intentId"] = id, ["offerGeneration"] = offerGeneration });
        }
    }
    internal JsonObject Renew(string owner, string id, string sessionId, IReadOnlyDictionary<string, long> generations, int seconds)
    {
        lock (Gate)
        {
            Refresh();
            return Call("renew", new()
            {
                ["owner"] = owner,
                ["durationMs"] = seconds * 1000,
                ["fence"] = new JsonObject
                { ["intentId"] = id, ["sessionId"] = sessionId, ["resourceGenerations"] = JsonSerializer.SerializeToNode(generations) }
            });
        }
    }
    internal string? Authorize(string owner, string id, string sessionId, IReadOnlyDictionary<string, long> generations, string? operation = null)
    {
        lock (Gate)
        {
            Refresh();
            if (_invoke is null) return "control_policy_unavailable";
            if (!_owners.Contains(owner)) return "stale_control_session";
            try
            {
                return Call("authorize", new()
                {
                    ["owner"] = owner,
                    ["operation"] = operation,
                    ["fence"] = new JsonObject
                    { ["intentId"] = id, ["sessionId"] = sessionId, ["resourceGenerations"] = JsonSerializer.SerializeToNode(generations) }
                })["refusal"]?.GetValue<string>();
            }
            catch (Exception ex) when (PolicyLoss(ex)) { return "control_policy_unavailable"; }
        }
    }
    /// Ends an owned intent. A platform safety reason (for example
    /// `locked_use_guard_failed`) replaces the caller-looking `cancelled`.
    internal void Cancel(string owner, string id, string? reason = null)
    {
        var fields = new JsonObject { ["owner"] = owner, ["intentId"] = id };
        if (reason is not null) fields["reason"] = reason;
        Call("cancel", fields);
    }
    internal void Disconnect(string owner)
    {
        lock (Gate)
        {
            foreach (var (intent, holder) in _intentOwners.ToArray()) if (holder == owner) _intentOwners.Remove(intent);
            if (_owners.Remove(owner) && _invoke is not null) Call("close", new() { ["owner"] = owner });
        }
    }
    /// Ends every active or queued intent this adapter submitted with one
    /// platform safety reason. Returns how many the policy accepted.
    internal int EndAll(string reason)
    {
        lock (Gate)
        {
            if (_invoke is null || _intentOwners.Count == 0) return 0;
            var ended = 0;
            foreach (var (intent, owner) in _intentOwners.ToArray())
            {
                _intentOwners.Remove(intent);
                try { Cancel(owner, intent, reason); ended++; }
                catch (InvalidOperationException) { }
                catch (Exception ex) when (PolicyLoss(ex)) { break; }
            }
            return ended;
        }
    }
    internal void Stop(string reason) { lock (Gate) { if (_invoke is not null) Call("stop"); } }
    internal void CancelFromOperator(string id) => Call("deny", new() { ["intentId"] = id });
    internal void Approve(string id, int seconds = 0)
    {
        if (seconds is < 0 or > 28800) throw new ArgumentException("Choose a valid delay");
        Call("approve", new() { ["intentId"] = id, ["milliseconds"] = seconds * 1000 });
    }
    internal JsonObject Preferences(JsonObject value) => (JsonObject)Call("preferences", new() { ["preferences"] = value.DeepClone() })["preferences"]!.DeepClone();
    internal void Hold(string id) => Call("hold", new() { ["intentId"] = id });
    internal void Postpone(string id, int seconds)
    {
        if (seconds is < 1 or > 28800) throw new ArgumentException("Choose a valid delay");
        Call("postpone", new() { ["intentId"] = id, ["milliseconds"] = seconds * 1000 });
    }
    internal void Defer(string id, int? seconds) => Call("defer", new() { ["intentId"] = id, ["milliseconds"] = seconds is int value ? value * 1000 : null });
    internal void StartNow(string id)
    {
        lock (Gate) { Refresh(); Call("start", new() { ["intentId"] = id }); }
    }
    internal void Refresh()
    {
        lock (Gate)
        {
            if (_refreshing) return;
            _refreshing = true;
            try { RefreshAvailability?.Invoke(); }
            finally { _refreshing = false; }
        }
    }
    internal object Status()
    {
        lock (Gate)
        {
            if (_invoke is not null)
                try { return Call("state"); }
                catch (Exception ex) when (PolicyLoss(ex)) { }
            return Unavailable();
        }
    }
    private static JsonObject Unavailable() => (JsonObject)JsonSerializer.SerializeToNode(new
    {
        schema = Schema,
        available = false,
        errorCode = "control_policy_unavailable",
        noticeSeconds = 10,
        active = 0,
        waiting = 0,
        requests = Array.Empty<object>(),
        surfaces = new[] { "desktop", "browser" }.ToDictionary(surface => surface, _ => new
        { mode = "off", expired = false, consentRemainingSeconds = (int?)0, profileIds = Array.Empty<string>(), ready = false, pauses = Array.Empty<object>() })
    })!;
    private JsonObject Query()
    {
        lock (Gate)
        {
            if (_invoke is not null)
                try { return Call("query"); }
                catch (Exception ex) when (PolicyLoss(ex)) { }
            return Unavailable();
        }
    }
    internal bool HasActiveSession => Query()["active"]?.GetValue<int>() > 0;
    internal bool HasActiveDesktopSession => Query()["activeDesktop"]?.GetValue<bool>() == true;
    internal bool Reserved => (Query()["requests"] as JsonArray)?.Any(value => value?["state"]?.GetValue<string>() is "active" or "offered" or "announcing") == true;
    private static bool PolicyLoss(Exception error) => error is IOException or TimeoutException or OperationCanceledException;
    private JsonObject Call(string method, JsonObject? fields = null)
    {
        lock (Gate)
        {
            fields ??= new(); fields["method"] = "access." + method;
            JsonObject result;
            try { result = (_invoke ?? throw new InvalidOperationException("control_policy_unavailable"))(fields); }
            catch (Exception ex) when (PolicyLoss(ex)) { Invalidate(); throw; }
            void Observe(JsonNode? request)
            {
                var id = request?["intentId"]?.GetValue<string>();
                if (id is null) return;
                var session = request?["sessionId"]?.GetValue<string>();
                if (_sessions.TryGetValue(id, out var previous) && previous.Session != session)
                { _sessions.Remove(id); OwnershipChanged?.Invoke(previous.Surfaces); }
                if (session is not null && !_sessions.ContainsKey(id))
                {
                    var surfaces = request!["surfaces"]!.Deserialize<string[]>()!;
                    _sessions[id] = (session, surfaces); OwnershipChanged?.Invoke(surfaces);
                }
            }
            if (result["requests"] is JsonArray requests)
            {
                var ids = requests.Select(value => value!["intentId"]!.GetValue<string>()).ToHashSet();
                foreach (var (id, previous) in _sessions.ToArray())
                    if (!ids.Contains(id)) { _sessions.Remove(id); OwnershipChanged?.Invoke(previous.Surfaces); }
                foreach (var request in requests) Observe(request);
            }
            else if (result.ContainsKey("intentId")) Observe(result);
            return result;
        }
    }
}
