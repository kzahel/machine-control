namespace MachineControl.Windows;

// Contract.Request's JsonIgnored protected in-process context is not used by
// the ordinary broker. Keep the portable contracts independent of Win32/WPF.
internal sealed class UnlockAttempt { }
