namespace MachineControl.Windows;

internal sealed record GrantReply(bool Accepted, string? ErrorCode = null, object? Data = null);

/// Authority lives in the resident, not in the WebView or public pipe. All
/// transitions and dispatch acceptance share Gate; durations are monotonic.
internal sealed class DesktopGrants(TimeProvider? time = null, DesktopJournal? journal = null)
{
    internal DesktopJournal? Journal { get; } = journal;
    internal readonly object Gate = new();
    private readonly TimeProvider _time = time ?? TimeProvider.System;
    private string _generation = Guid.NewGuid().ToString("n");
    private LiveGrant? _grant;
    private PendingGrant? _pending;
    private bool _ready;
    private bool _preparedConsole;
    private bool _lockedConsole;
    private long _authorizationRevision;
    internal bool PreparedConsole { get { lock (Gate) return _preparedConsole; } }
    internal bool ConsoleReady { get { lock (Gate) return _ready; } }
    internal bool? TaskStartLocked { get { lock (Gate) return _ready ? false : _lockedConsole ? true : null; } }
    internal long AuthorizationRevision { get { lock (Gate) return _authorizationRevision; } }
    internal void PrepareConsole(bool enabled)
    {
        lock (Gate)
        {
            Stop("locked_use_preference_changed");
            _preparedConsole = enabled;
            Admission.SetReady("desktop", _ready || enabled && _lockedConsole);
        }
    }
    private bool _updating;
    private string? _lastEnded;
    private readonly Queue<object> _activity = new();
    private AccessAdmission? _admission;
    private DesktopActivityPolicy? _activityPolicy;
    internal DesktopActivityPolicy Activity => _activityPolicy ??= new(this, _time);
    internal void ActivityPause(string reason)
    {
        lock (Gate)
        {
            _generation = Guid.NewGuid().ToString("n");
            Admission.Pause("desktop", reason);
        }
    }
    internal AccessAdmission Admission
    {
        get
        {
            lock (Gate)
            {
                if (_admission is not null) return _admission;
                _admission = new AccessAdmission(_time, Gate);
                _admission.Register("desktop", _ready);
                _admission.SessionActivated += () => _generation = Guid.NewGuid().ToString("n");
                _admission.SessionEnded += (_, _, _) => _generation = Guid.NewGuid().ToString("n");
                return _admission;
            }
        }
    }

    internal static readonly string[] SupportedScopes = ["observe", "control", "browser", "devtools"];
    internal string Generation { get { lock (Gate) { Refresh(); return _generation; } } }

    internal static string? ScopeFor(string operation) => operation switch
    {
        "windows" or "snapshot" or "screenshot" => "observe",
        "app.launch" or "app.activate" or "invoke" or "set.value" or
        "click" or "move" or "drag" or "scroll" or "key" or "key.timeline" or "key.delayed_hold" or "type" or "window.state" or "uac.respond" or "session.unlock.prepare" => "control",
        "browser.tabs" or "browser.wait" or "browser.navigate" or "browser.snapshot" or
        "browser.click" or "browser.type" or "browser.key" or "browser.capture" or
        "browser.upload" or "browser.release" => "browser",
        "browser.cdp" or "browser.eval" or "browser.endpoint" => "devtools",
        _ => null,
    };

    internal void SetReady(bool ready, bool lockedConsole = false)
    {
        lock (Gate)
        {
            Refresh();
            if (_ready != ready)
            {
                _generation = Guid.NewGuid().ToString("n");
                if (!ready)
                {
                    _pending?.Completion.TrySetResult(new GrantReply(false, "desktop_unavailable"));
                    _pending = null;
                }
            }
            _ready = ready;
            _lockedConsole = lockedConsole;
            Admission.SetReady("desktop", ready || _preparedConsole && lockedConsole);
        }
    }

    internal string? Authorize(Request request, string? expectedGeneration = null)
    {
        lock (Gate)
        {
            var ownership = request.ControlOwnership;
            if (ownership is not null && Admission.Authorize(ownership.Owner, ownership.Intent,
                ownership.Session, ownership.Generations) is { } denied) return denied;
            // Only AdmissionChannel can attach ControlOwnership (it is ignored
            // by JSON deserialization). A grant alone never owns the desktop.
            return Authorize(request.Operation, expectedGeneration, ownership is not null)
                ?? (ownership is null ? "control_session_required" : null);
        }
    }

    internal static object RefusalData(string operation, string code) => new
    {
        requiredScope = ScopeFor(operation),
        requestOperation = code == "control_session_required" ? "control.open" : "grant.request",
        controlSession = code == "control_session_required"
            ? new { schema = AccessAdmission.Schema, scope = ScopeFor(operation) } : null,
    };

    internal string? Authorize(string operation, string? expectedGeneration = null, bool controlled = false)
    {
        lock (Gate)
        {
            Refresh();
            if (expectedGeneration is not null && expectedGeneration != _generation)
                return "stale_generation";
            if (Journal?.Available == false) return "audit_storage_unavailable";
            var scope = ScopeFor(operation);
            if (scope is null) return "unsupported_operation";
            if (!controlled && Admission.Reserved) return "control_session_required";
            if (!_ready && !(controlled && operation == "session.unlock.prepare" && _preparedConsole && _lockedConsole)) return "desktop_unavailable";
            if (_updating) return "update_in_progress";
            if (Admission.Blocks("desktop").Length > 0) return "access_paused";
            if (_pending is not null && (scope is "control" or "devtools" ||
                scope == "browser" && !BrowserWire.Observes(operation))) return "approval_prompt_visible";
            if (_grant is null || !(_grant.Scopes.Contains(scope) ||
                scope == "browser" && _grant.Scopes.Contains("devtools"))) return "approval_required";
            return null;
        }
    }

    internal string? AdmissionAuthority(string[] scopes)
    {
        lock (Gate)
        {
            if (Journal?.Available == false) return "audit_storage_unavailable";
            if (_grant?.Duration is int duration && Elapsed(_grant.Started) >= duration) return "expired";
            return _grant is not null && scopes.All(scope => _grant.Scopes.Contains(scope) ||
                scope == "browser" && _grant.Scopes.Contains("devtools")) ? null : "approval_required";
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
            if (Journal?.Event("access.requested") == false) return Task.FromResult(new GrantReply(false, "audit_storage_unavailable"));
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
                Journal?.Event("access.denied", false);
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

    internal void Arm(string[]? scopes, int duration, string lifetime = "timed")
    {
        lock (Gate)
        {
            Refresh();
            if (!_ready || _updating || _pending is not null)
                throw new InvalidOperationException("Finish approval and use an unlocked desktop before enabling access");
            int? seconds = lifetime switch
            {
                "timed" => ValidateDuration(duration),
                "until_stopped" => null,
                _ => throw new ArgumentException("Choose a supported access lifetime"),
            };
            Issue(ValidateScopes(scopes), seconds, "Manually enabled by the person", "local operator");
        }
    }

    internal void Pause(int? seconds = null)
    {
        lock (Gate)
        {
            if (seconds is < 1 or > 28800) throw new ArgumentException("Invalid pause duration");
            _generation = Guid.NewGuid().ToString("n");
            Admission.Pause("desktop", "manual", seconds);
            Journal?.Event("access.paused");
        }
    }

    internal void Resume()
    {
        lock (Gate)
        {
            Admission.Resume("desktop", "manual");
            Admission.Resume("desktop", "operator_deferral");
            Activity.ResumeFromOperator();
            Admission.Resume("desktop", "physical_takeover");
            Journal?.Event("access.resumed");
        }
    }

    private void Issue(HashSet<string> scopes, int? duration, string reason, string caller)
    {
        if (Journal?.Event("access.enabled") == false) throw new InvalidOperationException("Audit storage unavailable");
        _generation = Guid.NewGuid().ToString("n");
        _grant = new LiveGrant(scopes, duration, reason, caller, _time.GetTimestamp());
        ++_authorizationRevision;
        _lastEnded = null;
    }

    internal void Stop(string reason)
    {
        lock (Gate)
        {
            Journal?.Event("access." + DesktopJournal.Token(reason));
            _generation = Guid.NewGuid().ToString("n");
            _grant = null;
            ++_authorizationRevision;
            _lastEnded = reason;
            _pending?.Completion.TrySetResult(new GrantReply(false, reason));
            _pending = null;
            _admission?.Stop(reason);
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
            if (_grant?.Duration is int duration && Elapsed(_grant.Started) >= duration) Stop("expired");
            if (_pending is not null && Elapsed(_pending.Started) >= _pending.Timeout)
            {
                Journal?.Event("access.approval_timeout", false);
                _pending.Completion.TrySetResult(new GrantReply(false, "approval_timeout"));
                _pending = null;
            }
            _admission?.Refresh();
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
        lifetime = _grant.Duration is null ? "until_stopped" : "timed",
        remainingSeconds = System.Text.Json.JsonSerializer.SerializeToElement(_grant.Duration is int duration
            ? (int?)Math.Max(0, (int)Math.Ceiling(duration - Elapsed(_grant.Started))) : null),
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
                lastEnded = _lastEnded,
                availability = new { paused = Admission.Blocks("desktop").Length > 0, blockingReasons = Admission.Blocks("desktop") },
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
                manualUntilStoppedSupported = true,
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
                logging = Journal?.Health,
                admission = Admission.Status(),
                pauseSupported = true,
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

    private sealed record LiveGrant(HashSet<string> Scopes, int? Duration, string Reason, string Caller, long Started);
    private sealed record PendingGrant(string Id, HashSet<string> Scopes, int Duration, int Timeout,
        string Reason, string Caller, long Started, TaskCompletionSource<GrantReply> Completion);
}
