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
        var clock = new TestTime();
        var grants = new DesktopGrants(clock); grants.SetReady(true); grants.Arm(["observe", "control"], 900);
        var effects = 0;
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
