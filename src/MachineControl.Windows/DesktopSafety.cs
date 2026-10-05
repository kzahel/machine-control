using System.Runtime.InteropServices;
using System.Text;
using System.Windows.Automation;

namespace MachineControl.Windows;

internal static class DesktopSafety
{
    internal static DesktopGrants? Broker { get; set; }
    internal static int OperatorProcessId { get; set; }
    internal static int CoverProcessId { get; set; }
    internal static Func<Request, string, int?, string?>? ExternalCheck { get; set; }

    internal static bool Ready()
    {
        try
        {
            return NativeMethods.WTSGetActiveConsoleSessionId() == (uint)RuntimeProfile.SessionId &&
                (DesktopUacClient.Enabled || DesktopController.GetInputDesktopName() == "Default") &&
                SessionStateInspector.IsLocked((uint)RuntimeProfile.SessionId) == false;
        }
        catch (System.ComponentModel.Win32Exception) { return false; }
    }

    internal static void RefreshAvailability(DesktopGrants broker)
    {
        var sameConsole = NativeMethods.WTSGetActiveConsoleSessionId() == (uint)RuntimeProfile.SessionId;
        broker.SetReady(Ready(), sameConsole && SessionStateInspector.IsLocked((uint)RuntimeProfile.SessionId) == true);
    }

    internal static string? Check(Request request, string generation, int? resolvedProcess = null)
    {
        if (ExternalCheck is { } external) return external(request, generation, resolvedProcess);
        if (Broker is not { } broker) return null;
        RefreshAvailability(broker);
        var refusal = broker.Authorize(request, generation);
        if (refusal is not null) return refusal;
        if (DesktopGrants.ScopeFor(request.Operation) != "control") return null;
        if (OwnProcess(resolvedProcess ?? request.ProcessId) || OwnWindow(new IntPtr(request.Hwnd ?? 0)))
            return "self_target_refused";
        if (request.Operation is "key" or "key.timeline" or "key.delayed_hold" or "type" && OwnWindow(NativeMethods.GetForegroundWindow()))
            return "self_target_refused";
        if (request.Operation is "key" or "key.timeline" or "key.delayed_hold" or "type" && OwnShellElement(AutomationElement.FocusedElement))
            return "self_target_refused";
        if (request.Operation is "click" or "move" or "drag" or "scroll")
        {
            var gui = new GuiThreadInfo { Size = Marshal.SizeOf<GuiThreadInfo>() };
            if (!GetGUIThreadInfo(0, ref gui)) return "pointer_routing_unknown";
            if (OwnWindow(gui.Capture)) return "self_target_refused";
            int x, y;
            if (request.Operation == "scroll")
            {
                if (!NativeMethods.GetCursorPos(out var cursor)) return "pointer_unavailable";
                x = cursor.X; y = cursor.Y;
                if (OwnWindow(NativeMethods.GetForegroundWindow())) return "self_target_refused";
            }
            else
            {
                if (request.X is not { } rx || request.Y is not { } ry) return "invalid_request";
                x = rx; y = ry;
            }
            var x2 = request.Operation == "drag" ? request.X2 ?? x : x;
            var y2 = request.Operation == "drag" ? request.Y2 ?? y : y;
            var hit = WindowFromPoint(new Point { X = x, Y = y });
            var endHit = WindowFromPoint(new Point { X = x2, Y = y2 });
            if ((OwnWindow(hit) && !CoverWindow(hit)) || (OwnWindow(endHit) && !CoverWindow(endHit)) ||
                OwnPath(x, y, x2, y2)) return "self_target_refused";
            if (OwnShellElement(AutomationElement.FromPoint(new System.Windows.Point(x, y))) ||
                OwnShellElement(AutomationElement.FromPoint(new System.Windows.Point(x2, y2))))
                return "self_target_refused";
        }
        if (request.Operation == "app.activate" && request.ApplicationId == "org.machine-control.app")
            return "self_target_refused";
        if (request.Operation == "app.launch" && request.ExecutablePath is { } executable)
        {
            var name = System.IO.Path.GetFileName(executable);
            if (name.Equals("machine-control.exe", StringComparison.OrdinalIgnoreCase) ||
                name.Equals("macui.exe", StringComparison.OrdinalIgnoreCase) ||
                name.Equals("machine-control-windows.exe", StringComparison.OrdinalIgnoreCase))
                return "self_target_refused";
        }
        return null;
    }

    internal static void Require(Request request, string generation, AutomationElement? element = null)
    {
        var code = Check(request, generation, element?.Current.ProcessId);
        if (code is null && element is not null && DesktopGrants.ScopeFor(request.Operation) == "control")
        {
            if (OwnShellElement(element)) code = "self_target_refused";
            // WebView controls can belong to a browser child process. Follow
            // native UI ancestry rather than trusting the element's PID alone.
            var current = element;
            for (var depth = 0; current is not null && depth < 64; depth++)
            {
                if (OwnProcess(current.Current.ProcessId) || OwnWindow(new IntPtr(current.Current.NativeWindowHandle)))
                { code = "self_target_refused"; break; }
                current = TreeWalker.RawViewWalker.GetParent(current);
            }
        }
        if (code is not null) throw new DesktopAccessRefusedException(code);
    }

    // Explorer owns our taskbar/tray elements. Their UIA identity plus shell
    // ancestry is required; PID/HWND ownership alone misses those controls.
    private static bool OwnShellElement(AutomationElement? element)
    {
        var ownIdentity = false;
        for (var depth = 0; element is not null && depth < 64; depth++)
        {
            var current = element.Current;
            ownIdentity |= OwnShellIdentity(current.Name, current.AutomationId);
            if (ownIdentity && ShellClass(current.ClassName)) return true;
            element = TreeWalker.RawViewWalker.GetParent(element);
        }
        return false;
    }

    private static bool OwnShellIdentity(string name, string automationId) =>
        automationId == "Appid: org.machine-control.app" || name == "Machine Control" ||
        name.StartsWith("Machine Control - ", StringComparison.Ordinal) ||
        name.StartsWith("Machine Control Machine Control - ", StringComparison.Ordinal);

    private static bool OwnPath(int x, int y, int x2, int y2)
    {
        // A transparent provider cursor overlay can win FromPoint discovery
        // while input passes through it. Guard visible operator regions and
        // Explorer-owned product buttons independently of the topmost hit.
        var windows = new List<IntPtr>();
        NativeMethods.EnumDesktopWindows(IntPtr.Zero, (hwnd, _) =>
        {
            if (!CoverWindow(hwnd) && NativeMethods.IsWindowVisible(hwnd) && !NativeMethods.IsIconic(hwnd) &&
                NativeMethods.GetWindowRect(hwnd, out var rect) &&
                PointerGeometry.Intersects(x, y, x2, y2, rect.Left, rect.Top, rect.Right, rect.Bottom))
                windows.Add(hwnd);
            return true;
        }, IntPtr.Zero);
        foreach (var hwnd in windows)
        {
            if (OwnWindow(hwnd)) return true;
            if (!IsShellWindow(hwnd.ToInt64())) continue;
            var root = AutomationElement.FromHandle(hwnd);
            var buttons = root.FindAll(TreeScope.Descendants, new PropertyCondition(
                AutomationElement.ControlTypeProperty, ControlType.Button));
            foreach (AutomationElement button in buttons)
            {
                var current = button.Current;
                if (!current.IsOffscreen && OwnShellIdentity(current.Name, current.AutomationId) &&
                    PointerGeometry.Intersects(x, y, x2, y2, current.BoundingRectangle.Left,
                        current.BoundingRectangle.Top, current.BoundingRectangle.Right, current.BoundingRectangle.Bottom)) return true;
            }
        }
        return false;
    }

    internal static bool IsShellWindow(long? hwnd)
    {
        if (hwnd is not > 0) return false;
        var name = new StringBuilder(256);
        return NativeMethods.GetClassName(new IntPtr(hwnd.Value), name, name.Capacity) > 0 && ShellClass(name.ToString());
    }
    private static bool ShellClass(string name) => name is
        "Shell_TrayWnd" or "Shell_SecondaryTrayWnd" or "TopLevelWindowForOverflowXamlIsland" or "NotifyIconOverflowWindow";

    private static bool OwnProcess(int? processId) => processId is > 0 &&
        (processId == OperatorProcessId || processId == Environment.ProcessId || processId == CoverProcessId);
    private static bool CoverWindow(IntPtr hwnd)
    {
        if (hwnd == IntPtr.Zero || CoverProcessId == 0) return false;
        NativeMethods.GetWindowThreadProcessId(hwnd, out var pid);
        return pid == CoverProcessId;
    }
    private static bool OwnWindow(IntPtr hwnd)
    {
        if (hwnd == IntPtr.Zero) return false;
        NativeMethods.GetWindowThreadProcessId(hwnd, out var pid);
        if (OwnProcess((int)pid)) return true;
        var root = GetAncestor(hwnd, 2); // GA_ROOT crosses native WebView children.
        NativeMethods.GetWindowThreadProcessId(root, out pid);
        return OwnProcess((int)pid);
    }
    [StructLayout(LayoutKind.Sequential)]
    private struct GuiThreadInfo
    {
        public int Size; public uint Flags;
        public IntPtr Active, Focus, Capture, MenuOwner, MoveSize, Caret;
        public NativeMethods.RECT CaretRect;
    }
    [DllImport("user32.dll")]
    private static extern bool GetGUIThreadInfo(uint thread, ref GuiThreadInfo info);
    [StructLayout(LayoutKind.Sequential)]
    private struct Point { public int X; public int Y; }
    [DllImport("user32.dll")]
    private static extern IntPtr WindowFromPoint(Point point);
    [DllImport("user32.dll")]
    private static extern IntPtr GetAncestor(IntPtr hwnd, uint flags);
}

internal sealed class DesktopAccessRefusedException(string code) : Exception(code)
{
    internal string Code => Message;
}
