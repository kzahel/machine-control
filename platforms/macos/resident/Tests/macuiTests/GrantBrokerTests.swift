import XCTest
@testable import macui

final class GrantBrokerTests: XCTestCase {
    private var clock = Date(timeIntervalSince1970: 1_000_000)

    private func broker(_ policy: DeploymentPolicy = .workstation(issue: nil)) -> GrantBroker {
        let value = GrantBroker(policy: policy)
        value.now = { [unowned self] in self.clock }
        return value
    }

    private func request(_ scopes: Set<GrantScope>, duration: Int = 900) -> GrantRequest {
        GrantRequest(id: "r", scopes: scopes, durationSeconds: duration, timeoutSeconds: 30,
                     reason: "test", claimID: nil, caller: CallerIdentity(uid: 0, chain: []))
    }

    func testOperationClasses() {
        XCTAssertEqual(operationClass("status"), .discovery)
        XCTAssertEqual(operationClass("grant.request"), .grantManagement)
        XCTAssertEqual(operationClass("snapshot"), .scoped(.observe))
        XCTAssertEqual(operationClass("input.click"), .scoped(.control))
        XCTAssertEqual(operationClass("browser.tabs"), .scoped(.browser))
        XCTAssertEqual(operationClass("session.unlock"), .protected)
        XCTAssertEqual(operationClass("something.new"), .scoped(.control))
    }

    func testDevtoolsIsSeparateFromBrowser() {
        XCTAssertEqual(operationClass("browser.cdp"), .scoped(.devtools))
        XCTAssertEqual(operationClass("browser.eval"), .scoped(.devtools))
        let broker = broker()
        broker.issue(scopes: [.browser], durationSeconds: 600, reason: "r", requester: "x",
                     approver: "test")
        XCTAssertNil(broker.authorize("browser.tabs"))
        XCTAssertEqual(broker.authorize("browser.cdp")?.requiredScope, .devtools)
        XCTAssertFalse(broker.devtoolsAllowed)
        broker.issue(scopes: [.browser, .devtools], durationSeconds: 600, reason: "r",
                     requester: "x", approver: "test")
        XCTAssertNil(broker.authorize("browser.eval"))
        XCTAssertTrue(broker.devtoolsAllowed)
    }

    func testWorkstationRefusesWithoutGrant() {
        let broker = broker()
        XCTAssertNil(broker.authorize("status"))
        XCTAssertNil(broker.authorize("grant.request"))
        XCTAssertEqual(broker.authorize("snapshot")?.code, "approval_required")
        XCTAssertEqual(broker.authorize("snapshot")?.requiredScope, .observe)
        XCTAssertEqual(broker.authorize("input.key")?.code, "approval_required")
        XCTAssertEqual(broker.authorize("session.unlock")?.code, "operation_not_permitted_by_policy")
    }

    func testStandingPolicyAllowsOrdinaryAndProtected() {
        let appliance = DeploymentPolicy(preset: "appliance", grantMode: .standing,
                                         protectedOperations: true, source: "policy_file", issue: nil)
        let broker = broker(appliance)
        XCTAssertNil(broker.authorize("input.key"))
        XCTAssertNil(broker.authorize("session.unlock"))
        let unprotected = self.broker(DeploymentPolicy(preset: "unattended", grantMode: .standing,
            protectedOperations: false, source: "policy_file", issue: nil))
        XCTAssertEqual(unprotected.authorize("session.unlock")?.code, "operation_not_permitted_by_policy")
    }

    func testGrantScopesAndExpiry() {
        let broker = broker()
        broker.issue(scopes: [.observe], durationSeconds: 120, reason: "r", requester: "x",
                     approver: "test")
        XCTAssertNil(broker.authorize("capture"))
        XCTAssertEqual(broker.authorize("input.text")?.code, "approval_required")
        clock = clock.addingTimeInterval(121)
        XCTAssertEqual(broker.authorize("capture")?.code, "approval_required")
        XCTAssertEqual(broker.lastEnded?.reason, "expired")
    }

    func testRevokeEndsGrant() {
        let broker = broker()
        broker.issue(scopes: [.observe, .control], durationSeconds: 600, reason: "r",
                     requester: "x", approver: "test")
        XCTAssertNil(broker.authorize("input.click"))
        broker.revoke(reason: "stop")
        XCTAssertEqual(broker.authorize("input.click")?.code, "approval_required")
        XCTAssertEqual(broker.lastEnded?.reason, "stop")
    }

    func testPendingPromptPausesControlButNotObservation() {
        let broker = broker()
        broker.issue(scopes: [.observe, .control], durationSeconds: 600, reason: "r",
                     requester: "x", approver: "test")
        XCTAssertNil(broker.beginPending(request([.browser])))
        XCTAssertEqual(broker.authorize("input.click")?.code, "approval_prompt_visible")
        XCTAssertNil(broker.authorize("snapshot"))
        XCTAssertEqual(broker.beginPending(request([.observe]))?.code, "approval_pending")
    }

    func testApprovalCanOnlyNarrow() {
        let broker = broker()
        XCTAssertNil(broker.beginPending(request([.observe], duration: 300)))
        let grant = broker.finishPending(.approved(scopes: [.observe, .control], durationSeconds: 3600),
                                         approver: "test")
        XCTAssertEqual(grant?.scopes, [.observe])
        XCTAssertEqual(grant.map { Int($0.expiresAt.timeIntervalSince(clock)) }, 300)
        XCTAssertNil(broker.pending)
    }

    func testDeniedOrTimedOutIssuesNothing() {
        let broker = broker()
        _ = broker.beginPending(request([.control]))
        XCTAssertNil(broker.finishPending(.denied, approver: "test"))
        _ = broker.beginPending(request([.control]))
        XCTAssertNil(broker.finishPending(.timedOut, approver: "test"))
        XCTAssertNil(broker.grant)
    }

    func testCoveringGrantAvoidsPrompt() {
        let broker = broker()
        broker.issue(scopes: [.observe, .control], durationSeconds: 600, reason: "r",
                     requester: "x", approver: "test")
        XCTAssertNotNil(broker.covering(request([.control])))
        XCTAssertNil(broker.covering(request([.browser])))
    }

    func testRequestParsingBoundsValues() throws {
        let caller = CallerIdentity(uid: 0, chain: [])
        let parsed = try GrantRequest.parse(["scopes": ["control"], "reason": " fix ",
                                             "durationSeconds": 999_999, "timeoutSeconds": 1],
                                            caller: caller).get()
        XCTAssertEqual(parsed.durationSeconds, GrantRequest.durationRange.upperBound)
        XCTAssertEqual(parsed.timeoutSeconds, GrantRequest.timeoutRange.lowerBound)
        XCTAssertEqual(parsed.reason, "fix")
        XCTAssertThrowsError(try GrantRequest.parse(["scopes": ["root"], "reason": "x"],
                                                    caller: caller).get())
        XCTAssertThrowsError(try GrantRequest.parse(["scopes": ["control"]], caller: caller).get())
    }

    func testAuditIsBounded() {
        let broker = broker()
        for index in 0..<150 {
            broker.record(operation: "op\(index)", accepted: false, errorCode: nil,
                          caller: CallerIdentity(uid: 0, chain: []), claimID: nil)
        }
        XCTAssertEqual(broker.audit.count, 100)
        XCTAssertEqual(broker.audit.first?.operation, "op50")
    }
}
