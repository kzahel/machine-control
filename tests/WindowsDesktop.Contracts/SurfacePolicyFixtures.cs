using System.Text.Json;
using System.Text.Json.Nodes;
using MachineControl.Windows;

internal static class SurfacePolicyFixtures
{
    internal static async Task RunAsync()
    {
        var optionsRoot = Path.Combine(Path.GetTempPath(), "mc-access-preferences-" + Guid.NewGuid().ToString("n"));
        Directory.CreateDirectory(optionsRoot);
        try
        {
            var optionsPath = Path.Combine(optionsRoot, "options.json");
            var store = new DesktopAccessPreferences(optionsPath);
            Require(store.Read() is null, "Missing preferences do not grant access");
            store.Set(new JsonObject { ["desktopNoticeSeconds"] = 0, ["browserNoticeSeconds"] = 30, ["yieldWaitSeconds"] = 10, ["yieldReapprove"] = true });
            var loaded = new DesktopAccessPreferences(optionsPath).Read();
            Require(loaded?["yieldReapprove"]?.GetValue<bool>() == true && loaded["desktopNoticeSeconds"]?.GetValue<int>() == 0, "Restart retains operator return-approval and immediate-start choices");
            Require(!File.ReadAllText(optionsPath).Contains("grant"), "Preferences contain no grant");
        }
        finally { Directory.Delete(optionsRoot, recursive: true); }

        var clock = new TestTime();
        var grants = TestBrowserProjection.Create(clock);
        grants.SetReady(true, consoleIdentity: "fixture-logon");
        JsonElement View(object value) => JsonSerializer.SerializeToElement(value, Contract.Json);
        foreach (var desktop in new[] { "off", "ask", "automatic" })
            foreach (var browser in new[] { "off", "ask", "automatic" })
            {
                grants.ConfigureSurface("desktop", desktop, 60, "timed");
                grants.ConfigureSurface("browser", browser, 60, "timed", ["fixture-profile"]);
                foreach (var (surface, mode, operation) in new[] { ("desktop", desktop, "type"), ("browser", browser, "browser.eval") })
                {
                    var initial = View(grants.Admission.Submit("fixture", desktop + browser + surface,
                        [surface], 300, 60, "Native/shared policy fixture", profileIds: surface == "browser" ? ["fixture-profile"] : []));
                    var id = initial.GetProperty("intentId").GetString()!;
                    Require(initial.GetProperty("state").GetString() == (mode == "off" ? "ended" : mode == "ask" ? "waiting_for_approval" : "offered"), "Independent native surface mode");
                    Require(grants.Authorize(new Request { Operation = operation }) == (mode == "off" ? "surface_disabled" : "control_session_required"), "Quiet Off or typed ownership negotiation");
                    if (mode == "off") continue;
                    if (mode == "ask") grants.Admission.Approve(id);
                    var offer = View(grants.Admission.Inspect("fixture", id));
                    var active = View(grants.Admission.Accept("fixture", id, offer.GetProperty("offerGeneration").GetInt64()));
                    var fence = new ControlOwnership("fixture", id, active.GetProperty("sessionId").GetString()!, active.GetProperty("resourceGenerations").Deserialize<Dictionary<string, long>>()!);
                    Require(grants.Authorize(new Request { Operation = operation, ControlOwnership = fence }) is null, "Approved native task reaches provider ceiling");
                    grants.Admission.Cancel("fixture", id);
                    Require(grants.Authorize(new Request { Operation = operation, ControlOwnership = fence }) is not null, "Cancelled native owner is fenced");
                }
                grants.Admission.Disconnect("fixture");
            }
        grants.ConfigureSurface("desktop", "automatic", 0, "until_stopped");
        grants.ConfigureSurface("browser", "automatic", 0, "until_stopped", ["fixture-profile"]);
        {
            // Tactical 159 decision 3: a locked-use guard failure ends the task
            // and fences dispatch, but it is not a person's Stop.
            var stops = grants.Stops;
            var guarded = View(grants.Admission.Submit("fixture", "guard-failure", ["desktop"], 300, 60, "Guard failure fixture"));
            var id = guarded.GetProperty("intentId").GetString()!;
            var active = View(grants.Admission.Accept("fixture", id, View(grants.Admission.Inspect("fixture", id)).GetProperty("offerGeneration").GetInt64()));
            var fence = new ControlOwnership("fixture", id, active.GetProperty("sessionId").GetString()!, active.GetProperty("resourceGenerations").Deserialize<Dictionary<string, long>>()!, StartedLocked: true);
            var generation = grants.Generation;
            Require(grants.Authorize(new Request { Operation = "type", ControlOwnership = fence }) is null, "Guarded owner authorized before failure");
            Require(grants.EndTask(fence, "locked_use_guard_failed"), "Guard failure ends the owned task");
            var ended = View(grants.Admission.Inspect("fixture", id));
            Require(ended.GetProperty("state").GetString() == "ended" && ended.GetProperty("terminalReason").GetString() == "locked_use_guard_failed",
                "Guard failure is the task's terminal reason, not cancelled");
            Require(grants.Authorize(new Request { Operation = "type", ControlOwnership = fence }) is not null && grants.Generation != generation,
                "Guard failure fences dispatch and rotates the desktop generation");
            Require(grants.Admission.Enabled("desktop") && grants.Admission.Enabled("browser") && grants.Stops == stops,
                "Guard failure retains saved consent and the Browser surface and is not a person's Stop");
            Require(!grants.EndTask(new ControlOwnership("fixture", "missing", "x", new()), "locked_use_guard_failed"), "Unknown task end is harmless");
            grants.Admission.Disconnect("fixture");
        }
        {
            // Tactical 159 decision 8: the common deployment projection.
            var deployment = View(grants.DeploymentState());
            Require(deployment.GetProperty("policy").GetProperty("protectedAdministration").ValueKind == JsonValueKind.False &&
                deployment.GetProperty("policy").GetProperty("preset").GetString() == "workstation" &&
                deployment.GetProperty("policy").GetProperty("operationSet").GetString() == "ordinary" &&
                deployment.GetProperty("availability").GetProperty("paused").ValueKind is JsonValueKind.True or JsonValueKind.False &&
                deployment.GetProperty("availability").GetProperty("blockingReasons").ValueKind == JsonValueKind.Array &&
                deployment.GetProperty("browserOnlyWhileLocked").ValueKind is JsonValueKind.True or JsonValueKind.False,
                "Deployment carries the common policy, availability and locked-browser fields");
            var modes = View(grants.SurfaceModes()).GetProperty("surfaces");
            Require(modes.GetProperty("desktop").GetProperty("mode").GetString() == "automatic" &&
                modes.GetProperty("browser").GetProperty("mode").GetString() == "automatic" &&
                !modes.GetProperty("desktop").GetProperty("expired").GetBoolean(), "Surface modes project for the doctor");
        }
        var protectedDesktopCeiling = grants.DesktopConsentRevision;
        grants.ConfigureSurface("browser", "automatic", 0, "until_stopped", ["fixture-profile"]);
        Require(grants.DesktopConsentRevision == protectedDesktopCeiling,
            "Browser consent cannot revoke the independent native protected Desktop ceiling");
        var browserGeneration = grants.BrowserGeneration;
        grants.Admission.Pause("desktop", "manual");
        Require(grants.Authorize("type") == "access_paused", "Desktop surface pause applies");
        Require(grants.Authorize("browser.eval") is null && grants.BrowserGeneration == browserGeneration, "Desktop pause preserves browser consent and generation");
        grants.Resume();
        Require(grants.Authorize("type") == "access_paused", "Global Resume preserves an independent surface pause");
        grants.ResumeSurface("desktop");
        clock.Advance(86400 * 365);
        Require(grants.Authorize("type") is null, "Explicit until-off consent has no deadline");
        grants.ConfigureSurface("desktop", "automatic", 60, "timed");
        grants.Pause(); clock.Advance(60); grants.Resume();
        Require(grants.Authorize("type") == "surface_disabled", "Pause cannot extend finite consent");
        grants.ConfigureSurface("desktop", "automatic", 300, "timed");
        grants.ConfigureBrowserWhileLocked(true);
        // Input-desktop and WTS lock observations need not settle in the same
        // poll. Unavailability blocks effects without deleting same-logon consent.
        grants.SetReady(false, false, "fixture-logon");
        Require(grants.Admission.Enabled("desktop") && grants.Admission.Enabled("browser"),
            "A same-logon lock transition retains both independent consents");
        Require(grants.Authorize("browser.eval", controlled: true) is not null &&
            grants.Authorize("type", controlled: true) is not null,
            "Unknown transition readiness cannot authorize either provider");
        grants.SetReady(false, true, "fixture-logon");
        Require(grants.BrowserOnlyWhileLocked && grants.Authorize("browser.eval", controlled: true) is null, "Full Browser surface retains same-logon locked opt-in");
        grants.ConfigureBrowserWhileLocked(false);
        Require(!grants.BrowserOnlyWhileLocked && grants.Admission.Enabled("desktop") && grants.Admission.Enabled("browser"),
            "Disabling locked Browser availability cannot revoke either surface consent");
        grants.SetReady(true, consoleIdentity: "fixture-logon");
        grants.ConfigureBrowserWhileLocked(true);
        grants.SetReady(false, true, "fixture-logon");
        grants.SetReady(false, true, "other-fixture-logon");
        Require(!grants.BrowserOnlyWhileLocked && grants.Authorize("browser.eval") is not null, "A different console cannot inherit browser consent");
        Require(grants.ConsoleElsewhere && grants.Authorize("browser.eval", controlled: true) == "console_session_elsewhere",
            "A different logon reports its own pause reason");
        Require(grants.Admission.Enabled("desktop") && grants.Admission.Enabled("browser"),
            "A different logon on the console pauses but never revokes consent");
        grants.SetReady(true, true, "other-fixture-logon");
        Require(grants.Authorize("type", controlled: true) == "console_session_elsewhere", "A different unlocked logon is not ready");
        grants.SetReady(false, false, null, consoleElsewhere: true);
        Require(grants.ConsoleElsewhere && grants.Admission.Enabled("browser"), "Another console session pauses without revoking");
        grants.SetReady(false, false, null);
        Require(!grants.ConsoleElsewhere && grants.Authorize("type", controlled: true) == "desktop_unavailable",
            "Unknown console identity is unavailability, not replacement");
        grants.SetReady(true, consoleIdentity: "fixture-logon");
        Require(!grants.ConsoleElsewhere && grants.Authorize("browser.eval", controlled: true) is null &&
            grants.Authorize("type", controlled: true) is null, "The approving logon's return resumes the same consent");
        grants.SetReady(true);
        grants.PrepareConsole(true);
        grants.ConfigureSurface("desktop", "automatic", 300, "timed");
        grants.SetReady(false, true);
        Require(grants.Authorize("session.unlock.prepare", controlled: true) is null, "Explicit native preparation retains its protected route");
        Require(grants.Authorize("type", controlled: true) == "desktop_unavailable", "Protected preparation never enables ordinary locked input");
        grants.PrepareConsole(false);
        Require(grants.Admission.Blocks("desktop").Contains("resource_unavailable"), "Unprepared locked desktop is unavailable");
        grants.SetReady(true);
        grants.Stop("fixture_stop");
        Require((await grants.RequestAsync(new Request { Operation = "grant.request", Scopes = ["control"] }, "fixture")).ErrorCode == "surface_disabled", "Off never asks for broad target approval");
        grants.PrepareUpdate();
        var refused = false;
        try { grants.ConfigureSurface("desktop", "automatic", 300, "timed"); } catch (InvalidOperationException) { refused = true; }
        Require(refused, "Native update gate cannot arm");
        grants.CancelUpdate();
        grants.Admission.Disconnect("fixture");
        Console.WriteLine("Windows/shared surface mode and safety contracts passed");
    }
    private static void Require(bool value, string message) { if (!value) throw new Exception(message); }
}
