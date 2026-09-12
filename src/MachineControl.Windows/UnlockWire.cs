using System.IO;
using System.Security.Cryptography;
using System.Text;

namespace MachineControl.Windows;

internal static class UnlockWire
{
    public static async Task<byte[]> ReadSecretAsync(Stream stream, CancellationToken cancellationToken)
    {
        var header = new byte[2];
        await stream.ReadExactlyAsync(header, cancellationToken);
        var length = header[0] | (header[1] << 8);
        if (length is < 1 or > 256) throw new InvalidDataException("Invalid credential length");
        var secret = new byte[length];
        try { await stream.ReadExactlyAsync(secret, cancellationToken); return secret; }
        catch { CryptographicOperations.ZeroMemory(secret); throw; }
    }

    public static async Task WriteSecretAsync(Stream stream, byte[] secret, CancellationToken cancellationToken)
    {
        if (secret.Length is < 1 or > 256) throw new InvalidDataException("Invalid credential length");
        await stream.WriteAsync(new byte[] { (byte)secret.Length, (byte)(secret.Length >> 8) }, cancellationToken);
        await stream.WriteAsync(secret, cancellationToken);
        await stream.FlushAsync(cancellationToken);
    }

    // Read exactly through the newline; never buffer ahead into a secret frame.
    public static async Task<string> ReadLineAsync(Stream stream, CancellationToken cancellationToken)
    {
        var bytes = new List<byte>();
        var buffer = new byte[1];
        while (await stream.ReadAsync(buffer, cancellationToken) != 0)
        {
            if (buffer[0] == '\n') return new UTF8Encoding(false, true).GetString(bytes.ToArray());
            if (bytes.Count >= 16 * 1024) throw new InvalidDataException("Frame exceeds 16 KiB");
            bytes.Add(buffer[0]);
        }
        throw new EndOfStreamException("Peer disconnected");
    }

    public static async Task WriteAsync(Stream stream, object value, CancellationToken cancellationToken)
    {
        var bytes = Encoding.UTF8.GetBytes(Contract.Serialize(value) + "\n");
        await stream.WriteAsync(bytes, cancellationToken);
        await stream.FlushAsync(cancellationToken);
    }
}
