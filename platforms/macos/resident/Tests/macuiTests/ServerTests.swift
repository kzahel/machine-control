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
                                preferences:preferences)
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

    private func console(_ state: String, uuid: String = "test-console") {
        server.grantConsoleObservation = {
            ["desktopState":state, "uuid":uuid, "boot":123, "uid":getuid()]
        }
        server.approvalDesktopUnlocked = { state == "unlocked" }
    }

    private func approve(_ scopes: Set<GrantScope>) -> Grant? {
        let approver = ScriptedApprover(.approved(scopes:scopes, durationSeconds:60))
        server.approver = approver
        XCTAssertEqual(call(["operation":"grant.request", "scopes":scopes.map(\.rawValue),
                             "reason":"Locked browser fixture"])["accepted"] as? Bool, true)
        withExtendedLifetime(approver) {}
        return broker.activeGrant
    }

    func testBrowserLockPreferenceDefaultsOffAndDoesNotGrantAccess() throws {
        XCTAssertFalse(server.browserWhileLockedEnabled)
        try server.configureBrowserWhileLocked(enabled:true)
        XCTAssertTrue(server.browserWhileLockedEnabled)
        XCTAssertNil(broker.activeGrant)
        XCTAssertEqual(broker.authorize("browser.tabs")?.code, "approval_required")
        // Preference is durable, but a setting command on the agent socket is
        // an unsupported provider operation and cannot change it.
        XCTAssertEqual(call(["operation":"browser_while_locked", "enabled":false])["accepted"] as? Bool, false)
        XCTAssertTrue(server.browserWhileLockedEnabled)
        let replacement = ResidentServer(socketPath:socketPath + ".replacement", service:ResidentService(),
                                        broker:GrantBroker(policy:.workstation(issue:nil)), preferences:preferences)
        XCTAssertTrue(replacement.browserWhileLockedEnabled)
        console("locked")
        XCTAssertThrowsError(try server.configureBrowserWhileLocked(enabled:true))
    }

    func testBrowserApprovalStillEndsOnLockWithoutOptIn() {
        _ = approve([.browser])
        console("locked")
        _ = call(["operation":"grant.status"])
        XCTAssertNil(broker.activeGrant)
        XCTAssertEqual(broker.lastEnded?.reason, "desktop_locked")
    }

    func testMixedApprovalRetainsOnlyBrowserAvailabilityWhileLocked() throws {
        try server.configureBrowserWhileLocked(enabled:true)
        let grant = try XCTUnwrap(approve([.observe, .control, .browser]))
        console("locked")
        let status = call(["operation":"grant.status"])["data"] as? [String:Any]
        XCTAssertEqual(broker.activeGrant?.id, grant.id)
        XCTAssertEqual(broker.activeGrant?.expiresAt, grant.expiresAt)
        XCTAssertEqual(status?["effectiveScopes"] as? [String], ["browser"])
        XCTAssertNil(broker.authorize("browser.tabs"))
        XCTAssertTrue(broker.browserAllowed)
        XCTAssertFalse(broker.devtoolsAllowed)
        XCTAssertEqual(broker.authorize("browser.eval")?.code, "approval_required")
        for operation in ["applications", "snapshot", "capture", "input.key", "application.launch", "session.control"] {
            XCTAssertEqual(call(["operation":operation])["errorCode"] as? String, "desktop_locked_browser_only", operation)
        }
        XCTAssertEqual(broker.authorize("input.key", controlled:true, delegatedScopes:[.control])?.code,
                       "desktop_locked_browser_only")
        XCTAssertEqual(broker.admissionAuthority(scopes:[.browser, .control]), "desktop_locked_browser_only")
        XCTAssertNil(broker.admissionAuthority(scopes:[.browser]))
        XCTAssertEqual((call(["operation":"grant.request", "scopes":["browser"], "reason":"reuse"])["data"] as? [String:Any])?["decision"] as? String, "existing_grant")
        for scope in ["observe", "control", "devtools"] {
            XCTAssertEqual(call(["operation":"grant.request", "scopes":[scope], "reason":"more"])["errorCode"] as? String,
                           "approval_unavailable_while_locked")
        }
        console("unlocked")
        _ = call(["operation":"grant.status"])
        XCTAssertEqual(broker.activeGrant?.id, grant.id)
        XCTAssertNil(broker.authorize("input.key"))
    }

    func testLockedBrowserPauseExpiryAndStopRemainEffective() throws {
        try server.configureBrowserWhileLocked(enabled:true)
        var clock = Date()
        broker.now = { clock }
        let grant = try XCTUnwrap(approve([.browser, .devtools]))
        console("locked")
        _ = call(["operation":"grant.status"])
        XCTAssertTrue(broker.devtoolsAllowed)
        XCTAssertNil(broker.authorize("browser.eval"))
        server.devtools.setTokenForTesting("fixture-token")
        let endpoint = WebSocketUpgrade(path:"/devtools/page/1", query:["token":"fixture-token"],
                                       key:"k", origin:nil, host:"127.0.0.1")
        XCTAssertEqual(server.devtools.acceptedTab(endpoint), 1)
        try broker.pause()
        XCTAssertFalse(broker.browserAllowed)
        XCTAssertFalse(broker.devtoolsAllowed)
        XCTAssertNil(server.devtools.acceptedTab(endpoint))
        XCTAssertEqual(broker.authorize("browser.tabs")?.code, "access_paused")
        try broker.resume()
        XCTAssertEqual(broker.activeGrant?.id, grant.id)
        XCTAssertTrue(broker.browserAllowed)
        clock = clock.addingTimeInterval(61)
        _ = call(["operation":"grant.status"])
        XCTAssertNil(broker.activeGrant)
        XCTAssertFalse(broker.browserAllowed)
        console("unlocked")
        _ = approve([.browser, .devtools])
        console("locked")
        _ = call(["operation":"grant.status"])
        server.revoke(reason:"stopped_by_person")
        XCTAssertFalse(broker.browserAllowed)
        XCTAssertFalse(broker.devtoolsAllowed)
    }

    func testDisableLockedBrowserRevokesRetainedGrant() throws {
        try server.configureBrowserWhileLocked(enabled:true)
        _ = approve([.browser])
        console("locked")
        _ = call(["operation":"grant.status"])
        try server.configureBrowserWhileLocked(enabled:false)
        XCTAssertFalse(server.browserWhileLockedEnabled)
        XCTAssertNil(broker.activeGrant)
        XCTAssertFalse(broker.browserAllowed)
    }

    func testBrowserOptInCannotPreserveDesktopOnlyOrUnknownConsole() throws {
        try server.configureBrowserWhileLocked(enabled:true)
        _ = approve([.observe, .control])
        console("locked")
        _ = call(["operation":"grant.status"])
        XCTAssertNil(broker.activeGrant)
        console("unlocked")
        _ = approve([.browser])
        console("locked", uuid:"replacement")
        _ = call(["operation":"grant.status"])
        XCTAssertNil(broker.activeGrant)
        XCTAssertEqual(broker.lastEnded?.reason, "console_session_changed")
        console("unlocked")
        _ = approve([.browser])
        console("unknown")
        _ = call(["operation":"grant.status"])
        XCTAssertNil(broker.activeGrant)
    }

    func testBrowserOptInCannotBindNewApprovalOnLockedConsole() throws {
        try server.configureBrowserWhileLocked(enabled:true)
        console("locked")
        broker.issue(scopes:[.browser], durationSeconds:60, reason:"invalid fixture issue",
                     requester:"fixture", approver:"fixture")
        _ = call(["operation":"grant.status"])
        XCTAssertNil(broker.activeGrant)
        XCTAssertFalse(broker.browserAllowed)
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

    func testCallerRevokeRetainsPersonArmedAccess() throws {
        let directory = FileManager.default.temporaryDirectory.appendingPathComponent("mc-retain-" + UUID().uuidString)
        try FileManager.default.createDirectory(at:directory, withIntermediateDirectories:false, attributes:[.posixPermissions:0o700])
        defer { try? FileManager.default.removeItem(at:directory) }
        let console = server.grantConsoleObservation()
        try OperatorConsentStore(directory:directory.path).enable(scopes:[.observe], duration:nil, console:console)
        broker.consentStore = try OperatorConsentStore(directory:directory.path)
        let armed = broker.issueUntilStopped(scopes:[.observe], reason:"Manually enabled by the person",
                                             requester:"local operator", approver:"local_tauri")
        let status = call(["operation": "grant.status"])
        XCTAssertEqual(((status["data"] as? [String: Any])?["grant"] as? [String: Any])?["origin"] as? String, "person")

        let revoked = call(["operation": "grant.revoke"])
        let data = revoked["data"] as? [String: Any]
        XCTAssertEqual(revoked["accepted"] as? Bool, true, "\(revoked)")
        XCTAssertEqual(data?["revoked"] as? Bool, false)
        XCTAssertEqual(data?["retained"] as? String, "person_armed")
        XCTAssertEqual(broker.activeGrant?.id, armed.id)
        XCTAssertEqual(call(["operation": "applications"])["accepted"] as? Bool, true)
        XCTAssertNotNil(try OperatorConsentStore(directory:directory.path).consent(console:console))
        XCTAssertNil(broker.lastEnded)

        // A request the person's grant covers reuses it.
        XCTAssertEqual((call(["operation": "grant.request", "scopes": ["observe"], "reason": "t"])["data"]
            as? [String: Any])?["decision"] as? String, "existing_grant")
        // An approved request for more replaces it; the caller may end that
        // one, and the person's saved arming survives for restoration.
        let approver = ScriptedApprover(.approved(scopes: [.control], durationSeconds: 600))
        server.approver = approver
        let replaced = call(["operation": "grant.request", "scopes": ["control"], "reason": "t"]); XCTAssertEqual(replaced["accepted"] as? Bool, true, "\(replaced)")
        XCTAssertEqual(broker.activeGrant?.origin, .request)
        let ended = call(["operation": "grant.revoke"])
        XCTAssertEqual((ended["data"] as? [String: Any])?["revoked"] as? Bool, true)
        XCTAssertNil(broker.activeGrant)
        XCTAssertEqual(broker.lastEnded?.reason, "revoked_by_caller")
        XCTAssertNotNil(try OperatorConsentStore(directory:directory.path).consent(console:console))

        // With nothing active, a caller revoke is a harmless no-op.
        XCTAssertEqual((call(["operation": "grant.revoke"])["data"] as? [String: Any])?["revoked"] as? Bool, false)
        XCTAssertNotNil(try OperatorConsentStore(directory:directory.path).consent(console:console))
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
