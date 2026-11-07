import Foundation

/// How dispatch treats an operation before any provider runs.
enum OperationClass: Equatable {
    case discovery
    case grantManagement
    case lifecycle
    case providerRegistration
    case scoped(GrantScope)
    case protected
}

func operationClass(_ operation: String) -> OperationClass {
    switch operation {
    case "capabilities", "status":
        return .discovery
    case "grant.request", "grant.status", "grant.revoke":
        return .grantManagement
    case "browser.provider":
        return .providerRegistration
    case "browser.profiles": return .discovery
    case "browser.endpoint": return .scoped(.devtools)
    case "browser.cdp", "browser.eval":
        // Raw DevTools protocol access is broader than operating tabs: it
        // can run scripts and read data on any signed-in site.
        return .scoped(.devtools)
    case "server.stop":
        return .lifecycle
    case "session.control.end":
        // A stop-only operation creates no authority.
        return .lifecycle
    case "session.control":
        return .scoped(.control)
    case "applications", "windows", "snapshot", "capture":
        return .scoped(.observe)
    case "session.unlock", "authorization.begin", "authorization.cancel",
         "authorization.submit":
        return .protected
    default:
        if operation.hasPrefix("browser.") { return .scoped(.browser) }
        // Actions, input, application lifecycle, and anything unknown need
        // the strongest ordinary scope.
        return .scoped(.control)
    }
}

/// Who created a grant. Only the person may end `person` access; a socket
/// caller's revoke leaves it in place.
enum GrantOrigin: String {
    case person, request
}

struct Grant {
    let id: String
    let scopes: Set<GrantScope>
    let issuedAt: Date
    /// Nil only for access manually armed by the local person until Stop.
    let expiresAt: Date?
    let reason: String
    let requester: String
    let approver: String
    var origin: GrantOrigin = .request

    func json(now: Date) -> [String: Any] {
        [
            "grantId": id,
            "scopes": scopes.sorted().map(\.rawValue),
            "issuedAt": ISO8601DateFormatter().string(from: issuedAt),
            "lifetime": expiresAt == nil ? "until_stopped" : "timed",
            "expiresAt": expiresAt.map { ISO8601DateFormatter().string(from: $0) as Any } ?? NSNull(),
            "remainingSeconds": expiresAt.map { max(0, Int($0.timeIntervalSince(now))) as Any } ?? NSNull(),
            "reason": reason,
            "requester": requester,
            "approver": approver,
            "origin": origin.rawValue,
            "binding": "target_wide",
        ]
    }
}

struct GrantRequest {
    static let defaultDuration = 900
    static let durationRange = 60...28_800
    static let defaultTimeout = 120
    static let timeoutRange = 5...600

    let id: String
    let scopes: Set<GrantScope>
    let durationSeconds: Int
    let timeoutSeconds: Int
    let reason: String
    let claimID: String?
    let caller: CallerIdentity

    /// Returns the parsed request or a refusal code and message.
    static func parse(_ request: [String: Any], caller: CallerIdentity)
        -> Result<GrantRequest, GrantRefusal> {
        guard let names = request["scopes"] as? [String], !names.isEmpty else {
            return .failure(GrantRefusal("invalid_request", "scopes must list observe, control, browser, or devtools"))
        }
        var scopes = Set<GrantScope>()
        for name in names {
            guard let scope = GrantScope(rawValue: name) else {
                return .failure(GrantRefusal("invalid_request", "Unknown grant scope: \(name)"))
            }
            scopes.insert(scope)
        }
        guard let reason = (request["reason"] as? String)?
                .trimmingCharacters(in: .whitespacesAndNewlines),
              !reason.isEmpty else {
            return .failure(GrantRefusal("invalid_request", "reason is required"))
        }
        func bounded(_ key: String, _ fallback: Int, _ range: ClosedRange<Int>) -> Int {
            let value = (request[key] as? NSNumber)?.intValue ?? fallback
            return min(max(value, range.lowerBound), range.upperBound)
        }
        let claim = (request["claimId"] as? String).map { String($0.prefix(80)) }
        return .success(GrantRequest(
            id: (request["requestId"] as? String).map { String($0.prefix(80)) }
                ?? UUID().uuidString.lowercased(),
            scopes: scopes,
            durationSeconds: bounded("durationSeconds", defaultDuration, durationRange),
            timeoutSeconds: bounded("timeoutSeconds", defaultTimeout, timeoutRange),
            reason: String(reason.prefix(240)),
            claimID: claim, caller: caller))
    }
}

struct GrantRefusal: Error, Equatable {
    let code: String
    let message: String
    var requiredScope: GrantScope?

    init(_ code: String, _ message: String, requiredScope: GrantScope? = nil) {
        self.code = code
        self.message = message
        self.requiredScope = requiredScope
    }
}

enum GrantDecision: Equatable {
    case approved(scopes: Set<GrantScope>, durationSeconds: Int)
    case denied
    case timedOut
}

/// A person-facing approval surface. The resident owns enforcement; an
/// approver only turns a request into a decision.
protocol GrantApprover: AnyObject {
    var kind: String { get }
    func present(_ request: GrantRequest, completion: @escaping (GrantDecision) -> Void)
    func dismiss(requestID: String)
}

struct AuditEntry {
    let at: Date
    let operation: String
    let accepted: Bool
    let errorCode: String?
    let caller: String
    let claimID: String?
    var detail: String? = nil

    var json: [String: Any] {
        [
            "at": ISO8601DateFormatter().string(from: at),
            "operation": operation,
            "accepted": accepted,
            "errorCode": errorCode.map { $0 as Any } ?? NSNull(),
            "caller": caller,
            "claimId": claimID.map { $0 as Any } ?? NSNull(),
        ]
    }
}

/// Native policy/safety ceilings and shared-policy projections. Surface
/// consent, task approval, queueing and expiry belong exclusively to Node.
final class GrantBroker {
    enum ConsentDisposition { case retain, invalidate }
    let policy: DeploymentPolicy
    var journal: DesktopJournal?
    var now: () -> Date = Date.init
    var authorityChanged: (() -> Void)?
    var availabilityChanged: (() -> Void)?
    var bindAuthorityBeforeObservers: (() -> Void)?
    private var observers: [() -> Void] = []
    private var observedAvailability = 0
    private(set) var desktopConsentID = UUID().uuidString
    private(set) var browserConsentID = UUID().uuidString
    private(set) var lastEnded: (reason: String, at: Date)?
    /// Every revocation, so the supervisor never restores access stopped
    /// after its last observation.
    private(set) var stops = 0
    private(set) var audit: [AuditEntry] = []
    var desktopRouteReady = false
    var browserRouteReady = false
    var browserOnlyWhileLocked = false
    var operatorReady: () -> Bool = { false }
    // Legacy authority records are deliberately not loaded or restored.
    var consentStorageError: String? { nil }
    var restorationBlockedScopes = Set<GrantScope>()
    var pending: GrantRequest? { nil }
    static let browserScopes: Set<GrantScope> = [.browser, .devtools]
    static let personStopReasons: Set<String> = ["stopped_from_menu", "stopped_by_hotkey", "stopped_by_person"]
    lazy var admission: AccessAdmission = {
        let value = AccessAdmission()
        value.register("desktop", ready: false); value.register("browser", ready: false)
        value.changed = { [weak self] in self?.refreshAvailability() }
        return value
    }()
    init(policy: DeploymentPolicy) { self.policy = policy }
    func observe(_ observer: @escaping () -> Void) { observers.append(observer) }
    private func notify() {
        bindAuthorityBeforeObservers?()
        for observer in observers { observer() }
    }
    func refreshAvailability() {
        admission.refresh()
        guard observedAvailability != admission.availabilityRevision else { return }
        observedAvailability = admission.availabilityRevision
        availabilityChanged?(); notify()
    }
    var browserAllowed: Bool {
        browserRouteReady && admission.enabled("browser") && admission.blocks("browser").isEmpty
    }
    var devtoolsAllowed: Bool { browserAllowed }
    var activeGrant: Grant? {
        // A read-only native helper binding. This cannot authorize an action;
        // every ordinary action also needs its live shared owner/fence.
        guard admission.enabled("desktop") else { return nil }
        let state = admission.surface("desktop")
        let remaining = (state["consentRemainingSeconds"] as? NSNumber)?.doubleValue
        return Grant(id: desktopConsentID, scopes: [.observe, .control], issuedAt: now(),
            expiresAt: remaining.map { now().addingTimeInterval($0) },
            reason: "Desktop surface consent", requester: "local operator",
            approver: "surface_modes", origin: .person)
    }
    var grant: Grant? { activeGrant }
    func validateSurface(_ surface: String, mode: String, seconds: Int?, profiles: [String]) throws {
        guard ["desktop", "browser"].contains(surface), ["off", "ask", "automatic"].contains(mode),
              seconds == nil || (60...28800).contains(seconds!) else {
            throw MacUIError.usage("invalid_surface_configuration")
        }
        guard mode == "off" || operatorReady() else { throw MacUIError.permission("unlocked_operator_required") }
        guard journal?.errorCode == nil || mode == "off" else { throw MacUIError.action("audit_storage_unavailable") }
    }
    func configureSurface(_ surface: String, mode: String, seconds: Int?, profiles: [String] = []) throws {
        try validateSurface(surface, mode:mode, seconds:seconds, profiles:profiles)
        try admission.configure(surface, mode: mode, seconds: seconds, profiles: profiles)
        if surface == "desktop" { desktopConsentID = UUID().uuidString; authorityChanged?() }
        else { browserConsentID = UUID().uuidString }
        lastEnded = nil; journal?.event(mode == "off" ? "access.disabled" : "access.enabled")
        notify()
    }
    func pause(reason: String = "manual", seconds: Int? = nil, surface: String = "all") throws {
        try admission.pause(surface, reason: reason, seconds: seconds.map(Double.init))
        journal?.event("access.paused")
    }
    func resume(surface: String = "all") throws {
        admission.resume(surface, reason: "manual"); admission.resume(surface, reason: "operator_deferral")
        admission.resume(surface, reason: "local_use_episode"); admission.resume(surface, reason: "physical_takeover")
        journal?.event("access.resumed")
    }
    func authorize(_ operation: String, controlled: Bool = false) -> GrantRefusal? {
        switch operationClass(operation) {
        case .discovery, .grantManagement, .lifecycle, .providerRegistration: return nil
        case .protected:
            // The explicitly installed managed-appliance administration plane
            // is separate from ordinary workstation surface consent.
            guard protectedAdministration else {
                return GrantRefusal("operation_not_permitted_by_policy", "Protected administration requires its native managed policy")
            }
            return nil
        case let .scoped(scope):
            let surface = Self.browserScopes.contains(scope) ? "browser" : "desktop"
            guard admission.enabled(surface) else { return GrantRefusal("surface_disabled", "This surface is Off", requiredScope: scope) }
            guard controlled else { return GrantRefusal("control_session_required", "Open one live surface task", requiredScope: scope) }
            guard surface == "browser" ? browserRouteReady : desktopRouteReady else {
                return GrantRefusal(surface == "desktop" && browserOnlyWhileLocked ? "desktop_locked_browser_only" : "desktop_unavailable",
                    "The native route is temporarily unavailable", requiredScope: scope)
            }
            guard journal?.errorCode == nil else { return GrantRefusal("audit_storage_unavailable", "Audit storage unavailable") }
            return nil
        }
    }
    /// The managed-appliance plane that admits `.protected` operations.
    var protectedAdministration: Bool { policy.protectedOperations && policy.grantMode == .standing }
    func admissionAuthority(scopes: Set<GrantScope>) -> String? {
        journal?.errorCode == nil ? nil : "audit_storage_unavailable"
    }
    func revoke(reason: String, consent: ConsentDisposition = .retain) {
        stops += 1
        fence(); admission.stop(reason); lastEnded = (reason, now())
        journal?.event("access." + DesktopJournal.token(reason)); notify()
    }
    func fence() {
        desktopConsentID = UUID().uuidString; browserConsentID = UUID().uuidString
        authorityChanged?()
    }
    static func clearsConsent(reason: String, ending: GrantOrigin?, consent: ConsentDisposition = .retain) -> Bool {
        personStopReasons.contains(reason) || consent == .invalidate
    }
    func record(operation: String, accepted: Bool, errorCode: String?, caller: CallerIdentity,
                claimID: String?, detail: String? = nil) {
        audit.append(AuditEntry(at: now(), operation: operation, accepted: accepted, errorCode: errorCode,
            caller: caller.summary, claimID: claimID, detail: detail))
        if audit.count > 100 { audit.removeFirst(audit.count - 100) }
    }
    var statusJSON: [String: Any] {
        ["policy": ["preset": policy.preset, "grantMode": "surface_modes",
                    "protectedAdministration": protectedAdministration],
         "grant": NSNull(), "pendingRequest": NSNull(),
         "lastEnded": lastEnded.map { ["reason": $0.reason] as Any } ?? NSNull(),
         "browserOnlyWhileLocked": browserOnlyWhileLocked,
         "effectiveScopes": GrantScope.allCases.filter {
             admission.enabled(Self.browserScopes.contains($0) ? "browser" : "desktop")
         }.map(\.rawValue),
         "availability": ["paused": !admission.blocks("desktop").isEmpty,
                          "blockingReasons": admission.blocks("desktop")]]
    }
}
