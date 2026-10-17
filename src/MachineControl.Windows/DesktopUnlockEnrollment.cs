using System.ComponentModel;
using System.Diagnostics;
using System.IO;
using System.IO.Pipes;
using System.Runtime.InteropServices;
using System.Security.AccessControl;
using System.Security.Cryptography;
using System.Security.Principal;
using System.Text;
using System.Text.Json;
using Forms = System.Windows.Forms;

namespace MachineControl.Windows;

/// Native setup and a SYSTEM-owned encrypted store with no export API. The
/// public grant is metadata only; no ordinary request carries credential material.
internal static class DesktopUnlockEnrollment
{
    private static string Root => UnlockPolicy.Root(DesktopLockedUse.Instance);
    private static string Vault => Path.Combine(Root, "credential.dpapi");
    private static string Policy => UnlockPolicy.GrantPath(DesktopLockedUse.Instance);
    private static readonly UTF8Encoding Utf8 = new(false, true);

    internal static async Task ServeAsync(NamedPipeServerStream pipe, bool remove, CancellationToken stop)
    {
        RequireSetupPeer(pipe);
        var session = NativeMethods.WTSGetActiveConsoleSessionId();
        var sid = UnlockNative.ConsoleUserSid(session);
        var logon = UnlockNative.ConsoleLogonId(session);
        _ = UnlockAccount.UniqueDisplayName(sid);
        var account = new SecurityIdentifier(sid).Translate(typeof(NTAccount)).Value;
        if (!account.StartsWith(Environment.MachineName + "\\", StringComparison.OrdinalIgnoreCase))
            throw new InvalidDataException("local_account_required");
        void Check()
        {
            RequireSetupPeer(pipe);
            if (NativeMethods.WTSGetActiveConsoleSessionId() != session ||
                UnlockNative.ConsoleUserSid(session) != sid || UnlockNative.ConsoleLogonId(session) != logon ||
                SessionStateInspector.IsLocked(session) != false)
                throw new UnauthorizedAccessException("enrollment_console_changed");
        }
        Check();
        if (remove)
        {
            Revoke();
            await UnlockWire.WriteAsync(pipe, new { stage = "removed" }, stop);
            return;
        }
        await UnlockWire.WriteAsync(pipe, new { stage = "enrollment_ready", account, targetUserSid = sid }, stop);
        byte[]? secret = null;
        try
        {
            // Exactly one binary frame after authenticated, unlocked local
            // account discovery. Cancel/disconnect never changes old enrollment.
            secret = await UnlockWire.ReadSecretAsync(pipe, stop);
            Check();
            ValidatePassword(account[(account.IndexOf('\\') + 1)..], sid, secret);
            Check();
            var grant = new UnlockGrant(UnlockPolicy.Schema, Guid.NewGuid().ToString("n"), sid, sid, "", null, "local_enrollment");
            Save(grant, secret);
            await UnlockWire.WriteAsync(pipe, new { stage = "enrolled" }, stop);
        }
        finally { if (secret is not null) CryptographicOperations.ZeroMemory(secret); }
    }

    private static void RequireSetupPeer(NamedPipeServerStream pipe)
    {
        if (!WindowsIdentity.GetCurrent().IsSystem) throw new UnauthorizedAccessException("system_required");
        using var process = Process.GetProcessById((int)DesktopUacNative.ClientPid(pipe));
        if (!string.Equals(process.MainModule?.FileName, DesktopUacNative.Executable, StringComparison.OrdinalIgnoreCase) ||
            process.SessionId == 0 || process.SessionId != NativeMethods.WTSGetActiveConsoleSessionId())
            throw new UnauthorizedAccessException("installed_console_setup_required");
        UnlockAdmin.RequireProtectedPath(DesktopUacNative.Executable, DesktopUacNative.Root);
        var administrator = false;
        pipe.RunAsClient(() =>
        {
            using var caller = WindowsIdentity.GetCurrent();
            administrator = !caller.IsSystem && new WindowsPrincipal(caller).IsInRole(WindowsBuiltInRole.Administrator);
        });
        if (!NativeMethods.OpenProcessToken(process.Handle, NativeMethods.TOKEN_QUERY, out var token))
            throw new Win32Exception(Marshal.GetLastWin32Error());
        using var handle = new NativeHandle(token);
        if (!administrator || TokenInspector.GetIntegrityRid(token) < 12288)
            throw new UnauthorizedAccessException("elevated_setup_required");
    }

    private static void ValidatePassword(string user, string sid, byte[] secret)
    {
        var chars = Utf8.GetChars(secret);
        var password = Marshal.AllocHGlobal((chars.Length + 1) * 2);
        try
        {
            if (chars.Length == 0 || chars.AsSpan().ContainsAny('\0', '\r', '\n')) throw new InvalidDataException("invalid_credential");
            Marshal.Copy(chars, 0, password, chars.Length);
            Marshal.WriteInt16(password, chars.Length * 2, 0);
            // One deliberate validation only. Never loop, retry or expose the
            // token. Windows password/lockout policy applies normally.
            if (!LogonUser(user, Environment.MachineName, password, 2, 0, out var token))
                throw new InvalidDataException("credential_rejected_reenter_in_setup");
            using var handle = new NativeHandle(token);
            using var identity = new WindowsIdentity(token);
            if (identity.User?.Value != sid) throw new UnauthorizedAccessException("credential_account_mismatch");
        }
        finally
        {
            Array.Clear(chars);
            for (var i = 0; i <= chars.Length; i++) Marshal.WriteInt16(password, i * 2, 0);
            Marshal.FreeHGlobal(password);
        }
    }

    private static byte[] Entropy(UnlockGrant grant) => SHA256.HashData(Utf8.GetBytes(
        "machine-control-desktop-enrollment/v1:" + grant.TargetUserSid + ":" + grant.Revision));

    private static void Save(UnlockGrant grant, byte[] secret)
    {
        UnlockAdmin.RequireProtectedPath(Root, Path.GetDirectoryName(Root)!);
        using var mutex = new FileStream(Path.Combine(Root, "admin.lock"), FileMode.OpenOrCreate, FileAccess.ReadWrite, FileShare.None);
        var ciphertext = ProtectedData.Protect(secret, Entropy(grant), DataProtectionScope.CurrentUser);
        // Publishing metadata last makes interrupted rotation fail closed.
        WriteProtected(Vault, ciphertext, publicRead: false);
        WriteProtected(Policy, Utf8.GetBytes(Contract.Serialize(grant)), publicRead: true);
    }

    private static void WriteProtected(string path, byte[] bytes, bool publicRead)
    {
        var temporary = Path.Combine(Root, Guid.NewGuid().ToString("n") + ".tmp");
        try
        {
            var acl = new FileSecurity();
            acl.SetAccessRuleProtection(true, false);
            var system = new SecurityIdentifier(WellKnownSidType.LocalSystemSid, null);
            acl.SetOwner(system);
            foreach (var sid in new[] { system, new SecurityIdentifier(WellKnownSidType.BuiltinAdministratorsSid, null) })
                acl.AddAccessRule(new FileSystemAccessRule(sid, FileSystemRights.FullControl, AccessControlType.Allow));
            if (publicRead) acl.AddAccessRule(new FileSystemAccessRule(new SecurityIdentifier(WellKnownSidType.BuiltinUsersSid, null), FileSystemRights.Read, AccessControlType.Allow));
            using (var output = new FileInfo(temporary).Create(FileMode.CreateNew, FileSystemRights.FullControl, FileShare.None, 4096, FileOptions.WriteThrough, acl))
            { output.Write(bytes); output.Flush(true); }
            File.Move(temporary, path, overwrite: true);
        }
        finally { File.Delete(temporary); }
    }

    internal static byte[] Read(UnlockGrant grant)
    {
        if (!WindowsIdentity.GetCurrent().IsSystem || grant.CredentialSource != "local_enrollment" ||
            UnlockPolicy.Read(DesktopLockedUse.Instance) != grant)
            throw new UnauthorizedAccessException("enrollment_authority_changed");
        UnlockAdmin.RequireProtectedPath(Vault, Path.GetDirectoryName(Root)!);
        var acl = new FileInfo(Vault).GetAccessControl();
        foreach (FileSystemAccessRule rule in acl.GetAccessRules(true, true, typeof(SecurityIdentifier)))
            if (rule.AccessControlType == AccessControlType.Allow && rule.IdentityReference.Value is not ("S-1-5-18" or "S-1-5-32-544"))
                throw new UnauthorizedAccessException("credential_store_permissions_invalid");
        if (new FileInfo(Vault).Length is < 1 or > 4096) throw new InvalidDataException("credential_store_invalid");
        return ProtectedData.Unprotect(File.ReadAllBytes(Vault), Entropy(grant), DataProtectionScope.CurrentUser);
    }

    internal static void Revoke(UnlockGrant? expected = null)
    {
        if (!WindowsIdentity.GetCurrent().IsSystem) throw new UnauthorizedAccessException("system_required");
        UnlockAdmin.RequireProtectedPath(Root, Path.GetDirectoryName(Root)!);
        using var mutex = new FileStream(Path.Combine(Root, "admin.lock"), FileMode.OpenOrCreate, FileAccess.ReadWrite, FileShare.None);
        if (expected is not null)
        {
            try { if (UnlockPolicy.Read(DesktopLockedUse.Instance) != expected) return; }
            catch (Exception error) when (error is IOException or InvalidDataException) { return; }
        }
        File.Delete(Policy); // Immediately fences resident and guardian queries.
        File.Delete(Vault);
    }

    internal static async Task<int> RunSetupAsync(bool remove)
    {
        using var identity = WindowsIdentity.GetCurrent();
        if (identity.IsSystem || !new WindowsPrincipal(identity).IsInRole(WindowsBuiltInRole.Administrator) ||
            DesktopController.GetIntegrityRid() < 12288 || RuntimeProfile.SessionId == 0 ||
            DesktopController.GetInputDesktopName() != "Default") throw new UnauthorizedAccessException("elevated_interactive_setup_required");
        using var stop = new CancellationTokenSource(TimeSpan.FromMinutes(5));
        if (remove && Forms.MessageBox.Show("Remove saved Windows unlock setup? Future locked-screen tasks will require setup again. Current access will end and Windows will relock if a task unlocked it.",
            "Machine Control — remove unlock setup", Forms.MessageBoxButtons.YesNo, Forms.MessageBoxIcon.Warning, Forms.MessageBoxDefaultButton.Button2) != Forms.DialogResult.Yes) return 1223;
        using var pipe = new NamedPipeClientStream(".", UnlockPolicy.Pipe(DesktopLockedUse.Instance), PipeDirection.InOut,
            PipeOptions.Asynchronous, TokenImpersonationLevel.Identification);
        await pipe.ConnectAsync(5000, stop.Token);
        UnlockNative.RequireServicePeer(pipe, DesktopLockedUse.Instance);
        await UnlockWire.WriteAsync(pipe, new UnlockHello(remove ? "desktop.enrollment.remove" : "desktop.enrollment", null), stop.Token);
        using var readiness = JsonDocument.Parse(await UnlockWire.ReadLineAsync(pipe, stop.Token));
        var stage = readiness.RootElement.GetProperty("stage").GetString();
        if (remove) return stage == "removed" ? 0 : 1;
        if (stage != "enrollment_ready") throw new InvalidOperationException("Native unlock setup refused");
        var account = readiness.RootElement.GetProperty("account").GetString()!;
        var password = Prompt(account);
        if (password is null) return 1223;
        try
        {
            UnlockNative.RequireServicePeer(pipe, DesktopLockedUse.Instance);
            await UnlockWire.WriteSecretAsync(pipe, password, stop.Token);
        }
        finally { CryptographicOperations.ZeroMemory(password); }
        using var result = JsonDocument.Parse(await UnlockWire.ReadLineAsync(pipe, stop.Token));
        if (result.RootElement.GetProperty("stage").GetString() == "enrolled") return 0;
        Forms.MessageBox.Show("Windows unlock setup failed. No automatic retry was made. Check your account password and run setup again.", "Machine Control — unlock setup", Forms.MessageBoxButtons.OK, Forms.MessageBoxIcon.Warning);
        return 1;
    }

    private static byte[]? Prompt(string account)
    {
        var info = new CredUiInfo
        {
            Size = Marshal.SizeOf<CredUiInfo>(),
            Caption = "Machine Control — enable covered desktop access",
            Message = "Enter this account's Windows password once (not a PIN). The privileged helper saves an encrypted copy on this PC for approved tasks that start locked. Windows unlocks behind a cover and relocks when the task ends. Remove setup in Machine Control to erase it. Browser-only access needs no password."
        };
        var user = new StringBuilder(account, 514);
        var password = Marshal.AllocHGlobal(514 * 2);
        for (var i = 0; i < 514; i++) Marshal.WriteInt16(password, i * 2, 0);
        try
        {
            var save = false;
            // Generic, nonpersistent native CredUI; fixed account. The OS never
            // stores these dialog bytes in Credential Manager.
            var status = CredUIPromptForCredentials(ref info, "Machine Control covered desktop", IntPtr.Zero, 0,
                user, user.Capacity, password, 514, ref save, 0x40000 | 0x2 | 0x80 | 0x100000);
            if (status == 1223) return null;
            if (status != 0) throw new Win32Exception(status);
            if (!string.Equals(user.ToString(), account, StringComparison.OrdinalIgnoreCase)) throw new InvalidDataException("setup_account_changed");
            var count = 0;
            while (count < 513 && Marshal.ReadInt16(password, count * 2) != 0) count++;
            var chars = new char[count];
            try
            {
                Marshal.Copy(password, chars, 0, count);
                if (count == 0 || Utf8.GetByteCount(chars) > 256) throw new InvalidDataException("credential_length_unsupported");
                return Utf8.GetBytes(chars);
            }
            finally { Array.Clear(chars); }
        }
        finally
        {
            for (var i = 0; i < 514; i++) Marshal.WriteInt16(password, i * 2, 0);
            Marshal.FreeHGlobal(password);
        }
    }

    [StructLayout(LayoutKind.Sequential, CharSet = CharSet.Unicode)]
    private struct CredUiInfo
    {
        internal int Size;
        internal IntPtr Parent;
        internal string Message, Caption;
        internal IntPtr Banner;
    }
    [DllImport("credui.dll", EntryPoint = "CredUIPromptForCredentialsW", CharSet = CharSet.Unicode)]
    private static extern int CredUIPromptForCredentials(ref CredUiInfo info, string target, IntPtr reserved, int error,
        StringBuilder user, int maximumUser, IntPtr password, int maximumPassword, [MarshalAs(UnmanagedType.Bool)] ref bool save, int flags);
    [DllImport("advapi32.dll", EntryPoint = "LogonUserW", CharSet = CharSet.Unicode, SetLastError = true)]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static extern bool LogonUser(string user, string domain, IntPtr password, int type, int provider, out IntPtr token);
}
