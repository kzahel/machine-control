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
var journalRoot = Path.Combine(Path.GetTempPath(), "mc-journal-" + Guid.NewGuid().ToString("n"));
try
{
    var journal = new DesktopJournal(journalRoot, segmentBytes: 1000, auditBytes: 5000);
    Assert(journal.Begin("input.text", "SENTINEL", callerPid: 123), "Durable intent");
    Assert(journal.Record(new Result { RequestId = "SENTINEL", Operation = "input.text", Accepted = true, Data = "SENTINEL", Message = "SENTINEL" }), "Durable result");
    var recovered = new DesktopJournal(journalRoot);
    var preview = JsonSerializer.Serialize(recovered.Preview(), Contract.Json);
    Assert(!preview.Contains("SENTINEL"), "Payload and raw request ID excluded");
    Assert(preview.Contains("\"callerPid\":123"), "Observed caller PID retained");
    Assert(preview.Contains("input.text") && preview.Contains("outcome_pending"), "Restart retains intent and result");
    Assert(File.Exists(recovered.Export()), "Private export");
    recovered.Debug(true);
    Assert(JsonSerializer.Serialize(recovered.Health, Contract.Json).Contains("debugRemainingSeconds"), "Bounded debug mode");
    var latest = Directory.GetFiles(Path.Combine(journalRoot, "audit")).OrderDescending().First();
    File.AppendAllText(latest, "{}\n42\n{partial");
    _ = recovered.Query();
    Assert(JsonSerializer.Serialize(recovered.Health, Contract.Json).Contains("\"historyGap\":true"), "Partial record detected");
    var invalid = Path.Combine(journalRoot, "audit", "00000000000000000000-invalid.jsonl");
    File.WriteAllText(invalid, "42\n");
    Assert(!JsonSerializer.SerializeToElement(recovered.Query(), Contract.Json).TryGetProperty("earliestAt", out var earliest) || earliest.ValueKind == JsonValueKind.Null, "Invalid earliest row tolerated");
    File.Delete(invalid);
    for (var i = 0; i < 100; i++) Assert(journal.Begin("input.key", i.ToString()), "Rotated append");
    Assert(Directory.GetFiles(Path.Combine(journalRoot, "audit")).Sum(p => new FileInfo(p).Length) <= 5000, "Retention cap");
    var paged = new DesktopJournal(Path.Combine(journalRoot, "pages"));
    for (var i = 0; i < 60; i++) paged.Record(new Result { RequestId = i.ToString(), Operation = "input.key", Accepted = i % 2 == 0 });
    var firstPage = JsonSerializer.SerializeToElement(paged.Query(operation: "input.key"), Contract.Json);
    var secondPage = JsonSerializer.SerializeToElement(paged.Query(offset: 50, operation: "input.key"), Contract.Json);
    Assert(firstPage.GetProperty("entries").GetArrayLength() == 50 && firstPage.GetProperty("hasMore").GetBoolean(), "First history page");
    Assert(secondPage.GetProperty("entries").GetArrayLength() == 10 && !secondPage.GetProperty("hasMore").GetBoolean(), "Last history page");
    Assert(JsonSerializer.SerializeToElement(paged.Query(operation: "input.key", outcome: "accepted"), Contract.Json).GetProperty("entries").GetArrayLength() == 30, "Outcome filter");
    var expired = Path.Combine(paged.Root, "audit", "00000000000000000000-expired.jsonl");
    File.WriteAllText(expired, "{}\n"); File.SetLastWriteTimeUtc(expired, DateTime.UtcNow.AddDays(-31));
    paged.Event("storage.recovered"); Assert(!File.Exists(expired), "Age retention");
    var blocked = Path.Combine(journalRoot, "blocked"); File.WriteAllText(blocked, "");
    var unavailable = new DesktopJournal(blocked);
    Assert(!unavailable.Begin("click", "x"), "Unavailable storage refuses intent");
    var gated = new DesktopGrants(journal: unavailable); gated.SetReady(true);
    Refuses(() => gated.Arm(["control"], 60), "Unlogged grant refused");
    gated.Stop("stopped_by_person");
    Assert(!State(gated).GetProperty("deployment").TryGetProperty("grant", out _) || State(gated).GetProperty("deployment").GetProperty("grant").ValueKind == JsonValueKind.Null, "Stop works without logging");
}
finally { if (Directory.Exists(journalRoot)) Directory.Delete(journalRoot, true); }
var clock = new TestTime();
var consent = new Request { Operation = "uac.respond", State = "approve" };
Assert(DesktopUacPolicy.Refusal(consent, false, true, "Winlogon", true) == "uac_access_disabled", "UAC opt-in required");
Assert(DesktopUacPolicy.Refusal(consent, true, false, "Winlogon", true) == "desktop_unavailable", "Locked console refused");
Assert(DesktopUacPolicy.Refusal(consent, true, true, "Winlogon", false) == "uac_prompt_unavailable", "Winlogon alone is not UAC");
Assert(DesktopUacPolicy.Refusal(consent, true, true, "unknown", true) == "uac_prompt_unavailable", "Unknown desktop refused");
Assert(DesktopUacPolicy.Refusal(consent, true, true, "Default", true) == "uac_prompt_unavailable", "No approval on ordinary desktop");
Assert(DesktopUacPolicy.Refusal(consent, true, true, "Winlogon", true) is null, "Typed UAC approval");
Assert(DesktopUacPolicy.Refusal(consent with { State = "cancel" }, true, true, "Winlogon", true) is null, "Typed UAC cancellation");
Assert(DesktopGrants.ScopeFor("uac.respond") == "control", "UAC response needs control scope");
foreach (var forbidden in new[] { "app.launch", "app.activate", "session.login", "session.lock", "service.revoke", "runtime.stop", "browser.eval" })
    Assert(DesktopUacPolicy.Refusal(consent with { Operation = forbidden }, true, true, "Default", true) == "protected_operation_refused", "Closed privileged surface: " + forbidden);
foreach (var forbidden in new[] { "invoke", "click", "key", "type", "set.value", "window.state" })
    Assert(DesktopUacPolicy.Refusal(consent with { Operation = forbidden }, true, true, "Winlogon", true) == "secure_desktop_operation_refused", "Secure input is typed: " + forbidden);
Assert(DesktopUacPolicy.Refusal(consent with { Text = "secret" }, true, true, "Winlogon", true) == "invalid_uac_response", "No secret in UAC response");
Assert(DesktopUacPolicy.Refusal(consent with { SecretPipe = "secret" }, true, true, "Winlogon", true) == "protected_operation_refused", "No credential transport");
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
Assert(State(broker).GetProperty("manualUntilStoppedSupported").GetBoolean(), "Indefinite manual access advertised");
Refuses(() => broker.Arm(["observe"], 60, "unknown"), "Unknown lifetime");
Refuses(() => broker.Arm(["observe"], 0), "Zero is not implicitly indefinite");
Refuses(() => broker.Arm(["protected"], 0, "until_stopped"), "Indefinite grant retains scope validation");
broker.Arm(["observe"], 0, "until_stopped");
clock.Advance(60 * 60 * 24 * 365);
var indefinite = State(broker).GetProperty("deployment").GetProperty("grant");
Assert(indefinite.GetProperty("lifetime").GetString() == "until_stopped" &&
    indefinite.GetProperty("remainingSeconds").ValueKind == JsonValueKind.Null, "Explicit lifetime and null countdown");
Assert(broker.Authorize("snapshot") is null && broker.AdmissionAuthority(["observe"]) is null, "No expiry in dispatch or admission");
Assert(broker.Authorize("invoke") == "approval_required", "Indefinite grant preserves scopes");
Refuses(broker.PrepareUpdate, "Indefinite access blocks replacement");
var indefiniteGeneration = broker.Generation;
broker.Pause(); clock.Advance(60 * 60 * 24 * 365);
Assert(broker.Authorize("snapshot") == "access_paused", "Indefinite access obeys pause");
broker.Resume();
Assert(broker.Authorize("snapshot") is null, "Resume retains indefinite access");
Assert(broker.Authorize("snapshot", indefiniteGeneration) == "stale_generation", "Pause fences indefinite references");
broker.SetReady(false);
Assert(broker.Authorize("snapshot") == "desktop_unavailable", "Indefinite access obeys availability");
broker.SetReady(true);
Assert(broker.Authorize("snapshot") is null, "Availability recovery retains existing Windows semantics");
Refuses(() => broker.RequestAsync(new Request { Operation = "grant.request", Scopes = ["observe"], DurationSeconds = 0, Reason = "No public indefinite grant" }, "caller"), "Public duration still bounded even with coverage");
var indefinitePending = broker.RequestAsync(new Request { Operation = "grant.request", Scopes = ["control"], DurationSeconds = 60, Reason = "Timed approval" }, "caller");
Refuses(() => broker.Arm(["observe"], 0, "until_stopped"), "Pending approval blocks indefinite arm");
Refuses(() => broker.Decide(Pending(broker), true, ["control"], 0), "Approval cannot issue indefinite grant");
broker.Decide(Pending(broker), true, ["control"], 60);
Assert((await indefinitePending).Accepted, "Bounded approval replaces indefinite grant");
clock.Advance(60);
Assert(broker.AdmissionAuthority(["control"]) == "expired", "Timed admission expiry retained");
Assert(broker.Authorize("invoke") == "approval_required", "Timed replacement expires");
broker.Arm(["observe"], 0, "until_stopped");
indefiniteGeneration = broker.Generation;
broker.Stop("stopped_by_person");
Assert(broker.Authorize("snapshot", indefiniteGeneration) == "stale_generation", "Stop fences indefinite references");
Assert(broker.AdmissionAuthority(["observe"]) == "approval_required", "Stop revokes indefinite admission");
broker.PrepareUpdate();
Refuses(() => broker.Arm(["observe"], 0, "until_stopped"), "Update blocks indefinite arming");
broker.CancelUpdate();
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
Assert(broker.Authorize("invoke") == "desktop_unavailable", "Unavailable desktop refuses use");
broker.SetReady(true);
Assert(broker.Authorize("invoke") is null && broker.Generation != original, "Lock pauses availability and fences old references without revoking authorization");
original = broker.Generation;
broker.Pause();
Assert(broker.Authorize("snapshot") == "access_paused" && broker.Authorize("invoke") == "access_paused", "Pause gates observation and action");
foreach (var operation in new[] { "key.timeline", "key.delayed_hold" })
{
    Assert(DesktopGrants.ScopeFor(operation) == "control", "Key timing requires control scope");
    Assert(broker.Authorize(operation) == "access_paused", "Pause gates key timing");
    var timing = new DesktopGrants(new TestTime());
    timing.SetReady(true);
    Assert(timing.Authorize(operation) == "approval_required", "Key timing is off by default");
    timing.Arm(["observe"], 60);
    Assert(timing.Authorize(operation) == "approval_required", "Observation does not allow key timing");
    timing.Arm(["control"], 60);
    var timingGeneration = timing.Generation;
    Assert(timing.Authorize(operation, timingGeneration) is null, "Control scope permits key timing");
    timing.Stop("test");
    Assert(timing.Authorize(operation, timingGeneration) == "stale_generation", "Stop fences key timing references");
    Assert(timing.Authorize(operation) == "approval_required", "Stop revokes key timing access");
}
Assert(broker.Generation != original && State(broker).GetProperty("deployment").GetProperty("grant").ValueKind == JsonValueKind.Object, "Pause preserves grant and fences references");
broker.Admission.Pause("desktop", "safety_fault"); broker.Resume();
Assert(broker.Authorize("invoke") == "access_paused", "Resume leaves independent safety block");
broker.Admission.Resume("desktop", "safety_fault");
Assert(broker.Authorize("invoke") is null, "No fresh permission after ordinary pause");
broker.Pause(1); clock.Advance(1);
Assert(broker.Authorize("invoke") is null, "Timed pause expires");
broker.Pause(); clock.Advance(300);
Assert(broker.Authorize("invoke") == "access_paused", "Expired authorization cannot bypass pause");
broker.Resume();
Assert(broker.Authorize("invoke") == "approval_required", "Grant clock ran while paused");
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
await AdmissionChannelFixtures.RunAsync();
Console.WriteLine("Windows desktop grant contracts passed");

sealed class TestTime : TimeProvider
{
    private long _seconds;
    public override long TimestampFrequency => 1;
    public override long GetTimestamp() => _seconds;
    public override DateTimeOffset GetUtcNow() => DateTimeOffset.UnixEpoch.AddSeconds(_seconds);
    public void Advance(int seconds) => _seconds += seconds;
}
