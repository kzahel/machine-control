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
    case "capabilities", "status", "desktop.delegation.status":
        return .discovery
    case "grant.request", "grant.status", "grant.revoke":
        return .grantManagement
    case "browser.provider":
        return .providerRegistration
    case "browser.endpoint":
        // Reports the DevTools WebSocket endpoint; the token, not this call,
        // gates the socket, and the endpoint is only present under a grant.
        return .discovery
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

/// Owns the live grant for this resident. All access happens on the main
/// queue, like the rest of the resident.
final class GrantBroker {
    /// Operational failure ends live authority, not the person's saved choice.
    /// Only a trusted authority transition may invalidate that choice.
    enum ConsentDisposition { case retain, invalidate }
    let policy: DeploymentPolicy
    var journal: DesktopJournal?
    var now: () -> Date = Date.init
    private var observers: [() -> Void] = []
    var bindAuthorityBeforeObservers: (() -> Void)?

    var authorityChanged: (() -> Void)?
    private(set) var grant: Grant? {
        didSet { if oldValue?.id != grant?.id { authorityChanged?() } }
    }
    private(set) var pending: GrantRequest?
    private(set) var lastEnded: (reason: String, at: Date)?
    private(set) var audit: [AuditEntry] = []
    private let auditLimit = 100
    var consentStore: OperatorConsentStore?
    var consentStorageError: String?
    var restorationBlockedScopes = Set<GrantScope>()
    /// A retained mixed grant keeps its identity and expiry, but cannot expose
    /// desktop observation/input while only browser access is permitted.
    var browserOnlyWhileLocked = false {
        didSet { if oldValue != browserOnlyWhileLocked { notify() } }
    }
    static let browserScopes: Set<GrantScope> = [.browser, .devtools]
    private func scopeAvailable(_ scope: GrantScope) -> Bool {
        !browserOnlyWhileLocked || Self.browserScopes.contains(scope)
    }
    var availabilityChanged: (() -> Void)?
    private var availabilityRevision = 0
    lazy var admission: AccessAdmission = {
        let value = AccessAdmission()
        value.register("desktop")
        value.changed = { [weak self] in self?.refreshAvailability() }
        return value
    }()

    func refreshAvailability() {
        admission.refresh()
        guard availabilityRevision != admission.revision else { return }
        availabilityRevision = admission.revision
        availabilityChanged?()
        notify()
    }

    /// Called only by trusted native/operator surfaces or internal monitors.
    func pause(reason: String = "manual", seconds: Int? = nil) throws {
        if reason == "manual" || reason == "operator_deferral" { try consentStore?.pause(seconds:seconds, deferral:reason == "operator_deferral") }
        try admission.pause("desktop", reason: reason, seconds: seconds.map(Double.init))
        journal?.event("access.paused")
    }

    func resume() throws {
        try consentStore?.resume()
        admission.resume("desktop", reason: "manual")
        admission.resume("desktop", reason: "operator_deferral")
        admission.resume("desktop", reason: "local_use_episode")
        journal?.event("access.resumed")
    }

    init(policy: DeploymentPolicy) {
        self.policy = policy
    }

    /// Registers a callback for grant, pending-request, and expiry changes.
    func observe(_ observer: @escaping () -> Void) {
        observers.append(observer)
    }

    private func notify() {
        bindAuthorityBeforeObservers?()
        for observer in observers { observer() }
    }

    /// Whether browser operations are currently allowed.
    var browserAllowed: Bool { allows(.browser) }

    /// Whether raw DevTools protocol access is currently allowed.
    var devtoolsAllowed: Bool { allows(.devtools) }

    private func allows(_ scope: GrantScope) -> Bool {
        scopeAvailable(scope) && admission.blocks("desktop").isEmpty &&
            (policy.grantMode == .standing || activeGrant?.scopes.contains(scope) == true)
    }

    /// The live grant, after retiring an expired one.
    var activeGrant: Grant? {
        if let expiry = grant?.expiresAt, expiry <= now() {
            end(reason: "expired", consent: grant?.origin == .person ? .invalidate : .retain)
        }
        return grant
    }

    func authorize(_ operation: String, controlled: Bool = false, delegatedScopes: Set<GrantScope>? = nil) -> GrantRefusal? {
        switch operationClass(operation) {
        case .discovery, .grantManagement, .lifecycle, .providerRegistration:
            return nil
        case .protected:
            guard policy.protectedOperations else {
                return GrantRefusal("operation_not_permitted_by_policy",
                    "The \(policy.preset) deployment policy does not allow \(operation)")
            }
            guard policy.grantMode == .standing else {
                return GrantRefusal("operation_not_permitted_by_policy",
                    "Protected operations require a standing deployment policy")
            }
            if !admission.blocks("desktop").isEmpty {
                return GrantRefusal("access_paused", "Computer access is temporarily paused")
            }
            return nil
        case let .scoped(scope):
            if restorationBlockedScopes.contains(scope) {
                return GrantRefusal("access_temporarily_unavailable", "Saved consent is retained; this route is waiting for readiness", requiredScope:scope)
            }
            guard scopeAvailable(scope) else {
                return GrantRefusal("desktop_locked_browser_only",
                    "Only previously approved browser access is available while locked",
                    requiredScope: scope)
            }
            if !controlled && admission.reserved {
                return GrantRefusal("control_session_required", "The desktop is reserved; use an owner-bound control channel", requiredScope:scope)
            }
            if !admission.blocks("desktop").isEmpty {
                return GrantRefusal("access_paused", "Computer access is temporarily paused; inspect grant.status", requiredScope: scope)
            }
            if policy.grantMode == .standing { return nil }
            // A controlled session must not be able to act on its own
            // approval prompt, so control waits while one is visible.
            if pending != nil && scope != .observe {
                return GrantRefusal("approval_prompt_visible",
                    "Control is paused while an approval prompt is visible",
                    requiredScope: scope)
            }
            if let delegatedScopes {
                return delegatedScopes.contains(scope) ? nil : GrantRefusal("desktop_trust_scope_denied", "This session has no authority for the requested scope")
            }
            guard let current = activeGrant else {
                return GrantRefusal("approval_required",
                    "No active grant; request one with grant.request",
                    requiredScope: scope)
            }
            guard current.scopes.contains(scope) else {
                return GrantRefusal("approval_required",
                    "The active grant does not include \(scope.rawValue)",
                    requiredScope: scope)
            }
            return nil
        }
    }

    func admissionAuthority(scopes: Set<GrantScope>) -> String? {
        if journal?.errorCode != nil { return "audit_storage_unavailable" }
        if !scopes.allSatisfy(scopeAvailable) { return "desktop_locked_browser_only" }
        if policy.grantMode == .standing { return nil }
        if !scopes.isDisjoint(with:restorationBlockedScopes) { return "access_temporarily_unavailable" }
        guard let grant = activeGrant, scopes.isSubset(of:grant.scopes) else { return "approval_required" }
        return nil
    }

    /// Returns an existing grant that already covers the request.
    func covering(_ request: GrantRequest) -> Grant? {
        guard let current = activeGrant, request.scopes.isSubset(of: current.scopes),
              request.scopes.allSatisfy(scopeAvailable) else {
            return nil
        }
        return current
    }

    func beginPending(_ request: GrantRequest) -> GrantRefusal? {
        guard pending == nil else {
            return GrantRefusal("approval_pending", "Another grant request is awaiting a decision")
        }
        guard journal?.event("access.requested") != false else { return GrantRefusal("audit_storage_unavailable", "Audit storage unavailable") }
        pending = request
        notify()
        return nil
    }

    /// Applies a decision to the pending request and returns the new grant.
    func finishPending(_ decision: GrantDecision, approver: String) -> Grant? {
        guard let request = pending else { return nil }
        pending = nil
        defer { notify() }
        guard case let .approved(scopes, duration) = decision else {
            journal?.event(decision == .timedOut ? "access.approval_timeout" : "access.denied", accepted: false)
            return nil
        }
        let narrowed = scopes.intersection(request.scopes)
        guard !narrowed.isEmpty else { return nil }
        let issued = issue(scopes: narrowed,
                     durationSeconds: min(duration, request.durationSeconds),
                     reason: request.reason, requester: request.caller.summary,
                     approver: approver)
        return journal?.errorCode == nil ? issued : nil
    }

    @discardableResult
    func issue(scopes: Set<GrantScope>, durationSeconds: Int, reason: String,
               requester: String, approver: String, origin: GrantOrigin = .request) -> Grant {
        restorationBlockedScopes.removeAll()
        let clamped = min(max(durationSeconds, GrantRequest.durationRange.lowerBound),
                          GrantRequest.durationRange.upperBound)
        let issued = now()
        let next = Grant(id: UUID().uuidString.lowercased(), scopes: scopes,
                         issuedAt: issued,
                         expiresAt: issued.addingTimeInterval(TimeInterval(clamped)),
                         reason: reason, requester: requester, approver: approver,
                         origin: origin)
        guard journal?.event("access.enabled") != false else {
            lastEnded = ("audit_storage_unavailable", now()); notify(); return next
        }
        grant = next
        lastEnded = nil
        notify()
        return next
    }

    /// The local operator can explicitly arm access without a timer. Agent
    /// requests still receive bounded grants through finishPending. This
    /// grant stays in memory and uses the same Stop/session revocation path.
    @discardableResult
    func issueUntilStopped(scopes: Set<GrantScope>, reason: String,
                           requester: String, approver: String) -> Grant {
        restorationBlockedScopes.removeAll()
        let next = Grant(id: UUID().uuidString.lowercased(), scopes: scopes,
                         issuedAt: now(), expiresAt: nil,
                         reason: reason, requester: requester, approver: approver,
                         origin: .person)
        guard journal?.event("access.enabled") != false else {
            lastEnded = ("audit_storage_unavailable", now()); notify(); return next
        }
        grant = next
        lastEnded = nil
        notify()
        return next
    }

    /// Restore only the remaining consent lifetime; never clamp it up to the
    /// minimum duration of a new approval request.
    @discardableResult
    func restoreConsent(scopes: Set<GrantScope>, remainingSeconds: Int?) -> Grant? {
        guard !scopes.isEmpty, remainingSeconds == nil || (1...28800).contains(remainingSeconds!) else { return nil }
        let issued = now()
        let next = Grant(id: UUID().uuidString.lowercased(), scopes:scopes, issuedAt:issued,
            expiresAt:remainingSeconds.map { issued.addingTimeInterval(Double($0)) },
            reason:"Restored local operator consent", requester:"local operator", approver:"local_consent",
            origin:.person)
        guard journal?.event("access.restored") != false else { return nil }
        grant = next; lastEnded = nil; notify()
        return next
    }

    func revoke(reason: String, consent: ConsentDisposition = .retain) {
        end(reason: reason, consent: consent)
    }

    /// Local authority ends before protected cleanup or durable writes wait.
    func fence() {
        if grant != nil { fenced = grant }
        grant = nil
    }
    /// The grant a fence cleared, so its end can still see its origin.
    private var fenced: Grant?

    /// The person's own controls; only these always clear saved consent.
    static let personStopReasons: Set<String> = ["stopped_from_menu", "stopped_by_hotkey", "stopped_by_person"]

    /// Saved consent is the person's arming. An agent's revoke or the end of
    /// an agent-request grant must not clear it; the person's Stop always does.
    static func clearsConsent(reason: String, ending: GrantOrigin?, consent: ConsentDisposition = .retain) -> Bool {
        if personStopReasons.contains(reason) { return true }
        return consent == .invalidate
    }

    private func end(reason: String, consent: ConsentDisposition = .retain) {
        let ending = grant ?? fenced
        grant = nil
        fenced = nil
        restorationBlockedScopes.removeAll()
        journal?.event("access." + DesktopJournal.token(reason))
        if Self.clearsConsent(reason: reason, ending: ending?.origin, consent: consent) {
            do { try consentStore?.disable() } catch { consentStorageError = String(describing:error) }
        }
        admission.stop(reason)
        lastEnded = (reason, now())
        notify()
    }

    func record(operation: String, accepted: Bool, errorCode: String?,
                caller: CallerIdentity, claimID: String?, detail: String? = nil) {
        audit.append(AuditEntry(at: now(), operation: operation, accepted: accepted,
                                errorCode: errorCode, caller: caller.summary,
                                claimID: claimID, detail: detail))
        if audit.count > auditLimit { audit.removeFirst(audit.count - auditLimit) }
    }

    var statusJSON: [String: Any] {
        let current = now()
        var value: [String: Any] = [
            "policy": policy.json,
            "grant": activeGrant.map { $0.json(now: current) as Any } ?? NSNull(),
            "pendingRequest": pending.map { request -> Any in
                ["requestId": request.id,
                 "scopes": request.scopes.sorted().map(\.rawValue),
                 "durationSeconds": request.durationSeconds,
                 "caller": request.caller.summary]
            } ?? NSNull(),
            "lastEnded": lastEnded.map { ended -> Any in
                ["reason": ended.reason,
                 "at": ISO8601DateFormatter().string(from: ended.at)]
            } ?? NSNull(),
            "consentStorageError":consentStorageError as Any? ?? NSNull(),
            "restorationBlockedScopes":restorationBlockedScopes.sorted().map(\.rawValue),
            "browserOnlyWhileLocked": browserOnlyWhileLocked,
            "effectiveScopes": (policy.grantMode == .standing ? Set(GrantScope.allCases) : activeGrant?.scopes ?? [])
                .filter(allows).sorted().map(\.rawValue),
            "availability": ["paused": !admission.blocks("desktop").isEmpty,
                "blockingReasons": admission.blocks("desktop")],
        ]
        if policy.grantMode == .standing {
            value["standingScopes"] = GrantScope.allCases.map(\.rawValue)
        }
        return value
    }
}
