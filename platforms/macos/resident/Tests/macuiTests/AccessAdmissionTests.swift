import XCTest
@testable import macui

final class AccessAdmissionTests: XCTestCase {
    func testRenewalKeepsOwnerAndGenerationAndCannotReviveExpiredAuthority() throws {
        var clock = 0.0
        var denied: String?
        let arbiter = AccessAdmission(); arbiter.now = { clock }; arbiter.register("desktop")
        let submitted = try arbiter.submit(owner:"a", requestID:"renew", resources:["desktop"],
            wait:300, duration:60, reason:"Fixture", authority:{ denied })
        let id = submitted["intentId"] as! String
        let active = try arbiter.accept(owner:"a", id:id, generation:submitted["offerGeneration"] as! Int)
        let session = active["sessionId"] as! String, generations = active["resourceGenerations"] as! [String:Int]
        clock = 4
        var acknowledged: Double?
        let renewed = try arbiter.renew(owner:"a", id:id, session:session, generations:generations, seconds:120) { acknowledged = $0 }
        XCTAssertEqual(acknowledged, 124)
        XCTAssertEqual(renewed["sessionId"] as? String, session)
        XCTAssertEqual(renewed["resourceGenerations"] as? [String:Int], generations)
        XCTAssertEqual(renewed["activeRemainingSeconds"] as? Double, 120)
        XCTAssertThrowsError(try arbiter.renew(owner:"b", id:id, session:session, generations:generations, seconds:120))
        XCTAssertThrowsError(try arbiter.renew(owner:"a", id:id, session:session, generations:["desktop":999], seconds:120))
        denied = "access_ended"
        XCTAssertThrowsError(try arbiter.renew(owner:"a", id:id, session:session, generations:generations, seconds:120))
        denied = nil
        XCTAssertThrowsError(try arbiter.renew(owner:"a", id:id, session:session, generations:generations, seconds:120))
        XCTAssertEqual(try arbiter.inspect(owner:"a", id:id)["state"] as? String, "ended")
    }
    func testFailedRenewalAcknowledgementAndLateHandshakeEndTheOwner() throws {
        for late in [false, true] {
            var clock = 0.0
            let arbiter = AccessAdmission(); arbiter.now = { clock }; arbiter.register("desktop")
            let submitted = try arbiter.submit(owner:"a", requestID:"renew", resources:["desktop"],
                wait:300, duration:60, reason:"Fixture", authority:{ nil })
            let id = submitted["intentId"] as! String
            let active = try arbiter.accept(owner:"a", id:id, generation:submitted["offerGeneration"] as! Int)
            XCTAssertThrowsError(try arbiter.renew(owner:"a", id:id, session:active["sessionId"] as! String,
                generations:active["resourceGenerations"] as! [String:Int], seconds:120) { _ in
                    if late { clock = 61 } else { throw MacUIError.action("renewal_unacknowledged") }
                })
            XCTAssertEqual(try arbiter.inspect(owner:"a", id:id)["state"] as? String, "ended")
        }
    }
    func testComposedPauseAndFreshSession() throws {
        var clock = 0.0
        let admission = AccessAdmission(); admission.now = { clock }; admission.register("desktop")
        let intent = try admission.submit(owner: "a", requestID: "one", resources: ["desktop"],
            wait: 300, duration: 120, reason: "Fixture", authority: { nil })
        let id = intent["intentId"] as! String
        let active = try admission.accept(owner: "a", id: id, generation: intent["offerGeneration"] as! Int)
        let session = active["sessionId"] as! String, generations = active["resourceGenerations"] as! [String: Int]
        XCTAssertNil(admission.authorize(owner: "a", id: id, session: session, generations: generations))
        try admission.pause("desktop", reason: "manual"); try admission.pause("desktop", reason: "activity", seconds: 30)
        admission.resume("desktop", reason: "manual")
        XCTAssertEqual(admission.blocks("desktop"), ["activity"])
        XCTAssertEqual(admission.authorize(owner: "a", id: id, session: session, generations: generations), "stale_control_session")
        var renewalAcknowledged = false
        XCTAssertThrowsError(try admission.renew(owner:"a", id:id, session:session,
            generations:generations, seconds:120) { _ in renewalAcknowledged = true })
        XCTAssertFalse(renewalAcknowledged, "A paused owner must not extend protected deadlines")
        clock = 30
        let offer = try admission.inspect(owner: "a", id: id, heartbeat: true)
        let resumed = try admission.accept(owner: "a", id: id, generation: offer["offerGeneration"] as! Int)
        XCTAssertNotEqual(resumed["sessionId"] as? String, session)
        XCTAssertThrowsError(try admission.renew(owner:"a", id:id, session:session,
            generations:generations, seconds:120))
        XCTAssertThrowsError(try admission.cancel(owner: "b", id: id))
        clock = 35
        XCTAssertEqual(try admission.inspect(owner: "a", id: id, heartbeat: true)["terminalReason"] as? String, "owner_disconnected")
    }
    func testCompleteResourceSetsAndYield() throws {
        let admission = AccessAdmission()
        ["host", "vm-a", "vm-b"].forEach { admission.register($0) }
        let first = try admission.submit(owner: "a", requestID: "one", resources: ["host", "vm-a"],
            wait: 300, duration: 120, reason: "Fixture", authority: { nil })
        let second = try admission.submit(owner: "b", requestID: "two", resources: ["host", "vm-b"],
            wait: 300, duration: 120, reason: "Fixture", authority: { nil })
        XCTAssertEqual(second["state"] as? String, "waiting_for_resource")
        let inner = try admission.submit(owner: "c", requestID: "inner", resources: ["vm-b"],
            wait: 300, duration: 120, reason: "Fixture", authority: { nil })
        XCTAssertEqual(inner["state"] as? String, "offered")
        XCTAssertEqual(try admission.submit(owner: "a", requestID: "one", resources: ["vm-a", "host"],
            wait: 300, duration: 120, reason: "Fixture", authority: { nil })["intentId"] as? String, first["intentId"] as? String)
        XCTAssertThrowsError(try admission.submit(owner: "a", requestID: "one", resources: ["host"],
            wait: 300, duration: 120, reason: "Fixture", authority: { nil }))
    }
    func testIndependentDeadlinesAndNoticeInvalidation() throws {
        var clock = 0.0
        let admission = AccessAdmission(); admission.now = { clock }; admission.register("desktop")
        try admission.pause("desktop", reason: "manual")
        var denied: String?
        let intent = try admission.submit(owner: "a", requestID: "one", resources: ["desktop"],
            wait: 10, duration: 120, reason: "Fixture", authority: { denied })
        let id = intent["intentId"] as! String
        clock = 9; _ = try admission.inspect(owner: "a", id: id, heartbeat: true)
        clock = 10
        XCTAssertEqual(try admission.inspect(owner: "a", id: id)["terminalReason"] as? String, "wait_deadline_exceeded")
        let other = try admission.submit(owner: "a", requestID: "two", resources: ["desktop"],
            wait: 300, duration: 120, reason: "Fixture", authority: { denied })
        denied = "authorization_expired"
        XCTAssertEqual(try admission.inspect(owner: "a", id: other["intentId"] as! String)["terminalReason"] as? String, denied)
        denied = nil; admission.resume("desktop", reason: "manual")
        let notice = try admission.submit(owner: "a", requestID: "notice", resources: ["desktop"],
            wait: 300, duration: 120, reason: "Fixture", authority: { nil }, notice: 10)
        XCTAssertEqual(notice["state"] as? String, "announcing")
        try admission.pause("desktop", reason: "activity", seconds: 30)
        clock = 20
        XCTAssertEqual(try admission.inspect(owner: "a", id: notice["intentId"] as! String)["state"] as? String, "paused")
        admission.disconnect("a")
        XCTAssertThrowsError(try admission.accept(owner: "a", id: notice["intentId"] as! String, generation: notice["offerGeneration"] as! Int))
        XCTAssertThrowsError(try admission.pause("desktop", reason: "bad", seconds: .nan))
    }
    func testNoticeChangesFenceOffersAndNeverReplaceActiveControl() throws {
        var clock = 0.0
        let arbiter = AccessAdmission(); arbiter.now = { clock }; arbiter.register("desktop")
        let intent = try arbiter.submit(owner:"a", requestID:"notice", resources:["desktop"],
            wait:100, duration:60, reason:"Fixture", authority:{ nil }, notice:10)
        let id = intent["intentId"] as! String
        clock = 9
        arbiter.reconfigureNotice(30)
        XCTAssertEqual(try arbiter.inspect(owner:"a", id:id)["noticeRemainingSeconds"] as? Double, 30)
        arbiter.reconfigureNotice(0)
        let offer = try arbiter.inspect(owner:"a", id:id)
        _ = try arbiter.accept(owner:"a", id:id, generation:offer["offerGeneration"] as! Int)
        XCTAssertThrowsError(try arbiter.startNow(id))
        arbiter.reconfigureNotice(10)
        XCTAssertEqual(try arbiter.inspect(owner:"a", id:id)["state"] as? String, "active")
        XCTAssertEqual(try arbiter.submit(owner:"a", requestID:"notice", resources:["desktop"],
            wait:100, duration:60, reason:"Fixture", authority:{ nil }, notice:10)["intentId"] as? String, id)
    }

}
