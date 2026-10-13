import Foundation
import XCTest
@testable import macui

final class BackgroundObservationTests: XCTestCase {
    func testResidentPollCannotRollBackFreshSessionObservation() throws {
        let complete = expectation(description:"locked poll completed")
        let locked: [String:Any] = ["desktopState":"locked", "uuid":"console", "boot":123, "uid":getuid()]
        var unlocked = locked; unlocked["desktopState"] = "unlocked"
        let service = ResidentService()
        service.sessionObservation = BackgroundObservation(label:"test.session.rollback", interval:100,
            unknown:{ ["desktopState":"unknown"] }, read:{ locked })
        service.helperObservation = BackgroundObservation(label:"test.helper.rollback",
            unknown:{ [:] }, read:{ [:] })
        defer { service.stopObservations() }
        service.sessionObservation.changed = { complete.fulfill() }
        service.sessionObservation.refresh(); wait(for:[complete], timeout:1)
        service.sessionObservation.changed = nil
        service.applySessionObservation(try coveredActivationObservation(unlocked, initial:locked))
        service.refreshObservations()
        XCTAssertEqual(service.observedDesktopState,"unlocked",
            "A pre-unlock cached poll must not overwrite the fresh native observation")
    }

    func testProjectedPollDoesNotExtendFreshObservationLifetime() {
        let complete = expectation(description:"initial poll completed")
        var time = 100.0
        let session: [String:Any] = ["desktopState":"unlocked", "uuid":"console", "boot":123, "uid":getuid()]
        let service = ResidentService()
        service.sessionObservation = BackgroundObservation(label:"test.session.expiry", interval:100, lifetime:1,
            unknown:{ ["desktopState":"unknown"] }, read:{ session })
        service.sessionObservation.now = { time }
        service.helperObservation = BackgroundObservation(label:"test.helper.expiry",
            unknown:{ [:] }, read:{ [:] })
        defer { service.stopObservations() }
        service.sessionObservation.changed = { complete.fulfill() }
        service.sessionObservation.refresh(); wait(for:[complete], timeout:1)
        service.sessionObservation.changed = nil
        service.applySessionObservation(session)
        for _ in 0..<3 {
            time += 0.25; service.refreshObservations()
            XCTAssertEqual(service.observedDesktopState,"unlocked")
        }
        time += 0.5; service.refreshObservations()
        XCTAssertEqual(service.observedDesktopState,"unknown",
            "Reading a cache must never renew the evidence lifetime")
    }

    func testReplacementRetainsWorkerCapacityAndCannotReviveStoppedObserver() {
        let started = expectation(description:"old read started")
        let drained = expectation(description:"old read drained")
        let release = DispatchSemaphore(value:0)
        let value = BackgroundObservation<Int>(label:"test.replace.capacity", interval:100,
            unknown:{ -1 }, read:{ started.fulfill(); release.wait(); return 42 })
        defer { release.signal(); value.stop() }
        value.refresh(); wait(for:[started], timeout:1)
        value.replace(with:84)
        for _ in 0..<100 { value.refresh() }
        XCTAssertEqual(value.metadata["refreshing"] as? Bool,true)
        XCTAssertEqual(value.value,84)
        release.signal()
        DispatchQueue.main.asyncAfter(deadline:.now() + 0.1) { drained.fulfill() }
        wait(for:[drained], timeout:1)
        XCTAssertEqual(value.metadata["refreshing"] as? Bool,false)
        XCTAssertEqual(value.value,84,"The older completion must not restore its stale value")
        value.stop(); value.replace(with:99)
        XCTAssertEqual(value.value,-1)
    }

    func testLatePollCannotReplaceNewerRequestObservation() {
        let started = expectation(description:"pre-transition poll started")
        let drained = expectation(description:"old poll drained")
        let release = DispatchSemaphore(value:0)
        let locked: [String:Any] = ["desktopState":"locked", "uuid":"console", "boot":123, "uid":getuid()]
        var unlocked = locked; unlocked["desktopState"] = "unlocked"
        let service = ResidentService()
        service.sessionObservation = BackgroundObservation(label:"test.session.late", interval:100,
            unknown:{ ["desktopState":"unknown"] }, read:{ started.fulfill(); release.wait(); return locked })
        service.helperObservation = BackgroundObservation(label:"test.helper.late",
            unknown:{ [:] }, read:{ [:] })
        defer { release.signal(); service.stopObservations() }
        service.sessionObservation.refresh(); wait(for:[started], timeout:1)
        service.applySessionObservation(unlocked)
        release.signal()
        DispatchQueue.main.asyncAfter(deadline:.now() + 0.1) { drained.fulfill() }
        wait(for:[drained], timeout:1)
        service.refreshObservations()
        XCTAssertEqual(service.observedDesktopState,"unlocked",
            "A read begun before a newer native result must not retarget the console")
    }

    func testBlockedDependencyCannotBlockMainQueueOrAccumulateWorkers() {
        let started = expectation(description:"worker started")
        let responsive = expectation(description:"main queue responsive")
        let expired = expectation(description:"deadline expired")
        let release = DispatchSemaphore(value:0)
        defer { release.signal() }
        let value = BackgroundObservation<Int>(label:"test.blocked", timeout:0.05,
            unknown:{ -1 }, read:{ started.fulfill(); release.wait(); return 42 })
        value.changed = { expired.fulfill() }; value.refresh()
        DispatchQueue.main.async { responsive.fulfill() }
        wait(for:[started, responsive, expired], timeout:1)
        XCTAssertEqual(value.value, -1)
        for _ in 0..<100 { value.refresh() }
        XCTAssertEqual(value.metadata["refreshing"] as? Bool, true)
        value.changed = nil; release.signal()
        let drained = expectation(description:"late result drained")
        DispatchQueue.main.asyncAfter(deadline:.now() + 0.1) { drained.fulfill() }
        wait(for:[drained], timeout:1)
        XCTAssertEqual(value.value, -1, "A timed-out observation must not become current")
        XCTAssertEqual(value.metadata["refreshing"] as? Bool, false)
        value.stop()
    }

    func testInvalidationAndStopDiscardOldCompletions() {
        let started = expectation(description:"worker started")
        let release = DispatchSemaphore(value:0)
        defer { release.signal() }
        let value = BackgroundObservation<Int>(label:"test.invalidate", unknown:{ -1 },
            read:{ started.fulfill(); release.wait(); return 42 })
        value.refresh(); wait(for:[started], timeout:1)
        value.invalidate(); value.stop(); release.signal()
        let drained = expectation(description:"worker drained")
        DispatchQueue.main.asyncAfter(deadline:.now() + 0.1) { drained.fulfill() }
        wait(for:[drained], timeout:1)
        XCTAssertEqual(value.value, -1)
        value.refresh()
        XCTAssertEqual(value.metadata["refreshing"] as? Bool, false)
    }

    func testExpiredSnapshotBecomesUnknown() {
        let complete = expectation(description:"observation complete")
        var time = 100.0
        let value = BackgroundObservation<Int>(label:"test.freshness", lifetime:1,
            unknown:{ -1 }, read:{ 42 })
        value.now = { time }; value.changed = { complete.fulfill() }
        value.refresh(); wait(for:[complete], timeout:1)
        XCTAssertEqual(value.value, 42); time += 2
        XCTAssertEqual(value.value, -1)
        XCTAssertEqual(value.metadata["available"] as? Bool, false)
        value.stop()
    }

    func testResidentTicksAndStopRemainResponsiveWithBlockedHelper() throws {
        let started = expectation(description:"helper reading")
        let release = DispatchSemaphore(value:0)
        defer { release.signal() }
        let service = ResidentService()
        service.helperObservation = BackgroundObservation(label:"test.resident.helper",
            unknown:{ ["installation":"unknown"] }, read:{
                started.fulfill(); release.wait(); return ["installation":"healthy"]
            })
        let broker = GrantBroker(policy:DeploymentPolicy.load(path:"/nonexistent/test-policy"))
        let server = ResidentServer(socketPath:"/nonexistent/test-socket", service:service, broker:broker)
        server.refreshAdmission()
        wait(for:[started], timeout:1)
        for _ in 0..<100 { server.refreshAdmission() }
        let stopped = expectation(description:"Stop processed on main queue")
        DispatchQueue.main.async { broker.revoke(reason:"stopped_by_person"); server.stop(); stopped.fulfill() }
        wait(for:[stopped], timeout:1)
        XCTAssertNil(broker.grant)
        XCTAssertEqual(service.displayedUnlockStatus["installation"] as? String, "unknown")
    }
}
