using System.Diagnostics;
using System.IO;
using System.Runtime.InteropServices;

namespace MachineControl.Windows;

internal static class UnlockPreparation
{
    public static void Run(uint sessionId, UnlockAttempt attempt)
    {
        attempt.CheckAuthority();
        // Existing-session lock can show the Windows LockApp curtain on
        // Default before entering Winlogon. Wake the display without typing
        // into an ordinary app, then dismiss only the verified OS curtain.
        var previous = SetThreadExecutionState(0x80000002); // CONTINUOUS | DISPLAY_REQUIRED
        try
        {
            var timer = Stopwatch.StartNew();
            var dismissed = false;
            var wakeSent = false;
            var expectedImage = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.Windows),
                "SystemApps", "Microsoft.LockApp_cw5n1h2txyewy", "LockApp.exe");
            while (timer.Elapsed < TimeSpan.FromSeconds(8))
            {
                attempt.CheckAuthority();
                var desktop = DesktopController.GetInputDesktopName();
                if (desktop == "Winlogon") return;
                if (desktop != "Default") throw new InvalidDataException("unlock_desktop_unsupported");
                var window = NativeMethods.GetForegroundWindow();
                NativeMethods.GetWindowThreadProcessId(window, out var processId);
                if (!wakeSent && window == IntPtr.Zero)
                {
                    // The locked display can be idle with no foreground window.
                    // A zero-delta relative mouse event reports activity without
                    // clicking, typing or changing the pointer coordinates.
                    attempt.CheckAuthority();
                    UnlockNative.RequireReleasedModifiers();
                    var wake = new NativeMethods.INPUT
                    {
                        type = 0,
                        union = new NativeMethods.INPUTUNION
                        { mouse = new NativeMethods.MOUSEINPUT { dwFlags = NativeMethods.MOUSEEVENTF_MOVE } },
                    };
                    if (NativeMethods.SendInput(1, [wake], Marshal.SizeOf<NativeMethods.INPUT>()) != 1)
                        throw new InvalidDataException("lock_display_wake_refused");
                    wakeSent = true;
                }
                if (!dismissed && processId != 0)
                {
                    using var process = Process.GetProcessById((int)processId);
                    if (process.SessionId == sessionId && string.Equals(process.MainModule?.FileName,
                            expectedImage, StringComparison.OrdinalIgnoreCase))
                    {
                        attempt.CheckAuthority();
                        UnlockNative.RequireReleasedModifiers();
                        if (NativeMethods.GetForegroundWindow() != window || DesktopController.GetInputDesktopName() != "Default")
                            throw new InvalidDataException("lock_curtain_changed");
                        // Escape cannot submit a credential if Windows changes
                        // desktops concurrently. Never send Enter from Default.
                        var inputs = new[] { Key(0), Key(NativeMethods.KEYEVENTF_KEYUP) };
                        if (NativeMethods.SendInput(2, inputs, Marshal.SizeOf<NativeMethods.INPUT>()) != 2)
                            throw new InvalidDataException("lock_curtain_input_refused");
                        dismissed = true;
                    }
                }
                Thread.Sleep(100);
            }
            throw new InvalidDataException(dismissed ? "lock_curtain_dismissal_not_observed" : "lock_curtain_not_foreground");
        }
        finally { SetThreadExecutionState(previous | 0x80000000); }
    }

    private static NativeMethods.INPUT Key(uint flags) => new()
    {
        type = 1,
        union = new NativeMethods.INPUTUNION { keyboard = new NativeMethods.KEYBDINPUT { wVk = 0x1B, dwFlags = flags } },
    };

    [DllImport("kernel32.dll")]
    private static extern uint SetThreadExecutionState(uint flags);
}
