using System.Diagnostics;
using System.IO;
using System.Text.Json;
using Microsoft.Win32;

namespace MachineControl.Windows;

/// Temporarily hide only this installation's native-host manifest while NSIS
/// replaces its executable. Chrome otherwise retries and locks the old image.
internal static class BrowserInstaller
{
    private const string KeyPath = @"Software\Google\Chrome\NativeMessagingHosts\org.machine_control.browser";
    internal static string Manifest => Path.Combine(Environment.GetFolderPath(
        Environment.SpecialFolder.LocalApplicationData), "MachineControl", "packages", "desktop", "browser-host.json");
    private static string Backup => Manifest + ".updating";

    private static string Executable(string installation)
    {
        if (!Path.IsPathFullyQualified(installation)) throw new ArgumentException("Absolute installation directory required");
        return Path.GetFullPath(Path.Combine(installation, "runtime", "machine-control-windows.exe"));
    }

    private static bool Owns(string file, string executable)
    {
        using var document = JsonDocument.Parse(File.ReadAllText(file));
        var value = document.RootElement;
        if (!value.TryGetProperty("path", out var path) ||
            !string.Equals(path.GetString(), executable, StringComparison.OrdinalIgnoreCase)) return false;
        if (value.GetProperty("name").GetString() != BrowserWire.Host ||
            value.GetProperty("type").GetString() != "stdio" ||
            value.GetProperty("allowed_origins").GetArrayLength() != 1 ||
            value.GetProperty("allowed_origins")[0].GetString() != BrowserWire.Origin)
            throw new InvalidDataException("Owned browser manifest is invalid");
        return true;
    }

    private static bool Registered()
    {
        using var root = RegistryKey.OpenBaseKey(RegistryHive.CurrentUser, RegistryView.Registry32);
        using var key = root.OpenSubKey(KeyPath);
        return key?.GetValue("") is string path && string.Equals(path, Manifest, StringComparison.OrdinalIgnoreCase);
    }

    internal static void Prepare(string installation)
    {
        var executable = Executable(installation);
        if (!Registered()) return;
        if (File.Exists(Backup))
        {
            if (!Owns(Backup, executable)) return;
            if (File.Exists(Manifest)) throw new InvalidOperationException("Browser update already has an active manifest");
        }
        else
        {
            if (!File.Exists(Manifest) || !Owns(Manifest, executable)) return;
            File.Move(Manifest, Backup);
        }
        try
        {
            var timer = Stopwatch.StartNew();
            while (true)
            {
                var running = false;
                foreach (var process in Process.GetProcessesByName("machine-control-windows"))
                {
                    using (process)
                    {
                        string? path;
                        try { path = process.MainModule?.FileName; }
                        catch (Exception ex) when (ex is System.ComponentModel.Win32Exception or InvalidOperationException) { continue; }
                        if (!string.Equals(path?.Replace(@"\\?\", ""), executable, StringComparison.OrdinalIgnoreCase)) continue;
                        running = true;
                        if (timer.Elapsed > TimeSpan.FromSeconds(10)) throw new IOException("Installed browser host has not exited");
                        process.WaitForExit(100);
                    }
                }
                if (!running) break;
                Thread.Sleep(50);
            }
        }
        catch
        {
            Finish(installation);
            throw;
        }
    }

    internal static void Finish(string installation)
    {
        var executable = Executable(installation);
        if (!File.Exists(Backup) || !Owns(Backup, executable)) return;
        if (!Registered() || File.Exists(Manifest)) throw new InvalidOperationException("Browser registration changed during update");
        File.Move(Backup, Manifest);
    }

    internal static void RecoverOwn()
    {
        var executable = Environment.ProcessPath ?? throw new InvalidOperationException("Browser executable unavailable");
        Finish(Path.GetDirectoryName(Path.GetDirectoryName(executable)!)!);
    }
}
