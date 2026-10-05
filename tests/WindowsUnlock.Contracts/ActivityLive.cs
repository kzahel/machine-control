using System.Diagnostics;
using System.Runtime.InteropServices;
using System.Text.Json;
using MachineControl.Windows;

/// Interactive-console native monitor fixture. Its explicit policy signal is
/// deterministic coverage, not evidence of a physical HID device or VM input.
internal static class ActivityLive
{
    internal static async Task RunAsync()
    {
        var checks = new List<string>();
        void Check(bool value, string name) { if (!value) throw new Exception(name); checks.Add(name); }
        RuntimeProfile.ConfigureUser("activity-conformance");
        var grants = new DesktopGrants(); grants.SetReady(true); grants.Arm(["observe", "control"], 900);
        using var monitor = new DesktopActivityMonitor(grants);
        Check(monitor.Healthy, "Native keyboard/mouse hook registrations and message loop healthy");
        async Task Wait(Func<bool> predicate)
        {
            var deadline = Stopwatch.StartNew();
            while (!predicate()) { if (deadline.Elapsed.TotalSeconds > 45) throw new TimeoutException(); await Task.Delay(200); }
        }
        await Wait(() => grants.Admission.Blocks("desktop").Length == 0);
        Check(true, "Startup session quiet permits ordinary admission");
        JsonElement View(object value) => JsonSerializer.SerializeToElement(value, Contract.Json);
        var offered = View(grants.Admission.Submit("fixture", "native-activity", ["desktop"], 300, 120, "Native activity fixture", () => grants.AdmissionAuthority(["control"])));
        var id = offered.GetProperty("intentId").GetString()!;
        var active = View(grants.Admission.Accept("fixture", id, offered.GetProperty("offerGeneration").GetInt64()));
        var session = active.GetProperty("sessionId").GetString()!;
        var generations = active.GetProperty("resourceGenerations").Deserialize<Dictionary<string, long>>()!;
        var keyboardBefore = monitor.InjectedKeyboard; var mouseBefore = monitor.InjectedMouse;
        var keys = new[] {
            new NativeMethods.INPUT { type = 1, union = new() { keyboard = new() { wVk = 0xFC } } },
            new NativeMethods.INPUT { type = 1, union = new() { keyboard = new() { wVk = 0xFC, dwFlags = 2 } } }
        };
        Check(NativeMethods.SendInput((uint)keys.Length, keys, Marshal.SizeOf<NativeMethods.INPUT>()) == 2, "Target-native injected keyboard pair delivered");
        var mouse = new[] { new NativeMethods.INPUT { type = 0, union = new() { mouse = new() { dwFlags = 1 } } } };
        Check(NativeMethods.SendInput(1, mouse, Marshal.SizeOf<NativeMethods.INPUT>()) == 1, "Target-native injected zero-motion mouse delivered");
        await Task.Delay(500);
        Check(monitor.InjectedKeyboard >= keyboardBefore + 2 && monitor.InjectedMouse > mouseBefore, "Native hooks independently observed injected keyboard/mouse flags");
        Check(grants.Admission.Authorize("fixture", id, session, generations) is null, "Injected keyboard/mouse do not pause or retire ownership");
        var original = grants.Generation;
        grants.Activity.ObservePhysical((double)Stopwatch.GetTimestamp() / Stopwatch.Frequency);
        Check(grants.Admission.Authorize("fixture", id, session, generations) == "stale_control_session", "Deterministic policy signal fences before next dispatch");
        Check(grants.Generation != original, "Activity changes native generation");
        Check(View(grants.DeploymentState()).GetProperty("grant").ValueKind == JsonValueKind.Object, "Activity retains ordinary consent");
        grants.Pause();
        await Wait(() => { grants.Admission.Inspect("fixture", id, heartbeat: true); return !grants.Admission.Blocks("desktop").Contains("physical_activity"); });
        Check(grants.Admission.Blocks("desktop").Contains("manual"), "Real quiet timer does not clear manual pause");
        grants.Resume();
        var next = View(grants.Admission.Inspect("fixture", id));
        Check(next.GetProperty("state").GetString() == "offered", "Quiet and operator Resume permit fresh offer");
        var fresh = View(grants.Admission.Accept("fixture", id, next.GetProperty("offerGeneration").GetInt64()));
        Check(fresh.GetProperty("sessionId").GetString() != session, "Fresh session identity after interruption");
        Check(grants.Admission.Authorize("fixture", id, session, generations) is not null, "Retired action fence remains unusable");
        Check(SessionStateInspector.IsLocked((uint)RuntimeProfile.SessionId) == false, "Unlocked fixture remains unlocked");
        grants.Stop("fixture_complete");
        Console.WriteLine(JsonSerializer.Serialize(new { schema = "machine-control-activity-live/v0", passed = true,
            checks, physicalSignal = "in_process_policy_fixture", physicalHidQualified = false }, Contract.Json));
    }
}
