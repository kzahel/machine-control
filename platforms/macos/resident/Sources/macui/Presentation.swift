import Darwin
import Foundation

enum PresentationProfile: String, CaseIterable {
    case personal, minimal, appliance
}

/// User-owned presentation only. Never loads or writes DeploymentPolicy.
struct PresentationPreference {
    let profile: PresentationProfile
    let diagnostic: String?
    var json: [String:Any] {
        ["schema":"machine-control-presentation/v1", "profile":profile.rawValue,
         "diagnostic":diagnostic ?? NSNull()]
    }
}

struct PresentationStore {
    let directory: String
    init(socketPath: String) { directory = (socketPath as NSString).deletingLastPathComponent }
    private let filename = "presentation.json"

    private func openDirectory(create: Bool) throws -> Int32 {
        if create && !FileManager.default.fileExists(atPath:directory) {
            try FileManager.default.createDirectory(atPath:directory, withIntermediateDirectories:true,
                attributes:[.posixPermissions:0o700])
        }
        let fd = Darwin.open(directory, O_RDONLY | O_DIRECTORY | O_NOFOLLOW | O_CLOEXEC)
        guard fd >= 0 else { throw MacUIError.permission("presentation_directory_unavailable") }
        var info = stat()
        guard fstat(fd, &info) == 0, info.st_uid == getuid(), info.st_mode & 0o022 == 0 else {
            Darwin.close(fd); throw MacUIError.permission("presentation_directory_unsafe")
        }
        return fd
    }
    func load() -> PresentationPreference {
        do {
            let dir = try openDirectory(create:false); defer { Darwin.close(dir) }
            let fd = openat(dir, filename, O_RDONLY | O_NOFOLLOW | O_CLOEXEC | O_NONBLOCK)
            if fd < 0 && errno == ENOENT { return PresentationPreference(profile:.personal, diagnostic:nil) }
            guard fd >= 0 else { throw MacUIError.permission("presentation_file_unavailable") }
            defer { Darwin.close(fd) }
            var info = stat()
            guard fstat(fd, &info) == 0, info.st_uid == getuid(),
                  info.st_mode & S_IFMT == S_IFREG, info.st_mode & 0o077 == 0,
                  info.st_size > 0, info.st_size <= 4096 else {
                throw MacUIError.permission("presentation_file_unsafe")
            }
            var bytes = [UInt8](repeating:0, count:4097)
            let count = Darwin.read(fd, &bytes, bytes.count)
            guard count > 0, count <= 4096,
                  let value = try JSONSerialization.jsonObject(with:Data(bytes.prefix(count))) as? [String:Any],
                  value["schema"] as? String == "machine-control-presentation/v1",
                  let name = value["profile"] as? String,
                  let profile = PresentationProfile(rawValue:name) else {
                throw MacUIError.usage("presentation_configuration_invalid")
            }
            return PresentationPreference(profile:profile, diagnostic:nil)
        } catch {
            // Missing directory is a normal first launch; unsafe existing paths
            // still get a diagnostic and cannot change authorization.
            if !FileManager.default.fileExists(atPath:directory) {
                return PresentationPreference(profile:.personal, diagnostic:nil)
            }
            return PresentationPreference(profile:.personal, diagnostic:String(describing:error))
        }
    }
    func save(_ profile: PresentationProfile) throws {
        let dir = try openDirectory(create:true); defer { Darwin.close(dir) }
        var existing = stat()
        if fstatat(dir, filename, &existing, AT_SYMLINK_NOFOLLOW) == 0 {
            guard existing.st_uid == getuid(), existing.st_mode & S_IFMT == S_IFREG else {
                throw MacUIError.permission("presentation_file_unsafe")
            }
        } else if errno != ENOENT { throw MacUIError.action("presentation_file_unavailable") }
        let temporary = ".presentation-\(UUID().uuidString)"
        let fd = openat(dir, temporary, O_WRONLY | O_CREAT | O_EXCL | O_NOFOLLOW | O_CLOEXEC, 0o600)
        guard fd >= 0 else { throw MacUIError.action("presentation_write_failed") }
        defer { Darwin.close(fd); unlinkat(dir, temporary, 0) }
        let bytes = try JSONSerialization.data(withJSONObject:["schema":"machine-control-presentation/v1", "profile":profile.rawValue], options:[.sortedKeys])
        let count = bytes.withUnsafeBytes { Darwin.write(fd, $0.baseAddress!, bytes.count) }
        guard count == bytes.count, fsync(fd) == 0, renameat(dir, temporary, dir, filename) == 0 else {
            throw MacUIError.action("presentation_write_failed")
        }
        _ = fsync(dir)
    }
}

/// Supported local operator/provisioning command, handled before UI startup.
/// Same-user ownership is an operational boundary, not shell containment.
func runPresentationCommand(_ arguments: [String]) throws -> Bool {
    guard arguments.first == "presentation" else { return false }
    var args = Array(arguments.dropFirst())
    var socketPath = defaultResidentSocket
    if let index = args.firstIndex(of:"--socket") {
        guard index + 1 < args.count else { throw MacUIError.usage("--socket requires a path") }
        socketPath = args[index + 1]; args.removeSubrange(index...index + 1)
    }
    let store = PresentationStore(socketPath:socketPath)
    if args == ["reset"] { try store.save(.personal) }
    else if args.count == 2, args[0] == "set", let profile = PresentationProfile(rawValue:args[1]) { try store.save(profile) }
    else if args != ["status"] {
        throw MacUIError.usage("Usage: macui presentation status|set personal|minimal|appliance|reset [--socket SOCKET]")
    }
    var result = store.load().json
    result["application"] = "live runtime applies saved changes after pending approval; temporary launch overrides last until restart"
    print(String(decoding:try JSONSerialization.data(withJSONObject:result, options:[.sortedKeys]), as:UTF8.self))
    return true
}
