using System.Text.Json;

namespace MachineControl.ElevatedFixture;

internal static class Program
{
    [STAThread]
    private static void Main(string[] args)
    {
        var marker = GetOption(args, "--marker");
        if (!string.IsNullOrWhiteSpace(marker))
        {
            Directory.CreateDirectory(Path.GetDirectoryName(marker)!);
            File.WriteAllText(marker, JsonSerializer.Serialize(new
            {
                approved = true,
                processId = Environment.ProcessId,
                startedUtc = DateTimeOffset.UtcNow,
            }));
        }

        ApplicationConfiguration.Initialize();
        Application.Run(new ElevatedForm(marker));
    }

    private static string? GetOption(string[] args, string name)
    {
        for (var index = 0; index + 1 < args.Length; index++)
        {
            if (string.Equals(args[index], name, StringComparison.OrdinalIgnoreCase))
            {
                return args[index + 1];
            }
        }
        return null;
    }
}

internal sealed class ElevatedForm : Form
{
    private readonly string? _marker;
    private readonly Label _counterLabel;
    private int _counter;

    public ElevatedForm(string? marker)
    {
        _marker = marker;
        Text = "Machine Control Elevated Fixture";
        AccessibleName = Text;
        StartPosition = FormStartPosition.CenterScreen;
        ClientSize = new Size(520, 190);

        var authority = new Label
        {
            Text = "Elevated fixture started",
            AccessibleName = "Elevated fixture started",
            AutoSize = true,
            Location = new Point(24, 24),
        };
        var increment = new Button
        {
            Text = "Increment elevated counter",
            AccessibleName = "Increment elevated counter",
            Location = new Point(24, 64),
            Size = new Size(220, 38),
        };
        _counterLabel = new Label
        {
            Text = "Elevated counter: 0",
            AccessibleName = "Elevated counter 0",
            AutoSize = true,
            Location = new Point(24, 124),
        };
        increment.Click += (_, _) =>
        {
            _counter++;
            _counterLabel.Text = $"Elevated counter: {_counter}";
            _counterLabel.AccessibleName = $"Elevated counter {_counter}";
            if (!string.IsNullOrWhiteSpace(_marker))
            {
                File.AppendAllText(_marker, Environment.NewLine + $"counter={_counter}");
            }
        };
        Controls.Add(authority);
        Controls.Add(increment);
        Controls.Add(_counterLabel);
    }
}
