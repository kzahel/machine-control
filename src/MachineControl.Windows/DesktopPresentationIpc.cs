using System.IO;
using System.IO.Pipes;
using System.Text;
using System.Text.Json.Nodes;

namespace MachineControl.Windows;

/// Local operator configuration is a separate, closed, same-user surface.
/// The public agent pipe cannot change presentation or approve requests.
internal static class DesktopPresentationIpc
{
    [System.Runtime.InteropServices.DllImport("kernel32.dll", CharSet = System.Runtime.InteropServices.CharSet.Unicode, SetLastError = true)]
    private static extern bool WaitNamedPipe(string name, uint milliseconds);
    internal static string PathFor(string instance) => Path.Combine(
        Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
        "MachineControl", "presentation", RuntimeProfile.ValidateInstance(instance) + ".json");
    private static string Pipe(string instance) => RuntimeProfile.UserPipe(instance, RuntimeProfile.SessionId) + "-presentation";
    internal static object Apply(DesktopPresentation presentation, DesktopGrants? broker, JsonObject request)
    {
        var method = request["method"]?.GetValue<string>();
        if (method is not ("status" or "set" or "reset")) throw new ArgumentException("Unknown presentation operation");
        if (method != "status" && broker is not null)
        {
            var state = System.Text.Json.JsonSerializer.SerializeToNode(broker.State(), Contract.Json)!;
            if (state["pending"] is not null) throw new InvalidOperationException("Finish approval before changing presentation");
        }
        return method == "status" ? presentation.Status() : presentation.Set(method == "reset" ? "personal" : request["profile"]?.GetValue<string>() ?? "");
    }
    internal static async Task ServeAsync(string instance, DesktopPresentation presentation, DesktopGrants broker, CancellationToken stop)
    {
        using var listener = UserHost.CreatePipe(Pipe(instance), first: true);
        while (!stop.IsCancellationRequested)
        {
            await listener.WaitForConnectionAsync(stop);
            using var timeout = CancellationTokenSource.CreateLinkedTokenSource(stop);
            timeout.CancelAfter(TimeSpan.FromSeconds(3));
            try
            {
                using var reader = new StreamReader(listener, Encoding.UTF8, leaveOpen: true);
                var bytes = new char[1];
                var frame = new StringBuilder();
                while (await reader.ReadAsync(bytes.AsMemory(), timeout.Token) != 0 && bytes[0] != '\n')
                {
                    if (frame.Length >= 4096) throw new InvalidDataException("Presentation frame exceeds bounds");
                    frame.Append(bytes[0]);
                }
                object reply;
                try { reply = new { ok = true, presentation = Apply(presentation, broker, JsonNode.Parse(frame.ToString()) as JsonObject ?? throw new ArgumentException("Object required")), runtimeId = Environment.ProcessId }; }
                catch (Exception ex) when (ex is ArgumentException or InvalidOperationException or IOException or System.Text.Json.JsonException or UnauthorizedAccessException)
                { reply = new { ok = false, error = ex.Message }; }
                await using var writer = new StreamWriter(listener, new UTF8Encoding(false), leaveOpen: true);
                await writer.WriteLineAsync(Contract.Serialize(reply).AsMemory(), timeout.Token);
                await writer.FlushAsync(timeout.Token);
                // Disconnect discards unread named-pipe bytes. The caller
                // acknowledges consumption before we reuse the listener.
                await reader.ReadAsync(bytes.AsMemory(), timeout.Token);
            }
            catch (Exception ex) when (ex is IOException or OperationCanceledException or System.Text.Json.JsonException) { }
            finally { listener.Disconnect(); }
        }
    }

    internal static async Task<int> RunCliAsync(string[] arguments)
    {
        var instance = Program.GetOption(arguments, "--instance") ?? "desktop";
        RuntimeProfile.ValidateInstance(instance);
        var positional = arguments.Skip(1).TakeWhile(value => value != "--instance").ToArray();
        if (positional.Length == 0 || !(positional is ["status"] or ["reset"] or ["set", _]) ||
            arguments.Length != 1 + positional.Length + (arguments.Contains("--instance") ? 2 : 0))
            throw new ArgumentException("Usage: presentation status|set PROFILE|reset [--instance NAME]");
        var command = new JsonObject { ["method"] = positional[0] };
        if (positional[0] == "set") command["profile"] = DesktopPresentation.Validate(positional[1]);
        using var pipe = new NamedPipeClientStream(".", Pipe(instance), PipeDirection.InOut, PipeOptions.Asynchronous);
        var connected = false;
        using var timeout = new CancellationTokenSource(TimeSpan.FromSeconds(4));
        try { await pipe.ConnectAsync(250, timeout.Token); connected = true; }
        catch (TimeoutException)
        {
            WaitNamedPipe(@"\\.\pipe\" + Pipe(instance), 1);
            if (System.Runtime.InteropServices.Marshal.GetLastWin32Error() != 2)
                throw new IOException("Presentation endpoint is busy; no offline edit was attempted");
        }
        object reply;
        if (connected)
        {
            await using var writer = new StreamWriter(pipe, new UTF8Encoding(false), leaveOpen: true) { AutoFlush = true };
            using var reader = new StreamReader(pipe, Encoding.UTF8, leaveOpen: true);
            await writer.WriteLineAsync(command.ToJsonString().AsMemory(), timeout.Token);
            // Never retry a mutation through the file after uncertain delivery.
            var frame = new StringBuilder();
            var character = new char[1];
            while (await reader.ReadAsync(character.AsMemory(), timeout.Token) != 0 && character[0] != '\n')
            {
                if (frame.Length >= 4096) throw new IOException("Presentation reply exceeds bounds");
                frame.Append(character[0]);
            }
            var value = JsonNode.Parse(frame.ToString()) as JsonObject ?? throw new IOException("Presentation reply missing");
            await writer.WriteLineAsync("ack".AsMemory(), timeout.Token);
            Console.WriteLine(value.ToJsonString());
            return value["ok"]?.GetValue<bool>() == true ? 0 : 1;
        }
        reply = new { ok = true, presentation = Apply(new DesktopPresentation(PathFor(instance)), null, command), runtimeId = (int?)null };
        Console.WriteLine(Contract.Serialize(reply));
        return 0;
    }
}
