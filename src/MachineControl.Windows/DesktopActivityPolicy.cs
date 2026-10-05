namespace MachineControl.Windows;

/// Composes human activity with operator pauses; never restores an old task.
internal sealed class DesktopActivityPolicy(DesktopGrants grants, TimeProvider? time = null)
{
    internal const double QuietSeconds = 30;
    private readonly TimeProvider _time = time ?? TimeProvider.System;
    private double? _physicalAt;
    private double? _takeoverAt;
    private bool _relocked;
    private bool _localUse;
    private readonly HashSet<string> _published = [];
    private double Now => (double)_time.GetTimestamp() / _time.TimestampFrequency;

    internal static bool Physical(bool keyboard, int flags) => (flags & (keyboard ? 0x12 : 0x03)) == 0;

    internal void ObservePhysical(double at)
    {
        lock (grants.Gate) _physicalAt = _physicalAt is { } previous ? Math.Max(previous, at) : at;
    }

    internal void CoveredTakeover()
    {
        lock (grants.Gate)
        {
            _takeoverAt ??= Now;
            _physicalAt = Now;
            Publish("physical_takeover", true);
        }
    }

    internal void ResumeFromOperator()
    {
        lock (grants.Gate)
        {
            _takeoverAt = null; _relocked = false; _localUse = false;
            Publish("physical_takeover", false); Publish("local_use_episode", false);
        }
    }

    internal void Tick(bool healthy, bool? locked, double? idleSeconds, bool active = false)
    {
        lock (grants.Gate)
        {
            var now = Now;
            var knownIdle = idleSeconds is { } idle && double.IsFinite(idle) && idle >= 0;
            // Seed conservatively once. Session idle includes synthetic input;
            // use it only at startup and on the inaccessible locked desktop.
            if (_physicalAt is null && healthy && knownIdle) _physicalAt = now - Math.Min(idleSeconds!.Value, now);
            var known = healthy && locked is not null && _physicalAt is { } at && double.IsFinite(at) && now >= at;
            // Session idle is an admission observation, not a human detector.
            // Stock unlock preparation injects wake/navigation events while
            // still locked; those must not interrupt an already accepted task.
            var checkLockedIdle = locked == true && !active;
            Publish("activity_unknown", !known || checkLockedIdle && !knownIdle);
            Publish("physical_activity", known && (now - _physicalAt!.Value < QuietSeconds || checkLockedIdle && idleSeconds < QuietSeconds));
            if (_takeoverAt is { } takeover)
            {
                if (locked == true) _relocked = true;
                if (locked == false && _relocked) _localUse = true;
                // Relock plus independently observed session quiet permits a
                // fresh owner. Unlocked local use never clears on an idle timer.
                if (known && locked == true && knownIdle && idleSeconds >= QuietSeconds &&
                    now >= takeover && now - takeover >= QuietSeconds && now - _physicalAt!.Value >= QuietSeconds)
                    ResumeFromOperator();
                else
                {
                    Publish("physical_takeover", !_localUse);
                    Publish("local_use_episode", _localUse);
                }
            }
        }
    }

    private void Publish(string reason, bool blocked)
    {
        if (blocked && _published.Add(reason)) grants.ActivityPause(reason);
        else if (!blocked && _published.Remove(reason)) grants.Admission.Resume("desktop", reason);
    }
}
