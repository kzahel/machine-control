using System.Text;
using MachineControl.Windows;
using Org.BouncyCastle.Crypto.Digests;
using Org.BouncyCastle.Crypto.Parameters;
using Org.BouncyCastle.Crypto.Signers;

internal static class DesktopHelperSignatureFixtures
{
    internal static void Run()
    {
        var key = new Ed25519PrivateKeyParameters(new byte[32], 0);
        var keyId = "fixture1"u8.ToArray();
        var publicKey = Text("untrusted comment: fixture\n" +
            Convert.ToBase64String([.. "Ed"u8, .. keyId, .. key.GeneratePublicKey().GetEncoded()]) + "\n");
        var payload = "helper release manifest"u8.ToArray();
        var digest = new Blake2bDigest(512);
        var hash = new byte[64];
        digest.BlockUpdate(payload, 0, payload.Length);
        digest.DoFinal(hash, 0);
        var signer = new Ed25519Signer();
        signer.Init(true, key);
        signer.BlockUpdate(hash, 0, hash.Length);
        var signature = signer.GenerateSignature();
        var comment = "fixture comment";
        var message = Encoding.UTF8.GetBytes(comment);
        signer.BlockUpdate(signature, 0, signature.Length);
        signer.BlockUpdate(message, 0, message.Length);
        var envelope = $"untrusted comment: fixture\n{Convert.ToBase64String([.. "ED"u8, .. keyId, .. signature])}\n" +
            $"trusted comment: {comment}\n{Convert.ToBase64String(signer.GenerateSignature())}\n";

        DesktopHelperSignature.Verify(payload, publicKey, Text(envelope));
        Refused(() => DesktopHelperSignature.Verify("different manifest"u8.ToArray(), publicKey, Text(envelope)));
        Refused(() => DesktopHelperSignature.Verify(payload, publicKey, Text(envelope.Replace(comment, "changed", StringComparison.Ordinal))));
        var otherPublicKey = new Ed25519PrivateKeyParameters(Enumerable.Repeat((byte)1, 32).ToArray(), 0)
            .GeneratePublicKey().GetEncoded();
        var otherKey = Convert.ToBase64String([.. "Ed"u8, .. keyId, .. otherPublicKey]);
        Refused(() => DesktopHelperSignature.Verify(payload, Text("untrusted comment: fixture\n" + otherKey), Text(envelope)));
        Console.WriteLine("Protected helper signature, key binding, and tamper contracts passed");
    }

    private static string Text(string value) => Convert.ToBase64String(Encoding.UTF8.GetBytes(value));

    private static void Refused(Action verify)
    {
        try { verify(); }
        catch (UnauthorizedAccessException) { return; }
        throw new Exception("An invalid helper release signature was accepted");
    }
}
