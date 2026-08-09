using System.Diagnostics;
using System.Runtime.InteropServices;
using System.Security.Cryptography;
using System.ServiceProcess;

namespace MachineControl.Windows;

internal sealed class BrokerWindowsService : ServiceBase
{
    private CancellationTokenSource? _cancellation;
    private Task? _runTask;

    public BrokerWindowsService()
    {
        ServiceName = "MachineControlRuntime";
        CanStop = true;
        CanShutdown = true;
        AutoLog = true;
    }

    protected override void OnStart(string[] args)
    {
        _cancellation = new CancellationTokenSource();
        _runTask = new BrokerHost().RunAsync(_cancellation.Token);
    }

    protected override void OnStop()
    {
        _cancellation?.Cancel();
        try { _runTask?.Wait(TimeSpan.FromSeconds(10)); } catch { }
    }

    protected override void OnShutdown() => OnStop();
}

internal sealed class BrokerHost
{
    public const string ServicePipe = "machine-control-runtime";
    public const string LoginPipe = "machine-control-runtime-login";

    private string _runtimeGeneration = Guid.NewGuid().ToString("n");
    private SessionProcess? _ordinarySession;
    private SessionProcess? _protectedSession;
    private readonly SemaphoreSlim _requestGate = new(1, 1);

    public async Task RunAsync(CancellationToken cancellationToken)
    {
        var loginLoop = RunLoginPipeAsync(cancellationToken);
        try
        {
            while (!cancellationToken.IsCancellationRequested)
            {
                await using var server = PipeTransport.CreateServiceServer(ServicePipe);
                try
                {
                    var (requestText, writer) = await PipeTransport.AcceptAsync(
                        server,
                        cancellationToken);
                    await using (writer)
                    {
                        await _requestGate.WaitAsync(cancellationToken);
                        string response;
                        try
                        {
                            response = await HandleAsync(
                                requestText,
                                cancellationToken);
                        }
                        finally
                        {
                            _requestGate.Release();
                        }
                        await writer.WriteLineAsync(
                            response.AsMemory(),
                            cancellationToken);
                    }
                }
                catch (OperationCanceledException) when (
                    cancellationToken.IsCancellationRequested)
                {
                    break;
                }
                catch (Exception ex)
                {
                    try
                    {
                        EventLog.WriteEntry(
                            "MachineControlRuntime",
                            ex.ToString(),
                            EventLogEntryType.Error);
                    }
                    catch { }
                }
            }
        }
        finally
        {
            StopSessions();
            try { await loginLoop; } catch (OperationCanceledException) { }
        }
    }

    private async Task RunLoginPipeAsync(CancellationToken cancellationToken)
    {
        while (!cancellationToken.IsCancellationRequested)
        {
            await using var server = PipeTransport.CreateServiceServer(LoginPipe);
            byte[]? secret = null;
            try
            {
                var accepted = await PipeTransport.AcceptLoginAsync(
                    server,
                    cancellationToken);
                secret = accepted.Secret;
                await using (accepted.Writer)
                {
                    await _requestGate.WaitAsync(cancellationToken);
                    string response;
                    try
                    {
                        response = await HandleLoginAsync(
                            accepted.CredentialKind,
                            secret,
                            cancellationToken);
                    }
                    finally
                    {
                        _requestGate.Release();
                    }
                    await accepted.Writer.WriteLineAsync(
                        response.AsMemory(),
                        cancellationToken);
                }
            }
            catch (OperationCanceledException) when (
                cancellationToken.IsCancellationRequested)
            {
                break;
            }
            catch (Exception ex)
            {
                WriteServiceError(ex);
            }
            finally
            {
                if (secret is not null)
                {
                    CryptographicOperations.ZeroMemory(secret);
                }
            }
        }
    }

    private async Task<string> HandleLoginAsync(
        string credentialKind,
        byte[] secret,
        CancellationToken cancellationToken)
    {
        var started = Stopwatch.StartNew();
        var requestId = Guid.NewGuid().ToString("n");
        var activeSession = NativeMethods.WTSGetActiveConsoleSessionId();
        if (activeSession == uint.MaxValue || HasInteractiveUser(activeSession))
        {
            return Contract.Serialize(new Result
            {
                RequestId = requestId,
                Operation = "session.login",
                Accepted = false,
                ActualRoute = "windows.service/protected_login",
                SessionId = activeSession == uint.MaxValue
                    ? null
                    : activeSession,
                Generation = _runtimeGeneration,
                Delivery = "refused",
                Effect = "refused",
                ErrorCode = "login_requires_no_user",
                Message = "Credential login is accepted only when no console " +
                    "user is logged in",
                ElapsedMs = started.ElapsedMilliseconds,
            });
        }

        try
        {
            var protectedSession = await EnsureSessionAsync(
                protectedAuthority: true,
                cancellationToken);
            var probeText = await PipeTransport.CallAsync(
                protectedSession.PipeName,
                Contract.Serialize(new Request
                {
                    Operation = "status",
                    RequestId = Guid.NewGuid().ToString("n"),
                }),
                TimeSpan.FromSeconds(25),
                cancellationToken);
            var probe = Contract.ParseResult(probeText);
            if (!string.Equals(
                    probe.Desktop,
                    "Winlogon",
                    StringComparison.OrdinalIgnoreCase))
            {
                return Contract.Serialize(new Result
                {
                    RequestId = requestId,
                    Operation = "session.login",
                    Accepted = false,
                    ActualRoute = "windows.service/protected_login",
                    SessionId = activeSession,
                    Generation = _runtimeGeneration,
                    Delivery = "refused",
                    Effect = "refused",
                    ErrorCode = "winlogon_not_active",
                    Message = "The active input desktop is not Winlogon",
                    Evidence = new { inputDesktop = probe.Desktop },
                    ElapsedMs = started.ElapsedMilliseconds,
                });
            }

            var secretPipe = $"machine-control-secret-{Guid.NewGuid():n}";
            using var secretCancellation =
                CancellationTokenSource.CreateLinkedTokenSource(
                    cancellationToken);
            var secretTask = PipeTransport.SendSecretOnceAsync(
                secretPipe,
                secret,
                TimeSpan.FromSeconds(20),
                secretCancellation.Token);
            try
            {
                return await PipeTransport.CallAsync(
                    protectedSession.PipeName,
                    Contract.Serialize(new Request
                    {
                        Operation = "session.login",
                        RequestId = requestId,
                        CredentialKind = credentialKind,
                        SecretPipe = secretPipe,
                    }),
                    TimeSpan.FromSeconds(45),
                    cancellationToken);
            }
            finally
            {
                secretCancellation.Cancel();
                try { await secretTask; }
                catch (OperationCanceledException) { }
            }
        }
        catch (Exception ex)
        {
            StopSessions();
            return Contract.Serialize(new Result
            {
                RequestId = requestId,
                Operation = "session.login",
                Accepted = false,
                ActualRoute = "windows.service/protected_login",
                SessionId = activeSession,
                Generation = _runtimeGeneration,
                Delivery = "unknown",
                Effect = "unknown",
                ErrorCode = "login_route_unavailable",
                Message = ex.Message,
                ElapsedMs = started.ElapsedMilliseconds,
            });
        }
    }

    private async Task<string> HandleAsync(
        string requestText,
        CancellationToken cancellationToken)
    {
        var started = Stopwatch.StartNew();
        Request request;
        try
        {
            request = Contract.ParseRequest(requestText);
        }
        catch (Exception ex)
        {
            return Contract.Serialize(new Result
            {
                RequestId = "invalid",
                Operation = "invalid",
                Accepted = false,
                ErrorCode = "invalid_request",
                Message = ex.Message,
                ElapsedMs = started.ElapsedMilliseconds,
            });
        }

        if (string.Equals(
                request.Operation,
                "service.status",
                StringComparison.OrdinalIgnoreCase))
        {
            var activeSession = NativeMethods.WTSGetActiveConsoleSessionId();
            return Contract.Serialize(new Result
            {
                RequestId = request.RequestId!,
                Operation = request.Operation,
                Accepted = true,
                ActualRoute = "windows.service",
                SessionId = activeSession == uint.MaxValue ? null : activeSession,
                Generation = _runtimeGeneration,
                Delivery = "confirmed",
                Effect = "not_applicable",
                Data = new
                {
                    profile = "dedicated-test-appliance",
                    interactiveUserPresent = activeSession != uint.MaxValue &&
                        HasInteractiveUser(activeSession),
                    sessionLocked = activeSession == uint.MaxValue
                        ? null
                        : SessionStateInspector.IsLocked(activeSession),
                    ordinaryHelperPid = IsSessionHealthy(_ordinarySession)
                        ? (int?)_ordinarySession!.ProcessId
                        : null,
                    protectedHelperPid = IsSessionHealthy(_protectedSession)
                        ? (int?)_protectedSession!.ProcessId
                        : null,
                },
                ElapsedMs = started.ElapsedMilliseconds,
            });
        }

        if (string.Equals(
                request.Operation,
                "service.revoke",
                StringComparison.OrdinalIgnoreCase))
        {
            var previousGeneration = _runtimeGeneration;
            StopSessions();
            _runtimeGeneration = Guid.NewGuid().ToString("n");
            return Contract.Serialize(new Result
            {
                RequestId = request.RequestId!,
                Operation = request.Operation,
                Accepted = true,
                ActualRoute = "windows.service/revoke",
                Generation = _runtimeGeneration,
                Delivery = "confirmed",
                Effect = "confirmed",
                Evidence = new
                {
                    previousGenerationInvalidated = previousGeneration,
                    helperStopped = true,
                },
                ElapsedMs = started.ElapsedMilliseconds,
            });
        }

        if (string.Equals(
                request.Operation,
                "session.login",
                StringComparison.OrdinalIgnoreCase))
        {
            return Contract.Serialize(new Result
            {
                RequestId = request.RequestId!,
                Operation = request.Operation,
                Accepted = false,
                ActualRoute = "windows.service/protected_login",
                Generation = _runtimeGeneration,
                Delivery = "refused",
                Effect = "refused",
                ErrorCode = "secret_transport_required",
                Message = "Use the dedicated non-JSON login command",
                ElapsedMs = started.ElapsedMilliseconds,
            });
        }

        if (string.Equals(
                request.Operation,
                "session.logoff",
                StringComparison.OrdinalIgnoreCase))
        {
            var activeSession = NativeMethods.WTSGetActiveConsoleSessionId();
            if (activeSession == uint.MaxValue ||
                !HasInteractiveUser(activeSession))
            {
                return Contract.Serialize(new Result
                {
                    RequestId = request.RequestId!,
                    Operation = request.Operation,
                    Accepted = false,
                    ActualRoute = "windows.service/wts_logoff_session",
                    SessionId = activeSession == uint.MaxValue
                        ? null
                        : activeSession,
                    Generation = _runtimeGeneration,
                    Delivery = "refused",
                    Effect = "refused",
                    ErrorCode = "no_interactive_session",
                    Message = "Windows has no logged-in console user",
                    ElapsedMs = started.ElapsedMilliseconds,
                });
            }

            var previousGeneration = _runtimeGeneration;
            StopSessions();
            _runtimeGeneration = Guid.NewGuid().ToString("n");
            if (!NativeMethods.WTSLogoffSession(
                    IntPtr.Zero,
                    activeSession,
                    wait: false))
            {
                return Contract.Serialize(new Result
                {
                    RequestId = request.RequestId!,
                    Operation = request.Operation,
                    Accepted = false,
                    ActualRoute = "windows.service/wts_logoff_session",
                    SessionId = activeSession,
                    Generation = _runtimeGeneration,
                    Delivery = "unknown",
                    Effect = "unknown",
                    ErrorCode = "logoff_failed",
                    Message = $"WTSLogoffSession failed with Windows error " +
                        Marshal.GetLastWin32Error(),
                    Evidence = new
                    {
                        previousGenerationInvalidated = previousGeneration,
                    },
                    ElapsedMs = started.ElapsedMilliseconds,
                });
            }

            // WTS can keep the old session authoritative while Winlogon tears
            // it down. Stay within the client's 30-second request deadline but
            // do not report an unverifiable effect merely because that normal
            // transition exceeds a few seconds.
            var deadline = DateTime.UtcNow + TimeSpan.FromSeconds(25);
            var currentSession = NativeMethods.WTSGetActiveConsoleSessionId();
            var loggedOff = currentSession != activeSession ||
                !HasInteractiveUser(activeSession);
            while (DateTime.UtcNow < deadline && !loggedOff)
            {
                await Task.Delay(100, cancellationToken);
                currentSession = NativeMethods.WTSGetActiveConsoleSessionId();
                loggedOff = currentSession != activeSession ||
                    !HasInteractiveUser(activeSession);
            }
            return Contract.Serialize(new Result
            {
                RequestId = request.RequestId!,
                Operation = request.Operation,
                Accepted = true,
                ActualRoute = "windows.service/wts_logoff_session",
                SessionId = activeSession,
                Generation = _runtimeGeneration,
                Delivery = "confirmed",
                Effect = loggedOff ? "confirmed" : "unverifiable",
                Evidence = new
                {
                    previousGenerationInvalidated = previousGeneration,
                    activeSessionChanged = currentSession != activeSession,
                    interactiveUserPresent = currentSession == uint.MaxValue
                        ? false
                        : HasInteractiveUser(currentSession),
                },
                ElapsedMs = started.ElapsedMilliseconds,
            });
        }

        try
        {
            var protectedSession = await EnsureSessionAsync(
                protectedAuthority: true,
                cancellationToken);
            var probeRequest = Contract.Serialize(new Request
            {
                Operation = "status",
                RequestId = Guid.NewGuid().ToString("n"),
            });
            var probeText = await PipeTransport.CallAsync(
                protectedSession.PipeName,
                probeRequest,
                TimeSpan.FromSeconds(25),
                cancellationToken);
            var probe = Contract.ParseResult(probeText);
            var useProtected = !string.Equals(
                probe.Desktop,
                "Default",
                StringComparison.OrdinalIgnoreCase) ||
                probe.SessionLocked == true;
            var session = useProtected
                ? protectedSession
                : await EnsureSessionAsync(
                    protectedAuthority: false,
                    cancellationToken);
            return await PipeTransport.CallAsync(
                session.PipeName,
                Contract.Serialize(request),
                TimeSpan.FromSeconds(25),
                cancellationToken);
        }
        catch (NoInteractiveSessionException ex)
        {
            return Contract.Serialize(new Result
            {
                RequestId = request.RequestId!,
                Operation = request.Operation,
                Accepted = false,
                ActualRoute = "windows.service",
                Generation = _runtimeGeneration,
                Delivery = "refused",
                Effect = "refused",
                ErrorCode = "no_interactive_session",
                Message = ex.Message,
                ElapsedMs = started.ElapsedMilliseconds,
            });
        }
        catch (Exception ex)
        {
            StopSessions();
            return Contract.Serialize(new Result
            {
                RequestId = request.RequestId!,
                Operation = request.Operation,
                Accepted = false,
                ActualRoute = "windows.service/session_proxy",
                Generation = _runtimeGeneration,
                Delivery = "unknown",
                Effect = "unknown",
                ErrorCode = "session_unavailable",
                Message = ex.Message,
                ElapsedMs = started.ElapsedMilliseconds,
            });
        }
    }

    private async Task<SessionProcess> EnsureSessionAsync(
        bool protectedAuthority,
        CancellationToken cancellationToken)
    {
        var activeSession = NativeMethods.WTSGetActiveConsoleSessionId();
        if (activeSession == uint.MaxValue)
        {
            throw new NoInteractiveSessionException(
                "Windows has no active console session");
        }

        var existing = protectedAuthority
            ? _protectedSession
            : _ordinarySession;
        if (IsSessionHealthy(existing) && existing!.SessionId == activeSession)
        {
            return existing;
        }

        StopSession(ref existing);
        var generation =
            $"{_runtimeGeneration}:{activeSession}:{Guid.NewGuid():n}";
        var pipeName = $"machine-control-session-{Guid.NewGuid():n}";
        var launched = protectedAuthority
            ? SessionLauncher.LaunchSystem(
                activeSession,
                pipeName,
                generation)
            : SessionLauncher.LaunchUser(
                activeSession,
                pipeName,
                generation);
        if (protectedAuthority)
        {
            _protectedSession = launched;
        }
        else
        {
            _ordinarySession = launched;
        }

        var deadline = DateTime.UtcNow + TimeSpan.FromSeconds(15);
        while (DateTime.UtcNow < deadline)
        {
            cancellationToken.ThrowIfCancellationRequested();
            try
            {
                var ping = Contract.Serialize(new Request
                {
                    Operation = "status",
                    RequestId = Guid.NewGuid().ToString("n"),
                });
                await PipeTransport.CallAsync(
                    pipeName,
                    ping,
                    TimeSpan.FromMilliseconds(750),
                    cancellationToken);
                return launched;
            }
            catch (Exception) when (DateTime.UtcNow < deadline)
            {
                await Task.Delay(200, cancellationToken);
            }
        }
        throw new System.TimeoutException(
            "Interactive-session helper did not become ready");
    }

    private static bool IsSessionHealthy(SessionProcess? session)
    {
        if (session is null) return false;
        try
        {
            return !Process.GetProcessById(session.ProcessId).HasExited;
        }
        catch
        {
            return false;
        }
    }

    private static void WriteServiceError(Exception ex)
    {
        try
        {
            EventLog.WriteEntry(
                "MachineControlRuntime",
                ex.ToString(),
                EventLogEntryType.Error);
        }
        catch { }
    }

    private static bool HasInteractiveUser(uint sessionId)
    {
        if (!NativeMethods.WTSQuerySessionInformation(
                IntPtr.Zero,
                sessionId,
                NativeMethods.WTSUserName,
                out var buffer,
                out var length))
        {
            return false;
        }
        try
        {
            return length > sizeof(char) &&
                !string.IsNullOrWhiteSpace(Marshal.PtrToStringUni(buffer));
        }
        finally
        {
            NativeMethods.WTSFreeMemory(buffer);
        }
    }

    private void StopSessions()
    {
        StopSession(ref _ordinarySession);
        StopSession(ref _protectedSession);
    }

    private static void StopSession(ref SessionProcess? session)
    {
        if (session is null) return;
        try
        {
            var process = Process.GetProcessById(session.ProcessId);
            if (!process.HasExited) process.Kill(entireProcessTree: true);
        }
        catch { }
        session = null;
    }
}

internal sealed class NoInteractiveSessionException(string message)
    : Exception(message);
