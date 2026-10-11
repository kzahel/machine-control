using System.IO;
using System.Security.AccessControl;
using System.Security.Principal;
using System.Text.Json;

namespace MachineControl.Windows;

/// Presentation has no authorization or provider-routing responsibility.
internal sealed class DesktopPresentation(string path, string? temporary = null)
{
    internal const string Schema = "machine-control-presentation/v1";
    internal static readonly string[] Profiles = ["personal", "minimal", "appliance"];
    private readonly object _gate = new();
    private string? _override = temporary is null ? null : Validate(temporary);
    internal static string Validate(string profile) => Profiles.Contains(profile, StringComparer.Ordinal)
        ? profile : throw new ArgumentException("Presentation must be personal, minimal or appliance");

    internal object Status()
    {
        lock (_gate)
        {
            var (saved, diagnostic) = Read();
            return new
            {
                schema = Schema,
                profile = _override ?? saved,
                savedProfile = saved,
                temporaryOverride = _override is not null,
                setting = false,
                diagnostic
            };
        }
    }

    private static void SafePath(string location)
    {
        for (var current = System.IO.Path.GetFullPath(location); current is not null; current = System.IO.Path.GetDirectoryName(current))
            if ((File.Exists(current) || Directory.Exists(current)) && (File.GetAttributes(current) & FileAttributes.ReparsePoint) != 0)
                throw new IOException("Presentation path contains a redirect");
    }
    private (string Profile, string? Diagnostic) Read()
    {
        try
        {
            SafePath(path);
            if (!File.Exists(path)) return ("personal", null);
            using var input = new FileStream(path, FileMode.Open, FileAccess.Read, FileShare.Read | FileShare.Delete);
            if (input.Length > 4096) throw new IOException("Presentation preference exceeds bounds");
            using var document = JsonDocument.Parse(input);
            var root = document.RootElement;
            if (root.GetProperty("schema").GetString() != Schema) throw new ArgumentException("Unsupported presentation schema");
            return (Validate(root.GetProperty("profile").GetString() ?? ""), null);
        }
        catch (Exception ex) when (ex is IOException or UnauthorizedAccessException or JsonException or
            ArgumentException or KeyNotFoundException or InvalidOperationException)
        { return ("personal", "presentation_preference_invalid"); }
    }
    internal object Set(string profile)
    {
        Validate(profile);
        lock (_gate)
        {
            SafePath(path);
            var directory = System.IO.Path.GetDirectoryName(path)!;
            Directory.CreateDirectory(directory);
            if (OperatingSystem.IsWindows())
            {
                var acl = new DirectorySecurity();
                acl.SetAccessRuleProtection(true, false);
                acl.AddAccessRule(new FileSystemAccessRule(WindowsIdentity.GetCurrent().User!, FileSystemRights.FullControl,
                    InheritanceFlags.ContainerInherit | InheritanceFlags.ObjectInherit, PropagationFlags.None, AccessControlType.Allow));
                new DirectoryInfo(directory).SetAccessControl(acl);
            }
            else File.SetUnixFileMode(directory, UnixFileMode.UserRead | UnixFileMode.UserWrite | UnixFileMode.UserExecute);
            // Cross-process edits either own the lock or refuse immediately.
            var lockPath = System.IO.Path.Combine(directory, "write.lock");
            SafePath(lockPath);
            using var exclusion = new FileStream(lockPath,
                FileMode.OpenOrCreate, FileAccess.ReadWrite, FileShare.None);
            var pending = System.IO.Path.Combine(directory, ".presentation-" + Guid.NewGuid().ToString("n"));
            try
            {
                using (var output = new FileStream(pending, FileMode.CreateNew, FileAccess.Write, FileShare.None))
                {
                    JsonSerializer.Serialize(output, new { schema = Schema, profile });
                    output.Flush(true);
                }
                SafePath(path);
                File.Move(pending, path, overwrite: true);
                _override = null;
            }
            finally { File.Delete(pending); }
            return Status();
        }
    }
}
