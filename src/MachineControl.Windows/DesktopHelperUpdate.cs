using System.ComponentModel;
using System.Diagnostics;
using System.IO;
using System.IO.Compression;
using System.IO.Pipes;
using System.Security.AccessControl;
using System.Security.Principal;
using System.ServiceProcess;
using System.Text;
using TimeoutException = System.TimeoutException;

namespace MachineControl.Windows;

internal static class DesktopHelperUpdate
{
    private const string PipeName = "machine-control-desktop-helper-update-v1";
    private const string Archive = "incoming.zip";
    private const string Payload = "runtime";
    private const uint MediumIntegrity = 8192;

    private static string CreateStage()
    {
        UnlockAdmin.RequireProtectedPath(DesktopUacNative.Root, DesktopUacNative.Root);
        var stage = Path.Combine(DesktopUacNative.Root, "maintenance-" + Guid.NewGuid().ToString("n"));
        Directory.CreateDirectory(stage);
        DesktopUacSetup.ProtectDirectory(stage, userReadable: false);
        return stage;
    }

    private static string ExistingStage(string id)
    {
        if (!Guid.TryParseExact(id, "n", out var value))
            throw new InvalidDataException("Expected a helper transaction ID");
        var stage = Path.Combine(DesktopUacNative.Root, "maintenance-" + value.ToString("n"));
        UnlockAdmin.RequireProtectedPath(stage, DesktopUacNative.Root);
        return stage;
    }

    private static string LockPath => Path.Combine(DesktopUacNative.Root, "maintenance.lock");
    private static FileStream EnterTransaction() =>
        new(LockPath, FileMode.Open, FileAccess.ReadWrite, FileShare.None);

    internal static FileStream EnterProtectedOperation() =>
        new(LockPath, FileMode.Open, FileAccess.Read, FileShare.Read);

    internal static void Initialize()
    {
        if (File.Exists(LockPath)) return;
        var acl = new FileSecurity();
        var administrators = new SecurityIdentifier(WellKnownSidType.BuiltinAdministratorsSid, null);
        acl.SetOwner(administrators);
        acl.SetAccessRuleProtection(true, false);
        foreach (var sid in new[] { administrators, new SecurityIdentifier(WellKnownSidType.LocalSystemSid, null) })
            acl.AddAccessRule(new FileSystemAccessRule(sid, FileSystemRights.FullControl, AccessControlType.Allow));
        using var created = new FileInfo(LockPath).Create(FileMode.CreateNew, FileSystemRights.FullControl,
            FileShare.ReadWrite, 4096, FileOptions.None, acl);
    }

    internal static async Task<int> RequestMigrationAsync()
    {
        if (DesktopUacNative.Installed() &&
            File.Exists(Path.Combine(Path.GetDirectoryName(DesktopUacNative.Executable)!, DesktopHelperRelease.Manifest)))
            return await UpdateAsync();
        using var child = Process.Start(new ProcessStartInfo(Environment.ProcessPath!, "uac-update-migrate")
        { UseShellExecute = true, Verb = "runas" }) ?? throw new IOException("Windows elevation did not start helper update");
        child.WaitForExit();
        return child.ExitCode;
    }

    internal static int Migrate()
    {
        // Package maintenance does not need a desktop handle. Require the
        // elevated native console session and independently observe its lock.
        DesktopUacSetup.RequireAdmin(requiresInputDesktop: false);
        if (!Directory.Exists(DesktopUacNative.Root))
            throw new InvalidOperationException("Install the UAC helper before updating it");
        if (!Path.GetFileName(AppContext.BaseDirectory.TrimEnd(Path.DirectorySeparatorChar)).Equals(Payload, StringComparison.OrdinalIgnoreCase))
            throw new InvalidOperationException("Run the installed desktop to update the helper");
        var stage = CreateStage();
        try
        {
            var copy = Path.Combine(stage, Payload);
            var files = DesktopHelperRelease.FilesIn(AppContext.BaseDirectory);
            if (files.Sum(file => new FileInfo(file).Length) > DesktopHelperRelease.MaximumBytes)
                throw new InvalidDataException("Helper release is too large");
            foreach (var file in files)
            {
                var name = Path.GetRelativePath(AppContext.BaseDirectory, file).Replace('\\', '/');
                var destination = DesktopHelperRelease.InDirectory(copy, name);
                Directory.CreateDirectory(Path.GetDirectoryName(destination)!);
                using var input = File.OpenRead(file);
                using var output = new FileStream(destination, FileMode.CreateNew, FileAccess.Write);
                DesktopHelperRelease.CopyExactly(input, output, input.Length);
            }
            Activate(copy, allowLegacy: true);
            return 0;
        }
        finally { Directory.Delete(stage, true); }
    }

    internal static async Task<int> UpdateAsync()
    {
        if (!Directory.Exists(DesktopUacNative.Root) || !File.Exists(Path.Combine(AppContext.BaseDirectory, DesktopHelperRelease.Manifest)))
            return 0;
        var bundled = Environment.ProcessPath!;
        if (DesktopUacNative.Installed() && DesktopHelperRelease.MatchesInstalled(DesktopUacNative.Executable, bundled))
            return 0;
        var archive = Path.Combine(Path.GetTempPath(), "machine-control-helper-" + Guid.NewGuid().ToString("n") + ".zip");
        try
        {
            using var timeout = new CancellationTokenSource(TimeSpan.FromMinutes(4));
            string receipt;
            using (var pipe = new NamedPipeClientStream(".", PipeName, PipeDirection.InOut, PipeOptions.Asynchronous,
                TokenImpersonationLevel.Identification))
            {
                try { await pipe.ConnectAsync(1500, timeout.Token); }
                catch (TimeoutException) { return 3; } // legacy or stopped
                DesktopUacNative.RequireServer(pipe, DesktopUacNative.ServicePid());
                using (var file = new FileStream(archive, FileMode.CreateNew, FileAccess.ReadWrite, FileShare.None))
                {
                    using (var zip = new ZipArchive(file, ZipArchiveMode.Create, leaveOpen: true))
                    {
                        var files = DesktopHelperRelease.FilesIn(AppContext.BaseDirectory);
                        if (files.Sum(path => new FileInfo(path).Length) > DesktopHelperRelease.MaximumBytes)
                            throw new InvalidDataException("Helper release is too large");
                        foreach (var path in files)
                            zip.CreateEntryFromFile(path, Path.GetRelativePath(AppContext.BaseDirectory, path).Replace('\\', '/'),
                                CompressionLevel.NoCompression);
                    }
                    file.Position = 0;
                    if (file.Length > DesktopHelperRelease.MaximumBytes) throw new InvalidDataException("Helper archive is too large");
                    await pipe.WriteAsync(BitConverter.GetBytes(file.Length), timeout.Token);
                    await file.CopyToAsync(pipe, timeout.Token);
                }
                using var reader = new StreamReader(pipe, Encoding.UTF8, false, 4096, leaveOpen: true);
                receipt = await DesktopUacNative.ReadAsync(reader, timeout.Token, 48);
                if (!Guid.TryParseExact(receipt, "n", out _)) return 4;
            }
            var result = ResultPath(receipt);
            while (!timeout.IsCancellationRequested)
            {
                if (File.Exists(result))
                    return File.ReadAllText(result) == "installed" && DesktopUacNative.Installed() &&
                        DesktopHelperRelease.MatchesInstalled(DesktopUacNative.Executable, bundled) ? 0 : 4;
                await Task.Delay(500, timeout.Token);
            }
            return 4;
        }
        finally { File.Delete(archive); }
    }

    internal static async Task ServeAsync(CancellationToken cancellation, Func<bool> ready)
    {
        if (!DesktopHelperSignature.Required) return;
        var image = Environment.ProcessPath!;
        UnlockAdmin.RequireProtectedPath(image, DesktopUacNative.Root);
        while (!cancellation.IsCancellationRequested)
        {
            using var pipe = await ListenAsync(cancellation);
            using var budget = CancellationTokenSource.CreateLinkedTokenSource(cancellation);
            string? stage = null;
            try
            {
                await pipe.WaitForConnectionAsync(cancellation);
                budget.CancelAfter(TimeSpan.FromSeconds(3));
                var header = new byte[8];
                await pipe.ReadExactlyAsync(header, budget.Token);
                var length = BitConverter.ToInt64(header);
                if (length == 0)
                {
                    await pipe.WriteAsync((ready() ? "ready\n"u8 : "refused\n"u8).ToArray(), budget.Token);
                    continue;
                }
                if (length is -1 or -2 or -3)
                {
                    await DesktopHelperHandoff.ServeAsync(pipe, length, budget.Token);
                    continue;
                }
                if (length < 0 || length > DesktopHelperRelease.MaximumBytes ||
                    !DesktopUacNative.IsActiveImage(image))
                    throw new UnauthorizedAccessException("Helper update sender or payload refused");
                RequireConsoleClient(pipe);
                budget.CancelAfter(TimeSpan.FromMinutes(2));
                stage = CreateStage();
                var archive = Path.Combine(stage, Archive);
                await using (var file = new FileStream(archive, FileMode.CreateNew, FileAccess.Write, FileShare.None, 128 * 1024, useAsync: true))
                {
                    var buffer = new byte[128 * 1024];
                    while (length > 0)
                    {
                        var requested = (int)Math.Min(length, buffer.Length);
                        await pipe.ReadExactlyAsync(buffer.AsMemory(0, requested), budget.Token);
                        await file.WriteAsync(buffer.AsMemory(0, requested), budget.Token);
                        length -= requested;
                    }
                }
                var payload = Path.Combine(stage, Payload);
                Directory.CreateDirectory(payload);
                DesktopHelperRelease.Extract(archive, payload);
                File.Delete(archive);
                var release = DesktopHelperRelease.Verify(payload);
                RequireNewer(release, image, false);
                budget.Token.ThrowIfCancellationRequested();
                var start = new ProcessStartInfo(image)
                {
                    UseShellExecute = false,
                    CreateNoWindow = true,
                    WorkingDirectory = Environment.SystemDirectory,
                };
                start.ArgumentList.Add("uac-update-activate");
                var receipt = Path.GetFileName(stage)["maintenance-".Length..];
                start.ArgumentList.Add(receipt);
                using var child = Process.Start(start) ?? throw new IOException("Could not start helper maintenance");
                stage = null; // The LocalSystem worker owns the protected stage.
                await pipe.WriteAsync(Encoding.ASCII.GetBytes(receipt + "\n"), budget.Token);
            }
            catch (Exception error) when (IsMaintenanceError(error))
            {
                if (pipe.IsConnected)
                {
                    try { await pipe.WriteAsync("refused\n"u8.ToArray(), budget.Token); }
                    catch (Exception writeError) when (IsMaintenanceError(writeError)) { }
                }
            }
            finally { if (stage is not null) DeleteStage(stage); }
        }
    }

    private static async Task<NamedPipeServerStream> ListenAsync(CancellationToken cancellation)
    {
        while (true)
        {
            cancellation.ThrowIfCancellationRequested();
            try { return DesktopUacNative.Server(PipeName); }
            catch (Exception error) when (error is IOException or UnauthorizedAccessException)
            { await Task.Delay(250, cancellation); }
        }
    }

    private static void RequireConsoleClient(NamedPipeServerStream pipe)
    {
        using var peer = Process.GetProcessById((int)DesktopUacNative.ClientPid(pipe));
        var session = (uint)peer.SessionId;
        string? caller = null;
        pipe.RunAsClient(() => { using var identity = WindowsIdentity.GetCurrent(); caller = identity.User?.Value; });
        if (session == 0 || session != NativeMethods.WTSGetActiveConsoleSessionId() ||
            caller is null || caller != UnlockNative.ConsoleUserSid(session))
            throw new UnauthorizedAccessException("Helper updates require the active local console account");
    }

    internal static int ActivateFromService(string id)
    {
        using var identity = WindowsIdentity.GetCurrent();
        if (!identity.IsSystem || RuntimeProfile.SessionId != 0 || !Guid.TryParseExact(id, "n", out var receipt))
            throw new UnauthorizedAccessException("Installed helper maintenance worker required");
        var result = ResultPath(receipt.ToString("n"));
        string? stage = null;
        var installed = false;
        try
        {
            if (!DesktopUacNative.IsActiveImage(Environment.ProcessPath))
                throw new UnauthorizedAccessException("Helper generation changed before activation");
            stage = ExistingStage(id);
            Activate(Path.Combine(stage, Payload), allowLegacy: false);
            installed = true;
            return 0;
        }
        finally
        {
            var temporary = result + ".tmp";
            File.WriteAllText(temporary, installed ? "installed" : "refused");
            File.Move(temporary, result);
            if (stage is not null) DeleteStage(stage);
        }
    }

    private static string ResultPath(string id) => Path.Combine(DesktopUacNative.Root, "maintenance-result-" + id);

    private static void RequireNewer(DesktopHelperRelease release, string oldImage, bool allowLegacy)
    {
        var current = Path.Combine(Path.GetDirectoryName(oldImage)!, DesktopHelperRelease.Manifest);
        if (!File.Exists(current))
        {
            if (allowLegacy && oldImage == DesktopUacNative.LegacyExecutable) return;
            throw new InvalidOperationException("An administrator must migrate the legacy helper");
        }
        var installed = System.Text.Json.JsonSerializer.Deserialize<DesktopHelperRelease>(File.ReadAllBytes(current), Contract.Json)
            ?? throw new InvalidDataException("Installed helper release is unreadable");
        var version = DesktopHelperRelease.ParseVersion(release.Version);
        var previousVersion = DesktopHelperRelease.ParseVersion(installed.Version);
        var sameBytes = release.Files.Count == installed.Files.Count &&
            release.Files.All(file => installed.Files.TryGetValue(file.Key, out var hash) && hash == file.Value);
        if (version < previousVersion || (version == previousVersion && (!allowLegacy || !sameBytes)))
            throw new InvalidOperationException("The helper update must advance the installed version");
    }

    private static void Activate(string payload, bool allowLegacy)
    {
        Initialize();
        // Wait briefly for a protected operation to drain. No upload is
        // trusted until the worker verifies its private copy under the lock.
        FileStream? transaction = null;
        for (var attempt = 0; attempt < 50 && transaction is null; attempt++)
        {
            try { transaction = EnterTransaction(); }
            catch (IOException) when (attempt < 49) { Thread.Sleep(100); }
        }
        using (transaction)
        {
            var release = DesktopHelperRelease.Verify(payload);
            PruneReceipts();
            File.Delete(Path.Combine(payload, DesktopHelperRelease.Catalog));
            var previous = DesktopUacNative.Executable;
            UnlockAdmin.RequireProtectedPath(previous, DesktopUacNative.Root);
            RequireNewer(release, previous, allowLegacy);
            RequireIdle(previous);
            Directory.CreateDirectory(DesktopUacNative.Versions);
            UnlockAdmin.RequireProtectedPath(DesktopUacNative.Versions, DesktopUacNative.Root);
            var directory = Path.Combine(DesktopUacNative.Versions, Guid.NewGuid().ToString("n"));
            Directory.Move(payload, directory);
            DesktopUacSetup.ProtectDirectory(directory);
            var incoming = Path.Combine(directory, DesktopHelperRelease.Image);
            using var service = new ServiceController(DesktopUacNative.Service);
            Stop(service);
            try
            {
                SetImage(incoming);
                Start(service);
            }
            catch
            {
                SetImage(previous);
                Stop(service);
                service.Start();
                service.WaitForStatus(ServiceControllerStatus.Running, TimeSpan.FromSeconds(20));
                throw;
            }
            PruneVersions(directory, Path.GetDirectoryName(previous)!);
        }
    }

    private static void RequireIdle(string image)
    {
        var session = NativeMethods.WTSGetActiveConsoleSessionId();
        if (session == 0 || session == uint.MaxValue || SessionStateInspector.IsLocked(session) != false)
            throw new InvalidOperationException("Helper maintenance requires an unlocked console");
        foreach (var process in Process.GetProcessesByName("machine-control-windows"))
        {
            using (process)
            {
                if (process.SessionId == 0 || process.Id == Environment.ProcessId || process.HasExited) continue;
                if (!NativeMethods.OpenProcessToken(process.Handle, NativeMethods.TOKEN_QUERY, out var token))
                    throw new Win32Exception(System.Runtime.InteropServices.Marshal.GetLastWin32Error());
                using var handle = new NativeHandle(token);
                if (TokenInspector.GetIntegrityRid(token) == MediumIntegrity &&
                    string.Equals(process.MainModule?.FileName, image, StringComparison.OrdinalIgnoreCase))
                    throw new InvalidOperationException("Close other desktop sessions using this helper");
            }
        }
    }

    private static void SetImage(string image) =>
        DesktopUacSetup.ServiceCommand("config", DesktopUacNative.Service, "binPath=", $"\"{image}\" uac-service");

    private static void Stop(ServiceController service)
    {
        service.Refresh();
        if (service.Status == ServiceControllerStatus.Stopped) return;
        if (service.Status != ServiceControllerStatus.StopPending) service.Stop();
        service.WaitForStatus(ServiceControllerStatus.Stopped, TimeSpan.FromSeconds(25));
    }

    private static void Start(ServiceController service)
    {
        service.Refresh();
        service.Start();
        service.WaitForStatus(ServiceControllerStatus.Running, TimeSpan.FromSeconds(20));
        using var timeout = new CancellationTokenSource(TimeSpan.FromSeconds(10));
        if (!HealthyAsync(DesktopUacNative.ServicePid(), timeout.Token).GetAwaiter().GetResult())
            throw new IOException("The updated helper did not become ready");
    }

    private static async Task<bool> HealthyAsync(uint expectedPid, CancellationToken cancellation)
    {
        using var pipe = new NamedPipeClientStream(".", PipeName, PipeDirection.InOut, PipeOptions.Asynchronous,
            TokenImpersonationLevel.Identification);
        try
        {
            await pipe.ConnectAsync(1500, cancellation);
            DesktopUacNative.RequireServer(pipe, expectedPid);
            await pipe.WriteAsync(new byte[8], cancellation);
            using var reader = new StreamReader(pipe, Encoding.UTF8);
            return await DesktopUacNative.ReadAsync(reader, cancellation, 32) == "ready";
        }
        catch (Exception error) when (IsMaintenanceError(error)) { return false; }
    }

    internal static async Task<bool> HandoffAsync(long operation, string? version = null)
    {
        using var deadline = new CancellationTokenSource(TimeSpan.FromSeconds(2));
        using var pipe = new NamedPipeClientStream(".", PipeName, PipeDirection.InOut, PipeOptions.Asynchronous,
            TokenImpersonationLevel.Identification);
        try
        {
            await pipe.ConnectAsync(1000, deadline.Token);
            DesktopUacNative.RequireServer(pipe, DesktopUacNative.ServicePid());
            await pipe.WriteAsync(BitConverter.GetBytes(operation), deadline.Token);
            if (version is not null) await pipe.WriteAsync(Encoding.UTF8.GetBytes(version + "\n"), deadline.Token);
            using var reader = new StreamReader(pipe, Encoding.UTF8);
            return await DesktopUacNative.ReadAsync(reader, deadline.Token, 32) == "accepted";
        }
        catch (Exception error) when (IsMaintenanceError(error))
        { return false; }
    }

    internal static bool IsMaintenanceError(Exception error) => error is IOException or InvalidDataException
        or UnauthorizedAccessException or InvalidOperationException or Win32Exception or OperationCanceledException
        or ArgumentException or System.Text.Json.JsonException or TimeoutException or FormatException
        or OverflowException or System.Security.SecurityException or System.Security.Cryptography.CryptographicException;

    private static void DeleteStage(string path)
    {
        try { Directory.Delete(path, true); }
        catch (Exception error) when (error is IOException or UnauthorizedAccessException) { }
    }

    private static void PruneReceipts()
    {
        var cutoff = DateTime.UtcNow.AddHours(-1);
        foreach (var result in Directory.EnumerateFiles(DesktopUacNative.Root, "maintenance-result-*"))
        {
            try { if (File.GetLastWriteTimeUtc(result) < cutoff) File.Delete(result); }
            catch (Exception error) when (error is IOException or UnauthorizedAccessException) { }
        }
    }

    private static void PruneVersions(string current, string previous)
    {
        foreach (var path in Directory.EnumerateDirectories(DesktopUacNative.Versions))
        {
            if (path == current || path == previous || !Guid.TryParseExact(Path.GetFileName(path), "n", out _)) continue;
            try
            {
                UnlockAdmin.RequireProtectedPath(path, DesktopUacNative.Root);
                Directory.Delete(path, true);
            }
            catch (Exception error) when (error is IOException or UnauthorizedAccessException or Win32Exception) { }
        }
    }
}
