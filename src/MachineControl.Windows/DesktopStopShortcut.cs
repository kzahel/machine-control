using System.Runtime.InteropServices;
using System.Windows.Forms;

namespace MachineControl.Windows;

internal sealed class DesktopStopShortcut : IDisposable
{
    private readonly Thread _thread;
    private readonly TaskCompletionSource<bool> _ready = new(TaskCreationOptions.RunContinuationsAsynchronously);
    private StopWindow? _window;
    internal bool Available => _ready.Task.IsCompletedSuccessfully && _ready.Task.Result;
    internal DesktopStopShortcut(DesktopGrants broker)
    {
        _thread = new Thread(() =>
        {
            using var window = new StopWindow(broker);
            _window = window;
            _ready.TrySetResult(window.Registered);
            Application.Run();
        })
        { IsBackground = true, Name = "MachineControlEmergencyStop" };
        _thread.SetApartmentState(ApartmentState.STA);
        _thread.Start();
        _ready.Task.Wait(TimeSpan.FromSeconds(5));
    }
    public void Dispose()
    {
        if (_window is { } window) PostMessage(window.Handle, 0x0010, IntPtr.Zero, IntPtr.Zero);
        _thread.Join(TimeSpan.FromSeconds(5));
    }
    private sealed class StopWindow : NativeWindow, IDisposable
    {
        private readonly DesktopGrants _broker;
        internal bool Registered { get; }
        internal StopWindow(DesktopGrants broker)
        {
            _broker = broker;
            CreateHandle(new CreateParams { Caption = "Machine Control Stop", Parent = new IntPtr(-3) });
            // Ctrl+Alt+Shift+Period, repeat suppressed. This native thread
            // remains responsive independently of the WebView/operator IPC.
            Registered = RegisterHotKey(Handle, 1, 0x4000 | 1 | 2 | 4, 0xBE);
        }
        protected override void WndProc(ref Message message)
        {
            if (message.Msg == 0x0312) _broker.Stop("stopped_by_person");
            if (message.Msg == 0x0010) Application.ExitThread();
            base.WndProc(ref message);
        }
        public void Dispose() { if (Registered) UnregisterHotKey(Handle, 1); DestroyHandle(); }
    }
    [DllImport("user32.dll")]
    private static extern bool RegisterHotKey(IntPtr hwnd, int id, uint modifiers, uint key);
    [DllImport("user32.dll")]
    private static extern bool UnregisterHotKey(IntPtr hwnd, int id);
    [DllImport("user32.dll")]
    private static extern bool PostMessage(IntPtr hwnd, uint message, IntPtr wParam, IntPtr lParam);
}
