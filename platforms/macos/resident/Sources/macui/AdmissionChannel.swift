import Darwin
import Foundation

func admissionInteger(_ value: Any?) -> Int? {
    guard let value = value as? NSNumber, CFGetTypeID(value) != CFBooleanGetTypeID(),
          value.doubleValue.isFinite, value.doubleValue == Double(value.intValue) else { return nil }
    return value.intValue
}

/// Ordered frames avoid a lifetime-sized replay cache. Once negotiated, a
/// connection cannot downgrade, skip a frame or replay an accepted sequence.
struct AdmissionRequestOrder {
    private var sequence: Int?
    private var seen = Set<String>()
    mutating func accept(_ request: [String:Any]) -> Bool {
        guard let id = request["requestId"] as? String, !id.isEmpty, id.count <= 80 else { return false }
        if sequence != nil || request["requestSequence"] != nil {
            guard let supplied = admissionInteger(request["requestSequence"]), supplied > 0,
                  (sequence ?? 0) < Int.max, supplied == (sequence ?? 0) + 1 else { return false }
            sequence = supplied; seen.removeAll(keepingCapacity:false)
            return true
        }
        return seen.count < 4096 && seen.insert(id).inserted
    }
}

/// One live same-user transport owns one intent. Labels and public identifiers
/// cannot select another connection's owner. This profile coordinates callers;
/// it does not isolate hostile processes sharing the user's shell authority.
final class AdmissionChannel {
    static let schema = "machine-control-admission-channel/v1"
    let descriptor: Int32
    let caller: CallerIdentity
    let owner = UUID().uuidString
    var intentID = ""
    var scopes: Set<GrantScope> = []
    private var source: DispatchSourceRead?
    private var buffer = Data()
    private var outgoing = Data()
    private var outgoingOffset = 0
    private var writeSource: DispatchSourceTimer?
    private var writeTimeout: DispatchWorkItem?

    private var order = AdmissionRequestOrder()
    private var closed = false
    private var dispatching = false
    private weak var server: ResidentServer?
    var coveredOwner: Int32 = -1
    var outer: OuterRecovery?
    private(set) var delegation: DesktopDelegation?
    private var trustRevision = ""

    init(_ descriptor: Int32, caller: CallerIdentity, server: ResidentServer) {
        self.descriptor = descriptor; self.caller = caller; self.server = server
    }
    func open(_ request: [String:Any]) throws {
        guard let server, caller.uid == getuid(), caller.pid > 0,
              Set(request.keys).isSubset(of:["operation", "schema", "requestId", "reason", "scopes", "durationSeconds", "waitSeconds", "claimId", "requestSequence", "outerRecovery", "desktopDelegation"]),
              request["schema"] as? String == AccessAdmission.schema,
              let names = request["scopes"] as? [String], !names.isEmpty, Set(names).count == names.count,
              names.allSatisfy({ GrantScope(rawValue:$0) != nil }),
              let duration = admissionInteger(request["durationSeconds"]),
              let wait = admissionInteger(request["waitSeconds"]),
              let reason = request["reason"] as? String,
              let requestID = request["requestId"] as? String, order.accept(request) else { throw MacUIError.usage("invalid_admission_request") }
        scopes = Set(names.compactMap(GrantScope.init(rawValue:)))
        if request["desktopDelegation"] != nil {
            guard request["outerRecovery"] == nil, server.broker.policy.grantMode == .approval else {
                throw MacUIError.permission("desktop_delegation_profile_denied")
            }
            delegation = try DesktopDelegation.parse(request["desktopDelegation"])
            trustRevision = try server.callerTrust.admittedRevision(descriptor:descriptor, scopes:scopes)
        }
        if request["outerRecovery"] != nil {
            guard scopes == Set([.observe, .control]) else { throw MacUIError.usage("invalid_outer_scopes") }
            let binding = try OuterClaimBinding.parse(request["outerRecovery"])
            outer = server.outerRecoveryFactory(binding)
        }
        let flags = fcntl(descriptor, F_GETFL)
        guard flags >= 0, fcntl(descriptor, F_SETFL, flags | O_NONBLOCK) == 0 else { throw MacUIError.action("control_transport_unavailable") }
        let broker = server.broker
        let view = try broker.admission.submit(owner:owner, requestID:requestID, resources:["desktop"],
            wait:Double(wait), duration:Double(duration), reason:reason,
            authority:{ [weak broker, weak self, scopes] in
                guard let broker, let self else { return "resident_stopped" }
                if self.delegation != nil {
                    guard let server = self.server else { return "resident_stopped" }
                    if let refusal = server.callerTrust.refusal(descriptor:self.descriptor, revision:self.trustRevision, scopes:scopes, checkPeer:false) { return refusal }
                    if broker.journal?.errorCode != nil { return "audit_storage_unavailable" }
                    if !server.approvalDesktopUnlocked() || (server.grantConsoleObservation()["uid"] as? NSNumber)?.uint32Value != getuid() {
                        return "desktop_delegation_requires_unlocked_console"
                    }
                } else if let refusal = broker.admissionAuthority(scopes:scopes) { return refusal }
                do { try self.outer?.binding.validate(); return nil }
                catch { return String(describing:error) }
            },
            notice:server.approvalDesktopUnlocked() ? server.noticeSeconds : 0)
        intentID = view["intentId"] as! String
        let source = DispatchSource.makeReadSource(fileDescriptor:descriptor, queue:.main)
        source.setEventHandler { [weak self] in self?.readable() }
        source.setCancelHandler { [descriptor] in Darwin.close(descriptor) }
        self.source = source; source.resume()
        reply(requestID, data:view)
    }
    private func readable() {
        guard !closed else { return }
        var bytes = [UInt8](repeating:0, count:16384)
        while true {
            let count = Darwin.read(descriptor, &bytes, bytes.count)
            if count == 0 { close(); return }
            if count < 0 {
                if errno == EINTR { continue }
                if errno != EAGAIN && errno != EWOULDBLOCK { close() }
                break
            }
            buffer.append(bytes, count:count)
            if buffer.count > 65536 { close(); return }
            while let newline = buffer.firstIndex(of:0x0a) {
                let line = buffer.prefix(upTo:newline); buffer.removeSubrange(...newline)
                guard let request = (try? JSONSerialization.jsonObject(with:line)) as? [String:Any] else { close(); return }
                process(request)
                if closed { return }
            }
        }
    }
    private func process(_ request: [String:Any]) {
        guard let server, let id = request["requestId"] as? String, order.accept(request) else { close(); return }
        do {
            let operation = request["operation"] as? String ?? ""
            // Clock/authority expiry is checked by inspect/cancel themselves.
            // Polls must not multiply OS/helper probes by the waiter count.
            // Revalidate native availability immediately before effects.
            if operation == "control.accept" || operation == "control.dispatch" {
                server.refreshAdmission()
                if delegation != nil, let refusal = server.callerTrust.refusal(descriptor:descriptor, revision:trustRevision, scopes:scopes) {
                    try? server.broker.admission.cancel(owner:owner, id:intentID)
                    throw MacUIError.permission(refusal)
                }
            }
            let common: Set<String> = ["operation", "requestId", "requestSequence"]
            let allowed = common.union(operation == "control.accept" ? ["offerGeneration"] :
                operation == "control.dispatch" ? ["sessionId", "resourceGenerations", "request"] : [])
            guard Set(request.keys).isSubset(of:allowed) else { throw MacUIError.usage("invalid_admission_request") }
            let admission = server.broker.admission
            switch operation {
            case "control.status", "control.heartbeat":
                reply(id, data:try admission.inspect(owner:owner, id:intentID, heartbeat:operation == "control.heartbeat"))
            case "control.accept":
                guard let generation = admissionInteger(request["offerGeneration"]) else { throw MacUIError.usage("invalid_activation_offer") }
                let physicalBaseline = server.activity.physicalAt
                let accept = { try admission.accept(owner:self.owner, id:self.intentID, generation:generation) }
                let view = try outer.map { try $0.binding.transaction(accept) } ?? accept()
                server.activity.arm(baseline:physicalBaseline)
                do {
                    if outer == nil && delegation == nil { try server.activateCovered(self, view:view) }
                    else if !server.approvalDesktopUnlocked() { throw MacUIError.action("outer_requires_unlocked_host") }
                }
                catch { try? admission.cancel(owner:owner, id:intentID); throw error }
                reply(id, data:view)
            case "control.cancel":
                try admission.cancel(owner:owner, id:intentID)
                reply(id, data:try admission.inspect(owner:owner, id:intentID))
            case "control.dispatch":
                guard !dispatching else { throw MacUIError.action("control_action_in_progress") }
                guard let session = request["sessionId"] as? String,
                      let generations = request["resourceGenerations"] as? [String:Int],
                      var action = request["request"] as? [String:Any],
                      let operation = action["operation"] as? String else { throw MacUIError.usage("invalid_control_action") }
                if let refusal = admission.authorize(owner:owner, id:intentID, session:session, generations:generations) {
                    throw MacUIError.action(refusal)
                }
                guard case let .scoped(scope) = operationClass(operation), scopes.contains(scope),
                      !["session.control", "permissions.request", "browser.endpoint"].contains(operation),
                      !(delegation != nil && operation.hasPrefix("outer.")) else {
                    throw MacUIError.action("operation_not_permitted_by_control_channel")
                }
                if let refusal = server.broker.authorize(operation, controlled:true, delegatedScopes:delegation == nil ? nil : scopes) { throw MacUIError.action(refusal.code) }
                action["requestId"] = id
                dispatching = true
                server.dispatchControlled(self, action:action, session:session, generations:generations) { [weak self] result in
                    self?.dispatching = false
                    self?.reply(id, data:result)
                }
            default: throw MacUIError.usage("unsupported_admission_operation")
            }
        } catch { reply(id, error:String(describing:error)) }
    }
    deinit { close() }
    func reply(_ id: String, data: [String:Any]? = nil, error: String? = nil) {
        guard !closed else { return }
        do {
            var data = data
            if data?["schema"] as? String == AccessAdmission.schema {
                data?["requestSequencing"] = "strict"
                if outer != nil { data?["outerRecovery"] = "borrowed_exact_claim/v1" }
                if let delegation {
                    data?["ownerAssurance"] = "verified_desktop_integration"
                    data?["desktopSession"] = ["sessionId":delegation.session, "sessionGeneration":delegation.generation]
                    data?["authorizationProfile"] = "ordinary_local_desktop"
                }
            }
            let frame = try encodeJSONLine([
                "schema":Self.schema, "requestId":id, "accepted":error == nil,
                "errorCode":error as Any? ?? NSNull(), "data":data as Any? ?? NSNull()])
            guard frame.count <= 4 * 1024 * 1024, outgoing.count - outgoingOffset + frame.count <= 8 * 1024 * 1024 else { close(); return }
            if outgoingOffset > 0 { outgoing.removeFirst(outgoingOffset); outgoingOffset = 0 }
            outgoing.append(frame)
            if writeTimeout == nil {
                let timeout = DispatchWorkItem { [weak self] in self?.close() }
                writeTimeout = timeout
                DispatchQueue.main.asyncAfter(deadline:.now() + 5, execute:timeout)
            }
            flushReplies()
        } catch { close() }
    }
    /// Slow readers cannot block the operator/main queue or truncate a large
    /// snapshot on EAGAIN. Both buffered bytes and write time are bounded.
    private func flushReplies() {
        guard !closed else { return }
        while outgoingOffset < outgoing.count {
            let written = outgoing.withUnsafeBytes { bytes in
                Darwin.write(descriptor, bytes.baseAddress!.advanced(by:outgoingOffset), outgoing.count - outgoingOffset)
            }
            if written > 0 { outgoingOffset += written; continue }
            if written < 0 && errno == EINTR { continue }
            if written < 0 && (errno == EAGAIN || errno == EWOULDBLOCK) {
                if writeSource == nil {
                    let source = DispatchSource.makeTimerSource(queue:.main)
                    // Darwin Unix-socket write readiness can remain below its
                    // low-water mark with a small peer buffer. Retry without
                    // blocking the main queue; the absolute timeout still caps
                    // a stalled reader.
                    source.schedule(deadline:.now() + .milliseconds(25), repeating:.milliseconds(25))
                    source.setEventHandler { [weak self] in self?.flushReplies() }
                    writeSource = source; source.resume()
                }
                return
            }
            close(); return
        }
        outgoing.removeAll(keepingCapacity:false); outgoingOffset = 0
        writeSource?.cancel(); writeSource = nil
        writeTimeout?.cancel(); writeTimeout = nil
    }

    func tick() {
        if coveredOwner >= 0 {
            var input = pollfd(fd:coveredOwner, events:Int16(POLLIN | POLLHUP), revents:0)
            if poll(&input, 1, 0) > 0 { Darwin.close(coveredOwner); coveredOwner = -1 }
            else { try? writeSocket(coveredOwner, data:encodeJSONLine(["operation":"heartbeat"])) }
        }
    }
    func close() {
        guard !closed else { return }; closed = true
        outer?.invalidate()
        writeSource?.cancel(); writeSource = nil
        writeTimeout?.cancel(); writeTimeout = nil
        outgoing.removeAll()
        server?.broker.admission.disconnect(owner)
        if coveredOwner >= 0 { Darwin.close(coveredOwner); coveredOwner = -1 }
        if let source { source.cancel() } else { Darwin.close(descriptor) }
        server?.removeChannel(descriptor)
        server = nil
    }
}
