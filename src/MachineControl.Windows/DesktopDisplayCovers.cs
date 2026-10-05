using System.ComponentModel;
using System.Drawing;
using System.Runtime.InteropServices;
using Forms = System.Windows.Forms;

namespace MachineControl.Windows;

/// Owned on the independent guardian's STA. These are presentation covers;
/// capture excludes them and injected input passes to the underlying desktop.
/// Physical input is intercepted separately before it can reach that desktop.
internal sealed class DesktopDisplayCovers : IDisposable
{
    private Cover? _cover;
    private Rectangle _bounds;
    internal bool Healthy => _cover is { IsDisposed: false, Visible: true } cover &&
        Forms.Screen.AllScreens is [var screen] && screen.Bounds == _bounds &&
        GetWindowDisplayAffinity(cover.Handle, out var affinity) && affinity == 0x11 &&
        DwmIsCompositionEnabled(out var composed) == 0 && composed;

    internal void Install()
    {
        if (!OperatingSystem.IsWindowsVersionAtLeast(10, 0, 19041) ||
            Forms.Screen.AllScreens is not [var screen] ||
            DwmIsCompositionEnabled(out var composed) != 0 || !composed)
            throw new InvalidOperationException("covered_display_configuration_unsupported");
        _bounds = screen.Bounds;
        _cover = new Cover
        {
            BackColor = Color.Black,
            FormBorderStyle = Forms.FormBorderStyle.None,
            StartPosition = Forms.FormStartPosition.Manual,
            Bounds = _bounds,
            TopMost = true,
            ShowInTaskbar = false,
            Text = "Machine Control privacy cover"
        };
        var window = _cover.Handle;
        if (!SetLayeredWindowAttributes(window, 0, 255, 2) || !SetWindowDisplayAffinity(window, 0x11))
            throw new Win32Exception(Marshal.GetLastWin32Error(), "covered_display_exclusion_unavailable");
        _cover.Show();
        _cover.Update();
        if (!Healthy) throw new InvalidOperationException("covered_display_unavailable");
    }

    internal bool Maintain()
    {
        if (!Healthy) return false;
        // Reassert presentation above newly activated ordinary application
        // windows without claiming foreground focus or changing their bounds.
        return SetWindowPos(_cover!.Handle, new IntPtr(-1), 0, 0, 0, 0, 0x13);
    }

    // Dispose only before unlock is admitted or after independent lock readback.
    public void Dispose() { _cover?.Dispose(); _cover = null; }

    private sealed class Cover : Forms.Form
    {
        protected override bool ShowWithoutActivation => true;
        protected override Forms.CreateParams CreateParams
        {
            get
            {
                var value = base.CreateParams;
                value.ExStyle |= 0x80000 | 0x20 | 0x8000000 | 0x80;
                return value;
            }
        }
    }

    [DllImport("user32.dll", SetLastError = true)]
    private static extern bool SetLayeredWindowAttributes(IntPtr window, uint color, byte alpha, uint flags);
    [DllImport("user32.dll", SetLastError = true)]
    private static extern bool SetWindowDisplayAffinity(IntPtr window, uint affinity);
    [DllImport("user32.dll")]
    private static extern bool GetWindowDisplayAffinity(IntPtr window, out uint affinity);
    [DllImport("user32.dll", SetLastError = true)]
    private static extern bool SetWindowPos(IntPtr window, IntPtr after, int x, int y, int width, int height, uint flags);
    [DllImport("dwmapi.dll")]
    private static extern int DwmIsCompositionEnabled(out bool enabled);
}
