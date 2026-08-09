namespace MachineControl.Windows;

internal sealed record ProviderDescriptor(
    string Id,
    string Availability,
    string[] Operations,
    string Fidelity,
    string? Detail = null);

internal interface IControlProvider
{
    ProviderDescriptor Describe();

    Task<Result> ExecuteAsync(
        Request request,
        string generation,
        CancellationToken cancellationToken);
}

internal sealed class WindowsNativeProvider : IControlProvider
{
    public ProviderDescriptor Describe() => new(
        "windows-native",
        "active",
        [
            "capabilities", "status", "windows", "snapshot", "screenshot",
            "invoke", "click", "key", "type", "window.state",
            "session.lock", "session.login",
        ],
        "Win32, UI Automation, input-desktop GDI, and SendInput");

    public Task<Result> ExecuteAsync(
        Request request,
        string generation,
        CancellationToken cancellationToken) =>
        DesktopController.ExecuteAsync(
            request,
            generation,
            cancellationToken);
}

internal static class ProviderRouter
{
    private static readonly IControlProvider Native =
        new WindowsNativeProvider();

    public static ProviderDescriptor[] Describe() =>
    [
        Native.Describe(),
        new ProviderDescriptor(
            "cua",
            "optional_not_connected",
            ["snapshot", "screenshot", "invoke", "click", "key"],
            "provider-defined",
            "Not bundled; the owned facade remains usable without Cua"),
        new ProviderDescriptor(
            "winapp",
            "external_baseline_not_connected",
            ["windows", "snapshot", "screenshot", "invoke"],
            "UI Automation and window capture",
            "Used by the testbed comparison relay, not by this service"),
    ];

    public static Task<Result> ExecuteAsync(
        Request request,
        string generation,
        CancellationToken cancellationToken) =>
        Native.ExecuteAsync(request, generation, cancellationToken);
}
