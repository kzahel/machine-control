using System.Diagnostics;
using System.IO;
using System.IO.Pipes;
using System.Runtime.InteropServices;
using System.Security.Principal;
using System.Text.Json;
using Forms = System.Windows.Forms;

namespace MachineControl.Windows;

/// Runs on the bound console's Default desktop as SYSTEM. Heartbeat loss,
/// physical input and a finite monotonic deadline all request the stock OS
/// lock. The deadline starts at 900 seconds and moves only by an acknowledged
/// extension of at most 900 seconds while the guardian is not ending.
/// This worker outlives a crashed resident/service until relock is observed.
internal static class DesktopRelockGuardian
{
    internal static async Task<int> RunAsync(string name)
    {
        if (!WindowsIdentity.GetCurrent().IsSystem) throw new UnauthorizedAccessException();
        await using var pipe = new NamedPipeClientStream(".", name, PipeDirection.InOut, PipeOptions.Asynchronous,
            TokenImpersonationLevel.Identification);
        using var setup = new CancellationTokenSource(TimeSpan.FromSeconds(5));
        await pipe.ConnectAsync(setup.Token);
        DesktopUacNative.RequireServer(pipe, DesktopUacNative.ServicePid());
        var frames = new GuardianJson(pipe);
        var start = JsonSerializer.Deserialize<RelockStart>(await frames.ReadAsync(setup.Token), Contract.Json)
            ?? throw new InvalidDataException();
        if (!start.StartedLocked || start.SessionId != Process.GetCurrentProcess().SessionId || !SameConsole(start) ||
            SessionStateInspector.IsLocked(start.SessionId) != true) throw new UnauthorizedAccessException();
        var result = new TaskCompletionSource<int>(TaskCreationOptions.RunContinuationsAsynchronously);
        var prepared = new TaskCompletionSource<bool>(TaskCreationOptions.RunContinuationsAsynchronously);
        var ending = 0;
        // First cause wins; only implementation-owned integer codes leave the
        // guardian. The low byte remains the independently observed relock.
        var cause = 0;
        void End(int reason)
        {
            Interlocked.CompareExchange(ref cause, reason, 0);
            Interlocked.Exchange(ref ending, 1);
        }
        var physical = 0;
        var heartbeat = Stopwatch.GetTimestamp();
        var monitorTick = heartbeat;
        var deadline = new GuardianDeadline(Stopwatch.GetTimestamp(), Stopwatch.Frequency);
        using var stop = new CancellationTokenSource();
        var thread = new Thread(() =>
        {
            using var context = new Forms.ApplicationContext();
            using var covers = new DesktopDisplayCovers();
            using var timer = new Forms.Timer { Interval = 100 };
            Hook callback = (code, message, data) =>
            {
                if (code >= 0)
                {
                    var keyboard = message.ToInt64() is >= 0x100 and <= 0x109;
                    var flags = Marshal.ReadInt32(data, keyboard ? 8 : 12);
                    if (DesktopActivityPolicy.Physical(keyboard, flags))
                    {
                        if (DesktopActivityPolicy.Deliberate(keyboard, message.ToInt64()))
                        { Interlocked.Exchange(ref physical, 1); End(1); }
                        // Motion alone is not takeover. Still swallow it and
                        // releases so no physical input reaches a hidden app.
                        // Swallow the entire physical sequence until relock;
                        // an interrupt must not click/type into a hidden app.
                        return new IntPtr(1);
                    }
                }
                return CallNextHookEx(IntPtr.Zero, code, message, data);
            };
            var keyboardHook = SetWindowsHookEx(13, callback, GetModuleHandle(null), 0);
            var mouseHook = SetWindowsHookEx(14, callback, GetModuleHandle(null), 0);
            if (keyboardHook == IntPtr.Zero || mouseHook == IntPtr.Zero) End(2);
            try
            {
                covers.Install();
                prepared.TrySetResult(keyboardHook != IntPtr.Zero && mouseHook != IntPtr.Zero && covers.Healthy);
            }
            catch (Exception) { prepared.TrySetResult(false); End(3); }
            timer.Tick += (_, _) =>
            {
                Interlocked.Exchange(ref monitorTick, Stopwatch.GetTimestamp());
                if (!covers.Maintain()) End(4);
                if (result.Task.IsCompleted) context.ExitThread();
            };
            try { timer.Start(); Forms.Application.Run(context); }
            catch (Exception) { End(5); }
            finally
            {
                if (keyboardHook != IntPtr.Zero) UnhookWindowsHookEx(keyboardHook);
                if (mouseHook != IntPtr.Zero) UnhookWindowsHookEx(mouseHook);
                GC.KeepAlive(callback);
                // The independent watchdog must still lock if this message
                // loop exits unexpectedly after admitting credential delivery.
                End(6);
                // Keep the native windows alive even if the message loop dies.
                // The independent watchdog must observe lock before disposal.
                if (prepared.Task.IsCompletedSuccessfully && prepared.Task.Result)
                    _ = result.Task.GetAwaiter().GetResult();
            }
        })
        { IsBackground = true, Name = "Machine Control relock guardian" };
        thread.SetApartmentState(ApartmentState.STA);
        thread.Start();
        if (!await prepared.Task.WaitAsync(setup.Token)) throw new IOException("relock_input_monitor_unavailable");
        await UnlockWire.WriteAsync(pipe, new { stage = "ready", extension = GuardianExtension.Protocol }, setup.Token);
        var watchdog = Task.Run(async () =>
        {
            while (!result.Task.IsCompleted)
            {
                if (!SameConsole(start)) { result.TrySetResult(1); break; }
                if (deadline.Expired(Stopwatch.GetTimestamp())) End(7);
                if (Stopwatch.GetElapsedTime(Volatile.Read(ref heartbeat)).TotalSeconds >= 3) End(8);
                if (Stopwatch.GetElapsedTime(Volatile.Read(ref monitorTick)).TotalSeconds >= 2) End(9);
                if (Volatile.Read(ref ending) != 0)
                {
                    if (SessionStateInspector.IsLocked(start.SessionId) == true) { result.TrySetResult(0); break; }
                    _ = NativeMethods.LockWorkStation();
                }
                await Task.Delay(100);
            }
        });
        var pulses = Task.Run(async () =>
        {
            try
            {
                while (!stop.IsCancellationRequested)
                {
                    using var pulseDeadline = CancellationTokenSource.CreateLinkedTokenSource(stop.Token);
                    pulseDeadline.CancelAfter(TimeSpan.FromSeconds(3));
                    using var pulse = JsonDocument.Parse(await frames.ReadAsync(pulseDeadline.Token));
                    if (!pulse.RootElement.GetProperty("allowed").GetBoolean()) End(10);
                    // An unknown or invalid extension ends protected use. An
                    // ending or expired guardian never acknowledges one.
                    if (!GuardianExtension.TryRead(pulse.RootElement, out var extension)) End(12);
                    else if (extension is not null)
                        switch (deadline.Extend(extension, Stopwatch.GetTimestamp(), Volatile.Read(ref ending) != 0))
                        {
                            case ExtensionOutcome.Invalid: End(12); break;
                            case ExtensionOutcome.Expired: End(7); break;
                        }
                    Interlocked.Exchange(ref heartbeat, Stopwatch.GetTimestamp());
                    await UnlockWire.WriteAsync(pipe, new
                    {
                        physicalTakeover = Volatile.Read(ref physical) != 0,
                        acknowledgedExtension = deadline.Acknowledged
                    }, pulseDeadline.Token);
                }
            }
            catch (Exception error) when (error is IOException or JsonException or OperationCanceledException or InvalidOperationException) { }
            finally { End(11); }
        });
        var exit = await result.Task;
        await watchdog;
        stop.Cancel();
        await pulses;
        thread.Join(TimeSpan.FromSeconds(2));
        return RelockExit.Encode(exit, Volatile.Read(ref cause));
    }

    private static bool SameConsole(RelockStart start)
    {
        try
        {
            return NativeMethods.WTSGetActiveConsoleSessionId() == start.SessionId &&
            UnlockNative.ConsoleUserSid(start.SessionId) == start.UserSid && UnlockNative.ConsoleLogonId(start.SessionId) == start.LogonId;
        }
        catch (Exception error) when (error is System.ComponentModel.Win32Exception or InvalidDataException) { return false; }
    }
    private delegate IntPtr Hook(int code, IntPtr message, IntPtr data);
    [DllImport("user32.dll", SetLastError = true)]
    private static extern IntPtr SetWindowsHookEx(int type, Hook callback, IntPtr module, uint thread);
    [DllImport("user32.dll")]
    private static extern bool UnhookWindowsHookEx(IntPtr hook);
    [DllImport("user32.dll")]
    private static extern IntPtr CallNextHookEx(IntPtr hook, int code, IntPtr message, IntPtr data);
    [DllImport("kernel32.dll", CharSet = CharSet.Unicode)]
    private static extern IntPtr GetModuleHandle(string? name);
}
