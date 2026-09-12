using System.IO;
using System.IO.Pipes;
using System.Security.AccessControl;
using System.Security.Principal;
using System.Text;
using System.Text.Json;

namespace MachineControl.Windows;

internal sealed class UserHost(string instance)
{
    private readonly string _generation = Guid.NewGuid().ToString("n");
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
        try
        {
            while (!cancellationToken.IsCancellationRequested)
            {
                await using var server = CreatePipe(pipe);
                await server.WaitForConnectionAsync(cancellationToken);
                try
                {
                    using var inputTimeout = CancellationTokenSource.CreateLinkedTokenSource(cancellationToken);
                    inputTimeout.CancelAfter(TimeSpan.FromSeconds(10));
                    using var reader = new StreamReader(server, Encoding.UTF8, false, 4096, leaveOpen: true);
                    var text = new StringBuilder();
                    var character = new char[1];
                    while (await reader.ReadAsync(character.AsMemory(), inputTimeout.Token) != 0)
                    {
                        if (character[0] == '\n') break;
                        if (text.Length >= 1024 * 1024)
                            throw new InvalidDataException("Request exceeds 1 MiB");
                        text.Append(character[0]);
                    }
                    var request = Contract.ParseRequest(text.ToString());
                    var result = await ExecuteAsync(request, cancellationToken);
                    using var outputTimeout = CancellationTokenSource.CreateLinkedTokenSource(cancellationToken);
                    outputTimeout.CancelAfter(TimeSpan.FromSeconds(10));
                    await using var writer = new StreamWriter(server, new UTF8Encoding(false), 4096, leaveOpen: true);
                    await writer.WriteLineAsync(Contract.Serialize(result).AsMemory(), outputTimeout.Token);
                    await writer.FlushAsync(outputTimeout.Token);
                    if (request.Operation == "runtime.stop" && result.Accepted) return;
                }
                catch (Exception ex) when (ex is IOException or JsonException or OperationCanceledException)
                {
                    // A disconnected, malformed or stalled caller cannot kill
                    // the resident or cause an automatic action retry.
                }
            }
        }
        finally { ProviderRouter.Stop(); }
    }

    private static NamedPipeServerStream CreatePipe(string name)
    {
        using var identity = WindowsIdentity.GetCurrent();
        var security = new PipeSecurity();
        security.SetAccessRuleProtection(true, false);
        security.AddAccessRule(new PipeAccessRule(identity.User!,
            PipeAccessRights.FullControl, AccessControlType.Allow));
        return NamedPipeServerStreamAcl.Create(name, PipeDirection.InOut, 1,
            PipeTransmissionMode.Byte, PipeOptions.Asynchronous | PipeOptions.FirstPipeInstance,
            65536, 65536, security);
    }

    private Result Envelope(Request request) => new()
    {
        RequestId = request.RequestId!,
        Operation = request.Operation,
        ActualRoute = "windows.user_session/workstation",
        SessionId = (uint)RuntimeProfile.SessionId,
        Generation = _generation,
        Delivery = "refused",
        Effect = "refused",
        RetrySafety = "safe_not_dispatched",
    };

    private async Task<Result> ExecuteAsync(Request request, CancellationToken cancellationToken)
    {
        var result = Envelope(request);
        if (request.ExpectedGeneration is not null && request.ExpectedGeneration != _generation)
            return result with { ErrorCode = "stale_generation", Message = "Runtime generation changed" };
        if (!Operations.Contains(request.Operation, StringComparer.Ordinal))
            return result with { ErrorCode = "unsupported_operation", Message = "Operation is unavailable in the workstation profile" };
        if (request.SecretPipe is not null || request.CredentialKind is not null)
            return result with { ErrorCode = "profile_refused", Message = "Workstation mode has no credential transport" };
        if (request.Operation == "runtime.stop")
            return request.ExpectedGeneration == _generation
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
                    artifactRoot = RuntimeProfile.ArtifactRoot,
                }
                : new
                {
                    profile = "workstation",
                    operations = Operations,
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
        return await ProviderRouter.ExecuteAsync(request, _generation, cancellationToken);
    }
}
