import Darwin
import XCTest
@testable import macui

final class AdmissionChannelTests: XCTestCase {
    private var server: ResidentServer!
    private var broker: GrantBroker!
    private var path = ""
    private var clients: [Int32] = []
    private final class State { var effects = 0; var clock = 100.0 }
    private let fixture = State()
    private var effects: Int { fixture.effects }
    private var clock: Double { get { fixture.clock } set { fixture.clock = newValue } }
    override func setUpWithError() throws {
        signal(SIGPIPE, SIG_IGN)
        path = "/tmp/mc-admission-\(getpid())-\(UUID().uuidString.prefix(8)).sock"
        broker = GrantBroker(policy:.workstation(issue:nil))
        broker.admission.now = { [fixture] in fixture.clock }
        server = ResidentServer(socketPath:path, service:ResidentService(), broker:broker)
        server.noticeSeconds = 0
        server.coveredActivation = { _, _ in }
        server.approvalDesktopUnlocked = { true }
        server.grantConsoleObservation = { ["desktopState":"unlocked", "uuid":"fixture", "boot":123, "uid":getuid()] }
        server.controlledProvider = { [fixture] request in
            fixture.effects += 1
            return ["accepted":true, "delivery":"confirmed", "effect":"observed", "data":["count":fixture.effects]]
        }
        broker.issueUntilStopped(scopes:[.observe, .control], reason:"fixture", requester:"fixture", approver:"fixture")
        try server.start()
    }
    override func tearDown() {
        for client in clients { Darwin.close(client) }
        clients = []; server.stop(); unlink(path)
        server = nil; broker = nil
    }
    func testOperatorMenuAndHotkeyStopSuspendDurableDesktopTrust() throws {
        let directory = FileManager.default.temporaryDirectory.appendingPathComponent("mc-stop-trust-fixture-" + UUID().uuidString)
        try FileManager.default.createDirectory(at:directory, withIntermediateDirectories:false, attributes:[.posixPermissions:0o700])
        defer { try? FileManager.default.removeItem(at:directory) }
        server.callerTrust = DesktopCallerTrust(directory:directory.path)
        for reason in ["stopped_by_person", "stopped_from_menu", "stopped_by_hotkey", "revoked_by_caller"] {
            try server.callerTrust.enroll(VerifiedDesktopIntegration(requirement:"fixture", publisher:"FIXTUREONLY"), scopes:[.observe,.control])
            server.revoke(reason:reason)
            XCTAssertEqual(server.callerTrust.status["enabled"] as? Bool,false)
            XCTAssertTrue(DesktopCallerTrust(directory:directory.path).suspended)
        }
        try server.callerTrust.enroll(VerifiedDesktopIntegration(requirement:"fixture", publisher:"FIXTUREONLY"), scopes:[.observe,.control])
        server.revoke(reason:"operator_quit")
        XCTAssertEqual(server.callerTrust.status["enabled"] as? Bool,true)
    }

    func testInputCancellationUsesCurrentLeaseLatchAcrossSessions() {
        let retired = server.lockedUse.safety
        retired.arm()
        server.lockedUse.prepareSessionSafety()
        let current = server.lockedUse.safety
        current.arm()
        XCTAssertTrue(retired.interrupt("retired_guardian"))
        XCTAssertNil(server.service.inputCancellation())
        let interrupted = expectation(description:"independent input cancellation")
        DispatchQueue.global().async {
            XCTAssertTrue(current.interrupt("physical_presence"))
            XCTAssertEqual(self.server.service.inputCancellation(), "physical_presence")
            interrupted.fulfill()
        }
        wait(for:[interrupted], timeout:2)
        server.lockedUse.prepareSessionSafety()
        XCTAssertNil(server.service.inputCancellation())
        server.lockedUse.safety.arm()
        XCTAssertTrue(server.lockedUse.safety.interrupt("guardian_failure"))
        XCTAssertEqual(server.service.inputCancellation(), "guardian_failure")
    }

    private func connect() throws -> Int32 {
        let fd = try residentSocket()
        var (address, length) = try unixAddress(path)
        XCTAssertEqual(withSockAddr(&address, length:length, { Darwin.connect(fd, $0, $1) }), 0)
        clients.append(fd); return fd
    }

    func testDelegatedOwnerDoesNotInheritAmbientGrantAndStopFencesFreshConnections() throws {
        let directory = FileManager.default.temporaryDirectory.appendingPathComponent("mc-admitted-desktop-fixture-" + UUID().uuidString)
        try FileManager.default.createDirectory(at:directory, withIntermediateDirectories:false, attributes:[.posixPermissions:0o700])
        defer { try? FileManager.default.removeItem(at:directory) }
        server.callerTrust = DesktopCallerTrust(directory:directory.path)
        server.callerTrust.peerValid = { _,_ in false }
        server.callerTrust.peerStillValid = { _,_ in true }
        try server.callerTrust.enroll(VerifiedDesktopIntegration(requirement:"fixture-only",publisher:"FIXTUREONLY"), scopes:[.observe,.control])
        let delegation: [String:Any] = ["schema":"machine-control-desktop-delegation/v1", "sessionId":"fixture-session", "sessionGeneration":UUID().uuidString]
        func request(_ fd: Int32, _ id: String) -> [String:Any] {
            exchange(fd,["operation":"control.open","schema":AccessAdmission.schema,"requestId":id,
                "scopes":["observe","control"],"reason":"Authenticated fixture session","durationSeconds":60,
                "waitSeconds":120,"desktopDelegation":delegation])
        }
        let foreign = try connect()
        XCTAssertEqual(request(foreign,"foreign")["errorCode"] as? String,"desktop_caller_identity_denied")
        XCTAssertEqual(effects,0)
        // Explicit ambient approval above did not rescue the rejected delegate.
        broker.revoke(reason:"fixture_reset")
        server.callerTrust.peerValid = { _,_ in true }
        let client = try connect(), first = request(client,"trusted")
        let offered = first["data"] as! [String:Any]
        XCTAssertEqual(offered["ownerAssurance"] as? String,"verified_desktop_integration")
        var active = command(client,"control.accept",["offerGeneration":offered["offerGeneration"]!])["data"] as! [String:Any]
        func dispatch(_ operation: String) -> [String:Any] {
            command(client,"control.dispatch",["sessionId":active["sessionId"]!,"resourceGenerations":active["resourceGenerations"]!,"request":["operation":operation]])
        }
        XCTAssertEqual((dispatch("snapshot")["data"] as? [String:Any])?["accepted"] as? Bool,true)
        XCTAssertEqual(effects,1)
        XCTAssertEqual(dispatch("session.unlock")["accepted"] as? Bool,false)
        XCTAssertEqual(dispatch("outer.prepare")["accepted"] as? Bool,false)
        XCTAssertEqual(effects,1)
        let old = active["sessionId"] as? String
        try broker.pause()
        XCTAssertEqual(dispatch("snapshot")["accepted"] as? Bool,false)
        XCTAssertEqual(effects,1)
        XCTAssertEqual(server.callerTrust.status["enabled"] as? Bool,true)
        try broker.resume()
        let next = command(client,"control.status")["data"] as! [String:Any]
        active = command(client,"control.accept",["offerGeneration":next["offerGeneration"]!])["data"] as! [String:Any]
        XCTAssertNotEqual(active["sessionId"] as? String,old)
        XCTAssertEqual((dispatch("snapshot")["data"] as? [String:Any])?["accepted"] as? Bool,true)
        XCTAssertEqual(effects,2)
        server.revoke(reason:"stopped_by_person")
        XCTAssertEqual(dispatch("snapshot")["accepted"] as? Bool,false)
        let reconnect = try connect()
        XCTAssertEqual(request(reconnect,"reconnect")["errorCode"] as? String,"desktop_trust_not_enabled")
        XCTAssertEqual(effects,2)
    }
    private func exchange(_ fd: Int32, _ request: [String:Any]) -> [String:Any] {
        let done = expectation(description:"channel reply")
        var result: [String:Any] = [:]
        DispatchQueue.global().async {
            defer { done.fulfill() }
            try? writeSocket(fd, data:encodeJSONLine(request))
            if let line = try? readSocket(fd), let value = (try? JSONSerialization.jsonObject(with:line)) as? [String:Any] { result = value }
        }
        wait(for:[done], timeout:5)
        XCTAssertEqual(result["requestId"] as? String, request["requestId"] as? String, "Unexpected reply: \(result)")
        return result
    }
    private func open(_ fd: Int32, _ id: String) -> [String:Any] {
        let response = exchange(fd, ["operation":"control.open", "schema":AccessAdmission.schema, "requestId":id,
            "scopes":["observe", "control"], "reason":"fixture", "durationSeconds":60, "waitSeconds":120])
        XCTAssertEqual(response["accepted"] as? Bool, true, "Open refused: \(response)")
        return response["data"] as? [String:Any] ?? [:]
    }
    private func command(_ fd: Int32, _ operation: String, _ extra: [String:Any] = [:]) -> [String:Any] {
        var request = extra; request["operation"] = operation; request["requestId"] = UUID().uuidString
        return exchange(fd, request)
    }
    func testLiveOwnersQueuePauseFenceAndCannotBorrowAnotherSession() throws {
        let a = try connect(), b = try connect()
        let first = open(a, "first"), second = open(b, "second")
        guard !first.isEmpty, !second.isEmpty else { return }
        XCTAssertEqual(first["state"] as? String, "offered")
        XCTAssertEqual(second["state"] as? String, "waiting_for_resource")
        let accepted = command(a, "control.accept", ["offerGeneration":first["offerGeneration"]!])["data"] as! [String:Any]
        let action: [String:Any] = ["sessionId":accepted["sessionId"]!, "resourceGenerations":accepted["resourceGenerations"]!, "request":["operation":"input.text", "text":"fixture"]]
        XCTAssertEqual(command(b, "control.dispatch", action)["accepted"] as? Bool, false)
        XCTAssertEqual(effects, 0)
        XCTAssertEqual(command(a, "control.dispatch", action)["accepted"] as? Bool, true)
        XCTAssertEqual(effects, 1)
        let grant = broker.grant!.id
        try broker.pause()
        XCTAssertEqual(command(a, "control.dispatch", action)["accepted"] as? Bool, false)
        XCTAssertEqual(effects, 1); XCTAssertEqual(broker.grant!.id, grant)
        try broker.resume()
        let next = command(b, "control.status")["data"] as! [String:Any]
        XCTAssertEqual(next["state"] as? String, "offered")
        XCTAssertEqual(command(a, "control.dispatch", action)["accepted"] as? Bool, false)
        _ = command(b, "control.cancel")
        let offered = command(a, "control.status")["data"] as! [String:Any]
        let fresh = command(a, "control.accept", ["offerGeneration":offered["offerGeneration"]!])["data"] as! [String:Any]
        XCTAssertNotEqual(accepted["sessionId"] as? String, fresh["sessionId"] as? String)
        XCTAssertEqual(effects, 1)
    }
    func testLargeReplySurvivesSocketBackpressureWithoutBlockingOperator() throws {
        let client = try connect()
        var capacity: Int32 = 1024
        XCTAssertEqual(setsockopt(client, SOL_SOCKET, SO_RCVBUF, &capacity, socklen_t(MemoryLayout<Int32>.size)), 0)
        let first = open(client, "large")
        let active = command(client, "control.accept", ["offerGeneration":first["offerGeneration"]!])["data"] as! [String:Any]
        server.controlledProvider = { _ in ["accepted":true, "data":["payload":String(repeating:"x", count:512 * 1024)]] }
        let reply = command(client, "control.dispatch", ["sessionId":active["sessionId"]!, "resourceGenerations":active["resourceGenerations"]!, "request":["operation":"snapshot"]])
        XCTAssertEqual(reply["accepted"] as? Bool, true)
        let result = reply["data"] as? [String:Any]
        XCTAssertEqual(((result?["data"] as? [String:Any])?["payload"] as? String)?.count, 512 * 1024)
        try broker.pause()
        XCTAssertEqual((command(client, "control.status")["data"] as? [String:Any])?["state"] as? String, "paused")
    }
    func testOrderedFramesOutliveLegacyBudgetAndCannotDowngrade() {
        var order = AdmissionRequestOrder()
        XCTAssertTrue(order.accept(["requestId":"opening"]))
        for sequence in 1...72000 {
            XCTAssertTrue(order.accept(["requestId":"bounded-label", "requestSequence":sequence]))
        }
        XCTAssertFalse(order.accept(["requestId":"replay", "requestSequence":72000]))
        XCTAssertFalse(order.accept(["requestId":"gap", "requestSequence":72002]))
        XCTAssertFalse(order.accept(["requestId":"downgrade"]))
        XCTAssertFalse(order.accept(["requestId":"boolean", "requestSequence":true]))
        XCTAssertTrue(order.accept(["requestId":"next", "requestSequence":72001]))
        var legacy = AdmissionRequestOrder()
        XCTAssertTrue(legacy.accept(["requestId":"unique"]))
        XCTAssertFalse(legacy.accept(["requestId":"unique"]))
        for number in 1..<4096 { XCTAssertTrue(legacy.accept(["requestId":String(number)])) }
        XCTAssertFalse(legacy.accept(["requestId":"over-budget"]))
    }
    func testConnectionAdvertisesOrderingAndEndsOnReplay() throws {
        let client = try connect()
        let first = open(client, "ordered")
        XCTAssertEqual(first["requestSequencing"] as? String, "strict")
        let active = command(client, "control.accept", ["offerGeneration":first["offerGeneration"]!, "requestSequence":1])["data"] as! [String:Any]
        XCTAssertEqual(active["state"] as? String, "active")
        let done = expectation(description:"replay disconnect")
        DispatchQueue.global().async {
            defer { done.fulfill() }
            try? writeSocket(client, data:encodeJSONLine(["operation":"control.heartbeat", "requestId":"replay", "requestSequence":1]))
            let ended = (try? readSocket(client))?.isEmpty ?? true
            XCTAssertTrue(ended, "Replay kept connection live")
        }
        wait(for:[done], timeout:5)
        let next = try connect()
        XCTAssertEqual(open(next, "successor")["state"] as? String, "offered")
        XCTAssertEqual(effects, 0)
    }
    func testOuterVmsAndPhysicalOwnerShareDesktopAndPausedReferencesFail() throws {
        let directory = NSTemporaryDirectory() + "mc-live-outer-" + UUID().uuidString
        try FileManager.default.createDirectory(atPath:directory, withIntermediateDirectories:false, attributes:[.posixPermissions:0o700])
        defer { try? FileManager.default.removeItem(atPath:directory) }
        func binding(_ name: String) throws -> [String:Any] {
            let value = OuterClaimBinding(directory:directory, provider:"tart-macos", resource:name,
                claim:"c-" + String(repeating:"a",count:24), windowName:name, width:640,height:480,generation:1)
            let format = ISO8601DateFormatter(), now = Date()
            let record: [String:Any] = ["schema":"machine-control-target-claim-record/v0",
                "resource":["provider":"tart-macos","id":name],"generation":1,
                "active":["claimId":value.claim,"mode":"exclusive","useClass":"disruptive","generation":1,
                    "acquiredAt":format.string(from:now.addingTimeInterval(-1)),"expiresAt":format.string(from:now.addingTimeInterval(60))]]
            let path = directory + "/resource-" + value.digest + ".json"
            try JSONSerialization.data(withJSONObject:record).write(to:URL(fileURLWithPath:path)); chmod(path, 0o600)
            return ["schema":"machine-control-outer-borrow/v1","directory":directory,"provider":"tart-macos","resource":name,
                "claimId":value.claim,"generation":1,"windowName":name,"displayWidth":640,"displayHeight":480]
        }
        server.outerRecoveryFactory = { [fixture] binding in
            let value = OuterRecovery(binding:binding, input:{ _ in fixture.effects += 1 })
            value.resolve = { OuterRecovery.Window(id:1,pid:123,bounds:CGRect(x:0,y:0,width:640,height:508)) }
            value.consoleUnlocked = { true }; value.activate = { _ in true }; value.foreground = { _ in true }
            return value
        }
        func openOuter(_ fd: Int32, _ name: String) throws -> [String:Any] {
            let reply = exchange(fd,["operation":"control.open","schema":AccessAdmission.schema,"requestId":name,
                "scopes":["observe","control"],"reason":"Explicit fixture recovery","durationSeconds":60,"waitSeconds":120,
                "outerRecovery":try binding(name)])
            XCTAssertEqual(reply["accepted"] as? Bool,true); return reply["data"] as! [String:Any]
        }
        let a = try connect(), b = try connect(), physical = try connect()
        let first = try openOuter(a,"first-vm"), second = try openOuter(b,"second-vm")
        XCTAssertEqual(first["outerRecovery"] as? String,"borrowed_exact_claim/v1")
        XCTAssertEqual(first["state"] as? String,"offered")
        XCTAssertEqual(second["state"] as? String,"waiting_for_resource")
        XCTAssertEqual(open(physical,"physical")["state"] as? String,"waiting_for_resource")
        let active = command(a,"control.accept",["offerGeneration":first["offerGeneration"]!])["data"] as! [String:Any]
        func dispatch(_ request: [String:Any]) -> [String:Any] {
            command(a,"control.dispatch",["sessionId":active["sessionId"]!,"resourceGenerations":active["resourceGenerations"]!,"request":request])
        }
        let prepared = dispatch(["operation":"outer.prepare"])["data"] as! [String:Any]
        XCTAssertEqual(prepared["accepted"] as? Bool,true)
        let ref = (prepared["data"] as! [String:Any])["reference"]!
        XCTAssertEqual(dispatch(["operation":"outer.begin","reference":ref])["accepted"] as? Bool,true)
        XCTAssertEqual(dispatch(["operation":"outer.step","reference":ref,"kind":"click","x":10,"y":10])["accepted"] as? Bool,true)
        XCTAssertEqual(effects,1)
        try broker.pause(); try broker.resume()
        XCTAssertEqual(dispatch(["operation":"outer.step","reference":ref,"kind":"click","x":10,"y":10])["accepted"] as? Bool,false)
        XCTAssertEqual((command(b,"control.status")["data"] as! [String:Any])["state"] as? String,"offered")
        XCTAssertEqual(effects,1)
    }
    func testWireNumbersCannotBeBooleanOrFractional() {
        XCTAssertNil(admissionInteger(true))
        XCTAssertNil(admissionInteger(1.5))
        XCTAssertEqual(admissionInteger(15), 15)
    }
    func testStalledInitialPeerDoesNotBlockPauseOrAnotherCaller() throws {
        _ = try connect() // deliberately send no first frame
        let live = try connect()
        let first = open(live, "live")
        XCTAssertEqual(first["state"] as? String, "offered")
        try broker.pause()
        XCTAssertEqual((command(live, "control.status")["data"] as? [String:Any])?["state"] as? String, "paused")
        XCTAssertEqual(effects, 0)
    }
    func testDeadWaiterAndLateOfferCannotExecute() throws {
        let a = try connect()
        let initial = open(a, "first")
        clock += 15
        let expired = command(a, "control.accept", ["offerGeneration":initial["offerGeneration"]!])
        XCTAssertEqual(expired["accepted"] as? Bool, false)
        XCTAssertEqual(effects, 0)
        let b = try connect(); _ = open(b, "second")
        clock += 60
        let status = command(b, "control.heartbeat")["data"] as! [String:Any]
        XCTAssertEqual(status["terminalReason"] as? String, "queue_lease_expired")
        XCTAssertEqual(effects, 0)
    }
}
