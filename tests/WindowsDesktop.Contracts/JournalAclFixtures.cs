using System.ComponentModel;
using System.Runtime.InteropServices;
using System.Security.AccessControl;
using System.Security.Principal;
using MachineControl.Windows;
using Microsoft.Win32.SafeHandles;

internal static class JournalAclFixtures
{
    internal static void Run()
    {
        if (!OperatingSystem.IsWindows()) return;
        var root = Path.Combine(Path.GetTempPath(), "mc-journal-acl-" + Guid.NewGuid().ToString("n"));
        try
        {
            var journal = new DesktopJournal(root);
            var before = Changed(root);
            var auditBefore = Changed(Path.Combine(root, "audit"));
            if (!journal.Event("fixture.repeat")) throw new Exception("Repeated audit append failed");
            if (before != Changed(root) || auditBefore != Changed(Path.Combine(root, "audit")))
                throw new Exception("Audit rewrote an already-private directory security descriptor");

            var directory = new DirectoryInfo(root);
            var widened = directory.GetAccessControl();
            widened.AddAccessRule(new FileSystemAccessRule(
                new SecurityIdentifier(WellKnownSidType.BuiltinUsersSid, null), FileSystemRights.ReadAndExecute,
                InheritanceFlags.ContainerInherit | InheritanceFlags.ObjectInherit, PropagationFlags.None, AccessControlType.Allow));
            directory.SetAccessControl(widened);
            if (!journal.Event("fixture.repair")) throw new Exception("Changed ACL audit append failed");
            var repaired = directory.GetAccessControl();
            var rules = repaired.GetAccessRules(true, true, typeof(SecurityIdentifier)).Cast<FileSystemAccessRule>().ToArray();
            if (!repaired.AreAccessRulesProtected || rules.Length != 1 ||
                !rules[0].IdentityReference.Equals(WindowsIdentity.GetCurrent().User))
                throw new Exception("Audit did not repair an externally widened private directory ACL");
            Console.WriteLine("Windows journal ACL reuse and repair contracts passed");
        }
        finally { if (Directory.Exists(root)) Directory.Delete(root, true); }
    }

    private static long Changed(string path)
    {
        using var handle = CreateFile(path, 0x80, 7, IntPtr.Zero, 3, 0x02000000, IntPtr.Zero);
        if (handle.IsInvalid || !GetFileInformationByHandleEx(handle, 0, out var info, (uint)Marshal.SizeOf<BasicInfo>()))
            throw new Win32Exception(Marshal.GetLastWin32Error());
        return info.ChangeTime;
    }

    [StructLayout(LayoutKind.Sequential)]
    private struct BasicInfo
    {
        public long CreationTime, LastAccessTime, LastWriteTime, ChangeTime;
        public uint Attributes;
    }
    [DllImport("kernel32.dll", EntryPoint = "CreateFileW", CharSet = CharSet.Unicode, SetLastError = true)]
    private static extern SafeFileHandle CreateFile(string path, uint access, uint share, IntPtr security, uint disposition, uint flags, IntPtr template);
    [DllImport("kernel32.dll", SetLastError = true)]
    private static extern bool GetFileInformationByHandleEx(SafeFileHandle handle, int kind, out BasicInfo info, uint size);
}
