import CryptoKit
import Darwin
import Foundation

/// Native-owned private segments. Payloads, secrets and caller labels are not logged.
final class DesktopJournal {
    let root: URL
    private let runtime = UUID().uuidString.lowercased()
    private var sequence = 0
    private var files: [String: URL] = [:]
    private(set) var errorCode: String?
    private(set) var historyGap = false
    private var diagnosticsAvailable = true
    private var debugUntil: TimeInterval = 0
    func debug(_ enabled: Bool) { debugUntil = enabled ? ProcessInfo.processInfo.systemUptime + 900 : 0; event(enabled ? "diagnostics.debug.enabled" : "diagnostics.debug.disabled") }
    private let segmentBytes: Int
    private let auditBytes: Int
    private let diagnosticBytes: Int
    private let lock = NSRecursiveLock()
    static let known = Set("applications windows snapshot capture screenshot action focus set_value app.launch app.activate application.launch application.activate application.terminate invoke set.value click key type input.move input.click input.key input.text input.scroll input.drag window.state browser.tabs browser.wait browser.navigate browser.snapshot browser.click browser.type browser.key browser.capture browser.release browser.upload browser.cdp browser.eval browser.provider browser.register grant.request grant.revoke runtime.stop server.stop session.control session.control.end session.unlock authorization.begin authorization.cancel authorization.submit permissions.request update.check".split(separator: " ").map(String.init))
    static func tracked(_ operation: String) -> Bool {
        !["status", "capabilities", "grant.status", "update.status", "browser.endpoint"].contains(operation)
    }
    static func token(_ value: Any?) -> String {
        guard let string = value as? String, string.count <= 160,
              string.range(of: "^[a-zA-Z0-9_./:-]+$", options: .regularExpression) != nil else { return "unknown" }
        return string
    }
    static func correlation(_ value: Any?) -> String {
        SHA256.hash(data: Data(((value as? String) ?? "").utf8)).prefix(12).map { String(format: "%02x", $0) }.joined()
    }
    init(root: URL? = nil, segmentBytes: Int = 1_048_576, auditBytes: Int = 104_857_600, diagnosticBytes: Int = 52_428_800) {
        self.root = root ?? FileManager.default.homeDirectoryForCurrentUser.appendingPathComponent("Library/Logs/MachineControl")
        self.segmentBytes = segmentBytes; self.auditBytes = auditBytes; self.diagnosticBytes = diagnosticBytes
        _ = event("resident.start")
    }
    private func privateDirectory(_ url: URL) throws {
        var st = stat()
        if lstat(url.path, &st) == 0 {
            guard st.st_mode & S_IFMT == S_IFDIR, st.st_uid == getuid() else { throw CocoaError(.fileWriteNoPermission) }
        } else {
            try FileManager.default.createDirectory(at: url, withIntermediateDirectories: true, attributes: [.posixPermissions: 0o700])
        }
        guard chmod(url.path, 0o700) == 0 else { throw CocoaError(.fileWriteNoPermission) }
    }
    private func paths(_ stream: String) -> [URL] {
        let directory = root.appendingPathComponent(stream == "diagnostics" ? "diagnostics" : "audit")
        var st = stat()
        guard lstat(directory.path, &st) == 0, st.st_mode & S_IFMT == S_IFDIR else { return [] }
        return ((try? FileManager.default.contentsOfDirectory(at: directory, includingPropertiesForKeys: nil)) ?? [])
            .filter { $0.pathExtension == "jsonl" }.sorted { $0.lastPathComponent < $1.lastPathComponent }
    }
    private func prune(_ stream: String) throws {
        let urls = paths(stream)
        var total: Int64 = 0
        for url in urls { var st = stat(); if lstat(url.path, &st) == 0 { total += st.st_size } }
        let cap = Int64(stream == "audit" ? auditBytes : diagnosticBytes)
        let cutoff = Date().timeIntervalSince1970 - Double((stream == "audit" ? 30 : 7) * 86400)
        for url in urls {
            var st = stat(); guard lstat(url.path, &st) == 0 else { continue }
            if Double(st.st_mtimespec.tv_sec) >= cutoff && total <= cap { break }
            total -= st.st_size
            try FileManager.default.removeItem(at: url)
        }
    }
    @discardableResult
    private func append(_ stream: String, _ fields: [String: Any]) -> Bool {
        lock.lock(); defer { lock.unlock() }
        do {
            try privateDirectory(root)
            let directory = root.appendingPathComponent(stream)
            try privateDirectory(directory)
            try prune(stream)
            var st = stat()
            var path = files[stream]
            if path == nil || lstat(path!.path, &st) != 0 || st.st_size >= segmentBytes {
                let name = String(format: "%020.0f", Date().timeIntervalSince1970 * 1_000_000) + "-" + runtime + ".jsonl"
                path = directory.appendingPathComponent(name)
                let fd = open(path!.path, O_CREAT | O_EXCL | O_WRONLY | O_NOFOLLOW | O_CLOEXEC, 0o600)
                guard fd >= 0 else { throw CocoaError(.fileWriteUnknown) }
                close(fd); files[stream] = path
            }
            sequence += 1
            var value = fields
            value["schema"] = "machine-control-desktop-event/v0"; value["stream"] = stream
            value["eventId"] = UUID().uuidString.lowercased(); value["runtimeId"] = runtime
            value["sequence"] = sequence; value["at"] = ISO8601DateFormatter().string(from: Date())
            value["component"] = "macos.resident"
            value["version"] = Bundle.main.object(forInfoDictionaryKey: "CFBundleShortVersionString") ?? "development"
            var data = try JSONSerialization.data(withJSONObject: value, options: [.sortedKeys]); data.append(10)
            let fd = open(path!.path, O_WRONLY | O_APPEND | O_NOFOLLOW | O_CLOEXEC)
            guard fd >= 0 else { throw CocoaError(.fileWriteUnknown) }
            defer { close(fd) }
            guard fstat(fd, &st) == 0, st.st_mode & S_IFMT == S_IFREG, st.st_uid == getuid(), st.st_nlink == 1,
                  fchmod(fd, 0o600) == 0 else { throw CocoaError(.fileWriteNoPermission) }
            try data.withUnsafeBytes { bytes in
                var count = 0
                while count < data.count {
                    let n = Darwin.write(fd, bytes.baseAddress!.advanced(by: count), data.count - count)
                    if n < 0 && errno == EINTR { continue }
                    guard n > 0 else { throw CocoaError(.fileWriteUnknown) }
                    count += n
                }
            }
            guard fsync(fd) == 0 else { throw CocoaError(.fileWriteUnknown) }
            // Request the macOS full device-cache flush, beyond a buffered write.
            guard fcntl(fd, F_FULLFSYNC) == 0 else { throw CocoaError(.fileWriteUnknown) }
            try prune(stream)
            if stream == "audit" { errorCode = nil } else { diagnosticsAvailable = true }
            return true
        } catch {
            if stream == "audit" { errorCode = "audit_storage_unavailable" } else { diagnosticsAvailable = false }
            return false
        }
    }
    @discardableResult func event(_ operation: String, accepted: Bool = true) -> Bool {
        append("audit", ["phase": "event", "operation": Self.token(operation), "accepted": accepted])
    }
    @discardableResult func diagnostic(_ operation: String, code: String) -> Bool {
        append("diagnostics", ["phase": "event", "operation": Self.token(operation), "errorCode": Self.token(code)])
    }
    func begin(_ request: [String: Any], caller: CallerIdentity? = nil) -> Bool {
        let operation = request["operation"] as? String ?? ""
        return !Self.tracked(operation) || append("audit", ["phase": "intent", "operation": Self.known.contains(operation) ? operation : "unknown",
            "requestId": Self.correlation(request["requestId"]), "callerPid": Int(caller?.pid ?? 0), "effect": "unknown", "uncertainty": "outcome_pending"])
    }
    func record(_ result: [String: Any]) -> Bool {
        let operation = result["operation"] as? String ?? ""
        if !Self.tracked(operation) { return true }
        var value: [String: Any] = ["phase": "result", "operation": Self.known.contains(operation) ? operation : "unknown",
            "requestId": Self.correlation(result["requestId"]), "accepted": result["accepted"] as? Bool == true,
            "elapsedMs": result["elapsedMs"] as? Int ?? 0]
        for key in ["generation", "actualRoute", "delivery", "effect", "uncertainty", "errorCode"] {
            value[key] = result[key] == nil || result[key] is NSNull ? NSNull() : Self.token(result[key]) as Any
        }
        if result["errorCode"] != nil && !(result["errorCode"] is NSNull) || debugUntil > ProcessInfo.processInfo.systemUptime { append("diagnostics", value) }
        return append("audit", value)
    }
    var health: [String: Any] { ["available": errorCode == nil, "errorCode": errorCode.map { $0 as Any } ?? NSNull(),
        "diagnosticsAvailable": diagnosticsAvailable, "historyGap": historyGap, "debugRemainingSeconds": max(0, Int(debugUntil - ProcessInfo.processInfo.systemUptime)),
        "auditDays": 30, "diagnosticDays": 7, "auditBytes": auditBytes, "diagnosticBytes": diagnosticBytes] }
    private func read(_ stream: String, limit: Int, offset: Int = 0, operation: String = "", outcome: String = "") -> [[String: Any]] {
        var result: [[String: Any]] = []; var skipped = 0
        for path in paths(stream).reversed() {
            let fd = open(path.path, O_RDONLY | O_NOFOLLOW | O_CLOEXEC)
            guard fd >= 0 else { continue }
            let file = FileHandle(fileDescriptor: fd, closeOnDealloc: true)
            var st = stat()
            guard fstat(fd, &st) == 0, st.st_mode & S_IFMT == S_IFREG, st.st_nlink == 1, st.st_size <= segmentBytes + 8192 else { continue }
            guard let data = try? file.readToEnd(), let text = String(data: data, encoding: .utf8) else { continue }
            var lines = text.components(separatedBy: "\n")
            if lines.last == "" { lines.removeLast() }
            else { lines.removeLast(); historyGap = true }
            for line in lines.reversed() {
                guard let row = try? JSONSerialization.jsonObject(with: Data(line.utf8)) as? [String: Any],
                      row["schema"] as? String == "machine-control-desktop-event/v0",
                      ["eventId", "operation", "at", "phase"].allSatisfy({ row[$0] is String }) else { historyGap = true; continue }
                if !operation.isEmpty && !(row["operation"] as? String ?? "").localizedCaseInsensitiveContains(operation) { continue }
                if !outcome.isEmpty && row["accepted"] as? Bool != (outcome == "accepted") { continue }
                if skipped < offset { skipped += 1; continue }
                result.append(row)
                if result.count >= limit { return result }
            }
        }
        return result
    }
    private func earliest(_ stream: String) -> Any {
        guard let path = paths(stream).first else { return NSNull() }
        let fd = open(path.path, O_RDONLY | O_NOFOLLOW | O_CLOEXEC)
        guard fd >= 0 else { return NSNull() }
        let file = FileHandle(fileDescriptor: fd, closeOnDealloc: true)
        guard let data = try? file.read(upToCount: 8192), let end = data.firstIndex(of: 10),
              let row = try? JSONSerialization.jsonObject(with: Data(data.prefix(upTo: end))) as? [String: Any],
              let at = row["at"] as? String else { historyGap = true; return NSNull() }
        return at
    }
    func query(offset: Int = 0, operation: String = "", outcome: String = "", stream: String = "audit") -> [String: Any] {
        lock.lock(); defer { lock.unlock() }
        let rows = read(stream, limit: 51, offset: min(max(offset, 0), 1_000_000), operation: operation, outcome: outcome)
        return ["entries": Array(rows.prefix(50)), "hasMore": rows.count > 50, "offset": offset, "earliestAt": earliest(stream), "health": health]
    }
    func preview() -> [String: Any] {
        lock.lock(); defer { lock.unlock() }
        return ["schema": "machine-control-diagnostics-export/v0", "health": health, "audit": read("audit", limit: 500), "diagnostics": read("diagnostics", limit: 500)]
    }
    func export() throws -> String {
        lock.lock(); defer { lock.unlock() }
        let dir = root.appendingPathComponent("exports"); try privateDirectory(dir)
        let path = dir.appendingPathComponent("diagnostics.json")
        let temporary = dir.appendingPathComponent(UUID().uuidString + ".tmp")
        let fd = open(temporary.path, O_CREAT | O_EXCL | O_WRONLY | O_NOFOLLOW | O_CLOEXEC, 0o600)
        guard fd >= 0 else { throw CocoaError(.fileWriteUnknown) }
        let file = FileHandle(fileDescriptor: fd, closeOnDealloc: true)
        try file.write(contentsOf: JSONSerialization.data(withJSONObject: preview(), options: [.sortedKeys]))
        try file.synchronize()
        guard rename(temporary.path, path.path) == 0 else { throw CocoaError(.fileWriteUnknown) }
        return path.path
    }
}
