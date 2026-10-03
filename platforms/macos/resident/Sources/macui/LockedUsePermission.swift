import AppKit
import ApplicationServices
import CoreGraphics
import Foundation
import ServiceManagement

protocol LockedUsePermissionManaging: AnyObject {
    var ready: Bool { get }
    var approvalState: String { get }
    var setupState: String { get }
    var setupError: String? { get }
    func ready(helper: [String:Any], approval: String) -> Bool
    func request() throws
    func remove() throws
    func tick()
}

extension LockedUsePermissionManaging {
    func ready(helper: [String:Any], approval: String) -> Bool { ready }
}

/// Only the native operator's preparation path owns this lifecycle. Waiting for
/// unregister completion is required before re-registration. macOS can still
/// briefly return EPERM afterward; retry that transition only, with a bound.
final class HelperRegistration {
    typealias Schedule = (TimeInterval, @escaping () -> Void) -> Void
    private let status: () -> SMAppService.Status
    private let register: () throws -> Void
    private let unregister: (@escaping (Error?) -> Void) -> Void
    private let schedule: Schedule
    private var generation = UUID()

    init(status: @escaping () -> SMAppService.Status,
         register: @escaping () throws -> Void,
         unregister: @escaping (@escaping (Error?) -> Void) -> Void,
         schedule: @escaping Schedule = { delay, work in
             DispatchQueue.main.asyncAfter(deadline:.now() + delay, execute:work)
         }) {
        self.status = status; self.register = register
        self.unregister = unregister; self.schedule = schedule
    }
    func cancel() { generation = UUID() }
    func start(restart: Bool, completion: @escaping (Result<SMAppService.Status, Error>) -> Void) {
        cancel(); let token = generation
        if restart {
            unregister { [weak self] error in
                guard let self else { return }
                self.schedule(0) {
                    guard self.generation == token else { return }
                    if let error { completion(.failure(error)); return }
                    self.register(token:token, retries:10, completion:completion)
                }
            }
        } else { register(token:token, retries:0, completion:completion) }
    }
    private func register(token: UUID, retries: Int,
                          completion: @escaping (Result<SMAppService.Status, Error>) -> Void) {
        guard generation == token else { return }
        do {
            if status() != .enabled { try register() }
            completion(.success(status()))
        } catch {
            if status() == .requiresApproval { completion(.success(.requiresApproval)); return }
            let issue = error as NSError
            // The named domain constant is SDK-gated to macOS 15; the same
            // NSError domain is emitted by ServiceManagement on earlier OSes.
            if retries > 0, issue.domain == "SMAppServiceErrorDomain", issue.code == Int(EPERM) {
                schedule(0.5) { [weak self] in
                    self?.register(token:token, retries:retries - 1, completion:completion)
                }
            } else { completion(.failure(error)) }
        }
    }
}

enum HelperUpdatePolicy {
    static func eligible(approved: Bool, capturePrepared: Bool,
                         installation: [String:Any]?, helper: [String:Any], console: [String:Any]) -> Bool {
        guard approved, capturePrepared, let installation,
              installation["version"] as? Int == 2,
              installation["management"] as? String == "service_managed",
              installation["profile"] as? String == "locked_use", installation["enabled"] as? Bool == true,
              helper["installation"] as? String == "healthy", helper["profile"] as? String == "locked_use",
              helper["policy"] as? String == "enabled", helper["callerEligibility"] as? String == "denied",
              helper["coveredSession"] as? Bool == false, helper["lockedUsePaused"] as? Bool == false,
              console["desktopState"] as? String == "unlocked",
              (console["uid"] as? NSNumber)?.uint32Value == getuid(),
              sameConsoleSession(console, console) else { return false }
        return true
    }
}

/// Permission preparation is local operator work. The preference never calls
/// this request path, and the public desktop socket never dispatches it.
final class MacLockedUsePermission: LockedUsePermissionManaging {
    private let service: ResidentService
    private let preferences: UserDefaults
    private let daemon = SMAppService.daemon(plistName:"org.machine-control.unlock.plist")
    private lazy var registration = HelperRegistration(status:{ [daemon] in daemon.status },
        register:{ [daemon] in try daemon.register() },
        unregister:{ [daemon] done in daemon.unregister(completionHandler:done) })
    private var preparing = false
    private var maintaining = false
    private var updateAttempted = false
    private var attempt = UUID()
    private(set) var setupState = "idle"
    private(set) var setupError: String?
    private var lastPoll: TimeInterval = 0

    init(service: ResidentService, preferences: UserDefaults) {
        self.service = service; self.preferences = preferences
    }
    var approvalState: String {
        switch daemon.status {
        case .enabled: return "granted"
        case .requiresApproval: return "requires_approval"
        case .notRegistered: return "not_registered"
        case .notFound: return "unavailable"
        @unknown default: return "unavailable"
        }
    }
    var ready: Bool {
        ready(helper:service.unlockStatus(), approval:approvalState)
    }
    func ready(helper: [String:Any], approval: String) -> Bool {
        guard #available(macOS 14.0, *), setupState == "idle", approval == "granted",
              preferences.bool(forKey:"lockedUseCapturePrepared"),
              CGPreflightScreenCaptureAccess(), AXIsProcessTrusted(), CGPreflightPostEventAccess() else { return false }
        return helper["profile"] as? String == "locked_use" && helper["policy"] as? String == "enabled" &&
            helper["installation"] as? String == "healthy" && helper["callerEligibility"] as? String == "allowed"
    }
    func request() throws {
        if preparing {
            if setupState == "approval" { SMAppService.openSystemSettingsLoginItems() }
            return
        }
        try beginPreparation(maintenance:false)
    }
    private func beginPreparation(maintenance: Bool) throws {
        guard #available(macOS 14.0, *), ConsoleRelock.available else {
            throw MacUIError.action("Locked use requires macOS 14 or later")
        }
        maintaining = maintenance; updateAttempted = true
        setupError = nil; preparing = true; attempt = UUID()
        // Keep the existing choice. ready is false throughout preparation, so
        // preserving an opt-in cannot unlock while the helper is being repaired.
        // Initial setup leaves the default-off preference untouched.
        let restart = daemon.status == .enabled &&
            service.unlockStatus()["callerEligibility"] as? String == "denied"
        setupState = "registering"
        let generation = attempt
        registration.start(restart:restart) { [weak self] result in
            guard let self, self.attempt == generation else { return }
            switch result {
            case .success(.enabled): self.startPreparation()
            case .success(.requiresApproval):
                self.setupState = "approval"
                if !self.maintaining { SMAppService.openSystemSettingsLoginItems() }
            case .success:
                self.finish("The Machine Control helper did not register. Try again in Permissions.")
            case .failure(let error):
                let issue = error as NSError
                self.finish("Unable to register the Machine Control helper: \(issue.localizedDescription) (\(issue.domain) \(issue.code))")
            }
        }
    }
    func tick() {
        let now = ProcessInfo.processInfo.systemUptime
        guard now - lastPoll >= 1 else { return }; lastPoll = now
        if preparing {
            if setupState == "approval", daemon.status == .enabled { startPreparation() }
            return
        }
        guard #available(macOS 14.0, *), !updateAttempted, setupState == "idle",
              CGPreflightScreenCaptureAccess(), AXIsProcessTrusted(), CGPreflightPostEventAccess(),
              HelperUpdatePolicy.eligible(approved:daemon.status == .enabled,
                capturePrepared:preferences.bool(forKey:"lockedUseCapturePrepared"),
                installation:Self.trustedInstallation(), helper:service.unlockStatus(),
                console:nativeSessionObservation()) else { return }
        // Maintenance of an already installed, OS-approved helper, once per
        // process. No agent request dispatches initial setup or grants consent.
        do { try beginPreparation(maintenance:true) }
        catch { finish("Machine Control helper update failed: \(error)") }
    }
    private static func trustedInstallation() -> [String:Any]? {
        let path = "/Library/Preferences/org.machine-control.unlock.plist"
        var info = stat()
        guard lstat(path, &info) == 0, info.st_uid == 0,
              info.st_mode & S_IFMT == S_IFREG, info.st_mode & 0o022 == 0 else { return nil }
        return NSDictionary(contentsOfFile:path) as? [String:Any]
    }
    func remove() throws {
        guard setupState == "idle" || setupState == "approval" else {
            throw MacUIError.action("Finish helper setup before removing it")
        }
        preparing = false; attempt = UUID(); setupError = nil
        updateAttempted = true
        registration.cancel()
        preferences.set(true, forKey:"lockedUseLocallyDisabled")
        if daemon.status != .enabled {
            let installation = service.unlockStatus()
            guard installation["profile"] as? String != "locked_use" || installation["installation"] as? String == "missing" else {
                throw MacUIError.action("Approve the helper in macOS Login Items & Extensions before removing its installed components")
            }
            try daemon.unregister(); setupState = "idle"; return
        }
        setupState = "removing"
        let generation = attempt
        DispatchQueue.global(qos:.userInitiated).async { [weak self] in
            guard let self else { return }
            let issue: String? = {
                do { try self.service.removeUnlockPermission(); return nil }
                catch { return "Unable to remove the helper: \(error)" }
            }()
            DispatchQueue.main.async {
                guard self.attempt == generation else { return }
                if let issue { self.finish(issue); return }
                do {
                    try self.daemon.unregister()
                    self.preferences.removeObject(forKey:"lockedUseCapturePrepared")
                    self.finish(nil)
                } catch { self.finish("Unable to unregister the helper: \(error.localizedDescription)") }
            }
        }
    }
    private func startPreparation() {
        guard preparing, setupState != "installing", setupState != "capture" else { return }
        setupState = "installing"
        let generation = attempt
        DispatchQueue.global(qos:.userInitiated).async { [weak self] in
            guard let self else { return }
            let issue: String? = {
                do {
                    // Service approval can precede daemon bootstrap. Retry only
                    // unavailable transport, before any setup request is sent.
                    for index in 0..<20 {
                        do { try self.service.prepareUnlockPermission(); return nil }
                        catch MacUIError.permission("unlock_not_installed") where index < 19 { Thread.sleep(forTimeInterval:0.25) }
                        catch MacUIError.action("unlock_helper_unreachable") where index < 19 { Thread.sleep(forTimeInterval:0.25) }
                    }
                    return "The Machine Control helper did not start. Try again in Permissions."
                }
                catch { return "Machine Control helper setup failed. Open Permissions to try again. \(error)" }
            }()
            DispatchQueue.main.async {
                guard self.attempt == generation else { return }
                if let issue { self.finish(issue); return }
                if self.maintaining { self.finish(nil); return }
                self.setupState = "capture"
                self.prepareCapture(generation)
            }
        }
    }
    private func prepareCapture(_ generation: UUID) {
        let url = FileManager.default.temporaryDirectory.appendingPathComponent("mc-capture-check-\(UUID().uuidString).png")
        DispatchQueue.global(qos:.userInitiated).async { [weak self] in
            guard let self else { return }
            defer { try? FileManager.default.removeItem(at:url) }
            let issue: String? = {
                do {
                    if #available(macOS 14.0, *) { try captureCoveredDisplay(to:url, displayID:CGMainDisplayID()); return nil }
                    return "Requires macOS 14 or later"
                } catch { return "Approve screen capture in macOS, then finish setup in Permissions." }
            }()
            DispatchQueue.main.async {
                guard self.attempt == generation else { return }
                self.preferences.set(issue == nil, forKey:"lockedUseCapturePrepared")
                self.finish(issue)
            }
        }
    }
    private func finish(_ issue: String?) {
        preparing = false; maintaining = false; setupState = "idle"; setupError = issue
    }
}
