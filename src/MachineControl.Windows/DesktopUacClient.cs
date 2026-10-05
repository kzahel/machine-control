using System.IO;
using System.IO.Pipes;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using System.Text.Json.Nodes;

namespace MachineControl.Windows;

internal static class DesktopUacClient
{
    private static volatile bool _enabled;
    internal static bool Enabled => _enabled;
    internal static object State() => new
    {
        installed = DesktopUacNative.Installed(),
        enabled = Enabled,
        available = Enabled && DesktopUacNative.Installed(),
        privilege = "LocalSystem",
        route = "windows.desktop_uac",
        provider = "windows-native-protected",
        setupState = "idle",
        operations = DesktopUacPolicy.Operations,
        sessionRequirement = "same active unlocked console; stock English UAC consent only",
        hostInterference = "none",
    };
    internal static void Enable(bool enabled, DesktopGrants grants)
    {
        lock (grants.Gate)
        {
            if (enabled && (!DesktopUacNative.Installed() || !string.Equals(Environment.ProcessPath, DesktopUacNative.Executable, StringComparison.OrdinalIgnoreCase)))
                throw new InvalidOperationException("Install the UAC helper and restart Machine Control first");
            if (_enabled == enabled) return;
            grants.Stop(enabled ? "uac_enabled_reapprove_access" : "uac_disabled");
            _enabled = enabled;
        }
    }

    internal static async Task<Result> ExecuteAsync(Request request, string generation, DesktopGrants grants, CancellationToken cancellation)
    {
        var refusal = DesktopSafety.Check(request, generation);
        Result Refused(string code, bool dispatched = false) => new()
        {
            RequestId = request.RequestId!,
            Operation = request.Operation,
            Generation = generation,
            ActualRoute = "windows.desktop_uac",
            ErrorCode = code,
            Delivery = dispatched ? "unknown" : "refused",
            Effect = dispatched ? "unknown" : "refused",
            RetrySafety = dispatched ? "unsafe_unknown_delivery" : "safe_not_dispatched"
        };
        if (!Enabled) return Refused("uac_access_disabled");
        if (refusal is not null) return Refused(refusal);
        using var deadline = CancellationTokenSource.CreateLinkedTokenSource(cancellation);
        deadline.CancelAfter(TimeSpan.FromSeconds(35));
        var guardName = $"machine-control-uac-guard-{Guid.NewGuid():n}";
        using var guardStop = CancellationTokenSource.CreateLinkedTokenSource(deadline.Token);
        var guardTask = GuardAsync(guardName, request, generation, grants, guardStop.Token);
        var dispatched = false;
        try
        {
            using var pipe = new NamedPipeClientStream(".", DesktopUacNative.Pipe, PipeDirection.InOut, PipeOptions.Asynchronous, System.Security.Principal.TokenImpersonationLevel.Identification);
            await pipe.ConnectAsync(3000, deadline.Token);
            DesktopUacNative.RequireServer(pipe, DesktopUacNative.ServicePid());
            using var writer = new StreamWriter(pipe, new UTF8Encoding(false), 4096, true) { AutoFlush = true };
            using var reader = new StreamReader(pipe, Encoding.UTF8, false, 4096, true);
            // The worker rechecks this exact request's live authority before
            // every native effect through the private System-only guard pipe.
            var frame = new DesktopUacFrame(request, generation, guardName, (uint)Environment.ProcessId, DesktopSafety.OperatorProcessId);
            dispatched = true;
            await writer.WriteLineAsync(Contract.Serialize(frame).AsMemory(), deadline.Token);
            var response = JsonSerializer.Deserialize<DesktopUacReply>(await DesktopUacNative.ReadAsync(reader, deadline.Token, 24 * 1024 * 1024), Contract.Json)
                ?? throw new InvalidDataException("Missing UAC result");
            var result = response.Result;
            if (response.Capture is { } capture)
            {
                if (capture.Length > 16 * 1024 * 1024) throw new InvalidDataException("Protected capture too large");
                var data = JsonSerializer.SerializeToNode(result.Data, Contract.Json)!.AsObject();
                var id = data["artifactId"]!.GetValue<string>();
                if (!Guid.TryParseExact(id, "n", out _) || Convert.ToHexString(SHA256.HashData(capture)).ToLowerInvariant() != data["sha256"]!.GetValue<string>())
                    throw new InvalidDataException("Protected capture identity mismatch");
                Directory.CreateDirectory(RuntimeProfile.ArtifactRoot);
                var path = Path.Combine(RuntimeProfile.ArtifactRoot, id + ".png");
                await File.WriteAllBytesAsync(path, capture, deadline.Token);
                data["targetLocalPath"] = path;
                result = result with { Data = data };
            }
            return result;
        }
        catch (Exception ex) when (ex is IOException or UnauthorizedAccessException or OperationCanceledException or JsonException or System.ComponentModel.Win32Exception)
        { return Refused("uac_helper_unavailable", dispatched); }
        finally
        {
            guardStop.Cancel();
            try { await guardTask; } catch (OperationCanceledException) { }
        }
    }

    private static async Task GuardAsync(string name, Request request, string generation, DesktopGrants grants, CancellationToken cancellation)
    {
        while (!cancellation.IsCancellationRequested)
        {
            using var pipe = DesktopUacNative.Server(name, systemOnly: true);
            await pipe.WaitForConnectionAsync(cancellation);
            try
            {
                using var reader = new StreamReader(pipe, Encoding.UTF8, false, 4096, true);
                using var timeout = CancellationTokenSource.CreateLinkedTokenSource(cancellation);
                timeout.CancelAfter(TimeSpan.FromSeconds(3));
                var check = JsonSerializer.Deserialize<JsonElement>(await DesktopUacNative.ReadAsync(reader, timeout.Token));
                DesktopUacNative.RequireSystem(pipe);
                var pid = check.TryGetProperty("processId", out var process) && process.ValueKind == JsonValueKind.Number ? process.GetInt32() : (int?)null;
                string? error;
                lock (grants.Gate) error = !Enabled ? "uac_access_disabled" : DesktopSafety.Check(request, generation, pid);
                await using var writer = new StreamWriter(pipe, new UTF8Encoding(false), 4096, true) { AutoFlush = true };
                await writer.WriteLineAsync(Contract.Serialize(new { error }).AsMemory(), timeout.Token);
            }
            catch (Exception ex) when (ex is IOException or UnauthorizedAccessException or JsonException or OperationCanceledException) { }
        }
    }
}
