using System.IO;
using System.Text.Json;
using Microsoft.Win32;

namespace MachineControl.Windows;

internal static class BrowserRegistration
{
    internal static void Install()
    {
        var executable = Environment.ProcessPath
            ?? throw new InvalidOperationException("Browser executable unavailable");
        if (Path.GetFileName(executable) != "machine-control-windows.exe")
            throw new InvalidOperationException("Install the packaged companion first");
        var extension = Path.Combine(Path.GetDirectoryName(executable)!, "browser-extension");
        if (!File.Exists(Path.Combine(extension, "manifest.json")))
            throw new InvalidOperationException("Packaged browser extension is missing");
        var manifest = Path.Combine(RuntimeProfile.ManagementRoot, "browser-host.json");
        Directory.CreateDirectory(RuntimeProfile.ManagementRoot);
        using var root = RegistryKey.OpenBaseKey(RegistryHive.CurrentUser, RegistryView.Registry32);
        var keyPath = @"Software\Google\Chrome\NativeMessagingHosts\" + BrowserWire.Host;
        using var existing = root.OpenSubKey(keyPath);
        if (existing?.GetValue("") is string path && !string.Equals(path, manifest, StringComparison.OrdinalIgnoreCase))
            throw new InvalidOperationException("A different browser host is already registered");
        File.WriteAllText(manifest + ".new", Contract.Serialize(new
        {
            name = BrowserWire.Host,
            description = "Machine Control browser provider",
            path = executable,
            type = "stdio",
            allowed_origins = new[] { BrowserWire.Origin },
        }));
        File.Move(manifest + ".new", manifest, overwrite: true);
        using var key = root.CreateSubKey(keyPath);
        key.SetValue("", manifest, RegistryValueKind.String);
        Exception? failure = null;
        var clipboard = new Thread(() =>
        {
            try { System.Windows.Forms.Clipboard.SetText(extension); }
            catch (Exception ex) { failure = ex; }
        });
        clipboard.IsBackground = true;
        clipboard.SetApartmentState(ApartmentState.STA);
        clipboard.Start();
        if (!clipboard.Join(3000) || failure is not null)
            throw new InvalidOperationException("Browser registered; clipboard unavailable");
    }
    internal static void RemoveOwned()
    {
        // Installer cleanup changes only owned per-user registration; it needs
        // no active desktop, Medium input capability, or resident grant.
        BrowserInstaller.RecoverOwn();
        var manifest = BrowserInstaller.Manifest;
        if (!File.Exists(manifest)) return;
        using var document = JsonDocument.Parse(File.ReadAllText(manifest));
        if (!document.RootElement.TryGetProperty("path", out var path) ||
            !string.Equals(path.GetString(), Environment.ProcessPath, StringComparison.OrdinalIgnoreCase)) return;
        using var root = RegistryKey.OpenBaseKey(RegistryHive.CurrentUser, RegistryView.Registry32);
        var keyPath = @"Software\Google\Chrome\NativeMessagingHosts\" + BrowserWire.Host;
        using (var key = root.OpenSubKey(keyPath))
        {
            if (key?.GetValue("") is not string registered ||
                !string.Equals(registered, manifest, StringComparison.OrdinalIgnoreCase)) return;
        }
        root.DeleteSubKeyTree(keyPath, throwOnMissingSubKey: false);
        File.Delete(manifest);
    }

}
