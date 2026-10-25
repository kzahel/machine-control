import Darwin
import XCTest
@testable import macui

final class OperatorConsentTests: XCTestCase {
    func testRestorationWaitsForRootCleanupEvenBeforeFaultPauseIsPublished() {
        var helper: [String:Any] = ["installation":"healthy", "coveredSession":true, "lockedUsePaused":false]
        XCTAssertFalse(helperAllowsConsentRestoration(helper, recoveryPending:false))
        helper["coveredSession"] = false
        XCTAssertTrue(helperAllowsConsentRestoration(helper, recoveryPending:false))
        XCTAssertFalse(helperAllowsConsentRestoration(helper, recoveryPending:true))
        helper.removeValue(forKey:"coveredSession")
        XCTAssertFalse(helperAllowsConsentRestoration(helper, recoveryPending:false))
        helper["coveredSession"] = false; helper["lockedUsePaused"] = true
        helper["lockedUsePauseReason"] = "watchdog_interrupted"
        XCTAssertFalse(helperAllowsConsentRestoration(helper, recoveryPending:false))
        helper["lockedUsePauseReason"] = "physical_presence"
        XCTAssertTrue(helperAllowsConsentRestoration(helper, recoveryPending:false))
        XCTAssertTrue(helperAllowsConsentRestoration(["installation":"missing"], recoveryPending:false))
        XCTAssertFalse(helperAllowsConsentRestoration([:], recoveryPending:false))
    }
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
    func testOnlyThePersonsStopClearsSavedConsent() throws {
        try store().enable(scopes:[.observe, .control], duration:nil, console:console)
        let broker = GrantBroker(policy:.workstation(issue:nil))
        broker.consentStore = try store()
        broker.issueUntilStopped(scopes:[.observe, .control], reason:"manual",
                                 requester:"local operator", approver:"local_tauri")
        // A caller's revoke never clears the person's arming.
        broker.revoke(reason:"revoked_by_caller")
        XCTAssertNotNil(try store().consent(console:console))
        // An agent-request grant replacing it may expire or be fenced away.
        broker.issue(scopes:[.observe], durationSeconds:60, reason:"agent", requester:"agent", approver:"test")
        broker.revoke(reason:"expired")
        XCTAssertNotNil(try store().consent(console:console))
        broker.issue(scopes:[.observe], durationSeconds:60, reason:"agent", requester:"agent", approver:"test")
        broker.fence(); broker.revoke(reason:"console_session_changed")
        XCTAssertNotNil(try store().consent(console:console))
        // The person's own Stop clears it whatever is active.
        broker.issue(scopes:[.observe], durationSeconds:60, reason:"agent", requester:"agent", approver:"test")
        broker.fence(); broker.revoke(reason:"stopped_from_menu")
        XCTAssertNil(try store().consent(console:console))
    }
    func testOnlyExplicitAuthorityTransitionsClearConsent() {
        XCTAssertTrue(GrantBroker.clearsConsent(reason:"stopped_by_hotkey", ending:.request))
        XCTAssertTrue(GrantBroker.clearsConsent(reason:"stopped_by_person", ending:nil))
        XCTAssertTrue(GrantBroker.clearsConsent(reason:"console_session_changed", ending:.person, consent:.invalidate))
        XCTAssertTrue(GrantBroker.clearsConsent(reason:"expired", ending:.person, consent:.invalidate))
        for reason in ["unlock_password_panel_unavailable_login_window_ambiguous", "future_unknown_fault", "guardian_disconnected"] {
            XCTAssertFalse(GrantBroker.clearsConsent(reason:reason, ending:.person))
        }
        XCTAssertFalse(GrantBroker.clearsConsent(reason:"desktop_locked", ending:.person))
        XCTAssertFalse(GrantBroker.clearsConsent(reason:"revoked_by_caller", ending:.person))
        XCTAssertFalse(GrantBroker.clearsConsent(reason:"revoked_by_caller", ending:nil))
        XCTAssertFalse(GrantBroker.clearsConsent(reason:"expired", ending:.request))
    }
    func testCoveredStartupFaultPreservesDurableArmingAcrossRestart() throws {
        try store().enable(scopes:[.observe,.control,.browser,.devtools], duration:nil, console:console)
        let broker = GrantBroker(policy:.workstation(issue:nil))
        broker.consentStore = try store()
        broker.issueUntilStopped(scopes:[.observe,.control,.browser,.devtools], reason:"manual",
                                 requester:"local operator", approver:"local")
        broker.revoke(reason:"unlock_password_panel_unavailable_login_window_ambiguous")
        XCTAssertNotNil(try store().consent(console:console))
        broker.revoke(reason:"console_session_changed", consent:.invalidate)
        XCTAssertNil(try store().consent(console:console))
    }
    func testIncompleteProbeThenUserSwitchCannotRestoreOldConsent() throws {
        let saved = try store()
        try saved.enable(scopes:[.control,.browser], duration:nil, console:console)
        for incomplete: [String:Any] in [
            ["desktopState":"unknown"],
            ["desktopState":"unknown", "uuid":NSNull(), "boot":NSNull(), "uid":NSNull()],
            ["desktopState":"unknown", "uuid":"", "boot":123, "uid":getuid()],
            ["desktopState":"unknown", "uuid":"other", "boot":"unknown", "uid":getuid()]
        ] {
            try saved.invalidateReplacedConsole(incomplete)
            XCTAssertNotNil(saved.consent(console:console))
        }
        var other = console; other["uuid"] = "other-console"
        try saved.invalidateReplacedConsole(other)
        XCTAssertNil(try store().consent(console:console))
    }
    func testLockedBrowserRestorationCannotCarryDesktopAuthorityPastFaults() {
        let original: Set<GrantScope> = [.observe,.control,.browser,.devtools]
        let browser = restorableConsentScopes(original, state:"locked", browserEnabled:true,
            lockedUseEnabled:true, helperEligible:false, desktopPermissions:false)
        XCTAssertEqual(browser, [.browser,.devtools])
        XCTAssertFalse(browser.contains(.control))
        XCTAssertEqual(restorableConsentScopes(original, state:"unlocked", browserEnabled:true,
            lockedUseEnabled:true, helperEligible:false, desktopPermissions:true), [])
        XCTAssertEqual(restorableConsentScopes(original, state:"unlocked", browserEnabled:true,
            lockedUseEnabled:true, helperEligible:true, desktopPermissions:true), original)
    }
    func testUnavailableRestoredScopesReportReadinessInsteadOfNewApproval() {
        let broker = GrantBroker(policy:.workstation(issue:nil))
        _ = broker.restoreConsent(scopes:[.browser], remainingSeconds:nil)
        broker.restorationBlockedScopes = [.observe,.control]
        XCTAssertNil(broker.authorize("browser.tabs"))
        XCTAssertEqual(broker.authorize("input.key")?.code, "access_temporarily_unavailable")
        XCTAssertEqual(broker.admissionAuthority(scopes:[.control]), "access_temporarily_unavailable")
        broker.issueUntilStopped(scopes:[.browser], reason:"new choice", requester:"local", approver:"local")
        XCTAssertTrue(broker.restorationBlockedScopes.isEmpty)
        XCTAssertEqual(broker.authorize("input.key")?.code, "approval_required")
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
