using System.IO;
using System.Reflection;
using System.Text;
using System.Text.Json;
using Org.BouncyCastle.Crypto.Digests;
using Org.BouncyCastle.Crypto.Parameters;
using Org.BouncyCastle.Crypto.Signers;

namespace MachineControl.Windows;

internal static class DesktopHelperSignature
{
    private static readonly Assembly Assembly = typeof(DesktopHelperSignature).Assembly;

    internal static bool Required { get; } = Assembly.GetCustomAttributes<AssemblyMetadataAttribute>()
        .Any(attribute => attribute.Key == "SignedDesktopHelper");

    internal static string PublicKey()
    {
        // The release job and the desktop updater already share this trust
        // anchor. A fixture can substitute a disposable key at compile time.
        var fixture = Assembly.GetCustomAttributes<AssemblyMetadataAttribute>()
            .SingleOrDefault(attribute => attribute.Key == "DesktopHelperFixturePublicKey")?.Value;
        if (fixture is not null) return fixture;
        using var source = Assembly.GetManifestResourceStream("DesktopUpdaterConfiguration.json")!;
        using var config = JsonDocument.Parse(source);
        return config.RootElement.GetProperty("plugins").GetProperty("updater").GetProperty("pubkey").GetString()!;
    }

    internal static void Verify(byte[] content, string publicKey, string detachedSignature)
    {
        var keyLines = Decode(publicKey).Split('\n');
        var signatureLines = Decode(detachedSignature).Split('\n');
        if (keyLines.Length != 2 || signatureLines.Length != 4 ||
            !keyLines[0].StartsWith("untrusted comment: ", StringComparison.Ordinal) ||
            !signatureLines[0].StartsWith("untrusted comment: ", StringComparison.Ordinal) ||
            !signatureLines[2].StartsWith("trusted comment: ", StringComparison.Ordinal))
            throw new InvalidDataException("Invalid helper signature format");
        var key = Convert.FromBase64String(keyLines[1]);
        var signature = Convert.FromBase64String(signatureLines[1]);
        var global = Convert.FromBase64String(signatureLines[3]);
        if (key.Length != 42 || signature.Length != 74 || global.Length != 64 ||
            !key.AsSpan(0, 2).SequenceEqual("Ed"u8) || !signature.AsSpan(0, 2).SequenceEqual("ED"u8) ||
            !key.AsSpan(2, 8).SequenceEqual(signature.AsSpan(2, 8)))
            throw new InvalidDataException("Unexpected helper signature key or algorithm");
        var digest = new Blake2bDigest(512);
        digest.BlockUpdate(content, 0, content.Length);
        var hash = new byte[64];
        digest.DoFinal(hash, 0);
        var verifier = new Ed25519Signer();
        verifier.Init(false, new Ed25519PublicKeyParameters(key, 10));
        verifier.BlockUpdate(hash, 0, hash.Length);
        if (!verifier.VerifySignature(signature[10..]))
            throw new UnauthorizedAccessException("Helper release signature refused");
        var comment = Encoding.UTF8.GetBytes(signatureLines[2]["trusted comment: ".Length..]);
        verifier.BlockUpdate(signature, 10, 64);
        verifier.BlockUpdate(comment, 0, comment.Length);
        if (!verifier.VerifySignature(global))
            throw new UnauthorizedAccessException("Helper release signature comment refused");
    }

    private static string Decode(string value) => Encoding.UTF8.GetString(Convert.FromBase64String(value))
        .Replace("\r\n", "\n", StringComparison.Ordinal).TrimEnd('\n');
}
