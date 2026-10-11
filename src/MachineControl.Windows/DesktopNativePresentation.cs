using System.Text.Json;
using System.Windows.Forms;
using System.Drawing;

namespace MachineControl.Windows;

/// One native STA owns safety presentation independently of Settings, provider
/// workers and inherited operator IPC. It sends intents to the existing broker.
internal sealed class DesktopNativePresentation : IDisposable
{
    private readonly Thread _thread;
    private readonly TaskCompletionSource<bool> _ready = new(TaskCreationOptions.RunContinuationsAsynchronously);
    private ApplicationContext? _context;
    private Control? _dispatcher;
    internal bool Ready => _ready.Task.IsCompletedSuccessfully && _ready.Task.Result;
    internal DesktopNativePresentation(DesktopGrants broker)
    {
        _thread = new Thread(() =>
        {
            try
            {
                using var dispatcher = new Control();
                dispatcher.CreateControl();
                _ = dispatcher.Handle;
                _dispatcher = dispatcher;
                using var context = new ApplicationContext();
                _context = context;
                using var timer = new System.Windows.Forms.Timer { Interval = 200 };
                Form? approval = null, notice = null;
                string? pendingId = null, noticeId = null;
                timer.Tick += (_, _) =>
                {
                    try
                    {
                        var state = JsonSerializer.SerializeToElement(broker.State(), Contract.Json);
                        state.TryGetProperty("pending", out var pending);
                        var id = pending.ValueKind != JsonValueKind.Object ? null : pending.GetProperty("id").GetString();
                        if (id != pendingId)
                        {
                            approval?.Dispose(); approval = null; pendingId = id;
                            if (id is not null) { approval = Approval(broker, pending); approval.Show(); }
                        }
                        var requests = state.GetProperty("admission").GetProperty("requests");
                        JsonElement? announcing = requests.EnumerateArray().FirstOrDefault(item => item.GetProperty("state").GetString() == "announcing");
                        var next = announcing?.ValueKind == JsonValueKind.Object ? announcing.Value.GetProperty("intentId").GetString() : null;
                        if (next != noticeId)
                        {
                            notice?.Dispose(); notice = null; noticeId = next;
                            if (next is not null) { notice = Notice(broker, announcing!.Value); notice.Show(); }
                        }
                    }
                    catch (Exception)
                    {
                        timer.Stop();
                        broker.ApprovalPresentationAvailable = false;
                        broker.Stop("native_presentation_unavailable");
                        approval?.Dispose(); notice?.Dispose();
                    }
                };
                timer.Start();
                _ready.TrySetResult(true);
                Application.Run(context);
                approval?.Dispose(); notice?.Dispose();
            }
            catch (Exception)
            {
                _ready.TrySetResult(false);
                broker.ApprovalPresentationAvailable = false;
                broker.Stop("native_presentation_unavailable");
            }
        })
        { IsBackground = true, Name = "MachineControlSafetyPresentation" };
        _thread.SetApartmentState(ApartmentState.STA);
        _thread.Start();
        _ready.Task.Wait(TimeSpan.FromSeconds(3));
        broker.ApprovalPresentationAvailable = Ready;
    }
    private static Form Window(string title, int height, bool focus = true) => new SafetyForm(!focus)
    {
        Text = title,
        ClientSize = new Size(420, height),
        FormBorderStyle = FormBorderStyle.FixedDialog,
        MaximizeBox = false,
        MinimizeBox = false,
        StartPosition = FormStartPosition.CenterScreen,
        TopMost = true,
        Font = new Font("Segoe UI", 10),
        AutoScaleMode = AutoScaleMode.Dpi,
    };
    private static Label Text(string content, int top, int height) => new()
    { Text = content, Location = new Point(18, top), Size = new Size(384, height), AutoEllipsis = true };
    private static Button Button(Form form, string label, int left, int top, Action action)
    {
        var button = new Button { Text = label, Location = new Point(left, top), Size = new Size(118, 34), AccessibleName = label };
        button.Click += (_, _) =>
        {
            try { action(); }
            catch (Exception ex) when (ex is ArgumentException or InvalidOperationException)
            { MessageBox.Show(form, ex.Message, "Machine Control", MessageBoxButtons.OK, MessageBoxIcon.Information); }
        };
        form.Controls.Add(button);
        return button;
    }
    private static Form Approval(DesktopGrants broker, JsonElement pending)
    {
        var id = pending.GetProperty("id").GetString()!;
        var form = Window("Machine Control access request", 345);
        form.Controls.Add(Text(pending.GetProperty("reason").GetString()!, 18, 50));
        form.Controls.Add(Text(pending.GetProperty("caller").GetString()!, 72, 28));
        var scopes = new CheckedListBox { Location = new Point(18, 108), Size = new Size(384, 92), CheckOnClick = true, AccessibleName = "Access scopes" };
        foreach (var scope in pending.GetProperty("scopes").EnumerateArray()) scopes.Items.Add(scope.GetString()!, true);
        form.Controls.Add(scopes);
        var duration = pending.GetProperty("duration").GetInt32();
        form.Controls.Add(Text("Duration (seconds)", 215, 28));
        var seconds = new NumericUpDown { Location = new Point(250, 215), Size = new Size(150, 28), Minimum = 60, Maximum = duration, Value = duration, AccessibleName = "Duration seconds" };
        form.Controls.Add(seconds);
        var decided = false;
        Button(form, "Deny", 18, 280, () => { broker.Decide(id, false, null, 0); decided = true; form.Close(); });
        Button(form, "Allow", 154, 280, () => { broker.Decide(id, true, scopes.CheckedItems.Cast<string>().ToArray(), (int)seconds.Value); decided = true; form.Close(); });
        Button(form, "Stop access", 286, 280, () => { broker.Stop("stopped_by_person"); decided = true; form.Close(); });
        form.FormClosing += (_, _) => { if (!decided) { try { broker.Decide(id, false, null, 0); } catch (InvalidOperationException) { } } };
        form.Controls.Add(Text("Access applies to callers running as your user.", 318, 25));
        return form;
    }
    private static Form Notice(DesktopGrants broker, JsonElement intent)
    {
        var id = intent.GetProperty("intentId").GetString()!;
        var form = Window("Machine Control is ready to use the desktop", 165, focus: false);
        form.Controls.Add(Text(intent.GetProperty("reason").GetString()!, 18, 60));
        var responded = false;
        Button(form, "Start now", 18, 100, () => { broker.Admission.StartNow(id); responded = true; form.Close(); });
        Button(form, "Later", 154, 100, () => { broker.Admission.Pause("desktop", "operator_deferral", 60); responded = true; form.Close(); });
        Button(form, "Stop access", 286, 100, () => { broker.Stop("stopped_by_person"); responded = true; form.Close(); });
        form.FormClosing += (_, _) => { if (!responded) broker.Admission.Pause("desktop", "operator_deferral", 60); };
        return form;
    }
    public void Dispose()
    {
        if (_dispatcher is { } dispatcher && !dispatcher.IsDisposed)
        { try { dispatcher.BeginInvoke(() => _context?.ExitThread()); } catch (InvalidOperationException) { } }
        _thread.Join(TimeSpan.FromSeconds(3));
    }
    private sealed class SafetyForm(bool withoutActivation) : Form
    { protected override bool ShowWithoutActivation => withoutActivation; }
}
