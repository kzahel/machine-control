import Foundation
import XCTest
@testable import macui

final class LockedUseTests: XCTestCase {
    private let session: [String:Any] = ["uuid":"console-a", "boot":123, "uid":501]

    private final class Permission: LockedUsePermissionManaging {
        var ready = false
        var approvalState = "not_registered"
        var setupState = "idle"
        var setupError: String?
        var requests = 0
        func request() throws { requests += 1; ready = false; setupState = "installing" }
        func remove() throws {}
        func tick() {}
    }

    func testCheckboxOnlyChangesPreferenceAfterPermissionsAreReady() throws {
        let name = "locked-use-test-\(UUID().uuidString)"
        let defaults = UserDefaults(suiteName:name)!
        defer { defaults.removePersistentDomain(forName:name) }
        let permission = Permission(); permission.ready = true
        let use = MacLockedUse(broker:GrantBroker(policy:.workstation(issue:nil)), service:ResidentService(),
            preferences:defaults, permission:permission, setupObservation:{ ["desktopState":"unlocked"] })
        XCTAssertTrue(use.locallyDisabled)
        try use.configure(enabled:true)
        XCTAssertFalse(use.locallyDisabled)
        try use.configure(enabled:false)
        XCTAssertTrue(use.locallyDisabled)
        try use.configure(enabled:true)
        XCTAssertFalse(use.locallyDisabled)
        XCTAssertEqual(permission.requests,0, "Preference changes must never request a grant")
        XCTAssertEqual(use.setupState,"idle")
    }

    func testMissingPermissionDoesNotTriggerAnInstallationFromCheckbox() {
        let name = "locked-use-test-\(UUID().uuidString)"
        let defaults = UserDefaults(suiteName:name)!
        defer { defaults.removePersistentDomain(forName:name) }
        let permission = Permission()
        let use = MacLockedUse(broker:GrantBroker(policy:.workstation(issue:nil)), service:ResidentService(),
            preferences:defaults, permission:permission, setupObservation:{ ["desktopState":"unlocked"] })
        XCTAssertThrowsError(try use.configure(enabled:true))
        XCTAssertTrue(use.locallyDisabled)
        XCTAssertEqual(permission.requests,0)
        XCTAssertEqual(use.setupState,"idle")
    }

    func testRepairPreservesExistingChoiceButCannotUseUnpreparedHelper() throws {
        let name = "locked-use-test-\(UUID().uuidString)"
        let defaults = UserDefaults(suiteName:name)!
        defer { defaults.removePersistentDomain(forName:name) }
        let permission = Permission(); permission.ready = true
        let use = MacLockedUse(broker:GrantBroker(policy:.workstation(issue:nil)), service:ResidentService(),
            preferences:defaults, permission:permission, setupObservation:{ ["desktopState":"unlocked"] })
        try use.configure(enabled:true)
        try use.preparePermission()
        XCTAssertFalse(use.locallyDisabled)
        XCTAssertFalse(permission.ready)
        XCTAssertFalse(use.enabled)
        XCTAssertEqual(permission.requests,1)
        XCTAssertNil(use.lease)
    }

    func testInitialPreparationLeavesDefaultOffChoiceUntouched() throws {
        let name = "locked-use-test-\(UUID().uuidString)"
        let defaults = UserDefaults(suiteName:name)!
        defer { defaults.removePersistentDomain(forName:name) }
        let permission = Permission()
        let use = MacLockedUse(broker:GrantBroker(policy:.workstation(issue:nil)), service:ResidentService(),
            preferences:defaults, permission:permission, setupObservation:{ ["desktopState":"unlocked"] })
        try use.preparePermission()
        XCTAssertTrue(use.locallyDisabled)
        XCTAssertNil(defaults.object(forKey:"lockedUseLocallyDisabled"))
        XCTAssertNil(use.lease)
    }

    func testASettingCannotAuthorizeControl() {
        let broker = GrantBroker(policy:.workstation(issue:nil))
        XCTAssertEqual(broker.authorize("session.control")?.code, "approval_required")
        XCTAssertEqual(broker.authorize("session.unlock")?.code, "operation_not_permitted_by_policy")
        XCTAssertNil(broker.authorize("session.control.end")) // Stop-only, no authority.
        broker.issue(scopes:[.observe], durationSeconds:300, reason:"View", requester:"test", approver:"local")
        XCTAssertEqual(broker.authorize("session.control")?.code, "approval_required")
    }

    func testLeaseEndsOnRealAuthorityOrIdentityChanges() {
        let lease = ControlSessionLease(id:"session", grantID:"grant", session:session,
            deadline:100, heartbeatDeadline:20)
        XCTAssertNil(lease.refusal(now:10, grantID:"grant", session:session))
        XCTAssertEqual(lease.refusal(now:10, grantID:nil, session:session), "access_ended")
        XCTAssertEqual(lease.refusal(now:10, grantID:"replacement", session:session), "access_ended")
        XCTAssertEqual(lease.refusal(now:20, grantID:"grant", session:session), "owner_disconnected")
        XCTAssertEqual(lease.refusal(now:100, grantID:"grant", session:session), "duration_expired")
        for key in ["uuid", "uid", "boot"] {
            var changed = session; changed[key] = "different"
            XCTAssertEqual(lease.refusal(now:10, grantID:"grant", session:changed), "session_changed")
        }
        XCTAssertEqual(lease.refusal(now:10, grantID:"grant", session:[:]), "session_changed")
    }

    func testUntilStoppedAccessStillHasAFiniteControlLease() {
        let broker = GrantBroker(policy:.workstation(issue:nil))
        let grant = broker.issueUntilStopped(scopes:[.control,.observe], reason:"test", requester:"local", approver:"local")
        let lease = ControlSessionLease(id:"session", grantID:grant.id, session:session,
            deadline:900, heartbeatDeadline:1000)
        XCTAssertNil(grant.expiresAt)
        XCTAssertEqual(lease.refusal(now:900, grantID:grant.id, session:session), "duration_expired")
        XCTAssertNil(ControlSessionLease.duration(901))
        XCTAssertNil(ControlSessionLease.duration(0))
        XCTAssertNil(ControlSessionLease.duration(true))
        XCTAssertNil(ControlSessionLease.duration(1.5))
        XCTAssertNil(ControlSessionLease.duration("300"))
        XCTAssertEqual(ControlSessionLease.duration(300),300)
    }

    func testPreparedLockedUseRetainsAccessDuringIdleLockAndCleanRelock() {
        for phase in ["ready", "waiting_for_lock", "unlocking", "active"] {
            XCTAssertTrue(retainLockedUseAccess(enabled:true, paused:false, phase:phase,
                interruption:nil, endReason:nil))
        }
        for reason in ["completed", "duration_expired"] {
            XCTAssertTrue(retainLockedUseAccess(enabled:true, paused:false, phase:"relocking",
                interruption:reason, endReason:reason))
        }
    }

    func testInterruptionOrMissingOptInCannotRetainAccess() {
        for reason in ["owner_disconnected", "display_changed", "system_sleep", "disabled"] {
            XCTAssertFalse(retainLockedUseAccess(enabled:true, paused:false, phase:"active",
                interruption:reason, endReason:nil))
            XCTAssertFalse(retainLockedUseAccess(enabled:true, paused:false, phase:"relocking",
                interruption:reason, endReason:reason))
        }
        XCTAssertFalse(retainLockedUseAccess(enabled:false, paused:false, phase:"ready", interruption:nil, endReason:nil))
        XCTAssertFalse(retainLockedUseAccess(enabled:true, paused:true, phase:"ready", interruption:nil, endReason:nil))
        for reason in ["physical_presence", "operator_paused"] {
            XCTAssertTrue(retainLockedUseAccess(enabled:true, paused:true, phase:"relocking", interruption:reason, endReason:reason))
            XCTAssertTrue(retainLockedUseAccess(enabled:true, paused:true, phase:"ready", interruption:nil, endReason:reason))
        }
    }

    func testAgentTransportLossIsCleanOnlyThroughHealthyAdmissionOwner() {
        let ending = coveredAdmissionEnding("owner_disconnected")
        XCTAssertEqual(ending, "client_disconnected")
        XCTAssertTrue(cleanCoveredEnding(ending))
        XCTAssertTrue(retainLockedUseAccess(enabled:true, paused:false, phase:"relocking",
            interruption:ending, endReason:ending))
        // An independently detected guardian/resident failure never takes this path.
        XCTAssertFalse(cleanCoveredEnding("owner_disconnected"))
        XCTAssertFalse(cleanCoveredEnding("watchdog_interrupted"))
        XCTAssertEqual(coveredAdmissionEnding("watchdog_interrupted"), "watchdog_interrupted")
        XCTAssertEqual(coveredAdmissionEnding("paused"), "operator_paused")
    }

    func testRetainedGrantIsBoundToTheApprovingConsole() throws {
        let observation: [String:Any] = ["desktopState":"unlocked", "uuid":"console-a", "boot":123, "uid":getuid()]
        let binding = try XCTUnwrap(GrantConsoleBinding(grantID:"grant-a", observation:observation))
        var locked = observation; locked["desktopState"] = "locked"
        XCTAssertTrue(binding.matches(grantID:"grant-a", observation:locked))
        XCTAssertFalse(binding.matches(grantID:"grant-b", observation:locked))
        for key in ["uuid", "boot", "uid"] {
            var replacement = locked; replacement[key] = "changed"
            XCTAssertFalse(binding.matches(grantID:"grant-a", observation:replacement))
        }
        XCTAssertFalse(binding.matches(grantID:"grant-a", observation:[:]))
        XCTAssertNil(GrantConsoleBinding(grantID:"grant-a", observation:locked))
        XCTAssertNil(GrantConsoleBinding(grantID:"grant-a", observation:[:]))
        var otherUser = observation; otherUser["uid"] = getuid() + 1
        XCTAssertNil(GrantConsoleBinding(grantID:"grant-a", observation:otherUser))
    }

    func testUnknownStateIsNotProofOfConsoleReplacement() {
        XCTAssertFalse(consoleSessionReplaced(session, [:]))
        XCTAssertFalse(consoleSessionReplaced(session, session))
        var replacement = session; replacement["uuid"] = "console-b"
        XCTAssertTrue(consoleSessionReplaced(session, replacement))
    }

    func testTakeoverLatchSurvivesFurtherEventsUntilCleanup() {
        let safety = LockedUseSafety()
        XCTAssertFalse(safety.interrupt("physical_presence"))
        safety.arm()
        XCTAssertTrue(safety.interrupt("physical_presence"))
        XCTAssertFalse(safety.interrupt("other_event"))
        XCTAssertEqual(safety.reason,"physical_presence")
        XCTAssertTrue(safety.blocksPhysicalInput)
        safety.disarm()
        XCTAssertNil(safety.reason)
        XCTAssertFalse(safety.blocksPhysicalInput)
    }

    func testPhysicalEventsAndNativeAgentEventsAreDistinct() {
        XCTAssertTrue(LockedUseSafety.physical(sourcePID:0))
        XCTAssertTrue(LockedUseSafety.physical(sourcePID:-1))
        XCTAssertFalse(LockedUseSafety.physical(sourcePID:123))
    }
}
