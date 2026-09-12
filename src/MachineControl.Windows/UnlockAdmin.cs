using System.IO;
using System.Security.AccessControl;
using System.Security.Principal;
using System.Text.Json;
using Forms = System.Windows.Forms;

namespace MachineControl.Windows;

internal static class UnlockAdmin
{
    public static void RequireProtectedPath(string path, string boundary)
    {
        for (var cursor = path; cursor.Length >= boundary.Length; cursor = Path.GetDirectoryName(cursor)!)
        {
            if ((File.GetAttributes(cursor) & FileAttributes.ReparsePoint) != 0)
                throw new InvalidDataException("Protected path cannot contain reparse points");
            FileSystemSecurity security = Directory.Exists(cursor)
                ? new DirectoryInfo(cursor).GetAccessControl() : new FileInfo(cursor).GetAccessControl();
            static bool Trusted(IdentityReference? value) => value?.Value is "S-1-5-18" or "S-1-5-32-544";
            if (!Trusted(security.GetOwner(typeof(SecurityIdentifier))))
                throw new UnauthorizedAccessException("Protected path has an untrusted owner");
            const FileSystemRights writes = FileSystemRights.Write | FileSystemRights.Delete |
                FileSystemRights.DeleteSubdirectoriesAndFiles | FileSystemRights.ChangePermissions | FileSystemRights.TakeOwnership;
            foreach (FileSystemAccessRule rule in security.GetAccessRules(true, true, typeof(SecurityIdentifier)))
                if (rule.AccessControlType == AccessControlType.Allow && !Trusted(rule.IdentityReference) &&
                    (rule.FileSystemRights & writes) != 0)
                    throw new UnauthorizedAccessException("Protected path is writable by an ordinary identity");
        }
    }

    public static int Arm(string instance, string proposalFile)
    {
        using var identity = WindowsIdentity.GetCurrent();
        if (!new WindowsPrincipal(identity).IsInRole(WindowsBuiltInRole.Administrator) || identity.IsSystem ||
            DesktopController.GetIntegrityRid() < 12288 || RuntimeProfile.SessionId == 0 ||
            !string.Equals(DesktopController.GetInputDesktopName(), "Default", StringComparison.OrdinalIgnoreCase))
            throw new UnauthorizedAccessException("Arming requires the elevated interactive setup UI");
        var root = UnlockPolicy.Root(instance);
        RequireProtectedPath(root, Path.GetDirectoryName(root)!);
        var installation = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.ProgramFiles), "MachineControlUnlock");
        var executable = Environment.ProcessPath!;
        if (!executable.StartsWith(installation + Path.DirectorySeparatorChar, StringComparison.OrdinalIgnoreCase))
            throw new UnauthorizedAccessException("Run the installed protected setup component");
        RequireProtectedPath(executable, installation);
        if (new FileInfo(proposalFile).Length > 16 * 1024) throw new InvalidDataException("Proposal too large");
        // Read once, validate and display the exact immutable value later written.
        var grant = UnlockPolicy.Validate(JsonSerializer.Deserialize<UnlockGrant>(File.ReadAllText(proposalFile), Contract.Json)
            ?? throw new InvalidDataException());
        var display = UnlockAccount.UniqueDisplayName(grant.TargetUserSid);
        var account = new SecurityIdentifier(grant.TargetUserSid).Translate(typeof(NTAccount)).Value;
        var transport = new SecurityIdentifier(grant.TransportUserSid).Translate(typeof(NTAccount)).Value;
        var lifetime = grant.ExpiresAt?.ToString("u") ?? "Until you revoke this approval";
        var text = $"Enable unattended unlock for this existing Windows console account?\n\n" +
            $"Account: {display} ({account})\nAccount SID: {grant.TargetUserSid}\n" +
            $"Transport account: {transport}\nTransport SID: {grant.TransportUserSid}\n" +
            $"Controller key SHA-256:\n{UnlockPolicy.Fingerprint(grant)}\n\n" +
            $"Expires: {lifetime}\n\n" +
            "The approved controller can unlock this account using its password or PIN, " +
            "without another local prompt. Unlock exposes the desktop. " +
            "The service does not save the Windows credential.\n\nApprove this controller?";
        if (Forms.MessageBox.Show(text, "Machine Control — approve unattended unlock",
            Forms.MessageBoxButtons.YesNo, Forms.MessageBoxIcon.Warning,
            Forms.MessageBoxDefaultButton.Button2) != Forms.DialogResult.Yes) return 1223;
        UnlockPolicy.Validate(grant); // Expiry may have passed while the dialog was open.
        RequireProtectedPath(root, Path.GetDirectoryName(root)!);
        using var mutex = new FileStream(Path.Combine(root, "admin.lock"), FileMode.OpenOrCreate,
            FileAccess.ReadWrite, FileShare.None);
        var temporary = Path.Combine(root, Guid.NewGuid().ToString("n") + ".tmp");
        try
        {
            File.WriteAllText(temporary, Contract.Serialize(grant));
            File.Move(temporary, UnlockPolicy.GrantPath(instance), overwrite: true);
        }
        finally { File.Delete(temporary); }
        Console.WriteLine("Unlock approval installed");
        return 0;
    }
}
