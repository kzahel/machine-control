import XCTest
@testable import macui

final class DesktopUpdatesTests: XCTestCase {
    func testOnlyDesktopOperatorEnablesDiscoveryAndRequestsCoalesce() {
        let updates = DesktopUpdates()
        XCTAssertNil(updates.request(check: true))
        XCTAssertFalse(updates.sync(["checking": false, "installing": false, "phase": "idle"]))
        XCTAssertEqual(updates.request(check: true)?["queued"] as? Bool, true)
        XCTAssertEqual(updates.request(check: true)?["queued"] as? Bool, true)
        XCTAssertTrue(updates.sync(["checking": true, "installing": false, "phase": "checking"]))
        XCTAssertEqual(updates.request(check: true)?["queued"] as? Bool, false)
        XCTAssertFalse(updates.sync(["checking": false, "installing": true, "phase": "installing"]))
        XCTAssertEqual(updates.request(check: true)?["queued"] as? Bool, false)
        XCTAssertFalse(updates.sync(["checking": false, "installing": false, "phase": "available",
            "availableVersion": "1.2.3"]))
        XCTAssertEqual((updates.request(check: false)?["update"] as? [String: Any])?["availableVersion"] as? String, "1.2.3")
        XCTAssertFalse(updates.sync(["checking": false])) // Status never queues a check.
    }
}
