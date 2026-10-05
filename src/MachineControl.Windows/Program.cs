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
            if (args[0].StartsWith("chrome-extension://", StringComparison.Ordinal))
                return await BrowserNativeHost.RunAsync(args[0]);
            switch (args[0].ToLowerInvariant())
            {
                case "uac-service":
                    ServiceBase.Run(new DesktopUacWindowsService());
                    return 0;
                case "uac-worker":
                    await DesktopUacWorker.RunAsync(GetOption(args, "--pipe") ?? throw new ArgumentException("--pipe required"), CancellationToken.None);
                    return 0;
                case "relock-guardian":
                    return await DesktopRelockGuardian.RunAsync(GetOption(args, "--pipe") ?? throw new ArgumentException("--pipe required"));
                case "unlock-desktop-setup":
                    return DesktopUacSetup.RequestUnlockApproval();
                case "uac-setup":
                    return DesktopUacSetup.Request(args.Contains("--remove"));
                case "uac-install":
                    return DesktopUacSetup.Install();
                case "uac-remove":
                    return DesktopUacSetup.Remove();
                case "uac-resolve":
                    Console.WriteLine(DesktopUacSetup.Resolve());
                    return 0;
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
                case "user":
                    using (var cancellation = new CancellationTokenSource())
                    {
                        Console.CancelKeyPress += (_, e) => { e.Cancel = true; cancellation.Cancel(); };
                        await new UserHost(GetOption(args, "--instance") ?? "default")
                            .RunAsync(cancellation.Token);
                    }
                    return 0;
                case "browser-unregister":
                    BrowserRegistration.RemoveOwned();
                    return 0;
                case "browser-install-prepare":
                    if (args.Length != 2) throw new ArgumentException("Installation directory required");
                    BrowserInstaller.Prepare(args[1]);
                    return 0;
                case "browser-install-finish":
                    if (args.Length != 2) throw new ArgumentException("Installation directory required");
                    BrowserInstaller.Finish(args[1]);
                    return 0;
                case "desktop":
                    return await DesktopHost.RunAsync();
                case "desktop-worker":
                    return await RunDesktopWorkerAsync(args);
                case "channel":
                    if (GetOption(args, "--profile") != "user") throw new ArgumentException("Admission requires a user resident profile");
                    await PipeTransport.ProxyAsync(RuntimeProfile.UserPipe(GetOption(args, "--instance") ?? "desktop",
                        int.Parse(GetOption(args, "--session-id") ?? RuntimeProfile.SessionId.ToString())));
                    return 0;
                case "call":
                    return await RunClientAsync(args);
                case "input-call":
                    return await RunLocalInputClientAsync(args);
                case "login":
                    return await RunLoginClientAsync(args);
                case "unlock-service":
                    ServiceBase.Run(new UnlockWindowsService(GetOption(args, "--instance") ?? "default"));
                    return 0;
                case "unlock-worker":
                    return await UnlockWorker.RunAsync(GetOption(args, "--instance") ?? "default",
                        GetOption(args, "--pipe") ?? throw new ArgumentException("--pipe required"));
                case "unlock-arm":
                    return UnlockAdmin.Arm(GetOption(args, "--instance") ?? "default",
                        GetOption(args, "--proposal") ?? throw new ArgumentException("--proposal required"));
                case "unlock":
                    return await UnlockClient.RunAsync(GetOption(args, "--instance") ?? "default",
                        GetOption(args, "--grant"), GetOption(args, "--key"),
                        GetOption(args, "--kind") ?? "password", args.Contains("--relay"), args.Contains("--status"));
                case "schema":
                    Console.WriteLine(Contract.Serialize(new
                    {
                        schema = Contract.Schema,
                        operations = new[]
                        {
                            "service.status", "service.revoke",
                            "status", "app.launch", "app.activate", "windows",
                            "snapshot", "screenshot",
                            "capabilities", "invoke", "click", "key", "key.timeline",
                            "key.delayed_hold",
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
        var profile = GetOption(args, "--profile") ?? "appliance";
        if (profile is not ("user" or "appliance"))
            throw new ArgumentException("--profile must be user or appliance");
        if (profile == "appliance" &&
            (GetOption(args, "--instance") is not null || GetOption(args, "--session-id") is not null))
            throw new ArgumentException("User endpoint selectors require --profile user");
        var pipe = profile == "user"
            ? RuntimeProfile.UserPipe(GetOption(args, "--instance") ?? "default",
                int.Parse(GetOption(args, "--session-id") ?? RuntimeProfile.SessionId.ToString()))
            : BrokerHost.ServicePipe;
        string requestText;
        if (args.Length > 1 && !args[1].StartsWith("--", StringComparison.Ordinal))
        {
            requestText = args[1];
        }
        else
        {
            requestText = await Console.In.ReadToEndAsync();
        }
        var request = Contract.ParseRequest(requestText);
        var defaultTimeout = request.Operation == "grant.request"
            ? (Math.Clamp(request.TimeoutSeconds ?? 120, 5, 600) + 15) * 1000 : args.Contains("--instance") && GetOption(args, "--instance") == "desktop" &&
                request.Operation.StartsWith("browser.", StringComparison.Ordinal) ? 60000 : 30000;
        var timeoutMs = int.Parse(GetOption(args, "--timeout-ms") ?? defaultTimeout.ToString());
        if (timeoutMs is < 100 or > 615000)
            throw new ArgumentException("--timeout-ms must be 100-615000");
        var response = await PipeTransport.CallAsync(
            pipe,
            Contract.Serialize(request),
            TimeSpan.FromMilliseconds(timeoutMs),
            CancellationToken.None);
        Console.WriteLine(response);
        return 0;
    }

    private static async Task<int> RunLocalInputClientAsync(string[] args)
    {
        string requestText;
        var hasRequestArgument = args.Length > 1 && !args[1].StartsWith("--", StringComparison.Ordinal);
        if (hasRequestArgument)
        {
            requestText = args[1];
        }
        else
        {
            requestText = await Console.In.ReadToEndAsync();
        }
        var request = Contract.ParseRequest(requestText);
        if (!new[] { "key.timeline", "key.delayed_hold" }.Contains(
                request.Operation,
                StringComparer.OrdinalIgnoreCase))
        {
            throw new ArgumentException(
                "input-call accepts only typed bounded key timeline operations");
        }
        return await RunClientAsync([
            "call", Contract.Serialize(request),
            .. args.Skip(hasRequestArgument ? 2 : 1),
        ]);
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
            "service|service-console|session|desktop-worker|user [--instance NAME]|" +
            "input-call [JSON]|call [JSON] [--profile appliance|user] [--instance NAME] [--session-id ID]|login|" +
            "unlock [--status|--relay] [--instance NAME] [--grant FILE --key FILE] [--kind password|pin]|schema");
    }
}
