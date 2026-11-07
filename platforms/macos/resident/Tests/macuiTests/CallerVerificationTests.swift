import Darwin
import Security
import XCTest
@testable import macui

/// Deterministic process trees for Only verified callers (Tactical 161).
final class CallerTree {
    var records: [pid_t:CallerProcessRecord] = [:]
    var facts: [pid_t:CallerCodeFacts] = [:]
    /// Optional per-PID records returned after the first read, modelling a
    /// process that exits and whose PID is reused mid-verification.
    var replaced: [pid_t:CallerProcessRecord] = [:]
    var reads: [pid_t:Int] = [:]
    var peerPID: pid_t = 100
    var peerAlive = true
    var satisfied: (pid_t, String) -> Bool = { _, _ in true }
    var codeDelay: TimeInterval = 0
    private(set) var codeCalls = 0
    private let lock = NSLock()

    static let own = CallerOwnIdentity(teamID:"MCTEAM0001", bundlePath:"/Applications/Machine Control.app", unsupportedReason:nil)
    static let macui = CallerCodeFacts(valid:true, platform:false, teamID:"MCTEAM0001", identifier:"org.machine-control.app",
                                       path:"/Applications/Machine Control.app", name:"Machine Control", publisher:"MC")
    static let python = CallerCodeFacts(valid:true, platform:false, teamID:"MCTEAM0001", identifier:"python3",
        path:"/Applications/Machine Control.app/Contents/Resources/mc-cli/python/bin/python3", name:"python3", publisher:"MC")
    static let shell = CallerCodeFacts(valid:true, platform:true, identifier:"com.apple.zsh", path:"/bin/zsh", name:"zsh")
    static let adhoc = CallerCodeFacts(valid:false, platform:false, identifier:"node-5555", path:"/opt/homebrew/bin/node", name:"node")
    static func app(_ name: String, team: String = "HOSTTEAM01", identifier: String = "com.example.agent") -> CallerCodeFacts {
        CallerCodeFacts(valid:true, platform:false, teamID:team, identifier:identifier, path:"/Applications/\(name).app",
                        name:name, publisher:"Example Inc")
    }

    /// Builds peer → ancestors → launchd, with strictly increasing ages.
    init(peer: CallerCodeFacts = CallerTree.macui, ancestors: [CallerCodeFacts]) {
        var pid = peerPID
        var started: UInt64 = 1_000_000
        records[pid] = CallerProcessRecord(pid:pid, parent:ancestors.isEmpty ? 1 : pid - 1, started:started)
        facts[pid] = peer
        for (index, value) in ancestors.enumerated() {
            pid -= 1; started -= 10
            records[pid] = CallerProcessRecord(pid:pid, parent:index == ancestors.count - 1 ? 1 : pid - 1, started:started)
            facts[pid] = value
        }
    }
    var source: CallerProcessSource {
        var source = CallerProcessSource()
        source.peer = { [self] _, _ in (peerPID, facts[peerPID]) }
        source.peerAlive = { [self] _ in peerAlive }
        source.record = { [self] pid in
            lock.lock(); defer { lock.unlock() }
            reads[pid, default:0] += 1
            if reads[pid]! > 1, let value = replaced[pid] { return value }
            return records[pid]
        }
        source.code = { [self] pid in
            lock.lock(); codeCalls += 1; lock.unlock()
            if codeDelay > 0 { Thread.sleep(forTimeInterval:codeDelay) }
            return facts[pid]
        }
        source.satisfies = { [self] pid, requirement in satisfied(pid, requirement) }
        return source
    }
    func evaluate(_ approved: [CallerApproval] = [], own: CallerOwnIdentity = CallerTree.own, hops: Int = 12) -> CallerVerdict {
        evaluateCaller(token:Data(count:32), own:own, approved:approved, source:source, maximumHops:hops)
    }
}

func approval(_ team: String = "HOSTTEAM01", _ identifier: String = "com.example.agent") -> CallerApproval {
    CallerApproval(teamID:team, identifier:identifier, name:"Agent", publisher:"Example Inc", approvedAt:"2026-11-07T00:00:00Z")
}

final class CallerVerificationTests: XCTestCase {
    func testRequirementTextAcceptsOnlyExactTeamAndIdentifier() {
        let text = CallerRequirement.host(team:"HOSTTEAM01", identifier:"com.example.agent")
        XCTAssertEqual(text, "anchor apple generic and identifier \"com.example.agent\" and certificate leaf[subject.OU] = \"HOSTTEAM01\"")
        XCTAssertNotNil(CallerRequirement.compile(text!))
        for (team, identifier) in [("hostteam01", "com.example.agent"), ("HOSTTEAM0", "com.example.agent"),
                                   ("HOSTTEAM01", "x\" or anchor apple generic or identifier \"y"),
                                   ("HOSTTEAM01", ""), ("HOSTTEAM01", ".leading"), ("HOSTTEAM01", "space id")] {
            XCTAssertNil(CallerRequirement.host(team:team, identifier:identifier), "\(team) \(identifier)")
        }
    }

    func testRealSecurityRequirementMismatchRefusesALiveProcess() throws {
        let foreign = try XCTUnwrap(CallerRequirement.host(team:"ZZZZZZZZZZ", identifier:"com.example.absent"))
        XCTAssertFalse(CallerProcessSource.liveSatisfies(getpid(), foreign))
        XCTAssertFalse(CallerProcessSource.liveSatisfies(getpid(), "not a requirement"))
        let record = try XCTUnwrap(CallerProcessSource.liveRecord(getpid()))
        XCTAssertEqual(record.pid, getpid())
        // A real parent always started no later than its child.
        let parent = try XCTUnwrap(CallerProcessSource.liveRecord(record.parent))
        XCTAssertLessThanOrEqual(parent.started, record.started)
    }

    func testApprovedSignedHostBehindShellsPasses() {
        let tree = CallerTree(peer:CallerTree.python,
            ancestors:[CallerTree.shell, CallerTree.macui, CallerTree.adhoc, CallerTree.shell, CallerTree.app("Agent")])
        var requirements: [String] = []
        tree.satisfied = { _, requirement in requirements.append(requirement); return true }
        guard case let .verified(host) = tree.evaluate([approval()]) else { return XCTFail("\(tree.evaluate([approval()]))") }
        XCTAssertEqual(host.name, "Agent"); XCTAssertEqual(host.publisher, "Example Inc")
        XCTAssertEqual(requirements.last, CallerRequirement.host(team:"HOSTTEAM01", identifier:"com.example.agent"))
    }

    func testRequirementMismatchAndUnapprovedHostsRefuseWithApprovableHost() {
        let tree = CallerTree(ancestors:[CallerTree.shell, CallerTree.app("Agent")])
        XCTAssertEqual(tree.evaluate(), .refused("unapproved_host", CallerHost(name:"Agent", publisher:"Example Inc",
            teamID:"HOSTTEAM01", identifier:"com.example.agent", approvable:true)))
        // Same publisher, another app; same app, another publisher.
        for other in [approval("HOSTTEAM01", "com.example.other"), approval("OTHERTEAM1", "com.example.agent")] {
            guard case .refused("unapproved_host", _) = tree.evaluate([other]) else { return XCTFail("\(other)") }
        }
        // The stored approval matches by metadata, but live code fails it.
        tree.satisfied = { _, _ in false }
        guard case .refused("unapproved_host", _) = tree.evaluate([approval()]) else { return XCTFail() }
    }

    func testDetachedAndUnsignedHostsCannotPass() {
        XCTAssertEqual(CallerTree(ancestors:[CallerTree.shell, CallerTree.adhoc]).evaluate([approval()]), .refused("detached", nil))
        XCTAssertEqual(CallerTree(ancestors:[]).evaluate([approval()]), .refused("detached", nil))
        var unsigned = CallerTree.app("Homemade"); unsigned.teamID = nil; unsigned.valid = false
        guard case let .refused("unsigned_host", host?) = CallerTree(ancestors:[CallerTree.shell, unsigned]).evaluate([approval()]) else {
            return XCTFail()
        }
        XCTAssertFalse(host.approvable); XCTAssertEqual(host.name, "Homemade")
        // A signed app without a usable identifier is named but not approvable.
        var odd = CallerTree.app("Odd"); odd.identifier = "bad identifier"
        guard case let .refused("unapproved_host", oddHost?) = CallerTree(ancestors:[odd]).evaluate() else { return XCTFail() }
        XCTAssertFalse(oddHost.approvable)
    }

    func testPeerMustBeMachineControlsOwnClient() {
        var foreign = CallerTree.python; foreign.path = "/usr/local/bin/python3"
        XCTAssertEqual(CallerTree(peer:foreign, ancestors:[CallerTree.app("Agent")]).evaluate([approval()]),
                       .refused("peer_not_machine_control", nil))
        var otherTeam = CallerTree.macui; otherTeam.teamID = "OTHERTEAM1"
        XCTAssertEqual(CallerTree(peer:otherTeam, ancestors:[CallerTree.app("Agent")]).evaluate([approval()]),
                       .refused("peer_not_machine_control", nil))
        var invalid = CallerTree.macui; invalid.valid = false
        XCTAssertEqual(CallerTree(peer:invalid, ancestors:[CallerTree.app("Agent")]).evaluate([approval()]),
                       .refused("peer_not_machine_control", nil))
        let gone = CallerTree(ancestors:[CallerTree.app("Agent")]); gone.peerAlive = false
        XCTAssertEqual(gone.evaluate([approval()]), .refused("process_changed", nil))
        XCTAssertEqual(CallerTree(ancestors:[CallerTree.app("Agent")]).evaluate([approval()], own:.unsupportedDevelopment),
                       .refused("verification_unsupported", nil))
    }

    func testAncestryWalkIsBoundedToTwelveHops() {
        let atBound = CallerTree(ancestors:Array(repeating:CallerTree.shell, count:11) + [CallerTree.app("Agent")])
        guard case .verified = atBound.evaluate([approval()]) else { return XCTFail("12th hop should be reachable") }
        let beyond = CallerTree(ancestors:Array(repeating:CallerTree.shell, count:12) + [CallerTree.app("Agent")])
        XCTAssertEqual(beyond.evaluate([approval()]), .refused("ancestry_too_deep", nil))
    }

    func testPIDReuseIsDetectedByStartTime() {
        // A "parent" that started after its child is a reused PID.
        let younger = CallerTree(ancestors:[CallerTree.shell, CallerTree.app("Agent")])
        younger.records[98] = CallerProcessRecord(pid:98, parent:1, started:2_000_000)
        XCTAssertEqual(younger.evaluate([approval()]), .refused("process_changed", nil))
        // The host exits during signature evaluation and its PID is reused.
        let swapped = CallerTree(ancestors:[CallerTree.shell, CallerTree.app("Agent")])
        swapped.replaced[98] = CallerProcessRecord(pid:98, parent:1, started:999_999)
        XCTAssertEqual(swapped.evaluate([approval()]), .refused("process_changed", nil))
        // A vanished parent ends verification instead of skipping a hop.
        let vanished = CallerTree(ancestors:[CallerTree.shell, CallerTree.app("Agent")])
        vanished.records.removeValue(forKey:98)
        XCTAssertEqual(vanished.evaluate([approval()]), .refused("process_changed", nil))
    }

    // MARK: persistence

    private func privateDirectory(mode: mode_t = 0o700) throws -> String {
        let path = NSTemporaryDirectory() + "mc-callers-" + UUID().uuidString
        XCTAssertEqual(mkdir(path, mode), 0); XCTAssertEqual(chmod(path, mode), 0)
        addTeardownBlock { try? FileManager.default.removeItem(atPath:path) }
        return path
    }
    private var host: CallerHost {
        CallerHost(name:"Agent", publisher:"Example Inc", teamID:"HOSTTEAM01", identifier:"com.example.agent", approvable:true)
    }

    func testStoreDefaultsOffAndPersistsPrivately() throws {
        let directory = try privateDirectory()
        let store = CallerVerificationStore(directory:directory)
        XCTAssertTrue(store.storageReady); XCTAssertFalse(store.enforced); XCTAssertTrue(store.approvals.isEmpty)
        try store.configure(enabled:true)
        try store.approve(host)
        try store.approve(host)
        let path = directory + "/caller-verification.json"
        var info = stat(); XCTAssertEqual(stat(path, &info), 0)
        XCTAssertEqual(info.st_mode & 0o777, 0o600)
        let reloaded = CallerVerificationStore(directory:directory)
        XCTAssertTrue(reloaded.enforced); XCTAssertEqual(reloaded.approvals.map(\.key), ["HOSTTEAM01/com.example.agent"])
        try reloaded.remove(team:"HOSTTEAM01", identifier:"com.example.agent")
        try reloaded.configure(enabled:false)
        let off = CallerVerificationStore(directory:directory)
        XCTAssertFalse(off.enforced); XCTAssertTrue(off.approvals.isEmpty)
        XCTAssertThrowsError(try off.approve(CallerHost(name:"x", publisher:"y", teamID:nil, identifier:nil, approvable:false)))
        // No temporary files remain.
        XCTAssertEqual(try FileManager.default.contentsOfDirectory(atPath:directory), ["caller-verification.json"])
    }

    func testUntrustedExistingStateFailsClosed() throws {
        let valid = #"{"approvedHosts":[],"mode":"off","schema":"machine-control-caller-verification/v1"}"#
        let cases: [(String, (String) throws -> Void)] = [
            ("malformed", { try "{".write(toFile:$0, atomically:false, encoding:.utf8); chmod($0, 0o600) }),
            ("unknown mode", { try valid.replacingOccurrences(of:"\"off\"", with:"\"maybe\"").write(toFile:$0, atomically:false, encoding:.utf8); chmod($0, 0o600) }),
            ("bad identifier", { try #"{"approvedHosts":[{"approvedAt":"x","identifier":"a\" or 1","name":"n","publisher":"p","teamId":"HOSTTEAM01"}],"mode":"off","schema":"machine-control-caller-verification/v1"}"#.write(toFile:$0, atomically:false, encoding:.utf8); chmod($0, 0o600) }),
            ("group readable", { try valid.write(toFile:$0, atomically:false, encoding:.utf8); chmod($0, 0o640) }),
            ("symlink", { path in
                let real = path + ".real"; try valid.write(toFile:real, atomically:false, encoding:.utf8); chmod(real, 0o600)
                XCTAssertEqual(symlink(real, path), 0) }),
            ("hard link", { path in
                try valid.write(toFile:path, atomically:false, encoding:.utf8); chmod(path, 0o600)
                XCTAssertEqual(link(path, path + ".alias"), 0) }),
        ]
        for (name, prepare) in cases {
            let directory = try privateDirectory()
            try prepare(directory + "/caller-verification.json")
            let store = CallerVerificationStore(directory:directory)
            XCTAssertTrue(store.storageInvalid, name); XCTAssertTrue(store.enforced, name)
            XCTAssertThrowsError(try store.approve(host), name)
            // The operator can still turn the mode off, replacing the file.
            try store.configure(enabled:false)
            XCTAssertFalse(CallerVerificationStore(directory:directory).enforced, name)
        }
    }

    func testSharedDirectoryCannotEnableTheMode() throws {
        let directory = try privateDirectory(mode:0o755)
        let gate = CallerVerificationGate(directory:directory, own:CallerTree.own)
        XCTAssertFalse(gate.supported); XCTAssertFalse(gate.store.enforced)
        XCTAssertThrowsError(try gate.configure(enabled:true))
        let development = CallerVerificationGate(directory:try privateDirectory(), own:.unsupportedDevelopment)
        XCTAssertThrowsError(try development.configure(enabled:true))
        XCTAssertEqual(development.status["unsupportedReason"] as? String, "development_signature")
        XCTAssertNoThrow(try development.configure(enabled:false))
    }

    // MARK: prompts

    func testPromptIsDebouncedPerHostAndNeverApprovesWithoutAllow() {
        let prompts = CallerApprovalPrompts()
        var clock: TimeInterval = 0
        prompts.now = { clock }
        var shown: [(CallerHost, (Bool) -> Void)] = []
        var approved: [String] = []
        let approve: (CallerHost) throws -> Void = { approved.append($0.key!) }
        XCTAssertEqual(prompts.request(host, approve:approve), "unavailable")
        prompts.present = { host, done in shown.append((host, done)); return true }
        XCTAssertEqual(prompts.request(host, approve:approve), "presented")
        XCTAssertEqual(prompts.request(host, approve:approve), "pending")
        XCTAssertEqual(shown.count, 1)
        let other = CallerHost(name:"Other", publisher:"O", teamID:"OTHERTEAM1", identifier:"com.example.other", approvable:true)
        XCTAssertEqual(prompts.request(other, approve:approve), "presented")
        shown[0].1(false)
        XCTAssertEqual(approved, [])
        XCTAssertEqual(prompts.request(host, approve:approve), "recently_declined")
        clock += 61
        XCTAssertEqual(prompts.request(host, approve:approve), "presented")
        shown[2].1(true)
        XCTAssertEqual(approved, ["HOSTTEAM01/com.example.agent"])
        let unapprovable = CallerHost(name:"U", publisher:"U", teamID:nil, identifier:nil, approvable:false)
        XCTAssertEqual(prompts.request(unapprovable, approve:approve), "unavailable")
        prompts.maximumPending = 1
        let third = CallerHost(name:"T", publisher:"T", teamID:"THIRDTEAM1", identifier:"com.example.third", approvable:true)
        XCTAssertEqual(prompts.request(third, approve:approve), "unavailable", "Other is still pending")
    }
}

/// The gate on the real resident socket, with a modelled process tree.
final class CallerVerificationServerTests: XCTestCase {
    private var server: ResidentServer!
    private var path = ""
    private var directory = ""
    private var clients: [Int32] = []
    private var tree = CallerTree(ancestors:[CallerTree.shell, CallerTree.app("Agent")])

    override func setUpWithError() throws {
        signal(SIGPIPE, SIG_IGN)
        directory = NSTemporaryDirectory() + "mc-gate-" + UUID().uuidString.prefix(8)
        XCTAssertEqual(mkdir(directory, 0o700), 0)
        path = "/tmp/mc-gate-\(getpid())-\(UUID().uuidString.prefix(8)).sock"
        let broker = GrantBroker(policy:.workstation(issue:nil))
        server = ResidentServer(socketPath:path, service:ResidentService(), broker:broker, policyDirectory:try testPolicyRoot())
        server.noticeSeconds = 0
        server.approvalDesktopUnlocked = { true }
        server.grantConsoleObservation = { ["desktopState":"unlocked", "uuid":"fixture", "boot":123, "uid":getuid()] }
        broker.admission.setInputReady(true)
        try server.configureSurface("desktop", mode:"automatic", seconds:nil)
        // Model the console, as AdmissionChannelTests does: the CI host's
        // real session can rotate a generation and refuse status mid-test.
        let console = server.grantConsoleObservation()
        server.service.sessionObservation.stop()
        server.service.sessionObservation = BackgroundObservation(label:"test.callers.session",
            timeout:1, unknown:{ console }, read:{ console })
        server.service.applySessionObservation(console)
        server.nativeProvider.readSession = { console }
        let gate = CallerVerificationGate(directory:directory, own:CallerTree.own)
        gate.source = tree.source
        server.callerGate = gate
        try server.start()
    }
    override func tearDown() {
        for client in clients { Darwin.close(client) }
        clients = []; server.stop(); unlink(path)
        try? FileManager.default.removeItem(atPath:directory)
        server = nil
    }
    private func connect() throws -> Int32 {
        let fd = try residentSocket()
        var (address, length) = try unixAddress(path)
        XCTAssertEqual(withSockAddr(&address, length:length, { Darwin.connect(fd, $0, $1) }), 0)
        clients.append(fd); return fd
    }
    private func exchange(_ request: [String:Any], on existing: Int32? = nil) throws -> [String:Any] {
        let fd = try existing ?? connect()
        let done = expectation(description:"reply")
        var result: [String:Any] = [:]
        DispatchQueue.global().async {
            defer { done.fulfill() }
            try? writeSocket(fd, data:encodeJSONLine(request))
            if let line = try? readSocket(fd), let value = (try? JSONSerialization.jsonObject(with:line)) as? [String:Any] { result = value }
        }
        wait(for:[done], timeout:5)
        return result
    }
    /// The resident closes channel descriptors on its main queue; wait for
    /// EOF without blocking it.
    private func waitClosed(_ fd: Int32, file: StaticString = #filePath, line: UInt = #line) {
        let done = expectation(description:"closed")
        DispatchQueue.global().async {
            var byte: UInt8 = 0
            var input = pollfd(fd:fd, events:Int16(POLLIN), revents:0)
            while poll(&input, 1, 3000) == 1, Darwin.read(fd, &byte, 1) > 0 {}
            if Darwin.read(fd, &byte, 1) == 0 { done.fulfill() }
        }
        wait(for:[done], timeout:4)
    }
    private func open(on fd: Int32) throws -> [String:Any] {
        try exchange(["operation":"control.open", "schema":AccessAdmission.schema, "requestId":UUID().uuidString,
                      "surfaces":["desktop"], "reason":"fixture", "durationSeconds":60, "waitSeconds":120], on:fd)
    }

    func testModeOffLeavesTheSocketUnchanged() throws {
        XCTAssertEqual(try exchange(["operation":"grant.status"])["accepted"] as? Bool, true)
        XCTAssertEqual(try open(on:try connect())["accepted"] as? Bool, true)
        XCTAssertEqual(tree.codeCalls, 0, "No verification work while the mode is off")
        let status = try exchange(["operation":"status"])
        let projection = (status["data"] as? [String:Any])?["callerVerification"] as? [String:Any]
        XCTAssertEqual(projection?["mode"] as? String, "off")
        XCTAssertEqual(projection?["supported"] as? Bool, true)
        XCTAssertEqual(projection?["limits"] as? [String], ["same_user_not_contained"])
    }

    func testDiscoveryStaysOpenWhileOtherOperationsRefuse() throws {
        try server.callerGate.configure(enabled:true)
        let detached = CallerTree(ancestors:[CallerTree.shell])
        server.callerGate.source = detached.source
        let status = try exchange(["operation":"status"])
        XCTAssertEqual(status["accepted"] as? Bool, true, "\(status["errorCode"] ?? "")")
        XCTAssertEqual(((status["data"] as? [String:Any])?["callerVerification"] as? [String:Any])?["mode"] as? String, "verified_only")
        XCTAssertEqual(try exchange(["operation":"capabilities"])["accepted"] as? Bool, true)
        let refused = try exchange(["operation":"grant.status"])
        XCTAssertEqual(refused["errorCode"] as? String, "caller_not_verified")
        XCTAssertEqual(refused["retrySafety"] as? String, "safe_not_dispatched")
        let data = refused["data"] as? [String:Any]
        XCTAssertEqual(data?["reason"] as? String, "detached")
        XCTAssertTrue(data?["callerHost"] is NSNull)
        // The live owner channel refuses in its own schema and closes.
        let fd = try connect()
        let channel = try open(on:fd)
        XCTAssertEqual(channel["schema"] as? String, AdmissionChannel.schema)
        XCTAssertEqual(channel["errorCode"] as? String, "caller_not_verified")
        XCTAssertEqual((channel["data"] as? [String:Any])?["reason"] as? String, "detached")
        waitClosed(fd)
        XCTAssertEqual((server.broker.admission.status["requests"] as? [[String:Any]] ?? []).count, 0)
    }

    func testApprovedHostPassesAndUnapprovedHostPromptsWithoutReplay() throws {
        try server.callerGate.configure(enabled:true)
        var shown: [(CallerHost, (Bool) -> Void)] = []
        server.callerGate.prompts.present = { host, done in shown.append((host, done)); return true }
        let first = try exchange(["operation":"grant.status"])
        XCTAssertEqual(first["errorCode"] as? String, "caller_not_verified")
        let data = first["data"] as? [String:Any]
        XCTAssertEqual(data?["reason"] as? String, "unapproved_host")
        let callerHost = data?["callerHost"] as? [String:Any]
        XCTAssertEqual(callerHost?["name"] as? String, "Agent")
        XCTAssertEqual(callerHost?["publisher"] as? String, "Example Inc")
        XCTAssertEqual(callerHost?["approvable"] as? Bool, true)
        XCTAssertNil(callerHost?["teamId"], "Refusals never carry full requirements")
        XCTAssertEqual(data?["approvalPrompt"] as? String, "presented")
        XCTAssertEqual(try exchange(["operation":"grant.status"])["data"].flatMap { ($0 as? [String:Any])?["approvalPrompt"] as? String }, "pending")
        XCTAssertEqual(shown.count, 1)
        shown[0].1(true)
        XCTAssertEqual(server.callerGate.store.approvals.map(\.key), ["HOSTTEAM01/com.example.agent"])
        XCTAssertEqual(try exchange(["operation":"grant.status"])["accepted"] as? Bool, true)
        let fd = try connect()
        XCTAssertEqual(try open(on:fd)["accepted"] as? Bool, true)
        let status = try exchange(["operation":"status"])
        let hosts = ((status["data"] as? [String:Any])?["callerVerification"] as? [String:Any])?["approvedHosts"] as? [[String:String]]
        XCTAssertEqual(hosts, [["name":"Agent", "publisher":"Example Inc"]])
        // Removing the approval ends the connection it admitted.
        try server.callerGate.store.remove(team:"HOSTTEAM01", identifier:"com.example.agent")
        server.callerVerificationChanged()
        waitClosed(fd)
        XCTAssertEqual(try exchange(["operation":"grant.status"])["errorCode"] as? String, "caller_not_verified")
    }

    func testEnablingEndsUnverifiedOwners() throws {
        let fd = try connect()
        XCTAssertEqual(try open(on:fd)["accepted"] as? Bool, true)
        try server.callerGate.configure(enabled:true)
        server.callerVerificationChanged()
        waitClosed(fd)
    }

    func testVerificationIsBoundedInTimeAndConcurrency() throws {
        let gate = CallerVerificationGate(directory:directory, own:CallerTree.own, concurrency:1)
        try gate.configure(enabled:true)
        let slow = CallerTree(ancestors:[CallerTree.shell, CallerTree.app("Agent")])
        slow.codeDelay = 1.5
        gate.source = slow.source; gate.timeout = 0.3
        server.callerGate = gate
        let first = try connect(), second = try connect()
        let results = [first, second].map { fd -> XCTestExpectation in
            let done = expectation(description:"reply \(fd)")
            DispatchQueue.global().async {
                defer { done.fulfill() }
                try? writeSocket(fd, data:encodeJSONLine(["operation":"grant.status", "requestId":"r\(fd)"]))
                if let line = try? readSocket(fd), let value = (try? JSONSerialization.jsonObject(with:line)) as? [String:Any] {
                    DispatchQueue.main.async { self.reasons.append((value["data"] as? [String:Any])?["reason"] as? String ?? "?") }
                }
            }
            return done
        }
        wait(for:results, timeout:5)
        let settled = expectation(description:"settled"); DispatchQueue.main.async { settled.fulfill() }
        wait(for:[settled], timeout:1)
        XCTAssertEqual(reasons.sorted(), ["verification_busy", "verification_timeout"])
    }
    private var reasons: [String] = []
}
