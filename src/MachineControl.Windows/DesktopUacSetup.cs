using System.Diagnostics;
using System.IO;
using System.Security.AccessControl;
using System.Security.Cryptography;
using System.Security.Principal;

namespace MachineControl.Windows;

internal static class DesktopUacSetup
{
    internal static string Resolve()
    {
        var bundled = Environment.ProcessPath!;
        if (!DesktopUacNative.Installed()) return bundled;
        using var installed = File.OpenRead(DesktopUacNative.Executable);
        using var source = File.OpenRead(bundled);
        // A product update must not run an old installed companion silently.
        return SHA256.HashData(installed).SequenceEqual(SHA256.HashData(source)) ? DesktopUacNative.Executable : bundled;
    }
    internal static int Request(bool remove)
    {
        using var process = Process.Start(new ProcessStartInfo(Environment.ProcessPath!, remove ? "uac-remove" : "uac-install")
        { UseShellExecute = true, Verb = "runas" }) ?? throw new InvalidOperationException("Windows elevation did not start setup");
        process.WaitForExit();
        return process.ExitCode;
    }
    private static void RequireAdmin()
    {
        using var identity = WindowsIdentity.GetCurrent();
        if (!new WindowsPrincipal(identity).IsInRole(WindowsBuiltInRole.Administrator) || identity.IsSystem ||
            DesktopController.GetIntegrityRid() < 12288 || RuntimeProfile.SessionId == 0 || DesktopController.GetInputDesktopName() != "Default")
            throw new UnauthorizedAccessException("UAC helper setup requires an elevated interactive administrator");
    }
    internal static int RequestUnlockApproval()
    {
        if (!DesktopUacNative.Installed()) throw new InvalidOperationException("Install the desktop helper first");
        string? proposal = null;
        Exception? failure = null;
        var thread = new Thread(() =>
        {
            try
            {
                using var picker = new System.Windows.Forms.OpenFileDialog
                { Title = "Choose the controller's public unlock approval", Filter = "Public approval (*.json)|*.json", CheckFileExists = true };
                if (picker.ShowDialog() == System.Windows.Forms.DialogResult.OK)
                    proposal = picker.FileName;
            }
            catch (Exception error) { failure = error; }
        });
        thread.SetApartmentState(ApartmentState.STA);
        thread.Start(); thread.Join();
        if (failure is not null) throw new InvalidOperationException("Controller approval failed", failure);
        if (proposal is null) return 1223;
        var launch = new ProcessStartInfo(DesktopUacNative.Executable) { UseShellExecute = true, Verb = "runas" };
        foreach (var argument in new[] { "unlock-arm", "--instance", DesktopLockedUse.Instance, "--proposal", proposal })
            launch.ArgumentList.Add(argument);
        using var process = Process.Start(launch) ?? throw new InvalidOperationException("Windows elevation did not start approval");
        process.WaitForExit();
        return process.ExitCode;
    }
    private static void ServiceCommand(params string[] args)
    {
        var start = new ProcessStartInfo(Path.Combine(Environment.SystemDirectory, "sc.exe")) { UseShellExecute = false, CreateNoWindow = true };
        foreach (var argument in args) start.ArgumentList.Add(argument);
        using var process = Process.Start(start)!;
        process.WaitForExit();
        if (process.ExitCode != 0) throw new IOException("UAC helper service setup failed: " + process.ExitCode);
    }
    private static void ProtectDirectory(string path)
    {
        var admin = new SecurityIdentifier(WellKnownSidType.BuiltinAdministratorsSid, null);
        var security = new DirectorySecurity();
        security.SetOwner(admin);
        security.SetAccessRuleProtection(true, false);
        foreach (var sid in new[] { admin, new SecurityIdentifier(WellKnownSidType.LocalSystemSid, null) })
            security.AddAccessRule(new FileSystemAccessRule(sid, FileSystemRights.FullControl, InheritanceFlags.ContainerInherit | InheritanceFlags.ObjectInherit, PropagationFlags.None, AccessControlType.Allow));
        security.AddAccessRule(new FileSystemAccessRule(new SecurityIdentifier(WellKnownSidType.BuiltinUsersSid, null), FileSystemRights.ReadAndExecute,
            InheritanceFlags.ContainerInherit | InheritanceFlags.ObjectInherit, PropagationFlags.None, AccessControlType.Allow));
        new DirectoryInfo(path).SetAccessControl(security);
    }
    internal static int Install()
    {
        RequireAdmin();
        if (Directory.Exists(DesktopUacNative.Root)) throw new InvalidOperationException("Remove the existing UAC helper before installing this version");
        var grants = UnlockPolicy.Root(DesktopLockedUse.Instance);
        if (Directory.Exists(grants)) throw new InvalidOperationException("Remove existing desktop unlock preparation before installing");
        var source = AppContext.BaseDirectory;
        // Validate the entire source topology before creating the privileged
        // payload. No links or writable destinations can escape this root.
        var files = Directory.GetFiles(source, "*", SearchOption.AllDirectories);
        foreach (var path in Directory.EnumerateFileSystemEntries(source, "*", SearchOption.AllDirectories))
            if ((File.GetAttributes(path) & FileAttributes.ReparsePoint) != 0) throw new IOException("UAC helper payload contains a link");
        if (files.Length > 1000 || files.Sum(file => new FileInfo(file).Length) > 512L * 1024 * 1024) throw new IOException("UAC helper payload exceeds bounds");
        Directory.CreateDirectory(DesktopUacNative.Root);
        ProtectDirectory(DesktopUacNative.Root);
        UnlockAdmin.RequireProtectedPath(DesktopUacNative.Root, DesktopUacNative.Root);
        var registered = false;
        var grantsCreated = false;
        try
        {
            foreach (var file in files)
            {
                var destination = Path.Combine(DesktopUacNative.Root, Path.GetRelativePath(source, file));
                Directory.CreateDirectory(Path.GetDirectoryName(destination)!);
                File.Copy(file, destination, false);
            }
            foreach (var path in Directory.EnumerateFileSystemEntries(DesktopUacNative.Root, "*", SearchOption.AllDirectories))
                UnlockAdmin.RequireProtectedPath(path, DesktopUacNative.Root);
            var parent = Path.GetDirectoryName(grants)!;
            if (!Directory.Exists(parent)) { Directory.CreateDirectory(parent); ProtectDirectory(parent); }
            UnlockAdmin.RequireProtectedPath(parent, parent);
            // Older standalone unlock installations made this shared parent
            // SYSTEM/admin-only. The Medium desktop must inspect its ACL to
            // verify that nobody can replace our protected child directory.
            // Add metadata inspection only, without enumeration or inheritance
            // into another unlock instance's files.
            var parentSecurity = new DirectoryInfo(parent).GetAccessControl();
            parentSecurity.AddAccessRule(new FileSystemAccessRule(
                new SecurityIdentifier(WellKnownSidType.BuiltinUsersSid, null),
                FileSystemRights.ReadPermissions, AccessControlType.Allow));
            new DirectoryInfo(parent).SetAccessControl(parentSecurity);
            if (Directory.Exists(grants)) throw new InvalidOperationException("Remove existing desktop unlock preparation before installing");
            Directory.CreateDirectory(grants); ProtectDirectory(grants);
            grantsCreated = true;
            ServiceCommand("create", DesktopUacNative.Service, "binPath=", $"\"{DesktopUacNative.Executable}\" uac-service", "start=", "auto", "DisplayName=", "Machine Control desktop UAC helper");
            registered = true;
            ServiceCommand("start", DesktopUacNative.Service);
            return 0;
        }
        catch
        {
            if (!registered)
            {
                if (grantsCreated) Directory.Delete(grants, true);
                Directory.Delete(DesktopUacNative.Root, true);
            }
            throw;
        }
    }
    internal static int Remove()
    {
        RequireAdmin();
        UnlockAdmin.RequireProtectedPath(DesktopUacNative.Root, DesktopUacNative.Root);
        // Refuse before mutation if another desktop still owns this payload.
        foreach (var process in Process.GetProcessesByName("machine-control-windows"))
            using (process)
            {
                if (process.Id == Environment.ProcessId || process.SessionId == 0) continue;
                if (!NativeMethods.OpenProcessToken(process.Handle, NativeMethods.TOKEN_QUERY, out var token))
                    throw new UnauthorizedAccessException("Cannot establish helper payload ownership");
                using var tokenHandle = new NativeHandle(token);
                if (TokenInspector.GetIntegrityRid(token) >= 16384) continue;
                if (string.Equals(process.MainModule?.FileName, DesktopUacNative.Executable, StringComparison.OrdinalIgnoreCase))
                    throw new InvalidOperationException("Close Machine Control before removing its UAC helper");
            }
        using (var service = new System.ServiceProcess.ServiceController(DesktopUacNative.Service))
        {
            if (service.Status != System.ServiceProcess.ServiceControllerStatus.Stopped)
            { service.Stop(); service.WaitForStatus(System.ServiceProcess.ServiceControllerStatus.Stopped, TimeSpan.FromSeconds(15)); }
        }
        ServiceCommand("delete", DesktopUacNative.Service);
        var grants = UnlockPolicy.Root(DesktopLockedUse.Instance);
        if (Directory.Exists(grants))
        { UnlockAdmin.RequireProtectedPath(grants, Path.GetDirectoryName(grants)!); Directory.Delete(grants, true); }
        Directory.Delete(DesktopUacNative.Root, true);
        return 0;
    }
}
