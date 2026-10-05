namespace MachineControl.Windows;

/// One controller's resource arbiter. Only the resident/adapter registers
/// resources and supplies owner identities and authority checks. Facade labels
/// and public request/session identifiers are never authentication.
internal sealed class AccessAdmission(TimeProvider? time = null, object? gate = null)
{
    internal const string Schema = "machine-control-admission/v1";
    internal readonly object Gate = gate ?? new();
    private readonly TimeProvider _time = time ?? TimeProvider.System;
    private readonly Dictionary<string, Resource> _resources = new(StringComparer.Ordinal);
    private readonly List<Intent> _intents = [];
    private readonly Queue<object> _events = new();
    private long _revision;
    private bool _refreshing;
    internal double QueueLeaseSeconds { get; init; } = 60;
    internal double OfferSeconds { get; init; } = 15;
    internal double ActiveHeartbeatSeconds { get; init; } = 5;
    internal event Action<string, string, string>? SessionEnded;
    internal event Action? SessionActivated;
    internal Action? RefreshAvailability { get; set; }
    internal bool HasActiveSession { get { lock (Gate) return _intents.Any(i => i.Session is not null); } }

    private double Now => (double)_time.GetTimestamp() / _time.TimestampFrequency;

    internal void Register(string resource, bool ready = true)
    {
        lock (Gate)
        {
            if (_resources.ContainsKey(resource)) return;
            if (_resources.Count >= 64 || string.IsNullOrWhiteSpace(resource) || resource.Length > 128)
                throw new ArgumentException("Invalid resource registration");
            _resources.Add(resource, new Resource { Ready = ready });
        }
    }

    internal void SetReady(string resource, bool ready)
    {
        lock (Gate)
        {
            var item = _resources[resource];
            if (item.Ready == ready) return;
            item.Ready = ready;
            Change("resource.readiness");
            Refresh();
        }
    }

    internal void Pause(string resource, string reason, double? seconds = null)
    {
        if (string.IsNullOrWhiteSpace(reason) || reason.Length > 80 || seconds is <= 0 or > 28800 ||
            seconds is { } value && !double.IsFinite(value))
            throw new ArgumentException("Invalid pause");
        lock (Gate)
        {
            _resources[resource].Pauses[reason] = seconds is { } duration ? Now + duration : null;
            Change("resource.paused");
            Refresh();
        }
    }

    internal void Resume(string resource, string reason)
    {
        lock (Gate)
        {
            if (_resources[resource].Pauses.Remove(reason)) Change("resource.resumed");
            Refresh();
        }
    }

    internal string[] Blocks(string resource)
    {
        lock (Gate)
        {
            Refresh();
            return ResourceBlocks(_resources[resource]);
        }
    }

    /// Ownership is supplied by an admitted channel, never from request JSON.
    internal object Submit(string owner, string requestId, string[] resources,
        double waitSeconds, double durationSeconds, string reason,
        Func<string?> authority, double noticeSeconds = 0)
    {
        lock (Gate)
        {
            Refresh();
            if (string.IsNullOrWhiteSpace(owner) || string.IsNullOrWhiteSpace(requestId) || requestId.Length > 80 ||
                resources.Length is < 1 or > 8 || resources.Distinct().Count() != resources.Length ||
                resources.Any(r => !_resources.ContainsKey(r)) || waitSeconds is < 1 or > 14400 ||
                durationSeconds is < 1 or > 900 || noticeSeconds is < 0 or > 60 ||
                !double.IsFinite(waitSeconds) || !double.IsFinite(durationSeconds) || !double.IsFinite(noticeSeconds) ||
                string.IsNullOrWhiteSpace(reason) || reason.Length > 240)
                throw new ArgumentException("Invalid admission request");
            var normalized = resources.Order(StringComparer.Ordinal).ToArray();
            var existing = _intents.FirstOrDefault(i => i.Owner == owner && i.RequestId == requestId);
            if (existing is not null)
            {
                if (!existing.Resources.SequenceEqual(normalized) || existing.Duration != durationSeconds ||
                    existing.WaitSeconds != waitSeconds || existing.Reason != reason || existing.RequestedNotice != noticeSeconds)
                    throw new ArgumentException("Idempotency key reused with different intent");
                return View(existing);
            }
            if (_intents.Count(i => i.Owner == owner && i.Terminal is null) >= 4 ||
                _intents.Count(i => i.Terminal is null) >= 256)
                throw new InvalidOperationException("admission_queue_full");
            var intent = new Intent
            {
                Id = Guid.NewGuid().ToString("n"),
                Owner = owner,
                RequestId = requestId,
                Resources = normalized,
                Deadline = Now + waitSeconds,
                WaitSeconds = waitSeconds,
                Heartbeat = Now + QueueLeaseSeconds,
                Duration = durationSeconds,
                Reason = reason,
                Authority = authority,
                Notice = noticeSeconds,
                RequestedNotice = noticeSeconds,
            };
            _intents.Add(intent);
            Change("intent.submitted", intent);
            Refresh();
            return View(intent);
        }
    }

    internal object Inspect(string owner, string id, bool heartbeat = false)
    {
        lock (Gate)
        {
            Refresh();
            var intent = Owned(owner, id);
            if (heartbeat && intent.Terminal is null)
                intent.Heartbeat = Now + (intent.Session is null ? QueueLeaseSeconds : ActiveHeartbeatSeconds);
            return View(intent);
        }
    }

    internal object Accept(string owner, string id, long offerGeneration)
    {
        lock (Gate)
        {
            Refresh();
            var intent = Owned(owner, id);
            if (intent.Terminal is not null || intent.State != "offered" || intent.OfferGeneration != offerGeneration)
                throw new InvalidOperationException("stale_activation_offer");
            // Refresh already checked authority, readiness and the complete set.
            if (intent.Resources.Any(r => ResourceBlocks(_resources[r]).Length != 0 ||
                _resources[r].Holder is not null)) throw new InvalidOperationException("admission_changed");
            intent.Session = Guid.NewGuid().ToString("n");
            intent.ActiveDeadline = Now + intent.Duration;
            intent.Heartbeat = Now + ActiveHeartbeatSeconds;
            intent.State = "active";
            intent.Generations.Clear();
            foreach (var resource in intent.Resources)
            {
                var item = _resources[resource];
                item.Holder = intent.Id;
                intent.Generations.Add(resource, ++item.Generation);
            }
            Change("session.activated", intent);
            SessionActivated?.Invoke();
            return View(intent);
        }
    }

    internal string? Authorize(string owner, string id, string sessionId, IReadOnlyDictionary<string, long> generations)
    {
        lock (Gate)
        {
            Refresh();
            var intent = _intents.FirstOrDefault(i => i.Id == id && i.Owner == owner);
            if (intent is null || intent.Terminal is not null || intent.Session != sessionId || intent.State != "active")
                return "stale_control_session";
            if (generations.Count != intent.Generations.Count || intent.Generations.Any(pair =>
                !generations.TryGetValue(pair.Key, out var value) || value != pair.Value)) return "stale_generation";
            return null;
        }
    }

    internal void Cancel(string owner, string id)
    {
        lock (Gate)
        {
            Refresh();
            var intent = Owned(owner, id);
            if (intent.Terminal is null) Finish(intent, "cancelled");
            Refresh();
        }
    }

    internal void Disconnect(string owner)
    {
        lock (Gate)
        {
            foreach (var intent in _intents.Where(i => i.Owner == owner && i.Terminal is null).ToArray())
                Finish(intent, "owner_disconnected");
            Refresh();
        }
    }

    internal void Stop(string reason)
    {
        lock (Gate)
        {
            foreach (var intent in _intents.Where(i => i.Terminal is null).ToArray()) Finish(intent, reason);
        }
    }

    internal void CancelFromOperator(string id)
    {
        lock (Gate)
        {
            Refresh();
            var intent = _intents.FirstOrDefault(i => i.Id == id)
                ?? throw new InvalidOperationException("stale_activation_notice");
            if (intent.Terminal is null) Finish(intent, "cancelled_by_person");
            Refresh();
        }
    }

    /// Local operator only; does not clear activity, readiness or authority.
    internal void StartNow(string id)
    {
        lock (Gate)
        {
            Refresh();
            var intent = _intents.FirstOrDefault(i => i.Id == id && i.Terminal is null && i.Session is null)
                ?? throw new InvalidOperationException("stale_activation_notice");
            intent.Notice = 0;
            intent.State = "waiting_for_resource";
            Refresh();
        }
    }

    internal void Refresh()
    {
        lock (Gate)
        {
            if (_refreshing) return;
            _refreshing = true;
            try
            {
                RefreshAvailability?.Invoke();
                var now = Now;
                foreach (var resource in _resources.Values)
                    foreach (var reason in resource.Pauses.Where(p => p.Value is { } end && now >= end).Select(p => p.Key).ToArray())
                    { resource.Pauses.Remove(reason); Change("resource.pause_expired"); }
                foreach (var intent in _intents.Where(i => i.Terminal is null).ToArray())
                {
                    var denied = intent.Authority();
                    intent.AuthorizationBlock = denied;
                    if (intent.Terminal is not null) continue;
                    if (denied is not null && (denied != "approval_required" || intent.Session is not null))
                    { Finish(intent, denied); continue; }
                    if (now >= intent.Heartbeat) { Finish(intent, intent.Session is null ? "queue_lease_expired" : "owner_disconnected"); continue; }
                    if (intent.Session is not null)
                    {
                        if (now >= intent.ActiveDeadline) { Finish(intent, "duration_expired"); continue; }
                        if (intent.Resources.Any(r => ResourceBlocks(_resources[r]).Length > 0))
                        {
                            Release(intent, "paused");
                            intent.State = "paused";
                            intent.Heartbeat = now + QueueLeaseSeconds;
                            // Yield position without extending the caller deadline.
                            _intents.Remove(intent); _intents.Add(intent);
                        }
                    }
                    else if (now >= intent.Deadline) Finish(intent, "wait_deadline_exceeded");
                    else if (intent.State == "offered" && now >= intent.OfferDeadline) Finish(intent, "activation_offer_expired");
                }
                var reserved = _resources.Where(pair => pair.Value.Holder is not null).Select(pair => pair.Key).ToHashSet();
                foreach (var intent in _intents.Where(i => i.Terminal is null && i.Session is null))
                {
                    if (intent.AuthorizationBlock is not null)
                    {
                        if (intent.State != "waiting_for_approval")
                        { intent.State = "waiting_for_approval"; intent.OfferGeneration = 0; Change("intent.waiting", intent); }
                        continue;
                    }
                    var blocks = intent.Resources.SelectMany(r => ResourceBlocks(_resources[r])).Distinct().Order().ToArray();
                    var contended = intent.Resources.Any(reserved.Contains);
                    if (blocks.Length > 0 || contended)
                    {
                        var state = blocks.Length > 0 ? "paused" : "waiting_for_resource";
                        if (intent.State != state) { intent.State = state; intent.OfferGeneration = 0; Change("intent.waiting", intent); }
                        continue;
                    }
                    // Notices/offers reserve the complete set for this pass only,
                    // never a partial set while unavailable.
                    foreach (var resource in intent.Resources) reserved.Add(resource);
                    if (intent.State is not ("announcing" or "offered"))
                    {
                        intent.NoticeDeadline = now + intent.Notice;
                        intent.State = intent.Notice > 0 ? "announcing" : "offered";
                        intent.OfferDeadline = now + OfferSeconds;
                        intent.OfferGeneration = Change("intent.eligible", intent);
                    }
                    if (intent.State == "announcing" && now >= intent.NoticeDeadline)
                    {
                        intent.State = "offered";
                        intent.OfferDeadline = now + OfferSeconds;
                        intent.OfferGeneration = Change("intent.offered", intent);
                    }
                }
                var terminal = _intents.Where(i => i.Terminal is not null).ToArray();
                foreach (var intent in terminal.Take(Math.Max(0, terminal.Length - 256))) _intents.Remove(intent);
            }
            finally { _refreshing = false; }
        }
    }

    internal bool Reserved
    {
        get { lock (Gate) { Refresh(); return _intents.Any(i => i.Terminal is null && i.State is "active" or "offered" or "announcing"); } }
    }

    internal object Status()
    {
        lock (Gate)
        {
            Refresh();
            return new
            {
                schema = Schema,
                revision = _revision,
                ownerBinding = "admitted_channel",
                resources = _resources.Select(pair => new
                {
                    resource = pair.Key,
                    generation = pair.Value.Generation,
                    blockingReasons = ResourceBlocks(pair.Value),
                    held = pair.Value.Holder is not null,
                }).ToArray(),
                waiting = _intents.Count(i => i.Terminal is null && i.Session is null),
                active = _intents.Count(i => i.Session is not null),
                events = _events.ToArray(),
                requests = _intents.Where(i => i.Terminal is null).Select(View).ToArray(),
            };
        }
    }

    private Intent Owned(string owner, string id) => _intents.FirstOrDefault(i => i.Id == id && i.Owner == owner)
        ?? throw new InvalidOperationException("admission_owner_mismatch");
    private static string[] ResourceBlocks(Resource resource) => resource.Pauses.Keys
        .Concat(resource.Ready ? [] : new[] { "resource_unavailable" }).Order().ToArray();
    private void Release(Intent intent, string reason)
    {
        if (intent.Session is not { } session) return;
        foreach (var resource in intent.Resources)
        {
            var item = _resources[resource];
            if (item.Holder == intent.Id) { item.Holder = null; ++item.Generation; }
        }
        intent.Session = null; intent.Generations.Clear(); intent.OfferGeneration = 0;
        Change("session." + reason, intent);
        SessionEnded?.Invoke(intent.Owner, session, reason);
    }
    private void Finish(Intent intent, string reason)
    {
        Release(intent, reason);
        intent.Terminal = reason; intent.State = "ended";
        Change("intent." + reason, intent);
    }
    private long Change(string kind, Intent? intent = null)
    {
        _events.Enqueue(new { revision = ++_revision, kind, intentId = intent?.Id });
        while (_events.Count > 128) _events.Dequeue();
        return _revision;
    }
    private object View(Intent intent) => new
    {
        schema = Schema,
        revision = _revision,
        intentId = intent.Id,
        state = intent.State,
        terminalReason = intent.Terminal,
        offerGeneration = intent.OfferGeneration,
        sessionId = intent.Session,
        resourceGenerations = new Dictionary<string, long>(intent.Generations),
        blockingReasons = intent.Resources.SelectMany(r => ResourceBlocks(_resources[r]))
            .Concat(intent.AuthorizationBlock is { } block ? new[] { block } : []).Distinct().Order().ToArray(),
        waitRemainingSeconds = Math.Max(0, intent.Deadline - Now),
        leaseRemainingSeconds = Math.Max(0, intent.Heartbeat - Now),
        offerRemainingSeconds = intent.State == "offered" ? Math.Max(0, intent.OfferDeadline - Now) : (double?)null,
        noticeRemainingSeconds = intent.State == "announcing" ? Math.Max(0, intent.NoticeDeadline - Now) : (double?)null,
        activeRemainingSeconds = intent.Session is null ? (double?)null : Math.Max(0, intent.ActiveDeadline - Now),
        reason = intent.Reason,
        maximumDurationSeconds = intent.Duration,
    };
    private sealed class Resource
    {
        internal bool Ready;
        internal long Generation;
        internal string? Holder;
        internal readonly Dictionary<string, double?> Pauses = new(StringComparer.Ordinal);
    }
    private sealed class Intent
    {
        internal required string Id, Owner, RequestId, Reason;
        internal required string[] Resources;
        internal required Func<string?> Authority;
        internal double Deadline, WaitSeconds, Heartbeat, Duration, Notice, RequestedNotice, NoticeDeadline, OfferDeadline, ActiveDeadline;
        internal long OfferGeneration;
        internal string State = "waiting_for_resource";
        internal string? Terminal, Session, AuthorizationBlock;
        internal readonly Dictionary<string, long> Generations = new(StringComparer.Ordinal);
    }
}
