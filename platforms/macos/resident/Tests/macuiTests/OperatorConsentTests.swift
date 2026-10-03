import Darwin
import XCTest
@testable import macui

final class OperatorConsentTests: XCTestCase {
    private var directory: URL!
    private var console: [String:Any] { ["desktopState":"unlocked", "uid":getuid(), "uuid":"fixture-console", "boot":123] }
    private var wall = Date(timeIntervalSince1970:1000)
    private var time = 100.0
    override func setUpWithError() throws {
        directory = FileManager.default.temporaryDirectory.appendingPathComponent("mc-consent-" + UUID().uuidString)
        try FileManager.default.createDirectory(at:directory, withIntermediateDirectories:false, attributes:[.posixPermissions:0o700])
    }
    override func tearDownWithError() throws { try FileManager.default.removeItem(at:directory) }
    private func store() throws -> OperatorConsentStore {
        let value = try OperatorConsentStore(directory:directory.path)
        value.now = { [unowned self] in self.wall }; value.uptime = { [unowned self] in self.time }
        return value
    }
    func testUntilStoppedRestoresConsentWithNoOldAuthorityAndStopSurvivesRestart() throws {
        let first = try store()
        try first.enable(scopes:[.observe, .control], duration:nil, console:console)
        try first.pause(seconds:nil)
        let second = try store()
        var locked = console; locked["desktopState"] = "locked"
        XCTAssertEqual(second.consent(console:locked)?.0, [.observe, .control])
        XCTAssertNil(second.consent(console:locked)?.1)
        XCTAssertEqual(second.manualPauseRemaining, 0)
        let data = try Data(contentsOf:URL(fileURLWithPath:first.path))
        let json = String(decoding:data, as:UTF8.self)
        for forbidden in ["grantId", "sessionId", "intentId", "token", "offerGeneration"] { XCTAssertFalse(json.contains(forbidden)) }
        let attributes = try FileManager.default.attributesOfItem(atPath:first.path)
        XCTAssertEqual((attributes[.posixPermissions] as? NSNumber)?.intValue, 0o600)
        try second.disable()
        let third = try store()
        XCTAssertNil(third.consent(console:console)); XCTAssertEqual(third.manualPauseRemaining, 0)
        try third.resume(); XCTAssertNil(try store().manualPauseRemaining)
    }
    func testExactConsoleBindingDoesNotTransferAcrossLogoutBootOrUser() throws {
        let value = try store(); try value.enable(scopes:[.control], duration:nil, console:console)
        for key in ["uuid", "boot", "uid"] {
            var other = console; other[key] = key == "uuid" ? "other" : 999
            XCTAssertNil(value.consent(console:other))
        }
    }
    func testTimedConsentAndPauseDoNotRenewOnRestartAndUncertainTimingBlocks() throws {
        let value = try store(); try value.enable(scopes:[.observe], duration:60, console:console)
        try value.pause(seconds:30)
        wall.addTimeInterval(29); time += 29
        let restored = try store()
        XCTAssertEqual(restored.consent(console:console)?.1, 31)
        XCTAssertEqual(restored.manualPauseRemaining, 1)
        wall.addTimeInterval(31); time += 31
        XCTAssertNil(try store().consent(console:console)); XCTAssertNil(try store().manualPauseRemaining)
        wall = Date(timeIntervalSince1970:1000); time = 100
        try value.enable(scopes:[.observe], duration:60, console:console); try value.pause(seconds:30)
        wall.addTimeInterval(20); time += 1
        XCTAssertNil(try store().consent(console:console)); XCTAssertEqual(try store().manualPauseRemaining, 0)
    }
    func testUnboundedConsentNeedsIdentityRatherThanAnExpiryClock() throws {
        let value = try store(); try value.enable(scopes:[.observe], duration:nil, console:console)
        wall.addTimeInterval(1000)
        XCTAssertEqual(try store().consent(console:console)?.0, [.observe])
    }
    func testDeferralIsResourceWideAndDoesNotRenewOnRestart() throws {
        let first = try store()
        try first.pause(seconds:nil)
        try first.pause(seconds:60, deferral:true)
        wall.addTimeInterval(59); time += 59
        let restarted = try store()
        XCTAssertEqual(restarted.deferralRemaining, 1)
        XCTAssertEqual(restarted.manualPauseRemaining, 0)
        wall.addTimeInterval(1); time += 1
        XCTAssertNil(try store().deferralRemaining)
        XCTAssertEqual(try store().manualPauseRemaining, 0)
        try restarted.resume()
        XCTAssertNil(try store().deferralRemaining)
        XCTAssertNil(try store().manualPauseRemaining)
    }
    func testStopClearsSavedConsentEvenBeforeReadinessAllowsRestoration() throws {
        let saved = try store()
        try saved.enable(scopes:[.control], duration:nil, console:console)
        let broker = GrantBroker(policy:.workstation(issue:nil))
        broker.consentStore = try store()
        XCTAssertNil(broker.grant)
        broker.revoke(reason:"stopped_by_person")
        XCTAssertNil(try store().consent(console:console))
    }
    func testRestoredTimedGrantUsesExactRemainingLifetimeAndNewIdentity() throws {
        let broker = GrantBroker(policy:.workstation(issue:nil))
        broker.now = { [unowned self] in self.wall }
        let original = broker.issue(scopes:[.observe], durationSeconds:60,
            reason:"fixture", requester:"operator", approver:"fixture")
        broker.revoke(reason:"operator_quit")
        let restored = try XCTUnwrap(broker.restoreConsent(scopes:[.observe], remainingSeconds:1))
        XCTAssertNotEqual(original.id, restored.id)
        XCTAssertEqual(restored.expiresAt?.timeIntervalSince(wall), 1)
        wall.addTimeInterval(1)
        XCTAssertNil(broker.activeGrant)
    }
    func testInsecureFileAndSymlinkRefuseAndDoNotFollow() throws {
        let value = try store(); try value.pause(seconds:nil)
        XCTAssertEqual(chmod(value.path, 0o644), 0)
        XCTAssertThrowsError(try store())
        try FileManager.default.removeItem(atPath:value.path)
        let outside = directory.appendingPathComponent("outside")
        try Data("fixture".utf8).write(to:outside)
        try FileManager.default.createSymbolicLink(atPath:value.path, withDestinationPath:outside.path)
        XCTAssertThrowsError(try store())
        XCTAssertEqual(try String(contentsOf:outside, encoding:.utf8), "fixture")
    }
}
