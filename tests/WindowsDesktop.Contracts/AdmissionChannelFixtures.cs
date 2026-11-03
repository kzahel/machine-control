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
        var grants = TestBrowserProjection.Create(clock); grants.SetReady(true); grants.PrepareConsole(true); grants.Arm(["observe", "control"], 900);
        foreach (var operation in new[] { "snapshot", "type", "app.launch", "screenshot", "uac.respond" })
            Require(grants.Authorize(new Request { Operation = operation }) == "control_session_required", "Idle grant cannot authorize unowned " + operation);
        var requirement = JsonNode.Parse(Contract.Serialize(DesktopGrants.RefusalData("type", "control_session_required")))!;
        Require(requirement["controlSession"]!["schema"]!.GetValue<string>() == AccessAdmission.Schema &&
            requirement["controlSession"]!["scope"]!.GetValue<string>() == "control", "Typed CLI handoff");
        var browserGrants = TestBrowserProjection.Create(clock); browserGrants.SetReady(true); browserGrants.Arm(["devtools"], 900);
        Require(browserGrants.AdmissionAuthority(["browser"]) is null, "Devtools grant covers browser admission");
        Require(browserGrants.Authorize(new Request { Operation = "browser.tabs" }) == "control_session_required", "Browser grant still needs owner");
        var effects = 0;
        var boundaryDispatch = new TaskCompletionSource(TaskCreationOptions.RunContinuationsAsynchronously);
        var providerStarted = new TaskCompletionSource(TaskCreationOptions.RunContinuationsAsynchronously);
        var heldProvider = new TaskCompletionSource<Result>(TaskCreationOptions.RunContinuationsAsynchronously);
        var replyBoundaries = new List<ReplyBoundaryStream>();
        ControlOwnership? lastFence = null;
        using var stop = new CancellationTokenSource(TimeSpan.FromSeconds(15));
        var listener = new TcpListener(IPAddress.Loopback, 0); listener.Start();
        var owners = new List<Task>();
        var clients = new List<TcpClient>();
        async Task<(StreamReader Reader, StreamWriter Writer, JsonObject View)> Open(string id, bool prepared = false)
        {
            var client = new TcpClient(); clients.Add(client);
            await client.ConnectAsync((IPEndPoint)listener.LocalEndpoint, stop.Token);
            var resident = await listener.AcceptTcpClientAsync(stop.Token);
            var boundary = new ReplyBoundaryStream(resident.GetStream());
            replyBoundaries.Add(boundary);
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
            if (prepared) opening["preparedConsole"] = true;
            owners.Add(Task.Run(async () =>
            {
                using (resident)
                using (var reader = new StreamReader(resident.GetStream(), Encoding.UTF8, false, 4096, leaveOpen: true))
                    await AdmissionChannel.RunAsync(boundary, reader, opening, grants, (request, fence, cancellation) =>
                    {
                        if (request.RequestId == "after-visible-result") boundaryDispatch.TrySetResult();
                        if (request.RequestId == "held-provider") { providerStarted.TrySetResult(); return heldProvider.Task; }
                        if (request.Operation is "capabilities" or "browser.profiles")
                            return Task.FromResult(new Result { Operation = request.Operation, RequestId = request.RequestId!, Accepted = true, Delivery = "confirmed", Effect = "not_applicable" });
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
            replyBoundaries[0].HoldNextFlush = true;
            var completed = Action(); completed["request"] = new JsonObject { ["operation"] = "capabilities" };
            Require((await Call(a, "control.dispatch", completed))["accepted"]!.GetValue<bool>(), "First result is visible before reply task unwinds");
            var following = Action(); following["request"] = new JsonObject { ["operation"] = "capabilities" };
            following["operation"] = "control.dispatch"; following["requestId"] = "after-visible-result";
            await a.Writer.WriteLineAsync(following.ToJsonString());
            try { await boundaryDispatch.Task.WaitAsync(TimeSpan.FromSeconds(2)); }
            finally { replyBoundaries[0].Release.TrySetResult(); }
            Require(JsonNode.Parse(await a.Reader.ReadLineAsync(stop.Token) ?? "")!["accepted"]!.GetValue<bool>(), "Visible result permits the next dispatch without replay");
            var held = Action(); held["request"] = new JsonObject { ["operation"] = "capabilities" };
            held["operation"] = "control.dispatch"; held["requestId"] = "held-provider";
            await a.Writer.WriteLineAsync(held.ToJsonString());
            await providerStarted.Task.WaitAsync(stop.Token);
            try
            {
                var overlapping = Action(); overlapping["request"] = new JsonObject { ["operation"] = "capabilities" };
                Require((await Call(a, "control.dispatch", overlapping))["errorCode"]!.GetValue<string>() == "control_action_in_progress", "Unsettled provider work still excludes another dispatch");
            }
            finally { heldProvider.TrySetResult(new Result { RequestId = "held-provider", Operation = "capabilities", Accepted = true }); }
            Require(JsonNode.Parse(await a.Reader.ReadLineAsync(stop.Token) ?? "")!["accepted"]!.GetValue<bool>(), "Original provider completes once");
            foreach (var metadata in new[] { "capabilities", "browser.profiles" })
            {
                var request = Action(); request["request"] = new JsonObject { ["operation"] = metadata };
                Require(!(await Call(b, "control.dispatch", (JsonObject)request.DeepClone()))["accepted"]!.GetValue<bool>() && effects == 0, "Metadata cannot borrow another owner's fence");
                Require((await Call(a, "control.dispatch", request))["accepted"]!.GetValue<bool>() && effects == 0, "Owned metadata does not need an effect scope");
            }
            Require(!(await Call(b, "control.dispatch", Action()))["accepted"]!.GetValue<bool>() && effects == 0, "Other owner cannot borrow fence");
            Require((await Call(a, "control.dispatch", Action()))["accepted"]!.GetValue<bool>() && effects == 1, "Owned effect observed");
            Require(lastFence!.StartedLocked == false, "Native unlocked task origin is carried in private ownership");
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
            foreach (var origin in new[] { false, true })
            {
                grants.SetReady(true); grants.Arm(["observe", "control"], 900); grants.SetReady(!origin, lockedConsole: origin);
                var prepared = await Open("prepared-" + origin, prepared: true);
                active = (await Call(prepared, "control.accept", new() { ["offerGeneration"] = prepared.View["offerGeneration"]!.DeepClone() }))["data"]!.AsObject();
                grants.SetReady(false, lockedConsole: true);
                var unlock = Action(); unlock["request"] = new JsonObject { ["operation"] = "session.unlock.prepare" };
                var response = await Call(prepared, "control.dispatch", unlock);
                Require(response["accepted"]!.GetValue<bool>() == origin, "Later lock never replaces native task origin");
                if (origin) Require(lastFence!.StartedLocked == true, "Locked-origin owner retains relock authority");
                else Require(response["errorCode"]!.GetValue<string>() == "task_did_not_start_locked", "Unlocked origin refuses before credential preparation");
                await Call(prepared, "control.cancel");
            }
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

    // A transport can expose response bytes before its asynchronous flush
    // continuation finishes. Hold precisely that boundary, without sleeps.
    private sealed class ReplyBoundaryStream(Stream inner) : Stream
    {
        internal volatile bool HoldNextFlush;
        internal readonly TaskCompletionSource Release = new(TaskCreationOptions.RunContinuationsAsynchronously);
        public override bool CanRead => inner.CanRead;
        public override bool CanSeek => false;
        public override bool CanWrite => inner.CanWrite;
        public override long Length => throw new NotSupportedException();
        public override long Position { get => throw new NotSupportedException(); set => throw new NotSupportedException(); }
        public override void Flush() => inner.Flush();
        public override async Task FlushAsync(CancellationToken cancellation)
        {
            await inner.FlushAsync(cancellation);
            if (HoldNextFlush) { HoldNextFlush = false; await Release.Task.WaitAsync(cancellation); }
        }
        public override int Read(byte[] buffer, int offset, int count) => inner.Read(buffer, offset, count);
        public override ValueTask<int> ReadAsync(Memory<byte> buffer, CancellationToken cancellation = default) => inner.ReadAsync(buffer, cancellation);
        public override void Write(byte[] buffer, int offset, int count) => inner.Write(buffer, offset, count);
        public override ValueTask WriteAsync(ReadOnlyMemory<byte> buffer, CancellationToken cancellation = default) => inner.WriteAsync(buffer, cancellation);
        public override long Seek(long offset, SeekOrigin origin) => throw new NotSupportedException();
        public override void SetLength(long value) => throw new NotSupportedException();
    }
}
