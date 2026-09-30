import Darwin
import Foundation

@_silgen_name("proc_pidpath")
func mcProcPIDPath(_ pid: Int32, _ buffer: UnsafeMutableRawPointer, _ size: UInt32) -> Int32

/// Kernel-observed peer of a resident connection plus its parent chain.
/// This is informative: it helps a person judge a request and fills the
/// audit log, but same-user processes can impersonate one another.
struct CallerIdentity {
    struct Process {
        let pid: pid_t
        let name: String
        let path: String?
    }

    let uid: uid_t
    let chain: [Process]

    var pid: pid_t { chain.first?.pid ?? 0 }

    static func of(socket descriptor: Int32) -> CallerIdentity {
        var uid: uid_t = 0
        var gid: gid_t = 0
        _ = getpeereid(descriptor, &uid, &gid)
        var pid: pid_t = 0
        var length = socklen_t(MemoryLayout<pid_t>.size)
        guard getsockopt(descriptor, SOL_LOCAL, LOCAL_PEERPID, &pid, &length) == 0,
              pid > 0 else {
            return CallerIdentity(uid: uid, chain: [])
        }
        return CallerIdentity(uid: uid, chain: ancestry(of: pid))
    }

    static func ancestry(of start: pid_t, limit: Int = 8) -> [Process] {
        var chain: [Process] = []
        var pid = start
        while pid > 1, chain.count < limit {
            var info = kinfo_proc()
            var size = MemoryLayout<kinfo_proc>.stride
            var mib: [Int32] = [CTL_KERN, KERN_PROC, KERN_PROC_PID, pid]
            guard sysctl(&mib, 4, &info, &size, nil, 0) == 0, size > 0 else { break }
            let name = withUnsafeBytes(of: info.kp_proc.p_comm) { raw in
                String(decoding: raw.prefix { $0 != 0 }, as: UTF8.self)
            }
            var buffer = [UInt8](repeating: 0, count: 4 * Int(MAXPATHLEN))
            let count = mcProcPIDPath(pid, &buffer, UInt32(buffer.count))
            let path = count > 0 ? String(decoding: buffer.prefix(Int(count)), as: UTF8.self) : nil
            chain.append(Process(pid: pid, name: path.map { ($0 as NSString).lastPathComponent } ?? name,
                                 path: path))
            let parent = info.kp_eproc.e_ppid
            if parent == pid { break }
            pid = parent
        }
        return chain
    }

    /// A short human-readable chain, such as `node ← claude ← zsh`.
    var summary: String {
        guard !chain.isEmpty else { return "unknown process" }
        return chain.prefix(5).map(\.name).joined(separator: " ← ")
    }

    var json: [String: Any] {
        [
            "assurance": "unverified_same_user",
            "uid": Int(uid),
            "processes": chain.map { process -> [String: Any] in
                ["pid": Int(process.pid), "name": process.name,
                 "path": process.path.map { $0 as Any } ?? NSNull()]
            },
        ]
    }
}
