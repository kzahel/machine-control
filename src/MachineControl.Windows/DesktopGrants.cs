namespace MachineControl.Windows;

internal sealed record GrantReply(bool Accepted, string? ErrorCode = null, object? Data = null);

/// Authority lives in the resident, not in the WebView or public pipe. All
/// transitions and dispatch acceptance share Gate; durations are monotonic.
internal sealed class DesktopGrants(TimeProvider? time = null)
{
    internal readonly object Gate = new();
    private readonly TimeProvider _time = time ?? TimeProvider.System;
    private string _generation = Guid.NewGuid().ToString("n");
    private LiveGrant? _grant;
    private PendingGrant? _pending;
    private bool _ready;
    private bool _updating;
    private string? _lastEnded;
    private readonly Queue<object> _activity = new();

    internal static readonly string[] SupportedScopes = ["observe", "control", "browser", "devtools"];
    internal string Generation { get { lock (Gate) { Refresh(); return _generation; } } }

    internal static string? ScopeFor(string operation) => operation switch
    {
        "windows" or "snapshot" or "screenshot" => "observe",
        "app.launch" or "app.activate" or "invoke" or "set.value" or
        "click" or "key" or "type" or "window.state" => "control",
        "browser.tabs" or "browser.wait" or "browser.navigate" or "browser.snapshot" or
        "browser.click" or "browser.type" or "browser.key" or "browser.capture" or
        "browser.release" => "browser",
        "browser.cdp" or "browser.eval" => "devtools",
        _ => null,
    };

    internal void SetReady(bool ready)
    {
        lock (Gate)
        {
            Refresh();
            if (_ready && !ready) Stop("desktop_unavailable");
            _ready = ready;
        }
    }

    internal string? Authorize(string operation, string? expectedGeneration = null)
    {
        lock (Gate)
        {
            Refresh();
            if (expectedGeneration is not null && expectedGeneration != _generation)
                return "stale_generation";
            var scope = ScopeFor(operation);
            if (scope is null) return "unsupported_operation";
            if (!_ready) return "desktop_unavailable";
            if (_updating) return "update_in_progress";
            if (_pending is not null && (scope is "control" or "devtools" ||
                scope == "browser" && !BrowserWire.Observes(operation))) return "approval_prompt_visible";
            if (_grant is null || !(_grant.Scopes.Contains(scope) ||
                scope == "browser" && _grant.Scopes.Contains("devtools"))) return "approval_required";
            return null;
        }
    }

    internal Task<GrantReply> RequestAsync(Request request, string caller)
    {
        lock (Gate)
        {
            Refresh();
            if (!_ready || _updating)
                return Task.FromResult(new GrantReply(false, !_ready ? "desktop_unavailable" : "update_in_progress"));
            var scopes = ValidateScopes(request.Scopes);
            var duration = ValidateDuration(request.DurationSeconds ?? 900);
            var timeout = request.TimeoutSeconds ?? 120;
            if (timeout is < 5 or > 600 || string.IsNullOrWhiteSpace(request.Reason) || request.Reason.Length > 240)
                throw new ArgumentException("Choose a reason (1-240 characters) and timeout (5-600 seconds)");
            if (_pending is not null) return Task.FromResult(new GrantReply(false, "approval_pending"));
            if (_grant is not null && scopes.IsSubsetOf(_grant.Scopes))
                return Task.FromResult(new GrantReply(true, Data: DeploymentState()));
            var completion = new TaskCompletionSource<GrantReply>(TaskCreationOptions.RunContinuationsAsynchronously);
            _pending = new PendingGrant(Guid.NewGuid().ToString("n"), scopes, duration,
                timeout, request.Reason.Trim(), caller, _time.GetTimestamp(), completion);
            return completion.Task;
        }
    }

    internal void Decide(string id, bool allow, string[]? scopes, int duration)
    {
        lock (Gate)
        {
            Refresh();
            var pending = _pending ?? throw new InvalidOperationException("No pending approval");
            if (pending.Id != id) throw new InvalidOperationException("Approval request changed");
            if (!allow)
            {
                _pending = null;
                pending.Completion.TrySetResult(new GrantReply(false, "approval_denied"));
                return;
            }
            var selected = ValidateScopes(scopes);
            ValidateDuration(duration);
            if (!selected.IsSubsetOf(pending.Scopes) || duration > pending.Duration)
                throw new ArgumentException("Approval may only narrow scope and duration");
            if (!_ready || _updating) throw new InvalidOperationException("Desktop is unavailable");
            _pending = null;
            Issue(selected, duration, pending.Reason, pending.Caller);
            pending.Completion.TrySetResult(new GrantReply(true, Data: DeploymentState()));
        }
    }

    internal void Arm(string[]? scopes, int duration)
    {
        lock (Gate)
        {
            Refresh();
            if (!_ready || _updating || _pending is not null)
                throw new InvalidOperationException("Finish approval and use an unlocked desktop before enabling access");
            Issue(ValidateScopes(scopes), ValidateDuration(duration), "Manually enabled by the person", "local operator");
        }
    }

    private void Issue(HashSet<string> scopes, int duration, string reason, string caller)
    {
        _generation = Guid.NewGuid().ToString("n");
        _grant = new LiveGrant(scopes, duration, reason, caller, _time.GetTimestamp());
        _lastEnded = null;
    }

    internal void Stop(string reason)
    {
        lock (Gate)
        {
            _generation = Guid.NewGuid().ToString("n");
            _grant = null;
            _lastEnded = reason;
            _pending?.Completion.TrySetResult(new GrantReply(false, reason));
            _pending = null;
        }
    }

    internal void PrepareUpdate()
    {
        lock (Gate)
        {
            Refresh();
            if (_updating || _grant is not null || _pending is not null)
                throw new InvalidOperationException("Stop access and finish approval before updating");
            _updating = true;
            Stop("update_in_progress");
        }
    }

    internal void CancelUpdate() { lock (Gate) _updating = false; }

    internal void Refresh()
    {
        lock (Gate)
        {
            if (_grant is not null && Elapsed(_grant.Started) >= _grant.Duration) Stop("expired");
            if (_pending is not null && Elapsed(_pending.Started) >= _pending.Timeout)
            {
                _pending.Completion.TrySetResult(new GrantReply(false, "approval_timeout"));
                _pending = null;
            }
        }
    }

    internal void Record(Result result)
    {
        lock (Gate)
        {
            _activity.Enqueue(new
            {
                at = _time.GetUtcNow(),
                operation = result.Operation,
                accepted = result.Accepted,
                errorCode = result.ErrorCode
            });
            while (_activity.Count > 100) _activity.Dequeue();
        }
    }

    private double Elapsed(long stamp) => _time.GetElapsedTime(stamp).TotalSeconds;
    private object? GrantState() => _grant is null ? null : new
    {
        scopes = _grant.Scopes.Order().ToArray(),
        remainingSeconds = Math.Max(0, (int)Math.Ceiling(_grant.Duration - Elapsed(_grant.Started))),
        reason = _grant.Reason,
        requester = _grant.Caller,
        binding = "target_wide",
    };

    internal object DeploymentState()
    {
        lock (Gate)
        {
            Refresh();
            return new
            {
                policy = new { preset = "workstation", grantMode = "approval", operationSet = "ordinary" },
                grant = GrantState(),
                pendingRequest = _pending?.Id,
                lastEnded = _lastEnded
            };
        }
    }

    internal object State()
    {
        lock (Gate)
        {
            Refresh();
            return new
            {
                generation = _generation,
                deployment = DeploymentState(),
                pending = _pending is null ? null : new
                {
                    id = _pending.Id,
                    scopes = _pending.Scopes.Order().ToArray(),
                    duration = _pending.Duration,
                    reason = _pending.Reason,
                    caller = _pending.Caller,
                },
                activity = _activity.Reverse().Take(30).ToArray(),
                supportedScopes = SupportedScopes,
            };
        }
    }

    private static HashSet<string> ValidateScopes(string[]? scopes)
    {
        if (scopes is null || scopes.Length is < 1 or > 4 ||
            scopes.Any(scope => !SupportedScopes.Contains(scope, StringComparer.Ordinal)))
            throw new ArgumentException("Choose supported access scopes");
        return scopes.ToHashSet(StringComparer.Ordinal);
    }
    private static int ValidateDuration(int seconds) => seconds is >= 60 and <= 28800
        ? seconds : throw new ArgumentException("Duration must be 60-28800 seconds");

    private sealed record LiveGrant(HashSet<string> Scopes, int Duration, string Reason, string Caller, long Started);
    private sealed record PendingGrant(string Id, HashSet<string> Scopes, int Duration, int Timeout,
        string Reason, string Caller, long Started, TaskCompletionSource<GrantReply> Completion);
}
