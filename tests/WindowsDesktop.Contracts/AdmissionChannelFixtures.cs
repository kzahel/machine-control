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
        var grants = TestBrowserProjection.Create(clock); grants.SetReady(true); grants.PrepareConsole(true); grants.ConfigureSurface("desktop", "automatic", 900, "timed");
        foreach (var operation in new[] { "snapshot", "type", "app.launch", "screenshot", "uac.respond" })
            Require(grants.Authorize(new Request { Operation = operation }) == "control_session_required", "Idle grant cannot authorize unowned " + operation);
        var requirement = JsonNode.Parse(Contract.Serialize(DesktopGrants.RefusalData("type", "control_session_required")))!;
        Require(requirement["controlSession"]!["schema"]!.GetValue<string>() == AccessAdmission.Schema &&
            requirement["controlSession"]!["surface"]!.GetValue<string>() == "desktop", "Typed CLI handoff");
        var browserGrants = TestBrowserProjection.Create(clock); browserGrants.SetReady(true); browserGrants.ConfigureSurface("browser", "automatic", 900, "timed", ["fixture-profile"]);
        Require(browserGrants.Admission.Enabled("browser"), "Devtools grant covers browser admission");
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
        var unlockCalls = 0;
        var unlockGate = new TaskCompletionSource(TaskCreationOptions.RunContinuationsAsynchronously); unlockGate.SetResult();
        async Task<(StreamReader Reader, StreamWriter Writer, JsonObject View)> Open(string id, bool prepared = false, bool enrolled = false, bool expectAccepted = true, List<string>? dispatched = null)
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
                ["surfaces"] = new JsonArray("desktop")
            };
            if (prepared) opening["preparedConsole"] = true;
            owners.Add(Task.Run(async () =>
            {
                using (resident)
                using (var reader = new StreamReader(resident.GetStream(), Encoding.UTF8, false, 4096, leaveOpen: true))
                    await AdmissionChannel.RunAsync(boundary, reader, opening, grants, async (request, fence, cancellation) =>
                    {
                        dispatched?.Add(request.Operation);
                        if (request.Operation == "session.unlock")
                        {
                            Interlocked.Increment(ref unlockCalls);
                            await unlockGate.Task.WaitAsync(cancellation);
                            grants.SetReady(true);
                            return new Result { Operation = request.Operation, RequestId = request.RequestId!, Accepted = true, Delivery = "confirmed", Effect = "confirmed" };
                        }
                        return await Effect(request, fence);
                    }, stop.Token, preparedUnlockAvailable: () => enrolled);
            }));
            Task<Result> Effect(Request request, ControlOwnership fence)
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
            }
            var readerClient = new StreamReader(client.GetStream());
            var writerClient = new StreamWriter(client.GetStream(), new UTF8Encoding(false)) { AutoFlush = true };
            var first = JsonNode.Parse(await readerClient.ReadLineAsync(stop.Token) ?? "")!.AsObject();
            if (!expectAccepted) return (readerClient, writerClient, first);
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
            Require(active["renewal"]!.GetValue<string>() == "owner_connection/v1", "Ordinary owner advertises typed renewal");
            var renewal = await Call(a, "control.renew", new()
            {
                ["sessionId"] = active["sessionId"]!.DeepClone(),
                ["resourceGenerations"] = active["resourceGenerations"]!.DeepClone(),
                ["durationSeconds"] = 120
            });
            Require(renewal["accepted"]!.GetValue<bool>() && renewal["data"]!["sessionId"]!.GetValue<string>() == active["sessionId"]!.GetValue<string>(),
                "Same-connection renewal retains the actual owner fence");
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
                var busyRenewal = await Call(a, "control.renew", new()
                {
                    ["sessionId"] = active["sessionId"]!.DeepClone(),
                    ["resourceGenerations"] = active["resourceGenerations"]!.DeepClone(),
                    ["durationSeconds"] = 120
                });
                Require(busyRenewal["accepted"]!.GetValue<bool>(), "An in-flight action cannot starve same-owner renewal");
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
            Require(grants.Authorize(new Request { Operation = "type" }) == "control_session_required", "Legacy callers cannot borrow holder");
            var forged = Contract.ParseRequest("{\"operation\":\"type\",\"controlOwnership\":{\"owner\":\"forged\"}}");
            Require(forged.ControlOwnership is null && grants.Authorize(forged) == "control_session_required", "JSON cannot supply native owner context");
            grants.Pause();
            Require(!(await Call(a, "control.dispatch", Action()))["accepted"]!.GetValue<bool>() && effects == 1, "Paused effect refused");
            grants.Resume();
            var next = (await Call(b, "control.status"))["data"]!.AsObject();
            Require(next["state"]!.GetValue<string>() == "offered", "Paused owner yields queue position without losing its task");
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
                grants.SetReady(true); grants.ConfigureSurface("desktop", "automatic", 900, "timed"); grants.SetReady(!origin, lockedConsole: origin);
                var prepared = await Open("prepared-" + origin, prepared: true);
                Require(!prepared.View.ContainsKey("renewal"), "Prepared owner does not advertise unacknowledged guardian renewal");
                active = (await Call(prepared, "control.accept", new() { ["offerGeneration"] = prepared.View["offerGeneration"]!.DeepClone() }))["data"]!.AsObject();
                Require(active.ContainsKey("renewal") == !origin, "Only an unlocked-origin prepared owner advertises renewal");
                var renewed = await Call(prepared, "control.renew", new()
                {
                    ["sessionId"] = active["sessionId"]!.DeepClone(),
                    ["resourceGenerations"] = active["resourceGenerations"]!.DeepClone(),
                    ["durationSeconds"] = 120
                });
                Require(origin ? renewed["errorCode"]!.GetValue<string>() == "control_renewal_unavailable" : renewed["accepted"]!.GetValue<bool>(),
                    "Protected renewal refuses before changing any deadline; an unlocked origin renews like any owner");
                grants.SetReady(false, lockedConsole: true);
                var unlock = Action(); unlock["request"] = new JsonObject { ["operation"] = "session.unlock.prepare" };
                var response = await Call(prepared, "control.dispatch", unlock);
                Require(response["accepted"]!.GetValue<bool>() == origin, "Later lock never replaces native task origin");
                if (origin) Require(lastFence!.StartedLocked == true, "Locked-origin owner retains relock authority");
                else Require(response["errorCode"]!.GetValue<string>() == "task_did_not_start_locked", "Unlocked origin refuses before credential preparation");
                await Call(prepared, "control.cancel");
            }
            // Tactical 159 decisions 1 and 2: one prepared route and waiting
            // rather than refusing outside a locked Desktop request.
            grants.SetReady(true); grants.ConfigureSurface("desktop", "automatic", 900, "timed");
            grants.SetReady(false, lockedConsole: true);
            var plainLocked = await Open("plain-locked", expectAccepted: false);
            Require(plainLocked.View["errorCode"]!.GetValue<string>() == "prepared_console_required" && plainLocked.View["requestId"]!.GetValue<string>() == "plain-locked",
                "A plain Desktop owner on a locked console refuses prepared_console_required");
            grants.SetReady(false, lockedConsole: false);
            var transient = await Open("plain-transient");
            Require(transient.View["state"]!.GetValue<string>() is "waiting_for_resource" or "paused" &&
                transient.View["blockingReasons"]!.AsArray().Any(reason => reason!.GetValue<string>() == "resource_unavailable"),
                "A transiently unready console queues as resource_unavailable");
            await Call(transient, "control.cancel");
            grants.SetReady(true);
            grants.PrepareConsole(false); grants.ConfigureSurface("desktop", "automatic", 900, "timed");
            var flagged = await Open("prepared-unlocked-unprepared", prepared: true);
            Require(flagged.View["state"]!.GetValue<string>() == "offered", "The prepared flag is harmless on an unlocked console without locked use");
            await Call(flagged, "control.cancel");
            grants.SetReady(false, lockedConsole: true);
            var unavailable = await Open("prepared-locked-unprepared", prepared: true, expectAccepted: false);
            Require(unavailable.View["errorCode"]!.GetValue<string>() == "prepared_console_unavailable", "Locked use disabled refuses a prepared owner");
            grants.SetReady(true); grants.PrepareConsole(true); grants.ConfigureSurface("desktop", "automatic", 900, "timed");
            // A plain owner admitted while unlocked pauses when the console
            // locks; it is never offered a locked desktop.
            var early = await Open("plain-before-lock");
            grants.SetReady(false, lockedConsole: true);
            var paused = (await Call(early, "control.status"))["data"]!.AsObject();
            Require(paused["state"]!.GetValue<string>() != "offered" && paused["blockingReasons"]!.AsArray().Any(reason => reason!.GetValue<string>() == "resource_unavailable"),
                "A plain owner waits while locked instead of being offered");
            await Call(early, "control.cancel");
            clients[^1].Dispose(); await owners[^1];
            // Enrolled prepared owner: unlocked at accept, then usable.
            unlockGate = new TaskCompletionSource(TaskCreationOptions.RunContinuationsAsynchronously);
            var calls = new List<string>();
            var enrolled = await Open("prepared-enrolled", prepared: true, enrolled: true, dispatched: calls);
            Require(enrolled.View["state"]!.GetValue<string>() == "offered", "A prepared owner is offered the locked console");
            var accepted = (await Call(enrolled, "control.accept", new() { ["offerGeneration"] = enrolled.View["offerGeneration"]!.DeepClone() }))["data"]!.AsObject();
            Require(accepted["consoleUnlock"]?["state"]?.GetValue<string>() == "unlocking" && !accepted.ContainsKey("renewal"),
                "Accept starts the prepared unlock without a separate dispatch");
            for (var spin = 0; Volatile.Read(ref unlockCalls) == 0 && spin < 100; spin++) await Task.Delay(10);
            Require(Volatile.Read(ref unlockCalls) == 1, "Exactly one accept-time unlock");
            JsonObject Owned(JsonObject request) => new()
            {
                ["sessionId"] = accepted["sessionId"]!.DeepClone(),
                ["resourceGenerations"] = accepted["resourceGenerations"]!.DeepClone(),
                ["request"] = request
            };
            var waiting = Owned(new JsonObject { ["operation"] = "type", ["text"] = "fixture" });
            waiting["operation"] = "control.dispatch"; waiting["requestId"] = "after-unlock";
            await enrolled.Writer.WriteLineAsync(waiting.ToJsonString());
            await Task.Delay(100);
            Require(!calls.Contains("type"), "Ordinary work waits for the accept-time unlock");
            unlockGate.SetResult();
            var typed = JsonNode.Parse(await enrolled.Reader.ReadLineAsync(stop.Token) ?? "")!.AsObject();
            Require(typed["requestId"]!.GetValue<string>() == "after-unlock" && typed["accepted"]!.GetValue<bool>() && calls.Contains("type"), "Work runs once unlocked");
            var again = await Call(enrolled, "control.dispatch", Owned(new JsonObject { ["operation"] = "session.unlock" }));
            Require(again["accepted"]!.GetValue<bool>() && again["data"]!["data"]!["alreadyUnlocked"]!.GetValue<bool>() && unlockCalls == 1,
                "An explicit unlock afterwards is an idempotent no-op");
            Require((await Call(enrolled, "control.status"))["data"]!["consoleUnlock"]!["state"]!.GetValue<string>() == "unlocked", "Status reports the completed unlock");
            await Call(enrolled, "control.cancel");
        }
        finally
        {
            foreach (var client in clients) client.Dispose();
            listener.Stop();
            foreach (var owner in owners) try { await owner; } catch (OperationCanceledException) { } catch (IOException) { }
        }
        Require(grants.Admission.Status() is not null, "Disconnect cleanup accessible");
        await FramingAsync();
        Console.WriteLine("Admission live transport fixtures passed");
    }
    private static void Require(bool value, string message) { if (!value) throw new Exception(message); }

    /// Tactical 159 decisions 6 and 7: one envelope, common refusal codes,
    /// and ordering violations or failed opens close the channel.
    private static async Task FramingAsync()
    {
        var grants = TestBrowserProjection.Create(new TestTime()); grants.SetReady(true);
        grants.ConfigureSurface("desktop", "automatic", 900, "timed");
        JsonObject Opening(Action<JsonObject>? change = null)
        {
            var frame = new JsonObject
            {
                ["operation"] = "control.open",
                ["schema"] = AccessAdmission.Schema,
                ["requestId"] = "open-" + Guid.NewGuid().ToString("n")[..8],
                ["reason"] = "fixture",
                ["durationSeconds"] = 60,
                ["waitSeconds"] = 5,
                ["surfaces"] = new JsonArray("desktop")
            };
            change?.Invoke(frame);
            return frame;
        }
        foreach (var (change, code) in new (Action<JsonObject>, string)[]
        {
            (frame => frame["schema"] = "machine-control-admission/v9", "unsupported_admission_schema"),
            (frame => frame["surfaces"] = new JsonArray("desktop", "printer"), "invalid_admission_surfaces"),
            (frame => frame["surfaces"] = new JsonArray("browser"), "exact_browser_profile_required"),
            (frame => frame["profileIds"] = new JsonArray("Work"), "invalid_browser_profiles"),
            (frame => frame["operations"] = new JsonArray("browser.tabs"), "invalid_admission_operations"),
            (frame => frame["requestSequence"] = 2L, "invalid_request_sequence"),
        })
        {
            var open = Opening(change);
            var trailing = new JsonObject { ["operation"] = "control.status", ["requestId"] = "after-refusal" };
            var replies = await Exchange(grants, open, trailing);
            Require(replies.Count == 1 && replies[0]["errorCode"]!.GetValue<string>() == code &&
                replies[0]["requestId"]!.GetValue<string>() == open["requestId"]!.GetValue<string>() &&
                replies[0]["schema"]!.GetValue<string>() == AdmissionChannel.Schema && replies[0].ContainsKey("data") && replies[0]["data"] is null,
                "Failed open refuses with " + code + " in the channel envelope and closes");
        }
        var gap = await Exchange(grants, Opening(),
            new JsonObject { ["operation"] = "control.status", ["requestId"] = "first", ["requestSequence"] = 1L },
            new JsonObject { ["operation"] = "control.status", ["requestId"] = "skipped", ["requestSequence"] = 3L },
            new JsonObject { ["operation"] = "control.cancel", ["requestId"] = "never", ["requestSequence"] = 2L });
        Require(gap.Count == 3 && gap[0]["accepted"]!.GetValue<bool>() && gap[0]["errorCode"] is null && gap[0].ContainsKey("errorCode") &&
            gap[1]["requestId"]!.GetValue<string>() == "first" && gap[1]["accepted"]!.GetValue<bool>(),
            "Accepted replies carry an explicit null errorCode");
        Require(gap[2]["requestId"]!.GetValue<string>() == "skipped" && gap[2]["errorCode"]!.GetValue<string>() == "invalid_request_sequence",
            "A sequence gap answers the offending request, then the channel closes");
        var unknown = await Exchange(grants, Opening(),
            new JsonObject { ["operation"] = "control.teleport", ["requestId"] = "odd" },
            new JsonObject { ["operation"] = "control.status", ["requestId"] = "still-open" });
        Require(unknown.Count == 3 && unknown[1]["errorCode"]!.GetValue<string>() == "unsupported_admission_operation" &&
            unknown[2]["requestId"]!.GetValue<string>() == "still-open", "An unknown operation is refused without closing");
        foreach (var (operation, scope) in new[] { ("applications", "observe"), ("action", "control"), ("application.terminate", "control") })
            Require(DesktopGrants.ScopeFor(operation) == scope, "Portable " + operation + " has a typed scope");
        Console.WriteLine("Admission channel framing and refusal vocabulary contracts passed");
    }

    /// Runs one channel over in-memory frames and returns every reply frame.
    internal static async Task<List<JsonObject>> Exchange(DesktopGrants grants, JsonObject open, params JsonObject[] frames)
    {
        var output = new MemoryStream();
        var input = new MemoryStream(Encoding.UTF8.GetBytes(string.Concat(frames.Select(frame => frame.ToJsonString() + "\n"))));
        using var reader = new StreamReader(input, Encoding.UTF8, false, 4096, leaveOpen: true);
        using var stop = new CancellationTokenSource(TimeSpan.FromSeconds(10));
        await AdmissionChannel.RunAsync(output, reader, open, grants, (request, fence, cancellation) =>
            Task.FromResult(new Result { Operation = request.Operation, RequestId = request.RequestId!, Accepted = true, Delivery = "confirmed", Effect = "not_applicable" }), stop.Token);
        return Encoding.UTF8.GetString(output.ToArray()).Split('\n', StringSplitOptions.RemoveEmptyEntries)
            .Select(line => JsonNode.Parse(line)!.AsObject()).ToList();
    }
    internal static async Task<JsonObject> OpenOnce(DesktopGrants grants, JsonObject open) => (await Exchange(grants, open))[0];

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
