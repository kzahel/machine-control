import XCTest
@testable import macui

final class AccessAdmissionTests: XCTestCase {
    func testSharedOwnerCannotBorrowSessionAndPauseNeedsFreshOffer() throws {
        let fixture = try SharedPolicyFixture(), admission = fixture.admission
        try admission.configure("desktop",mode:"automatic",seconds:nil)
        let offer = try admission.submit(owner:"one",requestID:"first",resources:["desktop"],wait:120,duration:60,reason:"Fixture",authority:{ nil })
        let id = try XCTUnwrap(offer["intentId"] as? String)
        let active = try admission.accept(owner:"one",id:id,generation:try XCTUnwrap(offer["offerGeneration"] as? Int))
        let session = try XCTUnwrap(active["sessionId"] as? String), generations = try XCTUnwrap(active["resourceGenerations"] as? [String:Int])
        XCTAssertNil(admission.authorize(owner:"one",id:id,session:session,generations:generations))
        XCTAssertNotNil(admission.authorize(owner:"other",id:id,session:session,generations:generations))
        var endings = 0
        admission.sessionEnded = { _,_,_ in endings += 1 }
        try admission.pause("desktop",reason:"manual")
        XCTAssertNotNil(admission.authorize(owner:"one",id:id,session:session,generations:generations))
        admission.resume("desktop",reason:"manual")
        let next = try admission.inspect(owner:"one",id:id)
        let fresh = try admission.accept(owner:"one",id:id,generation:try XCTUnwrap(next["offerGeneration"] as? Int))
        XCTAssertNotEqual(fresh["sessionId"] as? String,session)
        let before = endings
        admission.receive(["type":"access.event", "event":"yielded", "intentId":id, "sessionId":session])
        XCTAssertEqual(endings,before,"A queued old event cannot end the newly accepted native owner")
    }
    func testAskFirstApprovalIsSpecificAndStopDoesNotRearm() throws {
        let fixture = try SharedPolicyFixture(), admission = fixture.admission
        try admission.configure("desktop",mode:"ask",seconds:nil)
        let value = try admission.submit(owner:"one",requestID:"ask",resources:["desktop"],wait:120,duration:60,reason:"Fixture",authority:{ nil })
        let id = try XCTUnwrap(value["intentId"] as? String)
        XCTAssertEqual(value["state"] as? String,"waiting_for_approval")
        XCTAssertThrowsError(try admission.startNow(id))
        try admission.approve(id)
        XCTAssertEqual(try admission.inspect(owner:"one",id:id)["state"] as? String,"offered")
        admission.stop("operator_stop")
        admission.resume("all",reason:"manual")
        XCTAssertFalse(admission.enabled("desktop"))
    }
    func testNativeRevocationCancelsTheSharedOwner() throws {
        let fixture = try SharedPolicyFixture(), admission = fixture.admission
        try admission.configure("desktop",mode:"automatic",seconds:nil)
        var refusal:String?
        let value = try admission.submit(owner:"one",requestID:"native",resources:["desktop"],wait:120,duration:60,reason:"Fixture",authority:{ refusal })
        let id = try XCTUnwrap(value["intentId"] as? String)
        refusal = "console_session_changed"
        XCTAssertEqual(try admission.inspect(owner:"one",id:id)["state"] as? String,"ended")
        refusal = nil
        XCTAssertThrowsError(try admission.accept(owner:"one",id:id,generation:value["offerGeneration"] as? Int ?? 0))
    }
    func testNativeRenewalAcknowledgesClampedConsentAndFailureEndsOwner() throws {
        let fixture = try SharedPolicyFixture(), admission = fixture.admission
        try admission.configure("desktop",mode:"automatic",seconds:120)
        let value = try admission.submit(owner:"one",requestID:"renew",resources:["desktop"],wait:120,duration:60,reason:"Fixture",authority:{ nil })
        let id = try XCTUnwrap(value["intentId"] as? String)
        let active = try admission.accept(owner:"one",id:id,generation:try XCTUnwrap(value["offerGeneration"] as? Int))
        let session = try XCTUnwrap(active["sessionId"] as? String), generations = try XCTUnwrap(active["resourceGenerations"] as? [String:Int])
        let now = admission.now()
        var deadline = 0.0
        let extended = try admission.renew(owner:"one",id:id,session:session,generations:generations,seconds:900) { deadline = $0 }
        XCTAssertLessThanOrEqual(deadline - now,120.1)
        XCTAssertEqual(extended["sessionId"] as? String,session)
        XCTAssertLessThanOrEqual((extended["activeRemainingSeconds"] as? Double) ?? 901,120)
        // A separate task exercises refusal before an unacknowledged extension.
        try admission.cancel(owner:"one",id:id)
        let next = try admission.submit(owner:"one",requestID:"failed",resources:["desktop"],wait:120,duration:1,reason:"Fixture",authority:{ nil })
        let nextID = try XCTUnwrap(next["intentId"] as? String)
        let nextActive = try admission.accept(owner:"one",id:nextID,generation:try XCTUnwrap(next["offerGeneration"] as? Int))
        XCTAssertThrowsError(try admission.renew(owner:"one",id:nextID,session:try XCTUnwrap(nextActive["sessionId"] as? String),generations:try XCTUnwrap(nextActive["resourceGenerations"] as? [String:Int]),seconds:60) { _ in throw MacUIError.action("helper_unacknowledged") })
        XCTAssertEqual(try admission.inspect(owner:"one",id:nextID)["state"] as? String,"ended")
    }
    func testBrowserConfigurationDoesNotFenceDesktopReferences() throws {
        let fixture = try SharedPolicyFixture(), admission = fixture.admission
        try admission.configure("desktop",mode:"automatic",seconds:nil)
        _ = admission.status
        let revision = admission.availabilityRevision
        try admission.configure("browser",mode:"ask",seconds:nil,profiles:["profile-one"])
        XCTAssertEqual(admission.availabilityRevision,revision)
        try admission.pause("browser",reason:"manual")
        XCTAssertEqual(admission.availabilityRevision,revision)
        try admission.pause("desktop",reason:"manual")
        XCTAssertGreaterThan(admission.availabilityRevision,revision)
    }
}
