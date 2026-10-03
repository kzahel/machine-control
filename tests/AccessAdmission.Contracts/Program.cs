using System.Text.Json;
using MachineControl.Windows;

static JsonElement Json(object value) => JsonSerializer.SerializeToElement(value);
static string Id(object value) => Json(value).GetProperty("intentId").GetString()!;
static void Assert(bool test, string name) { if (!test) throw new Exception(name); }
static void Refuses(Action action, string name)
{
    try { action(); } catch (InvalidOperationException) { return; } catch (ArgumentException) { return; }
    throw new Exception("Expected refusal: " + name);
}
var clock = new Clock();
var admission = new AccessAdmission(clock);
foreach (var resource in new[] { "host", "vm-a", "vm-b" }) admission.Register(resource);
object Submit(string owner, string key, string[] resources, double wait = 300, double notice = 0,
    Func<string?>? authority = null) => admission.Submit(owner, key, resources, wait, 120, "Fixture", authority ?? (() => null), notice);
object Accept(string owner, string id) => admission.Accept(owner, id,
    Json(admission.Inspect(owner, id)).GetProperty("offerGeneration").GetInt64());
var first = Submit("a", "first", ["host", "vm-a"]);
var firstId = Id(first);
Assert(Json(first).GetProperty("state").GetString() == "offered", "First intent offered");
Assert(Id(Submit("a", "first", ["vm-a", "host"])) == firstId, "Idempotent normalized resource set");
Refuses(() => Submit("a", "first", ["host"]), "Cannot reuse key with different work");
var secondId = Id(Submit("b", "second", ["host", "vm-b"]));
Assert(Json(admission.Inspect("b", secondId)).GetProperty("state").GetString() == "waiting_for_resource", "Two VMs contend for host");
var innerId = Id(Submit("c", "inner", ["vm-b"]));
Assert(Json(admission.Inspect("c", innerId)).GetProperty("state").GetString() == "offered", "No partial host waiter hold");
Refuses(() => admission.Cancel("b", firstId), "Labels cannot cancel another owner");
var active = Json(Accept("a", firstId));
var session = active.GetProperty("sessionId").GetString()!;
var generations = active.GetProperty("resourceGenerations").Deserialize<Dictionary<string, long>>()!;
Assert(admission.Authorize("a", firstId, session, generations) is null, "Live generation accepted");
Assert(admission.Authorize("b", firstId, session, generations) == "stale_control_session", "Wrong channel rejected");
admission.Pause("host", "manual");
admission.Pause("host", "activity", 30);
Assert(admission.Authorize("a", firstId, session, generations) == "stale_control_session", "Pause fences active dispatch");
admission.Resume("host", "manual");
Assert(admission.Blocks("host").SequenceEqual(new[] { "activity" }), "Resume clears only selected reason");
clock.Advance(30);
admission.Inspect("a", firstId, heartbeat: true);
admission.Inspect("b", secondId, heartbeat: true);
admission.Cancel("c", innerId);
Assert(Json(admission.Inspect("b", secondId)).GetProperty("state").GetString() == "offered", "Paused owner yields position");
Assert(admission.Authorize("a", firstId, session, generations) == "stale_control_session", "Resume cannot replay old session");
admission.Cancel("b", secondId);
var resumed = Json(Accept("a", firstId));
Assert(resumed.GetProperty("sessionId").GetString() != session, "Fresh session after pause");
clock.Advance(5);
Assert(Json(admission.Inspect("a", firstId, heartbeat: true)).GetProperty("terminalReason").GetString() == "owner_disconnected", "Late heartbeat cannot revive active session");
var dead = Id(Submit("d", "dead", ["host"]));
clock.Advance(15);
Assert(Json(admission.Inspect("d", dead)).GetProperty("terminalReason").GetString() == "activation_offer_expired", "Offer expires without a ready owner");
admission.Pause("host", "manual");
var waiter = Id(Submit("e", "waiter", ["host"]));
clock.Advance(60);
Assert(Json(admission.Inspect("e", waiter, heartbeat: true)).GetProperty("terminalReason").GetString() == "queue_lease_expired", "Dead waiter expires while paused");
var useful = Id(Submit("e", "useful", ["host"], wait: 10));
clock.Advance(9); admission.Inspect("e", useful, heartbeat: true);
clock.Advance(1);
Assert(Json(admission.Inspect("e", useful)).GetProperty("terminalReason").GetString() == "wait_deadline_exceeded", "Useful deadline independent of heartbeat");
string? denial = null;
var denied = Id(Submit("f", "denied", ["host"], authority: () => denial));
denial = "authorization_expired";
Assert(Json(admission.Inspect("f", denied)).GetProperty("terminalReason").GetString() == denial, "Paused grant still expires");
admission.Resume("host", "manual");
var announced = Id(Submit("g", "announced", ["host"], notice: 10));
clock.Advance(9);
Assert(Json(admission.Inspect("g", announced)).GetProperty("state").GetString() == "announcing", "Notice does not activate early");
admission.Pause("host", "activity", 30);
clock.Advance(1);
Assert(Json(admission.Inspect("g", announced)).GetProperty("state").GetString() == "paused", "Activity invalidates countdown");
clock.Advance(29);
Assert(Json(admission.Inspect("g", announced)).GetProperty("state").GetString() == "announcing", "Quiet requires fresh notice");
admission.Disconnect("g");
Refuses(() => Accept("g", announced), "Disconnect cancels notice");
// Contention and cancellation run through the same arbiter lock.
Parallel.For(0, 100, n => { var id = Id(Submit("parallel-" + n, "task", ["host"])); admission.Cancel("parallel-" + n, id); });
Assert(Json(admission.Status()).GetProperty("active").GetInt32() == 0, "No orphan session after contention");
Assert(Json(admission.Status()).GetProperty("events").GetArrayLength() <= 128, "Event history bounded");
var restart = new AccessAdmission(clock); restart.Register("host");
Refuses(() => restart.Inspect("a", firstId), "Restart never restores old queue authority");
var approval = new AccessAdmission(clock); approval.Register("host");
var permission = false;
var awaiting = Id(approval.Submit("owner", "pending", ["host"], 100, 60, "Approval", () => permission ? null : "approval_required"));
Assert(Json(approval.Inspect("owner", awaiting)).GetProperty("state").GetString() == "waiting_for_approval", "Approval waiting holds no resource");
permission = true;
Assert(Json(approval.Inspect("owner", awaiting)).GetProperty("state").GetString() == "offered", "Approval permits eligible offer");
Refuses(() => approval.Submit("owner", "nan", ["host"], double.NaN, 60, "Invalid", () => null), "Non-finite deadline refused");
Refuses(() => approval.Pause("host", "invalid", double.NaN), "Non-finite pause refused");
approval.Pause("host", "manual"); approval.StartNow(awaiting);
Assert(Json(approval.Inspect("owner", awaiting)).GetProperty("state").GetString() == "paused", "Start now cannot bypass pause");
Console.WriteLine("Access admission contract checks passed");

sealed class Clock : TimeProvider
{
    private long _ticks;
    public override long TimestampFrequency => 1000;
    public override long GetTimestamp() => Interlocked.Read(ref _ticks);
    internal void Advance(double seconds) => Interlocked.Add(ref _ticks, (long)(seconds * 1000));
}
