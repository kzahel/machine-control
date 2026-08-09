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
    private readonly Label _status;

    public FixtureForm(string marker)
    {
        _marker = marker;
        Text = "Machine Control Medium Fixture";
        AccessibleName = Text;
        StartPosition = FormStartPosition.CenterScreen;
        ClientSize = new Size(520, 190);

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
        elevate.Click += RequestElevation;
        Controls.Add(identity);
        Controls.Add(elevate);
        Controls.Add(_status);
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
