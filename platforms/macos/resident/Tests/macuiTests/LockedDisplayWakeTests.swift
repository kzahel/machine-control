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
