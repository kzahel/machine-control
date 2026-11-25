using System.IO;
using System.IO.Pipes;
using System.Security.Principal;
using System.Text;
using System.Text.Json;

namespace MachineControl.Windows;

internal static class DesktopHelperHandoff
{
    private sealed record Pending(string FromVersion, string ToVersion, DateTimeOffset Expires);
    private static string Note(string sid) => Path.Combine(DesktopUacNative.Root, $"update-consent-{sid}.json");

    internal static Task<bool> SaveAsync(string version) => DesktopHelperUpdate.HandoffAsync(-1, version);
    internal static Task<bool> CancelAsync() => DesktopHelperUpdate.HandoffAsync(-3);

    internal static async Task<bool> RestoreAsync()
    {
        try
        {
            if (!DesktopHelperSignature.Required || !DesktopUacNative.IsActiveImage(Environment.ProcessPath)) return false;
            using var identity = WindowsIdentity.GetCurrent();
            return identity.User is { } sid && File.Exists(Note(sid.Value)) && await DesktopHelperUpdate.HandoffAsync(-2);
        }
        catch (Exception error) when (DesktopHelperUpdate.IsMaintenanceError(error)) { return false; }
    }

    internal static async Task ServeAsync(NamedPipeServerStream pipe, long operation, CancellationToken token)
    {
        using var request = CancellationTokenSource.CreateLinkedTokenSource(token);
        request.CancelAfter(TimeSpan.FromSeconds(2));
        var peer = await DesktopUacNative.RequireResidentAsync(pipe, request.Token);
        var sid = UnlockNative.ConsoleUserSid(peer.Session) ?? throw new UnauthorizedAccessException("Missing console account");
        var path = Note(sid);
        var currentManifest = Path.Combine(AppContext.BaseDirectory, DesktopHelperRelease.Manifest);
        var current = JsonSerializer.Deserialize<DesktopHelperRelease>(File.ReadAllBytes(currentManifest), Contract.Json)
            ?? throw new InvalidDataException("Missing installed helper release");
        var accepted = false;
        if (operation == -1)
        {
            using var reader = new StreamReader(pipe, Encoding.UTF8, leaveOpen: true);
            var next = await DesktopUacNative.ReadAsync(reader, request.Token, 32);
            if (DesktopHelperRelease.ParseVersion(next) > DesktopHelperRelease.ParseVersion(current.Version))
            {
                var temporary = path + ".tmp";
                File.WriteAllText(temporary, Contract.Serialize(new Pending(current.Version, next, DateTimeOffset.UtcNow.AddMinutes(10))));
                File.Move(temporary, path, overwrite: true);
                accepted = true;
            }
        }
        else if (File.Exists(path))
        {
            var saved = JsonSerializer.Deserialize<Pending>(File.ReadAllBytes(path), Contract.Json);
            if (operation == -3 && saved?.FromVersion == current.Version)
            {
                File.Delete(path);
                accepted = true;
            }
            else if (operation == -2 && saved is not null &&
                (saved.ToVersion == current.Version || saved.Expires <= DateTimeOffset.UtcNow))
            {
                File.Delete(path);
                accepted = saved.ToVersion == current.Version && saved.Expires > DateTimeOffset.UtcNow;
            }
        }
        await pipe.WriteAsync(Encoding.ASCII.GetBytes(accepted ? "accepted\n" : "refused\n"), request.Token);
    }
}
