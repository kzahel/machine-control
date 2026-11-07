using System.IO;
using System.Text.Json;

namespace MachineControl.Windows;

/// Tactical 160: renewal of a live locked-origin prepared owner. The resident
/// offers a finite extension; the service forwards it; the independent
/// guardian accepts it only while not ending and echoes its sequence. Admission
/// commits only after that echo returns to the resident.
internal interface IPreparedRenewal
{
    /// True only when this owner's bound service and guardian reported the
    /// extension protocol and the protected task is not ending.
    bool Supported(string owner);
    /// Returns true only after the guardian acknowledged the extension.
    Task<bool> ExtendAsync(string owner, int seconds, CancellationToken cancellation);
}

internal sealed record GuardianExtension(long Sequence, int Seconds)
{
    internal const int MaximumSeconds = 900;
    internal const string Protocol = "guardian_extension/v1";

    internal static bool Valid(long sequence, int seconds) => sequence > 0 && seconds is >= 1 and <= MaximumSeconds;

    /// An absent or null `extension` is valid and yields null. Any other shape,
    /// an unknown field, a nonpositive sequence or seconds outside 1–900 is
    /// invalid; callers end protected use rather than guess.
    internal static bool TryRead(JsonElement frame, out GuardianExtension? extension)
    {
        extension = null;
        if (frame.ValueKind != JsonValueKind.Object) return false;
        if (!frame.TryGetProperty("extension", out var value) || value.ValueKind == JsonValueKind.Null) return true;
        if (value.ValueKind != JsonValueKind.Object) return false;
        long sequence = 0; int seconds = 0; var fields = 0;
        foreach (var property in value.EnumerateObject())
        {
            fields++;
            if (property.Name == "sequence" && property.Value.ValueKind == JsonValueKind.Number && property.Value.TryGetInt64(out var s)) sequence = s;
            else if (property.Name == "seconds" && property.Value.ValueKind == JsonValueKind.Number && property.Value.TryGetInt32(out var t)) seconds = t;
            else return false;
        }
        if (fields != 2 || !Valid(sequence, seconds)) return false;
        extension = new(sequence, seconds);
        return true;
    }

    /// Absent or null yields null. A present acknowledgement must be a
    /// positive integer.
    internal static bool TryReadAcknowledgement(JsonElement frame, out long? sequence)
    {
        sequence = null;
        if (frame.ValueKind != JsonValueKind.Object) return false;
        if (!frame.TryGetProperty("acknowledgedExtension", out var value) || value.ValueKind == JsonValueKind.Null) return true;
        if (value.ValueKind != JsonValueKind.Number || !value.TryGetInt64(out var number) || number < 1) return false;
        sequence = number;
        return true;
    }
}

internal enum ExtensionOutcome { Acknowledged, Ending, Expired, Invalid }

/// The guardian's own finite monotonic deadline. It starts at 900 seconds,
/// moves only forward, never revives once expired and never extends once the
/// guardian is ending. Timestamps are caller-supplied monotonic ticks.
internal sealed class GuardianDeadline(long start, long frequency)
{
    private readonly object _gate = new();
    private long _deadline = start + GuardianExtension.MaximumSeconds * frequency;
    private long _sequence;
    internal long? Acknowledged { get { lock (_gate) return _sequence == 0 ? null : _sequence; } }
    internal bool Expired(long now) { lock (_gate) return now >= _deadline; }
    internal double RemainingSeconds(long now) { lock (_gate) return Math.Max(0, (_deadline - now) / (double)frequency); }

    internal ExtensionOutcome Extend(GuardianExtension extension, long now, bool ending)
    {
        lock (_gate)
        {
            if (ending) return ExtensionOutcome.Ending;
            if (now >= _deadline) return ExtensionOutcome.Expired;
            if (extension.Sequence <= _sequence || !GuardianExtension.Valid(extension.Sequence, extension.Seconds)) return ExtensionOutcome.Invalid;
            _sequence = extension.Sequence;
            _deadline = Math.Max(_deadline, now + extension.Seconds * frequency);
            return ExtensionOutcome.Acknowledged;
        }
    }
}

/// The service's watch bound. It forwards each resident extension once, in
/// strictly increasing sequence, and moves its own deadline only when the
/// guardian echoes that forwarded sequence.
internal sealed class ServiceExtensions(long start, long frequency)
{
    private readonly object _gate = new();
    private long _deadline = start + GuardianExtension.MaximumSeconds * frequency;
    private long _forwarded, _acknowledged;
    private int _seconds;
    internal bool Supported { get; set; }
    internal long? Acknowledged { get { lock (_gate) return _acknowledged == 0 ? null : _acknowledged; } }
    internal bool Expired(long now) { lock (_gate) return now >= _deadline; }
    internal TimeSpan Remaining(long now) { lock (_gate) return TimeSpan.FromSeconds(Math.Max(0, (_deadline - now) / (double)frequency)); }

    /// Returns the extension to send on this pulse, or null. A sequence lower
    /// than one already forwarded is a protocol violation.
    internal GuardianExtension? Forward(GuardianExtension? offered)
    {
        if (offered is null) return null;
        lock (_gate)
        {
            if (!GuardianExtension.Valid(offered.Sequence, offered.Seconds) || offered.Sequence < _forwarded)
                throw new InvalidDataException("guardian_extension_sequence");
            if (offered.Sequence == _forwarded) return null;
            _forwarded = offered.Sequence; _seconds = offered.Seconds;
            return offered;
        }
    }

    /// Applies a guardian echo. Returns true only when it newly acknowledges
    /// the forwarded extension. An echo beyond what was forwarded is invalid.
    internal bool Acknowledge(long? echoed, long now)
    {
        if (echoed is not { } sequence) return false;
        lock (_gate)
        {
            if (sequence > _forwarded) throw new InvalidDataException("guardian_extension_acknowledgement");
            if (sequence != _forwarded || sequence == _acknowledged) return false;
            if (now >= _deadline) return false;
            _acknowledged = sequence;
            _deadline = Math.Max(_deadline, now + _seconds * frequency);
            return true;
        }
    }
}

/// Resident-side pending extension for one protected lease. At most one
/// extension is outstanding; the admission renewal commits only on its echo.
internal sealed class ResidentExtensions
{
    private readonly object _gate = new();
    private long _issued;
    private GuardianExtension? _pending;
    private TaskCompletionSource<bool>? _waiter;
    internal bool Supported { get; set; }
    internal GuardianExtension? Pending { get { lock (_gate) return _pending; } }

    internal (GuardianExtension Extension, Task<bool> Acknowledged)? Issue(int seconds)
    {
        if (seconds is < 1 or > GuardianExtension.MaximumSeconds) throw new ArgumentException("invalid_renewal_duration");
        lock (_gate)
        {
            if (_pending is not null || _issued == long.MaxValue) return null;
            _pending = new(++_issued, seconds);
            _waiter = new(TaskCreationOptions.RunContinuationsAsynchronously);
            return (_pending, _waiter.Task);
        }
    }

    /// An echo of a sequence never issued is a protocol violation. A late echo
    /// of an abandoned extension is ignored: its admission renewal was refused.
    internal void Acknowledge(long sequence)
    {
        lock (_gate)
        {
            if (sequence < 1 || sequence > _issued) throw new InvalidDataException("guardian_extension_acknowledgement");
            if (_pending?.Sequence != sequence) return;
            _pending = null;
            _waiter!.TrySetResult(true);
        }
    }

    internal void Abandon(long sequence)
    {
        lock (_gate)
        {
            if (_pending?.Sequence != sequence) return;
            _pending = null;
            _waiter!.TrySetResult(false);
        }
    }

    internal void Fail()
    {
        lock (_gate)
        {
            _pending = null;
            _waiter?.TrySetResult(false);
        }
    }

    /// Waits a bounded time for the echo; a missing echo abandons the offer.
    internal async Task<bool> AwaitAsync(GuardianExtension extension, Task<bool> acknowledged, TimeSpan wait, CancellationToken cancellation)
    {
        try { return await acknowledged.WaitAsync(wait, cancellation); }
        catch (TimeoutException) { Abandon(extension.Sequence); return false; }
        catch (OperationCanceledException) { Abandon(extension.Sequence); throw; }
    }
}
