import Darwin
import Foundation
import Security

/// Only verified callers (Tactical 161). An opt-in picket fence on the
/// ordinary resident socket: the peer must be Machine Control's own signed
/// client, and the nearest code-signed, non-platform ancestor must be an app
/// the operator approved by Team ID and signing identifier. It is not
/// same-user containment: anything an approved app runs, and same-user code
/// that changes an approved app's environment or this support directory,
/// still passes.

/// Kernel facts for one live process, bound by PID and start time.
struct CallerProcessRecord: Equatable {
    let pid: pid_t
    let parent: pid_t
    /// Microseconds since the epoch; a reused PID always starts later.
    let started: UInt64
}

/// Code-signing facts for one process. `teamID` is set only when the code
/// is valid against an Apple-anchored requirement naming that Team ID, so a
/// self-signed certificate cannot borrow a publisher's identity.
struct CallerCodeFacts: Equatable {
    var valid = false
    var platform = false
    var teamID: String?
    var identifier: String?
    /// Static code location: an `.app` bundle or an executable file.
    var path: String?
    var name = "unknown"
    var publisher: String?
    var bundle: Bool { path?.hasSuffix(".app") == true }
}

/// What a refused caller learns about its host; never a full requirement.
struct CallerHost: Equatable {
    let name: String
    let publisher: String
    let teamID: String?
    let identifier: String?
    let approvable: Bool
    var key: String? { teamID.flatMap { team in identifier.map { team + "/" + $0 } } }
    var json: [String:Any] { ["name":name, "publisher":publisher, "approvable":approvable] }
}

enum CallerVerdict: Equatable {
    case verified(CallerHost)
    case refused(String, CallerHost?)
}

/// The resident's own signature decides whether verification is possible.
struct CallerOwnIdentity: Equatable {
    let teamID: String?
    let bundlePath: String?
    let unsupportedReason: String?

    static let unsupportedDevelopment = CallerOwnIdentity(teamID:nil, bundlePath:nil, unsupportedReason:"development_signature")

    /// A source or ad-hoc build has no publisher to anchor its own clients
    /// to, so the mode is unsupported there rather than silently weaker.
    static func current() -> CallerOwnIdentity {
        var own: SecCode?, ownStatic: SecStaticCode?, raw: CFDictionary?, location: CFURL?
        guard SecCodeCopySelf([], &own) == errSecSuccess, let own,
              SecCodeCopyStaticCode(own, [], &ownStatic) == errSecSuccess, let ownStatic,
              SecCodeCopySigningInformation(ownStatic, SecCSFlags(rawValue:kSecCSSigningInformation), &raw) == errSecSuccess,
              let info = raw as? [String:Any], SecCodeCopyPath(ownStatic, [], &location) == errSecSuccess,
              let location = location as URL? else { return unsupportedDevelopment }
        guard let team = info[kSecCodeInfoTeamIdentifier as String] as? String, CallerRequirement.validTeam(team),
              let requirement = CallerRequirement.compile(CallerRequirement.team(team)),
              SecCodeCheckValidity(own, [], requirement) == errSecSuccess else { return unsupportedDevelopment }
        let path = location.resolvingSymlinksInPath().path
        guard path.hasSuffix(".app") else {
            return CallerOwnIdentity(teamID:team, bundlePath:nil, unsupportedReason:"unbundled_build")
        }
        return CallerOwnIdentity(teamID:team, bundlePath:path, unsupportedReason:nil)
    }

    /// The installed app's own executable or its bundled Python runtime.
    func ownsClient(_ facts: CallerCodeFacts) -> Bool {
        guard let teamID, let bundlePath, facts.valid, facts.teamID == teamID,
              let path = facts.path.map({ URL(fileURLWithPath:$0).resolvingSymlinksInPath().path }) else { return false }
        return path == bundlePath || path.hasPrefix(bundlePath + "/Contents/Resources/mc-cli/python/bin/")
    }
}

enum CallerRequirement {
    static func validTeam(_ value: String) -> Bool {
        value.utf8.count == 10 && value.unicodeScalars.allSatisfy { ("A"..."Z").contains($0) || ("0"..."9").contains($0) }
    }
    static func validIdentifier(_ value: String) -> Bool {
        guard let first = value.unicodeScalars.first, (1...255).contains(value.utf8.count),
              CharacterSet.alphanumerics.contains(first) else { return false }
        return value.unicodeScalars.allSatisfy {
            $0.isASCII && (CharacterSet.alphanumerics.contains($0) || ".-_".unicodeScalars.contains($0))
        }
    }
    /// Apple-issued publisher identity (Developer ID or App Store chain).
    static func team(_ team: String) -> String {
        "anchor apple generic and certificate leaf[subject.OU] = \"\(team)\""
    }
    /// The stored approval: exactly one publisher's exactly one app.
    static func host(team: String, identifier: String) -> String? {
        guard validTeam(team), validIdentifier(identifier) else { return nil }
        return "anchor apple generic and identifier \"\(identifier)\" and certificate leaf[subject.OU] = \"\(team)\""
    }
    static func compile(_ text: String) -> SecRequirement? {
        var requirement: SecRequirement?
        guard SecRequirementCreateWithString(text as CFString, [], &requirement) == errSecSuccess else { return nil }
        return requirement
    }
}

/// Process and code-signing observations. The default reads the kernel and
/// Security framework; tests substitute deterministic process trees.
struct CallerProcessSource {
    /// PID and code facts of the socket peer, from its kernel audit token.
    var peer: (Data, String) -> (pid_t, CallerCodeFacts?) = CallerProcessSource.livePeer
    /// True while the exact audit-token process is still alive.
    var peerAlive: (Data) -> Bool = CallerProcessSource.livePeerAlive
    var record: (pid_t) -> CallerProcessRecord? = CallerProcessSource.liveRecord
    var code: (pid_t) -> CallerCodeFacts? = CallerProcessSource.liveCode
    /// Dynamic strict validity of a live PID against a requirement.
    var satisfies: (pid_t, String) -> Bool = CallerProcessSource.liveSatisfies

    static func auditToken(_ descriptor: Int32) -> Data? {
        var token = audit_token_t()
        var size = socklen_t(MemoryLayout<audit_token_t>.size)
        guard getsockopt(descriptor, SOL_LOCAL, LOCAL_PEERTOKEN, &token, &size) == 0,
              size == MemoryLayout<audit_token_t>.size else { return nil }
        return withUnsafeBytes(of:&token) { Data($0) }
    }
    private static func guest(_ attributes: [CFString:Any]) -> SecCode? {
        var guest: SecCode?
        guard SecCodeCopyGuestWithAttributes(nil, attributes as CFDictionary, [], &guest) == errSecSuccess else { return nil }
        return guest
    }
    static func livePeer(_ token: Data, _ team: String) -> (pid_t, CallerCodeFacts?) {
        // audit_token_t: val[5] is the PID and val[7] its version, which the
        // Security framework checks so a reused PID cannot stand in.
        let pid = token.count == MemoryLayout<audit_token_t>.size
            ? token.withUnsafeBytes { $0.load(fromByteOffset:5 * 4, as:UInt32.self) } : 0
        guard let code = guest([kSecGuestAttributeAudit:token]) else { return (pid_t(bitPattern:pid), nil) }
        return (pid_t(bitPattern:pid), facts(code, anchorTeam:team))
    }
    static func livePeerAlive(_ token: Data) -> Bool {
        guard let code = guest([kSecGuestAttributeAudit:token]) else { return false }
        return SecCodeCheckValidity(code, [], nil) != OSStatus(errSecCSNoSuchCode)
    }
    static func liveRecord(_ pid: pid_t) -> CallerProcessRecord? {
        var info = proc_bsdinfo()
        let size = Int32(MemoryLayout<proc_bsdinfo>.size)
        guard pid > 0, proc_pidinfo(pid, PROC_PIDTBSDINFO, 0, &info, size) == size,
              pid_t(bitPattern:info.pbi_pid) == pid else { return nil }
        return CallerProcessRecord(pid:pid, parent:pid_t(bitPattern:info.pbi_ppid),
            started:info.pbi_start_tvsec * 1_000_000 + info.pbi_start_tvusec)
    }
    static func liveCode(_ pid: pid_t) -> CallerCodeFacts? {
        guard let code = guest([kSecGuestAttributePid:Int(pid)]) else {
            var facts = CallerCodeFacts()
            var buffer = [UInt8](repeating:0, count:4 * Int(MAXPATHLEN))
            let count = mcProcPIDPath(pid, &buffer, UInt32(buffer.count))
            guard count > 0 else { return nil }
            let path = String(decoding:buffer.prefix(Int(count)), as:UTF8.self)
            facts.path = path.range(of:".app/Contents/MacOS/").map { String(path[..<$0.lowerBound]) + ".app" } ?? path
            facts.name = displayName(facts.path!, plist:nil)
            return facts
        }
        return facts(code, anchorTeam:nil)
    }
    static func liveSatisfies(_ pid: pid_t, _ requirement: String) -> Bool {
        guard let compiled = CallerRequirement.compile(requirement),
              let code = guest([kSecGuestAttributePid:Int(pid)]) else { return false }
        return SecCodeCheckValidity(code, SecCSFlags(rawValue:kSecCSStrictValidate), compiled) == errSecSuccess
    }

    /// Reads signing information, then accepts a Team ID only when the live
    /// code is valid against an Apple-anchored requirement for that team.
    static func facts(_ code: SecCode, anchorTeam: String?) -> CallerCodeFacts {
        var facts = CallerCodeFacts()
        var staticCode: SecStaticCode?, raw: CFDictionary?, location: CFURL?
        guard SecCodeCopyStaticCode(code, [], &staticCode) == errSecSuccess, let staticCode else { return facts }
        if SecCodeCopyPath(staticCode, [], &location) == errSecSuccess, let url = location as URL? { facts.path = url.path }
        guard SecCodeCopySigningInformation(staticCode, SecCSFlags(rawValue:kSecCSSigningInformation), &raw) == errSecSuccess,
              let info = raw as? [String:Any] else { facts.name = displayName(facts.path ?? "", plist:nil); return facts }
        facts.identifier = info[kSecCodeInfoIdentifier as String] as? String
        facts.name = displayName(facts.path ?? "", plist:info[kSecCodeInfoPList as String] as? [String:Any])
        let strict = SecCSFlags(rawValue:kSecCSStrictValidate)
        if (info[kSecCodeInfoPlatformIdentifier as String] as? NSNumber)?.intValue ?? 0 != 0,
           let apple = CallerRequirement.compile("anchor apple") {
            facts.platform = SecCodeCheckValidity(code, strict, apple) == errSecSuccess
            facts.valid = facts.platform
        }
        if !facts.platform, let team = info[kSecCodeInfoTeamIdentifier as String] as? String,
           CallerRequirement.validTeam(team), anchorTeam == nil || anchorTeam == team,
           let requirement = CallerRequirement.compile(CallerRequirement.team(team)) {
            facts.valid = SecCodeCheckValidity(code, strict, requirement) == errSecSuccess
            if facts.valid {
                facts.teamID = team
                let certificates = info[kSecCodeInfoCertificates as String] as? [SecCertificate]
                facts.publisher = certificates?.first.flatMap { publisherName(SecCertificateCopySubjectSummary($0) as String?, team:team) }
            }
        }
        return facts
    }
    static func displayName(_ path: String, plist: [String:Any]?) -> String {
        let name = (plist?["CFBundleDisplayName"] as? String) ?? (plist?["CFBundleName"] as? String)
            ?? ((path as NSString).lastPathComponent as NSString).deletingPathExtension
        return boundedLabel(name.isEmpty ? "unknown" : name)
    }
    /// "Developer ID Application: Example Inc (TEAM)" becomes "Example Inc".
    static func publisherName(_ summary: String?, team: String) -> String? {
        guard var value = summary else { return nil }
        if let colon = value.range(of:": ") { value = String(value[colon.upperBound...]) }
        if value.hasSuffix(" (\(team))") { value.removeLast(team.count + 3) }
        guard !value.isEmpty, !value.hasPrefix("Apple Mac OS Application Signing") else { return nil }
        return boundedLabel(value)
    }
    static func boundedLabel(_ value: String) -> String {
        String(String(value.unicodeScalars.filter { !CharacterSet.controlCharacters.contains($0) }).prefix(80))
    }
}

/// A connection's verdict, computed off the main queue from immutable
/// inputs. PID reuse cannot splice another process into the chain: each
/// parent must have started no later than its child, and its signature is
/// evaluated between two observations of the same start time.
func evaluateCaller(token: Data, own: CallerOwnIdentity, approved: [CallerApproval],
                    source: CallerProcessSource, maximumHops: Int = 12) -> CallerVerdict {
    guard let team = own.teamID, own.unsupportedReason == nil else { return .refused("verification_unsupported", nil) }
    let (pid, peerFacts) = source.peer(token, team)
    guard pid > 1, var child = source.record(pid), source.peerAlive(token) else { return .refused("process_changed", nil) }
    guard let peerFacts, own.ownsClient(peerFacts) else { return .refused("peer_not_machine_control", nil) }
    for _ in 0..<maximumHops {
        let parentPID = child.parent
        if parentPID <= 1 { return .refused("detached", nil) }
        guard let parent = source.record(parentPID), parent.started <= child.started else {
            return .refused("process_changed", nil)
        }
        let facts = source.code(parentPID)
        guard let observed = source.record(parentPID), observed.started == parent.started else {
            return .refused("process_changed", nil)
        }
        child = observed
        guard let facts, !facts.platform else { continue }
        // Machine Control's own launcher and runtime are intermediates.
        if own.ownsClient(facts) { continue }
        if let teamID = facts.teamID, facts.valid {
            let identifier = facts.identifier.flatMap { CallerRequirement.validIdentifier($0) ? $0 : nil }
            let host = CallerHost(name:facts.name, publisher:facts.publisher ?? teamID, teamID:teamID,
                                  identifier:identifier, approvable:identifier != nil)
            guard let identifier, let approval = approved.first(where:{ $0.teamID == teamID && $0.identifier == identifier }),
                  let requirement = CallerRequirement.host(team:approval.teamID, identifier:approval.identifier) else {
                return .refused("unapproved_host", host)
            }
            let satisfied = source.satisfies(parentPID, requirement)
            guard source.record(parentPID)?.started == parent.started else { return .refused("process_changed", nil) }
            return satisfied ? .verified(host) : .refused("unapproved_host", host)
        }
        // An application bundle without a valid Apple-anchored publisher is a
        // host that cannot be approved by signature. Unsigned or ad-hoc
        // command-line tools and shells are intermediates, like platform
        // binaries.
        if facts.bundle {
            return .refused("unsigned_host", CallerHost(name:facts.name, publisher:"Unidentified developer",
                teamID:nil, identifier:nil, approvable:false))
        }
    }
    return .refused("ancestry_too_deep", nil)
}

struct CallerApproval: Equatable {
    let teamID: String
    let identifier: String
    let name: String
    let publisher: String
    let approvedAt: String
    var key: String { teamID + "/" + identifier }
    var json: [String:Any] { ["teamId":teamID, "identifier":identifier, "name":name, "publisher":publisher, "approvedAt":approvedAt] }
}

/// Operator-owned mode and approvals in a private file next to the socket.
/// Default off. A file that exists but cannot be trusted fails closed.
final class CallerVerificationStore {
    static let schema = "machine-control-caller-verification/v1"
    static let limit = 64
    private let directory: Int32
    private let file = "caller-verification.json"
    private(set) var storageReady = false
    private(set) var storageInvalid = false
    private(set) var enabled = false
    private(set) var approvals: [CallerApproval] = []
    private(set) var revision = UUID().uuidString
    /// Effective enforcement: an unreadable existing file never means off.
    var enforced: Bool { enabled || storageInvalid }

    init(directory path: String) {
        directory = open(path, O_RDONLY | O_DIRECTORY | O_NOFOLLOW | O_CLOEXEC)
        var info = stat()
        guard directory >= 0, fstat(directory, &info) == 0, info.st_uid == getuid(),
              info.st_mode & 0o077 == 0 else { return }
        storageReady = true
        let fd = openat(directory, file, O_RDONLY | O_NOFOLLOW | O_CLOEXEC)
        if fd < 0 { storageInvalid = errno != ENOENT; return }
        defer { Darwin.close(fd) }
        guard fstat(fd, &info) == 0, info.st_uid == getuid(), info.st_mode & S_IFMT == S_IFREG,
              info.st_mode & 0o077 == 0, info.st_nlink == 1, (1...65536).contains(info.st_size) else {
            storageInvalid = true; return
        }
        var bytes = [UInt8](repeating:0, count:65537)
        let size = read(fd, &bytes, bytes.count)
        guard size > 0, size == info.st_size else { storageInvalid = true; return }
        guard let raw = (try? JSONSerialization.jsonObject(with:Data(bytes.prefix(size)))) as? [String:Any],
              Set(raw.keys) == ["schema", "mode", "approvedHosts"], raw["schema"] as? String == Self.schema,
              let mode = raw["mode"] as? String, ["off", "verified_only"].contains(mode),
              let hosts = raw["approvedHosts"] as? [[String:Any]], hosts.count <= Self.limit else {
            storageInvalid = true; return
        }
        var parsed: [CallerApproval] = []
        for host in hosts {
            guard Set(host.keys) == ["teamId", "identifier", "name", "publisher", "approvedAt"],
                  let team = host["teamId"] as? String, let identifier = host["identifier"] as? String,
                  CallerRequirement.host(team:team, identifier:identifier) != nil,
                  let name = host["name"] as? String, let publisher = host["publisher"] as? String,
                  let at = host["approvedAt"] as? String, name.count <= 80, publisher.count <= 80, at.count <= 40,
                  !parsed.contains(where:{ $0.teamID == team && $0.identifier == identifier }) else {
                storageInvalid = true; return
            }
            parsed.append(CallerApproval(teamID:team, identifier:identifier, name:name, publisher:publisher, approvedAt:at))
        }
        enabled = mode == "verified_only"; approvals = parsed
    }
    deinit { if directory >= 0 { Darwin.close(directory) } }

    func configure(enabled value: Bool) throws {
        try commit(enabled:value, approvals:storageInvalid ? [] : approvals)
    }
    func approve(_ host: CallerHost, at date: Date = Date()) throws {
        guard host.approvable, let team = host.teamID, let identifier = host.identifier,
              CallerRequirement.host(team:team, identifier:identifier) != nil else {
            throw MacUIError.permission("caller_host_not_approvable")
        }
        guard !storageInvalid else { throw MacUIError.action("caller_verification_storage_invalid") }
        if approvals.contains(where:{ $0.teamID == team && $0.identifier == identifier }) { return }
        guard approvals.count < Self.limit else { throw MacUIError.action("caller_approval_limit") }
        let stamp = ISO8601DateFormatter().string(from:date)
        try commit(enabled:enabled, approvals:approvals + [CallerApproval(teamID:team, identifier:identifier,
            name:host.name, publisher:host.publisher, approvedAt:stamp)])
    }
    func remove(team: String, identifier: String) throws {
        guard !storageInvalid else { throw MacUIError.action("caller_verification_storage_invalid") }
        try commit(enabled:enabled, approvals:approvals.filter { !($0.teamID == team && $0.identifier == identifier) })
    }
    private func commit(enabled value: Bool, approvals list: [CallerApproval]) throws {
        try persist(enabled:value, approvals:list)
        enabled = value; approvals = list; storageInvalid = false; revision = UUID().uuidString
    }
    private func persist(enabled value: Bool, approvals list: [CallerApproval]) throws {
        var info = stat()
        guard storageReady, fstat(directory, &info) == 0, info.st_uid == getuid(),
              info.st_mode & 0o077 == 0 else { throw MacUIError.action("caller_verification_storage_unavailable") }
        let data = try JSONSerialization.data(withJSONObject:["schema":Self.schema,
            "mode":value ? "verified_only" : "off", "approvedHosts":list.map(\.json)], options:[.sortedKeys])
        guard data.count <= 65536 else { throw MacUIError.action("caller_verification_storage_unavailable") }
        let temporary = file + "." + UUID().uuidString
        let fd = openat(directory, temporary, O_WRONLY | O_CREAT | O_EXCL | O_NOFOLLOW | O_CLOEXEC, 0o600)
        guard fd >= 0 else { throw MacUIError.action("caller_verification_storage_unavailable") }
        defer { Darwin.close(fd); _ = unlinkat(directory, temporary, 0) }
        try data.withUnsafeBytes { bytes in
            var offset = 0
            while offset < data.count {
                let count = Darwin.write(fd, bytes.baseAddress!.advanced(by:offset), data.count - offset)
                if count < 0 && errno == EINTR { continue }
                guard count > 0 else { throw MacUIError.action("caller_verification_storage_unavailable") }
                offset += count
            }
        }
        guard fsync(fd) == 0, renameat(directory, temporary, directory, file) == 0,
              fsync(directory) == 0 else { throw MacUIError.action("caller_verification_storage_unavailable") }
    }
}

/// Connection admission for the ordinary socket. Verification runs on a
/// bounded background pool with a deadline; its verdict is cached only on
/// the connection that produced it.
final class CallerVerificationGate {
    static let discoveryOperations: Set<String> = ["status", "capabilities", "browser.profiles"]
    /// Machine Control's own browser provider registers through its signed
    /// native-messaging host, which BrowserRelay verifies separately.
    static let providerOperations: Set<String> = ["browser.provider"]
    static let limits = ["same_user_not_contained"]
    let store: CallerVerificationStore
    var own: CallerOwnIdentity
    var source = CallerProcessSource()
    var timeout: TimeInterval = 8
    var maximumHops = 12
    let prompts = CallerApprovalPrompts()
    private let slots: DispatchSemaphore
    private let queue = DispatchQueue(label:"machine-control.caller-verification", qos:.userInitiated, attributes:.concurrent)

    init(directory: String, own: CallerOwnIdentity = .current(), concurrency: Int = 4) {
        store = CallerVerificationStore(directory:directory)
        self.own = own
        slots = DispatchSemaphore(value:concurrency)
    }
    var supported: Bool { own.unsupportedReason == nil && store.storageReady }
    func requiresVerification(_ operation: String) -> Bool {
        store.enforced && !Self.discoveryOperations.contains(operation) && !Self.providerOperations.contains(operation)
    }
    /// Agent-facing projection: names and publishers only.
    var status: [String:Any] {
        var value: [String:Any] = ["schema":CallerVerificationStore.schema,
            "mode":store.enforced ? "verified_only" : "off", "supported":supported,
            "approvedHosts":store.approvals.map { ["name":$0.name, "publisher":$0.publisher] },
            "limits":Self.limits, "discoveryOperations":Self.discoveryOperations.sorted()]
        if let reason = own.unsupportedReason ?? (store.storageReady ? nil : "storage_unavailable") { value["unsupportedReason"] = reason }
        if store.storageInvalid { value["storageInvalid"] = true }
        return value
    }
    /// Operator projection, including exact keys for removal.
    var operatorStatus: [String:Any] {
        var value = status
        value["approvedHosts"] = store.approvals.map(\.json)
        return value
    }
    func configure(enabled: Bool) throws {
        if enabled && !supported {
            throw MacUIError.permission(own.unsupportedReason.map { "caller_verification_unsupported:" + $0 }
                ?? "caller_verification_storage_unavailable")
        }
        try store.configure(enabled:enabled)
    }

    /// Calls `completion` exactly once on the main queue.
    func verify(_ descriptor: Int32, completion: @escaping (CallerVerdict) -> Void) {
        precondition(Thread.isMainThread)
        guard let token = CallerProcessSource.auditToken(descriptor) else { completion(.refused("process_changed", nil)); return }
        guard slots.wait(timeout:.now()) == .success else { completion(.refused("verification_busy", nil)); return }
        final class Once { var done = false }
        let once = Once()
        let finish: (CallerVerdict) -> Void = { verdict in
            guard !once.done else { return }; once.done = true; completion(verdict)
        }
        DispatchQueue.main.asyncAfter(deadline:.now() + timeout) { finish(.refused("verification_timeout", nil)) }
        let own = own, approvals = store.approvals, source = source, hops = maximumHops, revision = store.revision
        queue.async { [weak self, slots] in
            let verdict = evaluateCaller(token:token, own:own, approved:approvals, source:source, maximumHops:hops)
            slots.signal()
            DispatchQueue.main.async {
                guard let self else { finish(.refused("resident_stopping", nil)); return }
                finish(self.current(verdict, revision:revision))
            }
        }
    }
    /// An approval removed while verification ran is not honored afterwards.
    private func current(_ verdict: CallerVerdict, revision: String) -> CallerVerdict {
        guard revision != store.revision, case let .verified(host) = verdict else { return verdict }
        return stillApproved(host) ? verdict : .refused("unapproved_host", host)
    }
    func stillApproved(_ host: CallerHost) -> Bool {
        store.approvals.contains { $0.teamID == host.teamID && $0.identifier == host.identifier }
    }

    /// Refusal data. An approvable, unapproved host requests a native prompt
    /// when the operator surface can show one; the request is never replayed.
    func refusalData(reason: String, host: CallerHost?) -> [String:Any] {
        var data: [String:Any] = ["reason":reason, "callerHost":host?.json ?? NSNull(),
                                  "callerVerification":status]
        if reason == "unapproved_host", let host, host.approvable {
            data["approvalPrompt"] = prompts.request(host) { [weak self] host in try self?.store.approve(host) }
        }
        return data
    }
}

/// Debounced first-use prompts, at most one pending per host and a short
/// quiet period after the operator declines.
final class CallerApprovalPrompts {
    var maximumPending = 3
    var declineQuiet: TimeInterval = 60
    var now: () -> TimeInterval = { ProcessInfo.processInfo.systemUptime }
    /// Shows a native prompt and later reports the operator's choice; nil
    /// when no operator surface is currently available.
    var present: ((CallerHost, @escaping (Bool) -> Void) -> Bool)?
    var approved: ((CallerHost) -> Void)?
    var failed: ((String) -> Void)?
    private(set) var pending = Set<String>()
    private var declined: [String:TimeInterval] = [:]

    func request(_ host: CallerHost, approve: @escaping (CallerHost) throws -> Void) -> String {
        guard let key = host.key, host.approvable else { return "unavailable" }
        if pending.contains(key) { return "pending" }
        if let at = declined[key], now() - at < declineQuiet { return "recently_declined" }
        guard pending.count < maximumPending, let present else { return "unavailable" }
        pending.insert(key)
        let shown = present(host) { [weak self] allow in
            guard let self else { return }
            self.pending.remove(key)
            guard allow else { self.declined[key] = self.now(); return }
            self.declined.removeValue(forKey:key)
            do { try approve(host); self.approved?(host) } catch { self.failed?(String(describing:error)) }
        }
        guard shown else { pending.remove(key); return "unavailable" }
        return "presented"
    }
}
