using System.IO;
using System.IO.Pipes;
using System.Text.Json.Nodes;

namespace MachineControl.Windows;

internal static class BrowserNativeHost
{
    internal static async Task<int> RunAsync(string origin)
    {
        if (origin != BrowserWire.Origin || !Console.IsInputRedirected || !Console.IsOutputRedirected)
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
        stop.CancelAfter(Timeout.InfiniteTimeSpan);
        await using var input = Console.OpenStandardInput();
        await using var output = Console.OpenStandardOutput();
        var inbound = Task.Run(async () =>
        {
            while (await BrowserWire.ReadAsync(input, stop.Token) is { } frame)
            {
                // Provider-to-resident frames include screenshots, up to the
                // owned 16 MiB input ceiling rather than Chrome's 1 MiB output.
                var bytes = System.Text.Json.JsonSerializer.SerializeToUtf8Bytes(frame, Contract.Json);
                var header = BitConverter.GetBytes(bytes.Length);
                await pipe.WriteAsync(header, stop.Token);
                await pipe.WriteAsync(bytes, stop.Token);
                await pipe.FlushAsync(stop.Token);
            }
        });
        var outbound = Task.Run(async () =>
        {
            while (await BrowserWire.ReadAsync(pipe, stop.Token) is { } frame)
                await BrowserWire.WriteAsync(output, frame, stop.Token);
        });
        var completed = await Task.WhenAny(inbound, outbound);
        stop.Cancel();
        pipe.Close();
        // Chrome's inherited stdin is a synchronous anonymous pipe. A blocked
        // ReadFile cannot be canceled by a managed cancellation token. Do not
        // await that background reader after the resident disconnects: returning
        // from this native-host-only Main ends the process and closes its handles,
        // while the user's browser continues running.
        try { await completed; }
        catch (Exception ex) when (ex is IOException or OperationCanceledException or ObjectDisposedException) { }
        return 0;
    }
}
