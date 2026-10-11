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
}
