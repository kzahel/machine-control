using System.Diagnostics;
using System.IO;
using System.Runtime.InteropServices;
using System.Text;
using System.Windows.Automation;
using static MachineControl.Windows.ApplicationTargets;

namespace MachineControl.Windows;

/// Running-application identity for agent targets. A target names a running
/// application by process ID, process or product name, application user model
/// ID, or window title; an exact match wins over a unique partial match. A
/// target that resolves to nothing, or ambiguously, is refused rather than
/// silently replaced by the foreground or the whole screen.
internal static partial class DesktopController
{
    private static readonly HashSet<string> ShellWindowClasses = new(StringComparer.Ordinal)
    {
        "Progman", "WorkerW", "Shell_TrayWnd", "Shell_SecondaryTrayWnd",
        "TopLevelWindowForOverflowXamlIsland", "NotifyIconOverflowWindow",
    };

    /// Visible, uncloaked, unowned top-level windows in Z order (front first).
    private static List<ApplicationWindow> ApplicationWindows(IntPtr desktop)
    {
        var windows = new List<ApplicationWindow>();
        var names = new Dictionary<int, (string Process, string Name, string? ApplicationId)>();
        var order = 0;
        NativeMethods.EnumDesktopWindows(desktop, (hwnd, _) =>
        {
            order++;
            if (!NativeMethods.IsWindowVisible(hwnd) || ApplicationNative.GetWindow(hwnd, ApplicationNative.GW_OWNER) != IntPtr.Zero ||
                ApplicationNative.Cloaked(hwnd) || !NativeMethods.GetWindowRect(hwnd, out var rect) ||
                rect.Right - rect.Left <= 0 || rect.Bottom - rect.Top <= 0) return true;
            var className = new StringBuilder(256);
            NativeMethods.GetClassName(hwnd, className, className.Capacity);
            if (ShellWindowClasses.Contains(className.ToString())) return true;
            var title = new StringBuilder(512);
            NativeMethods.GetWindowText(hwnd, title, title.Capacity);
            if (title.Length == 0) return true;
            NativeMethods.GetWindowThreadProcessId(hwnd, out var processId);
            if (!names.TryGetValue((int)processId, out var identity))
            {
                identity = ProcessIdentity((int)processId);
                names[(int)processId] = identity;
            }
            windows.Add(new ApplicationWindow(hwnd.ToInt64(), (int)processId, identity.Process, identity.Name,
                ApplicationActivation.TryGetWindowApplicationId(hwnd) ?? identity.ApplicationId, title.ToString(), order));
            return true;
        }, IntPtr.Zero);
        return windows;
    }

    private static (string Process, string Name, string? ApplicationId) ProcessIdentity(int processId)
    {
        string? image = null;
        var handle = NativeMethods.OpenProcess(NativeMethods.PROCESS_QUERY_LIMITED_INFORMATION, false, (uint)processId);
        if (handle != IntPtr.Zero)
        {
            using var owned = new NativeHandle(handle);
            var buffer = new StringBuilder(1024);
            var length = buffer.Capacity;
            if (ApplicationNative.QueryFullProcessImageName(handle, 0, buffer, ref length)) image = buffer.ToString(0, length);
        }
        var process = image is null ? "" : Path.GetFileNameWithoutExtension(image);
        if (process.Length == 0)
            try { using var fallback = Process.GetProcessById(processId); process = fallback.ProcessName; }
            catch (Exception ex) when (ex is ArgumentException or InvalidOperationException) { }
        string? description = null;
        if (image is not null)
            try { description = FileVersionInfo.GetVersionInfo(image).FileDescription?.Trim(); }
            catch (Exception ex) when (ex is IOException or UnauthorizedAccessException or ArgumentException) { }
        return (process, string.IsNullOrWhiteSpace(description) ? process : description!, TryGetApplicationUserModelId(processId));
    }

    private static TargetResolution ResolveTarget(IntPtr desktop, string target) =>
        ApplicationTargets.Select(ApplicationWindows(desktop), target, ApplicationNative.RootOwner(NativeMethods.GetForegroundWindow()).ToInt64());

    private static object WindowIdentity(ApplicationWindow window) => new
    {
        application = window.Name,
        processName = window.ProcessName,
        processId = window.ProcessId,
        applicationId = window.ApplicationId,
        window = window.Title,
        hwnd = window.Hwnd,
    };

    private static Result TargetFailure(Request request, string generation, string desktopName, Stopwatch timer, TargetResolution resolution) =>
        Failure(request, generation, desktopName, timer,
            resolution.Refusal == "invalid_target" ? "invalid_request" : "target_unavailable",
            resolution.Refusal switch
            {
                "invalid_target" => "target must name one running application",
                "target_ambiguous" => $"target '{request.Target}' matches {resolution.Candidates} applications; use an exact name or process ID",
                _ => $"No running application with a visible window matches '{request.Target}'",
            }) with
        { Data = new { target = request.Target, matches = resolution.Candidates } };

    /// Brings the resolved application window to the foreground and confirms
    /// it independently. Every attempt is an authorized desktop effect.
    private static bool ActivateWindow(ApplicationWindow target)
    {
        var hwnd = new IntPtr(target.Hwnd);
        // The window itself or one of its owned dialogs is in front.
        bool Front() => ApplicationNative.RootOwner(NativeMethods.GetForegroundWindow()) == hwnd;
        bool Settled()
        {
            for (var attempt = 0; attempt < 10; attempt++)
            {
                if (Front()) return true;
                Thread.Sleep(50);
            }
            return Front();
        }
        if (Front()) return true;
        var element = AutomationElement.FromHandle(hwnd);
        if (NativeMethods.IsIconic(hwnd))
            DesktopAction(() => NativeMethods.ShowWindowAsync(hwnd, NativeMethods.SW_RESTORE), element);
        DesktopAction(() => ApplicationNative.SetForegroundWindow(hwnd), element);
        if (Settled()) return true;
        try { DesktopAction(() => element.SetFocus(), element); }
        catch (Exception ex) when (ex is InvalidOperationException or ElementNotAvailableException or COMException) { }
        if (Settled()) return true;
        // Foreground lock: a process that just delivered input may take the
        // foreground. Tap Alt (no menu activation once released) and retry.
        SendKeyboardInputs([KeyboardInput(0x12, 0)]);
        try { DesktopAction(() => ApplicationNative.SetForegroundWindow(hwnd), element); }
        finally { ReleaseKeyboardInputs([KeyboardInput(0x12, NativeMethods.KEYEVENTF_KEYUP)]); }
        return Settled();
    }

    /// The application, window and element that currently receive keystrokes.
    /// Never reads an element's value; only names and control types.
    private static object KeyboardReceiver()
    {
        var foreground = NativeMethods.GetForegroundWindow();
        if (foreground == IntPtr.Zero) return new { application = (string?)null };
        var root = ApplicationNative.Root(foreground);
        NativeMethods.GetWindowThreadProcessId(root, out var processId);
        var identity = ProcessIdentity((int)processId);
        var title = new StringBuilder(512);
        NativeMethods.GetWindowText(root, title, title.Capacity);
        string? focusedType = null, focusedName = null;
        try
        {
            var focused = AutomationElement.FocusedElement;
            if (focused is not null && focused.Current.ProcessId == processId)
            {
                focusedType = focused.Current.ControlType?.ProgrammaticName;
                focusedName = focused.Current.Name;
            }
        }
        catch (Exception ex) when (ex is InvalidOperationException or ElementNotAvailableException or COMException) { }
        return new
        {
            application = identity.Name,
            processName = identity.Process,
            processId = (int)processId,
            applicationId = ApplicationActivation.TryGetWindowApplicationId(root) ?? identity.ApplicationId,
            window = title.ToString(),
            hwnd = root.ToInt64(),
            focusedControlType = focusedType,
            focusedName,
        };
    }

    /// Resolves and activates request.Target for keyboard input. Returns a
    /// refusal, or null after the target is confirmed in the foreground.
    private static Result? PrepareKeyboardTarget(Request request, string generation, string desktopName, IntPtr desktop, Stopwatch timer,
        out ApplicationWindow? activated)
    {
        activated = null;
        if (request.Target is null) return null;
        var resolution = ResolveTarget(desktop, request.Target);
        if (resolution.Window is not { } window) return TargetFailure(request, generation, desktopName, timer, resolution);
        if (!ActivateWindow(window))
            return Failure(request, generation, desktopName, timer, "target_unavailable",
                $"Could not bring '{window.Name}' to the foreground; nothing was typed") with
            {
                Delivery = "refused",
                Effect = "refused",
                FocusConsequence = "may_change",
                RetrySafety = "safe_not_dispatched",
                Data = new { target = request.Target, resolved = WindowIdentity(window), keyboardReceiver = KeyboardReceiver() },
            };
        activated = window;
        // From here every keystroke is authorized against the real foreground.
        if (_desktopRequest is not null) _desktopRequest = _desktopRequest with { Target = null };
        return null;
    }

    private static object? ResolvedTargetData(Request request, ApplicationWindow? activated) =>
        activated is null ? null : new { requested = request.Target, resolved = WindowIdentity(activated) };

    private static partial class ApplicationNative
    {
        internal const uint GW_OWNER = 4;
        private const uint GA_ROOT = 2, GA_ROOTOWNER = 3;
        private const int DWMWA_CLOAKED = 14;

        [DllImport("user32.dll")]
        internal static extern IntPtr GetWindow(IntPtr hwnd, uint command);

        [DllImport("user32.dll")]
        private static extern IntPtr GetAncestor(IntPtr hwnd, uint flags);

        [DllImport("user32.dll")]
        [return: MarshalAs(UnmanagedType.Bool)]
        internal static extern bool SetForegroundWindow(IntPtr hwnd);

        [DllImport("dwmapi.dll")]
        private static extern int DwmGetWindowAttribute(IntPtr hwnd, int attribute, out int value, int size);

        [DllImport("kernel32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
        [return: MarshalAs(UnmanagedType.Bool)]
        internal static extern bool QueryFullProcessImageName(IntPtr process, uint flags, StringBuilder name, ref int size);

        internal static IntPtr Root(IntPtr hwnd) => hwnd == IntPtr.Zero ? IntPtr.Zero : GetAncestor(hwnd, GA_ROOT) is var root && root != IntPtr.Zero ? root : hwnd;

        internal static IntPtr RootOwner(IntPtr hwnd) => hwnd == IntPtr.Zero ? IntPtr.Zero : GetAncestor(hwnd, GA_ROOTOWNER) is var owner && owner != IntPtr.Zero ? owner : hwnd;

        internal static bool Cloaked(IntPtr hwnd) => DwmGetWindowAttribute(hwnd, DWMWA_CLOAKED, out var cloaked, sizeof(int)) == 0 && cloaked != 0;
    }
}
