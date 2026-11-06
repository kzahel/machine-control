using System.IO;
using System.Text.Json;
using System.Text.Json.Nodes;

namespace MachineControl.Windows;

internal sealed record GrantReply(bool Accepted, string? ErrorCode = null, object? Data = null);

/// Native safety ceilings and effects. Surface consent, task approval and
/// admission belong to the shared policy, never to the WebView or public pipe.
internal sealed class DesktopGrants(TimeProvider? time = null, DesktopJournal? journal = null)
{
    internal IBrowserPolicy? BrowserPolicy { get; set; }
    internal DesktopJournal? Journal { get; } = journal;
    internal readonly object Gate = new();
    internal volatile bool ApprovalPresentationAvailable = true;
    private readonly TimeProvider _time = time ?? TimeProvider.System;
    private string _generation = Guid.NewGuid().ToString("n");
    private string _browserGeneration = Guid.NewGuid().ToString("n");
    private bool _ready, _preparedConsole, _lockedConsole, _browserWhileLocked, _updating;
    private string? _consoleIdentity, _browserConsentConsole, _lastEnded;
    private long _desktopConsentRevision;
    private long _stops;
    /// Stops counted before any policy call, read live by status replies. Stops
    /// the supervisor itself causes (exit, policy loss) are not counted: they
    /// must not cancel the access restore that follows a resident restart.
    internal long Stops => Interlocked.Read(ref _stops);
    private AccessAdmission? _admission;
    private DesktopActivityPolicy? _activityPolicy;
    private readonly Queue<object> _activity = new();
    internal static readonly string[] SupportedScopes = ["observe", "control", "browser", "devtools"];
    internal static bool BrowserScope(string scope) => scope is "browser" or "devtools";
    internal static string SurfaceFor(string scope) => BrowserScope(scope) ? "browser" : "desktop";
    internal static string? ScopeFor(string operation) => operation switch
    {
        "windows" or "snapshot" or "screenshot" => "observe",
        "app.launch" or "app.activate" or "invoke" or "set.value" or "click" or "move" or "drag" or "scroll" or
        "key" or "key.timeline" or "key.delayed_hold" or "type" or "window.state" or "uac.respond" or "session.unlock.prepare" or "session.unlock" => "control",
        "browser.tabs" or "browser.wait" or "browser.navigate" or "browser.snapshot" or "browser.click" or "browser.type" or
        "browser.key" or "browser.capture" or "browser.upload" or "browser.release" or "browser.dialog" => "browser",
        "browser.cdp" or "browser.eval" or "browser.endpoint" => "devtools",
        _ => null
    };
    internal string Generation { get { lock (Gate) return _generation; } }
    internal string BrowserGeneration { get { lock (Gate) return _browserGeneration; } }
    internal string GenerationFor(string operation) => BrowserScope(ScopeFor(operation) ?? "") ? BrowserGeneration : Generation;
    internal bool PreparedConsole { get { lock (Gate) return _preparedConsole; } }
    internal bool ConsoleReady { get { lock (Gate) return _ready; } }
    internal bool? TaskStartLocked { get { lock (Gate) return _ready ? false : _lockedConsole ? true : null; } }
    internal long DesktopConsentRevision { get { lock (Gate) return _desktopConsentRevision; } }
    internal DesktopActivityPolicy Activity => _activityPolicy ??= new(this, _time);
    internal AccessAdmission Admission
    {
        get
        {
            lock (Gate)
            {
                if (_admission is not null) return _admission;
                _admission = new AccessAdmission(gate: Gate);
                _admission.Register("desktop", _ready || _preparedConsole && _lockedConsole, _ready);
                _admission.Register("browser", _ready);
                _admission.OwnershipChanged += surfaces => { if (surfaces.Contains("desktop")) _generation = Guid.NewGuid().ToString("n"); };
                return _admission;
            }
        }
    }
    internal bool BrowserOnlyWhileLocked
    {
        get
        {
            lock (Gate) return !_ready && _lockedConsole && _browserWhileLocked && _consoleIdentity is not null &&
            _browserConsentConsole == _consoleIdentity && Admission.Enabled("browser");
        }
    }
    internal bool ReadyForScopes(string[] scopes) => ConsoleReady || BrowserOnlyWhileLocked && scopes.All(BrowserScope);
    internal bool CanEnableBrowserWhileLocked { get { lock (Gate) return _ready && _consoleIdentity is not null; } }
    internal object BrowserWhileLockedState() => new
    {
        supported = true,
        enabled = _browserWhileLocked,
        active = BrowserOnlyWhileLocked,
        requiresUnlockedApproval = true,
        route = "chrome.extension/cdp"
    };
    internal void ConfigureBrowserWhileLocked(bool enabled, bool loading = false)
    {
        lock (Gate)
        {
            if (!loading && enabled && (!_ready || _consoleIdentity is null)) throw new InvalidOperationException("Enable browser access on the current unlocked console");
            _browserWhileLocked = enabled;
            PublishReady();
        }
    }
    internal void PrepareConsole(bool enabled)
    {
        lock (Gate) { Stop("locked_use_preference_changed"); _preparedConsole = enabled; PublishReady(); }
    }
    private void PublishReady()
    {
        var healthy = Journal?.Available != false && !_updating;
        Admission.SetReady("desktop", healthy && (_ready || _preparedConsole && _lockedConsole), healthy && _ready);
        Admission.SetReady("browser", healthy && (_ready || BrowserOnlyWhileLocked), healthy && _ready);
    }
    internal void SetReady(bool ready, bool lockedConsole = false, string? consoleIdentity = null)
    {
        lock (Gate)
        {
            if (_ready != ready || _consoleIdentity != consoleIdentity)
            { _generation = Guid.NewGuid().ToString("n"); _browserGeneration = Guid.NewGuid().ToString("n"); }
            _ready = ready; _lockedConsole = lockedConsole; _consoleIdentity = consoleIdentity;
            // Input-desktop readiness can change before the WTS lock flag.
            // Keep same-logon consent while unavailable; PublishReady denies
            // effects until a positively observed route is ready again.
            if (_browserConsentConsole is not null && consoleIdentity != _browserConsentConsole) Stop("console_session_changed");
            PublishReady();
        }
    }
    internal void ActivityPause(string reason)
    {
        lock (Gate) { Admission.Pause("desktop", reason); }
    }
    internal void ConfigureSurface(string surface, string mode, int duration, string lifetime, string[]? browserProfileIds = null)
    {
        lock (Gate)
        {
            if (surface is not ("desktop" or "browser") || mode is not ("off" or "ask" or "automatic")) throw new ArgumentException("Choose a surface and access mode");
            if (mode != "off" && (!_ready || _updating || !ApprovalPresentationAvailable)) throw new InvalidOperationException("Use an unlocked desktop with native notifications before enabling access");
            if (Journal?.Available == false && mode != "off") throw new InvalidOperationException("Audit storage unavailable");
            int? seconds = lifetime switch { "until_stopped" => null, "timed" => ValidateDuration(duration), _ => throw new ArgumentException("Choose an access lifetime") };
            if (surface == "browser")
            {
                if (BrowserPolicy is null && mode != "off") throw new InvalidOperationException("Browser runtime unavailable");
                // Browser is one complete surface. Old scope names are only a
                // native provider capability mapping, not separate consent.
                BrowserPolicy?.Configure(mode == "off" ? [] : ["browser", "devtools"], seconds, browserProfileIds ?? []);
                _browserConsentConsole = mode == "off" ? null : _consoleIdentity;
                _browserGeneration = Guid.NewGuid().ToString("n");
            }
            else _generation = Guid.NewGuid().ToString("n");
            Admission.Configure(surface, mode, seconds, surface == "browser" ? browserProfileIds ?? [] : []);
            if (surface == "desktop") ++_desktopConsentRevision;
            _lastEnded = null;
            Journal?.QueueEvent(mode == "off" ? "access.disabled" : "access.enabled");
            PublishReady();
        }
    }
    internal string? AuthorizeNative(Request request, string? expectedGeneration = null) => Authorize(request, expectedGeneration, nativeOnly: true);
    internal string? Authorize(Request request, string? expectedGeneration = null, bool nativeOnly = false)
    {
        lock (Gate)
        {
            var scope = ScopeFor(request.Operation);
            if (scope is null) return "unsupported_operation";
            var surface = SurfaceFor(scope);
            if (!Admission.Enabled(surface)) return "surface_disabled";
            // A paused/busy caller still negotiates one live waiting intent.
            if (request.ControlOwnership is not { } owner) return "control_session_required";
            if (Admission.Authorize(owner.Owner, owner.Intent, owner.Session, owner.Generations, request.Operation) is { } denied) return denied;
            return Authorize(request.Operation, expectedGeneration, controlled: true, nativeOnly: nativeOnly);
        }
    }
    internal string? AuthorizeNative(string operation, string? expectedGeneration = null, bool controlled = false) => Authorize(operation, expectedGeneration, controlled, nativeOnly: true);
    internal string? Authorize(string operation, string? expectedGeneration = null, bool controlled = false, bool nativeOnly = false)
    {
        lock (Gate)
        {
            Refresh();
            var scope = ScopeFor(operation);
            if (scope is null) return "unsupported_operation";
            if (expectedGeneration is not null && expectedGeneration != GenerationFor(operation)) return "stale_generation";
            if (Journal?.Available == false) return "audit_storage_unavailable";
            if (_updating) return "update_in_progress";
            var surface = SurfaceFor(scope);
            if (!Admission.Enabled(surface)) return "surface_disabled";
            if (!_ready && !(BrowserOnlyWhileLocked && BrowserScope(scope)) &&
                !(controlled && operation is ("session.unlock.prepare" or "session.unlock") && _preparedConsole && _lockedConsole))
                return BrowserOnlyWhileLocked ? "desktop_locked_browser_only" : "desktop_unavailable";
            if (Admission.Blocks(surface).Length > 0) return "access_paused";
            if (BrowserScope(scope) && !nativeOnly && BrowserPolicy?.Allows(scope) != true) return "browser_runtime_unavailable";
            return null;
        }
    }
    internal static object RefusalData(string operation, string code) => new
    {
        requiredSurface = SurfaceFor(ScopeFor(operation) ?? ""),
        requestOperation = code == "control_session_required" ? "control.open" : null,
        controlSession = code == "control_session_required" ? new
        {
            schema = AccessAdmission.Schema,
            surface = SurfaceFor(ScopeFor(operation) ?? ""),
            profileSelection = "exact"
        } : null
    };
    internal Task<GrantReply> RequestAsync(Request request, string caller) => Task.FromResult(new GrantReply(false,
        request.Scopes?.Any(scope => Admission.Enabled(SurfaceFor(scope))) == true ? "legacy_grant_request_unsupported" : "surface_disabled"));
    internal void Pause(int? seconds = null) { lock (Gate) { Admission.Pause("all", "manual", seconds); Journal?.QueueEvent("access.paused"); } }
    internal void Resume()
    {
        lock (Gate)
        {
            Admission.Resume("all", "manual"); Admission.Resume("all", "operator_deferral");
            Activity.ResumeFromOperator(); Admission.Resume("all", "physical_takeover"); Journal?.QueueEvent("access.resumed");
        }
    }
    internal void PauseRequest(string id, int? seconds)
    {
        lock (Gate) Admission.Defer(id, seconds);
    }
    internal void ResumeSurface(string surface)
    {
        if (surface is not ("desktop" or "browser")) throw new ArgumentException("Choose a surface");
        lock (Gate)
        {
            Admission.Resume(surface, "manual"); Admission.Resume(surface, "operator_deferral");
            if (surface == "desktop") Activity.ResumeFromOperator();
            Admission.Resume(surface, "physical_takeover");
        }
    }
    internal void Stop(string reason)
    {
        if (reason is not ("resident_policy_disconnected" or "operator_disconnected" or "operator_quit"))
            Interlocked.Increment(ref _stops);
        lock (Gate)
        {
            _generation = Guid.NewGuid().ToString("n"); _browserGeneration = Guid.NewGuid().ToString("n");
            ++_desktopConsentRevision; _lastEnded = reason; _browserConsentConsole = null;
            _admission?.Stop(reason); BrowserPolicy?.Stop(); Journal?.QueueEvent("access." + DesktopJournal.Token(reason));
        }
    }
    /// Ends one owned task for a platform safety reason without touching
    /// surface consent. Dispatch is fenced: the desktop generation changes so
    /// earlier references and admitted generations are stale.
    internal bool EndTask(ControlOwnership owner, string reason)
    {
        lock (Gate)
        {
            _generation = Guid.NewGuid().ToString("n");
            Journal?.QueueEvent("task." + DesktopJournal.Token(reason));
            try { Admission.Cancel(owner.Owner, owner.Intent, reason); return true; }
            catch (Exception ex) when (ex is InvalidOperationException or IOException or TimeoutException or OperationCanceledException or ArgumentException)
            {
                // The owner already closed or the policy is gone; either way
                // the intent no longer authorizes anything.
                return false;
            }
        }
    }
    internal (bool Revoked, bool Retained) RevokeFromCaller() => (false, Admission.Enabled("desktop") || Admission.Enabled("browser"));
    internal void PrepareUpdate()
    {
        lock (Gate)
        {
            if (_updating || Admission.Enabled("desktop") || Admission.Enabled("browser")) throw new InvalidOperationException("Stop access before updating");
            _updating = true; Stop("update_in_progress");
        }
    }
    internal void CancelUpdate() { lock (Gate) _updating = false; }
    internal void Refresh() { lock (Gate) { PublishReady(); _admission?.Refresh(); } }
    internal void Record(Result result)
    {
        lock (Gate)
        {
            _activity.Enqueue(new { at = _time.GetUtcNow(), operation = result.Operation, accepted = result.Accepted, errorCode = result.ErrorCode });
            while (_activity.Count > 100) _activity.Dequeue();
        }
    }
    private string[] EffectiveScopes() => SupportedScopes.Where(scope => Admission.Enabled(SurfaceFor(scope))).ToArray();
    internal object DeploymentState()
    {
        lock (Gate) return new
        {
            policy = new { preset = "workstation", grantMode = "surface_modes", operationSet = "ordinary" },
            grant = (object?)null,
            pendingRequest = (string?)null,
            lastEnded = _lastEnded,
            browserOnlyWhileLocked = BrowserOnlyWhileLocked,
            effectiveScopes = EffectiveScopes(),
            availability = new { paused = Admission.Blocks("desktop").Length > 0, blockingReasons = Admission.Blocks("desktop") }
        };
    }
    internal object State()
    {
        lock (Gate)
        {
            Refresh();
            var admission = (JsonObject)Admission.Status();
            var requests = admission["requests"]!.AsArray();
            admission["requestsTruncated"] = requests.Count > 16;
            admission["requests"] = new JsonArray(requests.OrderBy(request => request?["state"]?.GetValue<string>() switch
            { "announcing" => 0, "waiting_for_approval" => 1, "active" => 2, _ => 3 }).Take(16).Select(request => request?.DeepClone()).ToArray());
            return new
            {
                generation = _generation,
                browserGeneration = _browserGeneration,
                manualUntilStoppedSupported = true,
                deployment = DeploymentState(),
                pending = (object?)null,
                activity = _activity.Reverse().Take(30).ToArray(),
                supportedScopes = SupportedScopes,
                logging = Journal?.Health,
                admission,
                accessPolicy = admission,
                pauseSupported = true,
                browserWhileLocked = BrowserWhileLockedState()
            };
        }
    }
    private static int ValidateDuration(int seconds) => seconds is >= 60 and <= 28800 ? seconds : throw new ArgumentException("Duration must be 60-28800 seconds");
}
