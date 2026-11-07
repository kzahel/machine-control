using System.Text.Json;
using MachineControl.Windows;

/// Tactical 160: finite, acknowledged extension of a locked-origin prepared
/// owner across resident, service and guardian.
internal static class PreparedRenewalFixtures
{
    internal static async Task RunAsync()
    {
        Frames();
        Guardian();
        Service();
        await ResidentAsync();
        Console.WriteLine("Prepared-owner renewal contracts passed");
    }

    private static void Frames()
    {
        static JsonElement Json(string text) => JsonDocument.Parse(text).RootElement.Clone();
        Require(GuardianExtension.TryRead(Json("{\"allowed\":true}"), out var none) && none is null, "Absent extension is valid and empty");
        Require(GuardianExtension.TryRead(Json("{\"allowed\":true,\"extension\":null}"), out none) && none is null, "Null extension is valid and empty");
        Require(GuardianExtension.TryRead(Json("{\"extension\":{\"sequence\":3,\"seconds\":900}}"), out var parsed) &&
            parsed == new GuardianExtension(3, 900), "Bounded extension parses exactly");
        Require(GuardianExtension.TryRead(Json("{\"extension\":{\"seconds\":1,\"sequence\":1}}"), out parsed) && parsed == new GuardianExtension(1, 1),
            "Minimum extension parses");
        foreach (var invalid in new[]
        {
            "{\"extension\":{\"sequence\":0,\"seconds\":60}}",
            "{\"extension\":{\"sequence\":-1,\"seconds\":60}}",
            "{\"extension\":{\"sequence\":1,\"seconds\":0}}",
            "{\"extension\":{\"sequence\":1,\"seconds\":901}}",
            "{\"extension\":{\"sequence\":1,\"seconds\":60.5}}",
            "{\"extension\":{\"sequence\":1}}",
            "{\"extension\":{\"seconds\":60}}",
            "{\"extension\":{\"sequence\":1,\"seconds\":60,\"credential\":\"x\"}}",
            "{\"extension\":{\"sequence\":\"1\",\"seconds\":60}}",
            "{\"extension\":[1,60]}",
            "{\"extension\":true}",
            "[]"
        })
            Require(!GuardianExtension.TryRead(Json(invalid), out var refused) && refused is null, "Invalid extension frame refused: " + invalid);
        // The exact frames each layer serializes parse back on the next layer.
        GuardianExtension? pending = new(4, 300);
        Require(GuardianExtension.TryRead(Json(Contract.Serialize(new { allowed = true, extension = pending })), out parsed) && parsed == pending,
            "Resident and service extension frames round-trip");
        Require(GuardianExtension.TryRead(Json(Contract.Serialize(new { allowed = false, extension = (GuardianExtension?)null })), out parsed) && parsed is null,
            "A refusal carries no extension");
        long? acknowledged = 4;
        Require(GuardianExtension.TryReadAcknowledgement(Json(Contract.Serialize(new { physicalTakeover = false, acknowledgedExtension = acknowledged })), out var echoed) && echoed == 4,
            "Guardian echo round-trips");
        acknowledged = null;
        Require(GuardianExtension.TryReadAcknowledgement(Json(Contract.Serialize(new { physicalTakeover = false, acknowledgedExtension = acknowledged })), out echoed) && echoed is null,
            "An initial guardian pulse carries no echo");
        Require(GuardianExtension.TryReadAcknowledgement(Json("{\"physicalTakeover\":false}"), out var echo) && echo is null, "Absent echo");
        Require(GuardianExtension.TryReadAcknowledgement(Json("{\"acknowledgedExtension\":7}"), out echo) && echo == 7, "Echo parses");
        foreach (var invalid in new[] { "{\"acknowledgedExtension\":0}", "{\"acknowledgedExtension\":\"7\"}", "{\"acknowledgedExtension\":1.5}" })
            Require(!GuardianExtension.TryReadAcknowledgement(Json(invalid), out _), "Invalid echo refused: " + invalid);
    }

    private static void Guardian()
    {
        // Frequency 1: timestamps are seconds since guardian start.
        var deadline = new GuardianDeadline(0, 1);
        Require(!deadline.Expired(899) && deadline.Expired(900) && deadline.Acknowledged is null, "Guardian starts with a 900-second bound");
        Require(deadline.Extend(new(1, 300), 100, ending: false) == ExtensionOutcome.Acknowledged && deadline.Acknowledged == 1,
            "Guardian acknowledges a valid first extension");
        Require(deadline.Expired(900), "An extension never shortens and max(current, now + seconds) applies");
        Require(deadline.Extend(new(2, 900), 800, ending: false) == ExtensionOutcome.Acknowledged && !deadline.Expired(1699) && deadline.Expired(1700),
            "A later extension moves the deadline at most 900 seconds past acknowledgement");
        Require(deadline.Extend(new(2, 900), 801, ending: false) == ExtensionOutcome.Invalid && deadline.Expired(1700),
            "A replayed sequence is invalid and moves nothing");
        Require(deadline.Extend(new(1, 900), 801, ending: false) == ExtensionOutcome.Invalid, "A regressing sequence is invalid");
        Require(deadline.Extend(new(5, 901), 801, ending: false) == ExtensionOutcome.Invalid && deadline.Acknowledged == 2, "Seconds above 900 are invalid");
        Require(deadline.Extend(new(5, 0), 801, ending: false) == ExtensionOutcome.Invalid, "Zero seconds are invalid");
        Require(deadline.Extend(new(3, 900), 1000, ending: true) == ExtensionOutcome.Ending && deadline.Acknowledged == 2 && deadline.Expired(1700),
            "An ending guardian never extends");
        Require(deadline.Extend(new(3, 900), 1700, ending: false) == ExtensionOutcome.Expired && deadline.Expired(1701) && deadline.Acknowledged == 2,
            "An expired guardian deadline is never revived");
    }

    private static void Service()
    {
        var service = new ServiceExtensions(0, 1) { Supported = true };
        Require(!service.Expired(899) && service.Expired(900), "Service watch starts with a 900-second bound");
        Require(service.Forward(null) is null && !service.Acknowledge(null, 10), "No extension, no acknowledgement");
        Require(service.Forward(new(1, 600)) == new GuardianExtension(1, 600), "First extension is forwarded");
        Require(service.Forward(new(1, 600)) is null, "A pending extension is forwarded once");
        Require(!service.Expired(899) && service.Expired(900), "Forwarding alone moves nothing");
        Refuses(() => service.Acknowledge(2, 10), "An echo beyond the forwarded sequence is a protocol violation");
        Require(service.Acknowledge(1, 500) && service.Acknowledged == 1 && !service.Expired(1099) && service.Expired(1100),
            "Only the guardian echo moves the service deadline");
        Require(!service.Acknowledge(1, 600) && service.Expired(1100), "A repeated echo extends once");
        Refuses(() => service.Forward(new(0, 60)), "A nonpositive resident sequence is refused");
        Require(service.Forward(new(2, 60)) == new GuardianExtension(2, 60), "The next sequence is forwarded");
        Refuses(() => service.Forward(new(1, 60)), "A regressing resident sequence is refused");
        Require(!service.Acknowledge(2, 1100) && service.Expired(1100), "An echo after expiry never revives the service deadline");
    }

    private static async Task ResidentAsync()
    {
        var resident = new ResidentExtensions();
        Refuses(() => resident.Issue(0), "Zero-second renewal refused");
        Refuses(() => resident.Issue(901), "Renewal above 900 seconds refused");
        var first = resident.Issue(300)!.Value;
        Require(first.Extension == new GuardianExtension(1, 300) && resident.Pending == first.Extension, "Resident offers a pending extension");
        Require(resident.Issue(300) is null, "One extension outstanding at a time");
        Refuses(() => resident.Acknowledge(2), "An echo of an unissued sequence is a guard failure");
        resident.Acknowledge(1);
        Require(await resident.AwaitAsync(first.Extension, first.Acknowledged, TimeSpan.FromSeconds(1), default) && resident.Pending is null,
            "The matching echo commits");
        var second = resident.Issue(300)!.Value;
        Require(second.Extension.Sequence == 2, "Sequences strictly increase");
        Require(!await resident.AwaitAsync(second.Extension, second.Acknowledged, TimeSpan.FromMilliseconds(50), default) && resident.Pending is null,
            "A missing echo refuses and withdraws the offer");
        resident.Acknowledge(2);
        Require(resident.Pending is null, "A late echo after refusal is ignored");
        var third = resident.Issue(60)!.Value;
        Require(third.Extension.Sequence == 3, "A refused sequence is never reused");
        resident.Fail();
        Require(!await third.Acknowledged && resident.Pending is null, "An ending lease refuses its pending extension");
    }

    private static void Require(bool value, string message) { if (!value) throw new Exception(message); }
    private static void Refuses(Action action, string message)
    {
        try { action(); }
        catch (ArgumentException) { return; }
        catch (InvalidDataException) { return; }
        throw new Exception("Expected refusal: " + message);
    }
}

/// A protected-lease stand-in using the real resident extension state.
internal sealed class FixtureRenewal : IPreparedRenewal
{
    internal readonly ResidentExtensions Extensions = new();
    internal bool Acknowledges;
    internal int Offers;
    public bool Supported(string owner) => Extensions.Supported;
    public async Task<bool> ExtendAsync(string owner, int seconds, CancellationToken cancellation)
    {
        if (!Extensions.Supported || Extensions.Issue(seconds) is not { } offer) return false;
        Offers++;
        if (Acknowledges) Extensions.Acknowledge(offer.Extension.Sequence);
        return await Extensions.AwaitAsync(offer.Extension, offer.Acknowledged, TimeSpan.FromMilliseconds(200), cancellation);
    }
}
