using System.ComponentModel;
using System.Diagnostics;
using System.IO;
using System.Runtime.InteropServices;

namespace MachineControl.Windows;

internal static class DesktopApplicationLauncher
{
    internal static Process? Start(string path, string arguments)
    {
        if (DesktopSafety.Broker is null)
            return Process.Start(new ProcessStartInfo
            {
                FileName = path,
                Arguments = arguments,
                WorkingDirectory = Path.GetDirectoryName(path),
                UseShellExecute = false
            });
        // User applications are not resident-owned providers. Explicitly leave
        // our breakaway-enabled job; Quit must not kill a person's applications.
        var startup = new NativeMethods.STARTUPINFO { cb = Marshal.SizeOf<NativeMethods.STARTUPINFO>() };
        if (!NativeMethods.CreateProcess(path, $"\"{path}\" {arguments}", IntPtr.Zero, IntPtr.Zero,
            false, 0x01000000, IntPtr.Zero, Path.GetDirectoryName(path), ref startup, out var created))
            throw new Win32Exception(Marshal.GetLastWin32Error(), "Application launch failed");
        try { return Process.GetProcessById((int)created.dwProcessId); }
        finally { NativeMethods.CloseHandle(created.hThread); NativeMethods.CloseHandle(created.hProcess); }
    }
}
