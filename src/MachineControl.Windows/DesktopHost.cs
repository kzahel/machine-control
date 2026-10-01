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
        var broker = new DesktopGrants();
        DesktopSafety.Broker = broker;
        RuntimeProfile.ConfigureUser("desktop");
        using var reader = new StreamReader(Console.OpenStandardInput(), Encoding.UTF8, false);
        await using var writer = new StreamWriter(Console.OpenStandardOutput(), new UTF8Encoding(false)) { AutoFlush = true };
        // First frame comes from the parent before any public pipe is served.
        var hello = JsonNode.Parse(await reader.ReadLineAsync() ?? "")?.AsObject()
            ?? throw new InvalidDataException("Operator handshake missing");
        if (hello["method"]?.GetValue<string>() != "hello") throw new InvalidDataException("Operator handshake required");
        DesktopSafety.OperatorProcessId = hello["processId"]!.GetValue<int>();
        broker.SetReady(DesktopSafety.Ready());
        using var shortcut = new DesktopStopShortcut(broker);
        var resident = new UserHost("desktop", broker).RunAsync(stop.Token);
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
                var completed = await Task.WhenAny(read, resident);
                if (completed == resident) { await resident; break; }
                var line = await read;
                if (line is null) break;
                object reply;
                try
                {
                    var command = JsonNode.Parse(line)?.AsObject() ?? throw new ArgumentException("Object required");
                    var method = command["method"]?.GetValue<string>();
                    switch (method)
                    {
                        case "state":
                            var state = JsonSerializer.SerializeToNode(broker.State(), Contract.Json)!.AsObject();
                            if (!state.ContainsKey("pending")) state["pending"] = null;
                            var ready = DesktopSafety.Ready();
                            state["platform"] = "windows";
                            state["stopShortcutAvailable"] = shortcut.Available;
                            state["stopShortcut"] = "Ctrl+Alt+Shift+.";
                            state["permissions"] = new JsonObject { ["accessibility"] = ready, ["screenRecording"] = ready };
                            state["browser"] = new JsonObject { ["connected"] = false, ["available"] = false };
                            state["socket"] = RuntimeProfile.UserPipe("desktop", RuntimeProfile.SessionId);
                            reply = new { ok = true, state };
                            break;
                        case "arm":
                            broker.Arm(command["scopes"]?.Deserialize<string[]>(), command["duration"]?.GetValue<int>() ?? 900);
                            reply = new { ok = true }; break;
                        case "decision":
                            broker.Decide(command["id"]?.GetValue<string>() ?? "", command["allow"]?.GetValue<bool>() == true,
                                command["scopes"]?.Deserialize<string[]>(), command["duration"]?.GetValue<int>() ?? 0);
                            reply = new { ok = true }; break;
                        case "stop": broker.Stop("stopped_by_person"); reply = new { ok = true }; break;
                        case "prepare_update": broker.PrepareUpdate(); reply = new { ok = true }; break;
                        case "cancel_update": broker.CancelUpdate(); reply = new { ok = true }; break;
                        case "quit": broker.Stop("operator_quit"); reply = new { ok = true }; stop.Cancel(); break;
                        default: throw new ArgumentException("Unknown operator command");
                    }
                }
                catch (Exception ex) when (ex is ArgumentException or InvalidOperationException or JsonException)
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
