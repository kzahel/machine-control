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
        await SyncWithoutPoolProcess();
        BlockedWriter();
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
                if (!suppress) Post(new JsonObject
                {
                    ["type"] = "session.result",
                    ["id"] = id,
                    ["cmdId"] = frame["cmdId"]!.DeepClone(),
                    ["sessionId"] = frame["sessionId"]?.DeepClone(),
                    ["result"] = new JsonObject { ["nativeFixture"] = true }
                });
            }
        }, frame =>
        {
            Require(frame["authorityId"]!.GetValue<string>() == "fixture-native-owner", "native owner handle preserved");
            if (frame["phase"]?.GetValue<string>() == "result" && frame["delivery"]?.GetValue<string>() == "unknown") Interlocked.Increment(ref unknown);
            return nativeAllowed;
        }, () => failure = true);
        Environment.SetEnvironmentVariable("NODE_OPTIONS", originalOptions);
        host = process;
        // Native Allow/Stop and expiry can call the private client from a
        // WinForms STA. A synchronous call cannot depend on that UI thread
        // pumping its captured continuations while it waits for the reply.
        await Task.Factory.StartNew(() =>
        {
            SynchronizationContext.SetSynchronizationContext(new UnpumpedContext());
            host.Call(new JsonObject { ["method"] = "state" });
        }, CancellationToken.None, TaskCreationOptions.LongRunning, TaskScheduler.Default)
            .WaitAsync(TimeSpan.FromSeconds(3));
        var attachment = host.Call(new JsonObject
        {
            ["method"] = "browser.attach",
            ["extensionId"] = new string('a', 32),
            ["hello"] = new JsonObject
            {
                ["protocolVersion"] = 1,
                ["extensionVersion"] = "fixture",
                ["profile"] = new JsonObject
                { ["protocolVersion"] = 1, ["installationId"] = "00000000-0000-4000-8000-000000000001", ["name"] = "Fixture", ["enabled"] = true }
            }
        });
        connectionId = attachment["connectionId"]!.GetValue<string>();
        var profileId = attachment["profileId"]!.GetValue<string>();
        host.Call(new JsonObject
        {
            ["method"] = "operator.configure",
            ["scopes"] = new JsonArray("devtools"),
            ["profileIds"] = new JsonArray(profileId),
            ["durationMs"] = 60000
        });
        JsonObject Endpoint() => host.Call(new JsonObject
        {
            ["method"] = "browser.call",
            ["ownerSession"] = "fixture-owner",
            ["ownerProfileIds"] = new JsonArray(profileId),
            ["requestId"] = Guid.NewGuid().ToString("n"),
            ["authorityId"] = "fixture-native-owner",
            ["request"] = new JsonObject { ["operation"] = "browser.endpoint", ["browserProfileId"] = profileId }
        });
        var checkpoint = host.Call(new JsonObject { ["method"] = "operator.checkpoint" });
        host.Call(new JsonObject { ["method"] = "operator.configure", ["scopes"] = new JsonArray(), ["profileIds"] = new JsonArray(), ["durationMs"] = 1000 });
        Require(host.State["effectiveScopes"]!.AsArray().Count == 0, "temporary non-browser selection has no browser authority");
        host.Call(new JsonObject { ["method"] = "operator.restore", ["checkpointId"] = checkpoint["checkpointId"]!.DeepClone() });
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
        // An unsettled ordinary provider call gives a deterministic private
        // IPC timeout. Preserve its method in payload-free fault diagnostics.
        host.Call(new JsonObject
        {
            ["method"] = "operator.configure",
            ["scopes"] = new JsonArray("browser"),
            ["profileIds"] = new JsonArray(profileId),
            ["durationMs"] = 60000
        });
        try
        {
            host.Call(new JsonObject
            {
                ["method"] = "browser.call",
                ["ownerSession"] = "fixture-owner",
                ["ownerProfileIds"] = new JsonArray(profileId),
                ["requestId"] = "fixture-stalled-provider",
                ["authorityId"] = "fixture-native-owner",
                ["request"] = new JsonObject { ["operation"] = "browser.tabs", ["browserProfileId"] = profileId }
            }, 100);
            throw new Exception("Stalled private IPC unexpectedly completed");
        }
        catch (TimeoutException error)
        {
            Require(error.Message.Contains("browser.call") && host.FailureMethod == "browser.call" &&
                host.Failure == "ipc_reply_timeout" && failure, "private timeout identifies its method and fails closed");
        }
        Console.WriteLine("Shared browser/native IPC contracts passed");
    }

    private static async Task SyncWithoutPoolProcess()
    {
        var start = new ProcessStartInfo(Environment.ProcessPath!) { RedirectStandardOutput = true, RedirectStandardError = true };
        if (Path.GetFileNameWithoutExtension(Environment.ProcessPath) == "dotnet")
            start.ArgumentList.Add(typeof(BrowserDevToolsFixtures).Assembly.Location);
        start.ArgumentList.Add("--sync-ipc-without-pool");
        using var process = Process.Start(start)!;
        var output = process.StandardOutput.ReadToEndAsync();
        var error = process.StandardError.ReadToEndAsync();
        try { await process.WaitForExitAsync().WaitAsync(TimeSpan.FromSeconds(15)); }
        catch { process.Kill(entireProcessTree: true); throw; }
        Require(process.ExitCode == 0, "synchronous IPC under pool pressure: " + await error + await output);
    }

    internal static void SyncWithoutPool()
    {
        Require(ThreadPool.SetMinThreads(1, 1) && ThreadPool.SetMaxThreads(1, 1), "isolated worker-pool limit");
        using var occupied = new ManualResetEventSlim();
        using var release = new ManualResetEventSlim();
        var blocker = Task.Run(() => { occupied.Set(); release.Wait(); });
        occupied.Wait();
        // An OS thread releases the worker even if the old implementation
        // deadlocks. The private child and all three I/O directions are owned.
        var watchdog = new Thread(() => { if (!release.Wait(TimeSpan.FromSeconds(6))) release.Set(); });
        watchdog.Start();
        var timer = Stopwatch.StartNew();
        try
        {
            var start = new ProcessStartInfo(Environment.GetEnvironmentVariable("MACHINE_CONTROL_NODE") ?? "node");
            start.ArgumentList.Add(Path.GetFullPath("runtime/node/main.ts"));
            using var host = new SharedBrowserHost(start, _ => { }, _ => false, () => { });
            host.Call(new JsonObject { ["method"] = "state" });
            Require(timer.Elapsed < TimeSpan.FromSeconds(4), "sync reply must not require a free pool worker");
            var admission = new AccessAdmission();
            admission.Register("desktop", true);
            admission.SetInputReady(true);
            admission.Bind(frame => host.Call(frame));
            admission.Configure("desktop", "automatic", 60, []);
            admission.Notice(0);
            var offer = (JsonObject)admission.Submit("fixture", "loss", ["desktop"], 60, 60, "Policy-loss fixture");
            var id = offer["intentId"]!.GetValue<string>();
            var active = (JsonObject)admission.Accept("fixture", id, offer["offerGeneration"]!.GetValue<long>());
            var generations = active["resourceGenerations"]!.AsObject().ToDictionary(pair => pair.Key, pair => pair.Value!.GetValue<long>());
            host.Dispose();
            Require(admission.Authorize("fixture", id, active["sessionId"]!.GetValue<string>(), generations) == "control_policy_unavailable",
                "first authorization after policy loss fences the owner");
            Require(((JsonObject)admission.Status())["available"]!.GetValue<bool>() == false && !admission.Enabled("desktop") &&
                !admission.HasActiveSession && !admission.Reserved && admission.Blocks("desktop").Contains("control_policy_unavailable"),
                "policy loss retains native status without authority");
        }
        finally { release.Set(); watchdog.Join(); blocker.GetAwaiter().GetResult(); }
    }

    private static void BlockedWriter()
    {
        // The child acknowledges its private handshake, then stops consuming
        // stdin. A frame larger than the pipe buffer must fail closed without
        // blocking disposal or depending on OS cancellation of a partial write.
        var start = new ProcessStartInfo(Environment.GetEnvironmentVariable("MACHINE_CONTROL_NODE") ?? "node");
        start.ArgumentList.Add("--input-type=module");
        start.ArgumentList.Add("--eval");
        start.ArgumentList.Add("""
            import fs from 'node:fs';
            const read = size => { const b = Buffer.alloc(size); let n = 0;
              while (n < size) { const got = fs.readSync(0, b, n, size-n, null); if (!got) process.exit(1); n += got; } return b; };
            const hello = JSON.parse(read(read(4).readUInt32LE()).toString());
            const body = Buffer.from(JSON.stringify({type:'reply', id:hello.id, ok:true, data:{}}));
            const header = Buffer.alloc(4); header.writeUInt32LE(body.length);
            fs.writeSync(1, header); fs.writeSync(1, body);
            setInterval(() => {}, 1000);
            """);
        var failed = false;
        using var host = new SharedBrowserHost(start, _ => { }, _ => false, () => failed = true);
        var timer = Stopwatch.StartNew();
        try
        {
            host.Call(new JsonObject { ["method"] = "fixture.blocked_write", ["padding"] = new string('x', 1024 * 1024) });
            throw new Exception("Blocked private write unexpectedly completed");
        }
        catch (IOException)
        {
            Require(failed && !host.Alive && host.Failure == "ipc_write_timeout" &&
                host.FailureMethod == "fixture.blocked_write", "blocked writer kills its exact child and classifies unknown delivery");
            Require(timer.Elapsed < TimeSpan.FromSeconds(6), "blocked writer has a finite deadline");
        }
        timer.Restart();
        host.Dispose();
        Require(timer.Elapsed < TimeSpan.FromSeconds(2), "disposal cannot wait behind a blocked write");
    }

    private sealed class UnpumpedContext : SynchronizationContext
    {
        public override void Post(SendOrPostCallback callback, object? state) { }
    }
}
