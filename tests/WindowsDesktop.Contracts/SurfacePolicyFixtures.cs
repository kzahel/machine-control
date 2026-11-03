using System.Text.Json;
using MachineControl.Windows;

internal static class SurfacePolicyFixtures
{
    internal static async Task RunAsync()
    {
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
        var browserGeneration = grants.BrowserGeneration;
        grants.Admission.Pause("desktop", "manual");
        Require(grants.Authorize("type") == "access_paused", "Desktop surface pause applies");
        Require(grants.Authorize("browser.eval") is null && grants.BrowserGeneration == browserGeneration, "Desktop pause preserves browser consent and generation");
        grants.Resume();
        clock.Advance(86400 * 365);
        Require(grants.Authorize("type") is null, "Explicit until-off consent has no deadline");
        grants.ConfigureSurface("desktop", "automatic", 60, "timed");
        grants.Pause(); clock.Advance(60); grants.Resume();
        Require(grants.Authorize("type") == "surface_disabled", "Pause cannot extend finite consent");
        grants.ConfigureBrowserWhileLocked(true);
        grants.SetReady(false, true, "fixture-logon");
        Require(grants.BrowserOnlyWhileLocked && grants.Authorize("browser.eval", controlled: true) is null, "Full Browser surface retains same-logon locked opt-in");
        grants.SetReady(false, true, "other-fixture-logon");
        Require(!grants.BrowserOnlyWhileLocked && grants.Authorize("browser.eval") is not null, "A different console cannot inherit browser consent");
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
