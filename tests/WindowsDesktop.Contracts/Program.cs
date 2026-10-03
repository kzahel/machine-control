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
var updates = new DesktopUpdates();
Refuses(() => updates.Request(true), "Updater not initialized by operator");
var idleUpdates = System.Text.Json.Nodes.JsonNode.Parse("{\"checking\":false,\"installing\":false}")!.AsObject();
Assert(!updates.Sync(idleUpdates), "Status sync does not request discovery");
updates.Request(true);
updates.Request(true);
Assert(updates.Sync(idleUpdates), "Requests coalesce and are consumed once");
Assert(JsonSerializer.SerializeToElement(updates.Request(false), Contract.Json)
    .GetProperty("update").GetProperty("checking").GetBoolean(),
    "Consumed request stays busy until authoritative state arrives");
Assert(!updates.Sync(idleUpdates), "No repeated request");
var busyUpdates = System.Text.Json.Nodes.JsonNode.Parse("{\"checking\":true,\"installing\":false}")!.AsObject();
updates.Sync(busyUpdates);
updates.Request(true);
Assert(!updates.Sync(idleUpdates), "Check already in progress coalesces");
busyUpdates["checking"] = false;
busyUpdates["installing"] = true;
updates.Sync(busyUpdates);
updates.Request(true);
Assert(!updates.Sync(idleUpdates), "Installation excludes discovery");
var broker = new DesktopGrants(clock);
broker.SetReady(true);
Assert(broker.Authorize("snapshot") == "approval_required", "Off by default");
Assert(broker.Authorize("session.login") == "unsupported_operation", "No protected scope");
Refuses(() => broker.Arm(["protected"], 60), "Unsupported scope");
Refuses(() => broker.Arm(["observe"], 59), "Unbounded duration");
broker.Arm(["browser"], 60);
Assert(broker.Authorize("browser.tabs") is null, "Browser scope authorizes tabs");
Assert(broker.Authorize("browser.eval") == "approval_required", "Browser is not raw DevTools");
Assert(broker.Authorize("snapshot") == "approval_required", "Browser is not desktop observation");
broker.Stop("test");
broker.Arm(["devtools"], 60);
Assert(broker.Authorize("browser.eval") is null && broker.Authorize("browser.tabs") is null, "DevTools includes browser");
var browserPending = broker.RequestAsync(new Request { Operation = "grant.request", Scopes = ["control"], DurationSeconds = 60, Reason = "Other scope" }, "caller");
Assert(broker.Authorize("browser.eval") == "approval_prompt_visible" && broker.Authorize("browser.click") == "approval_prompt_visible", "Prompt pauses browser writes and raw evaluation");
Assert(broker.Authorize("browser.tabs") is null, "Prompt permits browser observation");
broker.Stop("test");
Assert((await browserPending).ErrorCode == "test", "Stop cancels browser prompt");
await using (var frame = new MemoryStream())
{
    await BrowserWire.WriteAsync(frame, new System.Text.Json.Nodes.JsonObject { ["type"] = "hello" }, CancellationToken.None);
    frame.Position = 0;
    Assert((await BrowserWire.ReadAsync(frame, CancellationToken.None))?["type"]?.GetValue<string>() == "hello", "Native framing round trip");
}
foreach (var length in new uint[] { 0, BrowserWire.MaximumInput + 1 })
{
    var header = new byte[4]; System.Buffers.Binary.BinaryPrimitives.WriteUInt32LittleEndian(header, length);
    await using var frame = new MemoryStream(header);
    try { await BrowserWire.ReadAsync(frame, CancellationToken.None); throw new Exception("Expected frame refusal"); }
    catch (InvalidDataException) { }
}
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
