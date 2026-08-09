using System.Diagnostics;
using System.Drawing;
using System.Drawing.Imaging;
using System.IO;
using System.Collections.Concurrent;
using System.Runtime.InteropServices;
using System.Security.Cryptography;
using System.Text;
using System.Windows.Automation;

namespace MachineControl.Windows;

internal static class DesktopController
{
    private static readonly ConcurrentDictionary<string, CachedSelector>
        Selectors = new();

    public static Task<Result> ExecuteAsync(
        Request request,
        string generation,
        CancellationToken cancellationToken)
    {
        var switchedDesktop = IntPtr.Zero;
        var completion = new TaskCompletionSource<Result>(
            TaskCreationOptions.RunContinuationsAsynchronously);
        var thread = new Thread(() =>
        {
            try
            {
                completion.SetResult(Execute(
                    request,
                    generation,
                    out switchedDesktop));
            }
            catch (Exception ex)
            {
                completion.SetResult(new Result
                {
                    RequestId = request.RequestId!,
                    Operation = request.Operation,
                    Accepted = false,
                    ActualRoute = "windows.protected_session",
                    SessionId = NativeMethods.WTSGetActiveConsoleSessionId(),
                    Generation = generation,
                    Delivery = "unknown",
                    Effect = "unknown",
                    ErrorCode = "desktop_operation_failed",
                    Message = ex.Message,
                    ElapsedMs = 0,
                });
            }
        })
        {
            IsBackground = true,
            Name = "MachineControlDesktopRequest",
        };
        thread.SetApartmentState(ApartmentState.STA);
        thread.Start();
        _ = Task.Run(() =>
        {
            thread.Join();
            if (switchedDesktop != IntPtr.Zero)
            {
                NativeMethods.CloseDesktop(switchedDesktop);
            }
        });
        cancellationToken.Register(() =>
            completion.TrySetCanceled(cancellationToken));
        return completion.Task;
    }

    private static Result Execute(
        Request request,
        string generation,
        out IntPtr switchedDesktop)
    {
        switchedDesktop = IntPtr.Zero;
        var timer = Stopwatch.StartNew();
        var desktop = NativeMethods.OpenInputDesktop(
            0,
            false,
            NativeMethods.DESKTOP_ALL_ACCESS);
        if (desktop == IntPtr.Zero)
        {
            throw new System.ComponentModel.Win32Exception(
                Marshal.GetLastWin32Error(),
                "OpenInputDesktop failed");
        }

        try
        {
            var currentDesktop = NativeMethods.GetThreadDesktop(
                NativeMethods.GetCurrentThreadId());
            var currentDesktopName = GetDesktopName(currentDesktop);
            var inputDesktopName = GetDesktopName(desktop);
            if (!string.Equals(
                    currentDesktopName,
                    inputDesktopName,
                    StringComparison.OrdinalIgnoreCase) &&
                !NativeMethods.SetThreadDesktop(desktop))
            {
                throw new System.ComponentModel.Win32Exception(
                    Marshal.GetLastWin32Error(),
                    $"SetThreadDesktop from '{currentDesktopName}' to " +
                    $"'{inputDesktopName}' failed");
            }

            if (!string.Equals(
                    currentDesktopName,
                    inputDesktopName,
                    StringComparison.OrdinalIgnoreCase))
            {
                switchedDesktop = desktop;
            }

            var desktopName = inputDesktopName;
            if (!string.IsNullOrWhiteSpace(request.ExpectedGeneration) &&
                !string.Equals(
                    request.ExpectedGeneration,
                    generation,
                    StringComparison.Ordinal))
            {
                return Failure(
                    request,
                    generation,
                    desktopName,
                    timer,
                    "stale_generation",
                    "The expected runtime/session generation is no longer active");
            }

            return request.Operation.ToLowerInvariant() switch
            {
                "capabilities" => Capabilities(
                    request, generation, desktopName, timer),
                "status" => Status(request, generation, desktopName, timer),
                "app.launch" => AppLaunch(
                    request, generation, desktopName, desktop, timer),
                "windows" => Windows(
                    request, generation, desktopName, desktop, timer),
                "snapshot" => Snapshot(
                    request, generation, desktopName, timer),
                "screenshot" => Screenshot(
                    request, generation, desktopName, timer),
                "invoke" => Invoke(request, generation, desktopName, timer),
                "click" => Click(request, generation, desktopName, timer),
                "key" => Key(request, generation, desktopName, timer),
                "type" => TypeText(request, generation, desktopName, timer),
                "window.state" => WindowState(
                    request, generation, desktopName, timer),
                "session.lock" => LockSession(
                    request, generation, desktopName, timer),
                "session.login" => Login(
                    request, generation, desktopName, timer),
                _ => Failure(
                    request,
                    generation,
                    desktopName,
                    timer,
                    "unsupported_operation",
                    $"Unsupported operation '{request.Operation}'"),
            };
        }
        finally
        {
            if (switchedDesktop == IntPtr.Zero)
            {
                NativeMethods.CloseDesktop(desktop);
            }
        }
    }

    private static Result Capabilities(
        Request request,
        string generation,
        string desktopName,
        Stopwatch timer) =>
        Success(
            request,
            generation,
            desktopName,
            timer,
            "windows.facade/provider_inventory",
            "confirmed",
            "not_applicable",
            new
            {
                providers = ProviderRouter.Describe(),
                routing = ProviderRouter.RoutingTable(),
                serviceOperations = new[]
                {
                    "service.status",
                    "service.revoke",
                    "session.logoff",
                    "session.login (dedicated secret transport)",
                },
                protectedDesktop = new
                {
                    profile = "dedicated-test-appliance",
                    processPlacement = "disposable LocalSystem desktop worker",
                    semantic = "UI Automation when exposed by Windows",
                    pixelFallback = "input-desktop GDI",
                    inputFallback = "SendInput on input desktop",
                },
            });

    private static Result Status(
        Request request,
        string generation,
        string desktopName,
        Stopwatch timer)
    {
        var sessionId = NativeMethods.WTSGetActiveConsoleSessionId();
        return Success(
            request,
            generation,
            desktopName,
            timer,
            IsLocalSystem()
                ? "windows.protected_session/input_desktop"
                : "windows.user_session/input_desktop",
            "confirmed",
            "not_applicable",
            new
            {
                inputDesktop = desktopName,
                integrityRid = GetIntegrityRid(),
                isLocalSystem = IsLocalSystem(),
                virtualScreen = ToSerializableBounds(GetVirtualScreen()),
                foregroundWindow = GetForegroundWindowSummary(),
                cursor = GetCursorSummary(),
            }) with
        {
            SessionLocked = sessionId == uint.MaxValue
                ? null
                : SessionStateInspector.IsLocked(sessionId),
        };
    }

    private static Result Windows(
        Request request,
        string generation,
        string desktopName,
        IntPtr desktop,
        Stopwatch timer)
    {
        var windows = EnumerateWindows(desktop);

        var filtered = (string.IsNullOrWhiteSpace(request.Query)
            ? windows
            : windows.Where(window =>
                window.Title.Contains(
                    request.Query,
                    StringComparison.OrdinalIgnoreCase) ||
                window.ClassName.Contains(
                    request.Query,
                    StringComparison.OrdinalIgnoreCase))
                .ToList())
            .Take(Math.Clamp(request.MaxElements ?? 100, 1, 1000))
            .ToList();
        return Success(
            request,
            generation,
            desktopName,
            timer,
            "windows.native/enum_desktop_windows",
            "confirmed",
            "not_applicable",
            new { windows = filtered, count = filtered.Count });
    }

    private static Result AppLaunch(
        Request request,
        string generation,
        string desktopName,
        IntPtr desktop,
        Stopwatch timer)
    {
        if (string.IsNullOrWhiteSpace(request.ExecutablePath) ||
            request.ExecutablePath.Length > 2048 ||
            !Path.IsPathFullyQualified(request.ExecutablePath) ||
            !File.Exists(request.ExecutablePath))
        {
            return Failure(
                request,
                generation,
                desktopName,
                timer,
                "invalid_executable_path",
                "app.launch requires an existing absolute executablePath");
        }
        if (request.Arguments?.Length > 4096)
        {
            return Failure(
                request,
                generation,
                desktopName,
                timer,
                "invalid_arguments",
                "app.launch arguments exceed 4096 UTF-16 code units");
        }

        var process = Process.Start(new ProcessStartInfo
        {
            FileName = request.ExecutablePath,
            Arguments = request.Arguments ?? string.Empty,
            WorkingDirectory = Path.GetDirectoryName(request.ExecutablePath),
            UseShellExecute = false,
        });
        if (process is null)
        {
            return Failure(
                request,
                generation,
                desktopName,
                timer,
                "application_launch_failed",
                "Windows did not return a process for app.launch");
        }
        try { process.WaitForInputIdle(5000); } catch { }
        var deadline = DateTime.UtcNow + TimeSpan.FromSeconds(5);
        var windows = EnumerateWindows(desktop)
            .Where(window => window.ProcessId == process.Id)
            .ToList();
        while (!windows.Any(window => window.Visible) &&
            !process.HasExited &&
            DateTime.UtcNow < deadline)
        {
            Thread.Sleep(100);
            windows = EnumerateWindows(desktop)
                .Where(window => window.ProcessId == process.Id)
                .ToList();
        }
        var running = !process.HasExited;
        return Success(
            request,
            generation,
            desktopName,
            timer,
            "windows.native/process_start",
            "confirmed",
            running && windows.Any(window => window.Visible)
                ? "confirmed"
                : running ? "partial" : "no_effect",
            new
            {
                processId = process.Id,
                running,
                windows,
            },
            fidelity: "target_local_application_launch");
    }

    private static List<WindowRecord> EnumerateWindows(IntPtr desktop)
    {
        var windows = new List<WindowRecord>();
        NativeMethods.EnumDesktopWindows(desktop, (hwnd, _) =>
        {
            var title = new StringBuilder(1024);
            var className = new StringBuilder(256);
            NativeMethods.GetWindowText(hwnd, title, title.Capacity);
            NativeMethods.GetClassName(hwnd, className, className.Capacity);
            NativeMethods.GetWindowThreadProcessId(hwnd, out var processId);
            if (!NativeMethods.GetWindowRect(hwnd, out var rect)) return true;
            windows.Add(new WindowRecord(
                hwnd.ToInt64(),
                (int)processId,
                title.ToString(),
                className.ToString(),
                NativeMethods.IsWindowVisible(hwnd),
                NativeMethods.IsIconic(hwnd),
                NativeMethods.IsZoomed(hwnd),
                new RectRecord(
                    rect.Left,
                    rect.Top,
                    rect.Right - rect.Left,
                    rect.Bottom - rect.Top)));
            return true;
        }, IntPtr.Zero);
        return windows;
    }

    private static Result Snapshot(
        Request request,
        string generation,
        string desktopName,
        Stopwatch timer)
    {
        var maxDepth = Math.Clamp(request.MaxDepth ?? 8, 1, 20);
        var maxElements = Math.Clamp(request.MaxElements ?? 250, 1, 2000);
        var root = ResolveAutomationRoot(request);
        if (root is null)
        {
            return Failure(
                request,
                generation,
                desktopName,
                timer,
                "target_unavailable",
                "The requested automation root is unavailable");
        }

        var records = new List<ElementRecord>();
        var visited = 0;
        Traverse(
            root,
            0,
            maxDepth,
            maxElements,
            maxElements * 20,
            request.Query,
            generation,
            records,
            ref visited);
        var json = Contract.Serialize(records);
        var bytes = Encoding.UTF8.GetByteCount(json);
        return Success(
            request,
            generation,
            desktopName,
            timer,
            "windows.native/uia",
            "confirmed",
            "not_applicable",
            new
            {
                elements = records,
                count = records.Count,
                visited,
                maxDepth,
                maxElements,
                serializedBytes = bytes,
                estimatedTokens = Math.Max(1, bytes / 4),
                queryProjected = !string.IsNullOrWhiteSpace(request.Query),
            });
    }

    private static Result Screenshot(
        Request request,
        string generation,
        string desktopName,
        Stopwatch timer)
    {
        var virtualScreen = GetVirtualScreen();
        var bounds = request.Hwnd is > 0 &&
            NativeMethods.GetWindowRect(
                new IntPtr(request.Hwnd.Value),
                out var windowRect)
            ? (
                X: windowRect.Left,
                Y: windowRect.Top,
                Width: windowRect.Right - windowRect.Left,
                Height: windowRect.Bottom - windowRect.Top)
            : virtualScreen;
        if (bounds.Width <= 0 || bounds.Height <= 0)
        {
            return Failure(
                request,
                generation,
                desktopName,
                timer,
                "capture_bounds_unavailable",
                "The requested capture bounds are unavailable");
        }
        using var bitmap = new Bitmap(
            bounds.Width,
            bounds.Height,
            PixelFormat.Format32bppArgb);
        var route = "windows.native/input_desktop_gdi";
        var fidelity = "input_desktop_pixels";
        if (request.Hwnd is > 0)
        {
            using var graphics = Graphics.FromImage(bitmap);
            var deviceContext = graphics.GetHdc();
            bool printed;
            try
            {
                printed = NativeMethods.PrintWindow(
                    new IntPtr(request.Hwnd.Value),
                    deviceContext,
                    2);
            }
            finally
            {
                graphics.ReleaseHdc(deviceContext);
            }
            if (!printed)
            {
                return Failure(
                    request,
                    generation,
                    desktopName,
                    timer,
                    "exact_window_capture_failed",
                    "PrintWindow did not capture the requested window");
            }
            route = "windows.native/print_window";
            fidelity = "exact_window_best_effort";
        }
        else
        {
            using var graphics = Graphics.FromImage(bitmap);
            graphics.CopyFromScreen(
                bounds.X,
                bounds.Y,
                0,
                0,
                new Size(bounds.Width, bounds.Height),
                CopyPixelOperation.SourceCopy);
        }

        var artifactRoot = Path.Combine(
            Environment.GetFolderPath(
                Environment.SpecialFolder.CommonApplicationData),
            "MachineControl",
            "artifacts");
        Directory.CreateDirectory(artifactRoot);
        var artifactId = Guid.NewGuid().ToString("n");
        var path = Path.Combine(artifactRoot, $"{artifactId}.png");
        bitmap.Save(path, ImageFormat.Png);
        var fileBytes = File.ReadAllBytes(path);
        var sha256 = Convert.ToHexString(SHA256.HashData(fileBytes))
            .ToLowerInvariant();
        return Success(
            request,
            generation,
            desktopName,
            timer,
            route,
            "confirmed",
            "not_applicable",
            new
            {
                artifactId,
                targetLocalPath = path,
                hwnd = request.Hwnd,
                bytes = fileBytes.Length,
                width = bounds.Width,
                height = bounds.Height,
                sha256,
            },
            fidelity: fidelity,
            coordinateSpace: "windows.virtual_screen_physical_pixels");
    }

    private static Result Invoke(
        Request request,
        string generation,
        string desktopName,
        Stopwatch timer)
    {
        if (string.IsNullOrWhiteSpace(request.Query) &&
            string.IsNullOrWhiteSpace(request.Reference))
        {
            return Failure(
                request,
                generation,
                desktopName,
                timer,
                "invalid_request",
                "invoke requires query or reference");
        }
        var root = ResolveAutomationRoot(request);
        CachedSelector? selector = null;
        if (!string.IsNullOrWhiteSpace(request.Reference) &&
            (!Selectors.TryGetValue(request.Reference, out selector) ||
             !string.Equals(
                 selector.Generation,
                 generation,
                 StringComparison.Ordinal)))
        {
            return Failure(
                request,
                generation,
                desktopName,
                timer,
                "stale_or_unknown_reference",
                "The semantic reference is not valid for this generation");
        }
        var query = request.Query ?? selector?.PreferredQuery ?? string.Empty;
        var element = FindElement(root, query, maxVisited: 10000);
        if (element is null)
        {
            return Failure(
                request,
                generation,
                desktopName,
                timer,
                "element_not_found",
                $"No element matched '{query}'");
        }

        var beforeDesktop = desktopName;
        var route = TryInvokePattern(element);
        if (route is null && request.AllowVisualFallback)
        {
            var bounds = element.Current.BoundingRectangle;
            if (bounds.IsEmpty)
            {
                return Failure(
                    request,
                    generation,
                    desktopName,
                    timer,
                    "element_not_actionable",
                    "The matched element has no actionable bounds");
            }
            SendClick(
                (int)bounds.X + (int)bounds.Width / 2,
                (int)bounds.Y + (int)bounds.Height / 2,
                "left");
            route = "windows.native/send_input";
        }
        if (route is null)
        {
            return Failure(
                request,
                generation,
                desktopName,
                timer,
                "semantic_action_unavailable",
                "No semantic pattern; visual fallback was not authorized");
        }

        Thread.Sleep(350);
        var afterDesktop = TryGetInputDesktopName();
        var changedDesktop = !string.Equals(
            beforeDesktop,
            afterDesktop,
            StringComparison.OrdinalIgnoreCase);
        return Success(
            request,
            generation,
            desktopName,
            timer,
            route,
            "confirmed",
            changedDesktop ? "confirmed" : "unverifiable",
            new
            {
                matched = SafeElementSummary(element),
                inputDesktopBefore = beforeDesktop,
                inputDesktopAfter = afterDesktop,
            });
    }

    private static Result Click(
        Request request,
        string generation,
        string desktopName,
        Stopwatch timer)
    {
        if (request.X is null || request.Y is null)
        {
            return Failure(
                request,
                generation,
                desktopName,
                timer,
                "invalid_request",
                "click requires x and y");
        }
        var button = request.Button?.ToLowerInvariant() ?? "left";
        if (button is not ("left" or "right"))
        {
            return Failure(
                request,
                generation,
                desktopName,
                timer,
                "invalid_button",
                "button must be left or right");
        }
        SendClick(request.X.Value, request.Y.Value, button);
        return Success(
            request,
            generation,
            desktopName,
            timer,
            "windows.native/send_input",
            "confirmed",
            "unverifiable",
            new { x = request.X, y = request.Y, button },
            coordinateSpace: "windows.virtual_screen_physical_pixels");
    }

    private static Result Key(
        Request request,
        string generation,
        string desktopName,
        Stopwatch timer)
    {
        if (string.IsNullOrWhiteSpace(request.Key))
        {
            return Failure(
                request,
                generation,
                desktopName,
                timer,
                "invalid_request",
                "key requires a supported key name");
        }
        SendKey(request.Key);
        return Success(
            request,
            generation,
            desktopName,
            timer,
            "windows.native/send_input",
            "confirmed",
            "unverifiable",
            new { key = request.Key });
    }

    private static Result TypeText(
        Request request,
        string generation,
        string desktopName,
        Stopwatch timer)
    {
        if (request.Text is null || request.Text.Length > 4096)
        {
            return Failure(
                request,
                generation,
                desktopName,
                timer,
                "invalid_request",
                "type requires text no longer than 4096 UTF-16 code units");
        }
        SendText(request.Text);
        return Success(
            request,
            generation,
            desktopName,
            timer,
            "windows.native/send_input_unicode",
            "confirmed",
            "unverifiable",
            new { textLength = request.Text.Length });
    }

    private static Result WindowState(
        Request request,
        string generation,
        string desktopName,
        Stopwatch timer)
    {
        if (request.Hwnd is null || string.IsNullOrWhiteSpace(request.State))
        {
            return Failure(
                request,
                generation,
                desktopName,
                timer,
                "invalid_request",
                "window.state requires hwnd and state");
        }
        var hwnd = new IntPtr(request.Hwnd.Value);
        var command = request.State.ToLowerInvariant() switch
        {
            "minimized" => NativeMethods.SW_MINIMIZE,
            "maximized" => NativeMethods.SW_MAXIMIZE,
            "restored" => NativeMethods.SW_RESTORE,
            "closed" => -2,
            _ => -1,
        };
        if (command == -1)
        {
            return Failure(
                request,
                generation,
                desktopName,
                timer,
                "invalid_window_state",
                "state must be minimized, maximized, restored, or closed");
        }
        var delivered = command == -2
            ? NativeMethods.PostMessage(
                hwnd,
                NativeMethods.WM_CLOSE,
                IntPtr.Zero,
                IntPtr.Zero)
            : NativeMethods.ShowWindowAsync(hwnd, command);
        Thread.Sleep(250);
        var minimized = NativeMethods.IsIconic(hwnd);
        var maximized = NativeMethods.IsZoomed(hwnd);
        var exists = NativeMethods.IsWindow(hwnd);
        var confirmed = request.State.Equals(
                "closed",
                StringComparison.OrdinalIgnoreCase)
            ? !exists
            : request.State.Equals(
                "minimized",
                StringComparison.OrdinalIgnoreCase)
            ? minimized
            : request.State.Equals(
                    "maximized",
                    StringComparison.OrdinalIgnoreCase)
                ? maximized
                : !minimized && !maximized;
        return Success(
            request,
            generation,
            desktopName,
            timer,
            "windows.native/show_window_async",
            delivered ? "confirmed" : "refused",
            confirmed ? "confirmed" : "no_effect",
            new { hwnd = request.Hwnd, exists, minimized, maximized });
    }

    private static Result LockSession(
        Request request,
        string generation,
        string desktopName,
        Stopwatch timer)
    {
        if (!NativeMethods.LockWorkStation())
        {
            throw new System.ComponentModel.Win32Exception(
                Marshal.GetLastWin32Error(),
                "LockWorkStation failed");
        }
        Thread.Sleep(350);
        var afterDesktop = TryGetInputDesktopName();
        var sessionId = NativeMethods.WTSGetActiveConsoleSessionId();
        var locked = sessionId == uint.MaxValue
            ? null
            : SessionStateInspector.IsLocked(sessionId);
        return Success(
            request,
            generation,
            desktopName,
            timer,
            "windows.native/lock_work_station",
            "confirmed",
            locked == true ? "confirmed" : "unverifiable",
            new
            {
                inputDesktopBefore = desktopName,
                inputDesktopAfter = afterDesktop,
                sessionLocked = locked,
            });
    }

    private static Result Login(
        Request request,
        string generation,
        string desktopName,
        Stopwatch timer)
    {
        if (!string.Equals(
                desktopName,
                "Winlogon",
                StringComparison.OrdinalIgnoreCase))
        {
            return Failure(
                request,
                generation,
                desktopName,
                timer,
                "winlogon_not_active",
                "Credential login requires the Winlogon input desktop");
        }
        var credentialKind = request.CredentialKind?.ToLowerInvariant();
        if (credentialKind is not ("pin" or "password") ||
            string.IsNullOrWhiteSpace(request.SecretPipe))
        {
            return Failure(
                request,
                generation,
                desktopName,
                timer,
                "invalid_request",
                "Credential kind and protected secret pipe are required");
        }

        var fieldNames = credentialKind == "pin"
            ? new[] { "PIN", "Enter your PIN" }
            : new[] { "Password", "Enter your password" };
        var providerNames = credentialKind == "pin"
            ? new[] { "PIN (Windows Hello)", "Windows Hello PIN", "PIN" }
            : new[] { "Password" };
        var providerIds = credentialKind == "pin"
            ? new[]
            {
                "SignInOptionsItem_{D6886603-9D2F-4EB2-B667-1971041FA96B}",
            }
            : new[]
            {
                "SignInOptionsItem_{60B78E88-EAD8-445C-9CFD-0B87F74EA6CD}",
            };
        var root = AutomationElement.RootElement;
        var field = WaitForLoginElement(
            root,
            fieldNames,
            automationIds: null,
            ControlType.Edit,
            requireActionable: false,
            TimeSpan.FromMilliseconds(500));
        var provider = WaitForLoginElement(
            root,
            providerNames,
            providerIds,
            expectedType: ControlType.Button,
            requireActionable: true,
            TimeSpan.FromMilliseconds(500));
        var options = WaitForLoginElement(
            root,
            ["Sign-in options"],
            ["SignInOptionsLink"],
            expectedType: null,
            requireActionable: true,
            TimeSpan.FromMilliseconds(500));
        var anyCredentialField = field ?? WaitForUniqueCredentialEdit(
            root,
            TimeSpan.FromMilliseconds(500));
        if (field is null && provider is null && options is null &&
            anyCredentialField is null)
        {
            // Reveal the credential surface only when accessibility confirms
            // that Winlogon is still showing a non-credential lock screen.
            // Pressing Enter against an already focused credential field could
            // otherwise cause an unintended empty submission.
            SendKey("enter");
            Thread.Sleep(750);
            field = WaitForLoginElement(
                root,
                fieldNames,
                automationIds: null,
                ControlType.Edit,
                requireActionable: false,
                TimeSpan.FromSeconds(2));
            provider = WaitForLoginElement(
                root,
                providerNames,
                providerIds,
                expectedType: ControlType.Button,
                requireActionable: true,
                TimeSpan.FromMilliseconds(500));
            options = WaitForLoginElement(
                root,
                ["Sign-in options"],
                ["SignInOptionsLink"],
                expectedType: null,
                requireActionable: true,
                TimeSpan.FromSeconds(2));
        }

        var providerRoute = "already_selected";
        var providerSelectedExplicitly = false;
        if (field is null)
        {
            var optionsRoute = "already_expanded";
            if (provider is null)
            {
                if (options is null)
                {
                    return Failure(
                        request,
                        generation,
                        desktopName,
                        timer,
                        "sign_in_options_unavailable",
                        "The stock Sign-in options control was not found");
                }
                optionsRoute = ActivateLoginElement(options);
                Thread.Sleep(500);
                provider = WaitForLoginElement(
                    root,
                    providerNames,
                    providerIds,
                    expectedType: ControlType.Button,
                    requireActionable: true,
                    TimeSpan.FromSeconds(3));
            }
            if (provider is null)
            {
                return Failure(
                    request,
                    generation,
                    desktopName,
                    timer,
                    "credential_provider_unavailable",
                    $"The stock {credentialKind} provider was not found");
            }
            providerRoute = $"{optionsRoute}+{ActivateLoginElement(provider)}";
            providerSelectedExplicitly = true;
            Thread.Sleep(500);
            field = WaitForLoginElement(
                root,
                fieldNames,
                automationIds: null,
                ControlType.Edit,
                requireActionable: false,
                TimeSpan.FromSeconds(4));
            if (field is null && providerSelectedExplicitly)
            {
                field = WaitForUniqueCredentialEdit(
                    root,
                    TimeSpan.FromSeconds(2));
            }
        }
        if (field is null)
        {
            return Failure(
                request,
                generation,
                desktopName,
                timer,
                "credential_field_unavailable",
                $"The stock {credentialKind} credential field was not found");
        }

        try
        {
            field.SetFocus();
        }
        catch (Exception ex) when (
            ex is ElementNotAvailableException or InvalidOperationException)
        {
            return Failure(
                request,
                generation,
                desktopName,
                timer,
                "credential_field_unfocusable",
                "The stock credential field could not receive focus");
        }

        byte[]? secret = null;
        char[]? characters = null;
        try
        {
            secret = PipeTransport.ReceiveSecretOnceAsync(
                    request.SecretPipe,
                    TimeSpan.FromSeconds(20),
                    CancellationToken.None)
                .GetAwaiter()
                .GetResult();
            var encoding = new UTF8Encoding(
                encoderShouldEmitUTF8Identifier: false,
                throwOnInvalidBytes: true);
            characters = new char[encoding.GetMaxCharCount(secret.Length)];
            var count = encoding.GetChars(
                secret.AsSpan(),
                characters.AsSpan());
            if (count == 0 || characters.AsSpan(0, count).ContainsAny(
                    '\0', '\r', '\n'))
            {
                return Failure(
                    request,
                    generation,
                    desktopName,
                    timer,
                    "invalid_credential_encoding",
                    "The credential contains an unsupported control character");
            }
            SendSecretText(characters, count);
        }
        catch (DecoderFallbackException)
        {
            return Failure(
                request,
                generation,
                desktopName,
                timer,
                "invalid_credential_encoding",
                "The credential is not valid UTF-8");
        }
        finally
        {
            if (secret is not null)
            {
                CryptographicOperations.ZeroMemory(secret);
            }
            if (characters is not null)
            {
                Array.Clear(characters);
            }
        }

        SendKey("enter");
        var deadline = DateTime.UtcNow + TimeSpan.FromSeconds(25);
        var activeSession = NativeMethods.WTSGetActiveConsoleSessionId();
        var interactiveUserPresent = activeSession != uint.MaxValue &&
            SessionStateInspector.HasInteractiveUser(activeSession);
        var inputDesktopAfter = TryGetInputDesktopName();
        var loggedIn = interactiveUserPresent && string.Equals(
            inputDesktopAfter,
            "Default",
            StringComparison.OrdinalIgnoreCase);
        while (!loggedIn && DateTime.UtcNow < deadline)
        {
            Thread.Sleep(200);
            activeSession = NativeMethods.WTSGetActiveConsoleSessionId();
            interactiveUserPresent = activeSession != uint.MaxValue &&
                SessionStateInspector.HasInteractiveUser(activeSession);
            inputDesktopAfter = TryGetInputDesktopName();
            loggedIn = interactiveUserPresent && string.Equals(
                inputDesktopAfter,
                "Default",
                StringComparison.OrdinalIgnoreCase);
        }
        return Success(
            request,
            generation,
            desktopName,
            timer,
            "windows.native/winlogon_credential_provider+send_input_secret",
            "confirmed",
            loggedIn ? "confirmed" : "no_effect",
            new
            {
                credentialKind,
                providerSelectionRoute = providerRoute,
                credentialFieldFocused = true,
                inputDesktopAfter,
                interactiveUserPresent,
            });
    }

    private static AutomationElement? WaitForLoginElement(
        AutomationElement root,
        string[] names,
        string[]? automationIds,
        ControlType? expectedType,
        bool requireActionable,
        TimeSpan timeout)
    {
        var deadline = DateTime.UtcNow + timeout;
        do
        {
            var found = FindLoginElement(
                root,
                names,
                automationIds,
                expectedType,
                requireActionable,
                maxVisited: 10_000);
            if (found is not null) return found;
            Thread.Sleep(150);
        }
        while (DateTime.UtcNow < deadline);
        return null;
    }

    private static AutomationElement? FindLoginElement(
        AutomationElement root,
        string[] names,
        string[]? automationIds,
        ControlType? expectedType,
        bool requireActionable,
        int maxVisited)
    {
        AutomationElement? partial = null;
        var queue = new Queue<AutomationElement>();
        queue.Enqueue(root);
        var visited = 0;
        while (queue.Count > 0 && visited++ < maxVisited)
        {
            var current = queue.Dequeue();
            try
            {
                var controlType = current.Current.ControlType;
                var typeMatches = expectedType is null ||
                    controlType == expectedType;
                var actionable = !requireActionable ||
                    current.GetSupportedPatterns().Any(pattern =>
                        pattern == InvokePattern.Pattern ||
                        pattern == SelectionItemPattern.Pattern ||
                        pattern == TogglePattern.Pattern) ||
                    !current.Current.BoundingRectangle.IsEmpty;
                if (typeMatches && actionable)
                {
                    var name = current.Current.Name ?? string.Empty;
                    var automationId = current.Current.AutomationId ??
                        string.Empty;
                    if (automationIds?.Any(candidate =>
                            automationId.Equals(
                                candidate,
                                StringComparison.OrdinalIgnoreCase)) == true)
                    {
                        return current;
                    }
                    if (names.Any(candidate =>
                            name.Equals(
                                candidate,
                                StringComparison.OrdinalIgnoreCase)))
                    {
                        return current;
                    }
                    if (partial is null && names.Any(candidate =>
                            name.Contains(
                                candidate,
                                StringComparison.OrdinalIgnoreCase)))
                    {
                        partial = current;
                    }
                }
                var child = TreeWalker.RawViewWalker.GetFirstChild(current);
                while (child is not null)
                {
                    queue.Enqueue(child);
                    child = TreeWalker.RawViewWalker.GetNextSibling(child);
                }
            }
            catch (ElementNotAvailableException) { }
            catch (InvalidOperationException) { }
        }
        return partial;
    }

    private static AutomationElement? WaitForUniqueCredentialEdit(
        AutomationElement root,
        TimeSpan timeout)
    {
        var deadline = DateTime.UtcNow + timeout;
        do
        {
            var edits = FindVisibleCredentialEdits(root, maxVisited: 10_000);
            if (edits.Count > 0)
            {
                var firstBounds = edits[0].Current.BoundingRectangle;
                if (edits.All(element =>
                        element.Current.BoundingRectangle == firstBounds))
                {
                    return edits.FirstOrDefault(element =>
                            !string.IsNullOrWhiteSpace(
                                element.Current.AutomationId)) ??
                        edits[0];
                }
            }
            Thread.Sleep(150);
        }
        while (DateTime.UtcNow < deadline);
        return null;
    }

    private static List<AutomationElement> FindVisibleCredentialEdits(
        AutomationElement root,
        int maxVisited)
    {
        var edits = new List<AutomationElement>();
        var queue = new Queue<AutomationElement>();
        queue.Enqueue(root);
        var visited = 0;
        while (queue.Count > 0 && visited++ < maxVisited)
        {
            var current = queue.Dequeue();
            try
            {
                if (current.Current.ControlType == ControlType.Edit &&
                    current.Current.IsEnabled &&
                    !current.Current.IsOffscreen &&
                    !current.Current.BoundingRectangle.IsEmpty &&
                    current.TryGetCurrentPattern(
                        ValuePattern.Pattern,
                        out _))
                {
                    edits.Add(current);
                }
                var child = TreeWalker.RawViewWalker.GetFirstChild(current);
                while (child is not null)
                {
                    queue.Enqueue(child);
                    child = TreeWalker.RawViewWalker.GetNextSibling(child);
                }
            }
            catch (ElementNotAvailableException) { }
            catch (InvalidOperationException) { }
        }
        return edits;
    }

    private static string ActivateLoginElement(AutomationElement element)
    {
        var route = TryInvokePattern(element);
        if (route is not null) return route;
        var bounds = element.Current.BoundingRectangle;
        if (bounds.IsEmpty)
        {
            throw new InvalidOperationException(
                "The sign-in control has no actionable bounds");
        }
        SendClick(
            (int)bounds.X + (int)bounds.Width / 2,
            (int)bounds.Y + (int)bounds.Height / 2,
            "left");
        return "windows.native/send_input";
    }

    private static void Traverse(
        AutomationElement element,
        int depth,
        int maxDepth,
        int maxElements,
        int maxVisited,
        string? query,
        string generation,
        List<ElementRecord> records,
        ref int visited)
    {
        if (depth > maxDepth || records.Count >= maxElements ||
            visited >= maxVisited)
        {
            return;
        }
        visited++;
        try
        {
            var current = element.Current;
            var type = current.ControlType?.ProgrammaticName ?? "unknown";
            var name = current.Name ?? string.Empty;
            var automationId = current.AutomationId ?? string.Empty;
            var match = string.IsNullOrWhiteSpace(query) ||
                name.Contains(query, StringComparison.OrdinalIgnoreCase) ||
                automationId.Contains(
                    query,
                    StringComparison.OrdinalIgnoreCase) ||
                type.Contains(query, StringComparison.OrdinalIgnoreCase);
            if (match)
            {
                var bounds = current.BoundingRectangle;
                var runtimeId = element.GetRuntimeId() ?? [];
                var referenceBytes = Encoding.UTF8.GetBytes(
                    $"{generation}:{string.Join('.', runtimeId)}");
                var reference = Convert.ToHexString(
                    SHA256.HashData(referenceBytes)[..12]).ToLowerInvariant();
                if (Selectors.Count > 10_000)
                {
                    Selectors.Clear();
                }
                Selectors[reference] = new CachedSelector(
                    generation,
                    string.IsNullOrWhiteSpace(automationId)
                        ? name
                        : automationId);
                records.Add(new ElementRecord(
                    reference,
                    depth,
                    type.Replace("ControlType.", string.Empty),
                    name,
                    automationId,
                    current.IsEnabled,
                    current.IsOffscreen,
                    SafeRect(bounds),
                    element.GetSupportedPatterns()
                        .Select(pattern => pattern.ProgrammaticName)
                        .OrderBy(value => value)
                        .ToArray()));
            }
            if (depth == maxDepth) return;
            var child = TreeWalker.RawViewWalker.GetFirstChild(element);
            while (child is not null && records.Count < maxElements &&
                   visited < maxVisited)
            {
                Traverse(
                    child,
                    depth + 1,
                    maxDepth,
                    maxElements,
                    maxVisited,
                    query,
                    generation,
                    records,
                    ref visited);
                child = TreeWalker.RawViewWalker.GetNextSibling(child);
            }
        }
        catch (ElementNotAvailableException) { }
        catch (InvalidOperationException) { }
    }

    private static AutomationElement? FindElement(
        AutomationElement? root,
        string query,
        int maxVisited)
    {
        if (root is null) return null;
        AutomationElement? partial = null;
        var queue = new Queue<AutomationElement>();
        queue.Enqueue(root);
        var visited = 0;
        while (queue.Count > 0 && visited++ < maxVisited)
        {
            var current = queue.Dequeue();
            try
            {
                var name = current.Current.Name ?? string.Empty;
                var automationId = current.Current.AutomationId ?? string.Empty;
                if (name.Equals(query, StringComparison.OrdinalIgnoreCase) ||
                    automationId.Equals(
                        query,
                        StringComparison.OrdinalIgnoreCase))
                {
                    return current;
                }
                if (partial is null &&
                    (name.Contains(query, StringComparison.OrdinalIgnoreCase) ||
                     automationId.Contains(
                         query,
                         StringComparison.OrdinalIgnoreCase)))
                {
                    partial = current;
                }
                var child = TreeWalker.RawViewWalker.GetFirstChild(current);
                while (child is not null)
                {
                    queue.Enqueue(child);
                    child = TreeWalker.RawViewWalker.GetNextSibling(child);
                }
            }
            catch (ElementNotAvailableException) { }
            catch (InvalidOperationException) { }
        }
        return partial;
    }

    private static AutomationElement? ResolveAutomationRoot(Request request)
    {
        if (request.Hwnd is > 0)
        {
            return AutomationElement.FromHandle(new IntPtr(request.Hwnd.Value));
        }
        if (string.Equals(
                request.Target,
                "taskbar",
                StringComparison.OrdinalIgnoreCase))
        {
            return FindTaskbarAutomationRoot();
        }
        var hwnd = request.Target?.ToLowerInvariant() switch
        {
            "foreground" => NativeMethods.GetForegroundWindow(),
            _ => IntPtr.Zero,
        };
        return hwnd != IntPtr.Zero
            ? AutomationElement.FromHandle(hwnd)
            : AutomationElement.RootElement;
    }

    private static AutomationElement? FindTaskbarAutomationRoot()
    {
        var taskbar = NativeMethods.FindWindow("Shell_TrayWnd", null);
        if (taskbar == IntPtr.Zero) return null;
        var handles = new List<IntPtr> { taskbar };
        NativeMethods.EnumChildWindows(
            taskbar,
            (hwnd, _) =>
            {
                handles.Add(hwnd);
                return true;
            },
            IntPtr.Zero);

        AutomationElement? best = null;
        var bestCount = -1;
        foreach (var handle in handles)
        {
            try
            {
                var candidate = AutomationElement.FromHandle(handle);
                if (candidate is null) continue;
                var count = CountAutomationNodes(candidate, 250);
                if (count <= bestCount) continue;
                best = candidate;
                bestCount = count;
            }
            catch (ElementNotAvailableException) { }
            catch (InvalidOperationException) { }
        }
        return best;
    }

    private static int CountAutomationNodes(
        AutomationElement root,
        int limit)
    {
        var count = 0;
        var queue = new Queue<AutomationElement>();
        queue.Enqueue(root);
        while (queue.Count > 0 && count < limit)
        {
            var element = queue.Dequeue();
            count++;
            try
            {
                var child = TreeWalker.RawViewWalker.GetFirstChild(element);
                while (child is not null && count + queue.Count < limit)
                {
                    queue.Enqueue(child);
                    child = TreeWalker.RawViewWalker.GetNextSibling(child);
                }
            }
            catch (ElementNotAvailableException) { }
            catch (InvalidOperationException) { }
        }
        return count;
    }

    private static string? TryInvokePattern(AutomationElement element)
    {
        if (element.TryGetCurrentPattern(
                InvokePattern.Pattern,
                out var invoke))
        {
            ((InvokePattern)invoke).Invoke();
            return "windows.native/uia_invoke";
        }
        if (element.TryGetCurrentPattern(
                TogglePattern.Pattern,
                out var toggle))
        {
            ((TogglePattern)toggle).Toggle();
            return "windows.native/uia_toggle";
        }
        if (element.TryGetCurrentPattern(
                SelectionItemPattern.Pattern,
                out var selection))
        {
            ((SelectionItemPattern)selection).Select();
            return "windows.native/uia_select";
        }
        if (element.TryGetCurrentPattern(
                ExpandCollapsePattern.Pattern,
                out var expand))
        {
            ((ExpandCollapsePattern)expand).Expand();
            return "windows.native/uia_expand";
        }
        return null;
    }

    private static object SafeElementSummary(AutomationElement element)
    {
        try
        {
            return new
            {
                name = element.Current.Name,
                automationId = element.Current.AutomationId,
                controlType = element.Current.ControlType?.ProgrammaticName,
            };
        }
        catch
        {
            return new { unavailable = true };
        }
    }

    private static void SendClick(int x, int y, string button)
    {
        var bounds = GetVirtualScreen();
        var normalizedX = (int)Math.Round(
            (x - bounds.X) * 65535.0 / Math.Max(1, bounds.Width - 1));
        var normalizedY = (int)Math.Round(
            (y - bounds.Y) * 65535.0 / Math.Max(1, bounds.Height - 1));
        var down = button == "right"
            ? NativeMethods.MOUSEEVENTF_RIGHTDOWN
            : NativeMethods.MOUSEEVENTF_LEFTDOWN;
        var up = button == "right"
            ? NativeMethods.MOUSEEVENTF_RIGHTUP
            : NativeMethods.MOUSEEVENTF_LEFTUP;
        var inputs = new[]
        {
            MouseInput(
                normalizedX,
                normalizedY,
                NativeMethods.MOUSEEVENTF_MOVE |
                NativeMethods.MOUSEEVENTF_ABSOLUTE |
                NativeMethods.MOUSEEVENTF_VIRTUALDESK),
            MouseInput(
                normalizedX,
                normalizedY,
                down |
                NativeMethods.MOUSEEVENTF_ABSOLUTE |
                NativeMethods.MOUSEEVENTF_VIRTUALDESK),
            MouseInput(
                normalizedX,
                normalizedY,
                up |
                NativeMethods.MOUSEEVENTF_ABSOLUTE |
                NativeMethods.MOUSEEVENTF_VIRTUALDESK),
        };
        if (NativeMethods.SendInput(
                (uint)inputs.Length,
                inputs,
                Marshal.SizeOf<NativeMethods.INPUT>()) != inputs.Length)
        {
            throw new System.ComponentModel.Win32Exception(
                Marshal.GetLastWin32Error());
        }
    }

    private static NativeMethods.INPUT MouseInput(int x, int y, uint flags) =>
        new()
        {
            type = NativeMethods.INPUT_MOUSE,
            union = new NativeMethods.INPUTUNION
            {
                mouse = new NativeMethods.MOUSEINPUT
                {
                    dx = x,
                    dy = y,
                    dwFlags = flags,
                },
            },
        };

    private static void SendKey(string key)
    {
        var strokes = key.ToLowerInvariant() switch
        {
            "enter" => new ushort[] { 0x0D },
            "escape" => new ushort[] { 0x1B },
            "tab" => new ushort[] { 0x09 },
            "space" => new ushort[] { 0x20 },
            "alt+y" => new ushort[] { 0x12, 0x59 },
            "alt+n" => new ushort[] { 0x12, 0x4E },
            "alt+tab" => new ushort[] { 0x12, 0x09 },
            "alt+f4" => new ushort[] { 0x12, 0x73 },
            "ctrl+escape" => new ushort[] { 0x11, 0x1B },
            "shift+f10" => new ushort[] { 0x10, 0x79 },
            "win" => new ushort[] { 0x5B },
            "win+a" => new ushort[] { 0x5B, 0x41 },
            "win+d" => new ushort[] { 0x5B, 0x44 },
            "win+e" => new ushort[] { 0x5B, 0x45 },
            "win+i" => new ushort[] { 0x5B, 0x49 },
            "win+l" => new ushort[] { 0x5B, 0x4C },
            "win+n" => new ushort[] { 0x5B, 0x4E },
            "win+r" => new ushort[] { 0x5B, 0x52 },
            "win+s" => new ushort[] { 0x5B, 0x53 },
            _ => throw new ArgumentException($"Unsupported key '{key}'"),
        };
        var inputs = new List<NativeMethods.INPUT>();
        foreach (var stroke in strokes)
        {
            inputs.Add(KeyboardInput(stroke, 0));
        }
        for (var i = strokes.Length - 1; i >= 0; i--)
        {
            inputs.Add(KeyboardInput(
                strokes[i],
                NativeMethods.KEYEVENTF_KEYUP));
        }
        if (NativeMethods.SendInput(
                (uint)inputs.Count,
                inputs.ToArray(),
                Marshal.SizeOf<NativeMethods.INPUT>()) != inputs.Count)
        {
            throw new System.ComponentModel.Win32Exception(
                Marshal.GetLastWin32Error());
        }
    }

    private static void SendText(string value)
    {
        var inputs = new List<NativeMethods.INPUT>(value.Length * 2);
        foreach (var character in value)
        {
            inputs.Add(UnicodeInput(character, 0));
            inputs.Add(UnicodeInput(
                character,
                NativeMethods.KEYEVENTF_KEYUP));
        }
        if (inputs.Count == 0) return;
        if (NativeMethods.SendInput(
                (uint)inputs.Count,
                inputs.ToArray(),
                Marshal.SizeOf<NativeMethods.INPUT>()) != inputs.Count)
        {
            throw new System.ComponentModel.Win32Exception(
                Marshal.GetLastWin32Error());
        }
    }

    private static void SendSecretText(char[] value, int count)
    {
        var inputs = new NativeMethods.INPUT[2];
        try
        {
            for (var i = 0; i < count; i++)
            {
                inputs[0] = UnicodeInput(value[i], 0);
                inputs[1] = UnicodeInput(
                    value[i],
                    NativeMethods.KEYEVENTF_KEYUP);
                if (NativeMethods.SendInput(
                        (uint)inputs.Length,
                        inputs,
                        Marshal.SizeOf<NativeMethods.INPUT>()) != inputs.Length)
                {
                    throw new System.ComponentModel.Win32Exception(
                        Marshal.GetLastWin32Error());
                }
                Array.Clear(inputs);
            }
        }
        finally
        {
            Array.Clear(inputs);
        }
    }

    private static NativeMethods.INPUT UnicodeInput(char character, uint flags) =>
        new()
        {
            type = NativeMethods.INPUT_KEYBOARD,
            union = new NativeMethods.INPUTUNION
            {
                keyboard = new NativeMethods.KEYBDINPUT
                {
                    wScan = character,
                    dwFlags = flags | NativeMethods.KEYEVENTF_UNICODE,
                },
            },
        };

    private static NativeMethods.INPUT KeyboardInput(ushort key, uint flags) =>
        new()
        {
            type = NativeMethods.INPUT_KEYBOARD,
            union = new NativeMethods.INPUTUNION
            {
                keyboard = new NativeMethods.KEYBDINPUT
                {
                    wVk = key,
                    dwFlags = flags,
                },
            },
        };

    internal static string GetCurrentDesktopName() => GetDesktopName(
        NativeMethods.GetThreadDesktop(NativeMethods.GetCurrentThreadId()));

    internal static string GetInputDesktopName()
    {
        var desktop = NativeMethods.OpenInputDesktop(
            0,
            false,
            NativeMethods.DESKTOP_ALL_ACCESS);
        if (desktop == IntPtr.Zero)
        {
            throw new System.ComponentModel.Win32Exception(
                Marshal.GetLastWin32Error(),
                "OpenInputDesktop failed");
        }
        try { return GetDesktopName(desktop); }
        finally { NativeMethods.CloseDesktop(desktop); }
    }

    private static string GetDesktopName(IntPtr desktop)
    {
        var name = new StringBuilder(256);
        if (!NativeMethods.GetUserObjectInformation(
                desktop,
                NativeMethods.UOI_NAME,
                name,
                name.Capacity * sizeof(char),
                out _))
        {
            throw new System.ComponentModel.Win32Exception(
                Marshal.GetLastWin32Error());
        }
        return name.ToString();
    }

    private static string? TryGetInputDesktopName()
    {
        try { return GetInputDesktopName(); }
        catch { return null; }
    }

    private static (int X, int Y, int Width, int Height) GetVirtualScreen() =>
        (
            NativeMethods.GetSystemMetrics(NativeMethods.SM_XVIRTUALSCREEN),
            NativeMethods.GetSystemMetrics(NativeMethods.SM_YVIRTUALSCREEN),
            NativeMethods.GetSystemMetrics(NativeMethods.SM_CXVIRTUALSCREEN),
            NativeMethods.GetSystemMetrics(NativeMethods.SM_CYVIRTUALSCREEN)
        );

    private static object ToSerializableBounds(
        (int X, int Y, int Width, int Height) bounds) =>
        new
        {
            x = bounds.X,
            y = bounds.Y,
            width = bounds.Width,
            height = bounds.Height,
        };

    private static object? GetForegroundWindowSummary()
    {
        var hwnd = NativeMethods.GetForegroundWindow();
        if (hwnd == IntPtr.Zero) return null;
        var title = new StringBuilder(1024);
        NativeMethods.GetWindowText(hwnd, title, title.Capacity);
        NativeMethods.GetWindowThreadProcessId(hwnd, out var processId);
        return new
        {
            hwnd = hwnd.ToInt64(),
            processId,
            title = title.ToString(),
        };
    }

    private static object? GetCursorSummary() =>
        NativeMethods.GetCursorPos(out var point)
            ? new { x = point.X, y = point.Y }
            : null;

    private static RectRecord SafeRect(System.Windows.Rect bounds) =>
        new(
            double.IsFinite(bounds.X) ? bounds.X : 0,
            double.IsFinite(bounds.Y) ? bounds.Y : 0,
            double.IsFinite(bounds.Width) ? bounds.Width : 0,
            double.IsFinite(bounds.Height) ? bounds.Height : 0);

    private static int GetIntegrityRid()
    {
        if (!NativeMethods.OpenProcessToken(
                NativeMethods.GetCurrentProcess(),
                NativeMethods.TOKEN_QUERY,
                out var token))
        {
            return 0;
        }
        using var tokenHandle = new NativeHandle(token);
        return TokenInspector.GetIntegrityRid(token);
    }

    private static bool IsLocalSystem()
    {
        using var identity =
            System.Security.Principal.WindowsIdentity.GetCurrent();
        return identity.User?.IsWellKnown(
            System.Security.Principal.WellKnownSidType.LocalSystemSid) == true;
    }

    private static Result Success(
        Request request,
        string generation,
        string desktopName,
        Stopwatch timer,
        string route,
        string delivery,
        string effect,
        object? data,
        string? fidelity = "native",
        string? coordinateSpace = null) =>
        new()
        {
            RequestId = request.RequestId!,
            Operation = request.Operation,
            Accepted = true,
            ActualRoute = route,
            SessionId = NativeMethods.WTSGetActiveConsoleSessionId(),
            Desktop = desktopName,
            Generation = generation,
            Delivery = delivery,
            Effect = effect,
            Fidelity = fidelity,
            CoordinateSpace = coordinateSpace,
            FocusConsequence = route.Contains("send_input", StringComparison.Ordinal)
                ? "may_change"
                : "none_expected",
            CursorConsequence = route.Contains("send_input", StringComparison.Ordinal)
                ? "may_move"
                : "unchanged_expected",
            ProviderAttempts =
            [
                new ProviderAttempt(
                    IsLocalSystem()
                        ? "windows-native-protected"
                        : "windows-native-user",
                    "selected"),
            ],
            Data = data,
            Uncertainty = effect is "confirmed" or "not_applicable"
                ? "none"
                : "intended effect was not independently established",
            RetrySafety = effect == "unknown"
                ? "observe_and_reconcile_before_retry"
                : "not_needed",
            ProviderLatencyMs = timer.ElapsedMilliseconds,
            ElapsedMs = timer.ElapsedMilliseconds,
        };

    private static Result Failure(
        Request request,
        string generation,
        string desktopName,
        Stopwatch timer,
        string errorCode,
        string message) =>
        new()
        {
            RequestId = request.RequestId!,
            Operation = request.Operation,
            Accepted = false,
            ActualRoute = "windows.protected_session",
            SessionId = NativeMethods.WTSGetActiveConsoleSessionId(),
            Desktop = desktopName,
            Generation = generation,
            Delivery = "refused",
            Effect = "refused",
            Uncertainty = "none",
            RetrySafety = "safe_not_dispatched",
            ProviderAttempts =
            [
                new ProviderAttempt(
                    IsLocalSystem()
                        ? "windows-native-protected"
                        : "windows-native-user",
                    "refused",
                    errorCode,
                    timer.ElapsedMilliseconds,
                    "refused",
                    "refused"),
            ],
            ProviderLatencyMs = timer.ElapsedMilliseconds,
            ErrorCode = errorCode,
            Message = message,
            ElapsedMs = timer.ElapsedMilliseconds,
        };
}

internal sealed record CachedSelector(
    string Generation,
    string PreferredQuery);

internal static class SessionStateInspector
{
    public static bool HasInteractiveUser(uint sessionId)
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

    public static bool? IsLocked(uint sessionId)
    {
        if (!NativeMethods.WTSQuerySessionInformation(
                IntPtr.Zero,
                sessionId,
                NativeMethods.WTSSessionInfoEx,
                out var buffer,
                out var length))
        {
            return null;
        }
        try
        {
            if (length < 20 || Marshal.ReadInt32(buffer) != 1)
            {
                return null;
            }
            // WTSINFOEX.Data is 8-byte aligned after the DWORD Level.
            // SessionFlags is the third 32-bit field in WTSINFOEX_LEVEL1.
            const int sessionFlagsOffset = 16;
            var flags = Marshal.ReadInt32(buffer, sessionFlagsOffset);
            return flags switch
            {
                0 => true,
                1 => false,
                _ => null,
            };
        }
        finally
        {
            NativeMethods.WTSFreeMemory(buffer);
        }
    }
}

internal static class TokenInspector
{
    private const int TokenIntegrityLevel = 25;

    public static int GetIntegrityRid(IntPtr token)
    {
        NativeToken.GetTokenInformation(
            token,
            TokenIntegrityLevel,
            IntPtr.Zero,
            0,
            out var length);
        var buffer = Marshal.AllocHGlobal(length);
        try
        {
            if (!NativeToken.GetTokenInformation(
                    token,
                    TokenIntegrityLevel,
                    buffer,
                    length,
                    out _))
            {
                return 0;
            }
            var label = Marshal.PtrToStructure<
                NativeToken.TOKEN_MANDATORY_LABEL>(buffer);
            var count = NativeToken.GetSidSubAuthorityCount(label.Label.Sid);
            if (count == IntPtr.Zero) return 0;
            var index = Marshal.ReadByte(count) - 1;
            var authority = NativeToken.GetSidSubAuthority(
                label.Label.Sid,
                index);
            return authority == IntPtr.Zero ? 0 : Marshal.ReadInt32(authority);
        }
        finally
        {
            Marshal.FreeHGlobal(buffer);
        }
    }

    private static class NativeToken
    {
        [StructLayout(LayoutKind.Sequential)]
        public struct SID_AND_ATTRIBUTES
        {
            public IntPtr Sid;
            public uint Attributes;
        }

        [StructLayout(LayoutKind.Sequential)]
        public struct TOKEN_MANDATORY_LABEL
        {
            public SID_AND_ATTRIBUTES Label;
        }

        [DllImport("advapi32.dll", SetLastError = true)]
        public static extern bool GetTokenInformation(
            IntPtr token,
            int tokenInformationClass,
            IntPtr tokenInformation,
            int tokenInformationLength,
            out int returnLength);

        [DllImport("advapi32.dll")]
        public static extern IntPtr GetSidSubAuthorityCount(IntPtr sid);

        [DllImport("advapi32.dll")]
        public static extern IntPtr GetSidSubAuthority(IntPtr sid, int index);
    }
}
