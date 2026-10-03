import AppKit
import ApplicationServices
import Darwin
import Foundation

/// Resident endpoints must not survive in restarted apps or tool children.
func closeOnExec(_ descriptor: Int32) throws {
    let flags = fcntl(descriptor, F_GETFD)
    guard flags >= 0, fcntl(descriptor, F_SETFD, flags | FD_CLOEXEC) == 0 else {
        throw MacUIError.action("Unable to protect Unix socket from inheritance")
    }
}

func residentSocket() throws -> Int32 {
    let descriptor = socket(AF_UNIX, SOCK_STREAM, 0)
    guard descriptor >= 0 else { throw MacUIError.action("Unable to create Unix socket") }
    do { try closeOnExec(descriptor) }
    catch { Darwin.close(descriptor); throw error }
    return descriptor
}

func encodeJSONLine(_ object: [String: Any]) throws -> Data {
    var data = try JSONSerialization.data(withJSONObject: object,
                                           options: [.sortedKeys])
    data.append(0x0a)
    return data
}

func unixAddress(_ path: String) throws -> (sockaddr_un, socklen_t) {
    let bytes = Array(path.utf8CString)
    var address = sockaddr_un()
    guard bytes.count <= MemoryLayout.size(ofValue: address.sun_path) else {
        throw MacUIError.usage("Unix socket path is too long")
    }
    address.sun_family = sa_family_t(AF_UNIX)
    withUnsafeMutableBytes(of: &address.sun_path) { destination in
        bytes.withUnsafeBytes { source in
            destination.copyBytes(from: source)
        }
    }
    let length = socklen_t(MemoryLayout<sa_family_t>.size + bytes.count)
    return (address, length)
}

func withSockAddr<T>(_ address: inout sockaddr_un, length: socklen_t,
                     _ body: (UnsafePointer<sockaddr>, socklen_t) throws -> T) rethrows -> T {
    try withUnsafePointer(to: &address) {
        try $0.withMemoryRebound(to: sockaddr.self, capacity: 1) {
            try body($0, length)
        }
    }
}

func readSocket(_ descriptor: Int32, limit: Int = 1_048_576) throws -> Data {
    var result = Data()
    var buffer = [UInt8](repeating: 0, count: 16_384)
    while result.count < limit {
        let count = Darwin.read(descriptor, &buffer, buffer.count)
        if count == 0 { break }
        if count < 0 {
            if errno == EINTR { continue }
            throw MacUIError.action("Socket read failed: \(String(cString: strerror(errno)))")
        }
        result.append(buffer, count: count)
        if result.last == 0x0a { break }
    }
    guard result.count < limit else {
        throw MacUIError.usage("Request exceeded \(limit) bytes")
    }
    return result
}

func writeSocket(_ descriptor: Int32, data: Data) throws {
    try data.withUnsafeBytes { rawBuffer in
        guard var pointer = rawBuffer.baseAddress else { return }
        var remaining = rawBuffer.count
        while remaining > 0 {
            let count = Darwin.write(descriptor, pointer, remaining)
            if count < 0 {
                if errno == EINTR { continue }
                throw MacUIError.action("Socket write failed: \(String(cString: strerror(errno)))")
            }
            remaining -= count
            pointer = pointer.advanced(by: count)
        }
    }
}

/// Event-driven resident server on the main queue. Requests still run one
/// at a time on the main thread, as providers expect; a grant request may
/// stay open while a person decides.
final class ResidentServer {
    let socketPath: String
    let service: ResidentService
    let broker: GrantBroker
    var callerTrust: DesktopCallerTrust
    let updates = DesktopUpdates()
    let activity = PhysicalAvailability()
    var noticeSeconds = 10.0
    var coveredActivation: ((AdmissionChannel, [String:Any]) throws -> Void)?
    var controlledProvider: (([String:Any]) -> [String:Any])?
    var outerRecoveryFactory: (OuterClaimBinding) -> OuterRecovery = {
        OuterRecovery(binding:$0, input:OuterRecovery.emitNative)
    }
    private var channels: [Int32:AdmissionChannel] = [:]
    private var noticePolicyState = ""
    var notice: AdmissionNotice?
    private var handshakes: [Int32:RequestHandshake] = [:]
    func callerSummary(for intent: String) -> String { channels.values.first(where:{ $0.intentID == intent })?.caller.summary ?? "Local process" }
    func startNow(_ intent: String) throws {
        try broker.admission.startNow(intent)
        activity.acknowledgeCurrentActivity()
        refreshAdmission()
    }
    func cancelFromOperator(_ intent: String) throws {
        guard let channel = channels.values.first(where:{ $0.intentID == intent }) else { throw MacUIError.action("stale_activation_notice") }
        try broker.admission.cancel(owner:channel.owner, id:intent)
    }
    func removeChannel(_ descriptor: Int32) { channels.removeValue(forKey:descriptor) }
    func refreshAdmission() { tick() }
    func activateCovered(_ channel: AdmissionChannel, view: [String:Any]) throws {
        if let coveredActivation { try coveredActivation(channel, view); return }
        guard service.observedDesktopState == "locked" else { return }
        guard channel.scopes.contains(.control) else { throw MacUIError.action("locked_control_scope_required") }
        var pair: [Int32] = [-1, -1]
        guard socketpair(AF_UNIX, SOCK_STREAM, 0, &pair) == 0 else { throw MacUIError.action("control_transport_unavailable") }
        do {
            try closeOnExec(pair[0]); try closeOnExec(pair[1])
            _ = try lockedUse.begin(["operation":"session.control", "requestId":UUID().uuidString,
                "durationSeconds":max(1, Int(view["activeRemainingSeconds"] as? Double ?? 1))], owner:pair[0])
            channel.coveredOwner = pair[1]
        } catch { Darwin.close(pair[0]); Darwin.close(pair[1]); throw error }
    }
    func dispatchControlled(_ channel: AdmissionChannel, action original: [String:Any], session: String,
                            generations: [String:Int], completion: @escaping ([String:Any]) -> Void) {
        var action = original
        let operation = action["operation"] as? String ?? ""
        if operation.hasPrefix("outer.") {
            guard let outer = channel.outer else {
                completion(service.refusal(action, code:"outer_binding_required", message:"Outer recovery requires an exact borrowed VM claim")); return
            }
            guard broker.journal?.begin(action, caller:channel.caller) != false else {
                completion(service.refusal(action, code:"audit_storage_unavailable", message:"Audit storage unavailable")); return
            }
            outer.fence = { [weak self, weak channel] in
                guard let self, let channel else { throw MacUIError.action("owner_disconnected") }
                self.refreshAdmission()
                if let refusal = self.broker.admission.authorize(owner:channel.owner, id:channel.intentID, session:session, generations:generations) { throw MacUIError.action(refusal) }
                if let refusal = self.service.inputCancellation() { throw MacUIError.action(refusal) }
            }
            do {
                let data: [String:Any]
                switch operation {
                case "outer.prepare": data = try outer.prepare()
                case "outer.begin": try outer.begin(action); data = ["delivery":"confirmed", "effect":"unverifiable"]
                case "outer.step": try outer.step(action); data = ["delivery":"confirmed", "effect":"unverifiable"]
                default: throw MacUIError.usage("unsupported_outer_operation")
                }
                try outer.fence()
                var response = service.acceptance(action, data:data)
                response["actualRoute"] = "host.user/macos-native.outer"
                response["hostInterference"] = "focus_cursor_keyboard"
                response["delivery"] = operation == "outer.prepare" ? "not_applicable" : "confirmed"
                response["effect"] = "unverifiable"
                response["uncertainty"] = "no_independent_guest_effect"
                if broker.journal?.record(response) == false {
                    response["accepted"] = false; response["errorCode"] = "audit_storage_unavailable"
                    response["uncertainty"] = "audit_result_not_persisted"
                }
                completion(response)
            } catch {
                outer.cleanup()
                var response = service.refusal(action, code:String(describing:error), message:"Outer recovery refused")
                response["uncertainty"] = operation == "outer.prepare" ? "none" : "interrupted_after_possible_dispatch"
                response["retrySafety"] = "unsafe"
                _ = broker.journal?.record(response); completion(response)
            }
            return
        }
        if let refusal = lockedUse.refusal(action) {
            completion(service.refusal(action, code:refusal.code, message:refusal.message)); return
        }
        if let refusal = guardRequest?(action) {
            completion(service.refusal(action, code:refusal.code, message:refusal.message)); return
        }
        guard broker.journal?.begin(action, caller:channel.caller) != false else {
            completion(service.refusal(action, code:"audit_storage_unavailable", message:"Audit storage unavailable")); return
        }
        let finish: ([String:Any]) -> Void = { [weak self, weak channel] original in
            guard let self, let channel else { return }
            var result = original
            self.refreshAdmission()
            if let refusal = self.broker.admission.authorize(owner:channel.owner, id:channel.intentID,
                session:session, generations:generations) {
                result["errorCode"] = refusal; result["accepted"] = false
                result["uncertainty"] = "interrupted_after_possible_dispatch"; result["retrySafety"] = "unsafe"
            }
            if self.broker.journal?.record(result) == false {
                result["accepted"] = false; result["errorCode"] = "audit_storage_unavailable"
                result["uncertainty"] = "audit_result_not_persisted"
            }
            completion(result)
        }
        if [.scoped(.browser), .scoped(.devtools)].contains(operationClass(operation)) {
            if let refusal = browser.forward(-1, action, caller:channel.caller, claimID:nil, completion:finish) { finish(refusal) }
        } else {
            if lockedUse.isCovered { action["provider"] = "macos-native" }
            finish(controlledProvider?(action) ?? service.handle(action))
        }
    }
    weak var approver: GrantApprover?
    /// Extra screening for approved control, such as refusing input aimed
    /// at the resident's own interface.
    var guardRequest: (([String: Any]) -> GrantRefusal?)?

    private var listener: Int32 = -1
    private var acceptSource: DispatchSourceRead?
    private var ticker: DispatchSourceTimer?
    private var pendingClient: Int32 = -1
    private var pendingRequest: [String: Any]?
    private var pendingTimeout: DispatchWorkItem?
    private var grantConsoleBinding: GrantConsoleBinding?
    private var observedGrantID: String?

    let browser: BrowserRelay
    let devtools: BrowserDevToolsBridge
    lazy var lockedUse = MacLockedUse(broker: broker, service: service)
    // Tests provide a desktop observation without relying on host lock state.
    var approvalDesktopUnlocked: () -> Bool
    var grantConsoleObservation: () -> [String:Any]

    init(socketPath: String, service: ResidentService, broker: GrantBroker) {
        self.socketPath = socketPath
        callerTrust = DesktopCallerTrust(directory:(socketPath as NSString).deletingLastPathComponent)
        self.service = service
        self.broker = broker
        approvalDesktopUnlocked = { service.observedDesktopState == "unlocked" }
        grantConsoleObservation = { service.observedConsoleSession }
        browser = BrowserRelay(service: service, broker: broker)
        devtools = BrowserDevToolsBridge(broker: broker, relay: browser)
        browser.respond = { [weak self] client, request, response, caller, claimID in
            self?.respond(client, request, response, caller: caller, claimID: claimID)
        }
        // Bind synchronously when approval is issued, including a lock that
        // follows before the next timer tick. Never adopt an unbound grant later.
        broker.observe { [weak self] in self?.bindApprovedConsole() }
        broker.admission.sessionEnded = { [weak self] owner, _, reason in
            self?.channels.values.first(where:{ $0.owner == owner })?.outer?.invalidate()
            self?.activity.disarm()
            self?.lockedUse.end(coveredAdmissionEnding(reason))
        }
        broker.availabilityChanged = { [weak self] in
            guard let self else { return }
            self.service.invalidateReferences()
            self.browser.closeAllSessions(reason:"control_generation_changed")
            let reasons = self.broker.admission.blocks("desktop")
            if !reasons.isEmpty {
                self.lockedUse.end(reasons.contains("physical_activity") ? "physical_presence" : "operator_paused")
            }
        }
        bindApprovedConsole()
        // Initialize the lazy coordinator before installing the callback. Each
        // lease gets a fresh latch; never capture a retired lease's safety.
        _ = lockedUse.safety
        service.inputCancellation = { [weak self] in
            self?.lockedUse.safety.reason ?? self?.activity.interruption
        }
    }

    func stop() {
        ticker?.cancel(); ticker = nil
        acceptSource?.cancel(); acceptSource = nil
        for channel in Array(channels.values) { channel.close() }
        for handshake in Array(handshakes.values) { handshake.cancel() }
        handshakes.removeAll()
        if listener >= 0 { Darwin.close(listener); listener = -1; unlink(socketPath) }
        activity.stop()
    }
    deinit { stop() }

    func restoreOperatorConsent() {
        guard broker.policy.grantMode == .approval, broker.grant == nil, broker.pending == nil,
              let store = broker.consentStore, broker.consentStorageError == nil, broker.journal?.errorCode == nil else { return }
        service.refreshSession()
        let observation = grantConsoleObservation()
        guard let (scopes, duration) = store.consent(console:observation) else { return }
        let helper = service.unlockStatus()
        if helper["lockedUsePaused"] as? Bool == true &&
            !["physical_presence", "local_use_episode"].contains(helper["lockedUsePauseReason"] as? String ?? "") { return }
        if observation["desktopState"] as? String == "locked" && !lockedUse.enabled { return }
        guard ["unlocked", "locked"].contains(observation["desktopState"] as? String ?? ""),
              AXIsProcessTrusted(), CGPreflightScreenCaptureAccess(), CGPreflightPostEventAccess() else { return }
        guard let fresh = broker.restoreConsent(scopes:scopes, remainingSeconds:duration) else { return }
        grantConsoleBinding = GrantConsoleBinding(grantID:fresh.id, observation:observation, restoring:true)
    }

    private func bindApprovedConsole() {
        let id = broker.grant?.id
        guard observedGrantID != id else { return }
        observedGrantID = id; grantConsoleBinding = nil
        guard broker.policy.grantMode == .approval, let id else { return }
        service.refreshSession()
        grantConsoleBinding = GrantConsoleBinding(grantID:id, observation:grantConsoleObservation())
    }

    func start() throws {
        let descriptor = try residentSocket()
        var started = false
        defer { if !started { Darwin.close(descriptor) } }
        unlink(socketPath)
        var (address, length) = try unixAddress(socketPath)
        guard withSockAddr(&address, length: length, {
            Darwin.bind(descriptor, $0, $1)
        }) == 0 else {
            throw MacUIError.action("Unable to bind Unix socket: \(String(cString: strerror(errno)))")
        }
        guard chmod(socketPath, S_IRUSR | S_IWUSR) == 0,
              listen(descriptor, 8) == 0 else {
            throw MacUIError.action("Unable to listen on Unix socket")
        }
        listener = descriptor
        let source = DispatchSource.makeReadSource(fileDescriptor: descriptor, queue: .main)
        source.setEventHandler { [weak self] in self?.acceptPending() }
        source.resume()
        acceptSource = source
        let timer = DispatchSource.makeTimerSource(queue: .main)
        timer.schedule(deadline: .now(), repeating: .milliseconds(250))
        timer.setEventHandler { [weak self] in self?.tick() }
        timer.resume()
        ticker = timer
        started = true
    }

    private func tick() {
        autoreleasepool { service.refreshSession() }
        restoreOperatorConsent()
        let observation = grantConsoleObservation()
        let state = observation["desktopState"] as? String ?? "unknown"
        let noticeState = "\(state):\(lockedUse.isCovered):\(noticeSeconds)"
        if noticeState != noticePolicyState {
            noticePolicyState = noticeState
            broker.admission.reconfigureNotice(state == "locked" || lockedUse.isCovered ? 0 : noticeSeconds)
        }
        if broker.policy.grantMode == .approval, let grant = broker.activeGrant {
            let reason: String?
            if grantConsoleBinding?.matches(grantID:grant.id, observation:observation) != true {
                reason = "console_session_changed"
            } else if state != "unlocked" && !(state == "locked" && lockedUse.preservesGrantAcrossLock) {
                reason = "desktop_\(state)"
            } else { reason = nil }
            if let reason {
                broker.revoke(reason:reason); grantConsoleBinding = nil
                service.invalidateReferences()
            }
        } else {
            grantConsoleBinding = nil
        }
        lockedUse.tick()
        if activity.enabled { activity.tick(broker, helper:service.unlockStatus()) }
        broker.refreshAvailability()
        for channel in Array(channels.values) { channel.tick() }
        notice?.update()
    }

    private func acceptPending() {
        let client = accept(listener, nil, nil)
        guard client >= 0 else { return }
        do { try closeOnExec(client) }
        catch { Darwin.close(client); return }
        // A stalled client must not wedge the single-threaded resident.
        var timeout = timeval(tv_sec: 5, tv_usec: 0)
        setsockopt(client, SOL_SOCKET, SO_RCVTIMEO, &timeout,
                   socklen_t(MemoryLayout.size(ofValue: timeout)))
        setsockopt(client, SOL_SOCKET, SO_SNDTIMEO, &timeout,
                   socklen_t(MemoryLayout.size(ofValue: timeout)))
        var noSignal: Int32 = 1
        setsockopt(client, SOL_SOCKET, SO_NOSIGPIPE, &noSignal,
                   socklen_t(MemoryLayout.size(ofValue: noSignal)))
        guard handshakes.count < 64 else { Darwin.close(client); return }
        let handshake = RequestHandshake(client)
        handshakes[client] = handshake
        handshake.completion = { [weak self] data in
            guard let self else { Darwin.close(client); return }
            self.handshakes.removeValue(forKey:client)
            guard let data else { Darwin.close(client); return }
            autoreleasepool { self.serve(client, data:data) }
        }
        do { try handshake.start() }
        catch { handshakes.removeValue(forKey:client); handshake.cancel() }
    }

    private func serve(_ client: Int32, data: Data) {
        var keepOpen = false
        defer { if !keepOpen { Darwin.close(client) } }
        var request: [String: Any] = [:]
        do {
            guard let object = try JSONSerialization.jsonObject(with: data) as? [String: Any] else {
                throw MacUIError.usage("Request must be a JSON object")
            }
            request = object
            request["requestId"] = request["requestId"] as? String ?? UUID().uuidString.lowercased()
        } catch {
            let response: [String: Any] = [
                "schema": "machine-control/v0", "operation": "unknown",
                "requestId": UUID().uuidString.lowercased(), "accepted": false,
                "actualRoute": "guest.user/macos.resident",
                "delivery": "refused", "effect": "refused",
                "uncertainty": "none", "errorCode": "invalid_request",
                "message": String(describing: error), "elapsedMs": 0,
            ]
            try? writeSocket(client, data: encodeJSONLine(response))
            return
        }
        let operation = request["operation"] as? String ?? ""
        if operation == "input.key", let key = request["key"] as? String {
            request["key"] = normalizedKeyChord(key)
        }
        let caller = CallerIdentity.of(socket: client)
        let claimID = request["claimId"] as? String
        if broker.journal?.begin(request, caller: caller) == false, !["grant.revoke", "server.stop", "session.control.end"].contains(operation) {
            respond(client, request, service.refusal(request, code: "audit_storage_unavailable", message: "Audit storage unavailable"), caller: caller, claimID: claimID)
            return
        }
        // Observe transitions before authorization, rather than leaving a
        // quarter-second gap in the timer's lock-revocation policy.
        tick()

        if operation == "control.open" {
            guard channels.count < 64, channels.values.filter({ $0.caller.pid == caller.pid }).count < 4 else {
                respond(client, request, service.refusal(request, code:"admission_queue_full", message:"Admission channel limit reached"), caller:caller, claimID:claimID); return
            }
            let channel = AdmissionChannel(client, caller:caller, server:self)
            // Transfer descriptor ownership before opening: an immediately
            // disconnected peer must not leave a resurrected channel or cause
            // both the server defer and source cancellation to close this fd.
            channels[client] = channel; keepOpen = true
            do { try channel.open(request) }
            catch { channel.reply(request["requestId"] as? String ?? "", error:String(describing:error)); channel.close() }
            return
        }

        if operation == "session.control.end" {
            guard let id = request["controlSessionId"] as? String, id == lockedUse.lease?.id else {
                respond(client, request, service.refusal(request, code:"stale_control_session",
                    message:"Observe the current control session before ending it"), caller:caller, claimID:claimID)
                return
            }
            lockedUse.end("completed")
            respond(client, request, service.acceptance(request, data:lockedUse.status), caller:caller, claimID:claimID)
            return
        }

        if operation == "update.check" || operation == "update.status" {
            let response = updates.request(check: operation == "update.check")
                .map { service.acceptance(request, data: $0) }
                ?? service.refusal(request, code: "unsupported_operation",
                    message: "Updates require the desktop product")
            respond(client, request, response, caller: caller, claimID: claimID)
            return
        }

        if operation == "browser.provider" {
            if let refusal = browser.register(client, request) {
                respond(client, request, refusal, caller: caller, claimID: claimID)
            } else {
                broker.journal?.event("browser.connected")
                keepOpen = true
            }
            return
        }
        if operation.hasPrefix("grant.") {
            if let response = handleGrant(request, operation: operation, caller: caller,
                                          client: client) {
                respond(client, request, response, caller: caller, claimID: claimID)
            } else {
                keepOpen = true
            }
            return
        }
        if let refusal = broker.authorize(operation) {
            respond(client, request, refused(request, refusal), caller: caller, claimID: claimID)
            return
        }
        if operation == "session.control" {
            do {
                let response = try lockedUse.begin(request, owner:client)
                respond(client, request, response, caller:caller, claimID:claimID)
                keepOpen = true
            } catch {
                respond(client, request, service.refusal(request, code:String(describing:error),
                    message:"Cannot start locked use; inspect lockedUse status and existing access"), caller:caller, claimID:claimID)
            }
            return
        }
        if lockedUse.isCovered, request["provider"] == nil,
           !operation.hasPrefix("browser.") && !operation.hasPrefix("devtools.") {
            request["provider"] = "macos-native"
        }
        if case .scoped = operationClass(operation), let refusal = lockedUse.refusal(request) {
            respond(client, request, refused(request, refusal), caller:caller, claimID:claimID)
            return
        }
        if broker.policy.grantMode == .approval, case let .scoped(scope) = operationClass(operation),
           scope != .observe, let refusal = guardRequest?(request) {
            respond(client, request, refused(request, refusal), caller: caller, claimID: claimID)
            return
        }
        if operation == "permissions.request" {
            // Registers this application in the Accessibility and Screen
            // Recording lists; macOS still requires a person or trusted
            // settings automation to enable them.
            let promptKey = kAXTrustedCheckOptionPrompt.takeUnretainedValue() as String
            let accessibility = AXIsProcessTrustedWithOptions([promptKey: true] as CFDictionary)
            let capture = CGPreflightScreenCaptureAccess() || CGRequestScreenCaptureAccess()
            respond(client, request, service.acceptance(request, data: [
                "accessibilityAuthorized": accessibility,
                "screenCaptureAuthorized": capture,
                "bundleIdentifier": Bundle.main.bundleIdentifier ?? NSNull(),
            ]), caller: caller, claimID: claimID)
            return
        }
        if operation == "browser.endpoint" {
            var data = browser.statusJSON
            data["devtoolsEndpoint"] = devtools.reconcile() ?? NSNull()
            respond(client, request, service.acceptance(request, data: data),
                    caller: caller, claimID: claimID)
            return
        }
        if [.scoped(.browser), .scoped(.devtools)].contains(operationClass(operation)) {
            if let refusal = browser.forward(client, request, caller: caller, claimID: claimID) {
                respond(client, request, refusal, caller: caller, claimID: claimID)
            } else {
                keepOpen = true
            }
            return
        }
        do {
            var response: [String: Any]
            if operation == "authorization.submit" {
                if let refusal = service.credentialPreflight(request) {
                    respond(client, request, refusal, caller: caller, claimID: claimID)
                    return
                }
                try writeSocket(client, data: Data([0x06]))
                var credential = try readSocket(client, limit: 257)
                defer {
                    credential.resetBytes(in: 0..<credential.count)
                    credential.removeAll(keepingCapacity: false)
                }
                response = service.handleCredential(request, credential: credential)
            } else {
                response = service.handle(request)
            }
            if operation == "input.key" || operation == "input.text",
               response["accepted"] as? Bool == true {
                // Untargeted keystrokes go wherever focus is; say where.
                var data = response["data"] as? [String: Any] ?? [:]
                data["keyboardReceiver"] = keyboardReceiver()
                response["data"] = data
            }
            if operation == "status" || operation == "capabilities",
               var data = response["data"] as? [String: Any] {
                data["deployment"] = broker.statusJSON
                data["lockedUse"] = lockedUse.status
                data["physicalActivity"] = activity.status
                data["admission"] = broker.admission.status
                data["admissionChannel"] = ["schema":AdmissionChannel.schema, "ownerBinding":"live_same_user_transport", "callerAssurance":"unverified_same_user", "delegatedAutomaticAccess":false, "outerRecovery":"borrowed_exact_claim/v1"]
                var browserStatus = browser.statusJSON
                browserStatus["devtoolsEndpoint"] = devtools.endpoint ?? NSNull()
                data["browser"] = browserStatus
                if updates.request(check: false) != nil {
                    data["updateDiscovery"] = ["operations": ["update.check", "update.status"],
                        "route": "desktop.native-updater", "installation": "local_operator_only"]
                }
                response["data"] = data
            }
            respond(client, request, response, caller: caller, claimID: claimID)
            if operation == "server.stop" {
                broker.journal?.event("resident.stop")
                lockedUse.end("resident_stopping")
                Darwin.close(listener)
                unlink(socketPath)
                exit(0)
            }
        } catch {
            respond(client, request, service.refusal(request, code: "operation_failed",
                message: String(describing: error)), caller: caller, claimID: claimID)
        }
    }

    /// Returns a response now, or nil when the client stays open for a
    /// decision.
    private func handleGrant(_ request: [String: Any], operation: String,
                             caller: CallerIdentity, client: Int32) -> [String: Any]? {
        switch operation {
        case "grant.status":
            return service.acceptance(request, data: broker.statusJSON)
        case "grant.revoke":
            let had = broker.grant != nil
            callerTrust.stop()
            broker.revoke(reason: "revoked_by_caller")
            if had { service.invalidateReferences() }
            var data = broker.statusJSON
            data["revoked"] = had
            return service.acceptance(request, data: data)
        case "grant.request":
            if broker.policy.grantMode == .standing {
                var data = broker.statusJSON
                data["decision"] = "standing"
                data["devtoolsEndpoint"] = devtools.reconcile() ?? NSNull()
                return service.acceptance(request, data: data)
            }
            let parsed: GrantRequest
            switch GrantRequest.parse(request, caller: caller) {
            case let .success(value): parsed = value
            case let .failure(refusal): return refused(request, refusal)
            }
            if let current = broker.covering(parsed) {
                var data = broker.statusJSON
                data["decision"] = "existing_grant"
                data["devtoolsEndpoint"] = devtools.reconcile() ?? NSNull()
                data["grant"] = current.json(now: broker.now())
                return service.acceptance(request, data: data)
            }
            if lockedUse.isCovered || !approvalDesktopUnlocked() {
                return refused(request, GrantRefusal("approval_unavailable_while_locked",
                    "Unlock manually before approving additional access"))
            }
            guard let approver else {
                return refused(request, GrantRefusal("approval_unavailable",
                    "No approval surface is running for this resident"))
            }
            if let refusal = broker.beginPending(parsed) { return refused(request, refusal) }
            pendingClient = client
            pendingRequest = request
            let timeout = DispatchWorkItem { [weak self] in self?.decide(.timedOut) }
            pendingTimeout = timeout
            DispatchQueue.main.asyncAfter(deadline: .now() + .seconds(parsed.timeoutSeconds),
                                          execute: timeout)
            approver.present(parsed) { [weak self] decision in self?.decide(decision) }
            return nil
        default:
            return refused(request, GrantRefusal("unsupported_operation",
                "Unsupported operation: \(operation)"))
        }
    }

    /// Ends the grant from a trusted local surface such as the menu.
    func revoke(reason: String) {
        if ["stopped_by_person", "revoked_by_caller"].contains(reason) { callerTrust.stop() }
        lockedUse.end(reason)
        broker.revoke(reason: reason)
        service.invalidateReferences()
    }

    private func decide(_ decision: GrantDecision) {
        guard let request = pendingRequest, let pending = broker.pending else { return }
        pendingTimeout?.cancel()
        pendingTimeout = nil
        approver?.dismiss(requestID: pending.id)
        let client = pendingClient
        pendingClient = -1
        pendingRequest = nil
        let grant = broker.finishPending(decision, approver: approver?.kind ?? "unknown")
        let response: [String: Any]
        if let grant {
            var data = broker.statusJSON
            data["decision"] = "approved"
            data["devtoolsEndpoint"] = devtools.reconcile() ?? NSNull()
            data["grant"] = grant.json(now: broker.now())
            response = service.acceptance(request, data: data)
        } else if decision == .timedOut {
            response = refused(request, GrantRefusal("approval_timeout",
                "No decision was made before the request timed out"))
        } else {
            response = refused(request, GrantRefusal("approval_denied",
                "The request was denied"))
        }
        respond(client, request, response, caller: pending.caller, claimID: pending.claimID)
        Darwin.close(client)
    }

    private func refused(_ request: [String: Any], _ refusal: GrantRefusal) -> [String: Any] {
        var data = broker.statusJSON
        if let scope = refusal.requiredScope {
            data["requiredScope"] = scope.rawValue
            data["requestOperation"] = "grant.request"
        }
        return service.refusal(request, code: refusal.code, message: refusal.message, data: data)
    }

    private func respond(_ client: Int32, _ request: [String: Any], _ originalResponse: [String: Any],
                         caller: CallerIdentity, claimID: String?) {
        var response = originalResponse
        if broker.journal?.record(response) == false {
            response["accepted"] = false; response["errorCode"] = "audit_storage_unavailable"
            response["uncertainty"] = "audit_result_not_persisted"; response["retrySafety"] = "unsafe"
        }
        let operation = request["operation"] as? String ?? "unknown"
        if operationClass(operation) != .discovery && operation != "grant.status" {
            var detail: String?
            if operation == "browser.upload", let files = request["files"] as? [String] {
                detail = files.map { ($0 as NSString).lastPathComponent }.joined(separator: ", ")
            } else if operation == "browser.cdp" {
                detail = (request["method"] as? String).map { String($0.prefix(80)) }
            } else if operation == "browser.eval" {
                detail = "Runtime.evaluate"
            }
            broker.record(operation: operation, accepted: response["accepted"] as? Bool == true,
                          errorCode: response["errorCode"] as? String, caller: caller,
                          claimID: claimID, detail: detail)
        }
        try? writeSocket(client, data: encodeJSONLine(response))
    }
}

/// Accepts `cmd+shift+g` as well as the resident's `cmd-shift-g`.
func normalizedKeyChord(_ chord: String) -> String {
    guard chord.count > 1, chord.contains("+") else { return chord }
    var parts = chord.split(separator: "+", omittingEmptySubsequences: false).map(String.init)
    // A trailing empty part means the key itself is "+".
    if parts.last == "" { parts.removeLast(); parts[parts.count - 1] += "+" }
    return parts.joined(separator: "-")
}

/// The application, window, and element that currently receive keystrokes.
func keyboardReceiver() -> [String: Any] {
    guard let app = NSWorkspace.shared.frontmostApplication else { return ["application": NSNull()] }
    var receiver: [String: Any] = [
        "application": app.localizedName ?? NSNull(),
        "bundleIdentifier": app.bundleIdentifier ?? NSNull(),
        "processId": app.processIdentifier,
    ]
    let root = AXUIElementCreateApplication(app.processIdentifier)
    if let window = attribute(root, kAXFocusedWindowAttribute as CFString) {
        receiver["window"] = stringAttribute(window as! AXUIElement, kAXTitleAttribute as CFString)
    }
    if let focused = attribute(root, kAXFocusedUIElementAttribute as CFString) {
        let element = focused as! AXUIElement
        receiver["focusedRole"] = stringAttribute(element, kAXRoleAttribute as CFString)
        let label = stringAttribute(element, kAXTitleAttribute as CFString)
        receiver["focusedLabel"] = label.isEmpty ?
            stringAttribute(element, kAXDescriptionAttribute as CFString) : label
    }
    return receiver
}

let residentLabel = "org.machine-control.resident"
let defaultResidentSocket = FileManager.default.homeDirectoryForCurrentUser
    .appendingPathComponent("Library/Application Support/MachineControl/control.sock").path

/// Opening the bundle directly starts the installed LaunchAgent, which owns
/// the resident's lifetime; without one the app serves the default socket.
func openedAsApplication() -> Never {
    let agent = FileManager.default.homeDirectoryForCurrentUser
        .appendingPathComponent("Library/LaunchAgents/\(residentLabel).plist").path
    if FileManager.default.fileExists(atPath: agent) {
        let domain = "gui/\(getuid())"
        for arguments in [["bootstrap", domain, agent], ["kickstart", "\(domain)/\(residentLabel)"]] {
            let launchctl = Process()
            launchctl.executableURL = URL(fileURLWithPath: "/bin/launchctl")
            launchctl.arguments = arguments
            launchctl.standardOutput = FileHandle.nullDevice
            launchctl.standardError = FileHandle.nullDevice
            try? launchctl.run()
            launchctl.waitUntilExit()
        }
        exit(0)
    }
    try? FileManager.default.createDirectory(
        atPath: (defaultResidentSocket as NSString).deletingLastPathComponent,
        withIntermediateDirectories: true, attributes: [.posixPermissions: 0o700])
    do {
        try runResident(socketPath: defaultResidentSocket)
    } catch {
        fail(error)
    }
}

/// Starts the resident under the trusted deployment policy and runs the
/// application event loop.
func runResident(socketPath: String) throws -> Never {
    // A server never wants a stray write to a closed peer to kill it.
    signal(SIGPIPE, SIG_IGN)
    let broker = GrantBroker(policy: DeploymentPolicy.load())
    broker.journal = DesktopJournal()
    try FileManager.default.createDirectory(atPath:(socketPath as NSString).deletingLastPathComponent,
        withIntermediateDirectories:true, attributes:[.posixPermissions:0o700])
    if broker.policy.grantMode == .approval { attachOperatorConsent(broker, socketPath:socketPath) }
    let server = ResidentServer(socketPath: socketPath, service: ResidentService(),
                                broker: broker)
    try server.start()
    server.devtools.start()
    let application = NSApplication.shared
    application.setActivationPolicy(.accessory)
    server.notice = AdmissionNotice(server:server)
    // Inner appliance input does not reserve or observe the controller desktop.
    if broker.policy.grantMode == .approval { server.activity.enable() }
    let approval = ApprovalPanelController()
    let setup = SetupWindowController()
    setup.browserConnected = { [weak server] in server?.browser.connected == true }
    let menu = StatusMenuController(broker: broker, approval: approval, setup: setup)
    menu.onRevoke = { [weak server] reason in server?.revoke(reason: reason) }
    menu.onResume = { [weak server] in
        try server?.service.resumeCoveredAvailability()
        try server?.broker.resume()
    }
    menu.onArm = { [weak server] duration in
        guard let server else { return }
        guard server.broker.consentStorageError == nil else { throw MacUIError.action("consent_storage_unavailable") }
        try server.broker.consentStore?.enable(scopes:Set(GrantScope.allCases), duration:duration,
            console:server.grantConsoleObservation())
        if let duration { server.broker.issue(scopes:Set(GrantScope.allCases), durationSeconds:duration,
            reason:"Armed from the menu bar", requester:"local operator", approver:"menu") }
        else { server.broker.issueUntilStopped(scopes:Set(GrantScope.allCases),
            reason:"Armed from the menu bar", requester:"local operator", approver:"menu") }
        if server.broker.journal?.errorCode != nil { server.revoke(reason:"audit_storage_unavailable") }
    }

    broker.observe { [weak menu] in menu?.updateIcon() }
    approval.onChange = { [weak menu] in menu?.updateIcon() }
    if broker.policy.grantMode == .approval {
        server.approver = approval
    }
    let processID = ProcessInfo.processInfo.processIdentifier
    let identifiers = Set([Bundle.main.bundleIdentifier, Bundle.main.infoDictionary?["CFBundleName"] as? String,
                           ProcessInfo.processInfo.processName].compactMap { $0?.lowercased() })
    server.guardRequest = { [weak server, weak menu] request in
        let own = OwnInterface(processID: processID, identifiers: identifiers,
                               windowFrames: ownWindowFrames(processID,
                                                             extra: menu?.interfaceWindows ?? [],
                                                             excluding: server?.lockedUse.coveredWindowIDs ?? []),
                               hasKeyWindow: NSApp.keyWindow != nil,
                               menuOpen: menu?.menuOpen == true,
                               pointer: CGEvent(source: nil)?.location)
        let reference = (request["reference"] as? String).flatMap { server?.service.referencedProcess($0) }
        return selfTargetRefusal(request, own: own, referencedProcess: reference)
    }
    // A personal Mac opens the checklist while macOS permissions are
    // missing; a restart for a new grant reopens it to show the result.
    let reopen = UserDefaults.standard.bool(forKey: SetupWindowController.reopenKey)
    UserDefaults.standard.removeObject(forKey: SetupWindowController.reopenKey)
    setup.refresh()
    if reopen {
        // Back after a restart for a new grant: show the result without
        // taking focus from System Settings.
        DispatchQueue.main.async { setup.show(activate: false, restarted: true) }
    } else if broker.policy.grantMode == .approval && !setup.state.complete {
        DispatchQueue.main.async { setup.show() }
    }
    withExtendedLifetime((server, menu, approval, setup)) { application.run() }
    exit(0)
}

/// On-screen windows owned by this process, in global display points. The
/// window server list can omit some system-hosted windows such as status
/// items, so AppKit's own windows are included as well.
func ownWindowFrames(_ processID: pid_t, extra: [NSWindow] = [], excluding: Set<Int> = []) -> [CGRect] {
    let listed = (CGWindowListCopyWindowInfo([.optionOnScreenOnly], kCGNullWindowID)
        as? [[String: Any]] ?? []).compactMap { window -> CGRect? in
        guard (window[kCGWindowOwnerPID as String] as? NSNumber)?.int32Value == processID,
              !excluding.contains((window[kCGWindowNumber as String] as? NSNumber)?.intValue ?? -1),
              let bounds = window[kCGWindowBounds as String] as? NSDictionary else { return nil }
        return CGRect(dictionaryRepresentation: bounds)
    }
    let primaryHeight = NSScreen.screens.first?.frame.height ?? 0
    let drawn = (NSApp.windows + extra).filter { $0.isVisible && !excluding.contains($0.windowNumber) }.map { window -> CGRect in
        let frame = window.frame
        return CGRect(x: frame.minX, y: primaryHeight - frame.maxY,
                      width: frame.width, height: frame.height)
    }
    return listed + drawn
}

/// Byte transport only. Liveness and activation belong to the client runtime;
/// EOF on either direction promptly closes the owning resident connection.
func runAdmissionProxy(socketPath: String) throws {
    let fd = try residentSocket(); defer { Darwin.close(fd) }
    var (address, length) = try unixAddress(socketPath)
    guard withSockAddr(&address, length:length, { Darwin.connect(fd, $0, $1) }) == 0 else { throw MacUIError.action("resident_unavailable") }
    var uid: uid_t = 0, gid: gid_t = 0
    guard getpeereid(fd, &uid, &gid) == 0, uid == getuid(), uid != 0 else { throw MacUIError.permission("same_user_resident_required") }
    var timeout = timeval(tv_sec:5, tv_usec:0)
    setsockopt(fd, SOL_SOCKET, SO_SNDTIMEO, &timeout, socklen_t(MemoryLayout.size(ofValue:timeout)))
    let parent = getppid()
    var bytes = [UInt8](repeating:0, count:16384)
    while getppid() == parent {
        var descriptors = [pollfd(fd:STDIN_FILENO, events:Int16(POLLIN | POLLHUP), revents:0),
            pollfd(fd:fd, events:Int16(POLLIN | POLLHUP), revents:0)]
        if poll(&descriptors, 2, 1000) < 0 { if errno == EINTR { continue }; return }
        for index in 0...1 where descriptors[index].revents != 0 {
            let count = Darwin.read(descriptors[index].fd, &bytes, bytes.count)
            if count <= 0 { return }
            let data = Data(bytes.prefix(count))
            if index == 0 { try writeSocket(fd, data:data) }
            else { FileHandle.standardOutput.write(data) }
        }
    }
}

func runResidentClient(socketPath: String, requestData: Data) throws {
    let descriptor = try residentSocket()
    defer { Darwin.close(descriptor) }
    var (address, length) = try unixAddress(socketPath)
    guard withSockAddr(&address, length: length, {
        Darwin.connect(descriptor, $0, $1)
    }) == 0 else {
        throw MacUIError.action("Resident service is unavailable")
    }
    var uid: uid_t = 0; var gid: gid_t = 0
    guard getpeereid(descriptor, &uid, &gid) == 0, uid == getuid(), uid != 0 else {
        // Generic CLI JSON must never become a proxy through the pinned
        // resident executable into its root protected broker.
        throw MacUIError.permission("The client requires a same-user resident endpoint")
    }
    var line = requestData
    if line.last != 0x0a { line.append(0x0a) }
    try writeSocket(descriptor, data: line)
    let request = (try? JSONSerialization.jsonObject(with:requestData)) as? [String:Any]
    if request?["operation"] as? String == "session.control" {
        let initial = try readSocket(descriptor)
        let response = (try? JSONSerialization.jsonObject(with:initial)) as? [String:Any]
        guard response?["accepted"] as? Bool == true else {
            FileHandle.standardOutput.write(initial); return
        }
        let parent = getppid()
        while getppid() == parent {
            var connection = pollfd(fd:descriptor, events:Int16(POLLIN | POLLHUP), revents:0)
            if poll(&connection, 1, 1000) > 0 {
                let final = try readSocket(descriptor)
                if !final.isEmpty { FileHandle.standardOutput.write(final) }
                return
            }
            // A dropped transport must not leave a guest-side heartbeat owner.
            var output = pollfd(fd:STDOUT_FILENO, events:Int16(POLLOUT), revents:0)
            _ = poll(&output, 1, 0)
            if output.revents & Int16(POLLHUP | POLLERR | POLLNVAL) != 0 { return }
            try writeSocket(descriptor, data:encodeJSONLine(["operation":"heartbeat"]))
        }
        return
    }
    _ = Darwin.shutdown(descriptor, SHUT_WR)
    let response = try readSocket(descriptor)
    FileHandle.standardOutput.write(response)
}

func runCredentialClient(socketPath: String, leaseID: String) throws {
    var credential = FileHandle.standardInput.readDataToEndOfFile()
    defer {
        credential.resetBytes(in: 0..<credential.count)
        credential.removeAll(keepingCapacity: false)
    }
    while credential.last == 0x0a || credential.last == 0x0d {
        credential.removeLast()
    }
    guard !credential.isEmpty, credential.count <= 256 else {
        throw MacUIError.usage("Credential must contain 1 through 256 bytes")
    }

    let descriptor = try residentSocket()
    defer { Darwin.close(descriptor) }
    var (address, length) = try unixAddress(socketPath)
    guard withSockAddr(&address, length: length, {
        Darwin.connect(descriptor, $0, $1)
    }) == 0 else {
        throw MacUIError.action("Resident service is unavailable")
    }
    let request: [String: Any] = [
        "schema": "machine-control/v0",
        "requestId": UUID().uuidString.lowercased(),
        "operation": "authorization.submit",
        "leaseId": leaseID,
    ]
    try writeSocket(descriptor, data: encodeJSONLine(request))
    var acknowledgment: UInt8 = 0
    var count: Int
    repeat {
        count = Darwin.read(descriptor, &acknowledgment, 1)
    } while count < 0 && errno == EINTR
    guard count == 1, acknowledgment == 0x06 else {
        throw MacUIError.action(
            "Resident did not accept the credential channel handshake")
    }
    try writeSocket(descriptor, data: credential)
    _ = Darwin.shutdown(descriptor, SHUT_WR)
    let response = try readSocket(descriptor)
    FileHandle.standardOutput.write(response)
}
