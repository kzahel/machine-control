using System.Diagnostics;
using System.IO.Pipes;
using System.Text;
using MachineControl.Windows;

internal static class RetainedPipeProxyFixtures
{
    internal static async Task Child(string pipeName)
    {
        using var pipe = new NamedPipeClientStream(".", pipeName, PipeDirection.InOut, PipeOptions.Asynchronous);
        await pipe.ConnectAsync(5000);
        if (!ThreadPool.SetMinThreads(1, 1) || !ThreadPool.SetMaxThreads(1, 1))
            throw new Exception("Cannot bound the proxy child worker pool");
        await RetainedPipeProxy.RunAsync(Console.OpenStandardInput(), Console.OpenStandardOutput(), pipe);
    }

    internal static async Task RunAsync()
    {
        await Exchange(residentEnds: true);
        await Exchange(residentEnds: false);
        Console.WriteLine("Retained stdio proxy remains responsive with one worker and either peer EOF");
    }

    private static async Task Exchange(bool residentEnds)
    {
        var pipeName = "mc-proxy-" + Guid.NewGuid().ToString("n");
        using var pipe = new NamedPipeServerStream(pipeName, PipeDirection.InOut, 1,
            PipeTransmissionMode.Byte, PipeOptions.Asynchronous);
        var start = new ProcessStartInfo(Environment.ProcessPath!)
        {
            RedirectStandardInput = true,
            RedirectStandardOutput = true,
            RedirectStandardError = true,
            UseShellExecute = false,
        };
        if (Path.GetFileNameWithoutExtension(Environment.ProcessPath) == "dotnet")
            start.ArgumentList.Add(typeof(RetainedPipeProxyFixtures).Assembly.Location);
        start.ArgumentList.Add("--stdio-proxy-without-pool");
        start.ArgumentList.Add(pipeName);
        using var child = Process.Start(start) ?? throw new Exception("Proxy child did not start");
        try
        {
            using var deadline = new CancellationTokenSource(TimeSpan.FromSeconds(8));
            await pipe.WaitForConnectionAsync(deadline.Token);
            {
                using var reader = new StreamReader(pipe, Encoding.UTF8, leaveOpen: true);
                using var writer = new StreamWriter(pipe, new UTF8Encoding(false), leaveOpen: true) { AutoFlush = true };
                for (var i = 0; i < 10; i++)
                {
                    var frame = "owned-frame-" + i;
                    await child.StandardInput.WriteLineAsync(frame);
                    await child.StandardInput.FlushAsync();
                    if (await reader.ReadLineAsync(deadline.Token) != frame)
                        throw new Exception("Proxy changed a request frame");
                    await writer.WriteLineAsync(frame);
                    if (await child.StandardOutput.ReadLineAsync(deadline.Token) != frame)
                        throw new Exception("Proxy changed a reply frame");
                }
            }
            // Resident EOF must terminate the proxy while its caller's stdin
            // remains open. No later input is needed to release ownership.
            if (residentEnds) pipe.Dispose();
            else
            {
                child.StandardInput.Close();
                if (await pipe.ReadAsync(new byte[1], deadline.Token) != 0)
                    throw new Exception("Caller EOF did not close the resident transport");
            }
            await child.WaitForExitAsync(deadline.Token);
            if (child.ExitCode != 0) throw new Exception("Proxy child failed");
        }
        finally
        {
            if (!child.HasExited) child.Kill(entireProcessTree: true);
            child.WaitForExit();
        }
    }
}
