import ApplicationServices
import CryptoKit
import Darwin
import Foundation

enum ProbeError: Error { case refused(String) }

func json(_ value: Any) throws -> Data {
    try JSONSerialization.data(withJSONObject: value, options: [.sortedKeys])
}

struct Options {
    let fixture: URL
    let output: URL
    let reads: Int
    let replacements: Int

    init(_ args: [String]) throws {
        // Gate before AXIsProcessTrusted, process launch, or any native reads.
        guard args.count >= 6, args[1] == "--disposable-guest" else {
            throw ProbeError.refused("Requires explicit --disposable-guest; never run on the controller desktop")
        }
        var values: [String: String] = [:]
        var index = 2
        while index < args.count {
            guard index + 1 < args.count,
                  ["--fixture", "--output", "--reads", "--replacements"].contains(args[index]),
                  values[args[index]] == nil else { throw ProbeError.refused("invalid_arguments") }
            values[args[index]] = args[index + 1]; index += 2
        }
        guard let fixture = values["--fixture"], fixture.hasPrefix("/"),
              let output = values["--output"], output.hasPrefix("/"),
              let reads = Int(values["--reads"] ?? "10"), (2...50).contains(reads),
              let replacements = Int(values["--replacements"] ?? "5"), (1...50).contains(replacements) else {
            throw ProbeError.refused("requires_absolute_fixture_and_new_output; reads 2...50; replacements 1...50")
        }
        self.fixture = URL(fileURLWithPath: fixture, isDirectory: true)
        self.output = URL(fileURLWithPath: output, isDirectory: true)
        self.reads = reads; self.replacements = replacements
    }
}

final class Retained {
    let handle: String
    let element: AXUIElement
    let incarnation: String
    let process: String
    let window: String
    let pid: pid_t
    let kind: String
    var destructionRegistration: Int32?

    init(handle: String, element: AXUIElement, incarnation: String,
         state: [String: Any], kind: String) {
        self.handle = handle; self.element = element; self.incarnation = incarnation
        self.process = state["processIncarnation"] as! String
        self.window = state["windowIncarnation"] as! String
        self.pid = (state["pid"] as! NSNumber).int32Value
        self.kind = kind
    }

    var identity: [String: Any] {
        ["handle": handle, "oracleIncarnation": incarnation, "processIncarnation": process,
         "windowIncarnation": window, "pid": pid, "kind": kind, "nativeHash": CFHash(element),
         "destroyRegistration": destructionRegistration ?? -1]
    }
}

func destroyedCallback(_ observer: AXObserver, _ element: AXUIElement,
                       _ notification: CFString, _ context: UnsafeMutableRawPointer?) {
    guard let context else { return }
    let probe = Unmanaged<IdentityProbe>.fromOpaque(context).takeUnretainedValue()
    probe.notifications.append([
        "name": notification as String, "uptime": ProcessInfo.processInfo.systemUptime,
        "nativeHash": CFHash(element),
        "equalRetainedHandles": probe.retained.filter { CFEqual($0.element, element) }.map(\.handle),
    ])
}

final class IdentityProbe {
    let options: Options
    let nonce = UUID().uuidString
    var retained: [Retained] = []
    var notifications: [[String: Any]] = []
    var records: [[String: Any]] = []
    var children: [Process] = []
    var observers: [String: AXObserver] = [:]
    var observerSources: [CFRunLoopSource] = []
    var childRoot: URL?
    var child: Process?
    var processIncarnation = ""
    var cleanupReceipts: [[String: Any]] = []
    var ownedProcesses: [[String: Any]] = []
    var childIncarnations: [ObjectIdentifier: String] = [:]

    init(_ options: Options) throws {
        self.options = options
        guard !FileManager.default.fileExists(atPath: options.output.path),
              FileManager.default.isExecutableFile(atPath: options.fixture
                .appendingPathComponent("Contents/MacOS/IdentityFixture").path) else {
            throw ProbeError.refused("output_must_be_new_and_fixture_must_be_built")
        }
        let build = try JSONSerialization.jsonObject(with: Data(contentsOf: options.fixture
            .deletingLastPathComponent().appendingPathComponent("build.json"))) as? [String: Any]
        guard let build, build["schema"] as? String == "machine-control/native-identity-build/v1",
              let hashes = build["binary_sha256"] as? [String: String] else {
            throw ProbeError.refused("build_manifest_required")
        }
        let fixtureBinary = options.fixture.appendingPathComponent("Contents/MacOS/IdentityFixture")
        let probeBinary = URL(fileURLWithPath: CommandLine.arguments[0])
        func digest(_ url: URL) throws -> String {
            SHA256.hash(data: try Data(contentsOf: url)).map { String(format: "%02x", $0) }.joined()
        }
        guard try digest(fixtureBinary) == hashes["IdentityFixture.app/Contents/MacOS/IdentityFixture"],
              try digest(probeBinary) == hashes["IdentityProbe.app/Contents/MacOS/IdentityProbe"] else {
            throw ProbeError.refused("build_binary_hash_mismatch")
        }
        try FileManager.default.createDirectory(at: options.output, withIntermediateDirectories: false,
                                                attributes: [.posixPermissions: 0o700])
        try json(["schema": "machine-control/native-identity-run/v1", "status": "started",
                  "disposableGuestAssertion": true, "reads": options.reads,
                  "replacements": options.replacements, "runNonce": nonce,
                  "probePID": ProcessInfo.processInfo.processIdentifier,
                  "osVersion": ProcessInfo.processInfo.operatingSystemVersionString,
                  "fixture": options.fixture.path, "build": build]).write(to: options.output.appendingPathComponent("run.json"))
    }

    func pump(_ seconds: Double) {
        let end = ProcessInfo.processInfo.systemUptime + seconds
        while ProcessInfo.processInfo.systemUptime < end {
            RunLoop.current.run(until: Date(timeIntervalSinceNow: min(0.01, max(0, end - ProcessInfo.processInfo.systemUptime))))
        }
    }

    func append(_ record: [String: Any]) throws {
        records.append(record)
        // Atomic checkpoints preserve failures and all prior attempts.
        try json(records).write(to: options.output.appendingPathComponent("records.json"), options: .atomic)
    }

    func readState() throws -> [String: Any] {
        guard let root = childRoot, let child else { throw ProbeError.refused("fixture_not_started") }
        let value = try JSONSerialization.jsonObject(with: Data(contentsOf: root.appendingPathComponent("state.json")))
        guard let state = value as? [String: Any], state["runNonce"] as? String == nonce,
              (state["pid"] as? NSNumber)?.int32Value == child.processIdentifier,
              let process = state["processIncarnation"] as? String,
              !process.isEmpty, state["windowIncarnation"] is String,
              state["items"] is [[String: Any]], state["effects"] is [String: Int],
              processIncarnation.isEmpty || process == processIncarnation else {
            throw ProbeError.refused("fixture_oracle_identity_mismatch")
        }
        return state
    }

    func command(_ operation: String, logical: String? = nil) throws -> [String: Any] {
        guard let root = childRoot else { throw ProbeError.refused("fixture_not_started") }
        let id = UUID().uuidString
        var request = ["id": id, "operation": operation, "runNonce": nonce]
        if let logical { request["logical"] = logical }
        try json(request).write(to: root.appendingPathComponent("command.json"), options: .atomic)
        let deadline = ProcessInfo.processInfo.systemUptime + 5
        while ProcessInfo.processInfo.systemUptime < deadline {
            if let state = try? readState(), state["lastCommand"] as? String == id {
                if let error = state["commandError"] { throw ProbeError.refused("fixture_command_error: \(error)") }
                return state
            }
            pump(0.01)
        }
        throw ProbeError.refused("fixture_command_timeout: \(operation)")
    }

    func launch() throws {
        let root = options.output.appendingPathComponent("process-\(children.count + 1)", isDirectory: true)
        try FileManager.default.createDirectory(at: root, withIntermediateDirectories: false,
                                                attributes: [.posixPermissions: 0o700])
        let log = root.appendingPathComponent("fixture.log")
        guard FileManager.default.createFile(atPath: log.path, contents: nil,
                                             attributes: [.posixPermissions: 0o600]) else {
            throw ProbeError.refused("fixture_log_unavailable")
        }
        let handle = try FileHandle(forWritingTo: log)
        defer { try? handle.close() }
        let next = Process()
        next.executableURL = options.fixture.appendingPathComponent("Contents/MacOS/IdentityFixture")
        next.arguments = ["--disposable-guest", "--root", root.path, "--run-nonce", nonce]
        next.standardOutput = handle; next.standardError = handle
        try next.run()
        children.append(next); child = next; childRoot = root; processIncarnation = ""
        let deadline = ProcessInfo.processInfo.systemUptime + 8
        while ProcessInfo.processInfo.systemUptime < deadline {
            if let state = try? readState() {
                processIncarnation = state["processIncarnation"] as! String
                ownedProcesses.append(["pid": next.processIdentifier, "processIncarnation": processIncarnation])
                childIncarnations[ObjectIdentifier(next)] = processIncarnation
                var observer: AXObserver?
                let status = AXObserverCreate(next.processIdentifier, destroyedCallback, &observer)
                try append(["kind": "observerCreated", "pid": next.processIdentifier,
                            "processIncarnation": processIncarnation, "axError": status.rawValue])
                if status == .success, let observer {
                    observers[processIncarnation] = observer
                    let source = AXObserverGetRunLoopSource(observer)
                    observerSources.append(source)
                    CFRunLoopAddSource(CFRunLoopGetCurrent(), source, .defaultMode)
                }
                return
            }
            guard next.isRunning else { throw ProbeError.refused("fixture_exited_before_ready") }
            pump(0.02)
        }
        throw ProbeError.refused("fixture_launch_timeout")
    }

    func attribute(_ element: AXUIElement, _ name: CFString) -> (AXError, CFTypeRef?) {
        var value: CFTypeRef?
        let code = AXUIElementCopyAttributeValue(element, name, &value)
        return (code, value)
    }

    func requireOwnedOrDeadPID(_ pid: pid_t) throws {
        if children.contains(where: { $0.isRunning && $0.processIdentifier == pid }) { return }
        errno = 0
        let exists = kill(pid, 0) == 0 || errno != ESRCH
        guard !exists else {
            // Do not probe a retained PID that has become an unrelated process.
            // PID reuse by a new owned fixture is addressable and measured;
            // unowned reuse is an explicit incomplete-run refusal.
            throw ProbeError.refused("retained_pid_now_unowned; no AX read/action dispatched")
        }
    }

    func nativeDescription(_ element: AXUIElement) -> [String: Any] {
        var result: [String: Any] = [:]
        for name in [kAXRoleAttribute, kAXIdentifierAttribute, kAXTitleAttribute] {
            let (code, value) = attribute(element, name as CFString)
            result[name + "Error"] = code.rawValue
            if let value = value as? String { result[name] = value }
        }
        for (name, point) in [(kAXPositionAttribute, true), (kAXSizeAttribute, false)] {
            let (code, value) = attribute(element, name as CFString)
            result[name + "Error"] = code.rawValue
            if let value, CFGetTypeID(value) == AXValueGetTypeID() {
                let ax = unsafeBitCast(value, to: AXValue.self)
                if point {
                    var p = CGPoint.zero
                    if AXValueGetType(ax) == .cgPoint, AXValueGetValue(ax, .cgPoint, &p) { result[name] = [p.x, p.y] }
                } else {
                    var size = CGSize.zero
                    if AXValueGetType(ax) == .cgSize, AXValueGetValue(ax, .cgSize, &size) { result[name] = [size.width, size.height] }
                }
            }
        }
        return result
    }

    func retain(_ element: AXUIElement, incarnation: String, state: [String: Any], kind: String) -> Retained {
        let item = Retained(handle: "h\(retained.count + 1)", element: element,
                            incarnation: incarnation, state: state, kind: kind)
        retained.append(item)
        if let observer = observers[item.process] {
            item.destructionRegistration = AXObserverAddNotification(observer, element,
                kAXUIElementDestroyedNotification as CFString,
                Unmanaged.passUnretained(self).toOpaque()).rawValue
        }
        return item
    }

    @discardableResult
    func snapshot(_ scenario: String) throws -> [String: Retained] {
        let state = try command("barrier")
        // Bounded collection interval for notifications, not proof of quietness.
        pump(0.15)
        let root = AXUIElementCreateApplication(child!.processIdentifier)
        _ = AXUIElementSetMessagingTimeout(root, 0.5)
        let (windowCode, rawWindows) = attribute(root, kAXWindowsAttribute as CFString)
        guard windowCode == .success, let windows = rawWindows as? [AXUIElement], windows.count == 1 else {
            try append(["kind": "snapshotFailure", "scenario": scenario, "oracle": state,
                        "windowsError": windowCode.rawValue])
            throw ProbeError.refused("expected_one_exact_fixture_window")
        }
        let oracleItems = state["items"] as! [[String: Any]]
        let expected = Set(oracleItems.map { $0["incarnation"] as! String })
        let joins = Dictionary(uniqueKeysWithValues: oracleItems.map {
            ($0["identifier"] as! String, $0["incarnation"] as! String)
        })
        let previous = retained
        var current: [String: Retained] = [:]
        var traversal: [[String: Any]] = []
        var visited = 0
        func walk(_ element: AXUIElement, depth: Int) throws {
            guard depth <= 20, visited < 2000 else { throw ProbeError.refused("probe_tree_truncated") }
            visited += 1
            _ = AXUIElementSetMessagingTimeout(element, 0.5)
            let description = nativeDescription(element)
            traversal.append(description.merging(["depth": depth]) { _, new in new })
            // Slot identifiers join this sample to the independent oracle;
            // replacement deliberately reuses the slot identifier. They are
            // never equality keys or evidence of incarnation continuity.
            if let nativeID = description[kAXIdentifierAttribute] as? String, let id = joins[nativeID] {
                guard current[id] == nil else { throw ProbeError.refused("duplicate_fixture_incarnation_in_tree") }
                current[id] = retain(element, incarnation: id, state: state, kind: "control")
            }
            let (code, value) = attribute(element, kAXChildrenAttribute as CFString)
            guard code == .success || code == .noValue || code == .attributeUnsupported else {
                throw ProbeError.refused("probe_children_read_failed: \(code.rawValue)")
            }
            for child in value as? [AXUIElement] ?? [] { try walk(child, depth: depth + 1) }
        }
        try walk(windows[0], depth: 0)
        guard Set(current.keys) == expected else {
            try append(["kind": "snapshotFailure", "scenario": scenario, "oracle": state,
                        "traversal": traversal, "foundIncarnations": Array(current.keys).sorted()])
            throw ProbeError.refused("fixture_controls_missing_from_ax_tree")
        }
        let windowID = "identity-window-" + (state["windowIncarnation"] as! String)
        current[windowID] = retain(windows[0], incarnation: windowID, state: state, kind: "window")
        let ordered = current.values.sorted { $0.handle.localizedStandardCompare($1.handle) == .orderedAscending }
        var comparisons: [[String: Any]] = []
        for old in previous {
            for new in ordered {
                comparisons.append(["prior": old.handle, "current": new.handle,
                    "sameOracleIncarnation": old.incarnation == new.incarnation && old.process == new.process && old.window == new.window,
                    "sameProcessEpoch": old.process == new.process, "sameWindowEpoch": old.window == new.window,
                    "nativeEqual": CFEqual(old.element, new.element),
                    "hashEqual": CFHash(old.element) == CFHash(new.element)])
            }
        }
        let validity = try previous.map { old -> [String: Any] in
            try requireOwnedOrDeadPID(old.pid)
            let (code, _) = attribute(old.element, kAXRoleAttribute as CFString)
            return ["handle": old.handle, "roleReadError": code.rawValue,
                    "oracleStillPresent": old.process == processIncarnation && old.window == state["windowIncarnation"] as? String &&
                        (expected.contains(old.incarnation) || old.incarnation == windowID)]
        }
        try append(["kind": "snapshot", "scenario": scenario, "oracle": state,
                    "handles": ordered.map { $0.identity.merging(["native": nativeDescription($0.element)]) { _, new in new } },
                    "comparisons": comparisons, "retainedValidity": validity,
                    "traversal": traversal, "notificationsThroughSnapshot": notifications.count])
        return current
    }

    func control(_ snapshot: [String: Retained], logical: String) throws -> Retained {
        let state = try readState()
        guard let item = (state["items"] as! [[String: Any]]).first(where: { $0["logical"] as? String == logical }),
              let id = item["incarnation"] as? String, let handle = snapshot[id] else {
            throw ProbeError.refused("fixture_control_not_observed")
        }
        return handle
    }

    func action(_ handle: Retained, scenario: String, expectedCurrent: Bool) throws {
        let before = try command("barrier")
        try requireOwnedOrDeadPID(handle.pid)
        let (roleCode, _) = attribute(handle.element, kAXRoleAttribute as CFString)
        let code = AXUIElementPerformAction(handle.element, kAXPressAction as CFString)
        pump(0.2)
        let after = try command("barrier")
        let old = before["effects"] as! [String: Int]
        let new = after["effects"] as! [String: Int]
        var deltas: [String: Int] = [:]
        for id in Set(old.keys).union(new.keys) where new[id, default: 0] != old[id, default: 0] {
            deltas[id] = new[id, default: 0] - old[id, default: 0]
        }
        try append(["kind": "action", "scenario": scenario, "handle": handle.handle,
                    "oracleIncarnation": handle.incarnation, "expectedCurrent": expectedCurrent,
                    "roleReadBeforeError": roleCode.rawValue,
                    "axError": code.rawValue, "effectDeltas": deltas, "before": before, "after": after])
    }

    func run() throws {
        guard AXIsProcessTrusted() else {
            throw ProbeError.refused("accessibility_not_trusted; authorize this exact probe inside disposable guest, never prompt on host")
        }
        try launch()
        var current = try snapshot("initial")
        let initial = try control(current, logical: "a")
        try action(initial, scenario: "initial_current", expectedCurrent: true)
        for index in 1...options.reads { current = try snapshot("unchanged_\(index)") }
        _ = try command("insert"); current = try snapshot("insertion")
        _ = try command("reorder"); current = try snapshot("reorder")
        for index in 1...options.replacements {
            let old = try control(current, logical: "a")
            _ = try command("replace", logical: "a")
            current = try snapshot("replacement_\(index)")
            try action(old, scenario: "replacement_\(index)_stale", expectedCurrent: false)
            try action(control(current, logical: "a"), scenario: "replacement_\(index)_current", expectedCurrent: true)
        }
        let removed = try control(current, logical: "b")
        _ = try command("remove", logical: "b"); current = try snapshot("removal")
        try action(removed, scenario: "removal_stale", expectedCurrent: false)
        let oldWindow = try control(current, logical: "a")
        _ = try command("recreateWindow"); current = try snapshot("window_recreation")
        try action(oldWindow, scenario: "window_recreation_stale", expectedCurrent: false)
        let oldProcess = try control(current, logical: "a")
        try action(oldProcess, scenario: "window_recreation_current", expectedCurrent: true)
        _ = try command("quit")
        let deadline = ProcessInfo.processInfo.systemUptime + 5
        while child!.isRunning && ProcessInfo.processInfo.systemUptime < deadline { pump(0.02) }
        guard !child!.isRunning else { throw ProbeError.refused("fixture_did_not_quit") }
        try launch(); current = try snapshot("process_recreation")
        try action(oldProcess, scenario: "process_recreation_stale", expectedCurrent: false)
        try action(control(current, logical: "a"), scenario: "process_recreation_current", expectedCurrent: true)
        // Probe the earliest retained proxy too, after both lifetime boundaries.
        try action(initial, scenario: "initial_after_process_recreation_stale", expectedCurrent: false)
        pump(0.25)
    }

    func cleanup() {
        for child in children {
            var forced = false
            if child.isRunning {
                child.terminate()
                let deadline = ProcessInfo.processInfo.systemUptime + 3
                while child.isRunning && ProcessInfo.processInfo.systemUptime < deadline { pump(0.02) }
                if child.isRunning { forced = true; kill(child.processIdentifier, SIGKILL) }
            }
            child.waitUntilExit()
            cleanupReceipts.append(["pid": child.processIdentifier, "reaped": !child.isRunning,
                                    "processIncarnation": childIncarnations[ObjectIdentifier(child)] ?? "unobserved",
                                    "terminationStatus": child.terminationStatus, "forced": forced])
        }
        pump(0.1)
        for source in observerSources { CFRunLoopRemoveSource(CFRunLoopGetCurrent(), source, .defaultMode) }
        observerSources.removeAll(); observers.removeAll()
    }

    func finish(_ failure: String?) throws {
        try json(notifications).write(to: options.output.appendingPathComponent("notifications.json"), options: .atomic)
        var run = try JSONSerialization.jsonObject(with: Data(contentsOf: options.output.appendingPathComponent("run.json"))) as! [String: Any]
        run["status"] = failure == nil ? "complete" : "failed"
        run["failure"] = failure
        run["ownedProcesses"] = ownedProcesses
        run["cleanup"] = cleanupReceipts
        run["notificationCollection"] = "bounded event-loop intervals; absent notification is not proof of no destruction"
        try json(run).write(to: options.output.appendingPathComponent("run.json"), options: .atomic)
    }
}

do {
    let probe = try IdentityProbe(Options(CommandLine.arguments))
    var failure: String?
    do { try probe.run() } catch { failure = String(describing: error) }
    probe.cleanup()
    try probe.finish(failure)
    if let failure { fputs("\(failure)\n", stderr); exit(1) }
} catch {
    fputs("\(error)\n", stderr)
    exit(64)
}
