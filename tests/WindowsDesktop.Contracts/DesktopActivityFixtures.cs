using System.Text.Json;
using MachineControl.Windows;

internal static class DesktopActivityFixtures
{
    internal static void Run()
    {
        var clock = new TestTime(); clock.Advance(100);
        var grants = new DesktopGrants(clock); grants.SetReady(true); grants.Arm(["observe", "control"], 900);
        var policy = grants.Activity;
        bool? locked = false; double? idle = 100; bool healthy = true;
        grants.Admission.RefreshAvailability = () => policy.Tick(healthy, locked, idle);
        JsonElement View(object value) => JsonSerializer.SerializeToElement(value, Contract.Json);
        bool Block(string reason) => grants.Admission.Blocks("desktop").Contains(reason);
        Require(!Block("physical_activity"), "Old startup idle allows admission");
        var offer = View(grants.Admission.Submit("owner", "request", ["desktop"], 300, 120, "activity fixture", () => grants.AdmissionAuthority(["control"])));
        var id = offer.GetProperty("intentId").GetString()!;
        var active = View(grants.Admission.Accept("owner", id, offer.GetProperty("offerGeneration").GetInt64()));
        var session = active.GetProperty("sessionId").GetString()!;
        var generations = active.GetProperty("resourceGenerations").Deserialize<Dictionary<string, long>>()!;
        var generation = grants.Generation;
        clock.Advance(1); policy.ObservePhysical(clock.GetTimestamp());
        Require(grants.Admission.Authorize("owner", id, session, generations) == "stale_control_session", "Input fences ownership before dispatch");
        Require(grants.Generation != generation && Block("physical_activity"), "Input invalidates references");
        Require(View(grants.DeploymentState()).GetProperty("grant").ValueKind == JsonValueKind.Object, "Activity preserves consent");
        grants.Pause(); clock.Advance(29);
        Require(Block("physical_activity"), "Quiet boundary does not clear early");
        clock.Advance(1);
        Require(!Block("physical_activity") && Block("manual"), "Quiet clears only physical pause");
        grants.Resume();
        var fresh = View(grants.Admission.Inspect("owner", id));
        Require(fresh.GetProperty("state").GetString() == "offered", "Waiting owner gets a fresh offer");
        var replacement = View(grants.Admission.Accept("owner", id, fresh.GetProperty("offerGeneration").GetInt64()));
        Require(replacement.GetProperty("sessionId").GetString() != session, "Resumption never restores retired ownership");
        Require(grants.Admission.Authorize("owner", id, session, generations) is not null, "Retired action cannot replay");
        policy.Tick(true, true, 0, active: true);
        Require(!Block("physical_activity"), "Synthetic locked preparation does not interrupt accepted owner");
        foreach (var keyboard in new[] { true, false })
        {
            Require(DesktopActivityPolicy.Physical(keyboard, 0), "Uninjected input classified");
            Require(!DesktopActivityPolicy.Physical(keyboard, keyboard ? 0x10 : 1), "Injected input ignored");
            Require(!DesktopActivityPolicy.Physical(keyboard, 2), "Lower-integrity injected input ignored");
        }
        healthy = false; Require(Block("activity_unknown"), "Monitor failure blocks admission");
        grants.Resume(); Require(Block("activity_unknown"), "Operator Resume cannot clear monitor failure");
        healthy = true; locked = true; idle = null;
        Require(Block("activity_unknown"), "Unknown locked idle refuses resumption");
        idle = 100; policy.CoveredTakeover();
        Require(Block("physical_takeover"), "Covered takeover pauses");
        locked = false; clock.Advance(31);
        Require(Block("local_use_episode"), "Owner unlock protects local-use episode");
        clock.Advance(100);
        Require(Block("local_use_episode"), "Local-use episode never auto clears while unlocked");
        locked = true; idle = 29;
        Require(Block("local_use_episode"), "Relock alone is insufficient");
        idle = 30;
        Require(!Block("local_use_episode") && !Block("physical_takeover"), "Relock plus verified quiet enables a fresh owner");
        policy.CoveredTakeover(); idle = double.NaN; clock.Advance(31);
        Require(Block("activity_unknown") && Block("physical_takeover"), "Nonfinite idle fails closed");
        idle = 100; policy.ObservePhysical(clock.GetTimestamp() + 10);
        Require(Block("activity_unknown"), "Future activity timestamp fails closed");
        grants.Stop("fixture_stop");
        Require(grants.AdmissionAuthority(["control"]) == "approval_required", "Quiet never recreates stopped consent");
        Console.WriteLine("Windows activity and quiet-resumption contracts passed");
    }
    private static void Require(bool value, string message) { if (!value) throw new Exception(message); }
}
