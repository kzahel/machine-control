import AppKit
import Darwin
import Foundation
import IOKit
import IOKit.pwr_mgt
import Security

func macLidClosed() -> Bool {
    let entry = IOServiceGetMatchingService(kIOMainPortDefault, IOServiceMatching("IOPMrootDomain"))
    guard entry != 0 else { return false }
    defer { IOObjectRelease(entry) }
    return (IORegistryEntryCreateCFProperty(entry, "AppleClamshellState" as CFString,
        kCFAllocatorDefault, 0)?.takeRetainedValue() as? NSNumber)?.boolValue == true
}

/// Wake an idle display only inside an authorized guardian startup. This does
/// not unlock, prevent system sleep, alter power policy, or synthesize input.
/// The assertion is released after readiness or any bounded failure.
struct LockedDisplayWake {
    var observation: () -> [String:Any] = { nativeSessionObservation() }
    var lidClosed: () -> Bool = { macLidClosed() }
    var cancelled: () -> String? = { nil }
    var active: () -> Bool = {
        var count: UInt32 = 0
        return CGGetActiveDisplayList(0, nil, &count) == .success && count > 0
    }
    var now: () -> TimeInterval = { ProcessInfo.processInfo.systemUptime }
    var pause: (TimeInterval) -> Void = { Thread.sleep(forTimeInterval:$0) }
    var declare: () throws -> IOPMAssertionID = {
        var identifier: IOPMAssertionID = 0
        let result = IOPMAssertionDeclareUserActivity("Machine Control covered task startup" as CFString,
            kIOPMUserActiveRemote, &identifier)
        guard result == kIOReturnSuccess else { throw MacUIError.action("locked_use_display_wake_failed") }
        return identifier
    }
    var release: (IOPMAssertionID) -> Void = { _ = IOPMAssertionRelease($0) }

    func prepare(session: [String:Any], deadline: TimeInterval) throws {
        func validate() throws {
            if let reason = cancelled() { throw MacUIError.action(reason) }
            let current = observation()
            guard current["desktopState"] as? String == "locked",
                  (current["uid"] as? NSNumber)?.uint32Value == getuid(),
                  sameConsoleSession(session, current), !lidClosed() else {
                throw MacUIError.action("locked_use_display_wake_session_changed")
            }
            guard now() < deadline else { throw MacUIError.action("duration_expired") }
        }
        try validate()
        if active() { return }
        let assertion = try declare()
        defer { release(assertion) }
        let limit = min(deadline, now() + 3)
        while true {
            try validate()
            if active() { return }
            guard now() < limit else { throw MacUIError.action("locked_use_display_wake_timeout") }
            pause(0.05)
        }
    }
}

private func processCodeHash(_ pid: pid_t) -> Data? {
    var code: SecCode?
    let attributes = [kSecGuestAttributePid as String: pid] as CFDictionary
    guard SecCodeCopyGuestWithAttributes(nil, attributes, [], &code) == errSecSuccess, let code,
          SecCodeCheckValidity(code, SecCSFlags(rawValue:kSecCSStrictValidate), nil) == errSecSuccess else { return nil }
    var info: CFDictionary?
    var staticCode: SecStaticCode?
    guard SecCodeCopyStaticCode(code, [], &staticCode) == errSecSuccess, let staticCode,
          SecCodeCopySigningInformation(staticCode, SecCSFlags(rawValue:kSecCSSigningInformation), &info) == errSecSuccess,
          let values = info as? [String:Any] else { return nil }
    return values[kSecCodeInfoUnique as String] as? Data
}

/// A private inherited socket and matching live signed parent are required.
/// Invoking the command from a shell/pipe cannot manufacture resident authority.
private func validateGuardianParent() throws {
    var uid: uid_t = 0; var gid: gid_t = 0; var peer: pid_t = 0
    var length = socklen_t(MemoryLayout<pid_t>.size)
    guard getpeereid(STDIN_FILENO, &uid, &gid) == 0, uid == getuid(),
          getsockopt(STDIN_FILENO, SOL_LOCAL, LOCAL_PEERPID, &peer, &length) == 0,
          peer == getppid(), peer > 1,
          let ownHash = processCodeHash(getpid()), processCodeHash(peer) == ownHash else {
        throw MacUIError.permission("guardian_parent_untrusted")
    }
}

/// One newline-delimited message, even when adjacent messages share a read.
private func guardianLine(_ fd: Int32) throws -> [String:Any] {
    var data = Data(); var byte: UInt8 = 0
    while data.count < 4096 {
        let count = Darwin.read(fd, &byte, 1)
        if count < 0 && errno == EINTR { continue }
        guard count == 1 else { throw MacUIError.action("guardian_disconnected") }
        if byte == 0x0a {
            guard let value = try JSONSerialization.jsonObject(with:data) as? [String:Any] else {
                throw MacUIError.usage("guardian_invalid_message")
            }
            return value
        }
        data.append(byte)
    }
    throw MacUIError.usage("guardian_message_too_large")
}

/// Small separate signed process: resident death closes the parent connection
/// but does not destroy these windows before the independently observed relock.
private final class CoveredGuardian {
    let service = ResidentService()
    let safety = LockedUseSafety()
    let covers = DisplayCovers()
    lazy var inputGuard = PhysicalInputGuard(safety:safety)
    var helper: Int32 = -1
    var parentBuffer = Data()
    var deadline: TimeInterval = 0
    var parentHeartbeat: TimeInterval = 0
    var helperHeartbeat: TimeInterval = 0
    var initial: [String:Any] = [:]
    var ending: String?
    var ticker: DispatchSourceTimer?

    func start(duration: Int, deadline: TimeInterval) throws {
        self.deadline = deadline
        initial = nativeSessionObservation()
        guard initial["desktopState"] as? String == "locked", !macLidClosed() else {
            throw MacUIError.action("guardian_requires_open_lid_locked_session")
        }
        service.coveredWindowIDs = { [weak self] in self?.covers.windowIDs ?? [] }
        service.inputCancellation = { [weak self] in self?.safety.reason }
        inputGuard.session = initial
        try inputGuard.start()
        safety.arm()
        var displayWake = LockedDisplayWake()
        displayWake.cancelled = { [weak self] in self?.safety.reason }
        try displayWake.prepare(session:initial, deadline:deadline)
        guard inputGuard.healthy, safety.reason == nil else { throw MacUIError.action("guardian_safety_unavailable") }
        try covers.install()
        // Publish cover IDs before arming so parent input cancellation and
        // its capture filter know about the companion during transitions.
        try writeSocket(STDOUT_FILENO, data:encodeJSONLine([
            "phase":"covered", "windowIds":Array(covers.windowIDs), "pid":getpid()]))
        helper = try service.beginCoveredUnlock(duration:duration, deadline:deadline)
        guard covers.healthy, inputGuard.healthy, safety.reason == nil else {
            throw MacUIError.action("guardian_safety_unavailable")
        }
        let now = ProcessInfo.processInfo.systemUptime
        guard now < deadline else { throw MacUIError.action("duration_expired") }
        parentHeartbeat = now + 5
        try writeSocket(STDOUT_FILENO, data:encodeJSONLine([
            "phase":"active", "windowIds":Array(covers.windowIDs), "pid":getpid()]))
        let timer = DispatchSource.makeTimerSource(queue:.main)
        timer.schedule(deadline:.now(), repeating:.milliseconds(250))
        timer.setEventHandler { [weak self] in autoreleasepool { self?.tick() } }
        timer.resume(); ticker = timer
        NSWorkspace.shared.notificationCenter.addObserver(forName:NSWorkspace.willSleepNotification,
            object:nil, queue:.main) { [weak self] _ in self?.end("system_sleep") }
        NSWorkspace.shared.notificationCenter.addObserver(forName:NSWorkspace.screensDidSleepNotification,
            object:nil, queue:.main) { [weak self] _ in self?.end("display_sleep") }
        NotificationCenter.default.addObserver(forName:NSApplication.didChangeScreenParametersNotification,
            object:nil, queue:.main) { [weak self] _ in
                guard let self, !self.covers.healthy else { return }
                self.end("display_changed")
            }
    }

    func end(_ reason: String) {
        if ending == nil {
            ending = reason; _ = safety.interrupt(reason)
            try? writeSocket(STDOUT_FILENO, data:encodeJSONLine(["phase":"interrupted", "reason":reason]))
            if helper >= 0 {
                try? writeSocket(helper, data:encodeJSONLine([
                    "operation":cleanCoveredEnding(reason) ? "complete" : "cancel", "reason":reason]))
                Darwin.close(helper); helper = -1
            }
        }
        ConsoleRelock.request(for:initial)
    }

    func tick() {
        let current = nativeSessionObservation()
        if let ending {
            if current["desktopState"] as? String == "locked" || consoleSessionReplaced(initial, current) {
                covers.removeAfterLock(); safety.disarm(); inputGuard.stop()
                try? writeSocket(STDOUT_FILENO, data:encodeJSONLine(["phase":"ended", "reason":ending, "lockObserved":current["desktopState"] as? String == "locked"]))
                exit(0)
            }
            ConsoleRelock.request(for:initial); return
        }
        let now = ProcessInfo.processInfo.systemUptime
        if let reason = safety.reason { end(reason); return }
        guard sameConsoleSession(initial, current), current["desktopState"] as? String == "unlocked",
              covers.healthy, inputGuard.healthy, !macLidClosed() else { end("guardian_safety_unavailable"); return }
        if now >= deadline { end("duration_expired"); return }
        if now >= parentHeartbeat || getppid() == 1 { end("owner_disconnected"); return }
        var p = pollfd(fd:STDIN_FILENO, events:Int16(POLLIN | POLLHUP), revents:0)
        if poll(&p, 1, 0) > 0 {
            var bytes = [UInt8](repeating:0, count:512)
            let n = recv(STDIN_FILENO, &bytes, bytes.count, MSG_DONTWAIT)
            guard n > 0 else { end("owner_disconnected"); return }
            parentBuffer.append(bytes, count:n)
            guard parentBuffer.count <= 4096 else { end("invalid_heartbeat"); return }
            while let newline = parentBuffer.firstIndex(of:0x0a) {
                let line = Data(parentBuffer[..<newline]); parentBuffer.removeSubrange(...newline)
                let message = (try? JSONSerialization.jsonObject(with:line)) as? [String:Any]
                if message?.count == 1 && message?["operation"] as? String == "heartbeat" { parentHeartbeat = now + 5 }
                else { end(message?["operation"] as? String == "complete" ? "completed" : message?["reason"] as? String ?? "owner_disconnected"); return }
            }
        }
        var h = pollfd(fd:helper, events:Int16(POLLIN | POLLHUP), revents:0)
        if poll(&h, 1, 0) > 0 { end("watchdog_interrupted"); return }
        if now - helperHeartbeat >= 1 {
            do { try writeSocket(helper, data:encodeJSONLine(["operation":"heartbeat"])); helperHeartbeat = now }
            catch { end("watchdog_interrupted") }
        }
    }
}

func runLockedUseGuardian() throws -> Never {
    signal(SIGPIPE, SIG_IGN)
    try validateGuardianParent()
    var timeout = timeval(tv_sec:5, tv_usec:0)
    setsockopt(STDIN_FILENO, SOL_SOCKET, SO_RCVTIMEO, &timeout, socklen_t(MemoryLayout.size(ofValue:timeout)))
    let request = try guardianLine(STDIN_FILENO)
    guard request.count == 3, request["operation"] as? String == "begin",
          let duration = ControlSessionLease.duration(request["durationSeconds"]),
          let deadline = request["deadlineUptime"] as? Double, deadline.isFinite,
          deadline > ProcessInfo.processInfo.systemUptime,
          deadline <= ProcessInfo.processInfo.systemUptime + Double(duration) + 1 else {
        throw MacUIError.usage("guardian_invalid_start")
    }
    // This companion has no restorable operator UI. Do not inherit a crash
    // restoration dialog from another process using the product bundle ID.
    UserDefaults.standard.setVolatileDomain(["ApplePersistenceIgnoreState":true,
        "NSQuitAlwaysKeepsWindows":false], forName:UserDefaults.argumentDomain)
    let app = NSApplication.shared; app.setActivationPolicy(.accessory)
    let guardian = CoveredGuardian()
    do { try guardian.start(duration:duration, deadline:deadline) }
    catch {
        try? writeSocket(STDOUT_FILENO, data:encodeJSONLine(["phase":"error", "reason":String(describing:error)]))
        if guardian.covers.windows.isEmpty { guardian.inputGuard.stop(); exit(1) }
        // If setup created any windows, retain them until OS lock readback.
        guardian.end(String(describing:error))
        while nativeSessionObservation()["desktopState"] as? String != "locked" &&
                !consoleSessionReplaced(guardian.initial, nativeSessionObservation()) {
            ConsoleRelock.request(for:guardian.initial); Thread.sleep(forTimeInterval:0.05)
        }
        guardian.covers.removeAfterLock(); guardian.safety.disarm(); guardian.inputGuard.stop()
        exit(1)
    }
    withExtendedLifetime(guardian) { app.run() }
    exit(0)
}

/// Parent endpoint. Only typed start/heartbeat/stop messages cross the private
/// socket; no agent-facing endpoint can invoke guardian setup or grant access.
final class CoveredGuardianClient {
    private let lock = NSLock()
    private var ids = Set<Int>()
    private var active = false
    private var ended = false
    private var failure: String?
    private var descriptor: Int32 = -1
    private var child: Process?
    private let safety: LockedUseSafety
    init(safety:LockedUseSafety) { self.safety = safety }
    var windowIDs: Set<Int> { lock.lock(); defer { lock.unlock() }; return ids }
    var healthy: Bool { lock.lock(); defer { lock.unlock() }; return active && !ended && failure == nil }

    func start(duration:Int, deadline:TimeInterval) throws {
        guard let executable = Bundle.main.executableURL else { throw MacUIError.action("guardian_executable_missing") }
        var sockets: [Int32] = [-1,-1]
        guard socketpair(AF_UNIX, SOCK_STREAM, 0, &sockets) == 0 else { throw MacUIError.action("guardian_socket_failed") }
        try closeOnExec(sockets[0]); try closeOnExec(sockets[1])
        var noSignal: Int32 = 1
        for fd in sockets { setsockopt(fd, SOL_SOCKET, SO_NOSIGPIPE, &noSignal, socklen_t(MemoryLayout.size(ofValue:noSignal))) }
        descriptor = sockets[0]
        let endpoint = FileHandle(fileDescriptor:sockets[1], closeOnDealloc:true)
        let process = Process(); process.executableURL = executable; process.arguments = ["locked-use-guardian"]
        process.standardInput = endpoint; process.standardOutput = endpoint; process.standardError = FileHandle.nullDevice
        do { try process.run() } catch { Darwin.close(sockets[0]); descriptor = -1; throw error }
        try endpoint.close(); child = process
        let ready = DispatchSemaphore(value:0)
        let fd = descriptor
        DispatchQueue.global(qos:.userInitiated).async { [self] in
            var signalled = false
            defer { if !signalled { ready.signal() } }
            do {
                while true {
                    let message = try guardianLine(fd)
                    let phase = message["phase"] as? String ?? "error"
                    lock.lock()
                    if let values = message["windowIds"] as? [Int] { ids = Set(values) }
                    if phase == "active" { active = true }
                    if ["interrupted", "error"].contains(phase) { failure = message["reason"] as? String ?? "guardian_interrupted" }
                    if phase == "ended" { ended = true; active = false }
                    let reason = failure
                    lock.unlock()
                    if let reason { _ = safety.interrupt(reason) }
                    if phase == "active" || phase == "error" {
                        if !signalled { signalled = true; ready.signal() }
                    }
                    if phase == "ended" { return }
                }
            } catch {
                lock.lock(); ended = true; active = false; failure = failure ?? "guardian_disconnected"; let reason = failure!; lock.unlock()
                _ = safety.interrupt(reason)
            }
        }
        try writeSocket(descriptor, data:encodeJSONLine(["operation":"begin", "durationSeconds":duration, "deadlineUptime":deadline]))
        guard ready.wait(timeout:.now() + 12) == .success, healthy else {
            stop(reason:"guardian_start_failed")
            lock.lock(); let reason = failure; lock.unlock()
            throw MacUIError.action(reason ?? "guardian_start_failed")
        }
    }
    func heartbeat() throws {
        guard descriptor >= 0, healthy else { throw MacUIError.action("guardian_disconnected") }
        try writeSocket(descriptor, data:encodeJSONLine(["operation":"heartbeat"]))
    }
    func stop(reason:String) {
        guard descriptor >= 0 else { return }
        try? writeSocket(descriptor, data:encodeJSONLine(["operation":reason == "completed" ? "complete" : "cancel", "reason":reason]))
        _ = Darwin.shutdown(descriptor, SHUT_WR)
    }
    func closeAfterLock() {
        guard descriptor >= 0 else { return }
        _ = Darwin.shutdown(descriptor, SHUT_RDWR); Darwin.close(descriptor); descriptor = -1
        lock.lock(); ids.removeAll(); active = false; ended = true; lock.unlock()
        // The companion exits itself after lock. Reap it without blocking the
        // main event loop; never terminate its covers while still unlocked.
        if let child { DispatchQueue.global().async { child.waitUntilExit() } }
        child = nil
    }
}
