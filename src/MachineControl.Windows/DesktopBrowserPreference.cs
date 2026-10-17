using System.IO;
using System.Text.Json;

namespace MachineControl.Windows;

/// Local operator choice, never a grant or an unlock preparation.
internal sealed class DesktopBrowserPreference(string path)
{
    internal bool Enabled { get; private set; } = Read(path);
    private static bool Read(string path)
    {
        try
        {
            DesktopPresentation.SafePath(path);
            using var input = new FileStream(path, FileMode.Open, FileAccess.Read, FileShare.Read | FileShare.Delete);
            if (input.Length > 1024) return false;
            using var value = JsonDocument.Parse(input);
            return value.RootElement.GetProperty("schema").GetString() == "machine-control-browser-locked/v1" &&
                value.RootElement.GetProperty("enabled").GetBoolean();
        }
        catch (Exception ex) when (ex is IOException or UnauthorizedAccessException or JsonException or
            KeyNotFoundException or InvalidOperationException)
        { return false; }
    }
    internal void Set(bool enabled)
    {
        DesktopPresentation.SafePath(path);
        var directory = Path.GetDirectoryName(path)!;
        Directory.CreateDirectory(directory);
        var temporary = Path.Combine(directory, ".browser-locked-" + Guid.NewGuid().ToString("n"));
        try
        {
            using (var output = new FileStream(temporary, FileMode.CreateNew, FileAccess.Write, FileShare.None))
            {
                JsonSerializer.Serialize(output, new { schema = "machine-control-browser-locked/v1", enabled });
                output.Flush(true);
            }
            File.Move(temporary, path, overwrite: true);
            Enabled = enabled;
        }
        finally { File.Delete(temporary); }
    }
}
