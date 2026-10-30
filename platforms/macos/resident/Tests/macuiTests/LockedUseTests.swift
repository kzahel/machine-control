import Foundation
import Darwin
import XCTest
@testable import macui

final class LockedUseTests: XCTestCase {
    private let session: [String:Any] = ["uuid":"console-a", "boot":123, "uid":501]

    func testOnlyIndependentlyLockedStartupCanPrepareAnAsleepDisplay() {
        for phase in ["waiting_for_lock","unlocking"] {
            XCTAssertFalse(displaySleepEndsControl(startedLocked:true,phase:phase,observedState:"locked"))
            for state in ["unlocked","unknown",""] {
                XCTAssertTrue(displaySleepEndsControl(startedLocked:true,phase:phase,observedState:state))
            }
            XCTAssertTrue(displaySleepEndsControl(startedLocked:false,phase:phase,observedState:"locked"))
        }
        for phase in ["active","relocking","off"] {
            for state in ["locked","unlocked","unknown"] {
                XCTAssertTrue(displaySleepEndsControl(startedLocked:true,phase:phase,observedState:state))
            }
        }
    }

    func testGuardianStartupWaitLeavesTheMainQueueResponsive() {
        let ready = DispatchSemaphore(value:0)
        let responsive = expectation(description:"main queue services startup heartbeat")
        let completed = expectation(description:"activation delivered on main")
        awaitGuardianStartup(ready, timeout:1, result:{ ["desktopState":"unlocked"] }) { result in
            XCTAssertTrue(Thread.isMainThread)
            XCTAssertEqual(try? result.get()["desktopState"] as? String,"unlocked")
            completed.fulfill()
        }
        DispatchQueue.main.async { responsive.fulfill(); ready.signal() }
        wait(for:[responsive,completed],timeout:0.5)
    }

    func testGuardianStartupTimeoutNeverReadsAnActivationResult() {
        let completed = expectation(description:"bounded startup failure")
        awaitGuardianStartup(DispatchSemaphore(value:0), timeout:0.02, result:{
            XCTFail("A timed-out handshake must not adopt activation")
            return [:]
        }) { result in
            XCTAssertTrue(Thread.isMainThread)
            if case .success = result { XCTFail("Missing acknowledgement must fail") }
            completed.fulfill()
        }
        wait(for:[completed],timeout:1)
    }

    func testCoveredHelperSilenceIsToleratedOnlyWithinItsBound() {
        var liveness = CoveredHelperLiveness(generation:"helper-a", lastPositive:100)
        let healthy: [String:Any] = ["helperGeneration":"helper-a", "installation":"healthy",
            "callerEligibility":"allowed", "lockedUsePaused":false, "relockAvailable":true, "coveredSession":true]
        XCTAssertNil(liveness.refusal(helper:[:], metadata:[:], now:129.9, covered:true))
        XCTAssertEqual(liveness.refusal(helper:[:], metadata:[:], now:130, covered:true), "helper_unavailable")
        XCTAssertNil(liveness.refusal(helper:healthy, metadata:["available":true,"ageMs":1000], now:130, covered:true))
        XCTAssertEqual(liveness.lastPositive,129)
        // Re-reading the same cached sample cannot extend the watchdog bound.
        XCTAssertEqual(liveness.refusal(helper:healthy, metadata:["available":true,"ageMs":31000], now:160, covered:true), "helper_unavailable")
        for key in ["helperGeneration", "installation", "callerEligibility", "lockedUsePaused", "relockAvailable", "coveredSession"] {
            var invalid = healthy; invalid.removeValue(forKey:key)
            XCTAssertEqual(liveness.refusal(helper:invalid, metadata:["available":true,"ageMs":0], now:160, covered:true), "helper_unavailable")
        }
        let conflicts: [(String,Any)] = [("helperGeneration","helper-b"), ("installation","missing"),
            ("callerEligibility","denied"), ("relockAvailable",false)]
        for (key,value) in conflicts {
            var invalid = healthy; invalid[key] = value
            XCTAssertEqual(liveness.refusal(helper:invalid, metadata:["available":true,"ageMs":0], now:160, covered:true), "helper_unavailable")
        }
        XCTAssertEqual(liveness.refusal(helper:healthy, metadata:["available":false,"ageMs":0], now:160, covered:true), "helper_unavailable")
        XCTAssertEqual(liveness.refusal(helper:healthy, metadata:[:], now:128, covered:true), "helper_unavailable")
    }

    func testFreshRootFaultEndsImmediatelyButStaleOrOtherEpochDoesNot() {
        for fault in [["lockedUsePaused":true], ["coveredSession":false]] {
            var helper: [String:Any] = fault; helper["helperGeneration"] = "helper-a"
            var liveness = CoveredHelperLiveness(generation:"helper-a", lastPositive:100)
            XCTAssertEqual(liveness.refusal(helper:helper, metadata:["available":true,"ageMs":100], now:101, covered:true), "watchdog_interrupted")
            XCTAssertNil(liveness.refusal(helper:helper, metadata:["available":true,"ageMs":2001], now:101, covered:true))
            XCTAssertNil(liveness.refusal(helper:helper, metadata:["available":false,"ageMs":0], now:101, covered:true))
            helper["helperGeneration"] = "helper-b"
            XCTAssertNil(liveness.refusal(helper:helper, metadata:["available":true,"ageMs":0], now:101, covered:true))
        }
    }

    func testDelayedGuardianObservesParentCancelAndEOFWithoutConsumingTraffic() throws {
        var descriptors: [Int32] = [-1, -1]
        XCTAssertEqual(socketpair(AF_UNIX, SOCK_STREAM, 0, &descriptors), 0)
        defer { Darwin.close(descriptors[0]); Darwin.close(descriptors[1]) }
        XCTAssertNil(guardianStartupCancellation(descriptors[1]))
        let cancellation = Array("{\"operation\":\"cancel\"}\n".utf8)
        XCTAssertEqual(cancellation.withUnsafeBytes { Darwin.write(descriptors[0], $0.baseAddress, $0.count) }, cancellation.count)
        XCTAssertEqual(guardianStartupCancellation(descriptors[1]), "owner_disconnected")
        var bytes = [UInt8](repeating:0, count:cancellation.count)
        XCTAssertEqual(Darwin.read(descriptors[1], &bytes, bytes.count), cancellation.count)
        XCTAssertEqual(bytes, cancellation, "Startup fencing must not consume active-loop protocol traffic")
        XCTAssertNil(guardianStartupCancellation(descriptors[1]))
        _ = Darwin.shutdown(descriptors[0], SHUT_WR)
        XCTAssertEqual(guardianStartupCancellation(descriptors[1]), "owner_disconnected")
    }

    private final class Permission: LockedUsePermissionManaging {
        var ready = false
        var ongoingAuthorization: Bool?
        var controlAuthorized: Bool { ongoingAuthorization ?? ready }
        var approvalState = "not_registered"
        var setupState = "idle"
        var setupError: String?
        var requests = 0
        func request() throws { requests += 1; ready = false; setupState = "installing" }
        func remove() throws {}
        func tick() {}
    }

    func testReadyWaitsForThePreviousRootSessionToFinishCleanup() throws {
        let name = "locked-use-test-\(UUID().uuidString)"
        let defaults = UserDefaults(suiteName:name)!
        defer { defaults.removePersistentDomain(forName:name) }
        let permission = Permission(); permission.ready = true
        let service = ResidentService()
        let use = MacLockedUse(broker:GrantBroker(policy:.workstation(issue:nil)), service:service,
            preferences:defaults, permission:permission, setupObservation:{ ["desktopState":"unlocked"] })
        try use.configure(enabled:true)
        var helper: [String:Any] = ["profile":"locked_use", "policy":"enabled", "installation":"healthy",
            "callerEligibility":"allowed", "lockedUsePaused":false, "coveredSession":true]
        service.helperObservation.replace(with:helper)
        XCTAssertEqual(use.status["phase"] as? String,"recovering")
        helper["coveredSession"] = false; service.helperObservation.replace(with:helper)
        XCTAssertEqual(use.status["phase"] as? String,"ready")
    }

    func testUnavailableAdmissionObservationDoesNotDisableAnAdmittedLease() throws {
        let name = "locked-use-test-\(UUID().uuidString)"
        let defaults = UserDefaults(suiteName:name)!
        defer { defaults.removePersistentDomain(forName:name) }
        let permission = Permission(); permission.ready = true
        let use = MacLockedUse(broker:GrantBroker(policy:.workstation(issue:nil)), service:ResidentService(),
            preferences:defaults, permission:permission, setupObservation:{ ["desktopState":"unlocked"] })
        try use.configure(enabled:true)
        permission.ready = false; permission.ongoingAuthorization = true
        XCTAssertFalse(use.enabled, "A fresh task must still await healthy admission observations")
        XCTAssertTrue(use.continuationAuthorized, "Live guardian/root enforcement owns the admitted task")
        permission.ongoingAuthorization = false
        XCTAssertFalse(use.continuationAuthorized, "Real OS permission loss still ends control")
        permission.ongoingAuthorization = true
        try use.configure(enabled:false)
        XCTAssertFalse(use.continuationAuthorized, "Explicit disable must win immediately")
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

    func testCoveredActivationRequiresUnlockedObservationOfOriginalConsole() throws {
        var initial = session; initial["desktopState"] = "locked"
        var unlocked = session; unlocked["desktopState"] = "unlocked"
        XCTAssertEqual(try coveredActivationObservation(unlocked, initial:initial)["desktopState"] as? String,"unlocked")
        for state in ["locked", "unknown", "no_session"] {
            var invalid = unlocked; invalid["desktopState"] = state
            XCTAssertThrowsError(try coveredActivationObservation(invalid, initial:initial))
        }
        for key in ["uuid", "uid", "boot"] {
            var replacement = unlocked; replacement[key] = "other"
            XCTAssertThrowsError(try coveredActivationObservation(replacement, initial:initial))
            replacement.removeValue(forKey:key)
            XCTAssertThrowsError(try coveredActivationObservation(replacement, initial:initial))
        }
        XCTAssertThrowsError(try coveredActivationObservation(unlocked, initial:unlocked),
            "An unlocked-origin task must never acquire covered authority")
    }

    func testOnlyLockedOriginTasksCanAcquireCoveredRelockAuthority() {
        for origin in ["unlocked", "locked", "unknown"] {
            var observation = session; observation["desktopState"] = origin
            let lease = ControlSessionLease(id:"session", grantID:"grant", session:observation,
                deadline:100, heartbeatDeadline:20)
            XCTAssertEqual(lease.startedLocked, origin == "locked")
            XCTAssertEqual(lease.mayActivateCovered(observedState:"locked"), origin == "locked",
                "A later idle lock cannot turn an unlocked-origin task into covered control")
            XCTAssertFalse(lease.mayActivateCovered(observedState:"unlocked"))
            XCTAssertFalse(lease.mayActivateCovered(observedState:"unknown"))
            XCTAssertEqual(lease.ordinaryLockEnding("desktop_locked"), origin == "unlocked",
                "An ordinary idle lock keeps otherwise valid standing approval")
            XCTAssertFalse(lease.ordinaryLockEnding("owner_disconnected"))
        }
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

    func testFaultFenceRequiresExplicitFreshHelperCleanupEvidence() {
        var fence = CoveredRecoveryFence()
        fence.arm(session)
        for helper: [String:Any] in [[:], ["installation":"healthy", "callerEligibility":"allowed"],
            ["installation":"healthy", "callerEligibility":"allowed", "coveredSession":true, "lockedUsePaused":false],
            ["installation":"healthy", "callerEligibility":"allowed", "coveredSession":false, "lockedUsePaused":true]] {
            fence.reconcile(helper:helper, observation:session)
            XCTAssertTrue(fence.pending)
        }
        let ready: [String:Any] = ["installation":"healthy", "callerEligibility":"allowed", "coveredSession":false, "lockedUsePaused":false]
        fence.reconcile(helper:ready, observation:[:]); XCTAssertTrue(fence.pending)
        var locked = session; locked["desktopState"] = "locked"
        fence.reconcile(helper:ready, observation:locked); XCTAssertFalse(fence.pending)
    }

    func testFaultFenceRefusesDesktopAndFreshProtectedTasksButLeavesBrowserIndependent() {
        var fence = CoveredRecoveryFence()
        fence.arm(session)
        for operation in ["snapshot", "input.key", "session.control"] {
            XCTAssertEqual(fence.refusal(for:operation)?.code, "locked_use_recovery_pending")
        }
        for operation in ["browser.tabs", "browser.dialog", "browser.eval"] {
            XCTAssertNil(fence.refusal(for:operation))
        }
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
