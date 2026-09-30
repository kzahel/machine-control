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
    }

    let service: ResidentService
    let broker: GrantBroker
    var identityCheck: (Int32) -> Bool = peerHasOwnCodeIdentity
    var respond: ((Int32, [String: Any], [String: Any], CallerIdentity, String?) -> Void)?

    private var provider: Int32 = -1
    private var source: DispatchSourceRead?
    private var buffer = Data()
    private var pending: [String: Pending] = [:]
    private(set) var hello: [String: Any]?
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
         "extensionVersion": hello?["extensionVersion"] ?? NSNull()]
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
                 claimID: String?) -> [String: Any]? {
        guard connected else {
            return routed(service.refusal(request, code: "browser_provider_unavailable",
                message: "The Machine Control Chrome extension is not connected"))
        }
        let id = UUID().uuidString.lowercased()
        var params = request
        for key in ["operation", "requestId", "claimId", "schema"] { params.removeValue(forKey: key) }
        let timeout = DispatchWorkItem { [weak self] in
            self?.complete(id, ["ok": false, "errorCode": "browser_timeout",
                                "message": "The browser did not answer in time"])
        }
        pending[id] = Pending(client: client, request: request, caller: caller,
                              claimID: claimID, timeout: timeout)
        DispatchQueue.main.asyncAfter(deadline: .now() + .seconds(BrowserRelay.timeoutSeconds),
                                      execute: timeout)
        write(["type": "request", "id": id,
               "operation": request["operation"] as? String ?? "", "params": params])
        return nil
    }

    private func sendGrantState() {
        guard connected else { return }
        write(["type": "grant", "browser": broker.browserAllowed])
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
        for id in Array(pending.keys) {
            complete(id, ["ok": false, "errorCode": reason,
                          "message": "The browser provider disconnected"])
        }
    }

    private func complete(_ id: String, _ message: [String: Any]) {
        guard let entry = pending.removeValue(forKey: id) else { return }
        entry.timeout.cancel()
        let response = message["ok"] as? Bool == true ?
            accepted(entry.request, data: message["data"] as? [String: Any] ?? [:]) :
            routed(service.refusal(entry.request,
                code: message["errorCode"] as? String ?? "browser_operation_failed",
                message: message["message"] as? String ?? "Browser operation failed"))
        respond?(entry.client, entry.request, response, entry.caller, entry.claimID)
        Darwin.close(entry.client)
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
