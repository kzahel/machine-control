using System.IO;
using System.IO.Pipes;
using System.Security.Cryptography;
using System.Security.Principal;
using System.Text;
using System.Text.Json;

namespace MachineControl.Windows;

internal static class UnlockClient
{
    public static async Task<int> RunAsync(string instance, string? grantFile, string? keyFile,
        string kind, bool relay, bool status)
    {
        using var stop = new CancellationTokenSource(TimeSpan.FromSeconds(70));
        await using var pipe = new NamedPipeClientStream(".", UnlockPolicy.Pipe(instance), PipeDirection.InOut,
            PipeOptions.Asynchronous, TokenImpersonationLevel.Identification);
        await pipe.ConnectAsync(5000, stop.Token);
        UnlockNative.RequireServicePeer(pipe, instance);
        var input = Console.OpenStandardInput();
        var output = Console.OpenStandardOutput();
        if (relay)
        {
            // JSON handshake followed by one binary credential frame. No reader
            // may buffer past the newline into the secret transport.
            var hello = await UnlockWire.ReadLineAsync(input, stop.Token);
            await WriteLineAsync(pipe, hello, stop.Token);
        }
        else await UnlockWire.WriteAsync(pipe, new UnlockHello(status ? "status" : "unlock", kind), stop.Token);
        var text = await UnlockWire.ReadLineAsync(pipe, stop.Token);
        using var frame = JsonDocument.Parse(text);
        if (frame.RootElement.GetProperty("stage").GetString() != "challenge")
        {
            await WriteLineAsync(output, text, stop.Token);
            return status && frame.RootElement.GetProperty("stage").GetString() == "status" ? 0 : 1;
        }
        var challengeText = frame.RootElement.GetProperty("challenge").GetString()!;
        if (relay)
        {
            await WriteLineAsync(output, text, stop.Token);
            await WriteLineAsync(pipe, await UnlockWire.ReadLineAsync(input, stop.Token), stop.Token);
        }
        else
        {
            var grant = UnlockPolicy.Validate(JsonSerializer.Deserialize<UnlockGrant>(File.ReadAllText(grantFile!), Contract.Json)!);
            var challenge = JsonSerializer.Deserialize<UnlockChallenge>(challengeText, Contract.Json)!;
            ValidateChallenge(challenge, grant, instance, kind);
            using var key = ECDsa.Create();
            key.ImportFromPem(File.ReadAllText(keyFile!));
            if (Convert.ToBase64String(key.ExportSubjectPublicKeyInfo()) != grant.ControllerPublicKey)
                throw new InvalidDataException("Controller key does not match grant");
            var signature = key.SignData(Encoding.UTF8.GetBytes(challengeText), HashAlgorithmName.SHA256,
                DSASignatureFormat.Rfc3279DerSequence);
            await UnlockWire.WriteAsync(pipe, new UnlockProof(Convert.ToBase64String(signature)), stop.Token);
        }
        text = await UnlockWire.ReadLineAsync(pipe, stop.Token);
        using var readiness = JsonDocument.Parse(text);
        if (readiness.RootElement.GetProperty("stage").GetString() != "ready")
        { await WriteLineAsync(output, text, stop.Token); return 1; }
        UnlockNative.RequireServicePeer(pipe, instance);
        if (relay) await WriteLineAsync(output, text, stop.Token);
        else Console.Error.WriteLine("Authorized credential field ready; reading redirected credential input once.");
        byte[]? secret = null;
        try
        {
            if (relay) secret = await UnlockWire.ReadSecretAsync(input, stop.Token);
            else
            {
                if (!Console.IsInputRedirected) throw new InvalidDataException("Redirect a non-echoing credential source to stdin");
                secret = await ReadCredentialAsync(input, stop.Token);
            }
            await UnlockWire.WriteSecretAsync(pipe, secret, stop.Token);
        }
        finally { if (secret is not null) CryptographicOperations.ZeroMemory(secret); }
        text = await UnlockWire.ReadLineAsync(pipe, stop.Token);
        await WriteLineAsync(output, text, stop.Token);
        using var result = JsonDocument.Parse(text);
        return result.RootElement.TryGetProperty("result", out var value) &&
            value.TryGetProperty("effect", out var effect) && effect.GetString() == "confirmed" ? 0 : 1;
    }

    internal static void ValidateChallenge(UnlockChallenge challenge, UnlockGrant grant, string instance, string kind)
    {
        if (challenge.Protocol != UnlockService.Protocol || challenge.Instance != instance ||
            challenge.GrantRevision != grant.Revision || challenge.TargetUserSid != grant.TargetUserSid ||
            challenge.ControllerFingerprint != UnlockPolicy.Fingerprint(grant) || challenge.CredentialKind != kind ||
            challenge.Deadline <= DateTimeOffset.UtcNow || challenge.Deadline > DateTimeOffset.UtcNow.AddMinutes(1) ||
            challenge.Nonce.Length != 64 || !Guid.TryParseExact(challenge.ServiceGeneration, "N", out _))
            throw new InvalidDataException("Unlock challenge does not match approved grant");
    }

    private static async Task<byte[]> ReadCredentialAsync(Stream input, CancellationToken stop)
    {
        var buffer = new byte[257];
        try
        {
            var total = 0;
            while (total < buffer.Length)
            {
                var count = await input.ReadAsync(buffer.AsMemory(total), stop);
                if (count == 0) break;
                total += count;
            }
            if (total is < 1 or > 256) throw new InvalidDataException("Credential must be 1-256 UTF-8 bytes");
            return buffer[..total];
        }
        finally { CryptographicOperations.ZeroMemory(buffer); }
    }

    private static async Task WriteLineAsync(Stream stream, string text, CancellationToken stop)
    {
        await stream.WriteAsync(Encoding.UTF8.GetBytes(text + "\n"), stop);
        await stream.FlushAsync(stop);
    }
}
