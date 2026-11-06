using MachineControl.Windows;
using static MachineControl.Windows.ApplicationTargets;

/// Targeted input and window capture must name one running application or
/// refuse; they never fall back to the foreground or the full screen.
internal static class ApplicationTargetFixtures
{
    internal static void Run()
    {
        ApplicationWindow[] windows =
        [
            new(101, 11, "explorer", "Windows Explorer", null, "Documents", 1),
            new(202, 22, "Notepad", "Notepad", "Microsoft.WindowsNotepad_8wekyb3d8bbwe!App", "notes.txt - Notepad", 2),
            new(203, 23, "Notepad", "Notepad", "Microsoft.WindowsNotepad_8wekyb3d8bbwe!App", "other.txt - Notepad", 3),
            new(301, 31, "MachineControl.Fixture", "MachineControl.Fixture", null, "Machine Control Medium Fixture", 4),
            new(302, 32, "msedge", "Microsoft Edge", null, "Fixture page", 5),
        ];
        Require(Select(windows, "notepad").Window?.Hwnd == 202, "Exact process name selects the frontmost instance");
        Require(Select(windows, "Notepad.exe").Window?.Hwnd == 202, "Executable name matches");
        Require(Select(windows, "Microsoft.WindowsNotepad_8wekyb3d8bbwe!App").Window?.Hwnd == 202, "Application user model ID matches");
        Require(Select(windows, "Microsoft Edge").Window?.ProcessId == 32, "Product description matches");
        Require(Select(windows, "Machine Control Medium Fixture").Window?.Hwnd == 301, "Exact window title matches");
        Require(Select(windows, "31").Window?.Hwnd == 301, "Process ID selects that process");
        Require(Select(windows, "Fixture").Refusal == "target_ambiguous" && Select(windows, "Fixture").Candidates == 2,
            "Partial match across two applications is refused");
        Require(Select(windows, "edge").Window?.ProcessId == 32 && Select(windows, "edge").Selection == "unique_partial", "Unique partial match selects");
        Require(Select(windows, "calculator").Refusal == "target_unavailable" && Select(windows, "calculator").Window is null,
            "Unknown application never becomes the foreground");
        Require(Select(windows, "99").Refusal == "target_unavailable", "Unknown process ID refused");
        Require(Select(windows, "foreground", foreground: 302).Window?.Hwnd == 302, "Explicit foreground target is honored");
        Require(Select(windows, "foreground", foreground: 0).Refusal == "target_unavailable", "Missing foreground refused");
        Require(Select(windows, " ").Refusal == "invalid_target" && Select(windows, "a\nb").Refusal == "invalid_target", "Blank or control target refused");
        Require(Select([], "notepad").Refusal == "target_unavailable", "No windows means unavailable");
        Console.WriteLine("Windows application target selection contracts passed");
    }

    private static void Require(bool value, string message) { if (!value) throw new Exception(message); }
}
