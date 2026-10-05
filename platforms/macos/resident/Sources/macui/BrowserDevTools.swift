import Foundation
import Security

/// Receives the extension's replies for one raw DevTools session.
protocol DevToolsSession: AnyObject {
    func sessionOpened()
    func sessionResult(_ message: [String: Any])
    func sessionEvent(_ message: [String: Any])
    func sessionClosed(_ reason: String)
}

/// Bridges one local WebSocket to a tab or the browser facade. The client
/// speaks raw CDP (`{"id",...,"method",...}` in, results and events out);
/// this translates to and from the relay's session messages.
final class DevToolsBridgeConnection: DevToolsSession {
    private let socket: WebSocketConnection
    private weak var relay: BrowserRelay?
    private let tabId: Int
    private var sessionId: String?
    private var opened = false

    var onFinished: (() -> Void)?

    init(socket: WebSocketConnection, relay: BrowserRelay, tabId: Int) {
        self.socket = socket
        self.relay = relay
        self.tabId = tabId
        socket.onText = { [weak self] in self?.onClientFrame($0) }
        socket.onClose = { [weak self] in self?.teardown() }
        sessionId = relay.openSession(tabId: tabId, handler: self)
    }

    private func onClientFrame(_ text: String) {
        guard let sessionId,
              let object = try? JSONSerialization.jsonObject(with: Data(text.utf8)) as? [String: Any],
              let cmdId = (object["id"] as? NSNumber)?.intValue,
              let method = object["method"] as? String else {
            return
        }
        relay?.sendSessionCommand(sessionId, cmdId: cmdId, method: method,
                                  params: object["params"] as? [String: Any] ?? [:],
                                  childSession: object["sessionId"] as? String)
    }

    func sessionOpened() { opened = true }

    func sessionResult(_ message: [String: Any]) {
        guard let cmdId = (message["cmdId"] as? NSNumber)?.intValue else { return }
        var frame: [String: Any] = ["id": cmdId]
        if let session = message["sessionId"] as? String { frame["sessionId"] = session }
        if let error = message["error"] {
            frame["error"] = normalizedError(error)
        } else {
            frame["result"] = message["result"] as? [String: Any] ?? [:]
        }
        sendFrame(frame)
    }

    func sessionEvent(_ message: [String: Any]) {
        guard let method = message["method"] as? String else { return }
        var frame: [String: Any] = ["method": method, "params": message["params"] as? [String: Any] ?? [:]]
        if let session = message["sessionId"] as? String { frame["sessionId"] = session }
        sendFrame(frame)
    }

    func sessionClosed(_ reason: String) {
        sessionId = nil
        socket.close()
    }

    private func normalizedError(_ error: Any) -> [String: Any] {
        if let dictionary = error as? [String: Any] { return dictionary }
        return ["code": -32000, "message": String(describing: error)]
    }

    private func sendFrame(_ object: [String: Any]) {
        guard let data = try? JSONSerialization.data(withJSONObject: object) else { return }
        socket.send(String(decoding: data, as: UTF8.self))
    }

    private func teardown() {
        if let sessionId { relay?.closeSession(sessionId) }
        sessionId = nil
        onFinished?()
        onFinished = nil
    }
}

/// Owns the loopback DevTools WebSocket server and binds it to the current
/// devtools grant. The server runs only while that grant is live; its token
/// stops working the moment the grant ends.
final class BrowserDevToolsBridge {
    static let path = "/devtools/page/"

    private let broker: GrantBroker
    private weak var relay: BrowserRelay?
    private var server: WebSocketServer?
    private var token = ""
    private var connections: [DevToolsBridgeConnection] = []

    init(broker: GrantBroker, relay: BrowserRelay) {
        self.broker = broker
        self.relay = relay
        broker.observe { [weak self] in self?.reconcile() }
    }

    /// The loopback server runs for the resident's lifetime so its port is
    /// ready before any grant; the per-grant token, cleared the moment the
    /// grant ends, is what actually gates a connection.
    /// Test seam: assign a known token without a live listener.
    func setTokenForTesting(_ value: String) { token = value }

    func start() {
        guard server == nil else { return }
        let server = WebSocketServer()
        do {
            try server.start { [weak self] socket, upgrade in
                self?.authorize(socket, upgrade) ?? false
            }
        } catch {
            return
        }
        self.server = server
        reconcile()
    }

    /// Syncs the token to the grant and drops connections when it ends.
    @discardableResult
    func reconcile() -> String? {
        if (broker.devtoolsAllowed && !broker.admission.reserved) {
            if token.isEmpty { token = randomToken() }
            return endpointTemplate()
        }
        if !token.isEmpty { revokeToken(reason: "devtools_grant_ended") }
        return nil
    }

    var endpoint: String? {
        (broker.devtoolsAllowed && !broker.admission.reserved) ? endpointTemplate() : nil
    }

    var browserEndpoint: String? {
        endpoint?.replacingOccurrences(of: "\(BrowserDevToolsBridge.path)<tabId>", with: "/devtools/browser")
    }

    private func endpointTemplate() -> String? {
        guard let server, server.port != 0, !token.isEmpty else { return nil }
        return "ws://127.0.0.1:\(server.port)\(BrowserDevToolsBridge.path)<tabId>?token=\(token)"
    }

    /// The accept/reject decision, separated from the connection for testing.
    /// A web page can also open ws://127.0.0.1; a browser sends Origin, an
    /// agent's raw client does not. The per-grant token gates either way.
    func acceptedTab(_ upgrade: WebSocketUpgrade) -> Int? {
        guard (broker.devtoolsAllowed && !broker.admission.reserved),
              !token.isEmpty, upgrade.query["token"] == token,
              upgrade.origin == nil else {
            return nil
        }
        if upgrade.path == "/devtools/browser" { return 0 }
        guard upgrade.path.hasPrefix(BrowserDevToolsBridge.path),
              let tabId = Int(upgrade.path.dropFirst(BrowserDevToolsBridge.path.count)), tabId > 0 else { return nil }
        return tabId
    }

    private func authorize(_ socket: WebSocketConnection, _ upgrade: WebSocketUpgrade) -> Bool {
        guard let tabId = acceptedTab(upgrade), let relay, relay.connected else { return false }
        // Authorization runs on the main queue, where sessions live.
        let connection = DevToolsBridgeConnection(socket: socket, relay: relay, tabId: tabId)
        connection.onFinished = { [weak self] in
            self?.connections.removeAll { $0 === connection }
        }
        connections.append(connection)
        return true
    }

    private func revokeToken(reason: String) {
        token = ""
        for connection in connections { connection.sessionClosed(reason) }
        connections.removeAll()
        relay?.closeAllSessions(reason: reason)
    }

    private func randomToken() -> String {
        var bytes = [UInt8](repeating: 0, count: 24)
        _ = SecRandomCopyBytes(kSecRandomDefault, bytes.count, &bytes)
        return Data(bytes).base64EncodedString()
            .replacingOccurrences(of: "+", with: "-")
            .replacingOccurrences(of: "/", with: "_")
            .replacingOccurrences(of: "=", with: "")
    }
}
