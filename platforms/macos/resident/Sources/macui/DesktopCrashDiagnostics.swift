import CryptoKit
import Darwin
import Foundation
import MachO

/// Loaded-image UUIDs bind an OS report to the matching symbol archive without
/// recording executable paths, request payloads, or machine identity.
enum DesktopBuildIdentity {
    static func imageUUID(_ index: UInt32) -> String? {
        guard let header = _dyld_get_image_header(index), header.pointee.magic == MH_MAGIC_64,
              header.pointee.ncmds <= 4096 else { return nil }
        let full = UnsafeRawPointer(header).assumingMemoryBound(to: mach_header_64.self).pointee
        guard full.sizeofcmds <= 1_048_576 else { return nil }
        var pointer = UnsafeRawPointer(header).advanced(by: MemoryLayout<mach_header_64>.size)
        let end = pointer.advanced(by: Int(full.sizeofcmds))
        for _ in 0..<full.ncmds {
            guard pointer + MemoryLayout<load_command>.size <= end else { return nil }
            let command = pointer.load(as: load_command.self)
            guard command.cmdsize >= MemoryLayout<load_command>.size,
                  pointer + Int(command.cmdsize) <= end else { return nil }
            if command.cmd == LC_UUID, command.cmdsize >= MemoryLayout<uuid_command>.size {
                return UUID(uuid: pointer.load(as: uuid_command.self).uuid).uuidString.lowercased()
            }
            pointer = pointer.advanced(by: Int(command.cmdsize))
        }
        return nil
    }
    static func sanitized(_ value: [String:Any]) -> [String:Any] {
        var result: [String:Any] = [:]
        for key in ["executableUUID", "nativeFrameworkUUID"] {
            result[key] = (value[key] as? String).flatMap { UUID(uuidString:$0)?.uuidString.lowercased() } as Any? ?? NSNull()
        }
        let raw = value["sourceRevision"] as? String ?? ""
        result["sourceRevision"] = raw.range(of:"^[a-fA-F0-9]{40}$", options:.regularExpression) != nil ? raw.lowercased() : NSNull()
        return result
    }
    static var current: [String: Any] {
        let raw = Bundle.main.object(forInfoDictionaryKey: "MCSourceRevision") as? String ?? ""
        let revision: Any = raw.range(of: "^[a-fA-F0-9]{40}$", options: .regularExpression) != nil ? raw.lowercased() : NSNull()
        var framework: String?
        for index in 0..<_dyld_image_count() {
            if let name = _dyld_get_image_name(index), URL(fileURLWithPath: String(cString:name)).lastPathComponent == "MCResident" {
                framework = imageUUID(index); break
            }
        }
        return ["sourceRevision": revision, "executableUUID": imageUUID(0) as Any? ?? NSNull(),
                "nativeFrameworkUUID": framework as Any? ?? NSNull()]
    }
}

/// Fixed local OS-report inventory. Reading is only invoked by an explicit
/// operator preview. Unknown formats, redirects and oversized files are skipped.
struct DesktopCrashReports {
    var directory = FileManager.default.homeDirectoryForCurrentUser.appendingPathComponent("Library/Logs/DiagnosticReports")
    var now: () -> Date = { Date() }
    let maximumReportBytes = 2_097_152
    func read() -> [[String: Any]] {
        var info = stat()
        guard lstat(directory.path, &info) == 0, info.st_mode & S_IFMT == S_IFDIR,
              info.st_uid == getuid(),
              let entries = try? FileManager.default.contentsOfDirectory(at:directory, includingPropertiesForKeys:nil) else { return [] }
        let paths = entries.filter { $0.lastPathComponent.hasPrefix("macui-") && $0.pathExtension == "ips" }.sorted { $0.lastPathComponent > $1.lastPathComponent }
        var result: [[String: Any]] = []
        for path in paths.prefix(100) {
            let fd = open(path.path, O_RDONLY | O_NOFOLLOW | O_CLOEXEC | O_NONBLOCK)
            guard fd >= 0 else { continue }
            let file = FileHandle(fileDescriptor:fd, closeOnDealloc:true)
            guard fstat(fd, &info) == 0, info.st_mode & S_IFMT == S_IFREG,
                  info.st_uid == getuid(), info.st_nlink == 1, info.st_size > 0,
                  info.st_size <= maximumReportBytes,
                  Double(info.st_mtimespec.tv_sec) >= now().timeIntervalSince1970 - 30 * 86400,
                  let data = try? file.read(upToCount:maximumReportBytes + 1), data.count <= maximumReportBytes,
                  let split = data.firstIndex(of:10),
                  let header = try? JSONSerialization.jsonObject(with:data.prefix(upTo:split)) as? [String:Any],
                  let body = try? JSONSerialization.jsonObject(with:data.suffix(from:data.index(after:split))) as? [String:Any],
                  header["bundleID"] as? String == "org.machine-control.app" ||
                    (body["bundleInfo"] as? [String:Any])?["CFBundleIdentifier"] as? String == "org.machine-control.app",
                  let text = String(data:data, encoding:.utf8) else { continue }
            result.append(["reportId": SHA256.hash(data:data).map { String(format:"%02x", $0) }.joined(),
                           "sizeBytes": data.count, "text":text])
            if result.count == 3 { break }
        }
        return result
    }
}

/// A marker means a runtime reached its serving state, not that it crashed.
/// Missing clean termination is reported as unknown/unclean, never replay advice.
final class DesktopExitMarker {
    let path: URL
    let runtime: String
    init(root: URL, instance: String, runtime: String) {
        let key = SHA256.hash(data:Data(instance.utf8)).prefix(12).map { String(format:"%02x", $0) }.joined()
        path = root.appendingPathComponent("lifecycle/\(key).json"); self.runtime = runtime
    }
    private func locked<T>(_ body: () throws -> T) throws -> T {
        // The lock has a stable inode: locking the marker itself would cease
        // to protect it when start atomically replaces that file. Never wait
        // on another process on the coordinator; tracking can fail separately.
        let fd = open(path.deletingPathExtension().appendingPathExtension("lock").path,
                      O_CREAT | O_RDWR | O_NOFOLLOW | O_CLOEXEC | O_NONBLOCK, 0o600)
        guard fd >= 0 else { throw MacUIError.action("exit_marker_unavailable") }
        defer { Darwin.close(fd) }
        var info = stat()
        guard fstat(fd,&info) == 0, info.st_mode & S_IFMT == S_IFREG,
              info.st_uid == getuid(), info.st_nlink == 1, info.st_mode & 0o077 == 0,
              flock(fd, LOCK_EX | LOCK_NB) == 0 else { throw MacUIError.action("exit_marker_unavailable") }
        defer { flock(fd, LOCK_UN) }
        return try body()
    }
    private func read() throws -> [String:Any]? {
        let fd = open(path.path, O_RDONLY | O_NOFOLLOW | O_CLOEXEC | O_NONBLOCK)
        if fd < 0 && errno == ENOENT { return nil }
        guard fd >= 0 else { throw MacUIError.action("exit_marker_unavailable") }
        let file = FileHandle(fileDescriptor:fd, closeOnDealloc:true)
        var info = stat()
        guard fstat(fd,&info) == 0, info.st_mode & S_IFMT == S_IFREG, info.st_uid == getuid(),
              info.st_nlink == 1, info.st_mode & 0o077 == 0, info.st_size <= 4096,
              let data = try file.read(upToCount:4097), data.count <= 4096,
              let value = try JSONSerialization.jsonObject(with:data) as? [String:Any],
              value["schema"] as? String == "machine-control-runtime-exit/v0",
              let id = value["runtimeId"] as? String, UUID(uuidString:id) != nil else {
            throw MacUIError.action("exit_marker_invalid")
        }
        return value
    }
    func start(build: [String:Any]) throws -> [String:Any]? {
        try locked { try startLocked(build:build) }
    }
    private func startLocked(build: [String:Any]) throws -> [String:Any]? {
        let previous = try read()
        let data = try JSONSerialization.data(withJSONObject:["schema":"machine-control-runtime-exit/v0", "runtimeId":runtime, "build":build], options:[.sortedKeys])
        let temporary = path.deletingLastPathComponent().appendingPathComponent(UUID().uuidString)
        let fd = open(temporary.path, O_CREAT | O_EXCL | O_WRONLY | O_NOFOLLOW | O_CLOEXEC, 0o600)
        guard fd >= 0 else { throw MacUIError.action("exit_marker_unavailable") }
        defer { Darwin.close(fd); unlink(temporary.path) }
        try data.withUnsafeBytes { bytes in
            guard Darwin.write(fd,bytes.baseAddress!,data.count) == data.count, fsync(fd) == 0 else { throw MacUIError.action("exit_marker_unavailable") }
        }
        guard rename(temporary.path,path.path) == 0 else { throw MacUIError.action("exit_marker_unavailable") }
        return previous
    }
    func finish() throws {
        try locked {
            guard try read()?["runtimeId"] as? String == runtime else { return }
            guard unlink(path.path) == 0 || errno == ENOENT else { throw MacUIError.action("exit_marker_unavailable") }
        }
    }
}
