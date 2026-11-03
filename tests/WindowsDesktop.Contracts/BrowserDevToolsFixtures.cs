using System.Diagnostics;
using System.Net.WebSockets;
using System.Text;
using System.Text.Json.Nodes;
using MachineControl.Windows;

/// Exercise the actual shared policy process through the Windows native IPC
/// client. Protocol edge cases also run in the portable Node conformance suite.
internal static class BrowserDevToolsFixtures
{
    private static void Require(bool condition, string message)
    { if (!condition) throw new Exception("Shared browser native IPC: " + message); }
    internal static async Task RunAsync()
    {
        var start = new ProcessStartInfo(Environment.GetEnvironmentVariable("MACHINE_CONTROL_NODE") ?? "node");
        start.ArgumentList.Add(Path.GetFullPath("runtime/node/main.ts"));
        SharedBrowserHost? host = null;
        string? connectionId = null;
        var nativeAllowed = true;
        var commands = 0;
        var unknown = 0;
        var suppress = false;
        var failure = false;
        var calls = new List<Task>();
        void Post(JsonObject frame)
        {
            lock (calls) calls.Add(Task.Run(() => host!.Call(new JsonObject
            { ["method"] = "provider.frame", ["connectionId"] = connectionId, ["frame"] = frame })));
        }
        // The native parent must ignore inherited Node execution options.
        var originalOptions = Environment.GetEnvironmentVariable("NODE_OPTIONS");
        Environment.SetEnvironmentVariable("NODE_OPTIONS", "--invalid-inherited-option");
        using var process = new SharedBrowserHost(start, message =>
        {
            var frame = message["frame"]!.AsObject();
            var id = frame["id"]?.DeepClone();
            if (frame["type"]?.GetValue<string>() == "session.open") Post(new JsonObject { ["type"] = "session.opened", ["id"] = id });
            if (frame["type"]?.GetValue<string>() == "session.command")
            {
                Interlocked.Increment(ref commands);
                if (!suppress) Post(new JsonObject { ["type"] = "session.result", ["id"] = id,
                    ["cmdId"] = frame["cmdId"]!.DeepClone(), ["sessionId"] = frame["sessionId"]?.DeepClone(),
                    ["result"] = new JsonObject { ["nativeFixture"] = true } });
            }
        }, frame =>
        {
            Require(frame["authorityId"]!.GetValue<string>() == "fixture-native-owner", "native owner handle preserved");
            if (frame["phase"]?.GetValue<string>() == "result" && frame["delivery"]?.GetValue<string>() == "unknown") Interlocked.Increment(ref unknown);
            return nativeAllowed;
        }, () => failure = true);
        Environment.SetEnvironmentVariable("NODE_OPTIONS", originalOptions);
        host = process;
        var attachment = host.Call(new JsonObject { ["method"] = "browser.attach", ["extensionId"] = new string('a', 32),
            ["hello"] = new JsonObject { ["protocolVersion"] = 1, ["extensionVersion"] = "fixture", ["profile"] = new JsonObject
            { ["protocolVersion"] = 1, ["installationId"] = "00000000-0000-4000-8000-000000000001", ["name"] = "Fixture", ["enabled"] = true } } });
        connectionId = attachment["connectionId"]!.GetValue<string>();
        var profileId = attachment["profileId"]!.GetValue<string>();
        host.Call(new JsonObject { ["method"] = "operator.configure", ["scopes"] = new JsonArray("devtools"),
            ["profileIds"] = new JsonArray(profileId), ["durationMs"] = 60000 });
        JsonObject Endpoint() => host.Call(new JsonObject { ["method"] = "browser.call", ["requestId"] = Guid.NewGuid().ToString("n"),
            ["authorityId"] = "fixture-native-owner", ["request"] = new JsonObject { ["operation"] = "browser.endpoint", ["browserProfileId"] = profileId } });
        var endpoint = Endpoint();
        Require(endpoint["accepted"]!.GetValue<bool>(), "shared endpoint accepted");
        var uri = new Uri(endpoint["data"]!["browserEndpoint"]!.GetValue<string>());
        Require(Endpoint()["data"]!["browserEndpoint"]!.GetValue<string>() == uri.ToString(), "same owner endpoint reused");
        using var timeout = new CancellationTokenSource(TimeSpan.FromSeconds(20));
        using (var socket = new ClientWebSocket())
        {
            socket.Options.Proxy = null;
            await socket.ConnectAsync(uri, timeout.Token);
            await socket.SendAsync(Encoding.UTF8.GetBytes("{\"id\":7,\"method\":\"Runtime.enable\",\"sessionId\":\"mc-session-1\"}"), WebSocketMessageType.Text, true, timeout.Token);
            var bytes = new byte[4096];
            var response = await socket.ReceiveAsync(bytes.AsMemory(), timeout.Token);
            var reply = JsonNode.Parse(bytes.AsSpan(0, response.Count))!;
            Require(reply["id"]!.GetValue<int>() == 7 && reply["sessionId"]!.GetValue<string>() == "mc-session-1", "subsession result correlated");
            Require(commands == 1, "one provider dispatch");
            suppress = true;
            await socket.SendAsync(Encoding.UTF8.GetBytes("{\"id\":8,\"method\":\"Runtime.enable\"}"), WebSocketMessageType.Text, true, timeout.Token);
            while (commands != 2) await Task.Delay(10, timeout.Token);
            nativeAllowed = false;
            try
            {
                var closed = await socket.ReceiveAsync(bytes.AsMemory(), timeout.Token);
                Require(closed.MessageType == WebSocketMessageType.Close, "native owner loss closes stream");
            }
            catch (WebSocketException) { }
            while (unknown == 0) await Task.Delay(10, timeout.Token);
        }
        host.Call(new JsonObject { ["method"] = "operator.stop" });
        using (var stale = new ClientWebSocket())
        {
            stale.Options.Proxy = null;
            try { await stale.ConnectAsync(uri, timeout.Token); throw new Exception("stale endpoint accepted"); }
            catch (WebSocketException) { }
        }
        Require(!failure, "native IPC remained healthy");
        lock (calls) Task.WaitAll(calls.ToArray(), timeout.Token);
        Console.WriteLine("Shared browser/native IPC contracts passed");
    }
}
