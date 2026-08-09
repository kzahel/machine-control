using System.Security.Cryptography;
using System.Text;

namespace MachineControl.Windows;

internal sealed record SnapshotProjectionResult(
    string Projection,
    string SnapshotDigest,
    bool Unchanged,
    object? Elements,
    int ContentBytes,
    int ContentEstimatedTokens);

internal static class SnapshotProjection
{
    public static bool IsSupported(string? projection) =>
        string.IsNullOrWhiteSpace(projection) ||
        string.Equals(projection, "full", StringComparison.OrdinalIgnoreCase) ||
        string.Equals(projection, "compact", StringComparison.OrdinalIgnoreCase);

    public static SnapshotProjectionResult Create(
        IReadOnlyList<ElementRecord> records,
        Request request)
    {
        var projection = string.Equals(
                request.Projection,
                "compact",
                StringComparison.OrdinalIgnoreCase)
            ? "compact"
            : "full";
        object content = projection == "compact"
            ? records.Select(ToCompact).ToArray()
            : records;
        var serialized = Contract.Serialize(content);
        var bytes = Encoding.UTF8.GetByteCount(serialized);
        object digestContent = projection == "compact"
            ? records.Select(element => ToCompact(element) with
                { Reference = string.Empty }).ToArray()
            : records.Select(element => element with
                { Reference = string.Empty }).ToArray();
        var digestSerialized = projection + "\n" +
            Contract.Serialize(digestContent);
        var digest = "sha256:" + Convert.ToHexString(
                SHA256.HashData(Encoding.UTF8.GetBytes(digestSerialized)))
            .ToLowerInvariant();
        var unchanged = string.Equals(
            request.KnownSnapshotDigest,
            digest,
            StringComparison.OrdinalIgnoreCase);
        return new SnapshotProjectionResult(
            projection,
            digest,
            unchanged,
            unchanged ? null : content,
            bytes,
            Math.Max(1, bytes / 4));
    }

    private static CompactElementRecord ToCompact(ElementRecord element) =>
        new(
            element.Reference,
            element.Depth,
            element.ControlType,
            element.Name,
            element.AutomationId,
            element.Enabled,
            element.Offscreen,
            [
                element.Bounds.X,
                element.Bounds.Y,
                element.Bounds.Width,
                element.Bounds.Height,
            ],
            element.Patterns,
            element.Value,
            element.Selected);
}
