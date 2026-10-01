using System.Text.Json;
using MachineControl.Windows;

static void Assert(bool condition, string message)
{
    if (!condition) throw new Exception(message);
}
static void Refuses(Action action, string message)
{
    try { action(); } catch (ArgumentException) { return; } catch (InvalidOperationException) { return; }
    throw new Exception("Expected refusal: " + message);
}
static JsonElement State(DesktopGrants broker) => JsonSerializer.SerializeToElement(broker.State(), Contract.Json);
static string Pending(DesktopGrants broker) => State(broker).GetProperty("pending").GetProperty("id").GetString()!;
var clock = new TestTime();
var broker = new DesktopGrants(clock);
broker.SetReady(true);
Assert(broker.Authorize("snapshot") == "approval_required", "Off by default");
Assert(broker.Authorize("session.login") == "unsupported_operation", "No protected scope");
Refuses(() => broker.Arm(["browser"], 60), "Unsupported scope");
Refuses(() => broker.Arm(["observe"], 59), "Unbounded duration");
var original = broker.Generation;
broker.Arm(["observe"], 60);
Assert(broker.Generation != original, "Arming changes generation");
Assert(broker.Authorize("snapshot") is null && broker.Authorize("invoke") == "approval_required", "View-only scope");
Assert(broker.Authorize("snapshot", original) == "stale_generation", "Old references invalidated");
Refuses(broker.PrepareUpdate, "No replacement with active access");
clock.Advance(61);
Assert(broker.Authorize("snapshot") == "approval_required", "Monotonic expiry");
var request = new Request
{
    Operation = "grant.request",
    Scopes = ["observe", "control"],
    DurationSeconds = 300,
    TimeoutSeconds = 5,
    Reason = "Fixture control"
};
broker.Arm(["observe", "control"], 60);
var covered = await broker.RequestAsync(request, "caller");
Assert(covered.Accepted, "Covered request reuses access");
broker.Stop("test");
var waiting = broker.RequestAsync(request, "caller");
Assert(broker.Authorize("click") == "approval_prompt_visible", "Prompt pauses control");
Assert(!(await broker.RequestAsync(request, "other")).Accepted, "One pending request");
Refuses(() => broker.Decide("stale", true, ["observe"], 60), "Stale approval");
Refuses(() => broker.Decide(Pending(broker), true, ["observe"], 301), "Duration widening");
Refuses(() => broker.Decide(Pending(broker), true, ["browser"], 60), "Scope widening");
broker.Decide(Pending(broker), true, ["observe"], 60);
Assert((await waiting).Accepted && broker.Authorize("invoke") == "approval_required", "Narrowed approval enforced");
broker.Stop("test");
waiting = broker.RequestAsync(request, "caller");
broker.Decide(Pending(broker), false, null, 0);
Assert((await waiting).ErrorCode == "approval_denied", "Denied request");
waiting = broker.RequestAsync(request, "caller");
clock.Advance(6); broker.Refresh();
Assert((await waiting).ErrorCode == "approval_timeout", "Bounded request timeout");
broker.Arm(["observe", "control"], 300);
original = broker.Generation;
broker.SetReady(false);
broker.SetReady(true);
Assert(broker.Authorize("invoke") == "approval_required" && broker.Generation != original, "Lock/unlock does not revive access");
waiting = broker.RequestAsync(request, "caller");
broker.Stop("stopped_by_person");
Assert((await waiting).ErrorCode == "stopped_by_person", "Stop dismisses approval");
broker.PrepareUpdate();
Refuses(() => broker.Arm(["control"], 60), "Update gate blocks arming");
Assert((await broker.RequestAsync(request, "caller")).ErrorCode == "update_in_progress", "Update gate blocks requests");
broker.CancelUpdate();
broker.Arm(["control"], 60);
Assert(broker.Authorize("type") is null, "Update failure restores availability with explicit rearm");
for (var i = 0; i < 150; i++) broker.Record(new Result { RequestId = "test", Operation = "invoke", Accepted = false });
Assert(State(broker).GetProperty("activity").GetArrayLength() == 30, "Bounded activity projection");
Console.WriteLine("Windows desktop grant contracts passed");

sealed class TestTime : TimeProvider
{
    private long _seconds;
    public override long TimestampFrequency => 1;
    public override long GetTimestamp() => _seconds;
    public override DateTimeOffset GetUtcNow() => DateTimeOffset.UnixEpoch.AddSeconds(_seconds);
    public void Advance(int seconds) => _seconds += seconds;
}
