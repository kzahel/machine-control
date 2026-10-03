import XCTest
@testable import macui
final class PhysicalAvailabilityTests: XCTestCase {
    func testUnknownAndClockReversalRefuseAndQuietBoundaryIsExact() {
        XCTAssertEqual(PhysicalAvailability.reason(healthy:false, physicalAt:10, now:100), "activity_unknown")
        XCTAssertEqual(PhysicalAvailability.reason(healthy:true, physicalAt:nil, now:100), "activity_unknown")
        XCTAssertEqual(PhysicalAvailability.reason(healthy:true, physicalAt:10, now:9), "activity_unknown")
        XCTAssertEqual(PhysicalAvailability.reason(healthy:true, physicalAt:10, now:39.999), "physical_activity")
        XCTAssertNil(PhysicalAvailability.reason(healthy:true, physicalAt:10, now:40))
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
