import Darwin
import XCTest
@testable import macui

private final class ScriptedApprover: GrantApprover {
    let kind = "test"
    var decision: GrantDecision
    var presented: [GrantRequest] = []

    init(_ decision: GrantDecision) { self.decision = decision }

    func present(_ request: GrantRequest, completion: @escaping (GrantDecision) -> Void) {
        presented.append(request)
        let decision = self.decision
        DispatchQueue.main.asyncAfter(deadline: .now() + .milliseconds(50)) { completion(decision) }
    }

    func dismiss(requestID: String) {}
}

/// Drives the real socket server the way any same-user process could.
final class ServerTests: XCTestCase {
    private var socketPath = ""
    private var server: ResidentServer!
    private var broker: GrantBroker!
    private var preferences: UserDefaults!
    private var preferenceSuite = ""

    override func setUpWithError() throws {
        signal(SIGPIPE, SIG_IGN)
        socketPath = "/tmp/mc-test-\(getpid())-\(Int.random(in: 0..<100_000)).sock"
        broker = GrantBroker(policy: .workstation(issue: nil))
        preferenceSuite = "mc-browser-lock-test-" + UUID().uuidString
        preferences = UserDefaults(suiteName:preferenceSuite)!
        server = ResidentServer(socketPath: socketPath, service: ResidentService(), broker: broker,
                                preferences:preferences, policyDirectory:try testPolicyRoot())
        server.approvalDesktopUnlocked = { true }
        server.grantConsoleObservation = {
            ["desktopState":"unlocked", "uuid":"test-console", "boot":123, "uid":getuid()]
        }
        try server.start()
    }

    override func tearDown() {
        server.stop()
        preferences.removePersistentDomain(forName:preferenceSuite)
        unlink(socketPath)
    }

    private func call(_ request: [String: Any]) -> [String: Any] {
        let done = expectation(description: "response")
        var result: [String: Any] = [:]
        let path = socketPath
        DispatchQueue.global().async {
            defer { done.fulfill() }
            let descriptor = socket(AF_UNIX, SOCK_STREAM, 0)
            defer { Darwin.close(descriptor) }
            guard let destination = try? unixAddress(path) else { return  }
            var address = destination.0
            guard withSockAddr(&address, length: destination.1, { Darwin.connect(descriptor, $0, $1) }) == 0,
                  let line = try? encodeJSONLine(request),
                  (try? writeSocket(descriptor, data: line)) != nil else { return }
            _ = Darwin.shutdown(descriptor, SHUT_WR)
            if let data = try? readSocket(descriptor),
               let object = try? JSONSerialization.jsonObject(with: data) as? [String: Any] {
                result = object
            }
        }
        wait(for: [done], timeout: 10)
        return result
    }

    func testDirectCallsNeedAGrant() {
        let result = call(["operation": "applications"])
        XCTAssertEqual(result["accepted"] as? Bool, false)
        XCTAssertEqual(result["errorCode"] as? String, "surface_disabled")
        XCTAssertEqual((result["data"] as? [String: Any])?["requiredScope"] as? String, "observe")
        XCTAssertEqual(call(["operation": "input.key", "key": "a"])["errorCode"] as? String,
                       "surface_disabled")
    }

    func testDiscoveryProgressesWhileAnOperatorMenuScreensDesktopEffects() {
        server.guardRequest = { _ in GrantRefusal("self_target_refused","Operator menu open") }
        XCTAssertEqual(call(["operation":"status"])["accepted"] as? Bool,true)
        XCTAssertEqual(call(["operation":"browser.profiles"])["accepted"] as? Bool,true)
    }
    func testStatusReportsDeployment() {
        let deployment = (call(["operation": "grant.status"])["data"] as? [String: Any])
        XCTAssertEqual((deployment?["policy"] as? [String: Any])?["preset"] as? String, "workstation")
    }

    func testDesktopDiscoveryDoesNotAuthorizeControl() {
        XCTAssertEqual(call(["operation": "update.status"])["errorCode"] as? String, "unsupported_operation")
        XCTAssertFalse(server.updates.sync(["phase": "idle", "checking": false, "installing": false]))
        XCTAssertEqual(call(["operation": "update.check"])["accepted"] as? Bool, true)
        XCTAssertNil(broker.grant)
        XCTAssertEqual(call(["operation": "input.key", "key": "a"])["errorCode"] as? String, "surface_disabled")
        XCTAssertEqual(call(["operation": "update.install"])["accepted"] as? Bool, false)
        XCTAssertTrue(server.updates.sync(["phase": "idle", "checking": false, "installing": false]))
        let data = call(["operation": "update.status"])["data"] as? [String: Any]
        XCTAssertEqual((data?["update"] as? [String: Any])?["checking"] as? Bool, true)
    }

    func testReplacementCannotInheritResidentListener() throws {
        // Discover the real server endpoint without exposing its private FD.
        let descriptor = try XCTUnwrap((3..<1024).first { fd in
            var address = sockaddr_un()
            var length = socklen_t(MemoryLayout.size(ofValue: address))
            guard withUnsafeMutablePointer(to: &address, {
                $0.withMemoryRebound(to: sockaddr.self, capacity: 1) {
                    Darwin.getsockname(Int32(fd), $0, &length)
                }
            }) == 0, address.sun_family == AF_UNIX else { return false }
            return withUnsafePointer(to: &address.sun_path) {
                $0.withMemoryRebound(to: CChar.self, capacity: 104) {
                    String(cString: $0) == socketPath
                }
            }
        })
        // Use plain posix_spawn, without a framework closing descriptors for
        // us. A replacement must not keep this socket alive after our exit.
        let arguments = ["/bin/sh", "-c", "test ! -S /dev/fd/$1", "mc-inheritance", String(descriptor)]
        var argv = arguments.map { strdup($0) } + [nil]
        defer { argv.forEach { free($0) } }
        var pid: pid_t = 0
        XCTAssertEqual(posix_spawn(&pid, "/bin/sh", nil, nil, &argv, environ), 0)
        var status: Int32 = 0
        XCTAssertEqual(waitpid(pid, &status, 0), pid)
        XCTAssertEqual(status, 0, "Replacement inherited the resident listener")
    }

    func testLegacyGrantRequestCannotIssueAuthority() {
        XCTAssertEqual(call(["operation":"grant.request", "scopes":["observe"], "reason":"Fixture"])["errorCode"] as? String,"legacy_grant_request_unsupported")
        XCTAssertNil(broker.activeGrant)
    }
    func testSurfaceConsentBindsToTheApprovingConsoleAndUnknownIsUnavailable() throws {
        try server.configureSurface("desktop",mode:"automatic",seconds:nil)
        let consent = broker.desktopConsentID
        XCTAssertTrue(broker.desktopRouteReady)
        server.grantConsoleObservation = { ["desktopState":"unknown"] }
        server.refreshAdmission()
        XCTAssertFalse(broker.desktopRouteReady)
        XCTAssertTrue(broker.admission.enabled("desktop"))
        server.grantConsoleObservation = { ["desktopState":"unlocked", "uuid":"replacement", "boot":123, "uid":getuid()] }
        server.refreshAdmission()
        XCTAssertFalse(broker.admission.enabled("desktop"))
        XCTAssertNotEqual(broker.desktopConsentID,consent)
    }
    func testBrowserLockPreferenceDoesNotArmEitherSurface() throws {
        try server.configureBrowserWhileLocked(enabled:true)
        XCTAssertFalse(broker.admission.enabled("desktop")); XCTAssertFalse(broker.admission.enabled("browser"))
        XCTAssertEqual((call(["operation":"browser.profiles"])["accepted"] as? Bool),true)
    }
}
