using System.Buffers.Binary;
using System.IO;
using System.Text.Json.Nodes;

namespace MachineControl.Windows;

internal static class BrowserWire
{
    internal const string Route = "chrome.extension/cdp";
    // The fixed development key gives unpacked copies Origin; the Chrome Web
    // Store signs its release with its own key and ID.
    internal const string Origin = "chrome-extension://ncbfifkjllmnkkjmomjohinigfgdocjc/";
    internal const string StoreOrigin = "chrome-extension://epejchbeajneooefnklikkfhbaeadkpc/";
    internal static readonly string[] Origins = [Origin, StoreOrigin];
    internal static bool Allowed(string? origin) => origin is not null && Origins.Contains(origin);
    internal const string Host = "org.machine_control.browser";
    internal const int MaximumInput = 16 * 1024 * 1024;
    internal const int MaximumOutput = 1024 * 1024;
    internal static readonly string[] Operations =
    [
        "browser.profiles", "browser.tabs", "browser.wait", "browser.navigate", "browser.snapshot",
        "browser.click", "browser.type", "browser.key", "browser.capture",
        "browser.upload", "browser.cdp", "browser.eval", "browser.release", "browser.endpoint", "browser.dialog",
    ];
    internal static bool Observes(string operation) => operation is
        "browser.tabs" or "browser.wait" or "browser.snapshot" or "browser.capture";

    // Provider messages may contain page data. Only closed diagnostic codes
    // from our stream lifecycle can enter operator metadata.
    internal static string? StreamEnd(JsonObject frame)
    {
        var type = frame["type"] is JsonValue kind && kind.TryGetValue<string>(out var text) ? text : null;
        if (type == "session.failed") return "provider_session_failed";
        if (type != "session.closed") return null;
        var reason = frame["reason"] is JsonValue value && value.TryGetValue<string>(out var code) ? code : null;
        return reason is "closed" or "tab_closed" or "detached" or "access_ended" or "devtools_grant_ended" or
            "browser_management_timeout_effect_unknown" or "target_discovery_failed" or "attached_session_capacity" or "native_debugger_detached"
            ? reason : "provider_closed";
    }

    // Process anonymous pipes are synchronous handles on Windows. Their
    // owners call these on dedicated I/O threads, never pool workers.
    internal static JsonObject? Read(Stream stream, int maximum = MaximumInput)
    {
        var header = new byte[4];
        if (stream.Read(header, 0, 1) == 0) return null;
        stream.ReadExactly(header.AsSpan(1));
        var size = BinaryPrimitives.ReadUInt32LittleEndian(header);
        if (size == 0 || size > maximum) throw new InvalidDataException("Invalid browser frame length");
        var body = new byte[(int)size];
        stream.ReadExactly(body);
        return JsonNode.Parse(body)?.AsObject() ?? throw new InvalidDataException("Browser object required");
    }

    internal static void Write(Stream stream, JsonObject value, int maximum = MaximumOutput)
    {
        var body = System.Text.Json.JsonSerializer.SerializeToUtf8Bytes(value, Contract.Json);
        if (body.Length > maximum) throw new InvalidDataException("Browser response exceeds native messaging limit");
        var header = new byte[4];
        BinaryPrimitives.WriteUInt32LittleEndian(header, (uint)body.Length);
        stream.Write(header);
        stream.Write(body);
        stream.Flush();
    }

    internal static async Task<JsonObject?> ReadAsync(Stream stream, CancellationToken cancellation, int maximum = MaximumInput)
    {
        var header = new byte[4];
        if (await stream.ReadAsync(header.AsMemory(0, 1), cancellation).ConfigureAwait(false) == 0) return null;
        await stream.ReadExactlyAsync(header.AsMemory(1), cancellation).ConfigureAwait(false);
        var size = BinaryPrimitives.ReadUInt32LittleEndian(header);
        if (size == 0 || size > maximum) throw new InvalidDataException("Invalid browser frame length");
        var body = new byte[(int)size];
        await stream.ReadExactlyAsync(body, cancellation).ConfigureAwait(false);
        return JsonNode.Parse(body)?.AsObject() ?? throw new InvalidDataException("Browser object required");
    }

    internal static async Task WriteAsync(Stream stream, JsonObject value, CancellationToken cancellation, int maximum = MaximumOutput)
    {
        var body = System.Text.Json.JsonSerializer.SerializeToUtf8Bytes(value, Contract.Json);
        if (body.Length > maximum) throw new InvalidDataException("Browser response exceeds native messaging limit");
        var header = new byte[4];
        BinaryPrimitives.WriteUInt32LittleEndian(header, (uint)body.Length);
        await stream.WriteAsync(header, cancellation).ConfigureAwait(false);
        await stream.WriteAsync(body, cancellation).ConfigureAwait(false);
        await stream.FlushAsync(cancellation).ConfigureAwait(false);
    }
}
