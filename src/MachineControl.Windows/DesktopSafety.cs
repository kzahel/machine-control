using System.Runtime.InteropServices;
using System.Windows.Automation;

namespace MachineControl.Windows;

internal static class DesktopSafety
{
    internal static DesktopGrants? Broker { get; set; }
    internal static int OperatorProcessId { get; set; }

    internal static bool Ready()
    {
        try
        {
            return NativeMethods.WTSGetActiveConsoleSessionId() == (uint)RuntimeProfile.SessionId &&
                DesktopController.GetInputDesktopName() == "Default" &&
                SessionStateInspector.IsLocked((uint)RuntimeProfile.SessionId) == false;
        }
        catch (System.ComponentModel.Win32Exception) { return false; }
    }

    internal static string? Check(Request request, string generation, int? resolvedProcess = null)
    {
        if (Broker is not { } broker) return null;
        broker.SetReady(Ready());
        var refusal = broker.Authorize(request.Operation, generation);
        if (refusal is not null) return refusal;
        if (DesktopGrants.ScopeFor(request.Operation) != "control") return null;
        if (OwnProcess(resolvedProcess ?? request.ProcessId) || OwnWindow(new IntPtr(request.Hwnd ?? 0)))
            return "self_target_refused";
        if (request.Operation is "key" or "type" && OwnWindow(NativeMethods.GetForegroundWindow()))
            return "self_target_refused";
        if (request.Operation == "click")
        {
            if (request.X is not { } x || request.Y is not { } y) return "invalid_request";
            if (OwnWindow(WindowFromPoint(new Point { X = x, Y = y }))) return "self_target_refused";
        }
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

    private static bool OwnProcess(int? processId) => processId is > 0 &&
        (processId == OperatorProcessId || processId == Environment.ProcessId);
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
