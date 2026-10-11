import Darwin
import XCTest
@testable import macui

final class PresentationTests: XCTestCase {
    private var directory: URL!
    private var store: PresentationStore!
    override func setUpWithError() throws {
        directory = URL(fileURLWithPath:"/tmp").appendingPathComponent("mc-presentation-\(UUID().uuidString)")
        try FileManager.default.createDirectory(at:directory, withIntermediateDirectories:false, attributes:[.posixPermissions:0o700])
        store = PresentationStore(socketPath:directory.appendingPathComponent("control.sock").path)
    }
    override func tearDownWithError() throws { try? FileManager.default.removeItem(at:directory) }
    func testMissingDefaultsAndEveryProfileRoundTrips() throws {
        XCTAssertEqual(store.load().profile, .personal); XCTAssertNil(store.load().diagnostic)
        for profile in PresentationProfile.allCases {
            try store.save(profile)
            XCTAssertEqual(store.load().profile, profile)
            XCTAssertNil(store.load().diagnostic)
            let attributes = try FileManager.default.attributesOfItem(atPath:directory.appendingPathComponent("presentation.json").path)
            XCTAssertEqual((attributes[.posixPermissions] as? NSNumber)?.intValue, 0o600)
        }
        try store.save(.personal); XCTAssertEqual(store.load().profile, .personal)
        XCTAssertEqual(try FileManager.default.contentsOfDirectory(atPath:directory.path), ["presentation.json"])
    }
    func testMalformedUnsupportedAndOversizedConfigurationsFailToPersonal() throws {
        for value in ["{", "{}", "{\"schema\":\"machine-control-presentation/v2\",\"profile\":\"appliance\"}", String(repeating:"x", count:4097)] {
            try store.save(.minimal)
            try Data(value.utf8).write(to:directory.appendingPathComponent("presentation.json"))
            XCTAssertEqual(store.load().profile, .personal); XCTAssertNotNil(store.load().diagnostic)
        }
        // Supported reset replaces a corrupt regular file atomically.
        try store.save(.personal); XCTAssertNil(store.load().diagnostic)
    }
    func testSymlinksAndWritableDirectoriesAreRefused() throws {
        let outside = directory.appendingPathComponent("outside")
        try Data("unchanged".utf8).write(to:outside)
        try FileManager.default.createSymbolicLink(at:directory.appendingPathComponent("presentation.json"), withDestinationURL:outside)
        XCTAssertNotNil(store.load().diagnostic)
        XCTAssertThrowsError(try store.save(.appliance))
        XCTAssertEqual(try String(contentsOf:outside), "unchanged")
        let linked = directory.appendingPathComponent("linked")
        try FileManager.default.createSymbolicLink(at:linked, withDestinationURL:directory)
        XCTAssertThrowsError(try PresentationStore(socketPath:linked.appendingPathComponent("control.sock").path).save(.minimal))
        try FileManager.default.setAttributes([.posixPermissions:0o777], ofItemAtPath:directory.path)
        XCTAssertThrowsError(try store.save(.minimal))
    }
    func testPreferenceAndTemporaryOverrideCannotChangeAuthority() throws {
        let socket = directory.appendingPathComponent("control.sock").path
        try store.save(.appliance)
        let runtime = try ResidentRuntime(socketPath:socket, policy:.workstation(issue:nil), journal:nil,
            presentationOverride:.minimal)
        XCTAssertEqual(runtime.presentation.profile, .minimal)
        XCTAssertEqual(store.load().profile, .appliance)
        XCTAssertEqual(runtime.server.broker.policy.grantMode, .approval)
        XCTAssertNil(runtime.server.broker.grant)
        runtime.server.broker.issue(scopes:[.observe], durationSeconds:60, reason:"test", requester:"fixture", approver:"fixture")
        let before = runtime.server.broker.statusJSON
        let saved = expectation(description:"presentation saved")
        try runtime.configurePresentation(.personal) { XCTAssertTrue($0); saved.fulfill() }
        wait(for:[saved], timeout:2)
        XCTAssertEqual(runtime.presentation.profile, .personal)
        XCTAssertEqual(runtime.presentationJSON["temporaryOverride"] as? Bool, false)
        XCTAssertTrue(NSDictionary(dictionary:before).isEqual(to:runtime.server.broker.statusJSON))
        XCTAssertFalse(runtime.server.lockedUse.enabled)
    }
    func testStandingPolicyStopFencesEffectsWithoutChangingPolicy() throws {
        let policy = DeploymentPolicy.parse(["schema":DeploymentPolicy.schema, "preset":"appliance"])!
        let runtime = try ResidentRuntime(socketPath:directory.appendingPathComponent("control.sock").path,
            policy:policy, journal:nil, presentationOverride:.appliance)
        XCTAssertNil(runtime.server.broker.authorize("action"))
        runtime.stopAccess()
        XCTAssertNotNil(runtime.server.broker.authorize("action"))
        XCTAssertEqual(runtime.server.broker.policy, policy)
        try runtime.server.broker.resume()
        XCTAssertNil(runtime.server.broker.authorize("action"))
    }

}
