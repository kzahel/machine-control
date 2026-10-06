import Foundation
import ServiceManagement
import XCTest
@testable import macui

final class HelperRegistrationTests: XCTestCase {
    private final class Service {
        var status: SMAppService.Status = .enabled
        var stopped: ((Error?) -> Void)?
        var scheduled: [() -> Void] = []
        var calls = 0
        var failures: [NSError] = []
        lazy var registration = HelperRegistration(status:{ self.status }, register:{
            self.calls += 1
            if !self.failures.isEmpty { throw self.failures.removeFirst() }
            self.status = .enabled
        }, unregister:{ self.stopped = $0 }, schedule:{ _, work in self.scheduled.append(work) })
        func stop() { status = .notRegistered; stopped?(nil) }
        func runNext() { scheduled.removeFirst()() }
    }
    private var transition: NSError { NSError(domain:"SMAppServiceErrorDomain", code:1) }

    func testHelperRefusalCodesStayVisibleInOperatorMessages() {
        let conflict = HelperSetupMessage.text(MacUIError.action("unlock_policy_conflict"))
        XCTAssertTrue(conflict.contains("lock screen rule") && conflict.hasSuffix("(unlock_policy_conflict)"))
        XCTAssertTrue(HelperSetupMessage.text(MacUIError.action("unlock_policy_contended"), action:"removal")
            .contains("during helper removal"))
        XCTAssertTrue(HelperSetupMessage.text(MacUIError.action("installer_command_failed"))
            .hasSuffix("(installer_command_failed)"))
        XCTAssertNotNil(HelperSetupMessage.note(issue:"unlock_policy_entry_missing"))
        XCTAssertNil(HelperSetupMessage.note(issue:"unlock_caller_denied"))
        XCTAssertNil(HelperSetupMessage.note(issue:nil))
    }

    func testRepairWaitsForUnregisterAndRunLoopBeforeRegistering() {
        let service = Service(); var completed = false
        service.registration.start(restart:true) { result in
            XCTAssertEqual(try? result.get(), .enabled); completed = true
        }
        XCTAssertEqual(service.calls,0)
        service.stop()
        XCTAssertEqual(service.calls,0)
        XCTAssertFalse(completed)
        service.runNext()
        XCTAssertEqual(service.calls,1)
        XCTAssertTrue(completed)
    }

    func testRepairRetriesOnlyThePostUnregisterTransition() {
        let service = Service(); service.failures = [transition, transition]
        var completed = false
        service.registration.start(restart:true) { _ in completed = true }
        service.stop(); service.runNext()
        XCTAssertFalse(completed)
        service.runNext(); XCTAssertFalse(completed)
        service.runNext(); XCTAssertTrue(completed)
        XCTAssertEqual(service.calls,3)
    }

    func testRegistrationWithoutRepairDoesNotRetryPermissionError() {
        let service = Service(); service.status = .notRegistered; service.failures = [transition]
        var failed = false
        service.registration.start(restart:false) { if case .failure = $0 { failed = true } }
        XCTAssertTrue(failed); XCTAssertEqual(service.calls,1); XCTAssertTrue(service.scheduled.isEmpty)
    }

    func testRepairDoesNotRetrySigningFailure() {
        let service = Service(); service.failures = [NSError(domain:"SMAppServiceErrorDomain",code:3)]
        var failed = false
        service.registration.start(restart:true) { if case .failure = $0 { failed = true } }
        service.stop(); service.runNext()
        XCTAssertTrue(failed); XCTAssertEqual(service.calls,1); XCTAssertTrue(service.scheduled.isEmpty)
    }

    func testRepairRetryIsBounded() {
        let service = Service(); service.failures = Array(repeating:transition,count:20)
        var failed = false
        service.registration.start(restart:true) { if case .failure = $0 { failed = true } }
        service.stop()
        for _ in 0..<11 { service.runNext() }
        XCTAssertTrue(failed); XCTAssertEqual(service.calls,11); XCTAssertTrue(service.scheduled.isEmpty)
    }

    func testCancellationCannotRestartHelperAfterDelayedCallback() {
        let service = Service()
        service.registration.start(restart:true) { _ in XCTFail("Cancelled repair completed") }
        service.registration.cancel(); service.stop(); service.runNext()
        XCTAssertEqual(service.calls,0)
    }

    func testUnregisterFailureDoesNotTryRegistration() {
        let service = Service(); var failed = false
        service.registration.start(restart:true) { if case .failure = $0 { failed = true } }
        service.stopped?(transition); service.runNext()
        XCTAssertTrue(failed); XCTAssertEqual(service.calls,0)
    }
}
