using System.Diagnostics;
using System.IO;
using System.IO.Pipes;
using System.Runtime.InteropServices;
using System.Security.Cryptography;
using System.Security.Principal;
using System.Text;
using System.Text.Json;
using System.Windows.Automation;
using MachineControl.Windows;

/// Dedicated appliance fixture only. Native CredUI is the product entry point;
/// this separate actor waits for its exact password field before accepting one
/// binary credential frame. Neither test arguments nor evidence carry a secret.
internal static class EnrollmentPromptLive
{
    internal static async Task RunAsync(string[] args)
    {
        using var stop = new CancellationTokenSource(TimeSpan.FromSeconds(90));
        if (args[0] == "--enrollment-feed")
        {
            using var pipe = new NamedPipeClientStream(".", args[1], PipeDirection.InOut, PipeOptions.Asynchronous, TokenImpersonationLevel.Identification);
            await pipe.ConnectAsync(5000, stop.Token);
            DesktopUacNative.RequireServer(pipe, uint.Parse(args[2]));
            using var ready = JsonDocument.Parse(await UnlockWire.ReadLineAsync(pipe, stop.Token));
            if (ready.RootElement.GetProperty("stage").GetString() != "ready") throw new InvalidDataException();
            Console.WriteLine("ready"); Console.Out.Flush();
            byte[]? secret = null;
            try
            {
                secret = await UnlockWire.ReadSecretAsync(Console.OpenStandardInput(), stop.Token);
                await UnlockWire.WriteSecretAsync(pipe, secret, stop.Token);
            }
            finally { if (secret is not null) CryptographicOperations.ZeroMemory(secret); }
            Console.WriteLine(await UnlockWire.ReadLineAsync(pipe, stop.Token));
            return;
        }
        var pid = int.Parse(args[1]);
        using var target = Process.GetProcessById(pid);
        if (target.SessionId != Process.GetCurrentProcess().SessionId || target.SessionId != NativeMethods.WTSGetActiveConsoleSessionId() ||
            target.SessionId == 0 || !string.Equals(target.MainModule?.FileName, DesktopUacNative.Executable, StringComparison.OrdinalIgnoreCase) ||
            DesktopController.GetInputDesktopName() != "Default") throw new UnauthorizedAccessException("Exact native setup console required");
        UnlockAdmin.RequireProtectedPath(DesktopUacNative.Executable, DesktopUacNative.Root);
        if (args[0] == "--enrollment-remove-confirm")
        {
            while (!stop.IsCancellationRequested)
            {
                var confirmation = AutomationElement.RootElement.FindFirst(TreeScope.Children, new AndCondition(
                    new PropertyCondition(AutomationElement.ProcessIdProperty, pid),
                    new PropertyCondition(AutomationElement.NameProperty, "Machine Control — remove unlock setup")));
                if (confirmation is not null)
                {
                    var yes = confirmation.FindFirst(TreeScope.Descendants, new AndCondition(
                        new PropertyCondition(AutomationElement.ControlTypeProperty, ControlType.Button),
                        new PropertyCondition(AutomationElement.NameProperty, "Yes")));
                    if (yes is null || !yes.Current.IsEnabled || yes.Current.IsOffscreen)
                        throw new InvalidDataException("Native removal confirmation uncertain");
                    ((InvokePattern)yes.GetCurrentPattern(InvokePattern.Pattern)).Invoke();
                    return;
                }
                await Task.Delay(100, stop.Token);
            }
            throw new InvalidDataException("Native removal confirmation unavailable");
        }
        AutomationElement? dialog = null, field = null;
        while (!stop.IsCancellationRequested)
        {
            var windows = AutomationElement.RootElement.FindAll(TreeScope.Children,
                new PropertyCondition(AutomationElement.ProcessIdProperty, pid));
            foreach (AutomationElement window in windows)
            {
                if (window.Current.Name != "Machine Control — enable covered desktop access") continue;
                var fields = window.FindAll(TreeScope.Descendants, new AndCondition(
                    new PropertyCondition(AutomationElement.IsPasswordProperty, true),
                    new PropertyCondition(AutomationElement.ControlTypeProperty, ControlType.Edit),
                    new PropertyCondition(AutomationElement.IsEnabledProperty, true),
                    new PropertyCondition(AutomationElement.IsOffscreenProperty, false)));
                if (fields.Count != 1) throw new InvalidDataException("Password field uncertain");
                dialog = window; field = fields[0]; break;
            }
            if (field is not null) break;
            await Task.Delay(100, stop.Token);
        }
        if (field is null || dialog is null) throw new InvalidDataException();
        if (args[0] == "--enrollment-cancel")
        {
            var cancel = dialog.FindFirst(TreeScope.Descendants, new AndCondition(
                new PropertyCondition(AutomationElement.NameProperty, "Cancel"),
                new PropertyCondition(AutomationElement.ControlTypeProperty, ControlType.Button)));
            ((InvokePattern)cancel.GetCurrentPattern(InvokePattern.Pattern)).Invoke();
            return;
        }
        using var server = DesktopUacNative.Server(args[2], systemOnly: true);
        await server.WaitForConnectionAsync(stop.Token);
        using var peer = Process.GetProcessById((int)DesktopUacNative.ClientPid(server));
        if (!string.Equals(peer.MainModule?.FileName, Environment.ProcessPath, StringComparison.OrdinalIgnoreCase))
            throw new UnauthorizedAccessException("Fixture peer image mismatch");
        field.SetFocus();
        void Check()
        {
            if (target.HasExited || DesktopController.GetInputDesktopName() != "Default" ||
                !Automation.Compare(AutomationElement.FocusedElement, field) || !field.Current.IsPassword ||
                !field.Current.IsEnabled || field.Current.IsOffscreen)
                throw new InvalidDataException("Native setup field changed");
        }
        Check();
        await UnlockWire.WriteAsync(server, new { stage = "ready" }, stop.Token);
        byte[]? bytes = null;
        char[]? chars = null;
        NativeMethods.INPUT[]? inputs = null;
        try
        {
            bytes = await UnlockWire.ReadSecretAsync(server, stop.Token);
            chars = new UTF8Encoding(false, true).GetChars(bytes);
            if (chars.AsSpan().ContainsAny('\0', '\r', '\n')) throw new InvalidDataException();
            Check(); UnlockNative.RequireReleasedModifiers();
            NativeMethods.INPUT Key(ushort value, uint flags) => new() { type = 1, union = new() { keyboard = new() { wVk = value, dwFlags = flags } } };
            inputs = new NativeMethods.INPUT[6 + chars.Length * 2];
            inputs[0] = Key(0x11, 0); inputs[1] = Key(0x41, 0); inputs[2] = Key(0x41, 2); inputs[3] = Key(0x11, 2);
            for (var i = 0; i < chars.Length; i++)
            {
                inputs[4 + 2 * i] = new() { type = 1, union = new() { keyboard = new() { wScan = chars[i], dwFlags = 4 } } };
                inputs[5 + 2 * i] = new() { type = 1, union = new() { keyboard = new() { wScan = chars[i], dwFlags = 6 } } };
            }
            inputs[^2] = Key(0x0D, 0); inputs[^1] = Key(0x0D, 2);
            if (NativeMethods.SendInput((uint)inputs.Length, inputs, Marshal.SizeOf<NativeMethods.INPUT>()) != inputs.Length)
                throw new InvalidDataException("Unknown native input delivery; never replay");
            await UnlockWire.WriteAsync(server, new { stage = "submitted_once" }, stop.Token);
        }
        finally
        {
            if (bytes is not null) CryptographicOperations.ZeroMemory(bytes);
            if (chars is not null) Array.Clear(chars);
            if (inputs is not null) Array.Clear(inputs);
        }
    }
}
