using System.Text.Json;
using MachineControl.Windows;

if (args.Contains("--stdio-proxy-without-pool"))
{
    await RetainedPipeProxyFixtures.Child(args[^1]);
    return;
}
if (args.Contains("--stdio-proxy-contract"))
{
    await RetainedPipeProxyFixtures.RunAsync();
    return;
}
if (args.Contains("--async-ipc-without-pool"))
{
    BrowserDevToolsFixtures.AsyncWithoutPool();
    return;
}

if (args.Contains("--sync-ipc-without-pool"))
{
    BrowserDevToolsFixtures.SyncWithoutPool();
    return;
}

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
await RetainedPipeProxyFixtures.RunAsync();
JournalAclFixtures.Run();
var journalRoot = Path.Combine(Path.GetTempPath(), "mc-journal-" + Guid.NewGuid().ToString("n"));
try
{
    var journal = new DesktopJournal(journalRoot, segmentBytes: 1000, auditBytes: 5000);
    Assert(journal.Begin("input.text", "SENTINEL", callerPid: 123), "Durable intent");
    Assert(journal.Record(new Result { RequestId = "SENTINEL", Operation = "input.text", Accepted = true, Data = "SENTINEL", Message = "SENTINEL" }), "Durable result");
    journal.QueueAdmission(new System.Text.Json.Nodes.JsonObject
    { ["event"] = "approved", ["intentId"] = "PRIVATE-INTENT", ["sessionId"] = "PRIVATE-SESSION", ["reason"] = "PRIVATE-TASK", ["surface"] = "browser" });
    var auditDeadline = System.Diagnostics.Stopwatch.StartNew();
    while (!JsonSerializer.Serialize(journal.Preview(), Contract.Json).Contains("admission.approved"))
    { if (auditDeadline.Elapsed.TotalSeconds > 5) throw new Exception("Admission audit not drained"); await Task.Delay(10); }
    var admissionAudit = JsonSerializer.Serialize(journal.Preview(), Contract.Json);
    Assert(!admissionAudit.Contains("PRIVATE-"), "Admission audit hashes correlations and rejects arbitrary reason text");
    Assert(admissionAudit.Contains("surface.browser"), "Scoped admission event retained");
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
    var gated = TestBrowserProjection.Create(journal: unavailable); gated.SetReady(true);
    Refuses(() => gated.ConfigureSurface("desktop", "automatic", 60, "timed"), "Unlogged grant refused");
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
var broker = TestBrowserProjection.Create(clock);
broker.SetReady(true);
await SurfacePolicyFixtures.RunAsync();
foreach (var operation in BrowserWire.Operations.Where(value => value != "browser.profiles"))
    Assert(DesktopGrants.ScopeFor(operation) is not null, "Browser operation has a native capability mapping");
Assert(DesktopGrants.ScopeFor("browser.profiles") is null, "Profile metadata has no page-control capability");
foreach (var operation in BrowserWire.Operations) Assert(DesktopJournal.Known(operation), "Browser audit operation is typed");
Assert(BrowserWire.StreamEnd(new() { ["type"] = "session.closed", ["reason"] = "private page content" }) == "provider_closed", "Untrusted stream reason is not reflected");
Assert(Contract.ParseRequest("{\"operation\":\"browser.upload\",\"files\":[\"C:\\\\fixture.txt\"]}").Files?.Single() == @"C:\fixture.txt", "Upload file list survives request parsing");
Assert(BrowserUpload.Validate(null).ErrorCode == "invalid_request" && BrowserUpload.Validate([]).ErrorCode == "invalid_request", "Upload needs files");
Assert(BrowserUpload.Validate(Enumerable.Repeat(@"C:\fixture.txt", 21).ToArray()).ErrorCode == "invalid_request", "Upload file count bounded");
foreach (var invalidPath in new[] { "relative.txt", @"C:relative.txt", @"\fixture.txt", @"\\server\share\fixture.txt", @"\\?\C:\fixture.txt", @"C:\fixture.txt:secret" })
    Assert(BrowserUpload.Validate([invalidPath]).ErrorCode == "invalid_request", "Reject nonlocal/stream path");
if (OperatingSystem.IsWindows())
{
    var uploadRoot = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.CommonDocuments), "upload-contract-" + Guid.NewGuid().ToString("n"));
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
    frame.Position = 0;
    Assert(BrowserWire.Read(frame)?["type"]?.GetValue<string>() == "hello", "Dedicated reader accepts async framing");
    frame.SetLength(0);
    BrowserWire.Write(frame, new System.Text.Json.Nodes.JsonObject { ["type"] = "hello" });
    frame.Position = 0;
    Assert((await BrowserWire.ReadAsync(frame, CancellationToken.None))?["type"]?.GetValue<string>() == "hello", "Dedicated writer preserves framing");
}
foreach (var length in new uint[] { 0, BrowserWire.MaximumInput + 1 })
{
    var header = new byte[4]; System.Buffers.Binary.BinaryPrimitives.WriteUInt32LittleEndian(header, length);
    await using var frame = new MemoryStream(header);
    try { await BrowserWire.ReadAsync(frame, CancellationToken.None); throw new Exception("Expected frame refusal"); }
    catch (InvalidDataException) { }
    frame.Position = 0;
    try { BrowserWire.Read(frame); throw new Exception("Expected dedicated frame refusal"); }
    catch (InvalidDataException) { }
}
for (var i = 0; i < 150; i++) broker.Record(new Result { RequestId = "test", Operation = "invoke", Accepted = false });
Assert(State(broker).GetProperty("activity").GetArrayLength() == 30, "Bounded activity projection");
await AdmissionChannelFixtures.RunAsync();
DesktopActivityFixtures.Run();
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
var fencedBroker = TestBrowserProjection.Create();
fencedBroker.SetReady(true); fencedBroker.ConfigureSurface("desktop", "automatic", 300, "timed");
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
fencedBroker.ConfigureSurface("desktop", "automatic", 300, "timed");
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
