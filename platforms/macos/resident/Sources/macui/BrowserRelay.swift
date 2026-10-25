import Darwin
import Foundation
import Security

/// Whether a socket peer is signed with this resident's own designated
/// requirement. With ad-hoc development signing that requirement is only an
/// identifier; release builds bind it to the publisher.
func peerHasOwnCodeIdentity(_ descriptor: Int32) -> Bool {
    var token = audit_token_t()
    var length = socklen_t(MemoryLayout<audit_token_t>.size)
    guard getsockopt(descriptor, SOL_LOCAL, LOCAL_PEERTOKEN, &token, &length) == 0 else {
        return false
    }
    let tokenData = withUnsafeBytes(of: &token) { Data($0) }
    var guest: SecCode?
    guard SecCodeCopyGuestWithAttributes(nil, [kSecGuestAttributeAudit: tokenData] as CFDictionary,
                                         [], &guest) == errSecSuccess, let guest,
          let requirement = ownDesignatedRequirement() else { return false }
    return SecCodeCheckValidity(guest, [], requirement) == errSecSuccess
}

private func ownDesignatedRequirement() -> SecRequirement? {
    var own: SecCode?
    var ownStatic: SecStaticCode?
    var requirement: SecRequirement?
    guard SecCodeCopySelf([], &own) == errSecSuccess, let own,
          SecCodeCopyStaticCode(own, [], &ownStatic) == errSecSuccess, let ownStatic,
          SecCodeCopyDesignatedRequirement(ownStatic, [], &requirement) == errSecSuccess else {
        return nil
    }
    return requirement
}

/// Checks files an agent asks to upload. Uploading sends a local file to a
/// website, so only named, readable regular files outside hidden directories
/// and the user's Library qualify; symbolic links are resolved first.
func validatedUploadFiles(_ value: Any?, home: String = NSHomeDirectory())
    -> Result<[String], GrantRefusal> {
    guard let names = value as? [String], (1...20).contains(names.count) else {
        return .failure(GrantRefusal("invalid_request", "files must list 1 to 20 absolute paths"))
    }
    let library = ((home as NSString).appendingPathComponent("Library") as NSString)
        .resolvingSymlinksInPath
    var resolved: [String] = []
    for name in names {
        guard name.hasPrefix("/") else {
            return .failure(GrantRefusal("invalid_request", "Upload paths must be absolute: \(name)"))
        }
        let path = (name as NSString).resolvingSymlinksInPath
        var isDirectory: ObjCBool = false
        guard FileManager.default.fileExists(atPath: path, isDirectory: &isDirectory),
              !isDirectory.boolValue, FileManager.default.isReadableFile(atPath: path) else {
            return .failure(GrantRefusal("upload_file_unavailable", "Not a readable file: \(name)"))
        }
        if path.split(separator: "/").contains(where: { $0.hasPrefix(".") }) ||
            path == library || path.hasPrefix(library + "/") {
            return .failure(GrantRefusal("upload_path_not_permitted",
                "Files in hidden folders or ~/Library are not uploaded: \(name)"))
        }
        resolved.append(path)
    }
    return .success(resolved)
}

/// Relays browser operations to the Machine Control Chrome extension through
/// its native-messaging host. The resident has already checked the grant;
/// the extension only executes.
final class BrowserRelay {
    static let route = "chrome.extension/cdp"
    static let timeoutSeconds = 45

    struct Pending {
        let client: Int32
        let request: [String: Any]
        let caller: CallerIdentity
        let claimID: String?
        let timeout: DispatchWorkItem
        let completion: (([String:Any]) -> Void)?
    }

    let service: ResidentService
    let broker: GrantBroker
    var identityCheck: (Int32) -> Bool = peerHasOwnCodeIdentity
    var requestTimeout: TimeInterval = TimeInterval(BrowserRelay.timeoutSeconds)
    var respond: ((Int32, [String: Any], [String: Any], CallerIdentity, String?) -> Void)?

    private var provider: Int32 = -1
    private var source: DispatchSourceRead?
    private var buffer = Data()
    private var pending: [String: Pending] = [:]
    private var sessions: [String: DevToolsSession] = [:]
    private(set) var hello: [String: Any]?
    private var lastSuccess: Date?
    private var consecutiveTimeouts = 0
    private var providerBlockedTabs = 0
    private var providerOpenDialogs = 0
    private let bufferLimit = 48 * 1_048_576

    init(service: ResidentService, broker: GrantBroker) {
        self.service = service
        self.broker = broker
        broker.observe { [weak self] in self?.sendGrantState() }
    }

    var connected: Bool { provider >= 0 }

    var statusJSON: [String: Any] {
        ["connected": connected,
         "route": BrowserRelay.route,
         "extensionVersion": hello?["extensionVersion"] ?? NSNull(),
         "health":!connected ? "unavailable" : consecutiveTimeouts > 0 || providerBlockedTabs > 0 ? "degraded" : lastSuccess == nil ? "connected_unverified" : "ready",
         "consecutiveTimeouts":consecutiveTimeouts,
         "blockedTabs":providerBlockedTabs, "openDialogs":providerOpenDialogs,
         "pendingRequests":pending.count,
         "lastSuccessAt":lastSuccess.map { ISO8601DateFormatter().string(from:$0) } as Any? ?? NSNull()]
    }

    /// Adopts a native-messaging host connection. Returns a refusal to send
    /// and close, or nil when the connection now belongs to the relay.
    func register(_ client: Int32, _ request: [String: Any]) -> [String: Any]? {
        guard identityCheck(client) else {
            return service.refusal(request, code: "browser_provider_untrusted",
                message: "Only this application's own native-messaging host may provide browser access")
        }
        disconnect(reason: "browser_provider_replaced")
        var noTimeout = timeval(tv_sec: 0, tv_usec: 0)
        setsockopt(client, SOL_SOCKET, SO_RCVTIMEO, &noTimeout,
                   socklen_t(MemoryLayout.size(ofValue: noTimeout)))
        provider = client
        lastSuccess = nil; consecutiveTimeouts = 0; providerBlockedTabs = 0; providerOpenDialogs = 0
        buffer.removeAll()
        let source = DispatchSource.makeReadSource(fileDescriptor: client, queue: .main)
        source.setEventHandler { [weak self] in self?.readable() }
        source.resume()
        self.source = source
        write(["type": "registered", "protocolVersion": 1])
        sendGrantState()
        return nil
    }

    /// Forwards an authorized browser request. Returns a refusal, or nil when
    /// the client stays open for the extension's answer.
    func forward(_ client: Int32, _ request: [String: Any], caller: CallerIdentity,
                 claimID: String?, completion: (([String:Any]) -> Void)? = nil) -> [String: Any]? {
        guard connected else {
            return routed(service.refusal(request, code: "browser_provider_unavailable",
                message: "The Machine Control Chrome extension is not connected"))
        }
        let supplied = request["timeoutMs"] as? Int
        if request["operation"] as? String != "browser.wait", let supplied, !(100...45000).contains(supplied) {
            return routed(service.refusal(request, code:"invalid_request", message:"Browser timeout must be 100-45000 ms"))
        }
        let budget = min(requestTimeout, supplied.map { Double($0) / 1000 } ?? requestTimeout)
        var params = request
        if request["operation"] as? String == "browser.upload" {
            switch validatedUploadFiles(request["files"]) {
            case let .success(files): params["files"] = files
            case let .failure(refusal):
                return routed(service.refusal(request, code: refusal.code, message: refusal.message))
            }
        }
        let id = UUID().uuidString.lowercased()
        for key in ["operation", "requestId", "claimId", "schema"] { params.removeValue(forKey: key) }
        let timeout = DispatchWorkItem { [weak self] in
            self?.write(["type":"cancel", "id":id])
            self?.complete(id, ["ok": false, "errorCode": "browser_timeout",
                                "delivery":"unknown", "message": "The browser did not answer in time; dispatched effects are unknown"])
        }
        pending[id] = Pending(client: client, request: request, caller: caller,
                              claimID: claimID, timeout: timeout, completion:completion)
        DispatchQueue.main.asyncAfter(deadline: .now() + budget,
                                      execute: timeout)
        write(["type": "request", "id": id,
               "timeoutMs":max(100, min(30000, Int(budget * 1000) - 100)),
               "operation": request["operation"] as? String ?? "", "params": params])
        return nil
    }

    /// Opens a raw DevTools session on a tab for `handler`. The extension
    /// attaches the debugger and forwards that tab's events.
    func openSession(tabId: Int, handler: DevToolsSession) -> String {
        let id = UUID().uuidString.lowercased()
        sessions[id] = handler
        write(["type": "session.open", "id": id, "tabId": tabId])
        return id
    }

    func sendSessionCommand(_ id: String, cmdId: Int, method: String, params: [String: Any],
                            childSession: String? = nil) {
        var frame: [String: Any] = ["type": "session.command", "id": id, "cmdId": cmdId,
                                 "method": method, "params": params]
        if let childSession { frame["sessionId"] = childSession }
        write(frame)
    }

    func closeSession(_ id: String) {
        guard sessions.removeValue(forKey: id) != nil else { return }
        write(["type": "session.close", "id": id])
    }

    /// Ends every open session, for grant loss or provider disconnect.
    func closeAllSessions(reason: String) {
        for (id, handler) in sessions { handler.sessionClosed(reason) ; _ = id }
        sessions.removeAll()
    }

    private func sendGrantState() {
        guard connected else { return }
        let devtools = broker.devtoolsAllowed
        let browser = broker.browserAllowed || devtools
        let grantGeneration = service.generation + ":" + (broker.grant?.id ?? "none")
        write(["type": "grant", "browser": browser, "devtools": devtools,
               "grantGeneration": grantGeneration])
    }

    private func write(_ message: [String: Any]) {
        guard connected, let line = try? encodeJSONLine(message) else { return }
        if (try? writeSocket(provider, data: line)) == nil {
            disconnect(reason: "browser_provider_disconnected")
        }
    }

    private func readable() {
        var chunk = [UInt8](repeating: 0, count: 65_536)
        let count = Darwin.read(provider, &chunk, chunk.count)
        guard count > 0 else {
            if count < 0 && errno == EINTR { return }
            disconnect(reason: "browser_provider_disconnected")
            return
        }
        buffer.append(chunk, count: count)
        guard buffer.count <= bufferLimit else {
            disconnect(reason: "browser_message_too_large")
            return
        }
        while let newline = buffer.firstIndex(of: 0x0a) {
            let line = buffer[buffer.startIndex..<newline]
            buffer.removeSubrange(buffer.startIndex...newline)
            guard let message = try? JSONSerialization.jsonObject(with: Data(line)) as? [String: Any] else {
                continue
            }
            switch message["type"] as? String {
            case "hello": hello = message
            case "response":
                if let id = message["id"] as? String { complete(id, message) }
            case "session.opened":
                if let id = message["id"] as? String { sessions[id]?.sessionOpened() }
            case "session.failed":
                if let id = message["id"] as? String {
                    sessions[id]?.sessionClosed(message["message"] as? String ?? "session_failed")
                    sessions.removeValue(forKey: id)
                }
            case "session.result":
                if let id = message["id"] as? String { sessions[id]?.sessionResult(message) }
            case "session.event":
                if let id = message["id"] as? String { sessions[id]?.sessionEvent(message) }
            case "session.closed":
                if let id = message["id"] as? String {
                    sessions[id]?.sessionClosed(message["reason"] as? String ?? "closed")
                    sessions.removeValue(forKey: id)
                }
            default: break
            }
        }
    }

    private func disconnect(reason: String) {
        source?.cancel()
        source = nil
        if provider >= 0 { Darwin.close(provider) }
        provider = -1
        hello = nil
        closeAllSessions(reason: "browser_provider_disconnected")
        for id in Array(pending.keys) {
            complete(id, ["ok": false, "errorCode": reason,
                          "delivery":"unknown",
                          "message": "The browser provider disconnected"])
        }
    }

    private func complete(_ id: String, _ message: [String: Any]) {
        guard let entry = pending.removeValue(forKey: id) else { return }
        entry.timeout.cancel()
        if let health = message["health"] as? [String:Any] {
            providerBlockedTabs = max(0, min(256, health["blockedTabs"] as? Int ?? 0))
            providerOpenDialogs = max(0, min(256, health["openDialogs"] as? Int ?? 0))
        }
        if message["errorCode"] as? String == "browser_timeout" { consecutiveTimeouts += 1 }
        if message["ok"] as? Bool == true { lastSuccess = Date(); consecutiveTimeouts = 0 }
        var response = message["ok"] as? Bool == true ?
            accepted(entry.request, data: message["data"] as? [String: Any] ?? [:]) :
            routed(service.refusal(entry.request,
                code: message["errorCode"] as? String ?? "browser_operation_failed",
                message: message["message"] as? String ?? "Browser operation failed"))
        if message["ok"] as? Bool != true && message["delivery"] as? String == "unknown" {
            response["delivery"] = "unknown"; response["effect"] = "unknown"
            response["uncertainty"] = "browser_command_may_have_executed"
        }
        if let completion = entry.completion { completion(response) }
        else { respond?(entry.client, entry.request, response, entry.caller, entry.claimID); Darwin.close(entry.client) }
    }

    private func accepted(_ request: [String: Any], data: [String: Any]) -> [String: Any] {
        let operation = request["operation"] as? String ?? ""
        var data = data
        if operation == "browser.capture", let encoded = data.removeValue(forKey: "png") as? String {
            guard let png = Data(base64Encoded: encoded), let url = try? service.artifactURL(),
                  (try? png.write(to: url, options: .atomic)) != nil else {
                return routed(service.refusal(request, code: "artifact_failed",
                    message: "The browser capture could not be stored"))
            }
            data["artifactPath"] = url.path
            data["bytes"] = png.count
        }
        var result = routed(service.acceptance(request, data: data))
        switch operation {
        case "browser.cdp", "browser.eval":
            result["delivery"] = "confirmed"
            result["effect"] = "unverifiable"
            result["uncertainty"] = "raw_protocol_effect_not_observed"
        case "browser.upload":
            result["delivery"] = "confirmed"
            result["effect"] = "unverifiable"
            result["uncertainty"] = "page_acceptance_not_observed"
        case "browser.click", "browser.type", "browser.key":
            result["delivery"] = "confirmed"
            result["effect"] = "unverifiable"
            result["uncertainty"] = "no_independent_state_change"
        case "browser.navigate":
            let loaded = data["loaded"] as? Bool == true
            result["delivery"] = "confirmed"
            result["effect"] = loaded ? "confirmed" : "unknown"
            result["uncertainty"] = loaded ? "none" : "load_not_observed"
        case "browser.capture":
            result["delivery"] = "confirmed"
            result["effect"] = "confirmed"
            result["fidelity"] = "browser_viewport"
        default:
            break
        }
        return result
    }

    private func routed(_ result: [String: Any]) -> [String: Any] {
        var result = result
        result["actualRoute"] = BrowserRelay.route
        return result
    }
}
