namespace MachineControl.Windows;

/// Closed product surface. In particular, app.launch never runs as SYSTEM.
internal static class DesktopUacPolicy
{
    internal static readonly string[] Operations =
    [
        "windows", "snapshot", "screenshot", "app.activate", "invoke",
        "set.value", "click", "key", "type", "window.state", "uac.respond",
    ];

    internal static string? Refusal(Request request, bool enabled, bool unlocked,
        string desktop, bool consentPrompt)
    {
        if (!enabled) return "uac_access_disabled";
        if (!Operations.Contains(request.Operation, StringComparer.Ordinal) ||
            request.CredentialKind is not null || request.SecretPipe is not null ||
            request.ExecutablePath is not null || request.Arguments is not null)
            return "protected_operation_refused";
        if (!unlocked) return "desktop_unavailable";
        if (desktop == "Default")
            return request.Operation == "uac.respond" ? "uac_prompt_unavailable" : null;
        if (desktop != "Winlogon" || !consentPrompt) return "uac_prompt_unavailable";
        if (request.Operation is "windows" or "snapshot" or "screenshot") return null;
        if (request.Operation != "uac.respond") return "secure_desktop_operation_refused";
        return request.State is "approve" or "cancel" && request.Text is null &&
            request.Key is null && request.Reference is null && request.Query is null &&
            request.Hwnd is null && request.ProcessId is null && request.X is null && request.Y is null
            ? null : "invalid_uac_response";
    }
}
