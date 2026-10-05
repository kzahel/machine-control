using System.Text.Json;
using System.Diagnostics;

namespace MachineControl.Fixture;

/// Independent window-message oracle. Evidence is explicitly directed to an
/// owned test directory; this does not use the resident's delivery result.
internal sealed class PointerForm : Form
{
    private readonly string _output;
    private readonly PointerSurface _surface;
    private readonly List<object> _events = new();
    private int _vertical, _horizontal;
    internal PointerForm(string output)
    {
        _output = output;
        Text = "Pointer conformance fixture";
        StartPosition = FormStartPosition.Manual;
        Location = new Point(500, 100);
        ClientSize = new Size(500, 450);
        _surface = new PointerSurface
        {
            Name = "pointer-surface",
            AccessibleName = "Pointer surface",
            BackColor = Color.SteelBlue,
            Location = new Point(20, 20),
            Size = new Size(450, 390),
            TabStop = true,
        };
        _surface.MouseDown += (_, e) =>
        {
            _surface.Focus(); _surface.Capture = true;
            Record("down", e);
        };
        _surface.MouseUp += (_, e) => { Record("up", e); _surface.Capture = false; };
        _surface.MouseMove += (_, e) => Record("move", e);
        _surface.Wheel += (horizontal, delta) =>
        {
            if (horizontal) _horizontal += delta; else _vertical += delta;
            Save();
        };
        Controls.Add(_surface);
        Shown += (_, _) => Save();
    }
    private void Record(string kind, MouseEventArgs e)
    {
        if (_events.Count == 1000) _events.RemoveAt(0);
        var point = _surface.PointToScreen(e.Location);
        _events.Add(new { kind, button = e.Button.ToString(), x = point.X, y = point.Y, atMs = Stopwatch.GetTimestamp() * 1000.0 / Stopwatch.Frequency });
        Save();
    }
    private void Save()
    {
        var rect = _surface.RectangleToScreen(_surface.ClientRectangle);
        var text = JsonSerializer.Serialize(new
        {
            processId = Environment.ProcessId,
            vertical = _vertical,
            horizontal = _horizontal,
            bounds = new { x = rect.X, y = rect.Y, width = rect.Width, height = rect.Height },
            events = _events
        });
        File.WriteAllText(_output + ".pending", text);
        File.Move(_output + ".pending", _output, true);
    }
    private sealed class PointerSurface : Control
    {
        internal event Action<bool, int>? Wheel;
        protected override void WndProc(ref Message message)
        {
            if (message.Msg is 0x20A or 0x20E)
                Wheel?.Invoke(message.Msg == 0x20E, unchecked((short)(message.WParam.ToInt64() >> 16)));
            base.WndProc(ref message);
        }
    }
}
