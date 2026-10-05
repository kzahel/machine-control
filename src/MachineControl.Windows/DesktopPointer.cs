using System.Diagnostics;
using System.Runtime.InteropServices;

namespace MachineControl.Windows;

internal static partial class DesktopController
{
    private static readonly object PointerGate = new();
    private static Result PointerSerialized(Func<Result> action)
    {
        lock (PointerGate) { RequireDesktopAuthority(); return action(); }
    }

    private static bool DisplayPoint(int x, int y) =>
        System.Windows.Forms.Screen.AllScreens.Any(screen => screen.Bounds.Contains(x, y));

    private static NativeMethods.INPUT AbsoluteMove(int x, int y)
    {
        var bounds = GetVirtualScreen();
        return MouseInput(
            (int)Math.Round(((double)x - bounds.X) * 65535 / Math.Max(1, bounds.Width - 1)),
            (int)Math.Round(((double)y - bounds.Y) * 65535 / Math.Max(1, bounds.Height - 1)),
            NativeMethods.MOUSEEVENTF_MOVE | NativeMethods.MOUSEEVENTF_ABSOLUTE |
            NativeMethods.MOUSEEVENTF_VIRTUALDESK);
    }

    private static void SendPointerInputs(params NativeMethods.INPUT[] inputs)
    {
        if (SendDesktopInput((uint)inputs.Length, inputs, Marshal.SizeOf<NativeMethods.INPUT>()) != inputs.Length)
            throw new System.ComponentModel.Win32Exception(Marshal.GetLastWin32Error());
    }

    private static Result Pointer(Request request, string generation, string desktop, Stopwatch timer)
    {
        Result Invalid(string message) => Failure(request, generation, desktop, timer, "invalid_request", message);
        if (request.Operation == "scroll")
        {
            var dx = request.DeltaX ?? 0; var dy = request.DeltaY ?? 0;
            if ((dx == 0 && dy == 0) || dx is < -12000 or > 12000 || dy is < -12000 or > 12000)
                return Invalid("scroll requires non-zero deltaX or deltaY, each between -12000 and 12000 wheel units");
            if (!NativeMethods.GetCursorPos(out var cursor))
                throw new System.ComponentModel.Win32Exception(Marshal.GetLastWin32Error());
            var inputs = new List<NativeMethods.INPUT>();
            if (dy != 0) inputs.Add(MouseInput(0, 0, NativeMethods.MOUSEEVENTF_WHEEL, dy));
            if (dx != 0) inputs.Add(MouseInput(0, 0, NativeMethods.MOUSEEVENTF_HWHEEL, dx));
            SendPointerInputs(inputs.ToArray());
            return Success(request, generation, desktop, timer, "windows.native/send_input", "confirmed", "unverifiable",
                new
                {
                    deltaX = dx,
                    deltaY = dy,
                    units = "windows.wheel_delta",
                    unitsPerDetent = 120,
                    positiveX = "right",
                    positiveY = "up",
                    cursorBeforeDispatch = new { x = cursor.X, y = cursor.Y }
                }) with
            { CursorConsequence = "unchanged_expected", FocusConsequence = "current_guest_input_routing" };
        }
        if (request.X is not { } x || request.Y is not { } y || !DisplayPoint(x, y))
            return Invalid("x and y must identify an active display pixel");
        if (request.Operation == "move")
        {
            SendPointerInputs(AbsoluteMove(x, y));
            return Success(request, generation, desktop, timer, "windows.native/send_input", "confirmed", "unverifiable",
                new { x, y }, coordinateSpace: "windows.virtual_screen_physical_pixels") with
            { CursorConsequence = "guest_cursor_moved", FocusConsequence = "none_expected" };
        }
        if (request.X2 is not { } x2 || request.Y2 is not { } y2 || !DisplayPoint(x2, y2))
            return Invalid("drag requires x2 and y2 on an active display");
        var duration = request.DurationMs ?? 300;
        var button = request.Button?.ToLowerInvariant() ?? "left";
        if (button is not ("left" or "right") || duration is < 50 or > 5000)
            return Invalid("drag button must be left or right; durationMs must be between 50 and 5000");
        var virtualBounds = GetVirtualScreen();
        var displayBounds = System.Windows.Forms.Screen.AllScreens.Select(screen => screen.Bounds).ToArray();
        var steps = Math.Clamp((duration + 19) / 20, 2, 50);
        var points = Enumerable.Range(0, steps + 1).Select(i => (
            X: (int)Math.Round(x + ((double)x2 - x) * i / steps),
            Y: (int)Math.Round(y + ((double)y2 - y) * i / steps))).ToArray();
        if (points.Any(point => !DisplayPoint(point.X, point.Y)))
            return Invalid("drag path must remain on active displays");
        var key = button == "right" ? 2 : 1;
        var down = button == "right" ? NativeMethods.MOUSEEVENTF_RIGHTDOWN : NativeMethods.MOUSEEVENTF_LEFTDOWN;
        var up = button == "right" ? NativeMethods.MOUSEEVENTF_RIGHTUP : NativeMethods.MOUSEEVENTF_LEFTUP;
        var releaseNeeded = false;
        try
        {
            if ((NativeMethods.GetAsyncKeyState(key) & 0x8000) != 0)
                throw new DesktopAccessRefusedException("pointer_button_already_held");
            SendPointerInputs(AbsoluteMove(x, y));
            DesktopAction(() =>
            {
                if ((NativeMethods.GetAsyncKeyState(key) & 0x8000) != 0)
                    throw new DesktopAccessRefusedException("pointer_button_already_held");
                // Mark before dispatch: a partial/unknown delivery must still
                // release our attempted press, without adding another motion.
                releaseNeeded = true;
                if (NativeMethods.SendInput(1, [MouseInput(0, 0, down)], Marshal.SizeOf<NativeMethods.INPUT>()) != 1)
                    throw new System.ComponentModel.Win32Exception(Marshal.GetLastWin32Error());
            });
            var elapsed = Stopwatch.StartNew();
            for (var i = 1; i <= steps; i++)
            {
                var wait = Math.Max(0, duration * i / steps - (int)elapsed.ElapsedMilliseconds);
                if (_desktopCancellation.WaitHandle.WaitOne(wait))
                    throw new DesktopAccessRefusedException("operation_cancelled");
                // Per-step authority includes current operator geometry and
                // session/desktop generation; no interrupted path is replayed.
                DesktopAction(() =>
                {
                    if (GetVirtualScreen() != virtualBounds ||
                        !displayBounds.SequenceEqual(System.Windows.Forms.Screen.AllScreens.Select(screen => screen.Bounds)))
                        throw new DesktopAccessRefusedException("display_changed");
                    // Authority discovery can be slow. Skip elapsed samples
                    // rather than extending the hold by their check latency.
                    i = Math.Clamp((int)Math.Ceiling(elapsed.Elapsed.TotalMilliseconds * steps / duration), i, steps);
                    if (!DisplayPoint(points[i].X, points[i].Y))
                        throw new DesktopAccessRefusedException("display_changed");
                    if (NativeMethods.SendInput(1, [AbsoluteMove(points[i].X, points[i].Y)],
                            Marshal.SizeOf<NativeMethods.INPUT>()) != 1)
                        throw new System.ComponentModel.Win32Exception(Marshal.GetLastWin32Error());
                });
            }
        }
        finally
        {
            if (releaseNeeded)
            {
                // Cleanup releases only the button we attempted to press.
                // This thread remains bound to the original desktop; never
                // switch to a newly active login/session to perform cleanup.
                if (NativeMethods.WTSGetActiveConsoleSessionId() != (uint)RuntimeProfile.SessionId ||
                    GetInputDesktopName() != desktop)
                    throw new DesktopAccessRefusedException("pointer_release_desktop_changed");
                if (NativeMethods.SendInput(1, [MouseInput(0, 0, up)], Marshal.SizeOf<NativeMethods.INPUT>()) != 1)
                    throw new System.ComponentModel.Win32Exception(Marshal.GetLastWin32Error());
            }
        }
        return Success(request, generation, desktop, timer, "windows.native/send_input", "confirmed", "unverifiable",
            new { x, y, x2, y2, button, durationMs = duration, buttonRelease = "delivered" },
            coordinateSpace: "windows.virtual_screen_physical_pixels") with
        { CursorConsequence = "guest_cursor_moved" };
    }
}
