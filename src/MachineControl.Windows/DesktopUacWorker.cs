using System.Diagnostics;
using System.IO;
using System.IO.Pipes;
using System.Security.Principal;
using System.Text;
using System.Text.Json;
using System.Windows.Automation;

namespace MachineControl.Windows;

internal static class DesktopUacWorker
{
    internal static int ConsentPid(uint session)
    {
        var matches = new List<int>();
        foreach (var process in Process.GetProcessesByName("consent"))
            using (process)
            {
                try
                {
                    if (process.SessionId == session && string.Equals(process.MainModule?.FileName,
                        Path.Combine(Environment.SystemDirectory, "consent.exe"), StringComparison.OrdinalIgnoreCase)) matches.Add(process.Id);
                }
                catch (System.ComponentModel.Win32Exception) { }
                catch (InvalidOperationException) { }
            }
        return matches.Count == 1 ? matches[0] : 0;
    }
    internal static AutomationElement ConsentUi(int consentPid)
    {
        // consent.exe also owns the secure background Pane. Require the
        // single visible, enabled dialog Window rather than treating that
        // independently observed stock background as a second prompt.
        var windows = AutomationElement.RootElement.FindAll(TreeScope.Children, new AndCondition(
            new PropertyCondition(AutomationElement.ProcessIdProperty, consentPid),
            new PropertyCondition(AutomationElement.ControlTypeProperty, ControlType.Window),
            new PropertyCondition(AutomationElement.IsOffscreenProperty, false),
            new PropertyCondition(AutomationElement.IsEnabledProperty, true)));
        if (windows.Count != 1) throw new DesktopAccessRefusedException("uac_prompt_ambiguous");
        var edits = windows[0].FindAll(TreeScope.Descendants, new OrCondition(
            new PropertyCondition(AutomationElement.ControlTypeProperty, ControlType.Edit), new PropertyCondition(AutomationElement.IsPasswordProperty, true)));
        if (edits.Count != 0) throw new DesktopAccessRefusedException("uac_credentials_unsupported");
        return windows[0];
    }
    internal static async Task RunAsync(string name, CancellationToken cancellation)
    {
        using var identity = WindowsIdentity.GetCurrent();
        if (!identity.IsSystem || RuntimeProfile.SessionId == 0) throw new UnauthorizedAccessException("UAC worker requires SYSTEM in a console session");
        var previousDesktop = "";
        var epoch = Guid.NewGuid().ToString("n");
        var epochGate = new object();
        using var lifetime = CancellationTokenSource.CreateLinkedTokenSource(cancellation);
        Process? resident = null;
        _ = Task.Run(async () =>
        {
            try
            {
                while (!lifetime.IsCancellationRequested)
                {
                    if (resident?.HasExited == true) { lifetime.Cancel(); break; }
                    var input = DesktopController.GetInputDesktopName();
                    lock (epochGate)
                        if (input != previousDesktop) { previousDesktop = input; epoch = Guid.NewGuid().ToString("n"); }
                    await Task.Delay(100, lifetime.Token);
                }
            }
            catch (Exception ex) when (ex is OperationCanceledException or System.ComponentModel.Win32Exception or InvalidOperationException) { lifetime.Cancel(); }
        });
        cancellation = lifetime.Token;
        while (!cancellation.IsCancellationRequested)
        {
            using var pipe = DesktopUacNative.Server(name, systemOnly: true);
            await pipe.WaitForConnectionAsync(cancellation);
            using var reader = new StreamReader(pipe, Encoding.UTF8, false, 4096, true);
            var frame = JsonSerializer.Deserialize<DesktopUacFrame>(await DesktopUacNative.ReadAsync(reader, cancellation), Contract.Json) ?? throw new InvalidDataException("UAC frame required");
            DesktopUacNative.RequireSystem(pipe);
            resident ??= Process.GetProcessById((int)frame.ResidentPid);
            string desktop, requestEpoch;
            lock (epochGate)
            {
                desktop = DesktopController.GetInputDesktopName();
                if (desktop != previousDesktop) { previousDesktop = desktop; epoch = Guid.NewGuid().ToString("n"); }
                requestEpoch = epoch;
            }
            var generation = frame.Generation + ":uac:" + requestEpoch;
            var request = frame.Request with { ExpectedGeneration = null };
            DesktopSafety.OperatorProcessId = frame.OperatorPid;
            DesktopSafety.ExternalCheck = (_, _, resolvedPid) =>
            {
                if (NativeMethods.WTSGetActiveConsoleSessionId() != (uint)RuntimeProfile.SessionId ||
                    SessionStateInspector.IsLocked((uint)RuntimeProfile.SessionId) != false || DesktopController.GetInputDesktopName() != desktop) return "desktop_changed";
                lock (epochGate) if (epoch != requestEpoch) return "desktop_changed";
                var consentPid = desktop == "Winlogon" ? ConsentPid((uint)RuntimeProfile.SessionId) : 0;
                var denial = DesktopUacPolicy.Refusal(frame.Request, true, true, desktop, consentPid > 0);
                if (denial is not null) return denial;
                if (desktop == "Winlogon" && DesktopController.GetCurrentDesktopName() == "Winlogon") _ = ConsentUi(consentPid);
                try
                {
                    using var guard = new NamedPipeClientStream(".", frame.GuardPipe, PipeDirection.InOut, PipeOptions.None, TokenImpersonationLevel.Identification);
                    guard.Connect(2000);
                    DesktopUacNative.RequireServer(guard, frame.ResidentPid);
                    using var output = new StreamWriter(guard, new UTF8Encoding(false), 4096, true) { AutoFlush = true };
                    output.WriteLine(Contract.Serialize(new { processId = resolvedPid }));
                    using var input = new StreamReader(guard, Encoding.UTF8, false, 4096, true);
                    using var timeout = new CancellationTokenSource(TimeSpan.FromSeconds(3));
                    var response = JsonSerializer.Deserialize<JsonElement>(DesktopUacNative.ReadAsync(input, timeout.Token).GetAwaiter().GetResult());
                    return response.TryGetProperty("error", out var error) ? error.GetString() : null;
                }
                catch (Exception ex) when (ex is IOException or UnauthorizedAccessException or OperationCanceledException or JsonException) { return "uac_authority_lost"; }
            };
            Result result;
            byte[]? capture = null;
            try
            {
                result = await DesktopController.ExecuteAsync(request, generation, cancellation);
                if (result.Accepted && request.Operation == "screenshot")
                {
                    var data = JsonSerializer.SerializeToElement(result.Data, Contract.Json);
                    var path = Path.Combine(RuntimeProfile.ArtifactRoot, data.GetProperty("artifactId").GetString()! + ".png");
                    if (new FileInfo(path).Length > 16 * 1024 * 1024) throw new IOException("Protected capture exceeds 16 MiB");
                    capture = await File.ReadAllBytesAsync(path, cancellation);
                    File.Delete(path);
                }
                result = result with { Generation = frame.Generation, ActualRoute = "windows.desktop_uac/" + result.ActualRoute };
            }
            finally { DesktopSafety.ExternalCheck = null; }
            await using var writer = new StreamWriter(pipe, new UTF8Encoding(false), 4096, true) { AutoFlush = true };
            await writer.WriteLineAsync(Contract.Serialize(new DesktopUacReply(result, capture)).AsMemory(), cancellation);
        }
    }
}
