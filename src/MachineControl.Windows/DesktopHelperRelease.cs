using System.IO;
using System.IO.Compression;
using System.Runtime.InteropServices;
using System.Security.Cryptography;
using System.Text.Json;
using System.Text.RegularExpressions;

namespace MachineControl.Windows;

internal sealed record DesktopHelperRelease(string Schema, string Version, string Runtime, Dictionary<string, string> Files)
{
    internal const string Manifest = "helper-release.json";
    internal const string Signature = Manifest + ".sig";
    internal const string Catalog = "package.cat";
    internal const string Image = "machine-control-windows.exe";
    internal const int MaximumFiles = 1000;
    internal const long MaximumBytes = 512L * 1024 * 1024;
    private static readonly Regex FileName = new(@"\A[A-Za-z0-9_@.-]+(?:/[A-Za-z0-9_@.-]+)*\z");
    private static readonly Regex ReleaseVersion = new(@"\A(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\z");
    private static readonly Regex Sha256 = new(@"\A[a-f0-9]{64}\z");

    internal static string InDirectory(string directory, string name)
    {
        if (!FileName.IsMatch(name) || name.Split('/').Any(part =>
            part.EndsWith('.') || part is "." or ".." ||
            Regex.IsMatch(part.Split('.')[0], @"\A(?:CON|PRN|AUX|NUL|COM[0-9]|LPT[0-9])\z", RegexOptions.IgnoreCase)))
            throw new InvalidDataException("Invalid helper release path");
        return Path.Combine(directory, name.Replace('/', Path.DirectorySeparatorChar));
    }

    internal static Version ParseVersion(string version) =>
        ReleaseVersion.IsMatch(version) && System.Version.TryParse(version, out var result)
            ? result : throw new InvalidDataException("Invalid helper release version");

    internal static bool MatchesInstalled(string installed, string bundled)
    {
        var manifest = Path.Combine(Path.GetDirectoryName(bundled)!, Manifest);
        var previous = Path.Combine(Path.GetDirectoryName(installed)!, Manifest);
        if (File.Exists(manifest) != File.Exists(previous)) return false;
        return (!File.Exists(manifest) || CompanionBinaryIdentity.Matches(previous, manifest)) &&
            CompanionBinaryIdentity.Matches(installed, bundled);
    }

    internal static Version? VersionOf(string image)
    {
        try
        {
            var path = Path.Combine(Path.GetDirectoryName(image)!, Manifest);
            if (new FileInfo(path).Length > 256 * 1024) return null;
            var release = JsonSerializer.Deserialize<DesktopHelperRelease>(File.ReadAllBytes(path), Contract.Json);
            return release?.Version is { } version ? ParseVersion(version) : null;
        }
        catch (Exception error) when (DesktopHelperUpdate.IsMaintenanceError(error)) { return null; }
    }

    internal static string[] FilesIn(string directory)
    {
        var files = new List<string>();
        var directories = new Queue<string>();
        directories.Enqueue(directory);
        while (directories.TryDequeue(out var current))
        {
            foreach (var path in Directory.EnumerateFileSystemEntries(current))
            {
                var attributes = File.GetAttributes(path);
                if ((attributes & FileAttributes.ReparsePoint) != 0)
                    throw new InvalidDataException("Helper release contains a reparse point");
                if ((attributes & FileAttributes.Directory) != 0) directories.Enqueue(path);
                else files.Add(path);
                if (files.Count + directories.Count > MaximumFiles)
                    throw new InvalidDataException("Too many helper release entries");
            }
        }
        return files.ToArray();
    }

    internal static void Extract(string archive, string destination)
    {
        using var zip = ZipFile.OpenRead(archive);
        if (zip.Entries.Count > MaximumFiles || zip.Entries.Sum(entry => entry.Length) > MaximumBytes)
            throw new InvalidDataException("Helper release is too large");
        foreach (var entry in zip.Entries)
        {
            var path = InDirectory(destination, entry.FullName);
            Directory.CreateDirectory(Path.GetDirectoryName(path)!);
            using var source = entry.Open();
            using var output = new FileStream(path, FileMode.CreateNew, FileAccess.Write);
            CopyExactly(source, output, entry.Length);
            if (source.ReadByte() != -1) throw new InvalidDataException("Helper entry length mismatch");
        }
    }

    internal static void CopyExactly(Stream input, Stream output, long remaining)
    {
        var buffer = new byte[128 * 1024];
        while (remaining > 0)
        {
            var count = input.Read(buffer, 0, (int)Math.Min(remaining, buffer.Length));
            if (count == 0) throw new EndOfStreamException("Incomplete helper payload");
            output.Write(buffer, 0, count);
            remaining -= count;
        }
    }

    internal static DesktopHelperRelease Verify(string directory, bool protectedDirectory = true)
    {
        if (protectedDirectory) UnlockAdmin.RequireProtectedPath(directory, DesktopUacNative.Root);
        var names = FilesIn(directory).Where(name => !name.Equals(
            Path.Combine(directory, Catalog), StringComparison.OrdinalIgnoreCase)).ToArray();
        var manifestPath = Path.Combine(directory, Manifest);
        var signaturePath = Path.Combine(directory, Signature);
        if (new FileInfo(manifestPath).Length > 256 * 1024 || new FileInfo(signaturePath).Length > 4096)
            throw new InvalidDataException("Helper manifest or signature is too large");
        var manifest = File.ReadAllBytes(manifestPath);
        DesktopHelperSignature.Verify(manifest, DesktopHelperSignature.PublicKey(), File.ReadAllText(signaturePath));
        var release = JsonSerializer.Deserialize<DesktopHelperRelease>(manifest, Contract.Json)
            ?? throw new InvalidDataException("Missing helper manifest");
        var runtime = RuntimeInformation.ProcessArchitecture switch
        {
            Architecture.X64 => "win-x64",
            Architecture.Arm64 => "win-arm64",
            _ => throw new InvalidDataException("Unsupported helper architecture"),
        };
        if (release.Schema != "machine-control-desktop-helper-release/v1" || release.Runtime != runtime ||
            release.Files is null || release.Files.Count + 2 != names.Length ||
            !release.Files.ContainsKey(Image))
            throw new InvalidDataException("Wrong helper release identity or file set");
        _ = ParseVersion(release.Version);
        var seen = new HashSet<string>(StringComparer.OrdinalIgnoreCase) { Manifest, Signature, Catalog };
        foreach (var (name, expected) in release.Files)
        {
            if (!seen.Add(name) || !Sha256.IsMatch(expected))
                throw new InvalidDataException("Invalid helper release file inventory");
            using var file = File.OpenRead(InDirectory(directory, name));
            if (!Convert.ToHexString(SHA256.HashData(file)).Equals(expected, StringComparison.OrdinalIgnoreCase))
                throw new InvalidDataException("Helper release file hash mismatch");
        }
        return release;
    }
}
