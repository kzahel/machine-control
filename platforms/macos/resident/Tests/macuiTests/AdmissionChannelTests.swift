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
    private func connect() throws -> Int32 {
        let fd = try residentSocket()
        var (address, length) = try unixAddress(path)
        XCTAssertEqual(withSockAddr(&address, length:length, { Darwin.connect(fd, $0, $1) }), 0)
        clients.append(fd); return fd
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
        broker.resume()
        let next = command(b, "control.status")["data"] as! [String:Any]
        XCTAssertEqual(next["state"] as? String, "offered")
        XCTAssertEqual(command(a, "control.dispatch", action)["accepted"] as? Bool, false)
        _ = command(b, "control.cancel")
        let offered = command(a, "control.status")["data"] as! [String:Any]
        let fresh = command(a, "control.accept", ["offerGeneration":offered["offerGeneration"]!])["data"] as! [String:Any]
        XCTAssertNotEqual(accepted["sessionId"] as? String, fresh["sessionId"] as? String)
        XCTAssertEqual(effects, 1)
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
