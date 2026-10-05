using System.Diagnostics;
using System.IO;
using System.IO.Pipes;
using System.Runtime.InteropServices;
using System.Security.Principal;
using System.Text.Json;
using Forms = System.Windows.Forms;

namespace MachineControl.Windows;

/// Runs on the bound console's Default desktop as SYSTEM. Heartbeat loss,
/// physical input and a fixed maximum deadline all request the stock OS lock.
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
        var start = JsonSerializer.Deserialize<RelockStart>(await UnlockWire.ReadLineAsync(pipe, setup.Token), Contract.Json)
            ?? throw new InvalidDataException();
        if (!start.StartedLocked || start.SessionId != Process.GetCurrentProcess().SessionId || !SameConsole(start) ||
            SessionStateInspector.IsLocked(start.SessionId) != true) throw new UnauthorizedAccessException();
        var result = new TaskCompletionSource<int>(TaskCreationOptions.RunContinuationsAsynchronously);
        var prepared = new TaskCompletionSource<bool>(TaskCreationOptions.RunContinuationsAsynchronously);
        var ending = 0;
        var physical = 0;
        var heartbeat = Stopwatch.GetTimestamp();
        var monitorTick = heartbeat;
        var clock = Stopwatch.StartNew();
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
                    if ((flags & (keyboard ? 0x12 : 0x03)) == 0)
                    {
                        Interlocked.Exchange(ref physical, 1); Interlocked.Exchange(ref ending, 1);
                        // Swallow the entire physical sequence until relock;
                        // an interrupt must not click/type into a hidden app.
                        return new IntPtr(1);
                    }
                }
                return CallNextHookEx(IntPtr.Zero, code, message, data);
            };
            var keyboardHook = SetWindowsHookEx(13, callback, GetModuleHandle(null), 0);
            var mouseHook = SetWindowsHookEx(14, callback, GetModuleHandle(null), 0);
            if (keyboardHook == IntPtr.Zero || mouseHook == IntPtr.Zero) Interlocked.Exchange(ref ending, 1);
            try
            {
                covers.Install();
                prepared.TrySetResult(keyboardHook != IntPtr.Zero && mouseHook != IntPtr.Zero && covers.Healthy);
            }
            catch (Exception) { prepared.TrySetResult(false); Interlocked.Exchange(ref ending, 1); }
            timer.Tick += (_, _) =>
            {
                Interlocked.Exchange(ref monitorTick, Stopwatch.GetTimestamp());
                if (!covers.Maintain()) Interlocked.Exchange(ref ending, 1);
                if (result.Task.IsCompleted) context.ExitThread();
            };
            try { timer.Start(); Forms.Application.Run(context); }
            catch (Exception) { Interlocked.Exchange(ref ending, 1); }
            finally
            {
                if (keyboardHook != IntPtr.Zero) UnhookWindowsHookEx(keyboardHook);
                if (mouseHook != IntPtr.Zero) UnhookWindowsHookEx(mouseHook);
                GC.KeepAlive(callback);
                // The independent watchdog must still lock if this message
                // loop exits unexpectedly after admitting credential delivery.
                Interlocked.Exchange(ref ending, 1);
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
        await UnlockWire.WriteAsync(pipe, new { stage = "ready" }, setup.Token);
        var watchdog = Task.Run(async () =>
        {
            while (!result.Task.IsCompleted)
            {
                if (!SameConsole(start)) { result.TrySetResult(1); break; }
                if (clock.Elapsed.TotalSeconds >= 900 ||
                    Stopwatch.GetElapsedTime(Volatile.Read(ref heartbeat)).TotalSeconds >= 3 ||
                    Stopwatch.GetElapsedTime(Volatile.Read(ref monitorTick)).TotalSeconds >= 2)
                    Interlocked.Exchange(ref ending, 1);
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
                    using var deadline = CancellationTokenSource.CreateLinkedTokenSource(stop.Token);
                    deadline.CancelAfter(TimeSpan.FromSeconds(3));
                    using var pulse = JsonDocument.Parse(await UnlockWire.ReadLineAsync(pipe, deadline.Token));
                    if (!pulse.RootElement.GetProperty("allowed").GetBoolean()) Interlocked.Exchange(ref ending, 1);
                    Interlocked.Exchange(ref heartbeat, Stopwatch.GetTimestamp());
                    await UnlockWire.WriteAsync(pipe, new { physicalTakeover = Volatile.Read(ref physical) != 0 }, deadline.Token);
                }
            }
            catch (Exception error) when (error is IOException or JsonException or OperationCanceledException or InvalidOperationException) { }
            finally { Interlocked.Exchange(ref ending, 1); }
        });
        var exit = await result.Task;
        await watchdog;
        stop.Cancel();
        await pulses;
        thread.Join(TimeSpan.FromSeconds(2));
        return exit;
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
