import Darwin
import Foundation

/// Durable local choices, never a live grant, bearer, queue position or session.
/// The native operator alone writes consent; every restore derives fresh
/// authority after checking the same console and the existing OS permissions.
final class OperatorConsentStore {
    let path: String
    var now: () -> Date = Date.init
    var uptime: () -> Double = { ProcessInfo.processInfo.systemUptime }
    private var state: [String:Any] = [:]
    init(directory: String) throws {
        path = (directory as NSString).appendingPathComponent("operator-consent.json")
        var info = stat()
        guard lstat(directory, &info) == 0, info.st_mode & S_IFMT == S_IFDIR,
              info.st_uid == getuid(), info.st_mode & 0o077 == 0 else { throw MacUIError.permission("consent_storage_not_private") }
        if lstat(path, &info) == 0 {
            guard info.st_mode & S_IFMT == S_IFREG, info.st_uid == getuid(), info.st_mode & 0o077 == 0,
                  info.st_nlink == 1, info.st_size > 0, info.st_size <= 8192 else { throw MacUIError.permission("consent_storage_not_private") }
            guard let data = FileManager.default.contents(atPath:path),
                  let value = (try? JSONSerialization.jsonObject(with:data)) as? [String:Any],
                  value["schema"] as? String == "machine-control-operator-consent/v1" else { throw MacUIError.action("consent_storage_invalid") }
            state = value
        } else if errno != ENOENT { throw MacUIError.action("consent_storage_unavailable") }
    }
    private func save() throws {
        state["schema"] = "machine-control-operator-consent/v1"
        let data = try JSONSerialization.data(withJSONObject:state, options:[.sortedKeys])
        let temporary = path + "." + UUID().uuidString
        let fd = open(temporary, O_WRONLY | O_CREAT | O_EXCL | O_NOFOLLOW, 0o600)
        guard fd >= 0 else { throw MacUIError.action("consent_storage_unavailable") }
        var complete = false
        defer { Darwin.close(fd); if !complete { unlink(temporary) } }
        try data.withUnsafeBytes { bytes in
            guard let address = bytes.baseAddress, Darwin.write(fd, address, data.count) == data.count, fsync(fd) == 0 else { throw MacUIError.action("consent_storage_unavailable") }
        }
        guard rename(temporary, path) == 0 else { throw MacUIError.action("consent_storage_unavailable") }
        complete = true
        let directory = open((path as NSString).deletingLastPathComponent, O_RDONLY | O_DIRECTORY)
        defer { if directory >= 0 { Darwin.close(directory) } }
        guard directory >= 0, fsync(directory) == 0 else { throw MacUIError.action("consent_storage_unavailable") }
    }
    func enable(scopes: Set<GrantScope>, duration: Int?, console: [String:Any]) throws {
        guard console["desktopState"] as? String == "unlocked", sameConsoleSession(console, console),
              (console["uid"] as? NSNumber)?.uint32Value == getuid(), !scopes.isEmpty,
              duration == nil || GrantRequest.durationRange.contains(duration!) else { throw MacUIError.action("consent_console_unavailable") }
        state["consent"] = ["console":["uid":console["uid"]!, "uuid":console["uuid"]!, "boot":console["boot"]!],
            "scopes":scopes.sorted().map(\.rawValue), "duration":duration as Any? ?? NSNull(),
            "issuedWall":now().timeIntervalSince1970, "issuedUptime":uptime()]
        try save()
    }
    func disable() throws {
        state.removeValue(forKey:"consent")
        do { try save() }
        catch { unlink(path); throw error } // never retain old consent on a failed Stop
    }
    func pause(seconds: Int?, deferral: Bool = false) throws {
        guard seconds == nil || (1...28800).contains(seconds!) else { throw MacUIError.usage("invalid_pause") }
        state[deferral ? "operatorDeferral" : "manualPause"] = ["duration":seconds as Any? ?? NSNull(), "issuedWall":now().timeIntervalSince1970, "issuedUptime":uptime()]
        try save()
    }
    func resume() throws { state.removeValue(forKey:"manualPause"); state.removeValue(forKey:"operatorDeferral"); try save() }
    private func elapsed(_ value: [String:Any]) -> Double? {
        guard let wall = value["issuedWall"] as? Double, let monotonic = value["issuedUptime"] as? Double,
              wall.isFinite, monotonic.isFinite else { return nil }
        let age = uptime() - monotonic, wallAge = now().timeIntervalSince1970 - wall
        guard age >= 0, wallAge >= 0, abs(age - wallAge) <= 5 else { return nil }
        return max(age, wallAge)
    }
    /// Nil means no manual pause; zero means hold until an explicit Resume.
    var manualPauseRemaining: Int? { pauseRemaining("manualPause") }
    var deferralRemaining: Int? { pauseRemaining("operatorDeferral") }
    private func pauseRemaining(_ key: String) -> Int? {
        guard let pause = state[key] as? [String:Any] else { return nil }
        guard let duration = admissionInteger(pause["duration"]), (1...28800).contains(duration), let age = elapsed(pause) else { return 0 }
        return age >= Double(duration) ? nil : max(1, Int(ceil(Double(duration) - age)))
    }
    func consent(console: [String:Any]) -> (Set<GrantScope>, Int?)? {
        guard let consent = state["consent"] as? [String:Any], let binding = consent["console"] as? [String:Any],
              sameConsoleSession(binding, console), (console["uid"] as? NSNumber)?.uint32Value == getuid(),
              let names = consent["scopes"] as? [String], !names.isEmpty, Set(names).count == names.count,
              names.allSatisfy({ GrantScope(rawValue:$0) != nil }) else { return nil }
        let scopes = Set(names.compactMap(GrantScope.init(rawValue:)))
        if consent["duration"] is NSNull { return (scopes, nil) }
        guard let age = elapsed(consent), let duration = admissionInteger(consent["duration"]), GrantRequest.durationRange.contains(duration), age < Double(duration) else { return nil }
        return (scopes, max(1, Int(floor(Double(duration) - age))))
    }
}

/// Shared startup for both owned Mac application shells.
func attachOperatorConsent(_ broker: GrantBroker, socketPath: String) {
    do {
        let store = try OperatorConsentStore(directory:(socketPath as NSString).deletingLastPathComponent)
        broker.consentStore = store
        if let remaining = store.manualPauseRemaining { try broker.admission.pause("desktop", reason:"manual", seconds:remaining == 0 ? nil : Double(remaining)) }
        if let remaining = store.deferralRemaining { try broker.admission.pause("desktop", reason:"operator_deferral", seconds:remaining == 0 ? nil : Double(remaining)) }
    } catch { broker.consentStorageError = String(describing:error) }
}
