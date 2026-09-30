import AppKit
import Darwin
import Foundation

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
    private var lastDesktopState: String?

    init(socketPath: String, service: ResidentService, broker: GrantBroker) {
        self.socketPath = socketPath
        self.service = service
        self.broker = broker
    }

    func start() throws {
        let descriptor = socket(AF_UNIX, SOCK_STREAM, 0)
        guard descriptor >= 0 else { throw MacUIError.action("Unable to create Unix socket") }
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
    }

    private func tick() {
        autoreleasepool { service.refreshSession() }
        let state = service.observedDesktopState
        // Leaving an unlocked desktop ends an approved grant: the person
        // who approved it may no longer be present.
        if lastDesktopState == "unlocked", state != "unlocked",
           broker.policy.grantMode == .approval, broker.grant != nil {
            broker.revoke(reason: "desktop_\(state)")
            service.invalidateReferences()
        }
        lastDesktopState = state
        _ = broker.activeGrant
    }

    private func acceptPending() {
        let client = accept(listener, nil, nil)
        guard client >= 0 else { return }
        // A stalled client must not wedge the single-threaded resident.
        var timeout = timeval(tv_sec: 5, tv_usec: 0)
        setsockopt(client, SOL_SOCKET, SO_RCVTIMEO, &timeout,
                   socklen_t(MemoryLayout.size(ofValue: timeout)))
        setsockopt(client, SOL_SOCKET, SO_SNDTIMEO, &timeout,
                   socklen_t(MemoryLayout.size(ofValue: timeout)))
        var noSignal: Int32 = 1
        setsockopt(client, SOL_SOCKET, SO_NOSIGPIPE, &noSignal,
                   socklen_t(MemoryLayout.size(ofValue: noSignal)))
        autoreleasepool { serve(client) }
    }

    private func serve(_ client: Int32) {
        var keepOpen = false
        defer { if !keepOpen { Darwin.close(client) } }
        var request: [String: Any] = [:]
        do {
            let data = try readSocket(client)
            guard let object = try JSONSerialization.jsonObject(with: data) as? [String: Any] else {
                throw MacUIError.usage("Request must be a JSON object")
            }
            request = object
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
        let caller = CallerIdentity.of(socket: client)
        let claimID = request["claimId"] as? String

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
        if broker.policy.grantMode == .approval, case let .scoped(scope) = operationClass(operation),
           scope != .observe, let refusal = guardRequest?(request) {
            respond(client, request, refused(request, refusal), caller: caller, claimID: claimID)
            return
        }
        do {
            var response: [String: Any]
            if operation == "authorization.submit" {
                if let refusal = service.credentialPreflight(request) {
                    try writeSocket(client, data: encodeJSONLine(refusal))
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
            if operation == "status" || operation == "capabilities",
               var data = response["data"] as? [String: Any] {
                data["deployment"] = broker.statusJSON
                response["data"] = data
            }
            respond(client, request, response, caller: caller, claimID: claimID)
            if operation == "server.stop" {
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
            broker.revoke(reason: "revoked_by_caller")
            if had { service.invalidateReferences() }
            var data = broker.statusJSON
            data["revoked"] = had
            return service.acceptance(request, data: data)
        case "grant.request":
            if broker.policy.grantMode == .standing {
                var data = broker.statusJSON
                data["decision"] = "standing"
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
                data["grant"] = current.json(now: broker.now())
                return service.acceptance(request, data: data)
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
        guard broker.grant != nil else { return }
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

    private func respond(_ client: Int32, _ request: [String: Any], _ response: [String: Any],
                         caller: CallerIdentity, claimID: String?) {
        let operation = request["operation"] as? String ?? "unknown"
        if operationClass(operation) != .discovery && operation != "grant.status" {
            broker.record(operation: operation, accepted: response["accepted"] as? Bool == true,
                          errorCode: response["errorCode"] as? String, caller: caller,
                          claimID: claimID)
        }
        try? writeSocket(client, data: encodeJSONLine(response))
    }
}

/// Starts the resident under the trusted deployment policy and runs the
/// application event loop.
func runResident(socketPath: String) throws -> Never {
    let broker = GrantBroker(policy: DeploymentPolicy.load())
    let server = ResidentServer(socketPath: socketPath, service: ResidentService(),
                                broker: broker)
    try server.start()
    let application = NSApplication.shared
    application.setActivationPolicy(.accessory)
    let approval = ApprovalPanelController()
    let menu = StatusMenuController(broker: broker, approval: approval)
    menu.onRevoke = { [weak server] reason in server?.revoke(reason: reason) }
    broker.onChange = { [weak menu] in menu?.updateIcon() }
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
                                                             extra: menu?.interfaceWindows ?? []),
                               hasKeyWindow: NSApp.keyWindow != nil,
                               menuOpen: menu?.menuOpen == true,
                               pointer: CGEvent(source: nil)?.location)
        let reference = (request["reference"] as? String).flatMap { server?.service.referencedProcess($0) }
        return selfTargetRefusal(request, own: own, referencedProcess: reference)
    }
    withExtendedLifetime((server, menu, approval)) { application.run() }
    exit(0)
}

/// On-screen windows owned by this process, in global display points. The
/// window server list can omit some system-hosted windows such as status
/// items, so AppKit's own windows are included as well.
func ownWindowFrames(_ processID: pid_t, extra: [NSWindow] = []) -> [CGRect] {
    let listed = (CGWindowListCopyWindowInfo([.optionOnScreenOnly], kCGNullWindowID)
        as? [[String: Any]] ?? []).compactMap { window -> CGRect? in
        guard (window[kCGWindowOwnerPID as String] as? NSNumber)?.int32Value == processID,
              let bounds = window[kCGWindowBounds as String] as? NSDictionary else { return nil }
        return CGRect(dictionaryRepresentation: bounds)
    }
    let primaryHeight = NSScreen.screens.first?.frame.height ?? 0
    let drawn = (NSApp.windows + extra).filter(\.isVisible).map { window -> CGRect in
        let frame = window.frame
        return CGRect(x: frame.minX, y: primaryHeight - frame.maxY,
                      width: frame.width, height: frame.height)
    }
    return listed + drawn
}

func runResidentClient(socketPath: String, requestData: Data) throws {
    let descriptor = socket(AF_UNIX, SOCK_STREAM, 0)
    guard descriptor >= 0 else { throw MacUIError.action("Unable to create Unix socket") }
    defer { Darwin.close(descriptor) }
    var (address, length) = try unixAddress(socketPath)
    guard withSockAddr(&address, length: length, {
        Darwin.connect(descriptor, $0, $1)
    }) == 0 else {
        throw MacUIError.action("Resident service is unavailable")
    }
    var line = requestData
    if line.last != 0x0a { line.append(0x0a) }
    try writeSocket(descriptor, data: line)
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

    let descriptor = socket(AF_UNIX, SOCK_STREAM, 0)
    guard descriptor >= 0 else {
        throw MacUIError.action("Unable to create Unix socket")
    }
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
