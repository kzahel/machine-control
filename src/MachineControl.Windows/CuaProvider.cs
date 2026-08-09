using System.Collections.Concurrent;
using System.Diagnostics;
using System.Drawing;
using System.IO;
using System.Runtime.InteropServices;
using System.Security.Cryptography;
using System.Security.Principal;
using System.Text;
using System.Text.Json;

namespace MachineControl.Windows;

internal sealed class CuaProvider : IControlProvider
{
    private readonly CuaDriverHost _host = new();
    private readonly ConcurrentDictionary<string, CuaElementReference>
        _references = new();

    public ProviderDescriptor Describe()
    {
        var health = _host.Describe();
        return new ProviderDescriptor(
            "cua",
            health.State,
            "guest.user",
            "child of the Medium interactive-session helper",
            "Medium",
            "unlocked Default desktop",
            [
                Operation(
                    "snapshot",
                    health.State,
                    "compact exact-window UIA",
                    "observation",
                    "provider snapshot only"),
                Operation(
                    "screenshot",
                    health.State,
                    "ordinary exact-window content capture",
                    "observation",
                    "artifact hash and extent"),
                Operation(
                    "invoke",
                    health.State,
                    "snapshot-bound semantic action",
                    "background-first",
                    "provider result; caller verifies fixture effect"),
            ],
            [
                "taskbar and selected shell HWND discovery",
                "packaged Settings inner/outer resolution",
                "protected and cross-integrity desktops",
                "selected window-state operations",
            ],
            Version: CuaDriverHost.Version,
            SourceRevision: CuaDriverHost.SourceReviewRevision,
            ArtifactDigest: $"sha256:{CuaDriverHost.ExpectedExecutableSha256()}",
            Provenance: "Exact evaluated release asset; its binary does not " +
                "attest a source SHA, so the pinned source review is not a " +
                "binary provenance claim",
            Detail: health.Detail);
    }

    public bool OwnsReference(string? reference) =>
        reference is not null && _references.ContainsKey(reference);

    public async Task<Result> ExecuteAsync(
        Request request,
        string generation,
        CancellationToken cancellationToken)
    {
        try
        {
            return request.Operation.ToLowerInvariant() switch
            {
                "snapshot" => await SnapshotAsync(
                    request,
                    generation,
                    cancellationToken),
                "screenshot" => await ScreenshotAsync(
                    request,
                    generation,
                    cancellationToken),
                "invoke" => await InvokeAsync(
                    request,
                    generation,
                    cancellationToken),
                _ => Failure(
                    request,
                    generation,
                    "provider_unsupported_operation",
                    "Cua does not implement this normalized operation",
                    "refused",
                    "refused",
                    elapsedMs: 0),
            };
        }
        catch (CuaProviderException ex)
        {
            return Failure(
                request,
                generation,
                ex.ErrorCode,
                ex.Message,
                ex.Delivery,
                ex.Effect,
                ex.ElapsedMs);
        }
        catch (OperationCanceledException) when (
            cancellationToken.IsCancellationRequested)
        {
            throw;
        }
        catch (Exception ex)
        {
            return Failure(
                request,
                generation,
                "provider_error",
                Bounded(ex.Message),
                "unknown",
                "unknown",
                elapsedMs: 0);
        }
    }

    private async Task<Result> SnapshotAsync(
        Request request,
        string generation,
        CancellationToken cancellationToken)
    {
        var target = ResolveWindow(request);
        var arguments = new Dictionary<string, object?>
        {
            ["pid"] = target.ProcessId,
            ["window_id"] = target.Hwnd,
            ["session"] = _host.SessionId,
            ["include_screenshot"] = false,
            ["max_elements"] = Math.Clamp(
                request.MaxElements ?? 250,
                1,
                2000),
            ["max_depth"] = Math.Clamp(request.MaxDepth ?? 12, 1, 20),
        };
        if (!string.IsNullOrWhiteSpace(request.Query))
        {
            arguments["query"] = request.Query;
        }

        var upstream = await _host.CallToolAsync(
            "get_window_state",
            arguments,
            screenshotOutFile: null,
            TimeSpan.FromSeconds(15),
            cancellationToken);
        var elements = NormalizeElements(
            upstream.Value,
            generation,
            target.ProcessId,
            target.Hwnd);
        var serializedBytes = Encoding.UTF8.GetByteCount(
            Contract.Serialize(elements));
        var total = ReadInt(upstream.Value, "total_element_count") ??
            ReadInt(upstream.Value, "element_count") ??
            elements.Count;
        var degraded = ReadBool(upstream.Value, "degraded") ?? false;
        return Success(
            request,
            generation,
            "windows.user_session/cua/get_window_state",
            "confirmed",
            "not_applicable",
            degraded ? "degraded_semantic" : "exact_window_semantic",
            new
            {
                elements,
                count = elements.Count,
                visited = total,
                maxDepth = arguments["max_depth"],
                maxElements = arguments["max_elements"],
                serializedBytes,
                estimatedTokens = Math.Max(1, serializedBytes / 4),
                queryProjected = !string.IsNullOrWhiteSpace(request.Query),
                elementsComplete = ReadBool(
                    upstream.Value,
                    "elements_complete") ?? false,
                degraded,
                degradedReason = ReadString(
                    upstream.Value,
                    "degraded_reason"),
                target = new
                {
                    processId = target.ProcessId,
                    hwnd = target.Hwnd,
                },
            },
            upstream.ElapsedMs,
            uncertainty: degraded
                ? "provider reported a degraded semantic snapshot"
                : "none");
    }

    private async Task<Result> ScreenshotAsync(
        Request request,
        string generation,
        CancellationToken cancellationToken)
    {
        var target = ResolveWindow(request);
        var artifactRoot = Path.Combine(
            Environment.GetFolderPath(
                Environment.SpecialFolder.CommonApplicationData),
            "MachineControl",
            "artifacts");
        Directory.CreateDirectory(artifactRoot);
        var artifactId = Guid.NewGuid().ToString("n");
        var path = Path.Combine(artifactRoot, $"{artifactId}.png");
        var arguments = new Dictionary<string, object?>
        {
            ["pid"] = target.ProcessId,
            ["window_id"] = target.Hwnd,
            ["session"] = _host.SessionId,
            ["max_elements"] = 1,
            ["max_depth"] = 1,
        };
        var upstream = await _host.CallToolAsync(
            "get_window_state",
            arguments,
            path,
            TimeSpan.FromSeconds(20),
            cancellationToken);
        if (!File.Exists(path))
        {
            throw new CuaProviderException(
                "exact_window_capture_failed",
                "Cua completed without producing the requested image",
                "unknown",
                "unknown",
                upstream.ElapsedMs);
        }

        var fileBytes = await File.ReadAllBytesAsync(path, cancellationToken);
        var sha256 = Convert.ToHexString(SHA256.HashData(fileBytes))
            .ToLowerInvariant();
        int width;
        int height;
        using (var image = Image.FromFile(path))
        {
            width = image.Width;
            height = image.Height;
        }
        return Success(
            request,
            generation,
            "windows.user_session/cua/get_window_state_capture",
            "confirmed",
            "not_applicable",
            "exact_window_content_crop",
            new
            {
                artifactId,
                targetLocalPath = path,
                hwnd = target.Hwnd,
                processId = target.ProcessId,
                bytes = fileBytes.Length,
                width,
                height,
                sha256,
            },
            upstream.ElapsedMs,
            coordinateSpace: "cua.window_content_physical_pixels");
    }

    private async Task<Result> InvokeAsync(
        Request request,
        string generation,
        CancellationToken cancellationToken)
    {
        if (string.IsNullOrWhiteSpace(request.Reference) ||
            !_references.TryGetValue(request.Reference, out var reference))
        {
            return Failure(
                request,
                generation,
                "stale_or_unknown_reference",
                "The semantic reference is not known to the Cua adapter",
                "refused",
                "refused",
                elapsedMs: 0,
                staleReferenceEvents: 1);
        }
        if (!string.Equals(reference.RuntimeGeneration, generation, StringComparison.Ordinal) ||
            !string.Equals(
                reference.ProviderGeneration,
                _host.ProviderGeneration,
                StringComparison.Ordinal))
        {
            return Failure(
                request,
                generation,
                "stale_or_unknown_reference",
                "The reference belongs to an earlier runtime or provider generation",
                "refused",
                "refused",
                elapsedMs: 0,
                staleReferenceEvents: 1);
        }

        var upstream = await _host.CallToolAsync(
            "click",
            new Dictionary<string, object?>
            {
                ["pid"] = reference.ProcessId,
                ["window_id"] = reference.Hwnd,
                ["element_token"] = reference.ElementToken,
                ["delivery_mode"] = "background",
                ["session"] = _host.SessionId,
            },
            screenshotOutFile: null,
            TimeSpan.FromSeconds(15),
            cancellationToken);
        var providerRoute = ReadString(upstream.Value, "route") ?? "click";
        var providerDelivery = ReadNestedString(
            upstream.Value,
            "delivery",
            "mode") ?? "unknown";
        var providerEffect = ReadString(upstream.Value, "effect") ?? "unknown";
        return Success(
            request,
            generation,
            $"windows.user_session/cua/{BoundedRoute(providerRoute)}",
            "confirmed",
            "unverifiable",
            "snapshot_bound_semantic",
            new
            {
                reference = request.Reference,
                target = new
                {
                    processId = reference.ProcessId,
                    hwnd = reference.Hwnd,
                },
            },
            upstream.ElapsedMs,
            evidence: new
            {
                providerReportedDelivery = providerDelivery,
                providerReportedEffect = providerEffect,
                independentEffectRequired = true,
            },
            uncertainty: "Cua reported delivery/effect but no independent oracle was supplied");
    }

    private List<ElementRecord> NormalizeElements(
        JsonElement value,
        string generation,
        int processId,
        long hwnd)
    {
        var result = new List<ElementRecord>();
        if (!value.TryGetProperty("elements", out var elements) ||
            elements.ValueKind != JsonValueKind.Array)
        {
            return result;
        }
        foreach (var element in elements.EnumerateArray())
        {
            var token = ReadString(element, "element_token");
            if (string.IsNullOrWhiteSpace(token)) continue;
            var reference = CreateReference(
                generation,
                processId,
                hwnd,
                token);
            var frame = element.TryGetProperty("frame", out var frameValue)
                ? new RectRecord(
                    ReadDouble(frameValue, "x") ?? 0,
                    ReadDouble(frameValue, "y") ?? 0,
                    ReadDouble(frameValue, "w") ?? 0,
                    ReadDouble(frameValue, "h") ?? 0)
                : new RectRecord(0, 0, 0, 0);
            result.Add(new ElementRecord(
                reference,
                ReadInt(element, "depth") ?? 0,
                ReadString(element, "role") ?? "unknown",
                ReadString(element, "label") ?? string.Empty,
                string.Empty,
                ReadBool(element, "enabled") ?? true,
                false,
                frame,
                ["snapshot_action"],
                ReadString(element, "value"),
                ReadBool(element, "selected")));
        }
        return result;
    }

    private string CreateReference(
        string generation,
        int processId,
        long hwnd,
        string elementToken)
    {
        if (_references.Count > 10_000) _references.Clear();
        var providerGeneration = _host.ProviderGeneration;
        var bytes = Encoding.UTF8.GetBytes(
            $"{generation}:{providerGeneration}:{processId}:{hwnd}:{elementToken}");
        var reference = Convert.ToHexString(
            SHA256.HashData(bytes)[..12]).ToLowerInvariant();
        _references[reference] = new CuaElementReference(
            generation,
            providerGeneration,
            processId,
            hwnd,
            elementToken);
        return reference;
    }

    private static (int ProcessId, long Hwnd) ResolveWindow(Request request)
    {
        if (request.Hwnd is not > 0)
        {
            throw new CuaProviderException(
                "target_required",
                "Cua exact-window operations require hwnd",
                "refused",
                "refused",
                0);
        }
        var processId = request.ProcessId ?? GetWindowProcessId(request.Hwnd.Value);
        if (processId <= 0)
        {
            throw new CuaProviderException(
                "target_unavailable",
                "The requested HWND no longer has an owning process",
                "refused",
                "refused",
                0);
        }
        return (processId, request.Hwnd.Value);
    }

    private static int GetWindowProcessId(long hwnd)
    {
        NativeMethods.GetWindowThreadProcessId(new IntPtr(hwnd), out var processId);
        return (int)processId;
    }

    private static ProviderOperationDescriptor Operation(
        string operation,
        string state,
        string fidelity,
        string delivery,
        string effectObservation) => new(
            operation,
            state,
            "desktop",
            ["Default"],
            fidelity,
            delivery,
            effectObservation,
            "none expected for background semantics and observation");

    private static Result Success(
        Request request,
        string generation,
        string route,
        string delivery,
        string effect,
        string fidelity,
        object data,
        long elapsedMs,
        object? evidence = null,
        string uncertainty = "none",
        string? coordinateSpace = null) => new()
        {
            RequestId = request.RequestId!,
            Operation = request.Operation,
            Accepted = true,
            ActualRoute = route,
            SessionId = NativeMethods.WTSGetActiveConsoleSessionId(),
            Desktop = "Default",
            Generation = generation,
            Delivery = delivery,
            Effect = effect,
            Fidelity = fidelity,
            CoordinateSpace = coordinateSpace,
            FocusConsequence = "unchanged_expected",
            CursorConsequence = "unchanged_expected",
            Uncertainty = uncertainty,
            RetrySafety = effect == "unverifiable"
                ? "observe_before_retry"
                : "not_needed",
            ProviderAttempts =
            [
                new ProviderAttempt(
                    "cua",
                    "selected",
                    null,
                    elapsedMs,
                    delivery,
                    effect),
            ],
            ProviderLatencyMs = elapsedMs,
            Evidence = evidence,
            Data = data,
            ElapsedMs = elapsedMs,
        };

    private static Result Failure(
        Request request,
        string generation,
        string errorCode,
        string message,
        string delivery,
        string effect,
        long elapsedMs,
        int staleReferenceEvents = 0) => new()
        {
            RequestId = request.RequestId!,
            Operation = request.Operation,
            Accepted = false,
            ActualRoute = "windows.user_session/cua",
            SessionId = NativeMethods.WTSGetActiveConsoleSessionId(),
            Desktop = "Default",
            Generation = generation,
            Delivery = delivery,
            Effect = effect,
            Fidelity = "provider_unavailable",
            FocusConsequence = delivery == "unknown"
                ? "unknown"
                : "unchanged",
            CursorConsequence = delivery == "unknown"
                ? "unknown"
                : "unchanged",
            Uncertainty = effect == "unknown"
                ? "provider failure occurred after dispatch may have begun"
                : "none",
            RetrySafety = effect == "unknown"
                ? "observe_and_reconcile_before_retry"
                : "safe_not_dispatched",
            ProviderAttempts =
            [
                new ProviderAttempt(
                    "cua",
                    errorCode,
                    message,
                    elapsedMs,
                    delivery,
                    effect),
            ],
            ProviderLatencyMs = elapsedMs,
            StaleReferenceEvents = staleReferenceEvents,
            ErrorCode = errorCode,
            Message = message,
            ElapsedMs = elapsedMs,
        };

    private static int? ReadInt(JsonElement value, string property) =>
        value.TryGetProperty(property, out var item) && item.TryGetInt32(out var number)
            ? number
            : null;

    private static double? ReadDouble(JsonElement value, string property) =>
        value.TryGetProperty(property, out var item) && item.TryGetDouble(out var number)
            ? number
            : null;

    private static bool? ReadBool(JsonElement value, string property) =>
        value.TryGetProperty(property, out var item) &&
        item.ValueKind is JsonValueKind.True or JsonValueKind.False
            ? item.GetBoolean()
            : null;

    private static string? ReadString(JsonElement value, string property) =>
        value.TryGetProperty(property, out var item) &&
        item.ValueKind == JsonValueKind.String
            ? item.GetString()
            : null;

    private static string? ReadNestedString(
        JsonElement value,
        string parent,
        string property) =>
        value.TryGetProperty(parent, out var item)
            ? ReadString(item, property)
            : null;

    private static string BoundedRoute(string value)
    {
        var safe = new string(value
            .Take(80)
            .Select(character => char.IsLetterOrDigit(character) ||
                character is '_' or '-' or '.'
                    ? character
                    : '_')
            .ToArray());
        return string.IsNullOrWhiteSpace(safe) ? "click" : safe;
    }

    private static string Bounded(string value) =>
        value.Length <= 512 ? value : value[..512];
}

internal sealed class CuaDriverHost
{
    public const string Version = "0.17.0";
    public const string SourceReviewRevision =
        "d21e3447f9b08c761c090946648d5aca5e6c9cf1";

    private readonly SemaphoreSlim _startGate = new(1, 1);
    private readonly SemaphoreSlim _callGate = new(1, 1);
    private Process? _daemon;
    private string? _endpoint;
    private string? _lastError;
    private string _providerGeneration = Guid.NewGuid().ToString("n");
    private int _restartCount;
    private bool _startedOnce;

    public string SessionId { get; } = $"machine-control-{Guid.NewGuid():n}";
    public string ProviderGeneration => _providerGeneration;

    public CuaHealth Describe()
    {
        if (IsLocalSystem())
        {
            return new CuaHealth(
                "policy_refused",
                "Cua is never launched in the LocalSystem protected helper");
        }
        var validation = ValidatePackage();
        if (!validation.Valid)
        {
            return new CuaHealth(validation.State, validation.Detail);
        }
        if (_daemon is { HasExited: false })
        {
            return new CuaHealth(
                "experimental",
                $"healthy private daemon; release artifact SHA-256 verified; " +
                $"restart count {_restartCount}");
        }
        if (_lastError is not null)
        {
            return new CuaHealth(
                "temporarily_unhealthy",
                Bounded(_lastError));
        }
        return new CuaHealth(
            "experimental",
            "verified release asset is packaged and starts on first eligible call");
    }

    public async Task<CuaCallResult> CallToolAsync(
        string tool,
        object arguments,
        string? screenshotOutFile,
        TimeSpan timeout,
        CancellationToken cancellationToken)
    {
        await EnsureStartedAsync(cancellationToken);
        await _callGate.WaitAsync(cancellationToken);
        try
        {
            var invocation = await RunCliAsync(
                ["call", tool, "--socket", _endpoint!],
                Contract.Serialize(arguments),
                screenshotOutFile,
                timeout,
                cancellationToken);
            if (invocation.ExitCode != 0)
            {
                throw ClassifyFailure(invocation, tool);
            }
            try
            {
                using var document = JsonDocument.Parse(invocation.StandardOutput);
                return new CuaCallResult(
                    document.RootElement.Clone(),
                    invocation.ElapsedMs);
            }
            catch (JsonException ex)
            {
                throw new CuaProviderException(
                    "provider_invalid_response",
                    $"Cua returned invalid JSON: {Bounded(ex.Message)}",
                    "unknown",
                    "unknown",
                    invocation.ElapsedMs);
            }
        }
        finally
        {
            _callGate.Release();
        }
    }

    private async Task EnsureStartedAsync(CancellationToken cancellationToken)
    {
        if (_daemon is { HasExited: false }) return;
        await _startGate.WaitAsync(cancellationToken);
        try
        {
            if (_daemon is { HasExited: false }) return;
            if (_startedOnce)
            {
                _restartCount++;
                if (_restartCount > 1)
                {
                    throw new CuaProviderException(
                        "provider_unhealthy",
                        "Cua exhausted its one automatic restart for this helper generation",
                        "refused",
                        "refused",
                        0);
                }
            }
            var validation = ValidatePackage();
            if (!validation.Valid)
            {
                throw new CuaProviderException(
                    validation.State == "policy_refused"
                        ? "provider_policy_refused"
                        : "provider_unavailable",
                    validation.Detail,
                    "refused",
                    "refused",
                    0);
            }
            if (IsLocalSystem())
            {
                throw new CuaProviderException(
                    "provider_policy_refused",
                    "Cua cannot run in the protected LocalSystem helper",
                    "refused",
                    "refused",
                    0);
            }

            _providerGeneration = Guid.NewGuid().ToString("n");
            _endpoint = $@"\\.\pipe\machine-control-cua-{Guid.NewGuid():n}";
            var start = CreateProcessStartInfo();
            start.ArgumentList.Add("serve");
            start.ArgumentList.Add("--socket");
            start.ArgumentList.Add(_endpoint);
            start.ArgumentList.Add("--permission-mode");
            start.ArgumentList.Add("standard");
            start.ArgumentList.Add("--no-permissions-gate");
            _daemon = new Process { StartInfo = start, EnableRaisingEvents = true };
            _daemon.OutputDataReceived += (_, _) => { };
            _daemon.ErrorDataReceived += (_, _) => { };
            if (!_daemon.Start())
            {
                throw new InvalidOperationException("Cua daemon did not start");
            }
            _daemon.BeginOutputReadLine();
            _daemon.BeginErrorReadLine();
            _startedOnce = true;

            var deadline = DateTime.UtcNow + TimeSpan.FromSeconds(20);
            CuaProcessResult? permissionResult = null;
            while (DateTime.UtcNow < deadline)
            {
                cancellationToken.ThrowIfCancellationRequested();
                if (_daemon.HasExited)
                {
                    throw new InvalidOperationException(
                        $"Cua daemon exited with {_daemon.ExitCode}");
                }
                try
                {
                    permissionResult = await RunCliAsync(
                        ["call", "check_permissions", "--socket", _endpoint],
                        "{}",
                        screenshotOutFile: null,
                        TimeSpan.FromSeconds(3),
                        cancellationToken);
                    if (permissionResult.ExitCode == 0) break;
                }
                catch (CuaProviderException) { }
                await Task.Delay(200, cancellationToken);
            }
            if (permissionResult is null || permissionResult.ExitCode != 0)
            {
                throw new TimeoutException(
                    "Cua private daemon did not become ready within 20 seconds");
            }
            using (var permissions = JsonDocument.Parse(
                permissionResult.StandardOutput))
            {
                var root = permissions.RootElement;
                var rid = root.TryGetProperty(
                        "integrity_level_rid",
                        out var ridValue) &&
                    ridValue.TryGetInt32(out var parsedRid)
                        ? parsedRid
                        : 0;
                var elevated = root.TryGetProperty("elevated", out var elevatedValue) &&
                    elevatedValue.ValueKind == JsonValueKind.True;
                if (rid != 8192 || elevated)
                {
                    throw new CuaProviderException(
                        "provider_policy_refused",
                        $"Cua requires Medium integrity RID 8192; observed {rid}",
                        "refused",
                        "refused",
                        permissionResult.ElapsedMs);
                }
            }

            var session = await RunCliAsync(
                ["call", "start_session", "--socket", _endpoint],
                Contract.Serialize(new
                {
                    session = SessionId,
                    capture_scope = "window",
                }),
                screenshotOutFile: null,
                TimeSpan.FromSeconds(10),
                cancellationToken);
            if (session.ExitCode != 0)
            {
                throw ClassifyFailure(session, "start_session");
            }
            _lastError = null;
        }
        catch (CuaProviderException ex)
        {
            _lastError = ex.Message;
            StopDaemon();
            throw;
        }
        catch (Exception ex)
        {
            _lastError = ex.Message;
            StopDaemon();
            throw new CuaProviderException(
                "provider_unavailable",
                Bounded(ex.Message),
                "refused",
                "refused",
                0);
        }
        finally
        {
            _startGate.Release();
        }
    }

    private async Task<CuaProcessResult> RunCliAsync(
        string[] arguments,
        string? standardInput,
        string? screenshotOutFile,
        TimeSpan timeout,
        CancellationToken cancellationToken)
    {
        var start = CreateProcessStartInfo();
        foreach (var argument in arguments) start.ArgumentList.Add(argument);
        if (screenshotOutFile is not null)
        {
            start.ArgumentList.Add("--screenshot-out-file");
            start.ArgumentList.Add(screenshotOutFile);
        }
        using var process = new Process { StartInfo = start };
        var timer = Stopwatch.StartNew();
        if (!process.Start())
        {
            throw new CuaProviderException(
                "provider_unavailable",
                "Cua client process did not start",
                "refused",
                "refused",
                0);
        }
        var standardOutput = process.StandardOutput.ReadToEndAsync(
            cancellationToken);
        var standardError = process.StandardError.ReadToEndAsync(
            cancellationToken);
        if (standardInput is not null)
        {
            await process.StandardInput.WriteAsync(
                standardInput.AsMemory(),
                cancellationToken);
        }
        process.StandardInput.Close();

        using var timeoutSource = CancellationTokenSource.CreateLinkedTokenSource(
            cancellationToken);
        timeoutSource.CancelAfter(timeout);
        try
        {
            await process.WaitForExitAsync(timeoutSource.Token);
        }
        catch (OperationCanceledException) when (!cancellationToken.IsCancellationRequested)
        {
            try { process.Kill(entireProcessTree: true); } catch { }
            throw new CuaProviderException(
                "provider_timeout",
                $"Cua call exceeded {timeout.TotalSeconds:0} seconds",
                "unknown",
                "unknown",
                timer.ElapsedMilliseconds);
        }
        return new CuaProcessResult(
            process.ExitCode,
            await standardOutput,
            await standardError,
            timer.ElapsedMilliseconds);
    }

    private ProcessStartInfo CreateProcessStartInfo()
    {
        var start = new ProcessStartInfo
        {
            FileName = BinaryPath(),
            UseShellExecute = false,
            RedirectStandardInput = true,
            RedirectStandardOutput = true,
            RedirectStandardError = true,
            CreateNoWindow = true,
            WorkingDirectory = Path.GetDirectoryName(BinaryPath()),
        };
        start.Environment["CUA_DRIVER_RS_TELEMETRY_ENABLED"] = "false";
        start.Environment["CUA_TELEMETRY_ENABLED"] = "false";
        start.Environment["CUA_DRIVER_RS_UPDATE_CHECK"] = "false";
        return start;
    }

    private CuaPackageValidation ValidatePackage()
    {
        var binary = BinaryPath();
        if (!File.Exists(binary))
        {
            return new CuaPackageValidation(
                false,
                "unavailable",
                "The pinned Cua executable is not installed with this runtime");
        }
        var expected = ExpectedExecutableSha256();
        if (expected.Length == 0)
        {
            return new CuaPackageValidation(
                false,
                "unsupported",
                $"No Cua artifact is pinned for {RuntimeInformation.ProcessArchitecture}");
        }
        try
        {
            using var stream = File.OpenRead(binary);
            var actual = Convert.ToHexString(SHA256.HashData(stream))
                .ToLowerInvariant();
            if (!string.Equals(actual, expected, StringComparison.Ordinal))
            {
                return new CuaPackageValidation(
                    false,
                    "policy_refused",
                    "The installed Cua executable does not match the pinned digest");
            }
        }
        catch (Exception ex)
        {
            return new CuaPackageValidation(
                false,
                "unavailable",
                Bounded(ex.Message));
        }
        return new CuaPackageValidation(
            true,
            "experimental",
            "Pinned release artifact digest verified");
    }

    public static string ExpectedExecutableSha256() =>
        RuntimeInformation.ProcessArchitecture switch
        {
            Architecture.X64 =>
                "635efe92eb0c3f9737db7e8aca0198f12ccf97e3269a9a75d28388690113db27",
            Architecture.Arm64 =>
                "fef346fc57fb57f5721ee77cf479c607cd5015580447cdca71a71ef43175afaa",
            _ => string.Empty,
        };

    private static CuaProviderException ClassifyFailure(
        CuaProcessResult result,
        string tool)
    {
        var detail = Bounded(string.IsNullOrWhiteSpace(result.StandardError)
            ? result.StandardOutput
            : result.StandardError);
        var lowered = detail.ToLowerInvariant();
        var code = lowered.Contains("stale_element_token", StringComparison.Ordinal) ||
            lowered.Contains("stale", StringComparison.Ordinal)
                ? "stale_or_unknown_reference"
                : lowered.Contains("outside", StringComparison.Ordinal) ||
                  lowered.Contains("authorization", StringComparison.Ordinal) ||
                  lowered.Contains("permission", StringComparison.Ordinal)
                    ? "provider_policy_refused"
                    : lowered.Contains("window_id", StringComparison.Ordinal) ||
                      lowered.Contains("not found", StringComparison.Ordinal)
                        ? "target_unavailable"
                        : lowered.Contains("not running", StringComparison.Ordinal) ||
                          lowered.Contains("incompatible", StringComparison.Ordinal)
                            ? "provider_unavailable"
                            : "provider_error";
        return new CuaProviderException(
            code,
            string.IsNullOrWhiteSpace(detail)
                ? $"Cua {tool} failed with exit code {result.ExitCode}"
                : detail,
            "refused",
            "refused",
            result.ElapsedMs);
    }

    private void StopDaemon()
    {
        try
        {
            if (_daemon is { HasExited: false })
            {
                _daemon.Kill(entireProcessTree: true);
                _daemon.WaitForExit(3000);
            }
        }
        catch { }
        _daemon?.Dispose();
        _daemon = null;
    }

    private static string BinaryPath() => Path.Combine(
        Path.GetDirectoryName(Environment.ProcessPath) ?? AppContext.BaseDirectory,
        "providers",
        "cua",
        "cua-driver.exe");

    private static bool IsLocalSystem()
    {
        using var identity = WindowsIdentity.GetCurrent();
        return identity.User?.IsWellKnown(
            WellKnownSidType.LocalSystemSid) == true;
    }

    private static string Bounded(string value)
    {
        var normalized = value.Replace('\r', ' ').Replace('\n', ' ').Trim();
        return normalized.Length <= 512 ? normalized : normalized[..512];
    }
}

internal sealed record CuaHealth(string State, string Detail);

internal sealed record CuaPackageValidation(
    bool Valid,
    string State,
    string Detail);

internal sealed record CuaProcessResult(
    int ExitCode,
    string StandardOutput,
    string StandardError,
    long ElapsedMs);

internal sealed record CuaCallResult(JsonElement Value, long ElapsedMs);

internal sealed record CuaElementReference(
    string RuntimeGeneration,
    string ProviderGeneration,
    int ProcessId,
    long Hwnd,
    string ElementToken);

internal sealed class CuaProviderException(
    string errorCode,
    string message,
    string delivery,
    string effect,
    long elapsedMs) : Exception(message)
{
    public string ErrorCode { get; } = errorCode;
    public string Delivery { get; } = delivery;
    public string Effect { get; } = effect;
    public long ElapsedMs { get; } = elapsedMs;
}
