import Foundation
import XCTest
@testable import macui

/// Tests use the packaged, pinned, real policy. No Swift policy substitute.
private enum TestPolicyPayload {
    static let root:Result<URL,Error> = Result {
        if let path = ProcessInfo.processInfo.environment["MACHINE_CONTROL_TEST_POLICY_ROOT"] {
            let root = URL(fileURLWithPath:path)
            guard FileManager.default.isExecutableFile(atPath:root.appendingPathComponent("node").path) else {
                throw SharedPolicyError(code:"test_policy_payload_missing")
            }
            return root
        }
        let package = URL(fileURLWithPath:#filePath).deletingLastPathComponent().deletingLastPathComponent().deletingLastPathComponent()
        let root = package.appendingPathComponent(".build/shared-policy-tests")
        let builder = Process()
        builder.executableURL = URL(fileURLWithPath:"/usr/bin/env")
        #if arch(arm64)
        let arch = "arm64"
        #else
        let arch = "x86_64"
        #endif
        builder.arguments = ["python3",package.appendingPathComponent("scripts/prepare-policy.py").path,
            "--arch",arch,"--output",root.path]
        try builder.run(); builder.waitUntilExit()
        guard builder.terminationStatus == 0 else { throw SharedPolicyError(code:"test_policy_build_failed") }
        return root
    }
}
func testPolicyRoot() throws -> URL { try TestPolicyPayload.root.get() }
final class SharedPolicyFixture {
    let admission: AccessAdmission
    let host: SharedResidentHost
    init(_ admission:AccessAdmission = AccessAdmission()) throws {
        self.admission = admission
        let root = try testPolicyRoot()
        host = try SharedResidentHost(executable:root.appendingPathComponent("node"),
            arguments:[root.appendingPathComponent("policy/node/main.ts").path], directory:root,
            receive:{ [weak admission] in admission?.receive($0) }, native:{ _ in true }, failed:{ [weak admission] _ in admission?.invalidate() })
        let host = self.host
        try admission.bind { try host.call($0) }
        admission.setInputReady(true)
        admission.setReady("desktop",true); admission.setReady("browser",true)
        admission.reconfigureNotice(0)
    }
    deinit { host.stop() }
}
extension XCTestCase {
    func bindPolicy(_ broker:GrantBroker) throws {
        let fixture = try SharedPolicyFixture(broker.admission)
        broker.operatorReady = { true }
        addTeardownBlock { fixture.host.stop() }
    }
}
