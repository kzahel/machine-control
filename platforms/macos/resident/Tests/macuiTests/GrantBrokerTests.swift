import XCTest
@testable import macui
final class GrantBrokerTests:XCTestCase {
    func testNativeConsentProjectionCannotAuthorizeAnOrdinaryCall() throws {
        let broker = GrantBroker(policy:.workstation(issue:nil)); try bindPolicy(broker)
        XCTAssertEqual(broker.authorize("snapshot")?.code,"surface_disabled")
        try broker.configureSurface("desktop",mode:"automatic",seconds:nil)
        broker.desktopRouteReady = true
        XCTAssertNotNil(broker.activeGrant)
        XCTAssertEqual(broker.authorize("snapshot")?.code,"control_session_required")
        XCTAssertNil(broker.authorize("snapshot",controlled:true))
        XCTAssertEqual(broker.authorize("session.unlock",controlled:true)?.code,"operation_not_permitted_by_policy")
        let id = broker.desktopConsentID
        try broker.configureSurface("browser",mode:"ask",seconds:nil,profiles:["profile-one"])
        XCTAssertEqual(broker.desktopConsentID,id)
        try broker.pause(surface:"browser")
        XCTAssertEqual(broker.desktopConsentID,id)
        broker.revoke(reason:"stopped_by_person")
        XCTAssertNil(broker.activeGrant)
        XCTAssertNotEqual(broker.desktopConsentID,id)
        try broker.resume(); XCTAssertFalse(broker.admission.enabled("desktop"))
    }
    func testUnknownOperatorCannotCreateConsentAndOffRemainsAvailable() throws {
        let broker = GrantBroker(policy:.workstation(issue:nil)); try bindPolicy(broker)
        broker.operatorReady = { false }
        XCTAssertThrowsError(try broker.configureSurface("desktop",mode:"automatic",seconds:nil))
        try broker.configureSurface("desktop",mode:"off",seconds:nil)
        XCTAssertFalse(broker.admission.enabled("desktop"))
    }
    func testManagedProtectedPlaneRemainsSeparateFromOrdinarySurfaceTasks() {
        let broker = GrantBroker(policy:DeploymentPolicy(preset:"appliance",grantMode:.standing,protectedOperations:true,source:"policy_file",issue:nil))
        XCTAssertNil(broker.authorize("session.unlock"))
        XCTAssertNotNil(broker.authorize("snapshot"))
    }
    func testAuditIsBounded() {
        let broker = GrantBroker(policy:.workstation(issue:nil))
        for index in 0..<150 { broker.record(operation:"op\(index)",accepted:false,errorCode:nil,caller:CallerIdentity(uid:0,chain:[]),claimID:nil) }
        XCTAssertEqual(broker.audit.count,100); XCTAssertEqual(broker.audit.first?.operation,"op50")
    }
}
