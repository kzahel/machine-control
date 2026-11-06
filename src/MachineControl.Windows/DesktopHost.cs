using System.IO;
using System.Text;
using System.Text.Json;
using System.Text.Json.Nodes;

namespace MachineControl.Windows;

/// Anonymous inherited stdin/stdout is the operator channel. There is no
/// approval endpoint on the named pipe and no approval bearer in arguments.
internal static class DesktopHost
{
    internal static async Task<int> RunAsync(string instance = "desktop", string? temporaryPresentation = null)
    {
        if (!Console.IsInputRedirected || !Console.IsOutputRedirected)
            throw new InvalidOperationException("The desktop resident requires its operator transport");
        using var stop = new CancellationTokenSource();
        RuntimeProfile.ConfigureUser(instance);
        var presentation = new DesktopPresentation(DesktopPresentationIpc.PathFor(instance), temporaryPresentation);
        var journal = new DesktopJournal(instance == "desktop" ? null : Path.Combine(RuntimeProfile.StateRoot, "logs"));
        var broker = new DesktopGrants(journal: journal);
        var browserPreference = new DesktopBrowserPreference(Path.Combine(
            Path.GetDirectoryName(DesktopPresentationIpc.PathFor(instance))!, instance + "-browser-while-locked.json"));
        broker.ConfigureBrowserWhileLocked(browserPreference.Enabled, loading: true);
        var lockedPreference = new DesktopBrowserPreference(Path.Combine(
            Path.GetDirectoryName(DesktopPresentationIpc.PathFor(instance))!, instance + "-covered-desktop.json"),
            "machine-control-covered-desktop/v1");
        var lockedUse = new DesktopLockedUse(broker, stop.Token);
        if (lockedPreference.Enabled && DesktopLockedUse.Prepared()) lockedUse.Enable(true);
        DesktopLockedUse.Current = lockedUse;
        var updates = new DesktopUpdates();
        DesktopSafety.Broker = broker;
        BrowserInstaller.RecoverOwn();
        using var reader = new StreamReader(Console.OpenStandardInput(), Encoding.UTF8, false);
        await using var writer = new StreamWriter(Console.OpenStandardOutput(), new UTF8Encoding(false)) { AutoFlush = true };
        // First frame comes from the parent before any public pipe is served.
        var hello = JsonNode.Parse(await reader.ReadLineAsync() ?? "")?.AsObject()
            ?? throw new InvalidDataException("Operator handshake missing");
        if (hello["method"]?.GetValue<string>() != "hello") throw new InvalidDataException("Operator handshake required");
        DesktopSafety.OperatorProcessId = hello["processId"]!.GetValue<int>();
        DesktopSafety.RefreshAvailability(broker);
        using var activity = new DesktopActivityMonitor(broker);
        using var shortcut = new DesktopStopShortcut(broker);
        using var nativePresentation = new DesktopNativePresentation(broker);
        using var browser = new BrowserRelay(broker);
        var accessPreferences = new DesktopAccessPreferences(Path.Combine(Path.GetDirectoryName(DesktopPresentationIpc.PathFor(instance))!, instance + "-access-preferences.json"));
        if (accessPreferences.Read() is { } savedPreferences)
        {
            try { broker.Admission.Preferences(savedPreferences); }
            catch (InvalidOperationException) { journal.Diagnostic("access.preferences", "invalid_saved_preferences"); }
        }
        var browserTask = browser.RunAsync(stop.Token);
        var resident = new UserHost(instance, broker, browser, updates).RunAsync(stop.Token);
        var presentationServer = DesktopPresentationIpc.ServeAsync(instance, presentation, broker, stop.Token);
        JsonObject BuildState()
        {
            var state = JsonSerializer.SerializeToNode(broker.State(), Contract.Json)!.AsObject();
            if (!state.ContainsKey("pending")) state["pending"] = null;
            var ready = DesktopSafety.Ready();
            state["platform"] = "windows";
            state["nativeApproval"] = true;
            state["presentation"] = JsonSerializer.SerializeToNode(presentation.Status(), Contract.Json);
            state["stopShortcutAvailable"] = shortcut.Available;
            state["stopShortcut"] = "Ctrl+Alt+Shift+.";
            state["permissions"] = new JsonObject { ["accessibility"] = ready, ["screenRecording"] = ready };
            state["browser"] = JsonSerializer.SerializeToNode(browser.State, Contract.Json);
            state["uac"] = JsonSerializer.SerializeToNode(DesktopUacClient.State(), Contract.Json);
            state["lockedUse"] = JsonSerializer.SerializeToNode(lockedUse.State(), Contract.Json);
            state["physicalAvailability"] = JsonSerializer.SerializeToNode(activity.State, Contract.Json);
            state["socket"] = RuntimeProfile.UserPipe(instance, RuntimeProfile.SessionId);
            return state;
        }
        // The operator status poll reads this snapshot and never waits for the
        // admission gate or the shared policy process. The monitor rebuilds it
        // about once a second, and promptly after each operator command.
        StateSnapshot? snapshot = null;
        long requested = 0;
        using var rebuild = new SemaphoreSlim(0, 1);
        var built = long.MinValue;
        void Publish(bool due)
        {
            var sequence = Volatile.Read(ref requested);
            if (sequence == (Volatile.Read(ref snapshot)?.Sequence ?? -1) && !due) return;
            built = Environment.TickCount64;
            try
            {
                Volatile.Write(ref snapshot, new StateSnapshot(BuildState(), Environment.TickCount64, sequence));
            }
            catch (Exception ex) when (ex is not OperationCanceledException || !stop.IsCancellationRequested)
            {
                // Keep the previous state and its age, which reaches the
                // supervisor; it restarts a resident that stops publishing.
                // Commands waiting for this sequence no longer wait.
                if (Volatile.Read(ref snapshot) is { } previous)
                    Volatile.Write(ref snapshot, previous with { Sequence = sequence });
                journal.Diagnostic("desktop.state", ex.GetType().Name);
            }
        }
        var monitor = Task.Run(async () =>
        {
            var policySeen = false;
            while (!stop.IsCancellationRequested)
            {
                if (browser.PolicyAvailable) policySeen = true;
                else if (policySeen)
                {
                    // A lost policy process cannot be rebound in place. End this
                    // resident; the supervisor restarts it and restores access.
                    broker.Admission.Invalidate();
                    broker.Stop("resident_policy_disconnected");
                    journal.Diagnostic("desktop.supervisor", "resident_policy_lost");
                    return;
                }
                // A command waiting for its effect is published before housekeeping.
                Publish(due: false);
                try
                {
                    DesktopSafety.RefreshAvailability(broker);
                    lockedUse.Tick();
                    broker.Refresh();
                    browser.SynchronizeSafety();
                }
                catch (Exception ex) when (!browser.PolicyAvailable && (ex is IOException or TimeoutException or OperationCanceledException))
                {
                    // Keep native status/Stop available after private policy
                    // loss. Invalidation retires ownership before any retry.
                    broker.Admission.Invalidate();
                    broker.Stop("resident_policy_disconnected");
                }
                Publish(due: Environment.TickCount64 - built >= 1000);
                await rebuild.WaitAsync(200, stop.Token);
            }
        });
        try
        {
            await writer.WriteLineAsync(Contract.Serialize(new { ok = true, stopWindow = shortcut.WindowHandle, presentation = presentation.Status() }));
            while (!stop.IsCancellationRequested)
            {
                // Windows console-pipe reads can block before yielding a Task.
                // Keep child failure monitoring independent of operator input.
                var read = Task.Run(() => ReadCommandAsync(reader, stop.Token));
                var completed = await Task.WhenAny(read, resident, browserTask, monitor, presentationServer);
                if (completed != read) { await completed; break; }
                var line = await read;
                if (line is null) break;
                object reply;
                string? method = null;
                try
                {
                    var command = JsonNode.Parse(line)?.AsObject() ?? throw new ArgumentException("Object required");
                    method = command["method"]?.GetValue<string>();
                    switch (method)
                    {
                        case "presentation":
                            reply = new
                            {
                                ok = true,
                                presentation = DesktopPresentationIpc.Apply(presentation, broker,
                                new JsonObject { ["method"] = "set", ["profile"] = command["profile"]?.GetValue<string>() })
                            };
                            break;
                        case "update_sync":
                            reply = new { ok = true, checkRequested = updates.Sync(command["state"]!.AsObject()) };
                            break;
                        case "state":
                            // `fresh` (update and restore flows) uses the direct path.
                            // An aged snapshot is still served: building it here
                            // would wait for the policy process again.
                            var current = Volatile.Read(ref snapshot);
                            var direct = current is null || command["fresh"]?.GetValue<bool>() == true;
                            var state = direct ? BuildState() : current!.State.DeepClone().AsObject();
                            state["stateAgeMs"] = direct ? 0 : Environment.TickCount64 - current!.At;
                            state["stops"] = broker.Stops;
                            reply = new { ok = true, state };
                            break;
                        case "logs.query":
                            reply = new { ok = true, history = journal.Query(command["offset"]?.GetValue<int>() ?? 0, command["operation"]?.GetValue<string>() ?? "", command["outcome"]?.GetValue<string>() ?? "", command["stream"]?.GetValue<string>() ?? "audit") }; break;
                        case "logs.debug": journal.Debug(command["enabled"]?.GetValue<bool>() == true); reply = new { ok = true }; break;
                        case "logs.preview": reply = new { ok = true, preview = journal.Preview() }; break;
                        case "logs.export": reply = new { ok = true, path = journal.Export() }; break;
                        case "logs.location": reply = new { ok = true, path = journal.Root }; break;
                        case "logs.diagnostic":
                            journal.Diagnostic("desktop.supervisor", command["code"]?.GetValue<string>() ?? "unknown");
                            reply = new { ok = true }; break;
                        case "browser.setup":
                            BrowserRegistration.Install(command["bundled"]?.GetValue<bool>() == true);
                            reply = new { ok = true }; break;
                        case "uac.enable":
                            DesktopUacClient.Enable(command["enabled"]?.GetValue<bool>() == true, broker);
                            reply = new { ok = true }; break;
                        case "locked_use":
                            var lockedEnabled = command["enabled"]?.GetValue<bool>() == true;
                            lockedUse.Enable(lockedEnabled);
                            lockedPreference.Set(lockedEnabled);
                            reply = new { ok = true }; break;
                        case "browser_while_locked":
                            DesktopSafety.RefreshAvailability(broker);
                            var browserEnabled = command["enabled"]?.GetValue<bool>() ?? throw new ArgumentException("Choose browser access while locked");
                            lock (broker.Gate)
                            {
                                if (browserEnabled && !broker.CanEnableBrowserWhileLocked) throw new InvalidOperationException("Use the unlocked console before enabling browser access");
                                browserPreference.Set(browserEnabled);
                                broker.ConfigureBrowserWhileLocked(browserEnabled);
                            }
                            reply = new { ok = true }; break;
                        case "surface.configure":
                            broker.ConfigureSurface(command["surface"]!.GetValue<string>(), command["mode"]!.GetValue<string>(),
                                command["duration"]?.GetValue<int>() ?? 900, command["lifetime"]?.GetValue<string>() ?? "timed",
                                command["browserProfileIds"]?.Deserialize<string[]>());
                            reply = new { ok = true }; break;
                        case "control_notice":
                            var noticeSeconds = command["noticeSeconds"]!.GetValue<int>();
                            if (noticeSeconds is < 0 or > 60) throw new ArgumentException("Choose a notice countdown between 0 and 60 seconds");
                            broker.Admission.Notice(noticeSeconds); reply = new { ok = true }; break;
                        case "access_preferences":
                            accessPreferences.Set(broker.Admission.Preferences(command["preferences"]!.AsObject())); reply = new { ok = true }; break;
                        case "hold_control":
                            broker.Admission.Hold(command["intentId"]!.GetValue<string>()); reply = new { ok = true }; break;
                        case "postpone_control":
                            broker.Admission.Postpone(command["intentId"]!.GetValue<string>(), command["duration"]!.GetValue<int>()); reply = new { ok = true }; break;
                        case "approve_control":
                        case "continue_control":
                            broker.Activity.AcknowledgeOperatorInput();
                            broker.Admission.Approve(command["intentId"]!.GetValue<string>(), command["duration"]?.GetValue<int>() ?? 0); reply = new { ok = true }; break;
                        case "pause_request": broker.PauseRequest(command["intentId"]!.GetValue<string>(), command["duration"]?.GetValue<int>()); reply = new { ok = true }; break;
                        case "pause_surface":
                            var surface = command["surface"]!.GetValue<string>();
                            if (surface is not ("desktop" or "browser")) throw new ArgumentException("Choose a surface");
                            broker.Admission.Pause(surface, "manual", command["duration"]?.GetValue<int>()); reply = new { ok = true }; break;
                        case "resume_surface": broker.ResumeSurface(command["surface"]!.GetValue<string>()); reply = new { ok = true }; break;
                        case "stop": broker.Stop("stopped_by_person"); reply = new { ok = true }; break;
                        case "pause": broker.Pause(command["duration"]?.GetValue<int>()); reply = new { ok = true }; break;
                        case "resume": broker.Resume(); reply = new { ok = true }; break;
                        case "start_control":
                            broker.Activity.AcknowledgeOperatorInput();
                            broker.Admission.StartNow(command["intentId"]!.GetValue<string>()); reply = new { ok = true }; break;
                        case "defer_control": broker.Admission.Pause("desktop", "operator_deferral", 60); reply = new { ok = true }; break;
                        case "cancel_control": broker.Admission.CancelFromOperator(command["intentId"]!.GetValue<string>()); reply = new { ok = true }; break;
                        case "prepare_exit": broker.Stop("operator_quit"); reply = new { ok = true }; break;
                        case "prepare_update": broker.PrepareUpdate(); reply = new { ok = true }; break;
                        case "cancel_update": broker.CancelUpdate(); reply = new { ok = true }; break;
                        case "quit": broker.Stop("operator_quit"); reply = new { ok = true }; stop.Cancel(); break;
                        default: throw new ArgumentException("Unknown operator command");
                    }
                }
                catch (Exception ex) when (ex is ArgumentException or InvalidOperationException or JsonException or
                    IOException or UnauthorizedAccessException or System.Security.SecurityException)
                { reply = new { ok = false, error = ex.Message }; }
                if (!stop.IsCancellationRequested &&
                    method is not ("state" or "update_sync" or "logs.query" or "logs.preview" or "logs.location" or "logs.diagnostic" or
                        "logs.export" or "logs.debug"))
                {
                    // Let the next status poll observe this command's effect
                    // rather than a snapshot built before it.
                    var needed = Interlocked.Increment(ref requested);
                    try { rebuild.Release(); } catch (SemaphoreFullException) { }
                    var until = Environment.TickCount64 + 1000;
                    while ((Volatile.Read(ref snapshot)?.Sequence ?? -1) < needed && Environment.TickCount64 < until)
                        await Task.Delay(20, stop.Token);
                }
                await writer.WriteLineAsync(Contract.Serialize(reply));
            }
        }
        finally
        {
            broker.Stop("operator_disconnected");
            stop.Cancel();
            try { await resident; } catch (OperationCanceledException) { }
            try { await monitor; } catch (OperationCanceledException) { }
            try { await browserTask; } catch (OperationCanceledException) { }
            try { await presentationServer; } catch (OperationCanceledException) { }
            journal.Event("resident.stop");
            DesktopSafety.Broker = null;
            DesktopLockedUse.Current = null;
        }
        return 0;
    }

    private sealed record StateSnapshot(JsonObject State, long At, long Sequence);

    private static async Task<string?> ReadCommandAsync(StreamReader reader, CancellationToken stop)
    {
        var value = new StringBuilder();
        var character = new char[1];
        while (await reader.ReadAsync(character.AsMemory(), stop) != 0)
        {
            if (character[0] == '\n') return value.ToString();
            if (value.Length >= 65536) throw new InvalidDataException("Operator frame exceeds 64 KiB");
            value.Append(character[0]);
        }
        return null;
    }
}
