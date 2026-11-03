using System.Diagnostics;
using System.Runtime.InteropServices;
using System.Text;
using System.Text.Json;
using System.Windows.Automation;
using MachineControl.Windows;

/// Native interactive-session qualification. Real hooks, notice windows and
/// injected effects; explicit physical facts are not a physical-HID claim.
internal static class ActivityLive
{
    internal static async Task RunAsync()
    {
        var checks = new List<string>();
        void Check(bool value, string name)
        {
            if (!value) throw new Exception(name);
            checks.Add(name); Console.WriteLine(name);
        }
        RuntimeProfile.ConfigureUser("activity-conformance");
        var grants = new DesktopGrants();
        using var relay = new BrowserRelay(grants);
        grants.SetReady(true);
        using var monitor = new DesktopActivityMonitor(grants);
        using var presentation = new DesktopNativePresentation(grants);
        Check(monitor.Healthy && presentation.Ready, "Native activity hooks and independent presentation are healthy");
        grants.ConfigureSurface("desktop", "automatic", 0, "until_stopped");
        JsonElement View(object value) => JsonSerializer.SerializeToElement(value, Contract.Json);
        JsonElement Status(string id, bool heartbeat = false) => View(grants.Admission.Inspect("fixture", id, heartbeat));
        string? liveIntent = null;
        async Task Wait(Func<bool> predicate, int seconds = 15)
        {
            var deadline = Stopwatch.StartNew();
            while (!predicate())
            {
                if (deadline.Elapsed.TotalSeconds > seconds)
                    throw new TimeoutException("Native handoff condition did not settle: " + View(grants.Admission.Status()).GetRawText());
                if (liveIntent is not null) Status(liveIntent, true);
                await Task.Delay(100);
            }
        }
        void Human(string kind = "key") => grants.Activity.ObservePhysical((double)Stopwatch.GetTimestamp() / Stopwatch.Frequency, kind);
        JsonElement Submit(string name)
        {
            var result = View(grants.Admission.Submit("fixture", name, ["desktop"], 300, 120, "Native handoff acceptance"));
            liveIntent = result.GetProperty("intentId").GetString();
            return result;
        }
        JsonElement Activate(string id)
        {
            var offer = Status(id);
            if (offer.GetProperty("state").GetString() != "offered")
                throw new Exception("Expected activation offer: " + offer.GetRawText());
            return View(grants.Admission.Accept("fixture", id, offer.GetProperty("offerGeneration").GetInt64()));
        }
        string? Authorize(JsonElement active) => grants.Admission.Authorize("fixture", active.GetProperty("intentId").GetString()!,
            active.GetProperty("sessionId").GetString()!, active.GetProperty("resourceGenerations").Deserialize<Dictionary<string, long>>()!);
        async Task Press(string title, string label)
        {
            IntPtr button = IntPtr.Zero;
            await Wait(() =>
            {
                var window = OwnWindow(title);
                if (window == IntPtr.Zero) return false;
                EnumChildWindows(window, (handle, _) => { if (Text(handle) == label) button = handle; return true; }, IntPtr.Zero);
                return button != IntPtr.Zero;
            });
            // BM_CLICK silently ignores some inactive dialogs. Exercise the
            // actual native accessibility action without activating the notice.
            var element = AutomationElement.FromHandle(button);
            ((InvokePattern)element.GetCurrentPattern(InvokePattern.Pattern)).Invoke();
            await Wait(() => !IsWindow(button));
            Console.WriteLine("Native action completed: " + label);
        }
        const string warning = "Machine Control will use desktop", approval = "Machine Control requests access";
        var foreground = GetForegroundWindow();
        Human();
        var first = Submit("automatic");
        var id = first.GetProperty("intentId").GetString()!;
        Check(first.GetProperty("state").GetString() == "announcing", "Recent human activity starts the default warning instead of refusing");
        Check(first.GetProperty("noticeRemainingSeconds").GetDouble() > 9, "Default warning is ten seconds");
        await Wait(() => OwnWindow(warning) != IntPtr.Zero);
        Check(GetForegroundWindow() == foreground, "Showing the native warning does not steal focus");
        var elapsed = Stopwatch.StartNew();
        while (Status(id).GetProperty("state").GetString() == "announcing")
        {
            Human(); Status(id, true); await Task.Delay(200);
            if (elapsed.Elapsed.TotalSeconds > 13) throw new Exception("Typing restarted the warning");
        }
        Check(Status(id).GetProperty("state").GetString() == "offered", "Ongoing typing reaches an offer without a quiet prerequisite");
        var active = Activate(id);
        var keyboardBefore = monitor.InjectedKeyboard; var mouseBefore = monitor.InjectedMouse;
        var keys = new[] {
            new NativeMethods.INPUT { type = 1, union = new() { keyboard = new() { wVk = 0x87 } } },
            new NativeMethods.INPUT { type = 1, union = new() { keyboard = new() { wVk = 0x87, dwFlags = 2 } } }
        };
        Check(NativeMethods.SendInput(2, keys, Marshal.SizeOf<NativeMethods.INPUT>()) == 2, "Target-native injected F24 pair delivered");
        var mouse = new[] {
            new NativeMethods.INPUT { type = 0, union = new() { mouse = new() { dx = 1, dwFlags = 1 } } },
            new NativeMethods.INPUT { type = 0, union = new() { mouse = new() { dx = -1, dwFlags = 1 } } }
        };
        Check(NativeMethods.SendInput(2, mouse, Marshal.SizeOf<NativeMethods.INPUT>()) == 2, "Target-native injected mouse pair delivered");
        await Task.Delay(500);
        Check(monitor.InjectedKeyboard >= keyboardBefore + 2 && monitor.InjectedMouse > mouseBefore, "Native hooks independently observe injection flags");
        Check(Authorize(active) is null, "Agent-injected input does not interrupt ownership");
        Human("movement");
        Check(Authorize(active) is null, "Accidental movement does not interrupt ownership");
        Human("scroll");
        Check(Authorize(active) == "stale_control_session", "Deliberate takeover retires the old native owner before dispatch");
        Check(grants.Admission.Enabled("desktop"), "Takeover retains until-off consent");
        elapsed.Restart();
        while (Status(id).GetProperty("state").GetString() == "paused")
        {
            Status(id, true); Human(); await Task.Delay(250);
            if (elapsed.Elapsed.TotalSeconds > 64) throw new Exception("Activity reset the fixed cooldown");
        }
        Check(elapsed.Elapsed.TotalSeconds >= 59 && Status(id).GetProperty("state").GetString() == "announcing", "A fixed minute of cooldown ends with a fresh warning while typing continues");
        Human("button");
        await Press(warning, "Start now");
        var fresh = Activate(id);
        Check(fresh.GetProperty("sessionId").GetString() != active.GetProperty("sessionId").GetString(), "Start now issues fresh ownership after acknowledging its input");
        Check(Authorize(fresh) is null && Authorize(active) is not null, "Only the fresh owner can dispatch");
        grants.Admission.Pause("desktop", "manual");
        grants.ResumeSurface("desktop");
        await Press(warning, "Pause 30 seconds");
        Check(Status(id).GetProperty("state").GetString() == "paused", "Native thirty-second pause keeps the live task waiting");
        var pause = View(grants.Admission.Status()).GetProperty("deferrals").EnumerateArray().Single(value => value.GetProperty("resource").GetString() == "desktop");
        Check(pause.GetProperty("remainingSeconds").GetDouble() is > 28 and <= 30, "Native thirty-second pause reports its real deadline");
        grants.ResumeSurface("desktop");
        await Press(warning, "Pause 1 minute");
        pause = View(grants.Admission.Status()).GetProperty("deferrals").EnumerateArray().Single(value => value.GetProperty("resource").GetString() == "desktop");
        Check(pause.GetProperty("remainingSeconds").GetDouble() is > 58 and <= 60, "Native one-minute pause reports its real deadline");
        grants.ResumeSurface("desktop");
        await Press(warning, "Until Resume");
        pause = View(grants.Admission.Status()).GetProperty("deferrals").EnumerateArray().Single(value => value.GetProperty("resource").GetString() == "desktop");
        Check(pause.GetProperty("remainingSeconds").ValueKind == JsonValueKind.Null, "Native indefinite pause has no automatic deadline");
        grants.ResumeSurface("desktop");
        await Press(warning, "Deny task");
        Check(Status(id).GetProperty("terminalReason").GetString() == "denied_by_person" && grants.Admission.Enabled("desktop"), "Deny ends one task without turning off operator consent");
        grants.ConfigureSurface("desktop", "ask", 300, "timed");
        first = Submit("ask"); id = first.GetProperty("intentId").GetString()!;
        await Wait(() => OwnWindow(approval) != IntPtr.Zero);
        Check(Status(id).GetProperty("state").GetString() == "waiting_for_approval", "Ask first waits for explicit task approval");
        await Press(approval, "Allow this task");
        Check(Status(id).GetProperty("state").GetString() == "announcing", "Native task approval is followed by the warning");
        await Press(warning, "Start now"); Activate(id);
        grants.Admission.Cancel("fixture", id);
        first = Submit("stop"); id = first.GetProperty("intentId").GetString()!;
        await Press(approval, "Stop access");
        Check(!grants.Admission.Enabled("desktop") && !grants.Admission.Enabled("browser") &&
            Status(id).GetProperty("terminalReason").ValueKind == JsonValueKind.String,
            "Native Stop turns both surfaces off and ends waiting work");
        grants.ConfigureSurface("desktop", "off", 300, "timed");
        first = Submit("off");
        await Task.Delay(400);
        Check(first.GetProperty("terminalReason").GetString() == "surface_disabled" && OwnWindow(approval) == IntPtr.Zero && OwnWindow(warning) == IntPtr.Zero, "Off refuses quietly without a request notification");
        grants.Stop("fixture_complete"); grants.Admission.Disconnect("fixture");
        Check(SessionStateInspector.IsLocked((uint)RuntimeProfile.SessionId) == false, "Ordinary handoff fixture leaves the console unlocked");
        Console.WriteLine(JsonSerializer.Serialize(new
        {
            schema = "machine-control-unified-handoff-live/v1",
            passed = true,
            checks,
            physicalSignal = "in_process_policy_fixture",
            physicalHidQualified = false,
            nativeHooks = true,
            nativeNotices = true,
            sharedPolicy = "typescript_node"
        }, Contract.Json));
    }
    private static IntPtr OwnWindow(string title)
    {
        var found = IntPtr.Zero;
        EnumWindows((window, _) => { GetWindowThreadProcessId(window, out var pid); if (pid == Environment.ProcessId && Text(window) == title) found = window; return true; }, IntPtr.Zero);
        return found;
    }
    private static string Text(IntPtr window) { var text = new StringBuilder(512); GetWindowText(window, text, text.Capacity); return text.ToString(); }
    private delegate bool EnumWindow(IntPtr window, IntPtr data);
    [DllImport("user32.dll")] private static extern bool EnumWindows(EnumWindow callback, IntPtr data);
    [DllImport("user32.dll")] private static extern bool EnumChildWindows(IntPtr parent, EnumWindow callback, IntPtr data);
    [DllImport("user32.dll")] private static extern uint GetWindowThreadProcessId(IntPtr window, out int process);
    [DllImport("user32.dll", CharSet = CharSet.Unicode)] private static extern int GetWindowText(IntPtr window, StringBuilder text, int maximum);
    [DllImport("user32.dll")] private static extern IntPtr GetForegroundWindow();
    [DllImport("user32.dll")] private static extern bool IsWindow(IntPtr window);
}
