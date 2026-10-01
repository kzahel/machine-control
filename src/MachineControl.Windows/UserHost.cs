using System.IO;
using System.IO.Pipes;
using System.Security.AccessControl;
using System.Security.Principal;
using System.Text;
using System.Text.Json;

namespace MachineControl.Windows;

internal sealed class UserHost(string instance, DesktopGrants? grants = null)
{
    private readonly string _generation = Guid.NewGuid().ToString("n");
    private readonly SemaphoreSlim _providerGate = new(1, 1);
    private string Generation => grants?.Generation ?? _generation;
    internal static readonly string[] Operations =
    [
        "status", "capabilities", "app.launch", "app.activate", "windows",
        "snapshot", "screenshot", "invoke", "set.value", "click", "key",
        "type", "window.state", "runtime.stop",
    ];

    public async Task RunAsync(CancellationToken cancellationToken)
    {
        RuntimeProfile.ConfigureUser(instance);
        Directory.CreateDirectory(RuntimeProfile.ManagementRoot);
        using var activation = new FileStream(
            Path.Combine(RuntimeProfile.ManagementRoot, "activation.lock"),
            FileMode.OpenOrCreate, FileAccess.ReadWrite, FileShare.ReadWrite);
        Directory.CreateDirectory(RuntimeProfile.StateRoot);
        // Hold the installation/session lock for the entire lifetime, including
        // gaps between pipe connections. Never terminate a process by PID file.
        using var ownership = new FileStream(
            Path.Combine(RuntimeProfile.StateRoot, "resident.lock"),
            FileMode.OpenOrCreate, FileAccess.ReadWrite, FileShare.None);
        var pipe = RuntimeProfile.UserPipe(instance, RuntimeProfile.SessionId);
        using var stop = CancellationTokenSource.CreateLinkedTokenSource(cancellationToken);
        using var slots = new SemaphoreSlim(7, 7);
        var calls = new List<Task>();
        NamedPipeServerStream? listener = CreatePipe(pipe, first: true);
        try
        {
            while (!stop.IsCancellationRequested)
            {
                await slots.WaitAsync(stop.Token);
                await listener.WaitForConnectionAsync(stop.Token);
                var connected = listener;
                listener = CreatePipe(pipe, first: false);
                var caller = ClientLabel(connected);
                calls.RemoveAll(task => task.IsCompleted);
                calls.Add(Task.Run(async () =>
                {
                    try { await ServeAsync(connected, caller, stop); }
                    finally { connected.Dispose(); slots.Release(); }
                }, CancellationToken.None));
            }
        }
        finally
        {
            listener?.Dispose();
            stop.Cancel();
            await Task.WhenAll(calls);
            ProviderRouter.Stop();
        }
    }

    private async Task ServeAsync(NamedPipeServerStream server, string caller, CancellationTokenSource stop)
    {
        try
        {
            using var inputTimeout = CancellationTokenSource.CreateLinkedTokenSource(stop.Token);
            inputTimeout.CancelAfter(TimeSpan.FromSeconds(10));
            using var reader = new StreamReader(server, Encoding.UTF8, false, 4096, leaveOpen: true);
            var text = new StringBuilder();
            var character = new char[1];
            while (await reader.ReadAsync(character.AsMemory(), inputTimeout.Token) != 0)
            {
                if (character[0] == '\n') break;
                if (text.Length >= 1024 * 1024) throw new InvalidDataException("Request exceeds 1 MiB");
                text.Append(character[0]);
            }
            var request = Contract.ParseRequest(text.ToString());
            Result result;
            try { result = await ExecuteAsync(request, caller, stop.Token); }
            catch (ArgumentException ex) { result = Envelope(request) with { ErrorCode = "invalid_request", Message = ex.Message }; }
            grants?.Record(result);
            using var outputTimeout = CancellationTokenSource.CreateLinkedTokenSource(stop.Token);
            outputTimeout.CancelAfter(TimeSpan.FromSeconds(10));
            await using var writer = new StreamWriter(server, new UTF8Encoding(false), 4096, leaveOpen: true);
            await writer.WriteLineAsync(Contract.Serialize(result).AsMemory(), outputTimeout.Token);
            await writer.FlushAsync(outputTimeout.Token);
            if (request.Operation == "runtime.stop" && result.Accepted) stop.Cancel();
        }
        catch (Exception ex) when (ex is IOException or JsonException or OperationCanceledException)
        {
            // Disconnected, malformed or stalled callers do not kill the
            // resident or cause automatic action retries.
        }
    }

    private static string ClientLabel(NamedPipeServerStream pipe)
    {
        if (!GetNamedPipeClientProcessId(pipe.SafePipeHandle, out var id)) return "unknown local caller";
        try { return $"{System.Diagnostics.Process.GetProcessById((int)id).ProcessName} (PID {id})"; }
        catch (ArgumentException) { return $"local PID {id}"; }
        catch (System.ComponentModel.Win32Exception) { return $"local PID {id}"; }
    }

    [System.Runtime.InteropServices.DllImport("kernel32.dll", SetLastError = true)]
    private static extern bool GetNamedPipeClientProcessId(Microsoft.Win32.SafeHandles.SafePipeHandle pipe, out uint id);

    private static NamedPipeServerStream CreatePipe(string name, bool first)
    {
        using var identity = WindowsIdentity.GetCurrent();
        var security = new PipeSecurity();
        security.SetAccessRuleProtection(true, false);
        security.AddAccessRule(new PipeAccessRule(identity.User!,
            PipeAccessRights.FullControl, AccessControlType.Allow));
        return NamedPipeServerStreamAcl.Create(name, PipeDirection.InOut, 8,
            PipeTransmissionMode.Byte, PipeOptions.Asynchronous | (first ? PipeOptions.FirstPipeInstance : PipeOptions.None),
            65536, 65536, security);
    }

    private Result Envelope(Request request) => new()
    {
        RequestId = request.RequestId!,
        Operation = request.Operation,
        ActualRoute = "windows.user_session/workstation",
        SessionId = (uint)RuntimeProfile.SessionId,
        Generation = Generation,
        Delivery = "refused",
        Effect = "refused",
        RetrySafety = "safe_not_dispatched",
    };

    private async Task<Result> ExecuteAsync(Request request, string caller, CancellationToken cancellationToken)
    {
        var result = Envelope(request);
        if (request.ExpectedGeneration is not null && request.ExpectedGeneration != Generation)
            return result with { ErrorCode = "stale_generation", Message = "Runtime generation changed" };
        if (!Operations.Contains(request.Operation, StringComparer.Ordinal) &&
            !(grants is not null && request.Operation is "grant.request" or "grant.status" or "grant.revoke"))
            return result with { ErrorCode = "unsupported_operation", Message = "Operation is unavailable in the workstation profile" };
        if (request.SecretPipe is not null || request.CredentialKind is not null)
            return result with { ErrorCode = "profile_refused", Message = "Workstation mode has no credential transport" };
        if (grants is not null)
        {
            grants.SetReady(DesktopSafety.Ready());
            if (request.Operation == "grant.revoke") grants.Stop("revoked_by_caller");
            if (request.Operation is "grant.status" or "grant.revoke")
                return Envelope(request) with { Accepted = true, Delivery = "confirmed", Effect = "not_applicable", Data = grants.DeploymentState() };
            if (request.Operation == "grant.request")
            {
                var reply = await grants.RequestAsync(request, caller).WaitAsync(cancellationToken);
                return Envelope(request) with
                {
                    Accepted = reply.Accepted,
                    ErrorCode = reply.ErrorCode,
                    Delivery = reply.Accepted ? "confirmed" : "refused",
                    Effect = "not_applicable",
                    Data = reply.Data
                };
            }
        }
        if (request.Operation == "runtime.stop")
            return request.ExpectedGeneration == Generation
                ? result with { Accepted = true, Delivery = "confirmed", Effect = "pending", RetrySafety = "not_needed" }
                : result with { ErrorCode = "generation_required", Message = "Stopping requires the observed runtime generation" };

        string? desktop = null;
        try { desktop = DesktopController.GetInputDesktopName(); }
        catch (System.ComponentModel.Win32Exception) { }
        var ready = string.Equals(desktop, "Default", StringComparison.OrdinalIgnoreCase) &&
            NativeMethods.WTSGetActiveConsoleSessionId() == (uint)RuntimeProfile.SessionId;
        if (request.Operation is "status" or "capabilities")
        {
            object data = request.Operation == "status"
                ? new
                {
                    profile = "workstation",
                    instance,
                    ready,
                    integrityRid = DesktopController.GetIntegrityRid(),
                    isLocalSystem = false,
                    processId = Environment.ProcessId,
                    protocol = Contract.Schema,
                    approvalRequired = grants is not null,
                    desktopProduct = grants is not null,
                    artifactRoot = RuntimeProfile.ArtifactRoot,
                }
                : new
                {
                    profile = "workstation",
                    operations = grants is null ? Operations : [.. Operations, "grant.request", "grant.status", "grant.revoke"],
                    authorization = grants is null ? "component_owner" : "native_target_wide_grants",
                    providers = ProviderRouter.DescribeUser(),
                    serviceOperations = Array.Empty<string>(),
                    protectedDesktop = new { available = false, reason = "not_installed_in_this_profile" },
                    sessionRequirement = "active unlocked console Default desktop",
                    knownOmissions = new[] { "elevated applications", "UAC", "lock/login", "RDP and other user sessions" },
                };
            return result with
            {
                Accepted = true,
                Desktop = desktop,
                SessionLocked = SessionStateInspector.IsLocked((uint)RuntimeProfile.SessionId),
                Delivery = "confirmed",
                Effect = "not_applicable",
                RetrySafety = "not_needed",
                Data = data,
            };
        }
        if (!ready)
            return result with { ErrorCode = "desktop_unavailable", Message = "The active unlocked user desktop is unavailable" };
        await _providerGate.WaitAsync(cancellationToken);
        try
        {
            var generation = Generation;
            var refusal = grants?.Authorize(request.Operation, request.ExpectedGeneration);
            if (refusal is not null) return Envelope(request) with
            {
                ErrorCode = refusal,
                Message = "Desktop access refused before dispatch",
                Data = new { requiredScope = DesktopGrants.ScopeFor(request.Operation), requestOperation = "grant.request" }
            };
            return await ProviderRouter.ExecuteAsync(request, generation, cancellationToken);
        }
        finally { _providerGate.Release(); }
    }
}
