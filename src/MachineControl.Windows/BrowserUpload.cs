using System.IO;

namespace MachineControl.Windows;

/// Browser-only uploads name existing target-local files. Refuse network/device
/// paths, streams, links and private/hidden storage before Chrome sees a path.
/// Chrome opens these paths itself; validation is not same-user containment or
/// a guarantee against concurrent replacement by another local process.
internal static class BrowserUpload
{
    internal const int MaximumFiles = 20;
    internal sealed record Validation(string[]? Files = null, string? ErrorCode = null);

    internal static Validation Validate(string[]? files)
    {
        if (files is null || files.Length is < 1 or > MaximumFiles)
            return new(ErrorCode: "invalid_request");
        var normalized = new List<string>();
        foreach (var file in files)
        {
            // A local drive-qualified Windows path only. In particular, do not
            // touch a UNC server or allow alternate streams/device namespaces.
            if (string.IsNullOrWhiteSpace(file) || file.Length < 3 ||
                !char.IsAsciiLetter(file[0]) || file[1] != ':' ||
                file[2] is not ('\\' or '/') || file.AsSpan(2).Contains(':'))
                return new(ErrorCode: "invalid_request");
            try
            {
                var path = Path.GetFullPath(file);
                var root = Path.GetPathRoot(path)!;
                if (new DriveInfo(root).DriveType == DriveType.Network)
                    return new(ErrorCode: "upload_path_not_permitted");
                var parts = path[root.Length..].Split(Path.DirectorySeparatorChar);
                if (parts.Any(part => part.StartsWith('.') ||
                    part.Equals("AppData", StringComparison.OrdinalIgnoreCase)))
                    return new(ErrorCode: "upload_path_not_permitted");
                var current = root;
                for (var i = 0; i < parts.Length; i++)
                {
                    current = Path.Combine(current, parts[i]);
                    var attributes = File.GetAttributes(current);
                    if ((attributes & (FileAttributes.ReparsePoint | FileAttributes.Hidden | FileAttributes.System)) != 0)
                        return new(ErrorCode: "upload_path_not_permitted");
                    if (i == parts.Length - 1 && (attributes & FileAttributes.Directory) != 0)
                        return new(ErrorCode: "upload_file_unavailable");
                }
                // Test ordinary-user readability without reading file content.
                using var readable = File.Open(path, FileMode.Open, FileAccess.Read, FileShare.ReadWrite | FileShare.Delete);
                normalized.Add(path);
            }
            catch (Exception ex) when (ex is IOException or UnauthorizedAccessException or ArgumentException or NotSupportedException)
            {
                return new(ErrorCode: "upload_file_unavailable");
            }
        }
        return new(Files: normalized.ToArray());
    }
}
