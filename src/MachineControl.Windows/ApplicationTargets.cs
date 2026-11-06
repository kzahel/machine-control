namespace MachineControl.Windows;

/// Pure application-target selection over observed top-level windows. A
/// target names a running application by process ID, process or product
/// name, application user model ID, or window title. An exact match wins over
/// a unique partial match; nothing or an ambiguous partial match is refused.
internal static class ApplicationTargets
{
    internal sealed record ApplicationWindow(
        long Hwnd,
        int ProcessId,
        string ProcessName,
        string Name,
        string? ApplicationId,
        string Title,
        int ZOrder);

    internal static string Key(ApplicationWindow window) => window.ApplicationId ?? "pid:" + window.ProcessId;

    internal sealed record TargetResolution(ApplicationWindow? Window, string? Refusal, string Selection, int Candidates);

    internal static TargetResolution Select(IReadOnlyList<ApplicationWindow> windows, string target, long foreground = 0)
    {
        var wanted = target.Trim();
        if (wanted.Length is 0 or > 512 || wanted.Any(char.IsControl))
            return new(null, "invalid_target", "none", 0);
        if (wanted.Equals("foreground", StringComparison.OrdinalIgnoreCase))
        {
            var front = windows.FirstOrDefault(window => window.Hwnd == foreground);
            return front is null ? new(null, "target_unavailable", "foreground", 0) : new(front, null, "foreground", 1);
        }
        if (int.TryParse(wanted, System.Globalization.NumberStyles.None, System.Globalization.CultureInfo.InvariantCulture, out var pid))
        {
            var owned = windows.Where(window => window.ProcessId == pid).OrderBy(window => window.ZOrder).FirstOrDefault();
            return owned is null ? new(null, "target_unavailable", "process_id", 0) : new(owned, null, "process_id", 1);
        }
        static bool Exact(ApplicationWindow window, string value) =>
            window.ProcessName.Equals(value, StringComparison.OrdinalIgnoreCase) ||
            (window.ProcessName + ".exe").Equals(value, StringComparison.OrdinalIgnoreCase) ||
            window.Name.Equals(value, StringComparison.OrdinalIgnoreCase) ||
            window.ApplicationId?.Equals(value, StringComparison.OrdinalIgnoreCase) == true ||
            window.Title.Equals(value, StringComparison.OrdinalIgnoreCase);
        static bool Partial(ApplicationWindow window, string value) =>
            window.ProcessName.Contains(value, StringComparison.OrdinalIgnoreCase) ||
            window.Name.Contains(value, StringComparison.OrdinalIgnoreCase) ||
            window.ApplicationId?.Contains(value, StringComparison.OrdinalIgnoreCase) == true ||
            window.Title.Contains(value, StringComparison.OrdinalIgnoreCase);
        var exact = windows.Where(window => Exact(window, wanted)).OrderBy(window => window.ZOrder).ToList();
        if (exact.Count > 0)
        {
            // Several instances of one named application: the frontmost wins,
            // and the result reports how many instances matched.
            return new(exact[0], null, "exact", exact.Select(Key).Distinct().Count());
        }
        var partial = windows.Where(window => Partial(window, wanted)).OrderBy(window => window.ZOrder).ToList();
        var applications = partial.Select(Key).Distinct().Count();
        if (applications == 1) return new(partial[0], null, "unique_partial", 1);
        return new(null, applications == 0 ? "target_unavailable" : "target_ambiguous", "partial", applications);
    }
}
