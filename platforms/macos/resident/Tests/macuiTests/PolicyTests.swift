import Darwin
import XCTest
@testable import macui

final class PolicyTests: XCTestCase {
    private var directory: URL!

    override func setUpWithError() throws {
        directory = FileManager.default.temporaryDirectory
            .appendingPathComponent("mc-policy-\(UUID().uuidString)")
        try FileManager.default.createDirectory(at: directory, withIntermediateDirectories: false)
        chmod(directory.path, 0o755)
    }

    override func tearDownWithError() throws {
        try? FileManager.default.removeItem(at: directory)
    }

    private func write(_ text: String, mode: mode_t = 0o644) -> String {
        let path = directory.appendingPathComponent("policy.json").path
        FileManager.default.createFile(atPath: path, contents: Data(text.utf8))
        chmod(path, mode)
        return path
    }

    private func load(_ path: String) -> DeploymentPolicy {
        DeploymentPolicy.load(path: path, trustedOwner: getuid())
    }

    func testMissingFileIsWorkstation() {
        let policy = load(directory.appendingPathComponent("absent.json").path)
        XCTAssertEqual(policy.preset, "workstation")
        XCTAssertEqual(policy.grantMode, .approval)
        XCTAssertFalse(policy.protectedOperations)
        XCTAssertEqual(policy.issue, "policy_absent")
    }

    func testProductionOwnerRejectsUserOwnedFile() {
        let path = write(#"{"schema":"machine-control-policy/v0","preset":"appliance"}"#)
        let policy = DeploymentPolicy.load(path: path)
        XCTAssertEqual(policy.preset, "workstation")
        XCTAssertEqual(policy.issue, "policy_untrusted")
    }

    func testApplianceIsStandingWithProtectedOperations() {
        let policy = load(write(#"{"schema":"machine-control-policy/v0","preset":"appliance"}"#))
        XCTAssertEqual(policy.preset, "appliance")
        XCTAssertEqual(policy.grantMode, .standing)
        XCTAssertTrue(policy.protectedOperations)
        XCTAssertEqual(policy.source, "policy_file")
    }

    func testUnattendedMayBeMadeStricter() {
        let policy = load(write(#"{"schema":"machine-control-policy/v0","preset":"unattended","grantMode":"approval","protectedOperations":false}"#))
        XCTAssertEqual(policy.preset, "unattended")
        XCTAssertEqual(policy.grantMode, .approval)
        XCTAssertFalse(policy.protectedOperations)
    }

    func testWorkstationCannotBeWidened() {
        for text in [
            #"{"schema":"machine-control-policy/v0","preset":"workstation","grantMode":"standing"}"#,
            #"{"schema":"machine-control-policy/v0","preset":"workstation","protectedOperations":true}"#,
        ] {
            let policy = load(write(text))
            XCTAssertEqual(policy.issue, "policy_invalid", text)
            XCTAssertEqual(policy.grantMode, .approval)
        }
    }

    func testWritableOrLinkedFilesAreUntrusted() throws {
        let text = #"{"schema":"machine-control-policy/v0","preset":"appliance"}"#
        XCTAssertEqual(load(write(text, mode: 0o666)).issue, "policy_untrusted")
        let target = write(text)
        let link = directory.appendingPathComponent("link.json").path
        try FileManager.default.createSymbolicLink(atPath: link, withDestinationPath: target)
        XCTAssertEqual(load(link).issue, "policy_untrusted")
        chmod(directory.path, 0o777)
        XCTAssertEqual(load(target).issue, "policy_untrusted")
    }

    func testMalformedDocumentsAreInvalid() {
        for text in [
            "not json",
            #"{"schema":"other","preset":"appliance"}"#,
            #"{"schema":"machine-control-policy/v0","preset":"root"}"#,
            #"{"schema":"machine-control-policy/v0","preset":"appliance","extra":1}"#,
        ] {
            XCTAssertEqual(load(write(text)).issue, "policy_invalid", text)
        }
    }
}
