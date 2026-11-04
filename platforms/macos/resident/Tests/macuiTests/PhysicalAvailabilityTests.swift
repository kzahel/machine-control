import XCTest
import CoreGraphics
@testable import macui
final class PhysicalAvailabilityTests: XCTestCase {
    func testPointerMotionIsNotDeliberateTakeover() {
        for type in [CGEventType.mouseMoved, .leftMouseDragged, .rightMouseUp, .keyUp] {
            XCTAssertFalse(LockedUseSafety.deliberate(type))
        }
        for type in [CGEventType.keyDown, .leftMouseDown, .rightMouseDown, .scrollWheel] {
            XCTAssertTrue(LockedUseSafety.deliberate(type))
        }
    }
    func testPhysicalInputDuringDispatchIsVisibleWithoutMainQueueTick() {
        let activity = PhysicalAvailability(); activity.enable()
        var time = 100.0; activity.now = { time }
        activity.recordPhysical(); activity.arm(baseline:100)
        XCTAssertNil(activity.interruption)
        time = 101; activity.recordPhysical()
        XCTAssertEqual(activity.interruption, "physical_presence")
        activity.disarm(); XCTAssertNil(activity.interruption)
    }
    func testSyntheticClassificationAndThreadSafeActivityTimestamp() {
        XCTAssertFalse(LockedUseSafety.physical(sourcePID:321))
        XCTAssertTrue(LockedUseSafety.physical(sourcePID:0))
        let activity = PhysicalAvailability(); activity.now = { 123 }
        activity.recordPhysical(); XCTAssertEqual(activity.physicalAt, 123)
    }
}
