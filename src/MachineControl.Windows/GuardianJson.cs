using System.IO;
using System.Text;

namespace MachineControl.Windows;

/// Buffered framing for private JSON-only guardian channels. Never use this
/// reader on credential channels: read-ahead could consume a secret frame.
internal sealed class GuardianJson(Stream stream)
{
    private const int Maximum = 16 * 1024;
    private readonly byte[] _buffer = new byte[4096];
    private int _offset, _count;

    internal async Task<string> ReadAsync(CancellationToken cancellation)
    {
        using var frame = new MemoryStream();
        while (true)
        {
            cancellation.ThrowIfCancellationRequested();
            if (_offset == _count)
            {
                _count = await stream.ReadAsync(_buffer, cancellation);
                _offset = 0;
                if (_count == 0) throw new EndOfStreamException("Guardian disconnected");
            }
            var newline = Array.IndexOf(_buffer, (byte)'\n', _offset, _count - _offset);
            var length = (newline < 0 ? _count : newline) - _offset;
            if (frame.Length + length > Maximum) throw new InvalidDataException("Guardian frame exceeds 16 KiB");
            frame.Write(_buffer, _offset, length);
            _offset += length;
            if (newline < 0) continue;
            ++_offset;
            return new UTF8Encoding(false, true).GetString(frame.GetBuffer(), 0, (int)frame.Length);
        }
    }
}
