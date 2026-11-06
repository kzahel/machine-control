import XCTest
@testable import macui

final class AccessAdmissionTests: XCTestCase {
    func testDelayedApprovalNeverTurnsMalformedValuesIntoAllowNow() throws {
        XCTAssertEqual(try accessDelaySeconds(nil), 0)
        XCTAssertEqual(try accessDelaySeconds(60), 60)
        for value: Any in ["60", 60.5, true, NSNull(), -1, 28801] { XCTAssertThrowsError(try accessDelaySeconds(value)) }
    }
    func testPreferencesReturnOnlyRuntimeNormalizedPropertyListValues() throws {
        let fixture = try SharedPolicyFixture()
        let normalized = try fixture.admission.preferences(["desktopNoticeSeconds":0, "browserNoticeSeconds":30,
            "yieldWaitSeconds":10, "yieldReapprove":true, "extra":NSNull()])
        XCTAssertNil(normalized["extra"])
        XCTAssertTrue(PropertyListSerialization.propertyList(normalized, isValidFor:.binary))
        XCTAssertEqual(normalized["yieldReapprove"] as? Bool, true)
    }

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
    func testSafetyRefusalsEndIntentsWithTheirOwnReason() throws {
        let fixture = try SharedPolicyFixture(), admission = fixture.admission
        try admission.configure("desktop",mode:"automatic",seconds:nil)
        var refusal: String?
        let offer = try admission.submit(owner:"one",requestID:"audit",resources:["desktop"],wait:120,duration:60,reason:"Fixture",authority:{ refusal })
        let id = try XCTUnwrap(offer["intentId"] as? String)
        _ = try admission.accept(owner:"one",id:id,generation:try XCTUnwrap(offer["offerGeneration"] as? Int))
        refusal = "audit_storage_unavailable"
        let ended = try admission.inspect(owner:"one",id:id)
        XCTAssertEqual(ended["state"] as? String,"ended")
        XCTAssertEqual(ended["terminalReason"] as? String,"audit_storage_unavailable")
        // Other refusals remain a generic cancellation.
        refusal = nil
        let second = try admission.submit(owner:"two",requestID:"other",resources:["desktop"],wait:120,duration:60,reason:"Fixture",authority:{ refusal })
        let next = try XCTUnwrap(second["intentId"] as? String)
        refusal = "desktop_delegation_requires_own_console"
        XCTAssertEqual(try admission.inspect(owner:"two",id:next)["terminalReason"] as? String,"cancelled")
    }
    func testStatusPresentationUsesCachedProjectionAndDropsOnlyOvertakenBackgroundReplies() throws {
        let fixture = try SharedPolicyFixture(), admission = fixture.admission, host = fixture.host
        let lock = NSLock()
        var replies: [() -> Void] = []
        admission.bindBackground { frame, done in
            host.request(frame) { result in lock.lock(); replies.append { done(result) }; lock.unlock() }
        }
        func settle() {
            let deadline = Date().addingTimeInterval(5)
            while admission.polling && Date() < deadline {
                lock.lock(); let ready = replies; replies.removeAll(); lock.unlock()
                ready.forEach { $0() }
                if admission.polling { Thread.sleep(forTimeInterval: 0.01) }
            }
            XCTAssertFalse(admission.polling)
        }
        func cached() -> [String: Any]? { (admission.cachedStatus?["surfaces"] as? [String: [String: Any]])?["desktop"] }
        let mode = { (admission.status["surfaces"] as? [String: [String: Any]])?["desktop"]?["mode"] as? String }
        try admission.configure("desktop", mode: "automatic", seconds: nil)
        XCTAssertEqual(admission.presentation { mode() }, "automatic")
        XCTAssertEqual(admission.presentation { admission.activeDesktop }, false)
        XCTAssertTrue(admission.polling, "Presentation refreshes its cache in the background")
        // A newer full projection supersedes the background reply requested before it.
        try admission.configure("desktop", mode: "off", seconds: nil)
        settle()
        XCTAssertEqual(cached()?["mode"] as? String, "off")
        XCTAssertEqual(admission.presentation { mode() }, "off")
        settle()
        admission.setInputReady(false)
        XCTAssertEqual(admission.cachedStatus?["humanInputReady"] as? Bool, true, "query replies do not replace the cache")
        _ = admission.presentation { mode() }
        // A synchronous housekeeping query is not a full projection, so the
        // background reply requested before it still refreshes the cache.
        admission.setReady("browser", false)
        settle()
        XCTAssertEqual(admission.cachedStatus?["humanInputReady"] as? Bool, false)
        // Cached query derives activeDesktop from an active desktop session.
        try admission.configure("desktop", mode: "automatic", seconds: nil)
        admission.setInputReady(true); admission.setReady("browser", true)
        let offer = try admission.submit(owner: "one", requestID: "cached", resources: ["desktop"], wait: 120,
                                         duration: 60, reason: "Fixture", authority: { nil })
        let id = try XCTUnwrap(offer["intentId"] as? String)
        _ = try admission.accept(owner: "one", id: id, generation: try XCTUnwrap(offer["offerGeneration"] as? Int))
        try admission.configure("browser", mode: "off", seconds: nil)
        XCTAssertEqual(admission.presentation { admission.activeDesktop }, true)
        // Invalidation clears the cache and drops a reply already in flight.
        admission.invalidate()
        XCTAssertNil(admission.cachedStatus)
        XCTAssertFalse(admission.polling)
        lock.lock(); let late = replies; replies.removeAll(); lock.unlock()
        Thread.sleep(forTimeInterval: 0.2)
        lock.lock(); let later = replies; replies.removeAll(); lock.unlock()
        (late + later).forEach { $0() }
        XCTAssertNil(admission.cachedStatus)
    }
    func testSynchronousCancelPreservesCleanEndingBeforeQueuedEvent() throws {
        let fixture = try SharedPolicyFixture(), admission = fixture.admission
        try admission.configure("desktop", mode:"automatic", seconds:nil)
        let offered = try admission.submit(owner:"clean", requestID:"cancel", resources:["desktop"],
            wait:120, duration:60, reason:"Fixture", authority:{ nil })
        let id = try XCTUnwrap(offered["intentId"] as? String)
        let active = try admission.accept(owner:"clean", id:id,
            generation:try XCTUnwrap(offered["offerGeneration"] as? Int))
        let session = try XCTUnwrap(active["sessionId"] as? String)
        var reasons:[String] = []
        admission.sessionEnded = { _, _, reason in reasons.append(reason) }
        try admission.cancel(owner:"clean", id:id)
        XCTAssertEqual(reasons, ["cancelled"])
        XCTAssertTrue(cleanCoveredEnding(coveredAdmissionEnding(try XCTUnwrap(reasons.first))))
        admission.receive(["type":"access.event", "event":"ended", "intentId":id,
                           "sessionId":session, "reason":"cancelled"])
        XCTAssertEqual(reasons, ["cancelled"], "Queued ending cannot release the native owner twice")
        XCTAssertTrue(admission.enabled("desktop"))
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
