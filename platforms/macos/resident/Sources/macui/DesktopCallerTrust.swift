import Darwin
import Foundation
import Security

/// A public session label selects attribution only. The signed native broker
/// authenticates the upstream launch over its private launch channel.
struct DesktopDelegation {
    let session: String
    let generation: String
    static func parse(_ value: Any?) throws -> DesktopDelegation {
        guard let value = value as? [String:Any],
              Set(value.keys) == ["schema", "sessionId", "sessionGeneration"],
              value["schema"] as? String == "machine-control-desktop-delegation/v1",
              let session = value["sessionId"] as? String, !session.isEmpty, session.utf8.count <= 128,
              session.unicodeScalars.allSatisfy({ $0.value >= 33 && $0.value <= 126 }),
              let generation = value["sessionGeneration"] as? String,
              UUID(uuidString:generation) != nil else { throw MacUIError.usage("invalid_desktop_delegation") }
        return DesktopDelegation(session:session, generation:generation)
    }
}

struct VerifiedDesktopIntegration {
    let requirement: String
    let publisher: String

    /// Enrollment is operator-only and selects the intended app, never an
    /// arbitrary executable or publisher-wide requirement supplied by a caller.
    static func yepAnywhere(at app: URL = URL(fileURLWithPath:"/Applications/YepAnywhere.app")) throws -> VerifiedDesktopIntegration {
        var code: SecStaticCode?
        guard SecStaticCodeCreateWithPath(app as CFURL, [], &code) == errSecSuccess, let code,
              SecStaticCodeCheckValidity(code, SecCSFlags(rawValue:kSecCSStrictValidate | kSecCSCheckNestedCode | kSecCSCheckAllArchitectures), nil) == errSecSuccess else {
            throw MacUIError.permission("desktop_integration_signature_invalid")
        }
        var raw: CFDictionary?
        guard SecCodeCopySigningInformation(code, SecCSFlags(rawValue:kSecCSSigningInformation), &raw) == errSecSuccess,
              let info = raw as? [String:Any],
              info[kSecCodeInfoIdentifier as String] as? String == "com.yepanywhere.desktop",
              let publisher = info[kSecCodeInfoTeamIdentifier as String] as? String,
              publisher.count == 10, publisher.allSatisfy({ $0.isASCII && ($0.isUppercase || $0.isNumber) }),
              let plist = info[kSecCodeInfoPList as String] as? [String:Any],
              admissionInteger(plist["MCDesktopDelegationProtocol"]) == 1 else {
            throw MacUIError.permission("desktop_integration_protocol_unavailable")
        }
        var requirement: SecRequirement?
        var string: CFString?
        guard SecCodeCopyDesignatedRequirement(code, [], &requirement) == errSecSuccess, let requirement,
              SecRequirementCopyString(requirement, [], &string) == errSecSuccess, let string else {
            throw MacUIError.permission("desktop_integration_identity_unavailable")
        }
        return VerifiedDesktopIntegration(requirement:string as String, publisher:publisher)
    }

    static func peer(_ descriptor: Int32, matches requirement: String, resources: Bool = true) -> Bool {
        var token = audit_token_t()
        var size = socklen_t(MemoryLayout<audit_token_t>.size)
        guard getsockopt(descriptor, SOL_LOCAL, LOCAL_PEERTOKEN, &token, &size) == 0,
              size == MemoryLayout<audit_token_t>.size else { return false }
        let data = withUnsafeBytes(of:&token) { Data($0) }
        var guest: SecCode?, expected: SecRequirement?
        guard SecRequirementCreateWithString(requirement as CFString, [], &expected) == errSecSuccess, let expected,
              SecCodeCopyGuestWithAttributes(nil, [kSecGuestAttributeAudit:data] as CFDictionary, [], &guest) == errSecSuccess,
              let guest, SecCodeCheckValidity(guest, SecCSFlags(rawValue:kSecCSStrictValidate), expected) == errSecSuccess else { return false }
        if !resources { return true }
        // Dynamic identity alone does not authenticate scripts/resources loaded
        // by an interpreter. Check the native broker's complete sealed bundle.
        var staticGuest: SecStaticCode?
        var raw: CFDictionary?
        guard SecCodeCopyStaticCode(guest, [], &staticGuest) == errSecSuccess, let staticGuest,
              SecCodeCopySigningInformation(staticGuest, SecCSFlags(rawValue:kSecCSSigningInformation), &raw) == errSecSuccess,
              let info = raw as? [String:Any], let executable = info[kSecCodeInfoMainExecutable as String] as? URL,
              executable.lastPathComponent == "yep-anywhere-desktop" else { return false }
        let app = executable.deletingLastPathComponent().deletingLastPathComponent().deletingLastPathComponent()
        var bundle: SecStaticCode?
        guard app.pathExtension == "app", SecStaticCodeCreateWithPath(app as CFURL, [], &bundle) == errSecSuccess,
              let bundle else { return false }
        var bundleInfo: CFDictionary?
        guard SecCodeCopySigningInformation(bundle, SecCSFlags(rawValue:kSecCSSigningInformation), &bundleInfo) == errSecSuccess,
              let values = bundleInfo as? [String:Any], let plist = values[kSecCodeInfoPList as String] as? [String:Any],
              admissionInteger(plist["MCDesktopDelegationProtocol"]) == 1 else { return false }
        return SecStaticCodeCheckValidity(bundle, SecCSFlags(rawValue:kSecCSStrictValidate | kSecCSCheckNestedCode), expected) == errSecSuccess
    }
}

/// Standing trust is separate from connection-owned finite admission. This
/// persistence is a same-user workstation policy, not same-user containment.
final class DesktopCallerTrust {
    private let directory: Int32
    private let file = "desktop-caller-trust.json"
    private var storageReady = false
    private var requirement: String?
    private var scopes = Set<GrantScope>()
    private(set) var revision = UUID().uuidString
    private(set) var suspended = true
    private(set) var storageInvalid = false
    var peerValid: (Int32, String) -> Bool = { VerifiedDesktopIntegration.peer($0, matches:$1) }
    var peerStillValid: (Int32, String) -> Bool = { VerifiedDesktopIntegration.peer($0, matches:$1, resources:false) }

    init(directory path: String) {
        directory = open(path, O_RDONLY | O_DIRECTORY | O_NOFOLLOW | O_CLOEXEC)
        var info = stat()
        guard directory >= 0, fstat(directory, &info) == 0, info.st_uid == getuid(),
              info.st_mode & 0o077 == 0 else { storageInvalid = true; return }
        storageReady = true
        let fd = openat(directory, file, O_RDONLY | O_NOFOLLOW | O_CLOEXEC)
        if fd < 0 { storageInvalid = errno != ENOENT; return }
        defer { Darwin.close(fd) }
        guard fstat(fd, &info) == 0, info.st_uid == getuid(), info.st_mode & S_IFMT == S_IFREG,
              info.st_mode & 0o077 == 0, info.st_nlink == 1, (1...8192).contains(info.st_size) else {
            storageInvalid = true; return
        }
        var bytes = [UInt8](repeating:0, count:8193)
        let size = read(fd, &bytes, bytes.count)
        guard size > 0, size == info.st_size, size <= 8192 else { storageInvalid = true; return }
        let raw = try? JSONSerialization.jsonObject(with:Data(bytes.prefix(size)))
        guard let raw = raw as? [String:Any],
              Set(raw.keys) == ["schema", "requirement", "scopes", "suspended"],
              raw["schema"] as? String == "machine-control-desktop-trust/v1",
              let requirement = raw["requirement"] as? String, !requirement.isEmpty, requirement.utf8.count <= 4096,
              let names = raw["scopes"] as? [String], !names.isEmpty, Set(names).count == names.count,
              names.allSatisfy({ [.observe, .control].contains(GrantScope(rawValue:$0)) }),
              let suspended = raw["suspended"] as? NSNumber,
              CFGetTypeID(suspended) == CFBooleanGetTypeID() else {
            storageInvalid = true; return
        }
        self.requirement = requirement; scopes = Set(names.compactMap(GrantScope.init(rawValue:)))
        self.suspended = suspended.boolValue
        // Deliberately fresh revision on restart; no prior live channel survives.
    }
    deinit { if directory >= 0 { Darwin.close(directory) } }
    var status: [String:Any] {
        ["supported":true, "enabled":requirement != nil && !suspended && !storageInvalid,
         "suspended":suspended, "storageInvalid":storageInvalid,
         "scopes":scopes.sorted().map(\.rawValue), "profile":"ordinary_local_desktop",
         "protectedControl":false, "outerRecovery":false, "preparedConsoleComposition":true]
    }
    func enroll(_ integration: VerifiedDesktopIntegration, scopes: Set<GrantScope>) throws {
        guard !scopes.isEmpty, scopes.isSubset(of:[.observe,.control]), integration.requirement.utf8.count <= 4096,
              !integration.requirement.isEmpty else { throw MacUIError.usage("invalid_desktop_trust") }
        self.requirement = integration.requirement; self.scopes = scopes
        suspended = false; storageInvalid = false; revision = UUID().uuidString
        do { try persist() } catch { discardUnsafeTrust(); throw error }
    }
    func stop() {
        suspended = true; revision = UUID().uuidString
        do { try persist() } catch { discardUnsafeTrust() }
    }
    func remove() {
        requirement = nil; scopes.removeAll(); suspended = true
        revision = UUID().uuidString; storageInvalid = false
        if !storageReady || (unlinkat(directory, file, 0) != 0 && errno != ENOENT) || fsync(directory) != 0 {
            storageInvalid = true
        }
    }
    private func discardUnsafeTrust() {
        suspended = true; storageInvalid = true
        if storageReady { _ = unlinkat(directory, file, 0); _ = fsync(directory) }
    }
    private func persist() throws {
        guard let requirement else { return }
        var info = stat()
        guard storageReady, fstat(directory, &info) == 0, info.st_uid == getuid(),
              info.st_mode & 0o077 == 0 else { throw MacUIError.action("desktop_trust_storage_unavailable") }
        let data = try JSONSerialization.data(withJSONObject:["schema":"machine-control-desktop-trust/v1",
            "requirement":requirement,"scopes":scopes.sorted().map(\.rawValue),"suspended":suspended], options:[.sortedKeys])
        guard data.count <= 8192 else { throw MacUIError.action("desktop_trust_storage_unavailable") }
        let temporary = file + "." + UUID().uuidString
        let fd = openat(directory, temporary, O_WRONLY | O_CREAT | O_EXCL | O_NOFOLLOW | O_CLOEXEC, 0o600)
        guard fd >= 0 else { throw MacUIError.action("desktop_trust_storage_unavailable") }
        defer { Darwin.close(fd); _ = unlinkat(directory, temporary, 0) }
        try data.withUnsafeBytes { bytes in
            var offset = 0
            while offset < data.count {
                let count = Darwin.write(fd,bytes.baseAddress!.advanced(by:offset),data.count-offset)
                if count < 0 && errno == EINTR { continue }
                guard count > 0 else { throw MacUIError.action("desktop_trust_storage_unavailable") }
                offset += count
            }
        }
        guard fsync(fd) == 0, renameat(directory, temporary, directory, file) == 0,
              fsync(directory) == 0 else { throw MacUIError.action("desktop_trust_storage_unavailable") }
    }
    /// Capture immutable policy on the resident queue, then recheck on return.
    func verification(scopes requested: Set<GrantScope>) throws -> (String, String, (Int32, String) -> Bool) {
        if let refusal = refusal(descriptor:-1, revision:revision, scopes:requested, checkPeer:false) {
            throw MacUIError.permission(refusal)
        }
        guard let requirement else { throw MacUIError.permission("desktop_trust_not_enabled") }
        return (revision, requirement, peerValid)
    }
    func admittedRevision(descriptor: Int32, scopes requested: Set<GrantScope>) throws -> String {
        if let refusal = refusal(descriptor:descriptor, revision:revision, scopes:requested, checkPeer:false) {
            throw MacUIError.permission(refusal)
        }
        guard let requirement, peerValid(descriptor, requirement) else { throw MacUIError.permission("desktop_caller_identity_denied") }
        return revision
    }
    func refusal(descriptor: Int32, revision expected: String, scopes requested: Set<GrantScope>, checkPeer: Bool = true) -> String? {
        guard !storageInvalid else { return "desktop_trust_storage_invalid" }
        guard requirement != nil, !suspended else { return "desktop_trust_not_enabled" }
        guard revision == expected else { return "desktop_trust_changed" }
        guard !requested.isEmpty, requested.isSubset(of:scopes) else { return "desktop_trust_scope_denied" }
        if checkPeer, let requirement, !peerStillValid(descriptor, requirement) { return "desktop_caller_identity_denied" }
        return nil
    }
}
