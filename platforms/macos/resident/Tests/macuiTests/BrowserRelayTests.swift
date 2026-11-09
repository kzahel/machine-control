import Darwin
import XCTest
@testable import macui

/// A stand-in for the native-messaging host that answers like the extension.
private final class FakeProvider {
    let descriptor: Int32
    private var buffer = Data()

    init?(socketPath: String) {
        descriptor = socket(AF_UNIX, SOCK_STREAM, 0)
        guard let destination = try? unixAddress(socketPath) else { return nil }
        var address = destination.0
        guard withSockAddr(&address, length: destination.1, { Darwin.connect(descriptor, $0, $1) }) == 0 else {
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
        signal(SIGPIPE, SIG_IGN)
        socketPath = "/tmp/mc-browser-\(getpid())-\(Int.random(in: 0..<100_000)).sock"
        broker = GrantBroker(policy: .workstation(issue: nil))
        server = ResidentServer(socketPath: socketPath, service: ResidentService(), broker: broker, policyDirectory:try testPolicyRoot())
        server.grantConsoleObservation = {
            ["desktopState":"unlocked", "uuid":"test-console", "boot":123, "uid":getuid()]
        }
        server.approvalDesktopUnlocked = { true }
        try server.start()
    }

    override func tearDown() {
        server.stop()
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
            guard let destination = try? unixAddress(path) else { return [:] }
            var address = destination.0
            guard withSockAddr(&address, length: destination.1, { Darwin.connect(descriptor, $0, $1) }) == 0,
                  (try? writeSocket(descriptor, data: encodeJSONLine(request))) != nil else { return [:] }
            _ = Darwin.shutdown(descriptor, SHUT_WR)
            guard let data = try? readSocket(descriptor),
                  let object = try? JSONSerialization.jsonObject(with: data) as? [String: Any] else { return [:] }
            return object
        }
    }

    /// Connects a provider and, when trusted, drains the "registered" reply in
    /// the same main-pumped hop so registration is deterministic under load.
    private func connectProvider(drainRegistered: Bool = true) -> FakeProvider? {
        let path = socketPath
        return onBackground { () -> FakeProvider? in
            guard let provider = FakeProvider(socketPath: path) else { return nil }
            provider.send(["operation": "browser.provider", "origin": "chrome-extension://test/"])
            if drainRegistered { _ = provider.next() }
            return provider
        }
    }

    func testUntrustedProviderIsRefused() {
        // In tests the fake provider shares this process's code identity, so
        // inject a peer that fails the check.
        server.browser.identityCheck = { _ in false }
        let provider = connectProvider(drainRegistered: false)
        let reply = onBackground { provider?.next() }
        XCTAssertEqual(reply?["errorCode"] as? String, "browser_provider_untrusted")
        XCTAssertFalse(server.browser.connected)
    }

    private func attach(_ name:String, _ suffix:String) throws -> FakeProvider {
        let path = socketPath
        let provider = try XCTUnwrap(onBackground { () -> FakeProvider? in
            guard let provider = FakeProvider(socketPath:path) else { return nil }
            provider.send(["operation":"browser.provider", "origin":"chrome-extension://ncbfifkjllmnkkjmomjohinigfgdocjc/"])
            guard provider.next()?["type"] as? String == "registered" else { return nil }
            provider.send(["type":"hello", "protocolVersion":1, "extensionVersion":"fixture",
                "profile":["protocolVersion":1, "installationId":"00000000-0000-4000-8000-00000000000" + suffix,
                    "name":name, "enabled":true]])
            return provider
        })
        return provider
    }
    private func settle(_ predicate:@escaping () -> Bool) {
        let done = expectation(description:"shared profile projection")
        let timer = DispatchSource.makeTimerSource(queue:.main)
        timer.schedule(deadline:.now(), repeating:.milliseconds(10))
        timer.setEventHandler { if predicate() { timer.cancel(); done.fulfill() } }; timer.resume()
        wait(for:[done],timeout:3); timer.cancel()
    }
    func testTwoProfilesStayConnectedAndCopiedIdentityIsRefusedWithoutEviction() throws {
        server.browser.identityCheck = { _ in true }
        let work = try attach("Work","1"), personal = try attach("Personal","2")
        settle { self.server.browser.profiles.count == 2 }
        let copied = try attach("Copied","1")
        let refusal = onBackground { copied.next() }
        XCTAssertEqual(refusal?["type"] as? String,"profile.refused")
        XCTAssertEqual(refusal?["reason"] as? String,"profile_conflict")
        XCTAssertEqual(server.browser.profiles.filter { $0["connected"] as? Bool == true }.count,2)
        withExtendedLifetime([work,personal,copied]) {}
    }
    func testRealSharedBrowserCallRequiresExactLiveOwnerAndProfile() throws {
        server.browser.identityCheck = { _ in true }
        let provider = try attach("Work","1")
        settle { self.server.browser.profiles.count == 1 }
        let profile = try XCTUnwrap(server.browser.profiles.first?["profileId"] as? String)
        try server.configureSurface("browser",mode:"automatic",seconds:nil,profiles:[profile])
        let admission = broker.admission
        let intent = try admission.submit(owner:"fixture-owner",requestID:"tabs",resources:["browser"],wait:120,duration:60,reason:"Fixture",authority:{ nil },profileIDs:[profile],operations:["browser.tabs"])
        let id = try XCTUnwrap(intent["intentId"] as? String)
        let active = try admission.accept(owner:"fixture-owner",id:id,generation:try XCTUnwrap(intent["offerGeneration"] as? Int))
        let session = try XCTUnwrap(active["sessionId"] as? String), generations = try XCTUnwrap(active["resourceGenerations"] as? [String:Int])
        let authority = BrowserRelay.Authority(ownerSession:"fixture-owner:" + session,profileIDs:[profile],validate:{ admission.authorize(owner:"fixture-owner",id:id,session:session,generations:generations,operation:"browser.tabs") })
        let answered = expectation(description:"real provider response")
        let owner: [String:Any] = ["claimId":"c-a1a1a1a1a1a1a1a1a1a1a1a1", "leaseSeconds":60, "sessionRef":"fixture-agent"]
        DispatchQueue.global().async {
            while let frame = provider.next() {
                if frame["type"] as? String == "request" {
                    // Claim attribution crosses the native relay and shared runtime unchanged.
                    let routed = (frame["params"] as? [String:Any])?["owner"] as? [String:Any]
                    XCTAssertEqual(routed?["claimId"] as? String, owner["claimId"] as? String)
                    XCTAssertEqual(routed?["leaseSeconds"] as? Int, 60)
                    XCTAssertEqual(routed?["sessionRef"] as? String, "fixture-agent")
                    provider.send(["type":"response", "id":frame["id"]!, "ok":true, "data":["tabs":[["id":1,"title":"Fixture"]]]])
                    answered.fulfill(); return
                }
            }
            XCTFail("No routed provider request"); answered.fulfill()
        }
        let completed = expectation(description:"native completion")
        let refusal = server.browser.forward(-1,["operation":"browser.tabs","requestId":"tabs","owner":owner],caller:CallerIdentity(uid:getuid(),chain:[]),claimID:nil,authority:authority) { result in
            XCTAssertEqual(result["accepted"] as? Bool,true)
            XCTAssertEqual((result["data"] as? [String:Any])?["browserProfileId"] as? String,profile)
            completed.fulfill()
        }
        XCTAssertNil(refusal); wait(for:[answered,completed],timeout:5)
        try admission.cancel(owner:"fixture-owner",id:id)
        let stale = server.browser.forward(-1,["operation":"browser.tabs"],caller:CallerIdentity(uid:getuid(),chain:[]),claimID:nil,authority:authority)
        XCTAssertEqual(stale?["accepted"] as? Bool,false)
    }
    func testDirectBrowserWorkCannotBorrowOperatorConsent() throws {
        XCTAssertEqual(call(["operation":"browser.tabs"])["errorCode"] as? String,"surface_disabled")
        XCTAssertEqual(call(["operation":"browser.profiles"])["accepted"] as? Bool,true)
    }
}
