using System.IO;
using System.IO.Pipes;
using System.Security.Principal;
using System.Text.Json;

namespace MachineControl.Windows;

/// The ordinary resident owns consent and task admission. Its SYSTEM-only
/// callback grants no credential authority: the unlock broker also requires
/// its independently approved controller signature and stock field discovery.
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
        lock (grants.Gate) return new
        {
            supported = DesktopDisplayCovers.Supported,
            permissionReady = Prepared(),
            preparationRefusal = PreparationRefusal(),
            enabled = grants.PreparedConsole,
            helperApproval = "approved_controller_required",
            helperHealthy = Prepared(),
            setupState = "idle",
            phase = _lease is null ? "idle" : _lease.Ending ? "relocking" : "task_owned",
            controlSessionId = _lease?.Request.ControlOwnership?.Session,
            pausedUntilManualUnlock = false,
            privacy = "opaque_single_display_cover",
            supportedDisplays = 1,
            relockPolicy = "only_if_task_started_locked",
            credentialSource = "approved_controller_one_shot",
        };
    }

    internal void Enable(bool enabled)
    {
        lock (grants.Gate)
        {
            if (_lease is not null) throw new InvalidOperationException("Finish the locked-screen task and relock before changing setup");
            if (enabled && !Prepared()) throw new InvalidOperationException("Install the helper and approve a controller for this account first");
            grants.PrepareConsole(enabled);
        }
    }

    internal void Tick()
    {
        lock (grants.Gate)
        {
            if (_lease is not { } lease) return;
            var owner = lease.Request.ControlOwnership!;
            if (!lease.Ending && (!grants.PreparedConsole || grants.AuthorizationRevision != lease.Revision ||
                grants.Admission.Authorize(owner.Owner, owner.Intent, owner.Session, owner.Generations) is not null))
            {
                lease.Ending = true;
                grants.Admission.Pause("desktop", "relock_pending");
            }
            if (lease.Ending && (lease.Complete || !lease.ServiceStarted) && SessionStateInspector.IsLocked((uint)RuntimeProfile.SessionId) == true)
            {
                _lease = null;
                DesktopSafety.CoverProcessId = 0;
                grants.Admission.Resume("desktop", "relock_pending");
            }
        }
    }

    internal Result Prepare(Request request, string generation)
    {
        lock (grants.Gate)
        {
            var denied = grants.Authorize(request, generation);
            if (denied is not null || !Prepared() || !grants.PreparedConsole ||
                request.ControlOwnership?.StartedLocked != true ||
                SessionStateInspector.IsLocked((uint)RuntimeProfile.SessionId) != true || _lease is not null)
                return new Result
                {
                    RequestId = request.RequestId!,
                    Operation = request.Operation,
                    Generation = generation,
                    ErrorCode = denied ?? "locked_console_not_prepared",
                    Delivery = "refused",
                    Effect = "refused"
                };
            var lease = new Lease(request, grants.AuthorizationRevision, UnlockPolicy.Read(Instance));
            _lease = lease;
            _ = ServeGuardAsync(lease);
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

    private async Task ServeGuardAsync(Lease lease)
    {
        try
        {
            while (!stop.IsCancellationRequested)
            {
                lock (grants.Gate) if (_lease != lease) break;
                using var pipe = DesktopUacNative.Server(lease.Pipe, systemOnly: true);
                await pipe.WaitForConnectionAsync(stop);
                using var deadline = CancellationTokenSource.CreateLinkedTokenSource(stop);
                deadline.CancelAfter(TimeSpan.FromSeconds(2));
                try
                {
                    DesktopUacNative.RequireSystem(pipe);
                    using var frame = JsonDocument.Parse(await UnlockWire.ReadLineAsync(pipe, deadline.Token));
                    object reply;
                    lock (grants.Gate)
                    {
                        Tick();
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
                            allowed = _lease == lease && !lease.Ending && Prepared() &&
                            UnlockPolicy.Read(Instance) == lease.ProtectedGrant &&
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
        catch (OperationCanceledException) when (stop.IsCancellationRequested) { }
        catch (Exception error) when (error is IOException or UnauthorizedAccessException)
        { lock (grants.Gate) grants.Stop("locked_use_guard_failed"); }
    }
}
