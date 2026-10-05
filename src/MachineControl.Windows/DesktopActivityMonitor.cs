using System.Diagnostics;
using System.Runtime.InteropServices;
using Forms = System.Windows.Forms;

namespace MachineControl.Windows;

/// Pass-through Default-desktop input hooks. The SYSTEM covered guardian owns
/// suppression and relock. No hook callback waits on admission/provider locks.
internal sealed class DesktopActivityMonitor : IDisposable
{
    private readonly DesktopGrants _grants;
    private readonly Thread _thread;
    private long _physical;
    private long _pulse;
    private long _injectedKeyboard;
    private long _injectedMouse;
    private int _installed;
    private int _stopping;
    private uint? _idleEvent;
    private long _idleChanged;
    private readonly TaskCompletionSource<bool> _ready = new(TaskCreationOptions.RunContinuationsAsynchronously);

    internal DesktopActivityMonitor(DesktopGrants grants)
    {
        _grants = grants;
        _thread = new Thread(Run) { IsBackground = true, Name = "Machine Control local activity" };
        _thread.SetApartmentState(ApartmentState.STA);
        _thread.Start();
        _ready.Task.Wait(TimeSpan.FromSeconds(5));
        grants.Admission.RefreshAvailability = Refresh;
    }

    internal void Refresh()
    {
        var same = NativeMethods.WTSGetActiveConsoleSessionId() == (uint)RuntimeProfile.SessionId;
        var locked = same ? SessionStateInspector.IsLocked((uint)RuntimeProfile.SessionId) : null;
        var physical = Volatile.Read(ref _physical);
        if (physical != 0) _grants.Activity.ObservePhysical((double)physical / Stopwatch.Frequency);
        _grants.Activity.Tick(Healthy, locked, IdleSeconds(), _grants.Admission.HasActiveSession);
    }

    internal bool Healthy => Volatile.Read(ref _installed) != 0 &&
        Stopwatch.GetElapsedTime(Volatile.Read(ref _pulse)).TotalSeconds < 2;
    internal long InjectedKeyboard => Volatile.Read(ref _injectedKeyboard);
    internal long InjectedMouse => Volatile.Read(ref _injectedMouse);
    internal object State => new
    {
        supported = true,
        healthy = Healthy,
        quietSeconds = DesktopActivityPolicy.QuietSeconds,
        physicalClassification = "win32_low_level_injection_flags",
        lockedQuiet = "conservative_session_last_input",
        unknownBlocksAdmission = true
    };

    private void Run()
    {
        IntPtr keyboard = IntPtr.Zero, mouse = IntPtr.Zero;
        Hook Callback(bool keys) => (code, message, data) =>
        {
            if (code >= 0)
            {
                if (DesktopActivityPolicy.Physical(keys, Marshal.ReadInt32(data, keys ? 8 : 12)))
                    Interlocked.Exchange(ref _physical, Stopwatch.GetTimestamp());
                else if (keys) Interlocked.Increment(ref _injectedKeyboard);
                else Interlocked.Increment(ref _injectedMouse);
            }
            return CallNextHookEx(IntPtr.Zero, code, message, data);
        };
        var keyCallback = Callback(true); var mouseCallback = Callback(false);
        using var context = new Forms.ApplicationContext();
        using var timer = new Forms.Timer { Interval = 200 };
        var renewAt = 0L;
        void Tick()
        {
            if (Volatile.Read(ref _stopping) != 0) { context.ExitThread(); return; }
            // Windows can silently remove a timed-out low-level hook. Renew
            // both registrations, installing replacements before removing old
            // hooks. Callbacks only record timestamps and always pass input.
            if (Stopwatch.GetTimestamp() >= renewAt)
            {
                var nextKeyboard = SetWindowsHookEx(13, keyCallback, GetModuleHandle(null), 0);
                var nextMouse = SetWindowsHookEx(14, mouseCallback, GetModuleHandle(null), 0);
                Volatile.Write(ref _installed, nextKeyboard != IntPtr.Zero && nextMouse != IntPtr.Zero ? 1 : 0);
                if (keyboard != IntPtr.Zero) UnhookWindowsHookEx(keyboard);
                if (mouse != IntPtr.Zero) UnhookWindowsHookEx(mouse);
                keyboard = nextKeyboard; mouse = nextMouse;
                renewAt = Stopwatch.GetTimestamp() + Stopwatch.Frequency;
            }
            Interlocked.Exchange(ref _pulse, Stopwatch.GetTimestamp());
        }
        try
        {
            Tick(); _ready.TrySetResult(Healthy);
            timer.Tick += (_, _) => Tick(); timer.Start(); Forms.Application.Run(context);
        }
        catch (Exception) { _ready.TrySetResult(false); }
        finally
        {
            Volatile.Write(ref _installed, 0);
            if (keyboard != IntPtr.Zero) UnhookWindowsHookEx(keyboard);
            if (mouse != IntPtr.Zero) UnhookWindowsHookEx(mouse);
            GC.KeepAlive(keyCallback); GC.KeepAlive(mouseCallback);
        }
    }

    private double? IdleSeconds()
    {
        var info = new LastInput { Size = (uint)Marshal.SizeOf<LastInput>() };
        if (!GetLastInputInfo(ref info)) return null;
        // DWORD wrap is intentional; half-range ambiguity or a future event
        // tick cannot establish quiet. SendInput can supply nonmonotonic ticks.
        var elapsed = unchecked((uint)Environment.TickCount - info.Time);
        if (elapsed > int.MaxValue) return null;
        if (_idleEvent is null) _idleChanged = Stopwatch.GetTimestamp() - (long)(elapsed / 1000.0 * Stopwatch.Frequency);
        else if (_idleEvent != info.Time) _idleChanged = Stopwatch.GetTimestamp();
        _idleEvent = info.Time;
        // A newly observed event may carry a backdated synthetic timestamp.
        // Its arrival still resets the conservative locked-screen quiet timer.
        return Math.Min(elapsed / 1000.0, Stopwatch.GetElapsedTime(_idleChanged).TotalSeconds);
    }

    public void Dispose()
    {
        _grants.Admission.RefreshAvailability = null;
        Volatile.Write(ref _stopping, 1);
        _thread.Join(TimeSpan.FromSeconds(3));
    }
    private delegate IntPtr Hook(int code, IntPtr message, IntPtr data);
    [StructLayout(LayoutKind.Sequential)] private struct LastInput { internal uint Size, Time; }
    [DllImport("user32.dll")] private static extern bool GetLastInputInfo(ref LastInput info);
    [DllImport("user32.dll", SetLastError = true)] private static extern IntPtr SetWindowsHookEx(int type, Hook callback, IntPtr module, uint thread);
    [DllImport("user32.dll")] private static extern bool UnhookWindowsHookEx(IntPtr hook);
    [DllImport("user32.dll")] private static extern IntPtr CallNextHookEx(IntPtr hook, int code, IntPtr message, IntPtr data);
    [DllImport("kernel32.dll", CharSet = CharSet.Unicode)] private static extern IntPtr GetModuleHandle(string? name);
}
