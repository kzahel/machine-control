using System.Text.Json;
using MachineControl.Windows;

internal static class DesktopActivityFixtures
{
    internal static void Run()
    {
        var clock = new TestTime(); clock.Advance(100);
        var grants = TestBrowserProjection.Create(clock); grants.SetReady(true); grants.ConfigureSurface("desktop", "automatic", 900, "timed");
        grants.Admission.Notice(10);
        var policy = grants.Activity;
        bool? locked = false; double? idle = 0; bool healthy = true;
        grants.Admission.RefreshAvailability = () => policy.Tick(healthy, locked, idle, grants.Admission.HasActiveSession);
        JsonElement View(object value) => JsonSerializer.SerializeToElement(value, Contract.Json);
        bool Block(string reason) => grants.Admission.Blocks("desktop").Contains(reason);
        Require(!Block("physical_activity"), "Recent unlocked activity does not block a warning");
        var notice = View(grants.Admission.Submit("owner", "request", ["desktop"], 300, 120, "activity fixture"));
        var id = notice.GetProperty("intentId").GetString()!;
        for (var i = 0; i < 10; ++i) { clock.Advance(1); policy.ObservePhysical(clock.GetTimestamp()); }
        var offer = View(grants.Admission.Inspect("owner", id));
        Require(offer.GetProperty("state").GetString() == "offered", "Typing does not restart countdown");
        var active = View(grants.Admission.Accept("owner", id, offer.GetProperty("offerGeneration").GetInt64()));
        var session = active.GetProperty("sessionId").GetString()!;
        var generations = active.GetProperty("resourceGenerations").Deserialize<Dictionary<string, long>>()!;
        clock.Advance(1); policy.ObservePhysical(clock.GetTimestamp(), "movement");
        Require(grants.Admission.Authorize("owner", id, session, generations) is null, "Mouse motion does not interrupt");
        policy.ObservePhysical(clock.GetTimestamp(), "button");
        Require(grants.Admission.Authorize("owner", id, session, generations) == "stale_control_session", "Deliberate input fences before dispatch");
        Require(grants.Admission.Enabled("desktop"), "Takeover retains consent");
        for (var i = 0; i < 12; ++i)
        {
            clock.Advance(5); policy.ObservePhysical(clock.GetTimestamp()); grants.Admission.Inspect("owner", id, heartbeat: true);
        }
        var fresh = View(grants.Admission.Inspect("owner", id));
        Require(fresh.GetProperty("state").GetString() == "announcing", "Fixed cooldown expires while typing continues");
        grants.Admission.StartNow(id);
        offer = View(grants.Admission.Inspect("owner", id));
        var replacement = View(grants.Admission.Accept("owner", id, offer.GetProperty("offerGeneration").GetInt64()));
        Require(replacement.GetProperty("sessionId").GetString() != session, "Fresh owner after takeover");
        foreach (var keyboard in new[] { true, false })
        {
            Require(DesktopActivityPolicy.Physical(keyboard, 0), "Uninjected input classified");
            Require(!DesktopActivityPolicy.Physical(keyboard, keyboard ? 0x10 : 1), "Injected input ignored");
            Require(!DesktopActivityPolicy.Physical(keyboard, 2), "Lower-integrity injected input ignored");
        }
        Require(!DesktopActivityPolicy.Deliberate(false, 0x200), "Ordinary and covered hooks ignore movement as takeover");
        Require(!DesktopActivityPolicy.Deliberate(false, 0x202) && !DesktopActivityPolicy.Deliberate(true, 0x101), "Releases do not interrupt the Start now interaction");
        foreach (var message in new long[] { 0x201, 0x204, 0x207, 0x20B, 0x20A, 0x20E })
            Require(DesktopActivityPolicy.Deliberate(false, message), "Mouse buttons and both wheel axes are deliberate");
        Require(DesktopActivityPolicy.Deliberate(true, 0x100) && DesktopActivityPolicy.Deliberate(true, 0x104), "Normal and system key down are deliberate");
        healthy = false; Require(Block("activity_unknown"), "Monitor failure blocks native desktop");
        grants.Resume(); Require(Block("activity_unknown"), "Resume does not clear a safety failure");
        healthy = true; locked = true; idle = null;
        Require(Block("activity_unknown"), "Unknown protected idle fails closed");
        idle = 100; policy.CoveredTakeover();
        Require(Block("physical_takeover"), "Covered takeover retains its native latch");
        locked = false; clock.Advance(31);
        Require(Block("local_use_episode"), "Covered local use does not auto-clear while unlocked");
        locked = true; idle = 30;
        Require(!Block("local_use_episode") && !Block("physical_takeover"), "Protected relock plus quiet permits new ownership");
        grants.Stop("fixture_stop");
        grants.Admission.Disconnect("owner");
        Console.WriteLine("Windows deliberate activity and protected guard contracts passed");
    }
    private static void Require(bool value, string message) { if (!value) throw new Exception(message); }
}
