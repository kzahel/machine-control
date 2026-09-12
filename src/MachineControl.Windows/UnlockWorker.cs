using System.ComponentModel;
using System.Diagnostics;
using System.IO;
using System.IO.Pipes;
using System.Security.Principal;
using System.Text.Json;
using System.Windows.Automation;

namespace MachineControl.Windows;

internal sealed class UnlockAttempt(UnlockWorkerStart start, NamedPipeClientStream service, CancellationToken stop)
{
    public void CheckAuthority()
    {
        stop.ThrowIfCancellationRequested();
        UnlockNative.RequireServicePeer(service, start.Instance);
        UnlockWire.WriteAsync(service, new UnlockWorkerMessage("check"), stop).GetAwaiter().GetResult();
        using var reply = JsonDocument.Parse(UnlockWire.ReadLineAsync(service, stop).GetAwaiter().GetResult());
        if (!reply.RootElement.GetProperty("allowed").GetBoolean()) throw new UnauthorizedAccessException();
        UnlockNative.RequireLockedAccount(start.SessionId, start.TargetUserSid);
    }

    public void Check(AutomationElement? field = null)
    {
        CheckAuthority();
        if (!string.Equals(DesktopController.GetInputDesktopName(), "Winlogon", StringComparison.OrdinalIgnoreCase))
            throw new InvalidDataException("winlogon_changed");
        if (field is null) return;
        UnlockNative.RequireReleasedModifiers();
        var displayName = UnlockAccount.UniqueDisplayName(start.TargetUserSid);
        using var process = Process.GetProcessById(field.Current.ProcessId);
        if (process.SessionId != start.SessionId || !string.Equals(process.MainModule?.FileName,
                Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.System), "LogonUI.exe"),
                StringComparison.OrdinalIgnoreCase) || !field.Current.IsPassword ||
            !field.Current.IsEnabled || field.Current.IsOffscreen)
            throw new InvalidDataException("credential_field_identity_uncertain");
        var parent = TreeWalker.RawViewWalker.GetParent(field);
        var matchedAccount = false;
        for (var depth = 0; parent is not null && depth < 8; depth++)
        {
            if (parent.Current.ControlType == ControlType.Group && parent.Current.Name == displayName)
            {
                var edits = parent.FindAll(TreeScope.Descendants,
                    new PropertyCondition(AutomationElement.ControlTypeProperty, ControlType.Edit));
                foreach (AutomationElement edit in edits)
                    if (edit.Current.IsEnabled && !edit.Current.IsOffscreen && !edit.Current.IsPassword)
                        throw new InvalidDataException("editable_account_selection_unsupported");
                matchedAccount = true;
                break;
            }
            parent = TreeWalker.RawViewWalker.GetParent(parent);
        }
        if (!matchedAccount) throw new InvalidDataException("selected_account_uncertain");
        var focus = AutomationElement.FocusedElement;
        for (var depth = 0; focus is not null && depth < 8; depth++)
        {
            if (Automation.Compare(focus, field)) return;
            focus = TreeWalker.RawViewWalker.GetParent(focus);
        }
        throw new InvalidDataException("credential_focus_changed");
    }

    public byte[] ReadSecret(AutomationElement field)
    {
        Check(field);
        UnlockWire.WriteAsync(service, new UnlockWorkerMessage("ready"), stop).GetAwaiter().GetResult();
        return UnlockWire.ReadSecretAsync(service, stop).GetAwaiter().GetResult();
    }

    public bool IsUnlocked() => NativeMethods.WTSGetActiveConsoleSessionId() == start.SessionId &&
        UnlockNative.ConsoleUserSid(start.SessionId) == start.TargetUserSid &&
        UnlockNative.ConsoleLogonId(start.SessionId) == start.SessionLogonId &&
        SessionStateInspector.IsLocked(start.SessionId) == false;
}

internal static class UnlockWorker
{
    public static async Task<int> RunAsync(string instance, string pipeName)
    {
        if (!WindowsIdentity.GetCurrent().IsSystem) throw new UnauthorizedAccessException("LocalSystem required");
        using var stop = new CancellationTokenSource(TimeSpan.FromSeconds(65));
        await using var pipe = new NamedPipeClientStream(".", pipeName, PipeDirection.InOut,
            PipeOptions.Asynchronous, TokenImpersonationLevel.Identification);
        await pipe.ConnectAsync(stop.Token);
        UnlockNative.RequireServicePeer(pipe, instance);
        var start = JsonSerializer.Deserialize<UnlockWorkerStart>(await UnlockWire.ReadLineAsync(pipe, stop.Token), Contract.Json)
            ?? throw new InvalidDataException();
        if (start.Instance != instance || Process.GetCurrentProcess().SessionId != start.SessionId)
            throw new InvalidDataException();
        var attempt = new UnlockAttempt(start, pipe, stop.Token);
        try
        {
            if (start.PrepareDesktop)
            {
                UnlockPreparation.Run(start.SessionId, attempt);
                await UnlockWire.WriteAsync(pipe, new UnlockWorkerMessage("prepared"), stop.Token);
                return 0;
            }
            var result = await DesktopController.ExecuteAsync(new Request
            {
                RequestId = Guid.NewGuid().ToString("n"),
                Operation = "session.login",
                CredentialKind = start.CredentialKind,
                UnlockAttempt = attempt,
            }, start.Generation, stop.Token);
            await UnlockWire.WriteAsync(pipe, new UnlockWorkerMessage("result", result with
            { Operation = "session.unlock", RetrySafety = "never_automatically" }), stop.Token);
            return result.Accepted ? 0 : 1;
        }
        catch (Exception error)
        {
            // Only implementation-owned failure types/codes cross this pipe.
            // Never serialize exception messages or credential/provider values.
            await UnlockWire.WriteAsync(pipe, new UnlockWorkerMessage("fault",
                Failure: error.Message is "unlock_desktop_unsupported" or "lock_curtain_changed" or
                    "lock_curtain_input_refused" or "protected_credential_desktop_unavailable" or
                    "lock_display_wake_refused" or "lock_curtain_dismissal_not_observed" or "lock_curtain_not_foreground" or
                    "keyboard_modifier_held" or "locked_account_changed" or "unlock_service_identity_mismatch"
                    ? error.Message : error.GetType().Name, NativeError: (error as Win32Exception)?.NativeErrorCode), stop.Token);
            return 1;
        }
    }
}
