using System.IO;
using System.Security.Cryptography;
using System.Security.Principal;
using System.Text;
using System.Text.Json;

namespace MachineControl.Windows;

internal sealed record UnlockGrant(
    string Schema,
    string Revision,
    string TargetUserSid,
    string TransportUserSid,
    string ControllerPublicKey,
    DateTimeOffset? ExpiresAt);

internal static class UnlockPolicy
{
    public const string Schema = "machine-control-unlock-grant/v0";
    public static string Root(string instance) => Path.Combine(
        Environment.GetFolderPath(Environment.SpecialFolder.CommonApplicationData),
        "MachineControlUnlock", RuntimeProfile.ValidateInstance(instance));
    public static string Pipe(string instance) => "machine-control-unlock-" + RuntimeProfile.ValidateInstance(instance);
    public static string Service(string instance) => "MachineControlUnlock_" + RuntimeProfile.ValidateInstance(instance);
    public static string GrantPath(string instance) => Path.Combine(Root(instance), "grant.json");

    public static UnlockGrant Validate(UnlockGrant grant, bool checkExpiry = true)
    {
        if (grant.Schema != Schema || !Guid.TryParseExact(grant.Revision, "N", out _))
            throw new InvalidDataException("Invalid grant schema or revision");
        _ = new SecurityIdentifier(grant.TargetUserSid);
        _ = new SecurityIdentifier(grant.TransportUserSid);
        using var key = ECDsa.Create();
        var bytes = Convert.FromBase64String(grant.ControllerPublicKey);
        key.ImportSubjectPublicKeyInfo(bytes, out var consumed);
        if (consumed != bytes.Length || key.KeySize != 256 ||
            key.ExportParameters(false).Curve.Oid.Value != "1.2.840.10045.3.1.7")
            throw new InvalidDataException("Controller key must be P-256 SubjectPublicKeyInfo");
        if (checkExpiry && grant.ExpiresAt <= DateTimeOffset.UtcNow)
            throw new InvalidDataException("grant_expired");
        return grant;
    }

    public static UnlockGrant Read(string instance)
    {
        var path = GrantPath(instance);
        if (!File.Exists(path)) throw new InvalidDataException("not_armed");
        UnlockAdmin.RequireProtectedPath(path, Path.GetDirectoryName(Root(instance))!);
        if (new FileInfo(path).Length > 16 * 1024) throw new InvalidDataException("grant_invalid");
        // The installer owns directory/file ACLs; ordinary clients never write
        // this state. Refuse reparse points instead of following another store.
        for (var parent = path; !string.IsNullOrEmpty(parent) &&
            parent.Length >= Root(instance).Length; parent = Path.GetDirectoryName(parent))
            if ((File.GetAttributes(parent) & FileAttributes.ReparsePoint) != 0)
                throw new InvalidDataException("grant_store_invalid");
        return Validate(JsonSerializer.Deserialize<UnlockGrant>(File.ReadAllText(path), Contract.Json)
            ?? throw new InvalidDataException("grant_invalid"));
    }

    public static string Fingerprint(UnlockGrant grant) => Convert.ToHexString(
        SHA256.HashData(Convert.FromBase64String(grant.ControllerPublicKey))).ToLowerInvariant();

    public static bool Verify(UnlockGrant grant, string challenge, string signature)
    {
        using var key = ECDsa.Create();
        key.ImportSubjectPublicKeyInfo(Convert.FromBase64String(grant.ControllerPublicKey), out _);
        return key.VerifyData(Encoding.UTF8.GetBytes(challenge), Convert.FromBase64String(signature),
            HashAlgorithmName.SHA256, DSASignatureFormat.Rfc3279DerSequence);
    }
}
