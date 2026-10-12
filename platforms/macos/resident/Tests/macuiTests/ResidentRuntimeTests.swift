import AppKit
import Darwin
import XCTest
@testable import macui

final class ResidentRuntimeTests: XCTestCase {
    private var directory: URL!
    override func setUpWithError() throws {
        directory = URL(fileURLWithPath:"/tmp").appendingPathComponent("mc-runtime-\(UUID().uuidString)")
        try FileManager.default.createDirectory(at:directory, withIntermediateDirectories:false,
            attributes:[.posixPermissions:0o700])
    }
    override func tearDownWithError() throws { try? FileManager.default.removeItem(at:directory) }
    private func runtime() throws -> ResidentRuntime {
        try ResidentRuntime(socketPath:directory.appendingPathComponent("control.sock").path,
            policy:.workstation(issue:nil), journal:nil)
    }
    func testSecondRuntimeCannotReplaceLiveEndpoint() throws {
        _ = NSApplication.shared
        let first = try runtime(); try first.start(); defer { first.stop() }
        XCTAssertThrowsError(try runtime())
        XCTAssertTrue(first.running)
        XCTAssertTrue(FileManager.default.fileExists(atPath:first.server.socketPath))
    }
    func testClosingPresentationDoesNotStopRuntimeButExplicitStopDoes() throws {
        _ = NSApplication.shared
        let value = try runtime(); try value.start(); defer { value.stop() }
        try value.start()
        XCTAssertTrue(value.running)
        value.stopAccess()
        XCTAssertTrue(value.running)
        XCTAssertNil(value.server.broker.grant)
        value.stop()
        XCTAssertFalse(FileManager.default.fileExists(atPath:value.server.socketPath))
        XCTAssertThrowsError(try value.start())
    }
    func testOperatorCommandsHaveClosedDispatchAndUpdateExclusion() throws {
        let value = try runtime()
        XCTAssertEqual(value.operatorCommand(["method":"arbitrary.provider"])["ok"] as? Bool, false)
        XCTAssertEqual(value.operatorCommand(["method":"prepare_update"])["ok"] as? Bool, true)
        XCTAssertTrue(value.updating)
        XCTAssertEqual(value.operatorCommand(["method":"arm", "scopes":["observe"], "duration":60])["ok"] as? Bool, false)
        XCTAssertEqual(value.operatorCommand(["method":"cancel_update"])["ok"] as? Bool, true)
        XCTAssertFalse(value.updating)
    }

    func testStalledResumeDoesNotBlockStatusOrStopAndCannotResumeAfterStop() throws {
        _ = NSApplication.shared
        let value = try runtime(); try value.start(); defer { value.stop() }
        try value.server.broker.pause()
        let started = expectation(description:"helper stalled")
        let cancelled = expectation(description:"Resume cancelled by Stop")
        let drained = expectation(description:"late helper drained")
        let release = DispatchSemaphore(value:0)
        defer { release.signal() }
        value.resumeHelper = { _, cancelled in
            started.fulfill(); release.wait(); XCTAssertNotNil(cancelled())
        }
        var completions = 0
        value.operatorCommand(["method":"resume"]) { result in
            completions += 1
            XCTAssertEqual(result["error"] as? String, "stopped_by_person")
            cancelled.fulfill()
        }
        wait(for:[started], timeout:1)
        let begin = ProcessInfo.processInfo.systemUptime
        for _ in 0..<100 {
            XCTAssertEqual(value.operatorCommand(["method":"state"])["ok"] as? Bool, true)
        }
        value.stopAccess()
        XCTAssertLessThan(ProcessInfo.processInfo.systemUptime - begin, 1)
        wait(for:[cancelled], timeout:1)
        XCTAssertTrue(value.server.broker.admission.blocks("desktop").contains("manual"))
        XCTAssertNil(value.server.broker.grant)
        release.signal()
        DispatchQueue.main.asyncAfter(deadline:.now() + 0.1) { drained.fulfill() }
        wait(for:[drained], timeout:1)
        XCTAssertEqual(completions,1)
        XCTAssertTrue(value.server.broker.admission.blocks("desktop").contains("manual"))
    }

    func testAsyncResumeKeepsPauseUntilHelperSucceeds() throws {
        _ = NSApplication.shared
        let value = try runtime(); try value.start(); defer { value.stop() }
        // This success fixture has a stable unlocked console. Initial notice
        // reconfiguration and host activity belong to separate fence tests.
        value.server.grantConsoleObservation = { ["desktopState":"unlocked"] }
        value.server.activity.stop()
        value.server.refreshAdmission()
        try value.server.broker.pause()
        let started = expectation(description:"helper started")
        let done = expectation(description:"Resume succeeded")
        let release = DispatchSemaphore(value:0)
        defer { release.signal() }
        value.resumeHelper = { _, _ in started.fulfill(); release.wait() }
        value.operatorCommand(["method":"resume"]) { result in
            XCTAssertEqual(result["ok"] as? Bool, true, "\(result)")
            XCTAssertFalse(value.server.broker.admission.blocks("desktop").contains("manual"))
            done.fulfill()
        }
        wait(for:[started], timeout:1)
        XCTAssertTrue(value.server.broker.admission.blocks("desktop").contains("manual"))
        release.signal(); wait(for:[done], timeout:1)
    }

    func testResumeCannotClearPauseChangedByAnotherSurface() throws {
        _ = NSApplication.shared
        let value = try runtime(); try value.start(); defer { value.stop() }
        try value.server.broker.pause()
        let started = expectation(description:"helper stalled")
        let done = expectation(description:"stale Resume refused")
        let release = DispatchSemaphore(value:0)
        defer { release.signal() }
        value.resumeHelper = { _, _ in started.fulfill(); release.wait() }
        value.operatorCommand(["method":"resume"]) { result in
            XCTAssertEqual(result["error"] as? String, "control_generation_changed"); done.fulfill()
        }
        wait(for:[started], timeout:1)
        try value.server.broker.pause(reason:"operator_deferral", seconds:60)
        release.signal(); wait(for:[done], timeout:1)
        XCTAssertTrue(value.server.broker.admission.blocks("desktop").contains("operator_deferral"))
    }
}
