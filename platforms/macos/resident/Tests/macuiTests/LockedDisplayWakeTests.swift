import Darwin
import XCTest
@testable import macui

final class LockedDisplayWakeTests: XCTestCase {
    private var session: [String:Any] { ["desktopState":"locked", "uid":getuid(), "uuid":"console", "boot":123] }

    private final class Harness {
        var time: TimeInterval = 10
        var displayActive = false
        var declareCount = 0
        var released: [UInt32] = []
        var onPause: (() -> Void)?
        func wake(session: [String:Any]) -> LockedDisplayWake {
            var value = LockedDisplayWake()
            value.observation = { session }
            value.lidClosed = { false }
            value.active = { self.displayActive }
            value.now = { self.time }
            value.pause = { self.time += $0; self.onPause?() }
            value.declare = { self.declareCount += 1; return 42 }
            value.release = { self.released.append($0) }
            return value
        }
    }

    func testActiveDisplayDoesNotDeclareActivity() throws {
        let h = Harness(); h.displayActive = true
        try h.wake(session:session).prepare(session:session, deadline:100)
        XCTAssertEqual(h.declareCount,0); XCTAssertTrue(h.released.isEmpty)
    }

    func testStartupDisplayHoldCoversTheBodyWithAKernelTimeout() throws {
        let h = Harness(); h.displayActive = true
        var wake = h.wake(session:session); var durations: [TimeInterval] = []
        wake.hold = { seconds in durations.append(seconds); return 43 }
        let result = try wake.withPreparedDisplay(session:session, deadline:100) {
            XCTAssertTrue(h.released.isEmpty)
            XCTAssertEqual(durations,[12]); XCTAssertEqual(h.declareCount,0)
            return 7
        }
        XCTAssertEqual(result,7); XCTAssertEqual(h.released,[43])
    }

    func testStartupHoldAcquiredBeforeWakeAndReleasedOnBodyFailure() throws {
        let h = Harness(); var events: [String] = []
        var wake = h.wake(session:session)
        wake.hold = { _ in events.append("hold"); return 43 }
        wake.declare = { events.append("wake"); h.displayActive = true; return 42 }
        XCTAssertThrowsError(try wake.withPreparedDisplay(session:session, deadline:100) {
            events.append("body"); XCTAssertEqual(h.released,[42])
            throw MacUIError.action("physical_presence")
        } as Void)
        XCTAssertEqual(events,["hold","wake","body"]); XCTAssertEqual(h.released,[42,43])
    }

    func testStartupHoldUsesRemainingTimeAndReportsItsExpiry() throws {
        let h = Harness(); h.displayActive = true
        var wake = h.wake(session:session); var expired = false
        wake.hold = { seconds in XCTAssertEqual(seconds,2); return 43 }
        wake.holdExpired = { expired = true }
        try wake.withPreparedDisplay(session:session, deadline:12) { h.time = 12 }
        XCTAssertTrue(expired); XCTAssertEqual(h.released,[43])
    }

    func testCancelledOrNearlyExpiredStartupAcquiresNoHold() {
        for cancelled in [false,true] {
            let h = Harness(); var wake = h.wake(session:session)
            wake.hold = { _ in XCTFail("Unusable startup must not acquire a hold"); return 43 }
            wake.cancelled = { cancelled ? "owner_disconnected" : nil }
            XCTAssertThrowsError(try wake.withPreparedDisplay(session:session, deadline:11) {
                XCTFail("Unusable startup body ran")
            })
            XCTAssertTrue(h.released.isEmpty)
        }
    }

    func testStartupHoldReleasedWhenDisplayNeverBecomesActive() {
        let h = Harness(); var wake = h.wake(session:session)
        wake.hold = { _ in 43 }
        XCTAssertThrowsError(try wake.withPreparedDisplay(session:session, deadline:100) {
            XCTFail("Body ran without an active display")
        })
        XCTAssertEqual(h.released,[42,43])
    }

    func testStartupHoldReleasedOnCancellationDuringWake() {
        let h = Harness(); var wake = h.wake(session:session); var cancelled = false
        wake.hold = { _ in 43 }
        wake.cancelled = { cancelled ? "owner_disconnected" : nil }
        h.onPause = { cancelled = true }
        XCTAssertThrowsError(try wake.withPreparedDisplay(session:session, deadline:100) {
            XCTFail("Cancelled body ran")
        })
        XCTAssertEqual(h.released,[42,43])
    }

    func testStartupHoldFailureDoesNotWakeOrRunTheBody() {
        let h = Harness(); var wake = h.wake(session:session)
        wake.hold = { _ in throw MacUIError.action("locked_use_display_hold_failed") }
        XCTAssertThrowsError(try wake.withPreparedDisplay(session:session, deadline:100) {
            XCTFail("Unheld body ran")
        })
        XCTAssertEqual(h.declareCount,0); XCTAssertTrue(h.released.isEmpty)
    }

    func testInactiveDisplayWakesOnceAndReleasesOnReadiness() throws {
        let h = Harness(); h.onPause = { h.displayActive = true }
        try h.wake(session:session).prepare(session:session, deadline:100)
        XCTAssertEqual(h.declareCount,1); XCTAssertEqual(h.released,[42])
    }

    func testMissingReadinessIsBoundedAndReleasesAssertion() {
        let h = Harness()
        XCTAssertThrowsError(try h.wake(session:session).prepare(session:session, deadline:100))
        XCTAssertLessThan(h.time,13.1); XCTAssertEqual(h.released,[42])
    }

    func testTaskDeadlineCannotBeExtendedByWake() {
        let h = Harness()
        XCTAssertThrowsError(try h.wake(session:session).prepare(session:session, deadline:10.1))
        XCTAssertLessThan(h.time,10.2); XCTAssertEqual(h.released,[42])
        let expired = Harness()
        XCTAssertThrowsError(try expired.wake(session:session).prepare(session:session, deadline:10))
        XCTAssertEqual(expired.declareCount,0)
    }

    func testUnknownUnlockedOrForeignConsoleNeverWakes() {
        var other = session; other["uid"] = getuid() + 1
        var unlocked = session; unlocked["desktopState"] = "unlocked"
        var replaced = session; replaced["uuid"] = "other"
        for observation in [[:], other, unlocked, replaced] {
            let h = Harness()
            XCTAssertThrowsError(try h.wake(session:observation).prepare(session:session, deadline:100))
            XCTAssertEqual(h.declareCount,0)
        }
    }

    func testLidClosureOrPhysicalTakeoverNeverWakes() {
        for takeover in [false, true] {
            let h = Harness(); var wake = h.wake(session:session)
            wake.lidClosed = { !takeover }
            wake.cancelled = { takeover ? "physical_presence" : nil }
            XCTAssertThrowsError(try wake.prepare(session:session, deadline:100))
            XCTAssertEqual(h.declareCount,0)
        }
    }

    func testSessionChangeDuringWakeReleasesBeforeProceeding() {
        let h = Harness(); var observation = session; var wake = h.wake(session:session)
        wake.observation = { observation }
        h.onPause = { observation["uuid"] = "other"; h.displayActive = true }
        XCTAssertThrowsError(try wake.prepare(session:session, deadline:100))
        XCTAssertEqual(h.released,[42])
    }

    func testPhysicalTakeoverDuringWakeReleasesAssertion() {
        let h = Harness(); var cancelled = false; var wake = h.wake(session:session)
        wake.cancelled = { cancelled ? "physical_presence" : nil }
        h.onPause = { cancelled = true; h.displayActive = true }
        XCTAssertThrowsError(try wake.prepare(session:session, deadline:100))
        XCTAssertEqual(h.released,[42])
    }

    func testDeclarationFailureDoesNotContinueOrReleaseUnknownID() {
        let h = Harness(); var wake = h.wake(session:session)
        wake.declare = { throw MacUIError.action("locked_use_display_wake_failed") }
        XCTAssertThrowsError(try wake.prepare(session:session, deadline:100))
        XCTAssertTrue(h.released.isEmpty); XCTAssertEqual(h.time,10)
    }
}
