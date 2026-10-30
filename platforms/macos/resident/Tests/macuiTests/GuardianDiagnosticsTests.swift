import XCTest
@testable import macui

final class GuardianDiagnosticsTests: XCTestCase {
    private func sample(console: Bool = true, state: GuardianDiagnostics.DesktopState = .unlocked,
                        covers: Bool = true, input: Bool = true, lid: Bool = false,
                        parent: Bool = true, now: Double = 100) -> GuardianDiagnostics {
        GuardianDiagnostics(sameConsole:console, desktopState:state, coversHealthy:covers,
            inputGuardHealthy:input, lidClosed:lid, parentAlive:parent, startedUptime:10,
            observedUptime:now, deadlineUptime:900, parentHeartbeatDeadline:905,
            helperHeartbeatUptime:99)
    }
    func testHealthFaultAndSimultaneousDeadlineAreBothReportedWithoutChangingPrecedence() {
        let value = sample(console:false, state:.unknown, covers:false, input:false, lid:true, parent:false, now:906)
        XCTAssertEqual(value.refusal, "guardian_safety_unavailable")
        XCTAssertEqual(value.failedChecks, ["console_identity_unavailable_or_changed", "session_observation_unknown",
            "covers_unhealthy", "input_guard_unhealthy", "lid_closed", "duration_expired",
            "owner_heartbeat_expired", "parent_gone"])
        XCTAssertEqual(value.json["remainingMs"] as? Int, -6000)
        XCTAssertEqual(value.json["elapsedMs"] as? Int, 896000)
    }
    func testEachPredicateHasAnIndependentRefusalAndNormalExpiryIsClean() {
        XCTAssertNil(sample().refusal)
        for value in [sample(console:false), sample(state:.locked), sample(state:.unknown),
                      sample(covers:false), sample(input:false), sample(lid:true)] {
            XCTAssertEqual(value.refusal, "guardian_safety_unavailable")
            XCTAssertFalse(value.failedChecks.isEmpty)
        }
        XCTAssertEqual(sample(parent:false).refusal, "owner_disconnected")
        XCTAssertEqual(sample(now:900).refusal, "duration_expired")
        XCTAssertTrue(cleanCoveredEnding(sample(now:900).refusal!))
    }
    func testWireDecodingRetainsOnlyClosedDiagnostics() throws {
        var wire = sample().json
        wire["typedText"] = "never retain this"
        wire["console"] = ["uuid":"private identity"]
        let parsed = try XCTUnwrap(GuardianDiagnostics.decode(wire))
        XCTAssertNil(parsed.json["typedText"])
        XCTAssertNil(parsed.json["console"])
        wire["observedUptime"] = -1
        XCTAssertNil(GuardianDiagnostics.decode(wire))
        wire = sample().json; wire["desktopState"] = "private arbitrary text"
        XCTAssertNil(GuardianDiagnostics.decode(wire))
    }
}
