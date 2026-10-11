import Foundation
import XCTest
@testable import macui

final class BackgroundObservationTests: XCTestCase {
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
