import Darwin
import XCTest
@testable import macui

/// A stand-in for the native-messaging host that answers like the extension.
private final class FakeProvider {
    let descriptor: Int32
    private var buffer = Data()

    init?(socketPath: String) {
        descriptor = socket(AF_UNIX, SOCK_STREAM, 0)
        guard var (address, length) = try? unixAddress(socketPath),
              withSockAddr(&address, length: length, { Darwin.connect(descriptor, $0, $1) }) == 0 else {
            return nil
        }
        var timeout = timeval(tv_sec: 5, tv_usec: 0)
        setsockopt(descriptor, SOL_SOCKET, SO_RCVTIMEO, &timeout, socklen_t(MemoryLayout.size(ofValue: timeout)))
    }

    deinit { Darwin.close(descriptor) }

    func send(_ message: [String: Any]) {
        _ = try? writeSocket(descriptor, data: encodeJSONLine(message))
    }

    func next() -> [String: Any]? {
        var chunk = [UInt8](repeating: 0, count: 65_536)
        while true {
            if let newline = buffer.firstIndex(of: 0x0a) {
                let line = buffer[buffer.startIndex..<newline]
                buffer.removeSubrange(buffer.startIndex...newline)
                return try? JSONSerialization.jsonObject(with: Data(line)) as? [String: Any]
            }
            let count = Darwin.read(descriptor, &chunk, chunk.count)
            guard count > 0 else { return nil }
            buffer.append(chunk, count: count)
        }
    }
}

final class BrowserRelayTests: XCTestCase {
    private var socketPath = ""
    private var server: ResidentServer!
    private var broker: GrantBroker!

    override func setUpWithError() throws {
        socketPath = "/tmp/mc-browser-\(getpid())-\(Int.random(in: 0..<100_000)).sock"
        broker = GrantBroker(policy: .workstation(issue: nil))
        server = ResidentServer(socketPath: socketPath, service: ResidentService(), broker: broker)
        try server.start()
    }

    override func tearDown() {
        unlink(socketPath)
    }

    private func onBackground<T>(_ body: @escaping () -> T) -> T {
        let done = expectation(description: "background")
        var value: T?
        DispatchQueue.global().async {
            value = body()
            done.fulfill()
        }
        wait(for: [done], timeout: 20)
        return value!
    }

    private func call(_ request: [String: Any]) -> [String: Any] {
        let path = socketPath
        return onBackground {
            let descriptor = socket(AF_UNIX, SOCK_STREAM, 0)
            defer { Darwin.close(descriptor) }
            guard var (address, length) = try? unixAddress(path),
                  withSockAddr(&address, length: length, { Darwin.connect(descriptor, $0, $1) }) == 0,
                  (try? writeSocket(descriptor, data: encodeJSONLine(request))) != nil else { return [:] }
            _ = Darwin.shutdown(descriptor, SHUT_WR)
            guard let data = try? readSocket(descriptor),
                  let object = try? JSONSerialization.jsonObject(with: data) as? [String: Any] else { return [:] }
            return object
        }
    }

    private func connectProvider() -> FakeProvider? {
        let path = socketPath
        let provider = onBackground { FakeProvider(socketPath: path) }
        provider?.send(["operation": "browser.provider", "origin": "chrome-extension://test/"])
        return provider
    }

    func testUntrustedProviderIsRefused() {
        // In tests the fake provider shares this process's code identity, so
        // inject a peer that fails the check.
        server.browser.identityCheck = { _ in false }
        let provider = connectProvider()
        let reply = onBackground { provider?.next() }
        XCTAssertEqual(reply?["errorCode"] as? String, "browser_provider_untrusted")
        XCTAssertFalse(server.browser.connected)
    }

    func testBrowserOperationsNeedGrantAndProvider() {
        XCTAssertEqual(call(["operation": "browser.tabs"])["errorCode"] as? String, "approval_required")
        broker.issue(scopes: [.browser], durationSeconds: 600, reason: "r", requester: "x", approver: "test")
        let unavailable = call(["operation": "browser.tabs"])
        XCTAssertEqual(unavailable["errorCode"] as? String, "browser_provider_unavailable")
        XCTAssertEqual(unavailable["actualRoute"] as? String, BrowserRelay.route)
    }

    func testRelayForwardsAndReportsGrantState() {
        server.browser.identityCheck = { _ in true }
        guard let provider = connectProvider() else { return XCTFail("provider did not connect") }
        XCTAssertEqual(onBackground { provider.next() }?["type"] as? String, "registered")
        XCTAssertEqual(onBackground { provider.next() }?["browser"] as? Bool, false)

        broker.issue(scopes: [.observe, .browser], durationSeconds: 600, reason: "r",
                     requester: "x", approver: "test")
        XCTAssertEqual(onBackground { provider.next() }?["browser"] as? Bool, true)

        // Answer the next request the way the extension would.
        let answered = expectation(description: "provider answered")
        DispatchQueue.global().async {
            if let request = provider.next(), request["type"] as? String == "request" {
                XCTAssertEqual(request["operation"] as? String, "browser.capture")
                XCTAssertEqual((request["params"] as? [String: Any])?["tabId"] as? Int, 7)
                XCTAssertNil((request["params"] as? [String: Any])?["claimId"])
                provider.send(["type": "response", "id": request["id"] ?? "", "ok": true,
                               "data": ["png": Data("png".utf8).base64EncodedString(),
                                        "tab": ["tabId": 7]]])
            }
            answered.fulfill()
        }
        let result = call(["operation": "browser.capture", "tabId": 7, "claimId": "c-x"])
        wait(for: [answered], timeout: 10)
        XCTAssertEqual(result["accepted"] as? Bool, true, "\(result)")
        let path = (result["data"] as? [String: Any])?["artifactPath"] as? String
        XCTAssertEqual(path.flatMap { try? Data(contentsOf: URL(fileURLWithPath: $0)) }, Data("png".utf8))
        path.map { try? FileManager.default.removeItem(atPath: $0) }

        broker.revoke(reason: "test")
        XCTAssertEqual(onBackground { provider.next() }?["browser"] as? Bool, false)
        XCTAssertEqual(call(["operation": "browser.tabs"])["errorCode"] as? String, "approval_required")
    }

    func testProviderDisconnectFailsPendingRequest() {
        server.browser.identityCheck = { _ in true }
        var provider = connectProvider()
        XCTAssertEqual(onBackground { provider?.next() }?["type"] as? String, "registered")
        broker.issue(scopes: [.browser], durationSeconds: 600, reason: "r", requester: "x", approver: "test")
        let dropped = expectation(description: "provider dropped")
        DispatchQueue.global().async {
            while let message = provider?.next(), message["type"] as? String != "request" {}
            provider = nil
            dropped.fulfill()
        }
        let result = call(["operation": "browser.tabs"])
        wait(for: [dropped], timeout: 10)
        XCTAssertEqual(result["errorCode"] as? String, "browser_provider_disconnected")
    }
}
