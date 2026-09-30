import XCTest
@testable import macui

final class DesktopApproverTests: XCTestCase {
    private func request() throws -> GrantRequest {
        try GrantRequest.parse(["requestId":"pending", "scopes":["observe","control"],
            "reason":"test", "durationSeconds":300], caller: CallerIdentity(uid:0, chain:[])).get()
    }
    func testDecisionsCannotWidenOrReplay() throws {
        let approver = DesktopApprover()
        var decisions: [GrantDecision] = []
        approver.present(try request()) { decisions.append($0); approver.dismiss(requestID:"pending") }
        XCTAssertThrowsError(try approver.decide(id:"old",scopes:["observe"],duration:60,allow:true))
        XCTAssertThrowsError(try approver.decide(id:"pending",scopes:["browser"],duration:60,allow:true))
        XCTAssertThrowsError(try approver.decide(id:"pending",scopes:["observe","unknown"],duration:60,allow:true))
        XCTAssertThrowsError(try approver.decide(id:"pending",scopes:["observe"],duration:600,allow:true))
        XCTAssertTrue(decisions.isEmpty)
        try approver.decide(id:"pending",scopes:["observe"],duration:60,allow:true)
        XCTAssertEqual(decisions,[.approved(scopes:[.observe],durationSeconds:60)])
        XCTAssertThrowsError(try approver.decide(id:"pending",scopes:["observe"],duration:60,allow:true))
    }
    func testDismissAndDenialDoNotApprove() throws {
        let approver = DesktopApprover()
        var decisions: [GrantDecision] = []
        approver.present(try request()) { decisions.append($0) }
        approver.dismiss(requestID:"old")
        XCTAssertNotNil(approver.request)
        try approver.decide(id:"pending",scopes:[],duration:0,allow:false)
        XCTAssertEqual(decisions,[.denied])
        approver.dismiss(requestID:"pending")
        XCTAssertThrowsError(try approver.decide(id:"pending",scopes:[],duration:0,allow:false))
    }
}
