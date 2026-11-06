using System.IO;
using System.Text;
using System.Text.Json;
using System.Text.Json.Nodes;

namespace MachineControl.Windows;

/// Connection ownership under the existing same-user workstation grant profile.
/// No public owner label, session identifier or request ID supplies authority.
internal static class AdmissionChannel
{
    internal const string Schema = "machine-control-admission-channel/v2";
    internal static async Task RunAsync(Stream stream, StreamReader reader, JsonObject open,
        DesktopGrants grants, Func<Request, ControlOwnership, CancellationToken, Task<Result>> dispatch,
        CancellationToken stop, Action? refreshConsole = null)
    {
        var owner = Guid.NewGuid().ToString("n");
        var admission = grants.Admission;
        string? intentId = null;
        string? initialSession = null;
        bool? startedLocked = null;
        var prepared = false;
        using var lifetime = CancellationTokenSource.CreateLinkedTokenSource(stop);
        using var writes = new SemaphoreSlim(1, 1);
        await using var writer = new StreamWriter(stream, new UTF8Encoding(false), 4096, leaveOpen: true);
        object? activeAction = null;
        var actions = new List<Task>();
        var order = new AdmissionRequestOrder();
        async Task Reply(string id, object? data = null, string? error = null, object? completedAction = null)
        {
            await writes.WaitAsync(lifetime.Token);
            try
            {
                using var timeout = CancellationTokenSource.CreateLinkedTokenSource(lifetime.Token);
                timeout.CancelAfter(TimeSpan.FromSeconds(5));
                if (data is not null)
                {
                    var projection = JsonSerializer.SerializeToNode(data, Contract.Json)?.AsObject();
                    if (projection?["schema"]?.GetValue<string>() == AccessAdmission.Schema)
                    {
                        projection["requestSequencing"] = "strict";
                        // The protected guardian has a separate hard deadline.
                        // Do not advertise renewal without its acknowledgement.
                        if (prepared) projection.Remove("renewal");
                        data = projection;
                    }
                }
                // A client may see these bytes before FlushAsync's continuation
                // (and its containing Task) finishes. Provider work has ended;
                // release occupancy before making its result visible.
                if (completedAction is not null) Interlocked.CompareExchange(ref activeAction, null, completedAction);
                await writer.WriteLineAsync(Contract.Serialize(new { schema = Schema, requestId = id, accepted = error is null, errorCode = error, data }).AsMemory(), timeout.Token);
                await writer.FlushAsync(timeout.Token);
            }
            finally { writes.Release(); }
        }
        try
        {
            Keys(open, ["operation", "schema", "requestId", "reason", "surfaces", "profileIds", "operations", "durationSeconds", "waitSeconds", "claimId", "requestSequence", "preparedConsole"]);
            if (!order.Accept(open)) throw new ArgumentException("invalid_admission_request_order");
            if (open["schema"]?.GetValue<string>() != AccessAdmission.Schema) throw new ArgumentException("unsupported_admission_schema");
            var surfaces = open["surfaces"]?.Deserialize<string[]>() ?? [];
            if (surfaces.Length is < 1 or > 2 || surfaces.Distinct().Count() != surfaces.Length || surfaces.Any(s => s is not ("desktop" or "browser"))) throw new ArgumentException("invalid_admission_surfaces");
            var scopes = DesktopGrants.SupportedScopes.Where(scope => surfaces.Contains(DesktopGrants.SurfaceFor(scope))).ToArray();
            var profileIds = open["profileIds"]?.Deserialize<string[]>() ?? [];
            if (surfaces.Contains("browser") && profileIds.Length == 0) throw new ArgumentException("exact_browser_profile_required");
            var operations = open["operations"]?.Deserialize<string[]>();
            if (operations is not null && (operations.Length is < 1 or > 64 || operations.Distinct().Count() != operations.Length ||
                operations.Any(op => DesktopGrants.ScopeFor(op) is not { } scope || !scopes.Contains(scope)))) throw new ArgumentException("invalid_admission_operations");
            if (grants.Journal?.Available == false) throw new InvalidOperationException("audit_storage_unavailable");
            prepared = open["preparedConsole"]?.GetValue<bool>() == true;
            if (prepared && (!grants.PreparedConsole || !scopes.Order().SequenceEqual(new[] { "control", "observe" })))
                throw new InvalidOperationException("prepared_console_unavailable");
            if (!grants.ReadyForScopes(scopes) && !prepared) throw new InvalidOperationException("prepared_console_required");
            // The shared host classifies impact from this enforced operation
            // set. Callers cannot assert that arbitrary effects are background.
            var initial = admission.Submit(owner, Required(open, "requestId").GetValue<string>(), surfaces,
                Required(open, "waitSeconds").GetValue<int>(), Required(open, "durationSeconds").GetValue<int>(),
                Required(open, "reason").GetValue<string>(),
                profileIds, operations);
            intentId = JsonSerializer.SerializeToElement(initial).GetProperty("intentId").GetString()!;
            await Reply(Required(open, "requestId").GetValue<string>(), initial);
            while (!lifetime.IsCancellationRequested)
            {
                using var timeout = CancellationTokenSource.CreateLinkedTokenSource(lifetime.Token);
                timeout.CancelAfter(TimeSpan.FromSeconds(65));
                var line = await ReadLine(reader, timeout.Token);
                if (line is null) break;
                if (actions.Any(task => task.IsFaulted)) throw new IOException("Admission response failed");
                actions.RemoveAll(task => task.IsCompletedSuccessfully);
                var request = JsonNode.Parse(line)?.AsObject() ?? throw new ArgumentException("invalid_admission_request");
                var id = request["requestId"]?.GetValue<string>() ?? "";
                if (!order.Accept(request)) throw new ArgumentException("invalid_admission_request_id");
                try
                {
                    var operation = request["operation"]?.GetValue<string>() ?? "";
                    Keys(request, operation == "control.accept" ? ["operation", "requestId", "offerGeneration", "requestSequence"] :
                        operation == "control.renew" ? ["operation", "requestId", "sessionId", "resourceGenerations", "durationSeconds", "requestSequence"] :
                        operation == "control.dispatch" ? ["operation", "requestId", "sessionId", "resourceGenerations", "request", "requestSequence"] : ["operation", "requestId", "requestSequence"]);
                    switch (operation)
                    {
                        case "control.status":
                        case "control.heartbeat":
                            await Reply(id, admission.Inspect(owner, intentId, operation == "control.heartbeat")); break;
                        case "control.accept":
                            object accepted;
                            lock (grants.Gate)
                            {
                                refreshConsole?.Invoke();
                                var initialLock = grants.TaskStartLocked;
                                accepted = admission.Accept(owner, intentId, Required(request, "offerGeneration").GetValue<long>());
                                var session = JsonSerializer.SerializeToElement(accepted, Contract.Json).GetProperty("sessionId").GetString();
                                if (initialSession != session) { initialSession = session; startedLocked = initialLock; }
                            }
                            await Reply(id, accepted); break;
                        case "control.renew":
                            if (prepared) throw new InvalidOperationException("control_renewal_unavailable");
                            // Renewal preserves the owner fence and performs no
                            // provider work. It must progress during a long action.
                            var seconds = Required(request, "durationSeconds").GetValue<int>();
                            if (seconds is < 1 or > 900) throw new ArgumentException("invalid_renewal_duration");
                            await Reply(id, admission.Renew(owner, intentId, Required(request, "sessionId").GetValue<string>(),
                                Required(request, "resourceGenerations").Deserialize<Dictionary<string, long>>()!, seconds));
                            break;
                        case "control.cancel":
                            admission.Cancel(owner, intentId); await Reply(id, admission.Inspect(owner, intentId)); break;
                        case "control.dispatch":
                            if (Volatile.Read(ref activeAction) is not null) throw new InvalidOperationException("control_action_in_progress");
                            if (actions.Count >= 128) throw new InvalidOperationException("control_response_capacity");
                            var fence = new ControlOwnership(owner, intentId, Required(request, "sessionId").GetValue<string>(),
                                Required(request, "resourceGenerations").Deserialize<Dictionary<string, long>>()!, startedLocked);
                            var effect = Contract.ParseRequest(Required(request, "request").ToJsonString()) with { RequestId = id };
                            var denied = admission.Authorize(owner, intentId, fence.Session, fence.Generations, effect.Operation);
                            if (denied is not null) throw new InvalidOperationException(denied);
                            var scope = DesktopGrants.ScopeFor(effect.Operation);
                            if (effect.Operation is not ("capabilities" or "browser.profiles") && (scope is null || !scopes.Contains(scope))) throw new InvalidOperationException("operation_not_permitted_by_control_channel");
                            if (operations is not null && effect.Operation is not ("capabilities" or "browser.profiles") && !operations.Contains(effect.Operation)) throw new InvalidOperationException("operation_not_permitted_by_control_channel");
                            if (effect.Operation is "session.unlock.prepare" or "session.unlock" && !prepared) throw new InvalidOperationException("prepared_console_required");
                            if (effect.Operation is "session.unlock.prepare" or "session.unlock" && fence.StartedLocked != true) throw new InvalidOperationException("task_did_not_start_locked");
                            var actionToken = new object();
                            if (Interlocked.CompareExchange(ref activeAction, actionToken, null) is not null) throw new InvalidOperationException("control_action_in_progress");
                            actions.Add(Task.Run(async () =>
                            {
                                try
                                {
                                    var result = await dispatch(effect, fence, lifetime.Token);
                                    var stale = admission.Authorize(owner, intentId, fence.Session, fence.Generations);
                                    if (stale is not null) result = result with { Accepted = false, ErrorCode = stale, Uncertainty = "interrupted_after_possible_dispatch", RetrySafety = "unsafe" };
                                    if (grants.Journal?.Record(result) == false) result = result with { Accepted = false, ErrorCode = "audit_storage_unavailable", Uncertainty = "audit_result_not_persisted" };
                                    await Reply(id, result, completedAction: actionToken);
                                }
                                catch (Exception ex) when (ex is ArgumentException or InvalidOperationException) { await Reply(id, error: ex.Message, completedAction: actionToken); }
                                finally { Interlocked.CompareExchange(ref activeAction, null, actionToken); }
                            }, lifetime.Token));
                            break;
                        default: throw new ArgumentException("unsupported_admission_operation");
                    }
                }
                catch (Exception ex) when (ex is ArgumentException or InvalidOperationException or JsonException) { await Reply(id, error: ex.Message); }
            }
        }
        catch (Exception ex) when (ex is ArgumentException or InvalidOperationException or JsonException)
        { await Reply(open["requestId"]?.GetValue<string>() ?? "invalid", error: ex.Message); }
        finally
        {
            admission.Disconnect(owner); lifetime.Cancel();
            try { await Task.WhenAll(actions); } catch (OperationCanceledException) { } catch (IOException) { }
        }
    }
    private static JsonNode Required(JsonObject value, string key) => value[key] ?? throw new ArgumentException("invalid_admission_request");
    private static void Keys(JsonObject request, string[] allowed)
    {
        if (request.Any(p => !allowed.Contains(p.Key))) throw new ArgumentException("invalid_admission_request");
    }
    private static async Task<string?> ReadLine(StreamReader reader, CancellationToken stop)
    {
        var text = new StringBuilder(); var character = new char[1];
        while (await reader.ReadAsync(character.AsMemory(), stop) != 0)
        {
            if (character[0] == '\n') return text.ToString();
            if (text.Length >= 65536) throw new InvalidDataException("Admission frame exceeds 64 KiB");
            text.Append(character[0]);
        }
        if (text.Length != 0) throw new InvalidDataException("Incomplete admission frame");
        return null;
    }
}

/// Strict ordered mode uses constant memory for the entire bounded connection.
internal sealed class AdmissionRequestOrder
{
    private long? _sequence;
    private readonly HashSet<string> _seen = [];
    internal bool Accept(JsonObject request)
    {
        if (request["requestId"] is not JsonValue identifier || !identifier.TryGetValue<string>(out var id) || id.Length is < 1 or > 80) return false;
        if (_sequence is not null || request.ContainsKey("requestSequence"))
        {
            if (request["requestSequence"] is not JsonValue number || !number.TryGetValue<long>(out var supplied) ||
                supplied <= 0 || _sequence == long.MaxValue || supplied != (_sequence ?? 0) + 1) return false;
            _sequence = supplied; _seen.Clear(); return true;
        }
        return _seen.Count < 4096 && _seen.Add(id);
    }
}
