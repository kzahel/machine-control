using System.ComponentModel;
using System.Diagnostics;
using System.Runtime.InteropServices;

namespace MachineControl.Fixture;

internal static class Program
{
    private static readonly string EvidenceDirectory = Path.Combine(
        Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
        "MachineControl",
        "conformance");

    [STAThread]
    private static void Main()
    {
        ApplicationConfiguration.Initialize();
        Directory.CreateDirectory(EvidenceDirectory);
        var marker = Path.Combine(EvidenceDirectory, "elevation-approved.json");
        Application.Run(new FixtureForm(marker));
    }
}

internal sealed class FixtureForm : Form
{
    private readonly string _marker;
    private readonly string _counterMarker;
    private readonly Label _status;
    private readonly Label _counter;
    private int _counterValue;

    public FixtureForm(string marker)
    {
        _marker = marker;
        _counterMarker = Path.Combine(
            Path.GetDirectoryName(marker)!,
            "counter.json");
        Text = "Machine Control Medium Fixture";
        AccessibleName = Text;
        StartPosition = FormStartPosition.CenterScreen;
        ClientSize = new Size(520, 250);

        var integrity = Integrity.GetRid();
        var identity = new Label
        {
            Text = $"Requester integrity RID: {integrity}",
            AccessibleName = $"Requester integrity RID {integrity}",
            AutoSize = true,
            Location = new Point(24, 24),
        };
        var elevate = new Button
        {
            Text = "Request elevation",
            AccessibleName = "Request elevation",
            Location = new Point(24, 64),
            Size = new Size(180, 38),
        };
        _status = new Label
        {
            Text = "Elevation not requested",
            AccessibleName = "Elevation status",
            AutoSize = true,
            Location = new Point(24, 124),
        };
        var increment = new Button
        {
            Name = "btn-increment",
            Text = "Increment counter",
            AccessibleName = "Increment counter",
            Location = new Point(250, 64),
            Size = new Size(180, 38),
        };
        _counter = new Label
        {
            Name = "counter-value",
            Text = "Counter: 0",
            AccessibleName = "Counter value 0",
            AutoSize = true,
            Location = new Point(250, 124),
        };
        increment.Click += (_, _) => SetCounter(_counterValue + 1);
        elevate.Click += RequestElevation;
        Controls.Add(identity);
        Controls.Add(elevate);
        Controls.Add(_status);
        Controls.Add(increment);
        Controls.Add(_counter);
        SetCounter(0);
    }

    private void SetCounter(int value)
    {
        _counterValue = value;
        _counter.Text = $"Counter: {value}";
        _counter.AccessibleName = $"Counter value {value}";
        File.WriteAllText(
            _counterMarker,
            $"{{\"counter\":{value},\"processId\":{Environment.ProcessId}}}");
    }

    private void RequestElevation(object? sender, EventArgs e)
    {
        _status.Text = "Elevation request sent to Windows";
        _ = Task.Run(() =>
        {
            try
            {
                File.Delete(_marker);
                var executable = Path.Combine(
                    AppContext.BaseDirectory,
                    "machine-control-elevated-fixture.exe");
                Process.Start(new ProcessStartInfo
                {
                    FileName = executable,
                    Arguments = $"--marker \"{_marker}\"",
                    UseShellExecute = true,
                    Verb = "runas",
                });
                SetStatus("Elevation request accepted by Windows");
            }
            catch (Win32Exception ex) when (ex.NativeErrorCode == 1223)
            {
                SetStatus("Elevation request cancelled");
            }
            catch (Exception ex)
            {
                SetStatus($"Elevation request failed: {ex.GetType().Name}");
            }
        });
    }

    private void SetStatus(string status)
    {
        if (IsDisposed) return;
        BeginInvoke(() =>
        {
            _status.Text = status;
            _status.AccessibleName = status;
        });
    }
}

internal static class Integrity
{
    private const int TokenIntegrityLevel = 25;
    private const uint TokenQuery = 0x0008;

    public static int GetRid()
    {
        if (!OpenProcessToken(
                Process.GetCurrentProcess().Handle,
                TokenQuery,
                out var token))
        {
            return 0;
        }
        try
        {
            GetTokenInformation(
                token,
                TokenIntegrityLevel,
                IntPtr.Zero,
                0,
                out var length);
            var buffer = Marshal.AllocHGlobal(length);
            try
            {
                if (!GetTokenInformation(
                        token,
                        TokenIntegrityLevel,
                        buffer,
                        length,
                        out _))
                {
                    return 0;
                }
                var label = Marshal.PtrToStructure<TokenMandatoryLabel>(buffer);
                var count = Marshal.ReadByte(GetSidSubAuthorityCount(
                    label.Label.Sid));
                return Marshal.ReadInt32(GetSidSubAuthority(
                    label.Label.Sid,
                    count - 1));
            }
            finally
            {
                Marshal.FreeHGlobal(buffer);
            }
        }
        finally
        {
            CloseHandle(token);
        }
    }

    [StructLayout(LayoutKind.Sequential)]
    private struct SidAndAttributes
    {
        public IntPtr Sid;
        public uint Attributes;
    }

    [StructLayout(LayoutKind.Sequential)]
    private struct TokenMandatoryLabel
    {
        public SidAndAttributes Label;
    }

    [DllImport("advapi32.dll", SetLastError = true)]
    private static extern bool OpenProcessToken(
        IntPtr process,
        uint access,
        out IntPtr token);

    [DllImport("advapi32.dll", SetLastError = true)]
    private static extern bool GetTokenInformation(
        IntPtr token,
        int informationClass,
        IntPtr information,
        int informationLength,
        out int returnLength);

    [DllImport("advapi32.dll")]
    private static extern IntPtr GetSidSubAuthorityCount(IntPtr sid);

    [DllImport("advapi32.dll")]
    private static extern IntPtr GetSidSubAuthority(IntPtr sid, int index);

    [DllImport("kernel32.dll")]
    private static extern bool CloseHandle(IntPtr handle);
}
