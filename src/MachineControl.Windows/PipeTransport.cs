using System.IO;
using System.IO.Pipes;
using System.Security.AccessControl;
using System.Security.Principal;
using System.Text;

namespace MachineControl.Windows;

internal static class PipeTransport
{
    private static readonly byte[] LoginMagic = "MCL1"u8.ToArray();

    public static NamedPipeServerStream CreateServiceServer(string pipeName)
    {
        var security = new PipeSecurity();
        security.AddAccessRule(new PipeAccessRule(
            new SecurityIdentifier(WellKnownSidType.LocalSystemSid, null),
            PipeAccessRights.FullControl,
            AccessControlType.Allow));
        security.AddAccessRule(new PipeAccessRule(
            new SecurityIdentifier(WellKnownSidType.AuthenticatedUserSid, null),
            PipeAccessRights.ReadWrite | PipeAccessRights.CreateNewInstance,
            AccessControlType.Allow));
        return NamedPipeServerStreamAcl.Create(
            pipeName,
            PipeDirection.InOut,
            1,
            PipeTransmissionMode.Byte,
            PipeOptions.Asynchronous,
            64 * 1024,
            64 * 1024,
            security);
    }

    public static NamedPipeServerStream CreateSystemServer(string pipeName) =>
        new(
            pipeName,
            PipeDirection.InOut,
            1,
            PipeTransmissionMode.Byte,
            PipeOptions.Asynchronous,
            64 * 1024,
            64 * 1024);

    public static NamedPipeServerStream CreateSystemOnlyServer(string pipeName)
    {
        var security = new PipeSecurity();
        security.AddAccessRule(new PipeAccessRule(
            new SecurityIdentifier(WellKnownSidType.LocalSystemSid, null),
            PipeAccessRights.FullControl,
            AccessControlType.Allow));
        return NamedPipeServerStreamAcl.Create(
            pipeName,
            PipeDirection.InOut,
            1,
            PipeTransmissionMode.Byte,
            PipeOptions.Asynchronous,
            4096,
            4096,
            security);
    }

    public static async Task<string> CallLoginAsync(
        string pipeName,
        string credentialKind,
        byte[] secret,
        CancellationToken cancellationToken)
    {
        if (secret.Length is < 1 or > 256)
        {
            throw new InvalidDataException(
                "credential must contain between 1 and 256 UTF-8 bytes");
        }
        var kind = credentialKind.ToLowerInvariant() switch
        {
            "pin" => (byte)1,
            "password" => (byte)2,
            _ => throw new InvalidDataException(
                "credential kind must be pin or password"),
        };
        await using var pipe = new NamedPipeClientStream(
            ".",
            pipeName,
            PipeDirection.InOut,
            PipeOptions.Asynchronous);
        await pipe.ConnectAsync(cancellationToken);
        await pipe.WriteAsync(LoginMagic, cancellationToken);
        await pipe.WriteAsync(new[]
        {
            kind,
            (byte)(secret.Length & 0xff),
            (byte)(secret.Length >> 8),
        }, cancellationToken);
        await pipe.WriteAsync(secret, cancellationToken);
        await pipe.FlushAsync(cancellationToken);
        using var reader = new StreamReader(
            pipe,
            Encoding.UTF8,
            false,
            4096,
            leaveOpen: true);
        return await reader.ReadLineAsync(cancellationToken)
            ?? throw new EndOfStreamException(
                "Login pipe closed without a response");
    }

    public static async Task<(string CredentialKind, byte[] Secret,
        StreamWriter Writer)> AcceptLoginAsync(
        NamedPipeServerStream server,
        CancellationToken cancellationToken)
    {
        await server.WaitForConnectionAsync(cancellationToken);
        var header = new byte[7];
        await server.ReadExactlyAsync(header, cancellationToken);
        if (!header.AsSpan(0, 4).SequenceEqual(LoginMagic))
        {
            throw new InvalidDataException("Invalid login protocol header");
        }
        var credentialKind = header[4] switch
        {
            1 => "pin",
            2 => "password",
            _ => throw new InvalidDataException(
                "Invalid login credential kind"),
        };
        var length = header[5] | (header[6] << 8);
        if (length is < 1 or > 256)
        {
            throw new InvalidDataException(
                "Invalid login credential length");
        }
        var secret = new byte[length];
        await server.ReadExactlyAsync(secret, cancellationToken);
        var writer = new StreamWriter(
            server,
            new UTF8Encoding(false),
            4096,
            leaveOpen: true)
        {
            AutoFlush = true,
        };
        return (credentialKind, secret, writer);
    }

    public static async Task SendSecretOnceAsync(
        string pipeName,
        byte[] secret,
        TimeSpan timeout,
        CancellationToken cancellationToken)
    {
        using var timeoutSource = CancellationTokenSource.CreateLinkedTokenSource(
            cancellationToken);
        timeoutSource.CancelAfter(timeout);
        await using var server = CreateSystemOnlyServer(pipeName);
        await server.WaitForConnectionAsync(timeoutSource.Token);
        var length = new[]
        {
            (byte)(secret.Length & 0xff),
            (byte)(secret.Length >> 8),
        };
        await server.WriteAsync(length, timeoutSource.Token);
        await server.WriteAsync(secret, timeoutSource.Token);
        await server.FlushAsync(timeoutSource.Token);
    }

    public static async Task<byte[]> ReceiveSecretOnceAsync(
        string pipeName,
        TimeSpan timeout,
        CancellationToken cancellationToken)
    {
        using var timeoutSource = CancellationTokenSource.CreateLinkedTokenSource(
            cancellationToken);
        timeoutSource.CancelAfter(timeout);
        await using var pipe = new NamedPipeClientStream(
            ".",
            pipeName,
            PipeDirection.In,
            PipeOptions.Asynchronous);
        await pipe.ConnectAsync(timeoutSource.Token);
        var lengthBytes = new byte[2];
        await pipe.ReadExactlyAsync(lengthBytes, timeoutSource.Token);
        var length = lengthBytes[0] | (lengthBytes[1] << 8);
        if (length is < 1 or > 256)
        {
            throw new InvalidDataException(
                "Invalid protected credential length");
        }
        var secret = new byte[length];
        await pipe.ReadExactlyAsync(secret, timeoutSource.Token);
        return secret;
    }

    public static async Task<string> CallAsync(
        string pipeName,
        string request,
        TimeSpan timeout,
        CancellationToken cancellationToken)
    {
        using var timeoutSource = CancellationTokenSource.CreateLinkedTokenSource(
            cancellationToken);
        timeoutSource.CancelAfter(timeout);
        await using var pipe = new NamedPipeClientStream(
            ".",
            pipeName,
            PipeDirection.InOut,
            PipeOptions.Asynchronous);
        await pipe.ConnectAsync(timeoutSource.Token);
        using var reader = new StreamReader(
            pipe,
            Encoding.UTF8,
            false,
            64 * 1024,
            leaveOpen: true);
        await using var writer = new StreamWriter(
            pipe,
            new UTF8Encoding(false),
            64 * 1024,
            leaveOpen: true)
        {
            AutoFlush = true,
        };
        await writer.WriteLineAsync(request.AsMemory(), timeoutSource.Token);
        return await reader.ReadLineAsync(timeoutSource.Token)
            ?? throw new EndOfStreamException("Pipe closed without a response");
    }

    public static async Task<(string Request, StreamWriter Writer)> AcceptAsync(
        NamedPipeServerStream server,
        CancellationToken cancellationToken)
    {
        await server.WaitForConnectionAsync(cancellationToken);
        var reader = new StreamReader(
            server,
            Encoding.UTF8,
            false,
            64 * 1024,
            leaveOpen: true);
        var writer = new StreamWriter(
            server,
            new UTF8Encoding(false),
            64 * 1024,
            leaveOpen: true)
        {
            AutoFlush = true,
        };
        var request = await reader.ReadLineAsync(cancellationToken)
            ?? throw new EndOfStreamException("Pipe closed before a request");
        return (request, writer);
    }
}
