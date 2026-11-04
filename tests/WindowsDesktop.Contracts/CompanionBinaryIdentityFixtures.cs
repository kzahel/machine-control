using System.IO;
using MachineControl.Windows;

internal static class CompanionBinaryIdentityFixtures
{
    internal static void Run()
    {
        using (var installed = new MetadataOnlyStream(10))
        using (var bundled = new MetadataOnlyStream(11))
            Require(!CompanionBinaryIdentity.Matches(installed, bundled),
                "Different-size companions must be rejected without reading either image");
        var root = Path.Combine(Path.GetTempPath(), "mc-companion-" + Guid.NewGuid().ToString("n"));
        Directory.CreateDirectory(root);
        try
        {
            var left = Path.Combine(root, "installed.bin");
            var right = Path.Combine(root, "bundled.bin");
            var bytes = Enumerable.Range(0, 512 * 1024).Select(value => (byte)(value % 251)).ToArray();
            File.WriteAllBytes(left, bytes); File.WriteAllBytes(right, bytes);
            Require(CompanionBinaryIdentity.Matches(left, right), "Identical complete companions match");
            bytes[^1] ^= 1; File.WriteAllBytes(right, bytes);
            Require(!CompanionBinaryIdentity.Matches(left, right), "Same-size companions require complete content equality");
            File.WriteAllBytes(right, bytes[..^1]);
            Require(!CompanionBinaryIdentity.Matches(left, right), "Truncated companions never match");
        }
        finally { Directory.Delete(root, recursive: true); }
        Console.WriteLine("Companion binary identity and cheap mismatch contracts passed");
    }
    private static void Require(bool value, string message) { if (!value) throw new Exception(message); }
    private sealed class MetadataOnlyStream(long length) : Stream
    {
        public override bool CanRead => true;
        public override bool CanSeek => true;
        public override bool CanWrite => false;
        public override long Length => length;
        public override long Position { get; set; }
        public override int Read(byte[] buffer, int offset, int count) => throw new IOException("Unexpected image read");
        public override int Read(Span<byte> buffer) => throw new IOException("Unexpected image read");
        public override void Flush() { }
        public override long Seek(long offset, SeekOrigin origin) => throw new NotSupportedException();
        public override void SetLength(long value) => throw new NotSupportedException();
        public override void Write(byte[] buffer, int offset, int count) => throw new NotSupportedException();
    }
}
