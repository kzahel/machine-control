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

struct Grant {
    let id: String
    let scopes: Set<GrantScope>
    let issuedAt: Date
    /// Nil only for access manually armed by the local person until Stop.
    let expiresAt: Date?
    let reason: String
    let requester: String
    let approver: String

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
    let policy: DeploymentPolicy
    var journal: DesktopJournal?
    var now: () -> Date = Date.init
    private var observers: [() -> Void] = []
    var bindAuthorityBeforeObservers: (() -> Void)?

    private(set) var grant: Grant?
    private(set) var pending: GrantRequest?
    private(set) var lastEnded: (reason: String, at: Date)?
    private(set) var audit: [AuditEntry] = []
    private let auditLimit = 100
    var consentStore: OperatorConsentStore?
    var consentStorageError: String?
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
        admission.blocks("desktop").isEmpty &&
            (policy.grantMode == .standing || activeGrant?.scopes.contains(scope) == true)
    }

    /// The live grant, after retiring an expired one.
    var activeGrant: Grant? {
        if let expiry = grant?.expiresAt, expiry <= now() {
            end(reason: "expired")
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
        if policy.grantMode == .standing { return nil }
        guard let grant = activeGrant, scopes.isSubset(of:grant.scopes) else { return "approval_required" }
        return nil
    }

    /// Returns an existing grant that already covers the request.
    func covering(_ request: GrantRequest) -> Grant? {
        guard let current = activeGrant, request.scopes.isSubset(of: current.scopes) else {
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
               requester: String, approver: String) -> Grant {
        let clamped = min(max(durationSeconds, GrantRequest.durationRange.lowerBound),
                          GrantRequest.durationRange.upperBound)
        let issued = now()
        let next = Grant(id: UUID().uuidString.lowercased(), scopes: scopes,
                         issuedAt: issued,
                         expiresAt: issued.addingTimeInterval(TimeInterval(clamped)),
                         reason: reason, requester: requester, approver: approver)
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
        let next = Grant(id: UUID().uuidString.lowercased(), scopes: scopes,
                         issuedAt: now(), expiresAt: nil,
                         reason: reason, requester: requester, approver: approver)
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
            reason:"Restored local operator consent", requester:"local operator", approver:"local_consent")
        guard journal?.event("access.restored") != false else { return nil }
        grant = next; lastEnded = nil; notify()
        return next
    }

    func revoke(reason: String) {
        end(reason: reason)
    }

    private func end(reason: String) {
        journal?.event("access." + DesktopJournal.token(reason))
        grant = nil
        if !["operator_quit", "operator_disconnected", "resident_stopping", "desktop_locked", "watchdog_interrupted", "helper_stopping", "helper_restarted", "system_sleep", "display_sleep", "display_changed", "owner_disconnected", "input_guard_unavailable"].contains(reason) {
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
            "availability": ["paused": !admission.blocks("desktop").isEmpty,
                "blockingReasons": admission.blocks("desktop")],
        ]
        if policy.grantMode == .standing {
            value["standingScopes"] = GrantScope.allCases.map(\.rawValue)
        }
        return value
    }
}
