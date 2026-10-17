using System.IO;
using System.IO.Pipes;
using System.Security.Principal;
using System.Text.Json;

namespace MachineControl.Windows;

/// The ordinary resident owns consent and task admission. Its SYSTEM-only
/// callback retains live owner authority. The broker independently requires
/// native enrollment or an approved controller plus stock field discovery.
internal sealed class DesktopLockedUse(DesktopGrants grants, CancellationToken stop)
{
    private Lease? _lease;
    internal const string Instance = "desktop";
    internal static DesktopLockedUse? Current { get; set; }
    private sealed class Lease(Request request, long revision, UnlockGrant protectedGrant)
    {
        internal readonly Request Request = request;
        internal readonly long Revision = revision;
        internal readonly UnlockGrant ProtectedGrant = protectedGrant;
        internal readonly string Pipe = "machine-control-locked-guard-" + Guid.NewGuid().ToString("n");
        internal readonly CancellationTokenSource Done = new();
        internal bool Ending;
        internal bool Complete;
        internal bool ServiceStarted;
    }

    internal static bool Prepared() => PreparationRefusal() is null;

    private static string? PreparationRefusal()
    {
        try
        {
            var grant = UnlockPolicy.Read(Instance);
            using var identity = WindowsIdentity.GetCurrent();
            if (!DesktopDisplayCovers.Supported) return "covered_display_configuration_unsupported";
            if (!DesktopUacNative.Installed()) return "helper_unavailable";
            if (grant.TargetUserSid != identity.User?.Value || grant.TransportUserSid != identity.User?.Value)
                return "controller_account_mismatch";
            var image = Environment.ProcessPath!;
            if (image.StartsWith(@"\\?\", StringComparison.Ordinal)) image = image[4..];
            return string.Equals(image, DesktopUacNative.Executable, StringComparison.OrdinalIgnoreCase)
                ? null : "installed_companion_required";
        }
        catch (Exception error) when (error is IOException or InvalidDataException or JsonException or ArgumentException or FormatException or UnauthorizedAccessException or System.ComponentModel.Win32Exception or System.Security.Cryptography.CryptographicException)
        { return error is UnauthorizedAccessException ? "controller_approval_unreadable" : "controller_approval_unavailable"; }
    }

    internal object State()
    {
        // Protected installation discovery may block on filesystem/provider
        // state. Never run it under the authority lock used by native Stop.
        var preparation = PreparationRefusal();
        var enrolled = false;
        try { enrolled = UnlockPolicy.Read(Instance).CredentialSource == "local_enrollment"; }
        catch (Exception) { }
        lock (grants.Gate) return new
        {
            supported = DesktopDisplayCovers.Supported,
            permissionReady = preparation is null,
            preparationRefusal = preparation,
            enabled = grants.PreparedConsole,
            helperApproval = enrolled ? "local_account_enrolled" : "approved_controller_required",
            helperHealthy = preparation is null,
            setupState = "idle",
            phase = _lease is null ? "idle" : _lease.Ending ? "relocking" : "task_owned",
            controlSessionId = _lease?.Request.ControlOwnership?.Session,
            pausedUntilManualUnlock = false,
            privacy = "opaque_single_display_cover",
            supportedDisplays = 1,
            relockPolicy = "only_if_task_started_locked",
            credentialSource = enrolled ? "service_enrolled_password" : "approved_controller_one_shot",
        };
    }

    internal void Enable(bool enabled)
    {
        if (enabled && !Prepared()) throw new InvalidOperationException("Set up covered desktop access for this account first");
        lock (grants.Gate)
        {
            if (_lease is not null) throw new InvalidOperationException("Finish the locked-screen task and relock before changing setup");
            grants.PrepareConsole(enabled);
        }
    }

    internal void Tick()
    {
        Lease? observed;
        lock (grants.Gate) observed = _lease;
        if (observed is null) return;
        var locked = SessionStateInspector.IsLocked((uint)RuntimeProfile.SessionId) == true;
        lock (grants.Gate)
        {
            if (_lease is not { } lease || lease != observed) return;
            var owner = lease.Request.ControlOwnership!;
            if (!lease.Ending && (!grants.PreparedConsole || grants.AuthorizationRevision != lease.Revision ||
                grants.Admission.Authorize(owner.Owner, owner.Intent, owner.Session, owner.Generations) is not null))
            {
                lease.Ending = true;
                grants.Admission.Pause("desktop", "relock_pending");
            }
            if (lease.Ending && (lease.Complete || !lease.ServiceStarted) && locked)
            {
                _lease = null;
                lease.Done.Cancel();
                DesktopSafety.CoverProcessId = 0;
                grants.Admission.Resume("desktop", "relock_pending");
            }
        }
    }

    internal Result Prepare(Request request, string generation, CancellationToken cancellation = default)
    {
        // Protected installation/policy and WTS observations can wait. The
        // captured request generation is checked after all preparation.
        var prepared = Prepared();
        var locked = SessionStateInspector.IsLocked((uint)RuntimeProfile.SessionId) == true;
        var policy = prepared ? UnlockPolicy.Read(Instance) : null;
        cancellation.ThrowIfCancellationRequested();
        if (policy?.CredentialSource == "local_enrollment" && request.Operation == "session.unlock.prepare")
            return new Result
            {
                RequestId = request.RequestId!,
                Operation = request.Operation,
                Generation = generation,
                ErrorCode = "use_session_unlock",
                Delivery = "refused",
                Effect = "refused"
            };
        lock (grants.Gate)
        {
            cancellation.ThrowIfCancellationRequested();
            var denied = grants.Authorize(request, generation);
            if (denied is not null || !prepared || policy is null || !grants.PreparedConsole ||
                request.ControlOwnership?.StartedLocked != true ||
                !locked || _lease is not null)
                return new Result
                {
                    RequestId = request.RequestId!,
                    Operation = request.Operation,
                    Generation = generation,
                    ErrorCode = denied ?? "locked_console_not_prepared",
                    Delivery = "refused",
                    Effect = "refused"
                };
            var lease = new Lease(request, grants.AuthorizationRevision, policy);
            _lease = lease;
            _ = Task.Run(() => ServeGuardAsync(lease));
            return new Result
            {
                RequestId = request.RequestId!,
                Operation = request.Operation,
                Generation = generation,
                Accepted = true,
                ActualRoute = "windows.desktop_locked_use",
                Delivery = "confirmed",
                Effect = "not_applicable",
                Data = new
                {
                    operation = "desktop.unlock",
                    credentialKind = "password",
                    instance = Instance,
                    guardPipe = lease.Pipe,
                    residentPid = Environment.ProcessId,
                    privacy = "opaque_single_display_cover",
                    startedLocked = true,
                    credentialTransport = "separate_unlock_relay"
                }
            };
        }
    }

    internal async Task<Result> UnlockAsync(Request request, string generation, CancellationToken cancellation)
    {
        try
        {
            if (UnlockPolicy.Read(Instance).CredentialSource != "local_enrollment")
                return new Result
                {
                    RequestId = request.RequestId!,
                    Operation = request.Operation,
                    Generation = generation,
                    ErrorCode = "native_enrollment_required",
                    Delivery = "refused",
                    Effect = "refused"
                };
        }
        catch (Exception error) when (error is IOException or InvalidDataException or UnauthorizedAccessException)
        {
            return new Result
            {
                RequestId = request.RequestId!,
                Operation = request.Operation,
                Generation = generation,
                ErrorCode = "native_enrollment_required",
                Delivery = "refused",
                Effect = "refused"
            };
        }
        var prepared = Prepare(request, generation, cancellation);
        if (!prepared.Accepted) return prepared;
        Lease lease;
        lock (grants.Gate) lease = _lease!;
        var result = new TaskCompletionSource<Result>(TaskCreationOptions.RunContinuationsAsynchronously);
        _ = RunEnrolledAsync(lease, result, generation, cancellation);
        return await result.Task.WaitAsync(cancellation);
    }

    private async Task RunEnrolledAsync(Lease lease, TaskCompletionSource<Result> completion, string generation, CancellationToken cancellation)
    {
        try
        {
            using var pipe = new NamedPipeClientStream(".", UnlockPolicy.Pipe(Instance), PipeDirection.InOut,
                PipeOptions.Asynchronous, TokenImpersonationLevel.Identification);
            // Before result, request cancellation closes the service connection;
            // afterward the live owner callback and runtime lifetime fence it.
            using var requestCancellation = cancellation.Register(() => pipe.Dispose());
            await pipe.ConnectAsync(5000, stop);
            UnlockNative.RequireServicePeer(pipe, Instance);
            await UnlockWire.WriteAsync(pipe, new UnlockHello("desktop.unlock", "password", lease.Pipe, (uint)Environment.ProcessId), stop);
            using var frame = JsonDocument.Parse(await UnlockWire.ReadLineAsync(pipe, stop));
            var root = frame.RootElement;
            if (root.GetProperty("stage").GetString() == "result")
            {
                var received = root.GetProperty("result").Deserialize<Result>(Contract.Json)!;
                completion.TrySetResult(received with { RequestId = lease.Request.RequestId!, Operation = lease.Request.Operation, Generation = generation });
            }
            else completion.TrySetResult(new Result
            {
                RequestId = lease.Request.RequestId!,
                Operation = lease.Request.Operation,
                Generation = generation,
                ErrorCode = "enrolled_unlock_refused",
                Delivery = root.TryGetProperty("delivery", out var delivery) && delivery.GetString() == "unknown" ? "unknown" : "refused",
                Effect = root.TryGetProperty("delivery", out delivery) && delivery.GetString() == "unknown" ? "unknown" : "refused",
                RetrySafety = "never_automatically",
                Evidence = root.Clone()
            });
            requestCancellation.Unregister();
            // Keep the authenticated connection alive for the finite task. EOF
            // means the service guardian has finished (or its process failed).
            var remaining = new byte[1];
            while (await pipe.ReadAsync(remaining, stop) != 0) { }
        }
        catch (Exception)
        {
            // A detached native task must always complete its waiting request,
            // including unexpected malformed service frames or peer failures.
            completion.TrySetResult(new Result
            {
                RequestId = lease.Request.RequestId!,
                Operation = lease.Request.Operation,
                Generation = generation,
                ErrorCode = "enrolled_unlock_interrupted",
                Delivery = "unknown",
                Effect = "unknown",
                RetrySafety = "never_automatically"
            });
        }
        finally
        {
            lock (grants.Gate)
            {
                if (_lease == lease)
                {
                    lease.Ending = true;
                    grants.Admission.Pause("desktop", "relock_pending");
                }
            }
        }
    }

    private async Task ServeGuardAsync(Lease lease)
    {
        using var guardStop = CancellationTokenSource.CreateLinkedTokenSource(stop, lease.Done.Token);
        var guardToken = guardStop.Token;
        try
        {
            while (!guardToken.IsCancellationRequested)
            {
                lock (grants.Gate) if (_lease != lease) break;
                using var pipe = DesktopUacNative.Server(lease.Pipe, systemOnly: true);
                await pipe.WaitForConnectionAsync(guardToken);
                using var deadline = CancellationTokenSource.CreateLinkedTokenSource(guardToken);
                deadline.CancelAfter(TimeSpan.FromSeconds(2));
                try
                {
                    DesktopUacNative.RequireSystem(pipe);
                    using var frame = JsonDocument.Parse(await UnlockWire.ReadLineAsync(pipe, deadline.Token));
                    Tick();
                    var prepared = Prepared();
                    var policy = prepared ? UnlockPolicy.Read(Instance) : null;
                    deadline.Token.ThrowIfCancellationRequested();
                    object reply;
                    lock (grants.Gate)
                    {
                        if (frame.RootElement.TryGetProperty("attemptStarted", out var started) && started.GetBoolean())
                            lease.ServiceStarted = true;
                        if (frame.RootElement.TryGetProperty("guardianPid", out var guardian) && guardian.ValueKind == JsonValueKind.Number)
                            DesktopSafety.CoverProcessId = guardian.GetInt32();
                        if (frame.RootElement.TryGetProperty("physicalTakeover", out var takeover) && takeover.GetBoolean())
                            grants.Activity.CoveredTakeover();
                        if (frame.RootElement.TryGetProperty("complete", out var complete) && complete.GetBoolean())
                        { lease.Ending = true; lease.Complete = true; grants.Admission.Pause("desktop", "relock_pending"); }
                        var owner = lease.Request.ControlOwnership!;
                        reply = new
                        {
                            allowed = _lease == lease && !lease.Ending && prepared &&
                            policy == lease.ProtectedGrant &&
                            grants.PreparedConsole && grants.AuthorizationRevision == lease.Revision &&
                            grants.Admission.Authorize(owner.Owner, owner.Intent, owner.Session, owner.Generations) is null
                        };
                    }
                    await UnlockWire.WriteAsync(pipe, reply, deadline.Token);
                }
                catch (Exception error) when (error is IOException or InvalidDataException or JsonException or OperationCanceledException or UnauthorizedAccessException or ArgumentException or FormatException or System.Security.Cryptography.CryptographicException)
                { lock (grants.Gate) grants.Stop("locked_use_guard_failed"); }
            }
        }
        catch (OperationCanceledException) when (guardToken.IsCancellationRequested) { }
        catch (Exception error) when (error is IOException or UnauthorizedAccessException)
        { lock (grants.Gate) grants.Stop("locked_use_guard_failed"); }
        finally { lease.Done.Dispose(); }
    }
}
