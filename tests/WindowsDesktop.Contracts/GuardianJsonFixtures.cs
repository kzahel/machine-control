using System.Text;
using MachineControl.Windows;

internal static class GuardianJsonFixtures
{
    internal static async Task RunAsync()
    {
        static void Check(bool value, string message) { if (!value) throw new Exception(message); }
        var first = "{\"physicalTakeover\":false,\"complete\":false,\"attemptStarted\":true,\"guardianPid\":1234}";
        using var stream = new Reads(Encoding.UTF8.GetBytes(first + "\n{\"allowed\":true}\n"));
        var reader = new GuardianJson(stream);
        Check(await reader.ReadAsync(default) == first, "Exact private callback frame");
        Check(stream.Calls == 1, "One underlying asynchronous read, not one per callback byte");
        Check(await reader.ReadAsync(default) == "{\"allowed\":true}" && stream.Calls == 1,
            "Persistent guardian keeps queued JSON frames without losing their boundary");
        try { await reader.ReadAsync(default); throw new Exception("Expected closed guardian"); }
        catch (EndOfStreamException) { }
        foreach (var bytes in new[] { Encoding.UTF8.GetBytes(new string('x', 16385) + "\n"), new byte[] { 0xff, 10 } })
        {
            using var invalid = new MemoryStream(bytes);
            try { await new GuardianJson(invalid).ReadAsync(default); throw new Exception("Expected invalid guardian frame"); }
            catch (InvalidDataException) { }
            catch (DecoderFallbackException) { }
        }
        using var partial = new Reads(Encoding.UTF8.GetBytes(first + "\n"), 3);
        Check(await new GuardianJson(partial).ReadAsync(default) == first, "Partial pipe reads preserve complete JSON");
        using var cancelled = new CancellationTokenSource();
        cancelled.Cancel();
        using var input = new MemoryStream([10]);
        try { await new GuardianJson(input).ReadAsync(cancelled.Token); throw new Exception("Expected cancellation"); }
        catch (OperationCanceledException) { }
        Console.WriteLine("Buffered private guardian JSON contracts passed");
    }

    private sealed class Reads(byte[] data, int chunk = int.MaxValue) : MemoryStream(data)
    {
        internal int Calls;
        public override ValueTask<int> ReadAsync(Memory<byte> buffer, CancellationToken cancellationToken = default)
        {
            ++Calls;
            return base.ReadAsync(buffer[..Math.Min(buffer.Length, chunk)], cancellationToken);
        }
    }
}
