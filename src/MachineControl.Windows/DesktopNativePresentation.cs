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
                Form? notice = null;
                string? noticeId = null;
                Form? yieldNotice = null;
                var yieldShown = false;
                var yieldUntil = DateTimeOffset.MinValue;
                timer.Tick += (_, _) =>
                {
                    try
                    {
                        var state = JsonSerializer.SerializeToElement(broker.State(), Contract.Json);
                        var admission = state.GetProperty("admission");
                        var requests = admission.GetProperty("requests");
                        var cooldown = admission.TryGetProperty("handoffCooldownRemainingSeconds", out var wait) ? wait.GetDouble() : 0;
                        if (cooldown <= 0) yieldShown = false;
                        if (yieldNotice is not null && DateTimeOffset.UtcNow >= yieldUntil) { yieldNotice.Dispose(); yieldNotice = null; }
                        if (cooldown > 0 && !yieldShown)
                        {
                            yieldShown = true; yieldUntil = DateTimeOffset.UtcNow.AddSeconds(3);
                            yieldNotice = Window("You have control", 80, focus: false);
                            yieldNotice.Controls.Add(Text("Desktop yielded. You have control.", 18, 40));
                            yieldNotice.Show();
                        }
                        var current = requests.EnumerateArray().OrderBy(item => item.GetProperty("state").GetString() == "announcing" ? 0 : 1)
                            .FirstOrDefault(item => item.GetProperty("state").GetString() is "announcing" or "waiting_for_approval");
                        var next = current.ValueKind == JsonValueKind.Object ? current.GetProperty("intentId").GetString() + ":" + current.GetProperty("state").GetString() : null;
                        // Dismissal makes no permission decision. Keep this binding
                        // dismissed until the task changes state.
                        if (notice?.IsDisposed == true) { notice = null; }
                        if (next != noticeId)
                        {
                            notice?.Dispose(); notice = null; noticeId = next;
                            if (next is not null) { notice = Notice(broker, current); notice.Show(); }
                        }
                        if (notice is not null && current.ValueKind == JsonValueKind.Object)
                        {
                            var label = notice.Controls.Find("countdown", false).OfType<Label>().First();
                            label.Text = current.GetProperty("state").GetString() == "waiting_for_approval" ? "Waiting for your approval for this task." :
                                "Starts in " + Math.Ceiling(current.GetProperty("noticeRemainingSeconds").GetDouble()) + " seconds. You can keep working.";
                        }
                    }
                    catch (Exception ex)
                    {
                        broker.Journal?.Diagnostic("native.presentation.failed", FailureCode(ex));
                        timer.Stop();
                        broker.ApprovalPresentationAvailable = false;
                        broker.Stop("native_presentation_unavailable");
                        notice?.Dispose();
                    }
                };
                timer.Start();
                _ready.TrySetResult(true);
                Application.Run(context);
                notice?.Dispose();
                yieldNotice?.Dispose();
            }
            catch (Exception ex)
            {
                broker.Journal?.Diagnostic("native.presentation.start_failed", FailureCode(ex));
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
        ClientSize = new Size(440, height),
        FormBorderStyle = FormBorderStyle.FixedDialog,
        MaximizeBox = false,
        MinimizeBox = false,
        StartPosition = FormStartPosition.CenterScreen,
        TopMost = true,
        ShowInTaskbar = false,
        Font = new Font("Segoe UI", 10),
        AutoScaleMode = AutoScaleMode.Dpi,
    };
    private static Label Text(string content, int top, int height) => new()
    { Text = content, Location = new Point(18, top), Size = new Size(404, height), AutoEllipsis = true };
    private static Button Button(Form form, string label, int left, int top, Action action)
    {
        var button = new Button { Text = label, Location = new Point(left, top), Size = new Size(128, 34), AccessibleName = label };
        button.Click += (_, _) =>
        {
            try { action(); }
            catch (Exception ex) when (ex is ArgumentException or InvalidOperationException)
            {
                if (form.Controls.Find("notice-error", false).OfType<Label>().FirstOrDefault() is { } error)
                    error.Text = "This task changed. Check its current status before trying again.";
                (form.Tag as DesktopJournal)?.Diagnostic("native.notice.action_failed", FailureCode(ex));
            }
        };
        form.Controls.Add(button);
        return button;
    }
    private static string FailureCode(Exception error) => error switch
    {
        System.Text.Json.JsonException => "invalid_json",
        InvalidOperationException => "invalid_state",
        ArgumentException => "invalid_argument",
        System.IO.IOException => "io_failure",
        TimeoutException => "timeout",
        _ => "unexpected_exception"
    };
    private static Form Notice(DesktopGrants broker, JsonElement intent)
    {
        var id = intent.GetProperty("intentId").GetString()!;
        var needsApproval = intent.GetProperty("state").GetString() == "waiting_for_approval";
        var surfaces = string.Join(" + ", intent.GetProperty("surfaces").EnumerateArray().Select(value => value.GetString()));
        var profiles = intent.GetProperty("profileIds").EnumerateArray().Select(value => value.GetString()!).ToArray();
        var extra = profiles.Length > 0 ? 50 : 0;
        var form = Window(needsApproval ? "Machine Control requests access" : "Machine Control will use " + surfaces, 285 + extra, focus: false);
        form.Tag = broker.Journal;
        if (profiles.Length > 0)
        {
            var known = JsonSerializer.SerializeToElement(broker.BrowserPolicy?.Profiles, Contract.Json);
            var labels = profiles.Select(profile =>
            {
                var name = known.ValueKind == JsonValueKind.Array ? known.EnumerateArray()
                    .FirstOrDefault(item => item.TryGetProperty("profileId", out var id) && id.GetString() == profile) : default;
                var shortId = profile.Length > 8 ? "…" + profile[^8..] : profile;
                return name.ValueKind == JsonValueKind.Object && name.TryGetProperty("name", out var title)
                    ? title.GetString() + " (" + shortId + ")" : "Profile " + shortId;
            });
            form.Controls.Add(Text("Browser profiles: " + string.Join(", ", labels), 100, 50));
        }
        form.Controls.Add(Text(intent.GetProperty("reason").GetString()!, 18, 50));
        form.Controls.Add(Text("Surface: " + surfaces + ". A local app requested this task.", 70, 28));
        var countdown = Text("", 104 + extra, 40); countdown.Name = "countdown"; form.Controls.Add(countdown);

        Button(form, needsApproval ? "Allow now" : "Start now", 18, 155 + extra, () =>
        {
            // Drain native input before activation so choosing this button
            // cannot immediately count as a later human takeover.
            broker.Activity.AcknowledgeOperatorInput();
            broker.Admission.Refresh();
            if (needsApproval) broker.Admission.Approve(id); else broker.Admission.StartNow(id);
            form.Close();
        });
        var delays = new ContextMenuStrip();
        form.Disposed += (_, _) => delays.Dispose();
        Button(form, needsApproval ? "Allow in…" : "More time…", 156, 155 + extra, () => delays.Show(Cursor.Position));
        var budget = intent.TryGetProperty("taskRemainingSeconds", out var remaining) ? remaining.GetDouble() : 0;
        foreach (var seconds in new[] { 30, 60, 300 })
        {
            var item = new ToolStripMenuItem(seconds == 30 ? "30 seconds" : seconds == 60 ? "1 minute" : "5 minutes") { Enabled = seconds + 65 < budget };
            item.Click += (_, _) =>
            {
                try
                {
                    broker.Activity.AcknowledgeOperatorInput();
                    if (needsApproval) broker.Admission.Approve(id, seconds); else broker.Admission.Postpone(id, seconds);
                    form.Close();
                }
                catch (Exception ex) when (ex is ArgumentException or InvalidOperationException)
                {
                    broker.Journal?.Diagnostic("native.notice.action_failed", FailureCode(ex));
                    if (form.Controls.Find("notice-error", false).OfType<Label>().FirstOrDefault() is { } error)
                        error.Text = "This task changed. Open Activity to review it.";
                }
            };
            delays.Items.Add(item);
        }
        Button(form, needsApproval ? "Decline" : "Cancel", 294, 155 + extra, () => { broker.Admission.CancelFromOperator(id); form.Close(); });
        Button(form, "Turn off access", 18, 200 + extra, () => { broker.Stop("stopped_by_person"); form.Close(); });
        var footer = Text("Desktop yields to your clicks, typing and scrolling. Browser work continues.", 245 + extra, 36);
        footer.Name = "notice-error"; form.Controls.Add(footer);
        return form;
    }
    public void Dispose()
    {
        if (_dispatcher is { } dispatcher && !dispatcher.IsDisposed)
        { try { dispatcher.BeginInvoke(() => _context?.ExitThread()); } catch (InvalidOperationException) { } }
        _thread.Join(TimeSpan.FromSeconds(3));
    }
    private sealed class SafetyForm(bool withoutActivation) : Form
    {
        protected override bool ShowWithoutActivation => withoutActivation;
        protected override CreateParams CreateParams
        {
            get
            {
                var parameters = base.CreateParams;
                // ShowWithoutActivation alone still allowed first-window
                // activation in the real interactive Windows qualification.
                if (withoutActivation) parameters.ExStyle |= 0x08000000; // WS_EX_NOACTIVATE
                return parameters;
            }
        }
    }
}
