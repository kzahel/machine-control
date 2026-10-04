using System.IO;
using System.Net;
using System.Net.Sockets;
using System.Text;
using System.Text.Json.Nodes;
using MachineControl.Windows;

internal static class AdmissionChannelFixtures
{
    internal static async Task RunAsync()
    {
        var order = new AdmissionRequestOrder();
        Require(order.Accept(new() { ["requestId"] = "open" }), "Legacy opening accepted");
        for (var sequence = 1; sequence <= 72000; sequence++)
            Require(order.Accept(new() { ["requestId"] = "bounded-label", ["requestSequence"] = (long)sequence }), "Ordered wait exceeds legacy budget");
        Require(!order.Accept(new() { ["requestId"] = "replay", ["requestSequence"] = 72000L }), "Replay refused");
        Require(!order.Accept(new() { ["requestId"] = "gap", ["requestSequence"] = 72002L }), "Gap refused");
        Require(!order.Accept(new() { ["requestId"] = "downgrade" }), "Downgrade refused");
        Require(!order.Accept(new() { ["requestId"] = "boolean", ["requestSequence"] = true }), "Boolean refused");
        Require(order.Accept(new() { ["requestId"] = "next", ["requestSequence"] = 72001L }), "Next frame remains valid");
        var clock = new TestTime();
        var grants = new DesktopGrants(clock); grants.SetReady(true); grants.Arm(["observe", "control"], 900);
        foreach (var operation in new[] { "snapshot", "type", "app.launch", "screenshot" })
            Require(grants.Authorize(new Request { Operation = operation }) == "control_session_required", "Idle grant cannot authorize unowned " + operation);
        var requirement = JsonNode.Parse(Contract.Serialize(DesktopGrants.RefusalData("type", "control_session_required")))!;
        Require(requirement["controlSession"]!["schema"]!.GetValue<string>() == AccessAdmission.Schema &&
            requirement["controlSession"]!["scope"]!.GetValue<string>() == "control", "Typed CLI handoff");
        var browserGrants = new DesktopGrants(clock); browserGrants.SetReady(true); browserGrants.Arm(["devtools"], 900);
        Require(browserGrants.AdmissionAuthority(["browser"]) is null, "Devtools grant covers browser admission");
        Require(browserGrants.Authorize(new Request { Operation = "browser.tabs" }) == "control_session_required", "Browser grant still needs owner");
        var effects = 0;
        ControlOwnership? lastFence = null;
        using var stop = new CancellationTokenSource(TimeSpan.FromSeconds(15));
        var listener = new TcpListener(IPAddress.Loopback, 0); listener.Start();
        var owners = new List<Task>();
        var clients = new List<TcpClient>();
        async Task<(StreamReader Reader, StreamWriter Writer, JsonObject View)> Open(string id)
        {
            var client = new TcpClient(); clients.Add(client);
            await client.ConnectAsync((IPEndPoint)listener.LocalEndpoint, stop.Token);
            var resident = await listener.AcceptTcpClientAsync(stop.Token);
            var opening = new JsonObject
            {
                ["operation"] = "control.open",
                ["schema"] = AccessAdmission.Schema,
                ["requestId"] = id,
                ["reason"] = "fixture",
                ["durationSeconds"] = 60,
                ["waitSeconds"] = 120,
                ["scopes"] = new JsonArray("observe", "control")
            };
            owners.Add(Task.Run(async () =>
            {
                using (resident)
                using (var reader = new StreamReader(resident.GetStream(), Encoding.UTF8, false, 4096, leaveOpen: true))
                    await AdmissionChannel.RunAsync(resident.GetStream(), reader, opening, grants, (request, fence, cancellation) =>
                    {
                        var denied = grants.Authorize(request with { ControlOwnership = fence });
                        if (denied is not null) return Task.FromResult(new Result { Operation = request.Operation, RequestId = request.RequestId!, ErrorCode = denied });
                        lastFence = fence;
                        Interlocked.Increment(ref effects);
                        return Task.FromResult(new Result { Operation = request.Operation, RequestId = request.RequestId!, Accepted = true, Delivery = "confirmed", Effect = "observed" });
                    }, stop.Token, noticeSeconds: 0);
            }));
            var readerClient = new StreamReader(client.GetStream());
            var writerClient = new StreamWriter(client.GetStream(), new UTF8Encoding(false)) { AutoFlush = true };
            var first = JsonNode.Parse(await readerClient.ReadLineAsync(stop.Token) ?? "")!.AsObject();
            Require(first["accepted"]!.GetValue<bool>(), "Open accepted");
            return (readerClient, writerClient, first["data"]!.AsObject());
        }
        async Task<JsonObject> Call((StreamReader Reader, StreamWriter Writer, JsonObject View) client, string op, JsonObject? request = null)
        {
            request ??= new(); request["operation"] = op; request["requestId"] = Guid.NewGuid().ToString("n");
            await client.Writer.WriteLineAsync(request.ToJsonString());
            return JsonNode.Parse(await client.Reader.ReadLineAsync(stop.Token) ?? "")!.AsObject();
        }
        try
        {
            var a = await Open("first"); var b = await Open("second");
            Require(a.View["requestSequencing"]!.GetValue<string>() == "strict", "Ordered capability negotiated");
            Require(a.View["state"]!.GetValue<string>() == "offered", "First owner offered");
            Require(b.View["state"]!.GetValue<string>() == "waiting_for_resource", "Second owner waits");
            var active = (await Call(a, "control.accept", new() { ["offerGeneration"] = a.View["offerGeneration"]!.DeepClone() }))["data"]!.AsObject();
            JsonObject Action() => new()
            {
                ["sessionId"] = active["sessionId"]!.DeepClone(),
                ["resourceGenerations"] = active["resourceGenerations"]!.DeepClone(),
                ["request"] = new JsonObject { ["operation"] = "type", ["text"] = "fixture" }
            };
            Require(!(await Call(b, "control.dispatch", Action()))["accepted"]!.GetValue<bool>() && effects == 0, "Other owner cannot borrow fence");
            Require((await Call(a, "control.dispatch", Action()))["accepted"]!.GetValue<bool>() && effects == 1, "Owned effect observed");
            Require(grants.Authorize("type") == "control_session_required", "Legacy callers cannot borrow holder");
            var forged = Contract.ParseRequest("{\"operation\":\"type\",\"controlOwnership\":{\"owner\":\"forged\"}}");
            Require(forged.ControlOwnership is null && grants.Authorize(forged) == "control_session_required", "JSON cannot supply native owner context");
            grants.Pause();
            Require(!(await Call(a, "control.dispatch", Action()))["accepted"]!.GetValue<bool>() && effects == 1, "Paused effect refused");
            grants.Resume();
            var next = (await Call(b, "control.status"))["data"]!.AsObject();
            Require(next["state"]!.GetValue<string>() == "offered", "Pause yields position");
            clock.Advance(15);
            Require(!(await Call(b, "control.accept", new() { ["offerGeneration"] = next["offerGeneration"]!.DeepClone() }))["accepted"]!.GetValue<bool>(), "Late accept refused");
            Require(effects == 1, "No effect from late offer");
            await Call(b, "control.cancel");
            await Call(a, "control.cancel");
            var c = await Open("disconnecting"); var d = await Open("successor");
            active = (await Call(c, "control.accept", new() { ["offerGeneration"] = c.View["offerGeneration"]!.DeepClone() }))["data"]!.AsObject();
            Require((await Call(c, "control.dispatch", Action()))["accepted"]!.GetValue<bool>(), "New owner dispatches");
            var oldFence = lastFence!;
            clients[2].Dispose();
            await owners[2];
            var offered = (await Call(d, "control.status"))["data"]!.AsObject();
            Require(offered["state"]!.GetValue<string>() == "offered", "EOF releases owner promptly");
            active = (await Call(d, "control.accept", new() { ["offerGeneration"] = offered["offerGeneration"]!.DeepClone() }))["data"]!.AsObject();
            Require(grants.Authorize(new Request { Operation = "type", ControlOwnership = oldFence }) is not null, "Disconnected owner cannot borrow replacement");
            Require((await Call(d, "control.dispatch", Action()))["accepted"]!.GetValue<bool>() && effects == 3, "Replacement owner alone dispatches");
            clock.Advance(6);
            Require(!(await Call(d, "control.dispatch", Action()))["accepted"]!.GetValue<bool>() && effects == 3, "Expired heartbeat refuses before effect");
        }
        finally
        {
            foreach (var client in clients) client.Dispose();
            listener.Stop();
            foreach (var owner in owners) try { await owner; } catch (OperationCanceledException) { } catch (IOException) { }
        }
        Require(grants.Admission.Status() is not null, "Disconnect cleanup accessible");
        Console.WriteLine("Admission live transport fixtures passed");
    }
    private static void Require(bool value, string message) { if (!value) throw new Exception(message); }
}
