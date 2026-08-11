using System.IO;
using System.Text.Json;
using System.Text.Json.Serialization;

namespace MachineControl.Windows;

internal static class Contract
{
    public const string Schema = "machine-control/v0";

    public static readonly JsonSerializerOptions Json = new()
    {
        PropertyNamingPolicy = JsonNamingPolicy.CamelCase,
        DefaultIgnoreCondition = JsonIgnoreCondition.WhenWritingNull,
        WriteIndented = false,
    };

    public static Request ParseRequest(string text)
    {
        var request = JsonSerializer.Deserialize<Request>(text, Json)
            ?? throw new InvalidDataException("Request JSON was null");
        if (string.IsNullOrWhiteSpace(request.Operation))
        {
            throw new InvalidDataException("operation is required");
        }
        return request with
        {
            RequestId = string.IsNullOrWhiteSpace(request.RequestId)
                ? Guid.NewGuid().ToString("n")
                : request.RequestId,
        };
    }

    public static string Serialize(object value) =>
        JsonSerializer.Serialize(value, Json);

    public static Result ParseResult(string text) =>
        JsonSerializer.Deserialize<Result>(text, Json)
        ?? throw new InvalidDataException("Result JSON was null");
}

internal sealed record Request
{
    public string? RequestId { get; init; }
    public required string Operation { get; init; }
    public string? Scope { get; init; }
    public string? Target { get; init; }
    public string? ExecutablePath { get; init; }
    public string? ApplicationId { get; init; }
    public string? Arguments { get; init; }
    public string? Query { get; init; }
    public string? Reference { get; init; }
    public long? Hwnd { get; init; }
    public int? ProcessId { get; init; }
    public int? MaxDepth { get; init; }
    public int? MaxElements { get; init; }
    public string? Projection { get; init; }
    public string? KnownSnapshotDigest { get; init; }
    public int? TimeoutMs { get; init; }
    public int? X { get; init; }
    public int? Y { get; init; }
    public string? Key { get; init; }
    public string? Text { get; init; }
    public string? Button { get; init; }
    public string? State { get; init; }
    public string? CredentialKind { get; init; }
    public string? SecretPipe { get; init; }
    public string? ExpectedGeneration { get; init; }
    public bool AllowVisualFallback { get; init; }
}

internal sealed record Result
{
    public string Schema { get; init; } = Contract.Schema;
    public required string RequestId { get; init; }
    public required string Operation { get; init; }
    public bool Accepted { get; init; }
    public string? ActualRoute { get; init; }
    public uint? SessionId { get; init; }
    public string? Desktop { get; init; }
    public bool? SessionLocked { get; init; }
    public string? Generation { get; init; }
    public string? Delivery { get; init; }
    public string? Effect { get; init; }
    public string? Fidelity { get; init; }
    public string? CoordinateSpace { get; init; }
    public string? FocusConsequence { get; init; }
    public string? CursorConsequence { get; init; }
    public string HostInterference { get; init; } = "none";
    public string Uncertainty { get; init; } = "none";
    public string RetrySafety { get; init; } = "not_applicable";
    public ProviderAttempt[]? ProviderAttempts { get; init; }
    public bool FallbackUsed { get; init; }
    public long? ProviderLatencyMs { get; init; }
    public int AgentRoundTrips { get; init; } = 1;
    public int RetryCount { get; init; }
    public int StaleReferenceEvents { get; init; }
    public string? ErrorCode { get; init; }
    public string? Message { get; init; }
    public object? Evidence { get; init; }
    public object? Data { get; init; }
    public long ElapsedMs { get; init; }
}

internal sealed record ProviderAttempt(
    string Provider,
    string Outcome,
    string? Detail = null,
    long? ElapsedMs = null,
    string? Delivery = null,
    string? Effect = null);

internal sealed record ElementRecord(
    string Reference,
    int Depth,
    string ControlType,
    string Name,
    string AutomationId,
    bool Enabled,
    bool Offscreen,
    RectRecord Bounds,
    string[] Patterns,
    string? Value = null,
    bool? Selected = null);

internal sealed record CompactElementRecord(
    [property: JsonPropertyName("r")] string Reference,
    [property: JsonPropertyName("d")] int Depth,
    [property: JsonPropertyName("t")] string ControlType,
    [property: JsonPropertyName("n")] string Name,
    [property: JsonPropertyName("a")] string AutomationId,
    [property: JsonPropertyName("e")] bool Enabled,
    [property: JsonPropertyName("o")] bool Offscreen,
    [property: JsonPropertyName("b")] double[] Bounds,
    [property: JsonPropertyName("p")] string[] Patterns,
    [property: JsonPropertyName("v")] string? Value = null,
    [property: JsonPropertyName("s")] bool? Selected = null);

internal sealed record RectRecord(double X, double Y, double Width, double Height);

internal sealed record WindowRecord(
    long Hwnd,
    int ProcessId,
    string Title,
    string ClassName,
    bool Visible,
    bool Minimized,
    bool Maximized,
    RectRecord Bounds);
