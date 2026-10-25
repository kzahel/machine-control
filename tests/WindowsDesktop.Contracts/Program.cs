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
    paged.Diagnostic("fixture", "failed");
    foreach (var days in new[] { 8, 31 })
    {
        var diagnostic = Path.Combine(paged.Root, "diagnostics", $"00000000000000000000-{days}.jsonl");
        File.WriteAllText(diagnostic, "{}\n"); File.SetLastWriteTimeUtc(diagnostic, DateTime.UtcNow.AddDays(-days));
    }
    paged.Diagnostic("fixture", "failed");
    Assert(File.Exists(Path.Combine(paged.Root, "diagnostics", "00000000000000000000-8.jsonl")), "Previous-week diagnostics retained");
    Assert(!File.Exists(Path.Combine(paged.Root, "diagnostics", "00000000000000000000-31.jsonl")), "Diagnostic age cap");
    Assert(JsonSerializer.SerializeToElement(paged.Health, Contract.Json).GetProperty("diagnosticDays").GetInt32() == 30, "Thirty-day diagnostics");
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
foreach (var forbidden in new[] { "invoke", "click", "move", "drag", "scroll", "key", "type", "set.value", "window.state" })
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
var lockedBrowser = new DesktopGrants(clock);
lockedBrowser.SetReady(true, consoleIdentity: "logon-one");
lockedBrowser.ConfigureBrowserWhileLocked(true);
Assert(lockedBrowser.Authorize("browser.tabs") == "approval_required", "Browser lock preference grants no access");
lockedBrowser.Arm(["observe", "control", "browser"], 300);
var lockedGrantId = JsonSerializer.SerializeToElement(lockedBrowser.DeploymentState()).GetProperty("grant").GetProperty("grantId").GetString();
lockedBrowser.SetReady(false, true, "logon-one");
Assert(lockedBrowser.BrowserOnlyWhileLocked && lockedBrowser.ReadyForScopes(["browser"]), "Same locked logon supports browser owners");
Assert(lockedBrowser.Authorize("browser.tabs", controlled: true) is null, "Locked browser operation allowed");
Assert(lockedBrowser.Authorize("snapshot", controlled: true) == "desktop_locked_browser_only", "Mixed grant cannot observe locked desktop");
Assert(lockedBrowser.Authorize("browser.eval", controlled: true) == "approval_required", "DevTools remains separate");
Assert(lockedBrowser.AdmissionAuthority(["control"]) == "desktop_locked_browser_only", "Desktop admission fenced while locked");
Assert(JsonSerializer.SerializeToElement(lockedBrowser.DeploymentState()).GetProperty("grant").GetProperty("grantId").GetString() == lockedGrantId, "Lock preserves grant identity");
Assert((await lockedBrowser.RequestAsync(new Request { Operation = "grant.request", Scopes = ["browser"], Reason = "reuse" }, "fixture")).Accepted, "Covered browser approval reused while locked");
Assert((await lockedBrowser.RequestAsync(new Request { Operation = "grant.request", Scopes = ["control"], Reason = "expand" }, "fixture")).ErrorCode == "approval_unavailable_while_locked", "New locked approval refused");
lockedBrowser.Pause();
Assert(lockedBrowser.Authorize("browser.tabs", controlled: true) == "access_paused", "Locked browser honors Pause");
lockedBrowser.Resume();
Assert(lockedBrowser.Authorize("browser.tabs", controlled: true) is null, "Locked browser resumes same approval");
lockedBrowser.ConfigureBrowserWhileLocked(false);
Assert(lockedBrowser.Authorize("browser.tabs", controlled: true) == "desktop_unavailable", "Disable ends retained access");
lockedBrowser.SetReady(true, consoleIdentity: "logon-one");
lockedBrowser.ConfigureBrowserWhileLocked(true);
lockedBrowser.Arm(["browser", "devtools"], 60);
lockedBrowser.SetReady(false, true, "logon-one");
Assert(lockedBrowser.Authorize("browser.eval", controlled: true) is null, "Approved DevTools works while locked");
clock.Advance(61);
Assert(lockedBrowser.Authorize("browser.eval", controlled: true) is not null, "Locked browser expiry enforced");
lockedBrowser.SetReady(true, consoleIdentity: "logon-one");
lockedBrowser.Arm(["browser"], 300);
lockedBrowser.SetReady(false, true, "replacement-logon");
Assert(!lockedBrowser.BrowserOnlyWhileLocked && lockedBrowser.AdmissionAuthority(["browser"]) == "approval_required", "Replacement logon loses authority");
lockedBrowser.SetReady(true, consoleIdentity: "logon-one");
lockedBrowser.Arm(["browser"], 300);
lockedBrowser.SetReady(false, false, null);
Assert(lockedBrowser.AdmissionAuthority(["browser"]) == "approval_required", "Unknown session loses authority");
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
var retained = new DesktopGrants(clock);
retained.SetReady(true);
retained.Arm(["observe"], 0, "until_stopped");
Assert(retained.RevokeFromCaller() == (false, true), "Caller revoke retains person-armed access");
Assert(retained.Authorize("snapshot") is null, "Person access survives caller revoke");
Assert(State(retained).GetProperty("deployment").GetProperty("grant").GetProperty("origin").GetString() == "person",
    "Grant reports person origin");
async Task ApproveControl(DesktopGrants grants, int seconds)
{
    var reply = grants.RequestAsync(new Request { Operation = "grant.request", Scopes = ["control"], DurationSeconds = seconds, Reason = "Broader agent access" }, "caller");
    grants.Decide(Pending(grants), true, ["control"], seconds);
    Assert((await reply).Accepted, "Broader request approved");
}
await ApproveControl(retained, 60);
Assert(State(retained).GetProperty("deployment").GetProperty("grant").GetProperty("origin").GetString() == "request",
    "Approved request replaces person access");
Assert(retained.RevokeFromCaller() == (true, false), "Caller ends its own request grant");
Assert(retained.Authorize("snapshot") is null && retained.Authorize("invoke") == "approval_required",
    "Person access returns after caller revoke");
await ApproveControl(retained, 60);
clock.Advance(61);
Assert(retained.Authorize("snapshot") is null && retained.Authorize("invoke") == "approval_required",
    "Person access returns after request expiry");
await ApproveControl(retained, 60);
retained.Stop("stopped_by_person");
Assert(retained.Authorize("snapshot") == "approval_required", "Person Stop clears replaced access");
Assert(retained.RevokeFromCaller() == (false, false), "Nothing left to revoke");
var lapsed = new DesktopGrants(clock);
lapsed.SetReady(true);
lapsed.Arm(["observe"], 60);
await ApproveControl(lapsed, 120);
clock.Advance(121);
Assert(lapsed.Authorize("snapshot") == "approval_required", "Expired person access is not restored");
Assert(broker.Authorize("session.login") == "unsupported_operation", "No protected scope");
Refuses(() => broker.Arm(["protected"], 60), "Unsupported scope");
Refuses(() => broker.Arm(["observe"], 59), "Unbounded duration");
broker.Arm(["browser"], 60);
Assert(broker.Authorize("browser.tabs") is null, "Browser scope authorizes tabs");
Assert(broker.Authorize("browser.eval") == "approval_required", "Browser is not raw DevTools");
Assert(broker.Authorize("snapshot") == "approval_required", "Browser is not desktop observation");
Assert(BrowserWire.Operations.Contains("browser.upload") && !BrowserWire.Observes("browser.upload"), "Upload is an advertised browser mutation");
Assert(DesktopGrants.ScopeFor("browser.dialog") == "browser" && broker.Authorize("browser.dialog") is null,
    "Typed dialog handling uses the browser grant");
foreach (var operation in BrowserWire.Operations)
    Assert(DesktopGrants.ScopeFor(operation) is not null, "Every advertised browser operation has a control-session scope: " + operation);
Assert(broker.Authorize("browser.upload") is null, "Browser scope permits upload without DevTools");
Assert(broker.Authorize(new Request { Operation = "browser.upload" }) == "control_session_required", "Upload requires live ownership");
Assert(broker.Authorize(new Request { Operation = "browser.dialog" }) == "control_session_required", "Typed dialogs require live ownership");
broker.Stop("test");
broker.Arm(["devtools"], 60);
Assert(broker.Authorize("browser.eval") is null && broker.Authorize("browser.tabs") is null, "DevTools includes browser");
var browserPending = broker.RequestAsync(new Request { Operation = "grant.request", Scopes = ["control"], DurationSeconds = 60, Reason = "Other scope" }, "caller");
Assert(broker.Authorize("browser.eval") == "approval_prompt_visible" && broker.Authorize("browser.click") == "approval_prompt_visible", "Prompt pauses browser writes and raw evaluation");
Assert(broker.Authorize("browser.tabs") is null, "Prompt permits browser observation");
Assert(broker.Authorize("browser.upload") == "approval_prompt_visible", "Prompt fences uploads");
broker.Stop("test");
Assert(broker.Authorize("browser.upload") == "approval_required", "Stop revokes uploads");
Assert(broker.Authorize("browser.dialog") == "approval_required", "Stop revokes typed dialogs");
Assert((await browserPending).ErrorCode == "test", "Stop cancels browser prompt");
Assert(Contract.ParseRequest("{\"operation\":\"browser.upload\",\"files\":[\"C:\\\\fixture.txt\"]}").Files?.Single() == @"C:\fixture.txt", "Upload file list survives request parsing");
Assert(BrowserUpload.Validate(null).ErrorCode == "invalid_request" && BrowserUpload.Validate([]).ErrorCode == "invalid_request", "Upload needs files");
Assert(BrowserUpload.Validate(Enumerable.Repeat(@"C:\fixture.txt", 21).ToArray()).ErrorCode == "invalid_request", "Upload file count bounded");
foreach (var invalidPath in new[] { "relative.txt", @"C:relative.txt", @"\fixture.txt", @"\\server\share\fixture.txt", @"\\?\C:\fixture.txt", @"C:\fixture.txt:secret" })
    Assert(BrowserUpload.Validate([invalidPath]).ErrorCode == "invalid_request", "Reject nonlocal/stream path");
if (OperatingSystem.IsWindows())
{
    var uploadRoot = Path.Combine(Environment.CurrentDirectory, "upload-contract-" + Guid.NewGuid().ToString("n"));
    Directory.CreateDirectory(uploadRoot);
    try
    {
        var file = Path.Combine(uploadRoot, "space résumé.txt");
        File.WriteAllText(file, "independent file bytes");
        Assert(BrowserUpload.Validate([file]).Files?.Single() == file, "Readable Unicode local file accepted");
        Assert(BrowserUpload.Validate([uploadRoot]).ErrorCode == "upload_file_unavailable", "Directory refused");
        Assert(BrowserUpload.Validate([Path.Combine(uploadRoot, "missing.txt")]).ErrorCode == "upload_file_unavailable", "Missing file refused");
        foreach (var folder in new[] { ".private", "AppData" })
        {
            var privateFile = Path.Combine(uploadRoot, folder, "private.txt");
            Directory.CreateDirectory(Path.GetDirectoryName(privateFile)!);
            File.WriteAllText(privateFile, "fixture");
            Assert(BrowserUpload.Validate([privateFile]).ErrorCode == "upload_path_not_permitted", "Private folder refused");
        }
        File.SetAttributes(file, FileAttributes.Hidden);
        Assert(BrowserUpload.Validate([file]).ErrorCode == "upload_path_not_permitted", "Hidden file refused");
        File.SetAttributes(file, FileAttributes.Normal);
        using (File.Open(file, FileMode.Open, FileAccess.ReadWrite, FileShare.None))
            Assert(BrowserUpload.Validate([file]).ErrorCode == "upload_file_unavailable", "Unreadable/locked file refused");
        Assert(BrowserUpload.Validate([file, Path.Combine(uploadRoot, "missing.txt")]).Files is null, "Failed batch forwards no files");
        var link = Path.Combine(uploadRoot, "link.txt");
        try
        {
            File.CreateSymbolicLink(link, file);
            Assert(BrowserUpload.Validate([link]).ErrorCode == "upload_path_not_permitted", "Reparse file refused");
        }
        catch (UnauthorizedAccessException) { Console.WriteLine("File symlink fixture unavailable without OS permission"); }
        catch (IOException ex) when ((ex.HResult & 0xffff) == 1314) { Console.WriteLine("File symlink fixture unavailable without OS privilege"); }
        finally { if (File.Exists(link)) File.Delete(link); }
    }
    finally { Directory.Delete(uploadRoot, true); }
}
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
DesktopActivityFixtures.Run();
var independentDesktop = new DesktopGrants(new TestTime());
independentDesktop.SetReady(true, consoleIdentity: "same-logon");
independentDesktop.ConfigureBrowserWhileLocked(true);
independentDesktop.PrepareConsole(true);
independentDesktop.Arm(["observe", "control"], 300);
independentDesktop.SetReady(false, false, "same-logon");
Assert(independentDesktop.AdmissionAuthority(["control"]) is null, "Browser preference cannot revoke a desktop-only approval during a lock transition");
Assert(independentDesktop.Authorize("snapshot", controlled: true) == "desktop_unavailable", "Unavailable desktop still refuses ordinary effects");
independentDesktop.SetReady(false, true, "same-logon");
Assert(independentDesktop.Authorize("session.unlock", controlled: true) is null, "Stable locked desktop permits its enrolled operation independently of browser preference");
var preparedGrant = new DesktopGrants(new TestTime());
preparedGrant.SetReady(true);
preparedGrant.Arm(["observe", "control"], 300);
var oldAuthorization = preparedGrant.AuthorizationRevision;
preparedGrant.PrepareConsole(true);
Assert(preparedGrant.AuthorizationRevision > oldAuthorization && preparedGrant.AdmissionAuthority(["control"]) == "approval_required", "Protected preference changes revoke ordinary consent");
preparedGrant.Arm(["observe", "control"], 300);
preparedGrant.SetReady(false, lockedConsole: true);
Assert(preparedGrant.Admission.Blocks("desktop").Length == 0, "Explicit preparation makes the locked console reservable");
Assert(preparedGrant.Authorize("snapshot", controlled: true) == "desktop_unavailable", "Prepared ownership never permits ordinary locked-screen dispatch");
Assert(preparedGrant.Authorize("session.unlock.prepare", controlled: true) is null, "Control consent permits typed unlock preparation");
Assert(preparedGrant.Authorize("session.unlock.prepare") == "desktop_unavailable", "Preparation requires an owned channel");
preparedGrant.Pause(null);
Assert(preparedGrant.Authorize("session.unlock.prepare", controlled: true) == "access_paused", "Pause refuses before credential preparation");
preparedGrant.Resume();
preparedGrant.Stop("fixture_stop");
Assert(preparedGrant.Authorize("session.unlock.prepare", controlled: true) == "approval_required", "Stop invalidates protected authority");
preparedGrant.SetReady(true);
preparedGrant.Arm(["observe"], 300);
preparedGrant.SetReady(false, lockedConsole: true);
Assert(preparedGrant.Authorize("session.unlock.prepare", controlled: true) == "approval_required", "Observe-only access cannot prepare a credential operation");
preparedGrant.SetReady(false, lockedConsole: false);
Assert(preparedGrant.Admission.Blocks("desktop").Contains("resource_unavailable"), "Unknown or foreign console cannot reserve protected control");
preparedGrant.PrepareConsole(false);
preparedGrant.SetReady(false, lockedConsole: true);
Assert(preparedGrant.Admission.Blocks("desktop").Contains("resource_unavailable"), "Disabled preparation never makes lock available");
await BrowserDevToolsFixtures.RunAsync();
Console.WriteLine("Windows desktop grant contracts passed");

foreach (var operation in new[] { "move", "drag", "scroll" })
{
    Assert(DesktopGrants.ScopeFor(operation) == "control", "Pointer control scope: " + operation);
    Assert(DesktopUacPolicy.Refusal(new Request { Operation = operation }, true, true, "Default", false) is null, "Native elevated pointer surface: " + operation);
}
Assert(PointerGeometry.Intersects(-100, 20, 100, 20, -10, 0, 10, 40), "Drag crossing protected rectangle with safe endpoints");
Assert(!PointerGeometry.Intersects(-100, 50, 100, 50, -10, 0, 10, 40), "Parallel drag outside protected rectangle");
Assert(PointerGeometry.Intersects(0, -100, 0, 100, -10, -10, 10, 10), "Vertical protected crossing");
Assert(PointerGeometry.Intersects(5, 5, 5, 5, 0, 0, 10, 10), "Protected stationary point");
Assert(!PointerGeometry.Intersects(10, 5, 10, 5, 0, 0, 10, 10), "Stationary point outside exclusive right edge");
Assert(PointerGeometry.Intersects(int.MinValue, int.MinValue, int.MaxValue, int.MaxValue, -10, -10, 10, 10), "No overflow in hostile coordinates");
Assert(DesktopUacPolicy.Refusal(consent with { X2 = 1 }, true, true, "Winlogon", true) == "invalid_uac_response", "Pointer fields cannot widen typed UAC response");


// A physical dependency remains occupied after caller timeout or Stop.
var work = new DesktopWork();
var dependency = new TaskCompletionSource(TaskCreationOptions.RunContinuationsAsynchronously);
var entered = new TaskCompletionSource(TaskCreationOptions.RunContinuationsAsynchronously);
var fencedBroker = new DesktopGrants();
fencedBroker.SetReady(true); fencedBroker.Arm(["control"], 300);
var oldGeneration = fencedBroker.Generation;
var effects = 0;
var faultRequest = new Request { Operation = "invoke", RequestId = "fault" };
var blockedWork = work.RunAsync(faultRequest, oldGeneration, async token =>
{
    entered.SetResult();
    await dependency.Task; // A native dependency ignores cancellation.
    var refusal = fencedBroker.Authorize("invoke", oldGeneration);
    if (refusal is null && !token.IsCancellationRequested) Interlocked.Increment(ref effects);
    return new Result { RequestId = "fault", Operation = "invoke", ErrorCode = refusal };
}, CancellationToken.None, TimeSpan.FromMilliseconds(100));
await entered.Task;
var stopTimer = System.Diagnostics.Stopwatch.StartNew();
fencedBroker.Stop("stopped_by_person");
Assert(stopTimer.ElapsedMilliseconds < 250, "Stop independent of blocked provider");
fencedBroker.Arm(["control"], 300);
Assert((await blockedWork).ErrorCode == "native_provider_timeout", "Caller deadline completes");
for (var i = 0; i < 1000; i++)
    Assert((await work.RunAsync(faultRequest, fencedBroker.Generation, _ => throw new Exception("Busy work dispatched"), CancellationToken.None)).ErrorCode == "native_provider_busy", "No queue or new worker after timeout");
dependency.SetResult();
Result recoveredWork;
var recoveryTimer = System.Diagnostics.Stopwatch.StartNew();
do
{
    recoveredWork = await work.RunAsync(faultRequest, fencedBroker.Generation, _ => Task.FromResult(new Result { RequestId = "recovery", Operation = "invoke", Accepted = true }), CancellationToken.None);
    if (!recoveredWork.Accepted) await Task.Delay(1);
} while (!recoveredWork.Accepted && recoveryTimer.Elapsed < TimeSpan.FromSeconds(2));
Assert(recoveredWork.Accepted && effects == 0, "Capacity recovers and late work cannot adopt replacement grant");
using (var cancelled = new CancellationTokenSource())
{
    cancelled.Cancel();
    Assert((await work.RunAsync(faultRequest, fencedBroker.Generation, _ => throw new Exception("Cancelled work dispatched"), cancelled.Token)).ErrorCode == "operation_cancelled", "Cancellation before admission has no effect");
}
Console.WriteLine("Windows bounded worker, Stop, deadline and late-authority contracts passed");

var preferenceDirectory = Path.Combine(Path.GetTempPath(), "presentation-contract-" + Guid.NewGuid().ToString("n"));
Directory.CreateDirectory(preferenceDirectory);
try
{
    var browserFile = Path.Combine(preferenceDirectory, "browser.json");
    var browserPreference = new DesktopBrowserPreference(browserFile);
    Assert(!browserPreference.Enabled, "Missing browser preference defaults off");
    browserPreference.Set(true);
    Assert(new DesktopBrowserPreference(browserFile).Enabled, "Browser preference persists without granting authority");
    Assert(!new DesktopBrowserPreference(browserFile, "machine-control-covered-desktop/v1").Enabled,
        "Browser preference cannot enable covered desktop access");
    browserPreference.Set(false);
    Assert(!new DesktopBrowserPreference(browserFile).Enabled, "Browser preference disable persists");
    foreach (var invalid in new[] { "{", "{}", "{\"schema\":\"wrong\",\"enabled\":true}", "{\"schema\":\"machine-control-browser-locked/v1\",\"enabled\":1}", new string('x', 1025) })
    {
        File.WriteAllText(browserFile, invalid);
        Assert(!new DesktopBrowserPreference(browserFile).Enabled, "Invalid browser preference defaults off");
    }
    var preferenceFile = Path.Combine(preferenceDirectory, "profile.json");
    JsonElement Profile(object value) => JsonSerializer.SerializeToElement(value);
    var preferences = new DesktopPresentation(preferenceFile);
    Assert(Profile(preferences.Status()).GetProperty("profile").GetString() == "personal", "Missing preferences default personal");
    foreach (var profile in DesktopPresentation.Profiles)
    {
        preferences.Set(profile);
        Assert(Profile(new DesktopPresentation(preferenceFile).Status()).GetProperty("profile").GetString() == profile, "Persistent profile round trip");
    }
    var temporary = new DesktopPresentation(preferenceFile, "minimal");
    Assert(Profile(temporary.Status()).GetProperty("savedProfile").GetString() == "appliance", "Override does not write preferences");
    temporary.Set("personal");
    Assert(!Profile(temporary.Status()).GetProperty("temporaryOverride").GetBoolean(), "Explicit configuration clears override");
    foreach (var invalid in new[] { "{", "{}", "{\"schema\":\"wrong\",\"profile\":\"minimal\"}", "{\"schema\":\"machine-control-presentation/v1\",\"profile\":\"root\"}", new string('x', 4097) })
    {
        File.WriteAllText(preferenceFile, invalid);
        Assert(Profile(preferences.Status()).GetProperty("diagnostic").GetString() == "presentation_preference_invalid", "Corrupt preference safely diagnosed");
    }
    preferences.Set("minimal");
    File.WriteAllText(Path.Combine(preferenceDirectory, ".presentation-interrupted"), "{");
    Assert(Profile(preferences.Status()).GetProperty("profile").GetString() == "minimal", "Interrupted replacement leaves committed preference intact");
    using (var exclusion = new FileStream(Path.Combine(preferenceDirectory, "write.lock"), FileMode.OpenOrCreate, FileAccess.ReadWrite, FileShare.None))
    {
        var refused = false;
        try { preferences.Set("appliance"); } catch (IOException) { refused = true; }
        Assert(refused && Profile(preferences.Status()).GetProperty("profile").GetString() == "minimal", "Concurrent edit refuses without partial write");
    }
    var rejected = false;
    try { preferences.Set("invalid"); } catch (ArgumentException) { rejected = true; }
    Assert(rejected, "Unknown profile is never persisted");
}
finally { Directory.Delete(preferenceDirectory, recursive: true); }
Console.WriteLine("Windows presentation persistence, override and recovery contracts passed");

sealed class TestTime : TimeProvider
{
    private long _seconds;
    public override long TimestampFrequency => 1;
    public override long GetTimestamp() => _seconds;
    public override DateTimeOffset GetUtcNow() => DateTimeOffset.UnixEpoch.AddSeconds(_seconds);
    public void Advance(int seconds) => _seconds += seconds;
}
