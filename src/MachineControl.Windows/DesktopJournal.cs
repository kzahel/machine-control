using System.IO;
using System.Security.AccessControl;
using System.Security.Cryptography;
using System.Security.Principal;
using System.Text;
using System.Text.Json;
using System.Text.RegularExpressions;

namespace MachineControl.Windows;

/// Private append-only segments. Only allowlisted metadata reaches disk.
internal sealed class DesktopJournal
{
    private readonly object _gate = new();
    private readonly string _root;
    private readonly string _runtime = Guid.NewGuid().ToString("n");
    private readonly long _segmentBytes;
    private readonly long _auditBytes;
    private readonly long _diagnosticBytes;
    private readonly Dictionary<string, string> _files = new();
    private long _sequence;
    private string? _error;
    private bool _historyGap;
    private bool _diagnosticsAvailable = true;
    private DateTimeOffset _debugUntil;
    internal bool Available => _error is null;
    internal void Debug(bool enabled) { _debugUntil = enabled ? DateTimeOffset.UtcNow.AddMinutes(15) : DateTimeOffset.MinValue; Event(enabled ? "diagnostics.debug.enabled" : "diagnostics.debug.disabled"); }
    internal string Root => _root;
    internal static string DefaultRoot => Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "MachineControl", "logs");
    internal DesktopJournal(string? root = null, long segmentBytes = 1_048_576, long auditBytes = 104_857_600, long diagnosticBytes = 52_428_800)
    {
        _root = root ?? DefaultRoot;
        _segmentBytes = segmentBytes; _auditBytes = auditBytes; _diagnosticBytes = diagnosticBytes;
        Event("resident.start");
    }
    internal static string Token(string? value) => value is not null && value.Length <= 160 && Regex.IsMatch(value, @"\A[a-zA-Z0-9_./:-]+\z") ? value : "unknown";
    internal static string Correlation(string? value) => Convert.ToHexString(SHA256.HashData(Encoding.UTF8.GetBytes(value ?? ""))).ToLowerInvariant()[..24];
    internal static bool Tracked(string operation) => operation is not ("status" or "capabilities" or "grant.status" or "update.status");
    internal static bool Known(string operation) => UserOperations.Contains(operation);
    private static readonly HashSet<string> UserOperations = new("applications windows snapshot capture screenshot action focus set_value app.launch app.activate application.launch application.activate application.terminate invoke set.value click key type input.move input.click input.key input.text input.scroll input.drag window.state browser.tabs browser.wait browser.navigate browser.snapshot browser.click browser.type browser.key browser.capture browser.release browser.upload browser.cdp browser.eval browser.endpoint browser.provider browser.register grant.request grant.revoke runtime.stop server.stop session.control session.control.end session.unlock authorization.begin authorization.cancel authorization.submit permissions.request update.check".Split(' '));
    internal bool Begin(string operation, string? requestId, string? generation = null, uint? callerPid = null) => !Tracked(operation) || Append("audit", new Dictionary<string, object?>
    {
        ["phase"] = "intent",
        ["operation"] = Known(operation) ? operation : "unknown",
        ["requestId"] = Correlation(requestId),
        ["generation"] = Token(generation),
        ["callerPid"] = callerPid,
        ["effect"] = "unknown",
        ["uncertainty"] = "outcome_pending"
    });
    internal bool Record(Result result)
    {
        if (!Tracked(result.Operation)) return true;
        var value = new Dictionary<string, object?>
        {
            ["phase"] = "result",
            ["operation"] = Known(result.Operation) ? result.Operation : "unknown",
            ["requestId"] = Correlation(result.RequestId),
            ["accepted"] = result.Accepted,
            ["generation"] = Token(result.Generation),
            ["actualRoute"] = Token(result.ActualRoute),
            ["delivery"] = Token(result.Delivery),
            ["effect"] = Token(result.Effect),
            ["uncertainty"] = Token(result.Uncertainty),
            ["errorCode"] = result.ErrorCode is null ? null : Token(result.ErrorCode),
            ["elapsedMs"] = result.ElapsedMs,
            ["sessionId"] = result.SessionId
        };
        if (result.ErrorCode is not null || _debugUntil > DateTimeOffset.UtcNow) Append("diagnostics", new Dictionary<string, object?>(value));
        return Append("audit", value);
    }
    internal bool Event(string operation, bool accepted = true) => Append("audit", new Dictionary<string, object?> { ["phase"] = "event", ["operation"] = Token(operation), ["accepted"] = accepted });
    internal bool Diagnostic(string operation, string code) => Append("diagnostics", new Dictionary<string, object?> { ["phase"] = "event", ["operation"] = Token(operation), ["errorCode"] = Token(code) });
    private void PrivateDirectory(string path)
    {
        // Refuse redirects in the application-owned subtree before touching it.
        if (Directory.Exists(path) && (File.GetAttributes(path) & FileAttributes.ReparsePoint) != 0) throw new IOException("Unsafe log directory");
        Directory.CreateDirectory(path);
        if (OperatingSystem.IsWindows())
        {
            var sid = WindowsIdentity.GetCurrent().User!;
            var acl = new DirectorySecurity();
            acl.SetAccessRuleProtection(true, false);
            acl.AddAccessRule(new FileSystemAccessRule(sid, FileSystemRights.FullControl, InheritanceFlags.ContainerInherit | InheritanceFlags.ObjectInherit, PropagationFlags.None, AccessControlType.Allow));
            new DirectoryInfo(path).SetAccessControl(acl);
        }
        else File.SetUnixFileMode(path, UnixFileMode.UserRead | UnixFileMode.UserWrite | UnixFileMode.UserExecute);
    }
    private bool Append(string stream, Dictionary<string, object?> value)
    {
        lock (_gate)
        {
            try
            {
                if (_root == DefaultRoot) PrivateDirectory(Path.GetDirectoryName(_root)!);
                PrivateDirectory(_root);
                var dir = Path.Combine(_root, stream); PrivateDirectory(dir);
                Prune(dir, stream == "audit" ? 30 : 7, stream == "audit" ? _auditBytes : _diagnosticBytes);
                if (!_files.TryGetValue(stream, out var path) || !File.Exists(path) || new FileInfo(path).Length >= _segmentBytes)
                {
                    path = Path.Combine(dir, ((DateTimeOffset.UtcNow.ToUnixTimeMilliseconds() * 1000).ToString("D20")) + "-" + _runtime + ".jsonl");
                    using var created = new FileStream(path, FileMode.CreateNew, FileAccess.Write, FileShare.Read);
                    if (!OperatingSystem.IsWindows()) File.SetUnixFileMode(path, UnixFileMode.UserRead | UnixFileMode.UserWrite);
                    _files[stream] = path;
                }
                if ((File.GetAttributes(path) & FileAttributes.ReparsePoint) != 0) throw new IOException("Unsafe log file");
                value["schema"] = "machine-control-desktop-event/v0"; value["stream"] = stream;
                value["eventId"] = Guid.NewGuid().ToString("n"); value["runtimeId"] = _runtime;
                value["sequence"] = ++_sequence; value["at"] = DateTimeOffset.UtcNow;
                value["component"] = "windows.resident"; value["version"] = typeof(DesktopJournal).Assembly.GetName().Version?.ToString();
                var bytes = Encoding.UTF8.GetBytes(JsonSerializer.Serialize(value, Contract.Json) + "\n");
                using var file = new FileStream(path, FileMode.Append, FileAccess.Write, FileShare.Read);
                file.Write(bytes); file.Flush(true);
                Prune(dir, stream == "audit" ? 30 : 7, stream == "audit" ? _auditBytes : _diagnosticBytes);
                if (stream == "audit") _error = null;
                else _diagnosticsAvailable = true;
                return true;
            }
            catch (Exception ex) when (ex is IOException or UnauthorizedAccessException or System.Security.SecurityException)
            {
                if (stream == "audit") _error = "audit_storage_unavailable";
                else _diagnosticsAvailable = false;
                return false;
            }
        }
    }
    private static void Prune(string directory, int days, long cap)
    {
        var files = new DirectoryInfo(directory).GetFiles("*.jsonl").OrderBy(f => f.Name).ToList();
        long total = files.Sum(f => f.Length);
        foreach (var file in files)
        {
            if (file.LastWriteTimeUtc >= DateTime.UtcNow.AddDays(-days) && total <= cap) break;
            total -= file.Length; file.Delete();
        }
    }
    internal object Health => new { available = _error is null, errorCode = _error, auditDays = 30, diagnosticDays = 7, auditBytes = _auditBytes, diagnosticBytes = _diagnosticBytes, diagnosticsAvailable = _diagnosticsAvailable, historyGap = _historyGap, debugRemainingSeconds = Math.Max(0, (int)(_debugUntil - DateTimeOffset.UtcNow).TotalSeconds) };
    internal object Query(int offset = 0, string operation = "", string outcome = "", string stream = "audit")
    {
        lock (_gate)
        {
            offset = Math.Clamp(offset, 0, 1_000_000);
            var entries = Read(stream).Where(e => operation.Length == 0 || e.GetProperty("operation").GetString()!.Contains(operation, StringComparison.OrdinalIgnoreCase))
                .Where(e => outcome.Length == 0 || e.TryGetProperty("accepted", out var a) && a.GetBoolean() == (outcome == "accepted"))
                .Skip(offset).Take(51).ToArray();
            return new { entries = entries.Take(50), hasMore = entries.Length > 50, offset, earliestAt = Earliest(stream), health = Health };
        }
    }
    private string? Earliest(string stream)
    {
        var dir = Path.Combine(_root, stream == "diagnostics" ? "diagnostics" : "audit");
        if (!Directory.Exists(dir) || (File.GetAttributes(dir) & FileAttributes.ReparsePoint) != 0) return null;
        var path = Directory.GetFiles(dir, "*.jsonl").Order().FirstOrDefault();
        if (path is null || (File.GetAttributes(path) & FileAttributes.ReparsePoint) != 0) return null;
        try
        {
            using var file = new FileStream(path, FileMode.Open, FileAccess.Read, FileShare.ReadWrite | FileShare.Delete);
            var bytes = new byte[8192]; var n = file.Read(bytes); var end = Array.IndexOf(bytes, (byte)10, 0, n);
            if (end < 0) return null;
            using var doc = JsonDocument.Parse(bytes.AsMemory(0, end));
            var row = doc.RootElement;
            if (row.ValueKind == JsonValueKind.Object && row.TryGetProperty("at", out var at) && at.ValueKind == JsonValueKind.String)
                return at.GetString();
            _historyGap = true; return null;
        }
        catch (Exception ex) when (ex is IOException or JsonException) { _historyGap = true; return null; }
    }
    private IEnumerable<JsonElement> Read(string stream)
    {
        var dir = Path.Combine(_root, stream == "diagnostics" ? "diagnostics" : "audit");
        if (!Directory.Exists(dir) || (File.GetAttributes(dir) & FileAttributes.ReparsePoint) != 0) yield break;
        foreach (var path in Directory.GetFiles(dir, "*.jsonl").OrderDescending())
        {
            if ((File.GetAttributes(path) & FileAttributes.ReparsePoint) != 0 || new FileInfo(path).Length > _segmentBytes + 8192) continue;
            var entries = new List<JsonElement>();
            using var file = new FileStream(path, FileMode.Open, FileAccess.Read, FileShare.ReadWrite | FileShare.Delete);
            using var reader = new StreamReader(file);
            var lines = reader.ReadToEnd().Split('\n');
            if (lines[^1].Length != 0) _historyGap = true;
            foreach (var line in lines.Take(lines.Length - 1))
            {
                try
                {
                    using var doc = JsonDocument.Parse(line);
                    var row = doc.RootElement;
                    if (row.ValueKind != JsonValueKind.Object || !row.TryGetProperty("schema", out var schema) || schema.ValueKind != JsonValueKind.String || schema.GetString() != "machine-control-desktop-event/v0" ||
                        new[] { "eventId", "operation", "at", "phase" }.Any(key => !row.TryGetProperty(key, out var field) || field.ValueKind != JsonValueKind.String) ||
                        row.TryGetProperty("accepted", out var accepted) && accepted.ValueKind is not (JsonValueKind.True or JsonValueKind.False))
                    { _historyGap = true; continue; }
                    entries.Add(row.Clone());
                }
                catch (JsonException) { _historyGap = true; }
            }
            foreach (var entry in entries.AsEnumerable().Reverse()) yield return entry;
        }
    }
    internal object Preview() { lock (_gate) return new { schema = "machine-control-diagnostics-export/v0", health = Health, audit = Read("audit").Take(500).ToArray(), diagnostics = Read("diagnostics").Take(500).ToArray() }; }
    internal string Export()
    {
        lock (_gate)
        {
            var dir = Path.Combine(_root, "exports"); PrivateDirectory(dir);
            var path = Path.Combine(dir, "diagnostics.json");
            if (File.Exists(path) && (File.GetAttributes(path) & FileAttributes.ReparsePoint) != 0) throw new IOException("Unsafe export");
            var temporary = Path.Combine(dir, Guid.NewGuid().ToString("n") + ".tmp");
            using (var file = new FileStream(temporary, FileMode.CreateNew, FileAccess.Write, FileShare.None))
            {
                if (!OperatingSystem.IsWindows()) File.SetUnixFileMode(temporary, UnixFileMode.UserRead | UnixFileMode.UserWrite);
                file.Write(Encoding.UTF8.GetBytes(JsonSerializer.Serialize(Preview(), Contract.Json))); file.Flush(true);
            }
            File.Move(temporary, path, overwrite: true);
            return path;
        }
    }
}
