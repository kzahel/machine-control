namespace MachineControl.Windows;

internal sealed record ProviderDescriptor(
    string Id,
    string State,
    string RouteClass,
    string ProcessPlacement,
    string Privilege,
    string SessionRequirement,
    ProviderOperationDescriptor[] Operations,
    string[] KnownOmissions,
    string? Version = null,
    string? SourceRevision = null,
    string? Detail = null);

internal sealed record ProviderOperationDescriptor(
    string Operation,
    string State,
    string Plane,
    string[] Desktops,
    string Fidelity,
    string Delivery,
    string EffectObservation,
    string HostInterference);

internal sealed record RoutePlan(
    string Operation,
    string Condition,
    string[] Providers,
    string FailurePolicy);

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
        "native",
        "guest.user_or_protected",
        "resident session helper or disposable protected worker",
        "Medium on Default; LocalSystem only on an authorized protected desktop",
        "active interactive console session",
        [
            Semantic("capabilities", "system", "machine-readable inventory"),
            Semantic("status", "session", "native state observation"),
            Semantic("windows", "desktop", "exact HWND inventory"),
            Semantic("snapshot", "desktop", "UI Automation"),
            Capture("screenshot", "input-desktop or exact-HWND pixels"),
            Semantic("invoke", "desktop", "UIA pattern; authorized input fallback"),
            Input("click", "coordinate input"),
            Input("key", "keyboard input"),
            Input("type", "Unicode keyboard input"),
            Semantic("window.state", "desktop", "Win32 state plus readback"),
            Semantic("session.lock", "session", "Win32 plus WTS readback"),
            Semantic("session.login", "protected", "stock Credential Provider"),
        ],
        [],
        Detail: "Win32, UI Automation, input-desktop GDI, and SendInput");

    public Task<Result> ExecuteAsync(
        Request request,
        string generation,
        CancellationToken cancellationToken) =>
        DesktopController.ExecuteAsync(
            request,
            generation,
            cancellationToken);

    private static ProviderOperationDescriptor Semantic(
        string operation,
        string plane,
        string fidelity) => new(
            operation,
            "native",
            plane,
            ["Default", "Winlogon", "Consent"],
            fidelity,
            "semantic_or_system_api",
            "independent readback where the operation defines an oracle",
            "none unless an explicit input fallback is used");

    private static ProviderOperationDescriptor Capture(
        string operation,
        string fidelity) => new(
            operation,
            "native",
            "desktop",
            ["Default", "Winlogon", "Consent"],
            fidelity,
            "observation",
            "artifact hash and bounds",
            "none");

    private static ProviderOperationDescriptor Input(
        string operation,
        string fidelity) => new(
            operation,
            "native",
            "desktop",
            ["Default", "Winlogon", "Consent"],
            fidelity,
            "guest-local SendInput",
            "unverifiable without a caller-supplied postcondition",
            "may change target focus or cursor; never host input");
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
            "not_yet_integrated",
            "guest.user",
            "planned child of the Medium interactive-session helper",
            "Medium",
            "unlocked Default desktop",
            [
                new ProviderOperationDescriptor(
                    "snapshot",
                    "not_yet_integrated",
                    "desktop",
                    ["Default"],
                    "compact exact-window UIA",
                    "observation",
                    "provider snapshot only",
                    "none"),
                new ProviderOperationDescriptor(
                    "screenshot",
                    "not_yet_integrated",
                    "desktop",
                    ["Default"],
                    "ordinary exact-window capture",
                    "observation",
                    "artifact hash and bounds",
                    "none"),
                new ProviderOperationDescriptor(
                    "invoke",
                    "not_yet_integrated",
                    "desktop",
                    ["Default"],
                    "snapshot-bound background semantic action",
                    "background-first",
                    "provider report; caller verifies fixture effect",
                    "none expected"),
            ],
            [
                "taskbar and selected shell HWND discovery",
                "packaged Settings inner/outer resolution",
                "protected and cross-integrity desktops",
                "selected window-state operations",
            ],
            Version: "0.17.0",
            SourceRevision: "d21e3447f9b08c761c090946648d5aca5e6c9cf1",
            Detail: "Pinned adapter connection is the next implementation slice"),
        new ProviderDescriptor(
            "winapp",
            "external_comparison",
            "guest.user",
            "authoritative testbed interactive-session relay",
            "Medium",
            "unlocked Default desktop",
            [
                new ProviderOperationDescriptor(
                    "windows",
                    "external_comparison",
                    "desktop",
                    ["Default"],
                    "exact HWND and shell discovery",
                    "observation",
                    "native window state",
                    "none"),
                new ProviderOperationDescriptor(
                    "snapshot",
                    "external_comparison",
                    "desktop",
                    ["Default"],
                    "UI Automation",
                    "semantic",
                    "provider acknowledgement requires independent effect",
                    "none"),
                new ProviderOperationDescriptor(
                    "screenshot",
                    "external_comparison",
                    "desktop",
                    ["Default"],
                    "exact HWND or foreground screen capture",
                    "observation",
                    "artifact dimensions",
                    "route-dependent"),
            ],
            ["protected and cross-integrity desktops", "common session/result contract"],
            Detail: "Comparison route only until a measured operation justifies adoption"),
    ];

    public static RoutePlan[] RoutingTable() =>
    [
        new RoutePlan(
            "capabilities,status,windows",
            "all current desktop states",
            ["windows-native"],
            "terminal structured refusal"),
        new RoutePlan(
            "snapshot,screenshot,invoke",
            "ordinary exact application window",
            ["cua", "windows-native"],
            "Cua is not connected yet; safe observation fallback only"),
        new RoutePlan(
            "snapshot,invoke,window.state",
            "taskbar, shell, packaged window, or system scope",
            ["windows-native"],
            "terminal unless an explicit target-local input fallback is authorized"),
        new RoutePlan(
            "click,key,type",
            "coordinate or desktop-wide target-local input",
            ["windows-native"],
            "never escalate to outer input"),
        new RoutePlan(
            "session.login and protected desktop operations",
            "Winlogon, Consent, lock, or non-Default input desktop",
            ["windows-native"],
            "typed protected route; never route through Cua"),
    ];

    public static Task<Result> ExecuteAsync(
        Request request,
        string generation,
        CancellationToken cancellationToken) =>
        Native.ExecuteAsync(request, generation, cancellationToken);
}
