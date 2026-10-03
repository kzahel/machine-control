import CryptoKit
import Foundation
import Network

/// The parts of a WebSocket upgrade request the server decides on.
struct WebSocketUpgrade: Equatable {
    var path: String
    var query: [String: String]
    var key: String
    var origin: String?
    var host: String?
}

enum WebSocketFraming {
    static let guid = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"

    /// The Sec-WebSocket-Accept value for a client key.
    static func acceptKey(_ key: String) -> String {
        let digest = Insecure.SHA1.hash(data: Data((key + guid).utf8))
        return Data(digest).base64EncodedString()
    }

    /// Parses an HTTP/1.1 upgrade request. Returns nil if it is not a
    /// well-formed WebSocket upgrade.
    static func parseUpgrade(_ data: Data) -> WebSocketUpgrade? {
        guard let text = String(data: data, encoding: .utf8) else { return nil }
        let lines = text.components(separatedBy: "\r\n")
        guard let requestLine = lines.first else { return nil }
        let parts = requestLine.split(separator: " ")
        guard parts.count >= 2, parts[0] == "GET" else { return nil }
        let target = String(parts[1])
        var headers: [String: String] = [:]
        for line in lines.dropFirst() where line.contains(":") {
            let pair = line.split(separator: ":", maxSplits: 1)
            headers[pair[0].lowercased().trimmingCharacters(in: .whitespaces)] =
                pair.count > 1 ? pair[1].trimmingCharacters(in: .whitespaces) : ""
        }
        guard headers["upgrade"]?.lowercased() == "websocket",
              headers["connection"]?.lowercased().contains("upgrade") == true,
              let key = headers["sec-websocket-key"] else { return nil }
        var path = target
        var query: [String: String] = [:]
        if let mark = target.firstIndex(of: "?") {
            path = String(target[target.startIndex..<mark])
            for pair in target[target.index(after: mark)...].split(separator: "&") {
                let kv = pair.split(separator: "=", maxSplits: 1)
                let name = kv[0].removingPercentEncoding ?? String(kv[0])
                query[name] = kv.count > 1 ? (kv[1].removingPercentEncoding ?? String(kv[1])) : ""
            }
        }
        return WebSocketUpgrade(path: path, query: query, key: key,
                                origin: headers["origin"], host: headers["host"])
    }

    /// A server text frame: fin, opcode 1, unmasked.
    static func encode(text: String) -> Data {
        encode(opcode: 0x1, payload: Data(text.utf8))
    }

    static func encode(opcode: UInt8, payload: Data) -> Data {
        var frame = Data([0x80 | opcode])
        let count = payload.count
        if count < 126 {
            frame.append(UInt8(count))
        } else if count <= 0xFFFF {
            frame.append(126)
            frame.append(UInt8(count >> 8)); frame.append(UInt8(count & 0xFF))
        } else {
            frame.append(127)
            for shift in stride(from: 56, through: 0, by: -8) {
                frame.append(UInt8((count >> shift) & 0xFF))
            }
        }
        frame.append(payload)
        return frame
    }

    enum Frame: Equatable {
        case text(String)
        case binary(Data)
        case ping(Data)
        case pong(Data)
        case close
    }

    /// Decodes one frame from the front of `buffer`, returning it and the
    /// number of bytes consumed, or nil if a whole frame is not present yet.
    /// Client frames must be masked per RFC 6455.
    static func decode(_ buffer: Data) -> (frame: Frame, consumed: Int)? {
        let bytes = [UInt8](buffer)
        guard bytes.count >= 2 else { return nil }
        let opcode = bytes[0] & 0x0F
        let masked = bytes[1] & 0x80 != 0
        var length = Int(bytes[1] & 0x7F)
        var offset = 2
        if length == 126 {
            guard bytes.count >= 4 else { return nil }
            length = Int(bytes[2]) << 8 | Int(bytes[3]); offset = 4
        } else if length == 127 {
            guard bytes.count >= 10 else { return nil }
            length = 0
            for index in 2..<10 { length = length << 8 | Int(bytes[index]) }
            offset = 10
        }
        let maskLength = masked ? 4 : 0
        guard bytes.count >= offset + maskLength + length else { return nil }
        var payload = [UInt8](bytes[(offset + maskLength)..<(offset + maskLength + length)])
        if masked {
            let mask = Array(bytes[offset..<offset + 4])
            for index in payload.indices { payload[index] ^= mask[index % 4] }
        }
        let consumed = offset + maskLength + length
        let data = Data(payload)
        switch opcode {
        case 0x1: return (.text(String(decoding: data, as: UTF8.self)), consumed)
        case 0x2: return (.binary(data), consumed)
        case 0x8: return (.close, consumed)
        case 0x9: return (.ping(data), consumed)
        case 0xA: return (.pong(data), consumed)
        default: return (.binary(data), consumed)
        }
    }
}

/// One accepted WebSocket connection. All callbacks run on the main queue.
final class WebSocketConnection {
    var onText: ((String) -> Void)?
    var onClose: (() -> Void)?

    private let connection: NWConnection
    private var buffer = Data()
    private var open = false
    private var closed = false
    private let maxMessageBytes = 32 * 1_048_576

    init(_ connection: NWConnection) {
        self.connection = connection
    }

    /// Reads the upgrade request and decides via `authorize`. Completing the
    /// handshake calls `onReady`; a rejected or malformed request is closed.
    func start(authorize: @escaping (WebSocketUpgrade) -> Bool, onReady: @escaping () -> Void) {
        connection.start(queue: .main)
        readUpgrade(authorize: authorize, onReady: onReady)
    }

    private func readUpgrade(authorize: @escaping (WebSocketUpgrade) -> Bool,
                             onReady: @escaping () -> Void) {
        connection.receive(minimumIncompleteLength: 1, maximumLength: 65_536) {
            [weak self] data, _, isComplete, error in
            guard let self else { return }
            if let data { self.buffer.append(data) }
            if let range = self.buffer.range(of: Data("\r\n\r\n".utf8)) {
                let head = self.buffer.subdata(in: self.buffer.startIndex..<range.lowerBound)
                self.buffer.removeSubrange(self.buffer.startIndex..<range.upperBound)
                guard let upgrade = WebSocketFraming.parseUpgrade(head), authorize(upgrade) else {
                    self.reject()
                    return
                }
                let response = "HTTP/1.1 101 Switching Protocols\r\n"
                    + "Upgrade: websocket\r\nConnection: Upgrade\r\n"
                    + "Sec-WebSocket-Accept: \(WebSocketFraming.acceptKey(upgrade.key))\r\n\r\n"
                self.connection.send(content: Data(response.utf8), completion: .contentProcessed { _ in
                    self.open = true
                    onReady()
                    self.pump()
                })
                return
            }
            if error != nil || isComplete || self.buffer.count > 65_536 { self.reject() }
            else { self.readUpgrade(authorize: authorize, onReady: onReady) }
        }
    }

    private func reject() {
        let response = "HTTP/1.1 403 Forbidden\r\nConnection: close\r\nContent-Length: 0\r\n\r\n"
        connection.send(content: Data(response.utf8), completion: .contentProcessed { _ in
            self.connection.cancel()
        })
    }

    func send(_ text: String) {
        guard open, !closed else { return }
        connection.send(content: WebSocketFraming.encode(text: text), completion: .idempotent)
    }

    func close() {
        guard !closed else { return }
        closed = true
        if open {
            connection.send(content: WebSocketFraming.encode(opcode: 0x8, payload: Data()),
                            completion: .contentProcessed { _ in self.connection.cancel() })
        } else {
            connection.cancel()
        }
        let callback = onClose
        onClose = nil
        callback?()
    }

    private func pump() {
        connection.receive(minimumIncompleteLength: 1, maximumLength: 262_144) {
            [weak self] data, _, isComplete, error in
            guard let self else { return }
            if let data { self.buffer.append(data) }
            while let (frame, consumed) = WebSocketFraming.decode(self.buffer) {
                self.buffer.removeSubrange(self.buffer.startIndex..<(self.buffer.startIndex + consumed))
                switch frame {
                case let .text(text): self.onText?(text)
                case .close: self.close(); return
                case let .ping(payload):
                    self.connection.send(content: WebSocketFraming.encode(opcode: 0xA, payload: payload),
                                         completion: .idempotent)
                case .binary, .pong: break
                }
            }
            if self.buffer.count > self.maxMessageBytes || error != nil || isComplete { self.close() }
            else { self.pump() }
        }
    }
}

/// Accepts local WebSocket connections on a chosen loopback port.
final class WebSocketServer {
    private var listener: NWListener?
    private(set) var port: UInt16 = 0

    /// Starts listening on 127.0.0.1 with an OS-assigned port. `onConnection`
    /// receives each connection and the upgrade it must authorize.
    func start(onConnection: @escaping (WebSocketConnection, WebSocketUpgrade) -> Bool) throws {
        let parameters = NWParameters.tcp
        parameters.requiredLocalEndpoint = .hostPort(host: .ipv4(.loopback), port: .any)
        parameters.allowLocalEndpointReuse = true
        let listener = try NWListener(using: parameters)
        listener.newConnectionHandler = { connection in
            let socket = WebSocketConnection(connection)
            socket.start(authorize: { onConnection(socket, $0) }, onReady: {})
        }
        listener.stateUpdateHandler = { [weak self] state in
            if case .ready = state, let assigned = listener.port { self?.port = assigned.rawValue }
        }
        listener.start(queue: .main)
        self.listener = listener
    }

    func stop() {
        listener?.cancel()
        listener = nil
        port = 0
    }
}
