import XCTest
@testable import macui

final class DesktopCallerTrustTests: XCTestCase {
    private var directory: URL!
    override func setUp() {
        directory = FileManager.default.temporaryDirectory.appendingPathComponent("mc-desktop-trust-fixture-" + UUID().uuidString)
        try! FileManager.default.createDirectory(at:directory, withIntermediateDirectories:false, attributes:[.posixPermissions:0o700])
    }
    override func tearDown() { try! FileManager.default.removeItem(at:directory) }
    private func trust() -> DesktopCallerTrust {
        let value = DesktopCallerTrust(directory:directory.path)
        value.peerValid = { fd, _ in fd == 42 }
        value.peerStillValid = { fd, _ in fd == 42 }
        return value
    }
    private func enroll(_ value: DesktopCallerTrust, scopes: Set<GrantScope> = [.observe,.control]) throws {
        try value.enroll(VerifiedDesktopIntegration(requirement:"fixture-only",publisher:"FIXTUREONLY"), scopes:scopes)
    }
    func testDefaultOffAndForeignPeerCannotBorrowTrustedScopes() throws {
        let value = trust()
        XCTAssertThrowsError(try value.admittedRevision(descriptor:42, scopes:[.observe]))
        try enroll(value)
        XCTAssertThrowsError(try value.admittedRevision(descriptor:41, scopes:[.observe]))
        XCTAssertThrowsError(try value.admittedRevision(descriptor:42, scopes:[.devtools]))
        XCTAssertNotNil(try value.admittedRevision(descriptor:42, scopes:[.observe]))
        XCTAssertEqual(value.status["protectedControl"] as? Bool,false)
        XCTAssertEqual(value.status["outerRecovery"] as? Bool,false)
    }
    func testStopPersistsAndReconnectDoesNotReenableTrust() throws {
        let value = trust(); try enroll(value)
        let revision = try value.admittedRevision(descriptor:42, scopes:[.control])
        value.stop()
        XCTAssertNotNil(value.refusal(descriptor:42, revision:revision, scopes:[.control]))
        let restored = trust()
        XCTAssertThrowsError(try restored.admittedRevision(descriptor:42, scopes:[.control]))
        XCTAssertTrue(restored.suspended)
        try enroll(restored)
        XCTAssertNotEqual(try restored.admittedRevision(descriptor:42, scopes:[.control]),revision)
    }
    func testRemovalReductionAndRestartFenceOldConnections() throws {
        let value = trust(); try enroll(value)
        let original = try value.admittedRevision(descriptor:42, scopes:[.control])
        let restored = trust()
        XCTAssertEqual(restored.refusal(descriptor:42, revision:original, scopes:[.control]),"desktop_trust_changed")
        let fresh = try restored.admittedRevision(descriptor:42, scopes:[.control])
        try enroll(restored, scopes:[.observe])
        XCTAssertNotNil(restored.refusal(descriptor:42, revision:fresh, scopes:[.control]))
        XCTAssertThrowsError(try restored.admittedRevision(descriptor:42, scopes:[.control]))
        restored.remove()
        XCTAssertThrowsError(try trust().admittedRevision(descriptor:42, scopes:[.observe]))
    }
    func testInvalidStorageFailsClosedIncludingIntegerBoolean() {
        for raw: Any in ["invalid", ["schema":"machine-control-desktop-trust/v1",
             "requirement":"fixture-only","scopes":["observe"],"suspended":1],
             ["schema":"machine-control-desktop-trust/v1", "requirement":"fixture-only",
              "scopes":["observe","observe"],"suspended":false]] {
            let data = try! JSONSerialization.data(withJSONObject:raw, options:[.fragmentsAllowed])
            let path = directory.appendingPathComponent("desktop-caller-trust.json")
            try! data.write(to:path); try! FileManager.default.setAttributes([.posixPermissions:0o600], ofItemAtPath:path.path)
            let value = trust(); XCTAssertTrue(value.storageInvalid)
            XCTAssertThrowsError(try value.admittedRevision(descriptor:42, scopes:[.observe]))
        }
    }
    func testQueueInspectionDoesNotRepeatSealedResourceAuthentication() throws {
        let value = trust(); try enroll(value)
        var attestations = 0
        value.peerValid = { _,_ in attestations += 1; return true }
        let revision = try value.admittedRevision(descriptor:42, scopes:[.observe])
        for _ in 0..<1000 { XCTAssertNil(value.refusal(descriptor:42, revision:revision, scopes:[.observe], checkPeer:false)) }
        XCTAssertEqual(attestations,1)
        value.peerStillValid = { _,_ in false }
        XCTAssertEqual(value.refusal(descriptor:42, revision:revision, scopes:[.observe]),"desktop_caller_identity_denied")
    }
    func testPublicLabelIsStrictAttributionRatherThanAuthority() throws {
        let frame: [String:Any] = ["schema":"machine-control-desktop-delegation/v1",
            "sessionId":"fixture-session","sessionGeneration":UUID().uuidString]
        XCTAssertEqual(try DesktopDelegation.parse(frame).session,"fixture-session")
        for field in ["schema", "sessionGeneration", "sessionId"] {
            var invalid = frame; invalid[field] = "\n"; XCTAssertThrowsError(try DesktopDelegation.parse(invalid))
        }
        var forged = frame; forged["grant"] = true
        XCTAssertThrowsError(try DesktopDelegation.parse(forged))
        XCTAssertThrowsError(try trust().admittedRevision(descriptor:42, scopes:[.observe]))
    }
    func testPrivateAtomicStorageRefusesLinksAndDropsAuthorityOnFailedStop() throws {
        let value = trust(); try enroll(value)
        let path = directory.appendingPathComponent("desktop-caller-trust.json")
        let attributes = try FileManager.default.attributesOfItem(atPath:path.path)
        XCTAssertEqual((attributes[.posixPermissions] as? NSNumber)?.intValue,0o600)
        let stored = try String(contentsOf:path, encoding:.utf8)
        for field in ["sessionId", "sessionGeneration", "intentId", "grantId", "revision"] { XCTAssertFalse(stored.contains(field)) }
        let outside = directory.appendingPathComponent("outside")
        try FileManager.default.moveItem(at:path,to:outside)
        try FileManager.default.createSymbolicLink(at:path,withDestinationURL:outside)
        XCTAssertTrue(trust().storageInvalid)
        try FileManager.default.removeItem(at:path)
        try FileManager.default.linkItem(at:outside,to:path)
        XCTAssertTrue(trust().storageInvalid)
        try FileManager.default.removeItem(at:path)
        try FileManager.default.moveItem(at:outside,to:path)
        try FileManager.default.setAttributes([.posixPermissions:0o755],ofItemAtPath:directory.path)
        value.stop()
        XCTAssertTrue(value.suspended); XCTAssertTrue(value.storageInvalid)
        try FileManager.default.setAttributes([.posixPermissions:0o700],ofItemAtPath:directory.path)
        XCTAssertThrowsError(try trust().admittedRevision(descriptor:42,scopes:[.observe]))
    }
    func testUnsignedPeerAndUnsignedEnrollmentFailBeforeAuthority() throws {
        var pair: [Int32] = [-1,-1]
        XCTAssertEqual(socketpair(AF_UNIX,SOCK_STREAM,0,&pair),0)
        defer { Darwin.close(pair[0]); Darwin.close(pair[1]) }
        XCTAssertFalse(VerifiedDesktopIntegration.peer(pair[0],matches:"identifier com.yepanywhere.desktop"))
        XCTAssertThrowsError(try VerifiedDesktopIntegration.yepAnywhere(at:directory))
    }
}
