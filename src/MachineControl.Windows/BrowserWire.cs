using System.Buffers.Binary;
using System.IO;
using System.Text.Json.Nodes;

namespace MachineControl.Windows;

internal static class BrowserWire
{
    internal const string Origin = "chrome-extension://ncbfifkjllmnkkjmomjohinigfgdocjc/";
    internal const string Host = "org.machine_control.browser";
    internal const int MaximumInput = 16 * 1024 * 1024;
    internal const int MaximumOutput = 1024 * 1024;
    internal static readonly string[] Operations =
    [
        "browser.tabs", "browser.wait", "browser.navigate", "browser.snapshot",
        "browser.click", "browser.type", "browser.key", "browser.capture",
        "browser.upload", "browser.cdp", "browser.eval", "browser.release",
    ];
    internal static bool Observes(string operation) => operation is
        "browser.tabs" or "browser.wait" or "browser.snapshot" or "browser.capture";

    internal static async Task<JsonObject?> ReadAsync(Stream stream, CancellationToken cancellation)
    {
        var header = new byte[4];
        if (await stream.ReadAsync(header.AsMemory(0, 1), cancellation) == 0) return null;
        await stream.ReadExactlyAsync(header.AsMemory(1), cancellation);
        var size = BinaryPrimitives.ReadUInt32LittleEndian(header);
        if (size is 0 or > MaximumInput) throw new InvalidDataException("Invalid browser frame length");
        var body = new byte[(int)size];
        await stream.ReadExactlyAsync(body, cancellation);
        return JsonNode.Parse(body)?.AsObject() ?? throw new InvalidDataException("Browser object required");
    }

    internal static async Task WriteAsync(Stream stream, JsonObject value, CancellationToken cancellation)
    {
        var body = System.Text.Json.JsonSerializer.SerializeToUtf8Bytes(value, Contract.Json);
        if (body.Length > MaximumOutput) throw new InvalidDataException("Browser response exceeds native messaging limit");
        var header = new byte[4];
        BinaryPrimitives.WriteUInt32LittleEndian(header, (uint)body.Length);
        await stream.WriteAsync(header, cancellation);
        await stream.WriteAsync(body, cancellation);
        await stream.FlushAsync(cancellation);
    }
}
