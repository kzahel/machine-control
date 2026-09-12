using System.Security.Cryptography;
using System.Text;
using MachineControl.Windows;

static void Assert(bool value, string message)
{
    if (!value) throw new Exception(message);
}
static void Refuses(Action action, string label)
{
    try { action(); }
    catch { return; }
    throw new Exception("Expected refusal: " + label);
}
using var controller = ECDsa.Create(ECCurve.NamedCurves.nistP256);
using var attacker = ECDsa.Create(ECCurve.NamedCurves.nistP256);
var grant = new UnlockGrant(UnlockPolicy.Schema, Guid.NewGuid().ToString("n"),
    "S-1-5-21-100-200-300-1001", "S-1-5-21-100-200-300-1002",
    Convert.ToBase64String(controller.ExportSubjectPublicKeyInfo()), null);
UnlockPolicy.Validate(grant);
Refuses(() => UnlockPolicy.Validate(grant with { ExpiresAt = DateTimeOffset.UtcNow.AddSeconds(-1) }), "expired");
Refuses(() => UnlockPolicy.Validate(grant with { Revision = "label" }), "non-revision");
using (var otherCurve = ECDsa.Create(ECCurve.NamedCurves.nistP384))
    Refuses(() => UnlockPolicy.Validate(grant with { ControllerPublicKey = Convert.ToBase64String(otherCurve.ExportSubjectPublicKeyInfo()) }), "wrong curve");
var challenge = new UnlockChallenge(UnlockService.Protocol, "contracts", Guid.NewGuid().ToString("n"),
    4, 2, "0000000000000001", grant.Revision, grant.TargetUserSid, UnlockPolicy.Fingerprint(grant), "password",
    Convert.ToHexString(RandomNumberGenerator.GetBytes(32)), DateTimeOffset.UtcNow.AddSeconds(40));
var text = Contract.Serialize(challenge);
string Sign(ECDsa key, string value) => Convert.ToBase64String(key.SignData(Encoding.UTF8.GetBytes(value),
    HashAlgorithmName.SHA256, DSASignatureFormat.Rfc3279DerSequence));
Assert(UnlockPolicy.Verify(grant, text, Sign(controller, text)), "Controller signature");
Assert(!UnlockPolicy.Verify(grant, text, Sign(attacker, text)), "Wrong key denied");
Assert(!UnlockPolicy.Verify(grant, Contract.Serialize(challenge with { Nonce = new string('0', 64) }),
    Sign(controller, text)), "Proof cannot replay against a fresh challenge");
UnlockClient.ValidateChallenge(challenge, grant, "contracts", "password");
Refuses(() => UnlockClient.ValidateChallenge(challenge with { TargetUserSid = grant.TransportUserSid }, grant, "contracts", "password"), "wrong account");
Refuses(() => UnlockClient.ValidateChallenge(challenge with { GrantRevision = Guid.NewGuid().ToString("n") }, grant, "contracts", "password"), "revoked revision");
Refuses(() => UnlockClient.ValidateChallenge(challenge with { Deadline = DateTimeOffset.UtcNow.AddSeconds(-1) }, grant, "contracts", "password"), "stale challenge");
Refuses(() => UnlockClient.ValidateChallenge(challenge, grant, "another-instance", "password"), "other instance");
Refuses(() => UnlockClient.ValidateChallenge(challenge, grant, "contracts", "pin"), "other provider");
using var stream = new MemoryStream();
await UnlockWire.WriteAsync(stream, new { hello = true }, CancellationToken.None);
await UnlockWire.WriteSecretAsync(stream, [65, 66], CancellationToken.None);
stream.Position = 0;
Assert(await UnlockWire.ReadLineAsync(stream, CancellationToken.None) == "{\"hello\":true}", "Handshake frame");
Assert(stream.Length - stream.Position == 4, "Handshake did not read ahead into credential");
var bytes = await UnlockWire.ReadSecretAsync(stream, CancellationToken.None);
Assert(bytes.SequenceEqual(new byte[] { 65, 66 }), "Secret frame intact");
CryptographicOperations.ZeroMemory(bytes);
Console.WriteLine("Windows unlock authorization and transport contracts passed");
