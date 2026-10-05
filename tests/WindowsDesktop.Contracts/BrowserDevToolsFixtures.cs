using System.IO;
using System.Net.Sockets;
using System.Net.WebSockets;
using System.Text;
using System.Text.Json;
using System.Text.Json.Nodes;
using MachineControl.Windows;

internal static class BrowserDevToolsFixtures
{
    private static void Require(bool value, string label)
    {
        if (!value) throw new Exception("Streaming CDP: " + label);
    }

    internal static async Task RunAsync()
    {
        var clock = new TestTime();
        var journalRoot = Path.Combine(Path.GetTempPath(), "mc-cdp-" + Guid.NewGuid().ToString("n"));
        var journal = new DesktopJournal(journalRoot);
        var grants = new DesktopGrants(clock, journal); grants.SetReady(true); grants.Arm(["devtools"], 300);
        var provider = new Provider();
        using var bridge = new BrowserDevToolsBridge(grants, provider);
        using var stop = new CancellationTokenSource(TimeSpan.FromSeconds(30));
        var server = bridge.RunAsync(stop.Token);
        var owner = "fixture-owner";
        Request Owned()
        {
            var offered = JsonSerializer.SerializeToNode(grants.Admission.Submit(owner, Guid.NewGuid().ToString("n"),
                ["desktop"], 60, 60, "fixture", () => grants.AdmissionAuthority(["devtools"])), Contract.Json)!;
            var active = JsonSerializer.SerializeToNode(grants.Admission.Accept(owner, offered["intentId"]!.GetValue<string>(),
                offered["offerGeneration"]!.GetValue<long>()), Contract.Json)!;
            return new Request
            {
                Operation = "browser.endpoint",
                ControlOwnership = new(owner,
                active["intentId"]!.GetValue<string>(), active["sessionId"]!.GetValue<string>(),
                JsonSerializer.Deserialize<Dictionary<string, long>>(active["resourceGenerations"]!.ToJsonString())!)
            };
        }
        Result Envelope() => new() { Operation = "browser.endpoint", RequestId = "endpoint" };
        Uri Endpoint(Request request)
        {
            var result = bridge.Endpoint(request, Envelope());
            Require(result.Accepted, "owned endpoint accepted");
            Require(journal.Begin("browser.endpoint", result.RequestId) && journal.Record(result), "endpoint metadata audited");
            var data = JsonSerializer.SerializeToNode(result.Data, Contract.Json)!;
            return new Uri(data["devtoolsEndpoint"]!.GetValue<string>().Replace("<tabId>", "1"));
        }
        async Task<WebSocket> Connect(Uri uri, bool waitForCleanup = true)
        {
            var deadline = Environment.TickCount64 + 3000;
            while (true)
            {
                var socket = new ClientWebSocket();
                try { await socket.ConnectAsync(uri, stop.Token); return socket; }
                catch (WebSocketException) when (waitForCleanup && Environment.TickCount64 < deadline)
                {
                    socket.Dispose(); await Task.Delay(10, stop.Token);
                }
                catch { socket.Dispose(); throw; }
            }
        }
        async Task Refuse(Uri uri)
        {
            try { using var socket = await Connect(uri, false); throw new Exception("Stale endpoint connected"); }
            catch (WebSocketException) { }
        }
        async Task Closed(WebSocket socket)
        {
            using var deadline = new CancellationTokenSource(TimeSpan.FromSeconds(3));
            try
            {
                var reply = await socket.ReceiveAsync(new byte[1024].AsMemory(), deadline.Token);
                Require(reply.MessageType == WebSocketMessageType.Close, "revoked socket closed");
            }
            catch (WebSocketException) { }
        }
        async Task<JsonObject> Read(WebSocket socket)
        {
            var bytes = new byte[4096];
            var received = await socket.ReceiveAsync(bytes.AsMemory(), stop.Token);
            Require(received.EndOfMessage, "bounded fixture response");
            return JsonNode.Parse(bytes.AsSpan(0, received.Count))!.AsObject();
        }
        async Task Send(WebSocket socket, string command) => await socket.SendAsync(Encoding.UTF8.GetBytes(command).AsMemory(),
            WebSocketMessageType.Text, true, stop.Token);
        try
        {
            Require(DesktopGrants.ScopeFor("browser.endpoint") == "devtools" && BrowserWire.Operations.Contains("browser.endpoint"), "advertised devtools operation");
            Require(bridge.Endpoint(new Request { Operation = "browser.endpoint" }, Envelope()).ErrorCode == "control_session_required", "unowned grant refused");
            var request = Owned();
            var uri = Endpoint(request);
            for (var i = 0; i < 20; i++) Require(Endpoint(request with
            {
                ControlOwnership = request.ControlOwnership! with
                {
                    Generations = new(request.ControlOwnership.Generations)
                }
            }) == uri, "same owner reuses endpoint without consuming capacity");
            var starts = provider.Opens;
            await Refuse(new Uri(uri.AbsoluteUri[..^64] + new string('0', 64)));
            await Refuse(new Uri(uri.AbsoluteUri.Replace("/page/1?", "/page/0?")));
            using (var origin = new ClientWebSocket())
            {
                origin.Options.SetRequestHeader("Origin", "https://fixture.invalid");
                try { await origin.ConnectAsync(uri, stop.Token); throw new Exception("Origin admitted"); }
                catch (WebSocketException) { }
            }
            foreach (var extra in new[] { "Origin: \r\n", "Host: duplicate\r\n", "Content-Length: 0\r\n", "Transfer-Encoding: chunked\r\n" })
            {
                using var client = new TcpClient(); await client.ConnectAsync("127.0.0.1", bridge.Port, stop.Token);
                var bytes = Encoding.ASCII.GetBytes($"GET {uri.PathAndQuery} HTTP/1.1\r\nHost: 127.0.0.1:{bridge.Port}\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Version: 13\r\nSec-WebSocket-Key: AAAAAAAAAAAAAAAAAAAAAA==\r\n{extra}\r\n");
                await client.GetStream().WriteAsync(bytes, stop.Token);
                Require(await client.GetStream().ReadAsync(new byte[1024], stop.Token) == 0, "malformed handshake refused");
            }
            Require(provider.Opens == starts && provider.Commands == 0, "unauthenticated handshakes have no provider effects");
            using (var socket = await Connect(uri))
            {
                await Send(socket, "{\"id\":1,\"method\":\"Runtime.evaluate\",\"params\":{\"expression\":\"fixture-secret\"}}");
                Require((await Read(socket))["id"]!.GetValue<int>() == 1, "raw CDP result correlated");
                Require((await Read(socket))["method"]!.GetValue<string>() == "Runtime.consoleAPICalled", "raw CDP event streamed");
                await Refuse(uri);
                Require(provider.Commands == 1, "second connection to same tab refused");
                grants.Pause(); await Closed(socket); await Refuse(uri);
            }
            grants.Resume(); grants.Admission.Disconnect(owner);
            request = Owned(); var next = Endpoint(request);
            Require(next != uri, "new owner generation rotates endpoint"); await Refuse(uri);
            using (var socket = await Connect(next))
            {
                await Send(socket, "{\"id\":1,\"method\":\"Runtime.evaluate\",\"sessionId\":\"forged\"}");
                await Closed(socket); Require(provider.Commands == 1, "invalid frame refused before dispatch");
            }
            // Wait for provider cleanup before intentionally reconnecting.
            for (var i = 0; i < 100 && provider.Closes < 2; i++) await Task.Delay(10);
            using (var socket = await Connect(next))
            {
                provider.Generation = "replacement";
                await Closed(socket); await Refuse(next);
            }
            next = Endpoint(request);
            using (var socket = await Connect(next))
            {
                provider.Connected = false; await Closed(socket); await Refuse(next);
                provider.Connected = true; await Refuse(next);
            }
            next = Endpoint(request);
            using (var socket = await Connect(next))
            {
                // A read-only sharing lease deterministically refuses append
                // without racing directory rename against Windows scanners.
                if (OperatingSystem.IsWindows())
                {
                    FileStream? readLease = null;
                    for (var i = 0; i < 100 && readLease is null; i++)
                    {
                        try
                        {
                            readLease = new FileStream(Directory.GetFiles(Path.Combine(journalRoot, "audit")).Single(),
                            FileMode.Open, FileAccess.Read, FileShare.Read);
                        }
                        catch (IOException) { await Task.Delay(10, stop.Token); }
                    }
                    Require(readLease is not null, "audit sharing lease acquired");
                    using (readLease)
                    {
                        Require(!journal.Begin("browser.cdp", "blocked"), "audit outage detected");
                        await Closed(socket); await Refuse(next);
                    }
                }
                else
                {
                    Directory.Move(journalRoot, journalRoot + "-saved"); File.WriteAllText(journalRoot, "blocked");
                    Require(!journal.Begin("browser.cdp", "blocked"), "audit outage detected");
                    await Closed(socket); await Refuse(next);
                    File.Delete(journalRoot); Directory.Move(journalRoot + "-saved", journalRoot);
                }
                Require(journal.Event("storage.recovered"), "audit recovered");
                await Refuse(next);
            }
            request = Owned();
            next = Endpoint(request);
            foreach (var malformed in new[] { "{\"id\":1,\"id\":2,\"method\":\"Runtime.enable\"}", new string('x', BrowserWire.MaximumOutput) })
            {
                using var socket = await Connect(next);
                try { await Send(socket, malformed); } catch (WebSocketException) { }
                await Closed(socket);
                Require(provider.Commands == 1, "duplicate keys and oversized frames refused before provider dispatch");
            }
            using (var socket = await Connect(next))
            {
                await socket.SendAsync(new byte[] { 1 }.AsMemory(), WebSocketMessageType.Binary, true, stop.Token);
                await Closed(socket); Require(provider.Commands == 1, "binary frame refused");
            }
            provider.SuppressResults = true;
            using (var socket = await Connect(next))
            {
                await Send(socket, "{\"id\":5,\"method\":\"Runtime.enable\"}");
                await Send(socket, "{\"id\":5,\"method\":\"Runtime.enable\"}");
                await Closed(socket); Require(provider.Commands == 2, "duplicate outstanding id has no second dispatch");
            }
            using (var socket = await Connect(next))
            {
                for (var i = 0; i < 17; i++) await Send(socket, $"{{\"id\":{i},\"method\":\"Runtime.enable\"}}");
                await Closed(socket); Require(provider.Commands == 18, "outstanding-command bound prevents seventeenth dispatch");
            }
            provider.SuppressResults = false;
            using (var socket = await Connect(next))
            {
                grants.Admission.Disconnect(owner); await Closed(socket); await Refuse(next);
            }
            request = Owned(); next = Endpoint(request);
            using (var socket = await Connect(next))
            {
                grants.Stop("fixture"); await Closed(socket); await Refuse(next);
            }
            grants.Arm(["devtools"], 60); request = Owned(); next = Endpoint(request);
            using (var socket = await Connect(next))
            {
                clock.Advance(61); await Closed(socket); await Refuse(next);
            }
            foreach (var json in new[] { "{}", "{\"id\":true,\"method\":\"Runtime.enable\"}", "{\"id\":-1,\"method\":\"Runtime.enable\"}",
                "{\"id\":1,\"method\":\"Runtime.enable\",\"params\":null}", "{\"id\":1,\"method\":\"bad\"}" })
                Require(!BrowserDevToolsBridge.ValidCommand(JsonNode.Parse(json)!.AsObject()), "invalid command contract");
            Require(provider.Commands == 18, "authority transitions never replay effects");
            var audit = Contract.Serialize(journal.Preview());
            Require(audit.Contains("browser.endpoint") && audit.Contains("browser.cdp") && audit.Contains("browser_completion_not_observed"), "endpoint and uncertain raw commands audited");
            Require(!audit.Contains("fixture-secret") && !audit.Contains("Runtime.evaluate") &&
                !audit.Contains(uri.Query[7..]), "tokens, methods and params excluded from audit");
        }
        finally
        {
            stop.Cancel(); await server;
            try { provider.EmitLateFrame(); }
            finally
            {
                if (File.Exists(journalRoot)) File.Delete(journalRoot);
                if (Directory.Exists(journalRoot)) Directory.Delete(journalRoot, true);
                if (Directory.Exists(journalRoot + "-saved")) Directory.Delete(journalRoot + "-saved", true);
            }
        }
        Console.WriteLine("Windows streaming CDP contracts passed");
    }

    private sealed class Provider : IBrowserDevToolsProvider
    {
        public bool Connected { get; set; } = true;
        public string Generation { get; set; } = "first";
        internal int Opens, Commands, Closes;
        internal bool SuppressResults;
        private Action<JsonObject>? _receive;
        internal void EmitLateFrame() => _receive!(new() { ["type"] = "session.closed" });
        public Task OpenAsync(string id, int tabId, Request authority, string generation, string providerGeneration,
            Action<JsonObject> receive, CancellationToken cancellation)
        {
            Interlocked.Increment(ref Opens); _receive = receive;
            receive(new() { ["type"] = "session.opened" }); return Task.CompletedTask;
        }
        public Task CommandAsync(string id, JsonObject command, Request authority, string generation,
            string providerGeneration, CancellationToken cancellation)
        {
            Interlocked.Increment(ref Commands);
            if (SuppressResults) return Task.CompletedTask;
            _receive!(new() { ["type"] = "session.result", ["cmdId"] = command["id"]!.DeepClone(), ["result"] = new JsonObject() });
            _receive(new() { ["type"] = "session.event", ["method"] = "Runtime.consoleAPICalled", ["params"] = new JsonObject() });
            return Task.CompletedTask;
        }
        public Task CloseAsync(string id, string providerGeneration) { Interlocked.Increment(ref Closes); return Task.CompletedTask; }
    }
}
