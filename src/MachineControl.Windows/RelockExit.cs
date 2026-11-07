namespace MachineControl.Windows;

/// Internal guardian exit status. A reason never substitutes for independently
/// observed lock: the low byte records that observation, the high byte its
/// first ending cause. Unknown/crashed processes cannot acknowledge cleanup.
internal static class RelockExit
{
    internal static int Encode(int status, int reason) => status | (reason << 8);
    internal static bool Relocked(int code) => (code & 0xff) == 0 && code is >= 0 and <= 3072;
    internal static string Reason(int code) => (code >> 8) switch
    {
        0 => "unspecified",
        1 => "physical_takeover",
        2 => "input_hooks_unavailable",
        3 => "cover_setup_failed",
        4 => "cover_maintenance_failed",
        5 => "message_loop_failed",
        6 => "message_loop_ended",
        7 => "task_deadline",
        8 => "heartbeat_timeout",
        9 => "message_loop_timeout",
        10 => "authority_refused",
        11 => "heartbeat_connection_ended",
        12 => "extension_invalid",
        _ => "unknown"
    };
}
