using System.IO;
using System.Text;
using System.Text.Json;
using System.Text.Json.Nodes;

namespace MachineControl.Windows;

/// Anonymous inherited stdin/stdout is the operator channel. There is no
/// approval endpoint on the named pipe and no approval bearer in arguments.
internal static class DesktopHost
{
    internal static async Task<int> RunAsync()
    {
        if (!Console.IsInputRedirected || !Console.IsOutputRedirected)
            throw new InvalidOperationException("The desktop resident requires its operator transport");
        using var stop = new CancellationTokenSource();
        var journal = new DesktopJournal();
        var broker = new DesktopGrants(journal: journal);
        var updates = new DesktopUpdates();
        DesktopSafety.Broker = broker;
        RuntimeProfile.ConfigureUser("desktop");
        BrowserInstaller.RecoverOwn();
        using var reader = new StreamReader(Console.OpenStandardInput(), Encoding.UTF8, false);
        await using var writer = new StreamWriter(Console.OpenStandardOutput(), new UTF8Encoding(false)) { AutoFlush = true };
        // First frame comes from the parent before any public pipe is served.
        var hello = JsonNode.Parse(await reader.ReadLineAsync() ?? "")?.AsObject()
            ?? throw new InvalidDataException("Operator handshake missing");
        if (hello["method"]?.GetValue<string>() != "hello") throw new InvalidDataException("Operator handshake required");
        DesktopSafety.OperatorProcessId = hello["processId"]!.GetValue<int>();
        broker.SetReady(DesktopSafety.Ready());
        using var shortcut = new DesktopStopShortcut(broker);
        var browser = new BrowserRelay(broker);
        var browserTask = browser.RunAsync(stop.Token);
        var resident = new UserHost("desktop", broker, browser, updates).RunAsync(stop.Token);
        var monitor = Task.Run(async () =>
        {
            while (!stop.IsCancellationRequested)
            {
                broker.SetReady(DesktopSafety.Ready());
                broker.Refresh();
                await Task.Delay(200, stop.Token);
            }
        });
        try
        {
            await writer.WriteLineAsync(Contract.Serialize(new { ok = true }));
            while (!stop.IsCancellationRequested)
            {
                var read = ReadCommandAsync(reader, stop.Token);
                var completed = await Task.WhenAny(read, resident, browserTask, monitor);
                if (completed != read) { await completed; break; }
                var line = await read;
                if (line is null) break;
                object reply;
                try
                {
                    var command = JsonNode.Parse(line)?.AsObject() ?? throw new ArgumentException("Object required");
                    var method = command["method"]?.GetValue<string>();
                    switch (method)
                    {
                        case "update_sync":
                            reply = new { ok = true, checkRequested = updates.Sync(command["state"]!.AsObject()) };
                            break;
                        case "state":
                            var state = JsonSerializer.SerializeToNode(broker.State(), Contract.Json)!.AsObject();
                            if (!state.ContainsKey("pending")) state["pending"] = null;
                            var ready = DesktopSafety.Ready();
                            state["platform"] = "windows";
                            state["stopShortcutAvailable"] = shortcut.Available;
                            state["stopShortcut"] = "Ctrl+Alt+Shift+.";
                            state["permissions"] = new JsonObject { ["accessibility"] = ready, ["screenRecording"] = ready };
                            state["browser"] = JsonSerializer.SerializeToNode(browser.State, Contract.Json);
                            state["socket"] = RuntimeProfile.UserPipe("desktop", RuntimeProfile.SessionId);
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
                            BrowserRegistration.Install();
                            reply = new { ok = true }; break;
                        case "arm":
                            broker.Arm(command["scopes"]?.Deserialize<string[]>(), command["duration"]?.GetValue<int>() ?? 900,
                                command["lifetime"]?.GetValue<string>() ?? "timed");
                            reply = new { ok = true }; break;
                        case "decision":
                            broker.Decide(command["id"]?.GetValue<string>() ?? "", command["allow"]?.GetValue<bool>() == true,
                                command["scopes"]?.Deserialize<string[]>(), command["duration"]?.GetValue<int>() ?? 0);
                            reply = new { ok = true }; break;
                        case "stop": broker.Stop("stopped_by_person"); reply = new { ok = true }; break;
                        case "pause": broker.Pause(command["duration"]?.GetValue<int>()); reply = new { ok = true }; break;
                        case "resume": broker.Resume(); reply = new { ok = true }; break;
                        case "start_control": broker.Admission.StartNow(command["intentId"]!.GetValue<string>()); reply = new { ok = true }; break;
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
            journal.Event("resident.stop");
            DesktopSafety.Broker = null;
        }
        return 0;
    }

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
