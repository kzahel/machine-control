using System.IO;
using System.Text;
using System.Text.Json;
using System.Text.Json.Nodes;

namespace MachineControl.Windows;

internal sealed record ControlOwnership(string Owner, string Intent, string Session, Dictionary<string, long> Generations);

/// Connection ownership under the existing same-user workstation grant profile.
/// No public owner label, session identifier or request ID supplies authority.
internal static class AdmissionChannel
{
    internal const string Schema = "machine-control-admission-channel/v1";
    internal static async Task RunAsync(Stream stream, StreamReader reader, JsonObject open,
        DesktopGrants grants, Func<Request, ControlOwnership, CancellationToken, Task<Result>> dispatch,
        CancellationToken stop, double noticeSeconds = 10)
    {
        var owner = Guid.NewGuid().ToString("n");
        var admission = grants.Admission;
        string? intentId = null;
        using var lifetime = CancellationTokenSource.CreateLinkedTokenSource(stop);
        using var writes = new SemaphoreSlim(1, 1);
        await using var writer = new StreamWriter(stream, new UTF8Encoding(false), 4096, leaveOpen: true);
        Task? action = null;
        var seen = new HashSet<string>();
        async Task Reply(string id, object? data = null, string? error = null)
        {
            await writes.WaitAsync(lifetime.Token);
            try
            {
                using var timeout = CancellationTokenSource.CreateLinkedTokenSource(lifetime.Token);
                timeout.CancelAfter(TimeSpan.FromSeconds(5));
                await writer.WriteLineAsync(Contract.Serialize(new { schema = Schema, requestId = id, accepted = error is null, errorCode = error, data }).AsMemory(), timeout.Token);
                await writer.FlushAsync(timeout.Token);
            }
            finally { writes.Release(); }
        }
        try
        {
            Keys(open, ["operation", "schema", "requestId", "reason", "scopes", "durationSeconds", "waitSeconds", "claimId"]);
            if (open["schema"]?.GetValue<string>() != AccessAdmission.Schema) throw new ArgumentException("unsupported_admission_schema");
            var scopes = open["scopes"]?.Deserialize<string[]>() ?? [];
            if (scopes.Length == 0 || scopes.Distinct().Count() != scopes.Length || scopes.Any(s => !DesktopGrants.SupportedScopes.Contains(s))) throw new ArgumentException("invalid_admission_scopes");
            var initial = admission.Submit(owner, Required(open, "requestId").GetValue<string>(), ["desktop"],
                Required(open, "waitSeconds").GetValue<int>(), Required(open, "durationSeconds").GetValue<int>(),
                Required(open, "reason").GetValue<string>(), () => grants.AdmissionAuthority(scopes), noticeSeconds);
            intentId = JsonSerializer.SerializeToElement(initial).GetProperty("intentId").GetString()!;
            await Reply(Required(open, "requestId").GetValue<string>(), initial);
            while (!lifetime.IsCancellationRequested)
            {
                using var timeout = CancellationTokenSource.CreateLinkedTokenSource(lifetime.Token);
                timeout.CancelAfter(TimeSpan.FromSeconds(65));
                var line = await ReadLine(reader, timeout.Token);
                if (line is null) break;
                var request = JsonNode.Parse(line)?.AsObject() ?? throw new ArgumentException("invalid_admission_request");
                var id = request["requestId"]?.GetValue<string>() ?? "";
                if (id.Length is < 1 or > 80 || seen.Count >= 4096 || !seen.Add(id)) throw new ArgumentException("invalid_admission_request_id");
                try
                {
                    var operation = request["operation"]?.GetValue<string>() ?? "";
                    Keys(request, operation == "control.accept" ? ["operation", "requestId", "offerGeneration"] :
                        operation == "control.dispatch" ? ["operation", "requestId", "sessionId", "resourceGenerations", "request"] : ["operation", "requestId"]);
                    switch (operation)
                    {
                        case "control.status":
                        case "control.heartbeat":
                            await Reply(id, admission.Inspect(owner, intentId, operation == "control.heartbeat")); break;
                        case "control.accept":
                            await Reply(id, admission.Accept(owner, intentId, Required(request, "offerGeneration").GetValue<long>())); break;
                        case "control.cancel":
                            admission.Cancel(owner, intentId); await Reply(id, admission.Inspect(owner, intentId)); break;
                        case "control.dispatch":
                            if (action is { IsCompleted: false }) throw new InvalidOperationException("control_action_in_progress");
                            var fence = new ControlOwnership(owner, intentId, Required(request, "sessionId").GetValue<string>(),
                                Required(request, "resourceGenerations").Deserialize<Dictionary<string, long>>()!);
                            var denied = admission.Authorize(owner, intentId, fence.Session, fence.Generations);
                            if (denied is not null) throw new InvalidOperationException(denied);
                            var effect = Contract.ParseRequest(Required(request, "request").ToJsonString()) with { RequestId = id };
                            var scope = DesktopGrants.ScopeFor(effect.Operation);
                            if (scope is null || !scopes.Contains(scope) || effect.Operation == "browser.endpoint") throw new InvalidOperationException("operation_not_permitted_by_control_channel");
                            action = Task.Run(async () =>
                            {
                                try
                                {
                                    var result = await dispatch(effect, fence, lifetime.Token);
                                    var stale = admission.Authorize(owner, intentId, fence.Session, fence.Generations);
                                    if (stale is not null) result = result with { Accepted = false, ErrorCode = stale, Uncertainty = "interrupted_after_possible_dispatch", RetrySafety = "unsafe" };
                                    if (grants.Journal?.Record(result) == false) result = result with { Accepted = false, ErrorCode = "audit_storage_unavailable", Uncertainty = "audit_result_not_persisted" };
                                    await Reply(id, result);
                                }
                                catch (Exception ex) when (ex is ArgumentException or InvalidOperationException) { await Reply(id, error: ex.Message); }
                            }, lifetime.Token);
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
            if (action is not null) try { await action; } catch (OperationCanceledException) { } catch (IOException) { }
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
