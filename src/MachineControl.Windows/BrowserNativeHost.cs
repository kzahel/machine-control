using System.IO;
using System.IO.Pipes;
using System.Text.Json.Nodes;

namespace MachineControl.Windows;

internal static class BrowserNativeHost
{
    internal static async Task<int> RunAsync(string origin)
    {
        if (!BrowserWire.Allowed(origin) || !Console.IsInputRedirected || !Console.IsOutputRedirected)
            throw new ArgumentException("Browser origin or transport refused");
        RuntimeProfile.ConfigureUser("desktop");
        using var stop = new CancellationTokenSource(TimeSpan.FromSeconds(5));
        await using var pipe = new NamedPipeClientStream(".",
            RuntimeProfile.UserPipe("desktop-browser", RuntimeProfile.SessionId),
            PipeDirection.InOut, PipeOptions.Asynchronous);
        await pipe.ConnectAsync(3000, stop.Token);
        await BrowserWire.WriteAsync(pipe, new JsonObject { ["type"] = "register", ["origin"] = origin }, stop.Token);
        var registered = await BrowserWire.ReadAsync(pipe, stop.Token);
        if (registered?["type"]?.GetValue<string>() != "registered") return 1;
        var input = Console.OpenStandardInput();
        var output = Console.OpenStandardOutput();
        try
        {
            await RetainedPipeProxy.RunAsync(() =>
            {
                while (BrowserWire.Read(input) is { } frame)
                    BrowserWire.Write(pipe, frame, BrowserWire.MaximumInput);
            }, () =>
            {
                while (BrowserWire.Read(pipe) is { } frame)
                    BrowserWire.Write(output, frame);
            });
        }
        catch (Exception ex) when (ex is IOException or OperationCanceledException or ObjectDisposedException) { }
        return 0;
    }
}
