using System.IO;
using System.Security.Cryptography;

namespace MachineControl.Windows;

internal static class CompanionBinaryIdentity
{
    internal static bool Matches(string installed, string bundled)
    {
        using var left = Open(installed);
        using var right = Open(bundled);
        return Matches(left, right);
    }
    private static FileStream Open(string path) => new(path, FileMode.Open, FileAccess.Read,
        FileShare.Read, 128 * 1024, FileOptions.SequentialScan);

    internal static bool Matches(Stream installed, Stream bundled)
    {
        // Updates commonly differ in size. Do not page two complete native
        // payloads in merely to establish an already-known mismatch.
        if (installed.Length != bundled.Length) return false;
        installed.Position = 0; bundled.Position = 0;
        return SHA256.HashData(installed).AsSpan().SequenceEqual(SHA256.HashData(bundled));
    }
}
