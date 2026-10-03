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

    override func setUpWithError() throws {
        signal(SIGPIPE, SIG_IGN)
        socketPath = "/tmp/mc-test-\(getpid())-\(Int.random(in: 0..<100_000)).sock"
        broker = GrantBroker(policy: .workstation(issue: nil))
        server = ResidentServer(socketPath: socketPath, service: ResidentService(), broker: broker)
        server.approvalDesktopUnlocked = { true }
        server.grantConsoleObservation = {
            ["desktopState":"unlocked", "uuid":"test-console", "boot":123, "uid":getuid()]
        }
        try server.start()
    }

    override func tearDown() {
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
            guard var (address, length) = try? unixAddress(path),
                  withSockAddr(&address, length: length, { Darwin.connect(descriptor, $0, $1) }) == 0,
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
        XCTAssertEqual(result["errorCode"] as? String, "approval_required")
        XCTAssertEqual((result["data"] as? [String: Any])?["requiredScope"] as? String, "observe")
        XCTAssertEqual(call(["operation": "input.key", "key": "a"])["errorCode"] as? String,
                       "approval_required")
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
        XCTAssertEqual(call(["operation": "input.key", "key": "a"])["errorCode"] as? String, "approval_required")
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

    func testRequestWithoutApproverIsRefused() {
        let result = call(["operation": "grant.request", "scopes": ["observe"], "reason": "t"])
        XCTAssertEqual(result["errorCode"] as? String, "approval_unavailable")
    }

    func testLockedDesktopCannotPresentAdditionalApproval() {
        let approver = ScriptedApprover(.approved(scopes: [.control], durationSeconds: 60))
        server.approver = approver
        server.approvalDesktopUnlocked = { false }
        XCTAssertEqual(call(["operation":"grant.request", "scopes":["control"],
                             "reason":"t"])["errorCode"] as? String,
                       "approval_unavailable_while_locked")
        XCTAssertTrue(approver.presented.isEmpty)
        XCTAssertNil(broker.grant)
    }

    func testApprovedGrantAllowsScopeUntilRevoked() {
        let approver = ScriptedApprover(.approved(scopes: [.observe], durationSeconds: 600))
        server.approver = approver
        let granted = call(["operation": "grant.request", "scopes": ["observe", "control"],
                            "reason": "read the screen", "claimId": "c-test"])
        XCTAssertEqual(granted["accepted"] as? Bool, true, "\(granted)")
        XCTAssertEqual((granted["data"] as? [String: Any])?["decision"] as? String, "approved")
        XCTAssertEqual(approver.presented.first?.reason, "read the screen")
        XCTAssertEqual(approver.presented.first?.caller.pid, getpid())

        XCTAssertEqual(call(["operation": "applications"])["accepted"] as? Bool, true)
        // The approver narrowed the request to observation only.
        XCTAssertEqual(call(["operation": "input.key", "key": "a"])["errorCode"] as? String,
                       "approval_required")

        XCTAssertEqual(call(["operation": "grant.revoke"])["accepted"] as? Bool, true)
        XCTAssertEqual(call(["operation": "applications"])["errorCode"] as? String,
                       "approval_required")
        XCTAssertTrue(broker.audit.contains { $0.claimID == "c-test" })
    }

    func testDeniedAndTimedOutRequests() {
        let denier = ScriptedApprover(.denied)
        server.approver = denier
        XCTAssertEqual(call(["operation": "grant.request", "scopes": ["control"],
                             "reason": "t"])["errorCode"] as? String, "approval_denied")
        let silent = SilentApprover()
        server.approver = silent
        XCTAssertEqual(call(["operation": "grant.request", "scopes": ["control"], "reason": "t",
                             "timeoutSeconds": 5])["errorCode"] as? String, "approval_timeout")
        XCTAssertNil(broker.grant)
    }

    func testExpiredGrantIsRefused() {
        var clock = Date()
        broker.now = { clock }
        broker.issue(scopes: [.observe], durationSeconds: 60, reason: "r", requester: "x",
                     approver: "test")
        XCTAssertEqual(call(["operation": "applications"])["accepted"] as? Bool, true)
        clock = clock.addingTimeInterval(61)
        XCTAssertEqual(call(["operation": "applications"])["errorCode"] as? String,
                       "approval_required")
    }

    func testConsoleReplacementRevokesExistingApprovalWhileUnlocked() {
        broker.issueUntilStopped(scopes:[.observe], reason:"r", requester:"local", approver:"test")
        server.grantConsoleObservation = {
            ["desktopState":"unlocked", "uuid":"replacement-console", "boot":123, "uid":getuid()]
        }
        XCTAssertEqual(call(["operation":"applications"])["errorCode"] as? String,"approval_required")
        XCTAssertEqual(broker.lastEnded?.reason,"console_session_changed")
    }

    func testUnknownConsoleCannotRetainApproval() {
        broker.issueUntilStopped(scopes:[.observe], reason:"r", requester:"local", approver:"test")
        server.grantConsoleObservation = { [:] }
        XCTAssertEqual(call(["operation":"applications"])["errorCode"] as? String,"approval_required")
        XCTAssertNil(broker.grant)
    }

    func testGrantIssuedWithoutUnlockedConsoleCannotBindOnLaterUnlock() {
        server.grantConsoleObservation = {
            ["desktopState":"locked", "uuid":"test-console", "boot":123, "uid":getuid()]
        }
        broker.issueUntilStopped(scopes:[.observe], reason:"r", requester:"local", approver:"test")
        server.grantConsoleObservation = {
            ["desktopState":"unlocked", "uuid":"test-console", "boot":123, "uid":getuid()]
        }
        XCTAssertEqual(call(["operation":"applications"])["errorCode"] as? String,"approval_required")
        XCTAssertNil(broker.grant)
    }
}

private final class SilentApprover: GrantApprover {
    let kind = "silent"
    func present(_ request: GrantRequest, completion: @escaping (GrantDecision) -> Void) {}
    func dismiss(requestID: String) {}
}
