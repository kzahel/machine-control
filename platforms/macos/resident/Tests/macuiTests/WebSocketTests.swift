import XCTest
@testable import macui

final class WebSocketTests: XCTestCase {
    func testAcceptKeyMatchesRFC6455Example() {
        // The example from RFC 6455 section 1.3.
        XCTAssertEqual(WebSocketFraming.acceptKey("dGhlIHNhbXBsZSBub25jZQ=="),
                       "s3pPLMBiTxaQ9kYGzzhZRbK+xOo=")
    }

    func testParsesUpgradeWithPathQueryAndOrigin() {
        let request = Data([
            "GET /devtools/page/42?token=abc%2Fd HTTP/1.1",
            "Host: 127.0.0.1:9014",
            "Upgrade: websocket",
            "Connection: Upgrade",
            "Sec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==",
            "Origin: https://evil.example",
            "", "",
        ].joined(separator: "\r\n").utf8)
        let upgrade = WebSocketFraming.parseUpgrade(request)
        XCTAssertEqual(upgrade?.path, "/devtools/page/42")
        XCTAssertEqual(upgrade?.query["token"], "abc/d")
        XCTAssertEqual(upgrade?.origin, "https://evil.example")
        XCTAssertEqual(upgrade?.key, "dGhlIHNhbXBsZSBub25jZQ==")
    }

    func testRejectsNonWebSocketRequests() {
        XCTAssertNil(WebSocketFraming.parseUpgrade(Data("GET / HTTP/1.1\r\nHost: x\r\n\r\n".utf8)))
        XCTAssertNil(WebSocketFraming.parseUpgrade(Data("POST /devtools/page/1 HTTP/1.1\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Key: k\r\n\r\n".utf8)))
    }

    func testEncodesAndDecodesRoundTrip() {
        // A masked client frame decodes to its text.
        let text = "{\"id\":1,\"method\":\"Page.enable\"}"
        var frame = Data([0x81, 0x80 | UInt8(text.utf8.count)])
        let mask: [UInt8] = [0x0A, 0x0B, 0x0C, 0x0D]
        frame.append(contentsOf: mask)
        for (index, byte) in Array(text.utf8).enumerated() { frame.append(byte ^ mask[index % 4]) }
        let decoded = WebSocketFraming.decode(frame)
        XCTAssertEqual(decoded?.frame, .text(text))
        XCTAssertEqual(decoded?.consumed, frame.count)

        // A server frame is unmasked with the same payload length structure.
        let server = WebSocketFraming.encode(text: text)
        XCTAssertEqual(server.first, 0x81)
        XCTAssertEqual(Int(server[1] & 0x7F), text.utf8.count)
    }

    func testDecodeNeedsWholeFrame() {
        XCTAssertNil(WebSocketFraming.decode(Data([0x81])))
        // 200-byte payload uses the 16-bit length; header present, body missing.
        XCTAssertNil(WebSocketFraming.decode(Data([0x81, 126, 0x00, 0xC8])))
    }

    func testDecodesLargeSixteenBitFrame() {
        let payload = String(repeating: "x", count: 300)
        var frame = Data([0x81, 0x80 | 126, 0x01, 0x2C])
        let mask: [UInt8] = [1, 2, 3, 4]
        frame.append(contentsOf: mask)
        for (index, byte) in Array(payload.utf8).enumerated() { frame.append(byte ^ mask[index % 4]) }
        XCTAssertEqual(WebSocketFraming.decode(frame)?.frame, .text(payload))
    }
}

final class DevToolsBridgeTests: XCTestCase {
    private func upgrade(path: String = "/devtools/page/7", token: String,
                         origin: String? = nil) -> WebSocketUpgrade {
        WebSocketUpgrade(path: path, query: ["token": token], key: "k", origin: origin, host: "127.0.0.1")
    }

    func testTokenAndOriginGateAcceptance() {
        let broker = GrantBroker(policy: .workstation(issue: nil))
        let relay = BrowserRelay(service: ResidentService(), broker: broker)
        let bridge = BrowserDevToolsBridge(broker: broker, relay: relay)
        bridge.setTokenForTesting("secret")

        XCTAssertNil(bridge.acceptedTab(upgrade(token: "secret")))

        broker.issue(scopes: [.devtools], durationSeconds: 600, reason: "r", requester: "x",
                     approver: "test")
        XCTAssertEqual(bridge.acceptedTab(upgrade(token: "secret")), 7)
        XCTAssertNil(bridge.acceptedTab(upgrade(token: "wrong")))
        XCTAssertNil(bridge.acceptedTab(upgrade(token: "secret", origin: "https://evil.example")))
        XCTAssertNil(bridge.acceptedTab(upgrade(path: "/other/7", token: "secret")))

        broker.revoke(reason: "stop")
        XCTAssertNil(bridge.acceptedTab(upgrade(token: "secret")))
        XCTAssertNil(bridge.reconcile())
    }

    func testStandingPolicyKeepsAToken() {
        let broker = GrantBroker(policy: DeploymentPolicy(preset: "appliance", grantMode: .standing,
            protectedOperations: true, source: "policy_file", issue: nil))
        let bridge = BrowserDevToolsBridge(broker: broker,
            relay: BrowserRelay(service: ResidentService(), broker: broker))
        bridge.setTokenForTesting("t")
        XCTAssertEqual(bridge.acceptedTab(upgrade(token: "t")), 7)
    }
}
