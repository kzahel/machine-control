using System.ComponentModel;
using System.Diagnostics;
using System.IO;
using System.IO.Pipes;
using System.Security.AccessControl;
using System.Security.Cryptography;
using System.Security.Principal;
using System.ServiceProcess;
using System.Text.Json;

namespace MachineControl.Windows;

internal sealed class UnlockWindowsService : ServiceBase
{
    private readonly UnlockService _host;
    private readonly CancellationTokenSource _stop = new();
    private Task? _run;
    public UnlockWindowsService(string instance)
    {
        ServiceName = UnlockPolicy.Service(instance);
        CanHandleSessionChangeEvent = true;
        _host = new UnlockService(instance);
    }
    protected override void OnStart(string[] args) => _run = _host.RunAsync(_stop.Token);
    protected override void OnSessionChange(SessionChangeDescription change) => _host.Invalidate();
    protected override void OnStop()
    {
        _stop.Cancel();
        try { _run?.GetAwaiter().GetResult(); }
        catch (OperationCanceledException) { }
    }
}

internal sealed record UnlockChallenge(string Protocol, string Instance, string ServiceGeneration,
    long SessionEpoch, uint SessionId, string SessionLogonId, string GrantRevision, string TargetUserSid,
    string ControllerFingerprint, string CredentialKind, string Nonce, DateTimeOffset Deadline, string? DesktopControlBinding = null);
internal sealed record UnlockHello(string Operation, string? CredentialKind, string? GuardPipe = null, uint? ResidentPid = null);
internal sealed record UnlockProof(string Signature);
internal sealed record UnlockWorkerStart(string Instance, string Revision, uint SessionId,
    string SessionLogonId, string TargetUserSid, string CredentialKind, string Generation, bool PrepareDesktop = false);
internal sealed record UnlockWorkerMessage(string Stage, Result? Result = null, string? Failure = null, int? NativeError = null);

internal sealed class UnlockProgress
{
    public string Phase { get; set; } = "hello";
    public bool CredentialRead { get; set; }
    public bool ForwardAttempted { get; set; }
    public bool UnlockConfirmed { get; set; }
    public string? WorkerFailure { get; set; }
    public int? NativeError { get; set; }
}

internal sealed class UnlockService(string instance)
{
    public const string Protocol = "machine-control-unlock/v0";
    private readonly string _generation = Guid.NewGuid().ToString("n");
    private long _epoch;
    private readonly SemaphoreSlim _attempt = new(1, 1);
    public void Invalidate() => Interlocked.Increment(ref _epoch);

    public async Task RunAsync(CancellationToken stop)
    {
        if (!WindowsIdentity.GetCurrent().IsSystem) throw new UnauthorizedAccessException("LocalSystem required");
        var pending = new List<Task>();
        using var capacity = new SemaphoreSlim(8, 8);
        var firstInstance = true;
        try
        {
            while (!stop.IsCancellationRequested)
            {
                await capacity.WaitAsync(stop);
                NamedPipeServerStream? pipe = null;
                try
                {
                    pipe = CreatePipe(UnlockPolicy.Pipe(instance), firstInstance);
                    firstInstance = false;
                    await pipe.WaitForConnectionAsync(stop);
                    pending.RemoveAll(task => task.IsCompletedSuccessfully);
                    pending.Add(ServeAsync(pipe));
                    pipe = null;
                }
                finally
                {
                    if (pipe is not null) { await pipe.DisposeAsync(); capacity.Release(); }
                }
            }
        }
        finally { await Task.WhenAll(pending); }

        async Task ServeAsync(NamedPipeServerStream pipe)
        {
            await using var owned = pipe;
            using var timeout = CancellationTokenSource.CreateLinkedTokenSource(stop);
            timeout.CancelAfter(TimeSpan.FromSeconds(instance == DesktopLockedUse.Instance ? 920 : 70));
            var progress = new UnlockProgress();
            try { await HandleAsync(pipe, progress, timeout.Token); }
            catch (Exception error)
            {
                // Input errors and disconnects do not terminate the service.
                // Do not echo attacker-controlled input or provider exceptions.
                try
                {
                    await UnlockWire.WriteAsync(pipe, new
                    {
                        stage = "refused",
                        errorCode = "unlock_refused",
                        phase = progress.Phase,
                        errorType = error.GetType().Name,
                        workerFailure = progress.WorkerFailure,
                        nativeError = progress.NativeError ?? (error as Win32Exception)?.NativeErrorCode,
                        credentialRead = progress.CredentialRead,
                        delivery = progress.ForwardAttempted ? "unknown" : "not_sent",
                        retrySafety = "never_automatically"
                    }, timeout.Token);
                }
                catch (Exception) { }
            }
            finally { capacity.Release(); }
        }
    }

    private async Task HandleAsync(NamedPipeServerStream pipe, UnlockProgress progress, CancellationToken stop)
    {
        using var first = CancellationTokenSource.CreateLinkedTokenSource(stop);
        first.CancelAfter(TimeSpan.FromSeconds(5));
        var hello = JsonSerializer.Deserialize<UnlockHello>(await UnlockWire.ReadLineAsync(pipe, first.Token), Contract.Json)
            ?? throw new InvalidDataException();
        if (hello.Operation == "status")
        {
            string state;
            try { _ = UnlockPolicy.Read(instance); state = "armed"; }
            catch (Exception)
            { state = "unarmed_or_invalid"; }
            await UnlockWire.WriteAsync(pipe, new { stage = "status", protocol = Protocol, state, generation = _generation }, stop);
            return;
        }
        var desktop = instance == DesktopLockedUse.Instance;
        if (hello.Operation != (desktop ? "desktop.unlock" : "unlock") ||
            hello.CredentialKind is not ("password" or "pin") || desktop && hello.CredentialKind != "password")
            throw new InvalidDataException();
        if (!_attempt.Wait(0))
        {
            await RefuseAsync(pipe, "unlock_attempt_active", stop);
            return;
        }
        try { await HandleUnlockAsync(pipe, hello, progress, stop); }
        finally { _attempt.Release(); }
    }

    private async Task HandleUnlockAsync(NamedPipeServerStream pipe, UnlockHello hello, UnlockProgress progress, CancellationToken stop)
    {
        var desktop = instance == DesktopLockedUse.Instance;
        await using var control = desktop ? await DesktopUnlockControl.CreateAsync(pipe, hello, stop) : null;
        UnlockGrant grant;
        try { grant = UnlockPolicy.Read(instance); }
        catch (Exception)
        {
            await RefuseAsync(pipe, "not_armed_or_expired", stop);
            return;
        }
        string? caller = null;
        pipe.RunAsClient(() => { using var identity = WindowsIdentity.GetCurrent(); caller = identity.User?.Value; });
        if (caller != grant.TransportUserSid)
        {
            await RefuseAsync(pipe, "transport_caller_denied", stop);
            return;
        }
        var session = NativeMethods.WTSGetActiveConsoleSessionId();
        var epoch = Interlocked.Read(ref _epoch);
        try { UnlockNative.RequireLockedAccount(session, grant.TargetUserSid); _ = UnlockAccount.UniqueDisplayName(grant.TargetUserSid); }
        catch (Exception)
        {
            await RefuseAsync(pipe, "locked_local_account_unavailable", stop);
            return;
        }
        var challenge = new UnlockChallenge(Protocol, instance, _generation, epoch, session,
            UnlockNative.ConsoleLogonId(session), grant.Revision, grant.TargetUserSid, UnlockPolicy.Fingerprint(grant), hello.CredentialKind!,
            Convert.ToHexString(RandomNumberGenerator.GetBytes(32)), DateTimeOffset.UtcNow.AddSeconds(45), control?.Binding);
        var challengeText = Contract.Serialize(challenge);
        var timer = Stopwatch.StartNew();
        await UnlockWire.WriteAsync(pipe, new { stage = "challenge", challenge = challengeText }, stop);
        progress.Phase = "controller_proof";
        using var proofTimeout = CancellationTokenSource.CreateLinkedTokenSource(stop);
        proofTimeout.CancelAfter(TimeSpan.FromSeconds(15));
        var proof = JsonSerializer.Deserialize<UnlockProof>(await UnlockWire.ReadLineAsync(pipe, proofTimeout.Token), Contract.Json);
        if (proof is null || !UnlockPolicy.Verify(grant, challengeText, proof.Signature))
        {
            await RefuseAsync(pipe, "controller_signature_denied", stop);
            return;
        }
        void Check()
        {
            control?.Check();
            if (timer.Elapsed > TimeSpan.FromSeconds(45) || DateTimeOffset.UtcNow >= challenge.Deadline ||
                Interlocked.Read(ref _epoch) != epoch || UnlockPolicy.Read(instance) != grant ||
                UnlockNative.ConsoleLogonId(session) != challenge.SessionLogonId)
                throw new InvalidDataException("unlock_authority_changed");
            UnlockNative.RequireLockedAccount(session, grant.TargetUserSid);
        }
        progress.Phase = "authority_check";
        Check();
        if (control is not null) await control.StartAsync(challenge, stop);
        using var attempt = CancellationTokenSource.CreateLinkedTokenSource(stop, control?.Interrupted ?? CancellationToken.None);
        await ExecuteAsync(pipe, grant, challenge, Check, progress, attempt.Token, prepareDesktop: true);
        Check();
        await ExecuteAsync(pipe, grant, challenge, Check, progress, attempt.Token);
        if (control is not null && progress.UnlockConfirmed) await control.WaitForEndAsync(stop);
    }

    private async Task ExecuteAsync(NamedPipeServerStream client, UnlockGrant grant, UnlockChallenge challenge,
        Action check, UnlockProgress progress, CancellationToken stop, bool prepareDesktop = false)
    {
        progress.Phase = prepareDesktop ? "preparation_launch" : "credential_worker_launch";
        var privatePipe = "machine-control-unlock-worker-" + Guid.NewGuid().ToString("n");
        await using var worker = PipeTransport.CreateSystemOnlyServer(privatePipe);
        var child = SessionLauncher.LaunchSystem(challenge.SessionId, privatePipe, _generation, instance, prepareDesktop);
        var secretRequested = false;
        try
        {
            progress.Phase = prepareDesktop ? "preparation_connect" : "credential_worker_connect";
            await worker.WaitForConnectionAsync(stop);
            progress.Phase = prepareDesktop ? "desktop_preparation" : "credential_discovery";
            await UnlockWire.WriteAsync(worker, new UnlockWorkerStart(instance, grant.Revision,
                challenge.SessionId, challenge.SessionLogonId, grant.TargetUserSid, challenge.CredentialKind, _generation, prepareDesktop), stop);
            while (true)
            {
                var message = JsonSerializer.Deserialize<UnlockWorkerMessage>(await UnlockWire.ReadLineAsync(worker, stop), Contract.Json)
                    ?? throw new InvalidDataException();
                if (message.Stage == "fault")
                {
                    progress.WorkerFailure = message.Failure;
                    progress.NativeError = message.NativeError;
                    throw new InvalidOperationException("Unlock worker refused");
                }
                if (prepareDesktop && message.Stage == "prepared") { check(); return; }
                if (message.Stage == "result")
                {
                    progress.UnlockConfirmed = message.Result?.Effect == "confirmed";
                    await UnlockWire.WriteAsync(client, new { stage = "result", result = message.Result }, stop);
                    return;
                }
                check();
                if (message.Stage == "check")
                    await UnlockWire.WriteAsync(worker, new { allowed = true }, stop);
                else if (message.Stage == "ready" && !prepareDesktop && !secretRequested)
                {
                    secretRequested = true;
                    await UnlockWire.WriteAsync(client, new { stage = "ready", credentialTransport = "uint16le-length+utf8", maximumBytes = 256 }, stop);
                    byte[]? secret = null;
                    try
                    {
                        progress.Phase = "credential_transport";
                        progress.CredentialRead = true;
                        secret = await UnlockWire.ReadSecretAsync(client, stop);
                        check();
                        progress.ForwardAttempted = true;
                        await UnlockWire.WriteSecretAsync(worker, secret, stop);
                        progress.Phase = "credential_result";
                    }
                    finally { if (secret is not null) CryptographicOperations.ZeroMemory(secret); }
                }
                else throw new InvalidDataException();
            }
        }
        finally
        {
            try
            {
                using var process = Process.GetProcessById(child.ProcessId);
                if (!process.HasExited) { process.Kill(entireProcessTree: true); process.WaitForExit(3000); }
            }
            catch (ArgumentException) { }
        }
    }

    private static Task RefuseAsync(Stream pipe, string code, CancellationToken stop) =>
        UnlockWire.WriteAsync(pipe, new { stage = "refused", errorCode = code, delivery = "refused", credentialRead = false }, stop);

    private static NamedPipeServerStream CreatePipe(string name, bool firstInstance)
    {
        var acl = new PipeSecurity();
        acl.SetAccessRuleProtection(true, false);
        acl.AddAccessRule(new PipeAccessRule(new SecurityIdentifier(WellKnownSidType.LocalSystemSid, null),
            PipeAccessRights.FullControl, AccessControlType.Allow));
        acl.AddAccessRule(new PipeAccessRule(new SecurityIdentifier(WellKnownSidType.AuthenticatedUserSid, null),
            PipeAccessRights.ReadWrite, AccessControlType.Allow));
        return NamedPipeServerStreamAcl.Create(name, PipeDirection.InOut, 8, PipeTransmissionMode.Byte,
            PipeOptions.Asynchronous | (firstInstance ? PipeOptions.FirstPipeInstance : PipeOptions.None), 4096, 4096, acl);
    }
}
