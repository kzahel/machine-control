using System.Security.Cryptography;
using System.ServiceProcess;

namespace MachineControl.Windows;

internal static class Program
{
    private static async Task<int> Main(string[] args)
    {
        if (!OperatingSystem.IsWindows())
        {
            Console.Error.WriteLine("MachineControl.Windows runs only on Windows");
            return 2;
        }

        if (args.Length == 0)
        {
            PrintUsage();
            return 2;
        }

        try
        {
            switch (args[0].ToLowerInvariant())
            {
                case "service":
                    ServiceBase.Run(new BrokerWindowsService());
                    return 0;
                case "service-console":
                    using (var cancellation = new CancellationTokenSource())
                    {
                        Console.CancelKeyPress += (_, e) =>
                        {
                            e.Cancel = true;
                            cancellation.Cancel();
                        };
                        await new BrokerHost().RunAsync(cancellation.Token);
                    }
                    return 0;
                case "session":
                    return await RunSessionAsync(args);
                case "desktop-worker":
                    return await RunDesktopWorkerAsync(args);
                case "call":
                    return await RunClientAsync(args);
                case "login":
                    return await RunLoginClientAsync(args);
                case "schema":
                    Console.WriteLine(Contract.Serialize(new
                    {
                        schema = Contract.Schema,
                        operations = new[]
                        {
                            "service.status", "service.revoke",
                            "status", "app.launch", "windows", "snapshot", "screenshot",
                            "capabilities", "invoke", "click", "key",
                            "type", "window.state",
                            "session.lock", "session.logoff",
                            "session.login (dedicated secret transport)",
                        },
                    }));
                    return 0;
                default:
                    PrintUsage();
                    return 2;
            }
        }
        catch (Exception ex)
        {
            Console.Error.WriteLine(ex.Message);
            return 1;
        }
    }

    private static async Task<int> RunSessionAsync(string[] args)
    {
        var pipe = GetOption(args, "--pipe")
            ?? throw new ArgumentException("session requires --pipe");
        var generation = GetOption(args, "--generation")
            ?? throw new ArgumentException("session requires --generation");
        await new SessionHost(pipe, generation).RunAsync(CancellationToken.None);
        return 0;
    }

    private static async Task<int> RunDesktopWorkerAsync(string[] args)
    {
        var pipe = GetOption(args, "--pipe")
            ?? throw new ArgumentException("desktop-worker requires --pipe");
        var generation = GetOption(args, "--generation")
            ?? throw new ArgumentException(
                "desktop-worker requires --generation");
        await ProtectedDesktopWorker.RunOneAsync(
            pipe,
            generation,
            CancellationToken.None);
        return 0;
    }

    private static async Task<int> RunClientAsync(string[] args)
    {
        string requestText;
        if (args.Length > 1)
        {
            requestText = args[1];
        }
        else
        {
            requestText = await Console.In.ReadToEndAsync();
        }
        var request = Contract.ParseRequest(requestText);
        var response = await PipeTransport.CallAsync(
            BrokerHost.ServicePipe,
            Contract.Serialize(request),
            TimeSpan.FromSeconds(30),
            CancellationToken.None);
        Console.WriteLine(response);
        return 0;
    }

    private static async Task<int> RunLoginClientAsync(string[] args)
    {
        var credentialKind = GetOption(args, "--kind")?.ToLowerInvariant()
            ?? throw new ArgumentException("login requires --kind pin|password");
        if (credentialKind is not ("pin" or "password"))
        {
            throw new ArgumentException("login --kind must be pin or password");
        }
        if (!Console.IsInputRedirected)
        {
            throw new ArgumentException(
                "login reads the credential from redirected standard input; " +
                "use the non-echoing login-windows.sh helper");
        }

        var buffer = new byte[257];
        byte[]? secret = null;
        try
        {
            var input = Console.OpenStandardInput();
            var total = 0;
            while (total < buffer.Length)
            {
                var read = await input.ReadAsync(
                    buffer.AsMemory(total, buffer.Length - total));
                if (read == 0) break;
                total += read;
            }
            if (total is < 1 or > 256)
            {
                throw new ArgumentException(
                    "credential must contain between 1 and 256 UTF-8 bytes");
            }
            secret = buffer[..total];
            using var cancellation = new CancellationTokenSource(
                TimeSpan.FromSeconds(50));
            var response = await PipeTransport.CallLoginAsync(
                BrokerHost.LoginPipe,
                credentialKind,
                secret,
                cancellation.Token);
            Console.WriteLine(response);
            return 0;
        }
        finally
        {
            CryptographicOperations.ZeroMemory(buffer);
            if (secret is not null)
            {
                CryptographicOperations.ZeroMemory(secret);
            }
        }
    }

    private static string? GetOption(string[] args, string name)
    {
        for (var i = 0; i + 1 < args.Length; i++)
        {
            if (string.Equals(args[i], name, StringComparison.OrdinalIgnoreCase))
            {
                return args[i + 1];
            }
        }
        return null;
    }

    private static void PrintUsage()
    {
        Console.Error.WriteLine(
            "usage: machine-control-windows " +
            "service|service-console|session|desktop-worker|call|login|schema");
    }
}
