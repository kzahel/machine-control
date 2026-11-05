using System.IO;
using System.Text.Json;
using System.Text.Json.Nodes;

namespace MachineControl.Windows;

/// Operator form preferences only. Loading this file cannot grant access.
internal sealed class DesktopAccessPreferences(string path)
{
    internal JsonObject? Read()
    {
        try
        {
            DesktopPresentation.SafePath(path);
            using var input = new FileStream(path, FileMode.Open, FileAccess.Read, FileShare.Read | FileShare.Delete);
            if (input.Length > 2048) return null;
            var value = JsonNode.Parse(input)?.AsObject();
            return value?["schema"]?.GetValue<string>() == "machine-control-access-preferences/v1"
                ? value["preferences"]?.AsObject() : null;
        }
        catch (Exception ex) when (ex is IOException or UnauthorizedAccessException or JsonException or InvalidOperationException)
        { return null; }
    }
    internal void Set(JsonObject preferences)
    {
        DesktopPresentation.SafePath(path);
        var directory = Path.GetDirectoryName(path)!;
        Directory.CreateDirectory(directory);
        var temporary = Path.Combine(directory, ".access-preferences-" + Guid.NewGuid().ToString("n"));
        try
        {
            using (var output = new FileStream(temporary, FileMode.CreateNew, FileAccess.Write, FileShare.None))
            {
                JsonSerializer.Serialize(output, new { schema = "machine-control-access-preferences/v1", preferences });
                output.Flush(true);
            }
            File.Move(temporary, path, overwrite: true);
        }
        finally { File.Delete(temporary); }
    }
}
