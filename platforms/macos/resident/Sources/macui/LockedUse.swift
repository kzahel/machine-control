import AppKit
import ApplicationServices
import CoreGraphics
import Darwin
import Foundation
import ScreenCaptureKit

/// The setting is not authority. A live ordinary grant and this bounded,
/// connection-owned lease must both exist before any covered unlock.
struct ControlSessionLease {
    static let maximumDuration = 900
    let id: String
    let grantID: String
    let session: [String: Any]
    let deadline: TimeInterval
    var heartbeatDeadline: TimeInterval

    static func duration(_ value: Any?) -> Int? {
        guard let number = value as? NSNumber,
              CFGetTypeID(number) != CFBooleanGetTypeID(),
              number.doubleValue == Double(number.intValue),
              (1...maximumDuration).contains(number.intValue) else { return nil }
        return number.intValue
    }

    func refusal(now: TimeInterval, grantID: String?, session: [String: Any]) -> String? {
        if self.grantID != grantID { return "access_ended" }
        if now >= deadline { return "duration_expired" }
        if now >= heartbeatDeadline { return "owner_disconnected" }
        if !sameConsoleSession(self.session, session) { return "session_changed" }
        return nil
    }
}

func sameConsoleSession(_ a: [String: Any], _ b: [String: Any]) -> Bool {
    ["uuid", "boot", "uid"].allSatisfy { key in
        guard let left = a[key] as? NSObject, let right = b[key] as? NSObject else { return false }
        return left == right
    }
}

func consoleSessionReplaced(_ initial: [String:Any], _ current: [String:Any]) -> Bool {
    ["uuid", "boot", "uid"].allSatisfy { current[$0] is NSObject } &&
        !sameConsoleSession(initial, current)
}

/// Retained access belongs to the same console in which the person approved it.
/// A preference cannot transfer that approval across logout or user switching.
struct GrantConsoleBinding {
    let grantID: String
    let session: [String:Any]
    init?(grantID: String, observation: [String:Any], restoring: Bool = false) {
        guard (observation["desktopState"] as? String == "unlocked" || (restoring && observation["desktopState"] as? String == "locked")),
              (observation["uid"] as? NSNumber)?.uint32Value == getuid(),
              sameConsoleSession(observation, observation) else { return nil }
        self.grantID = grantID; session = observation
    }
    func matches(grantID: String, observation: [String:Any]) -> Bool {
        self.grantID == grantID && sameConsoleSession(session, observation)
    }
}

func retainLockedUseAccess(enabled: Bool, paused: Bool, phase: String,
                           interruption: String?, endReason: String?, pauseReason: String? = nil) -> Bool {
    guard enabled else { return false }
    let resumable = ["physical_presence", "local_use_episode", "operator_paused", "paused", "cancelled", "client_disconnected", "operator_quit", "resident_stopping"]
    if paused && !resumable.contains(pauseReason ?? endReason ?? interruption ?? "") { return false }
    if phase == "relocking" {
        return ["completed", "duration_expired"].contains(endReason ?? "") || resumable.contains(endReason ?? "")
    }
    return interruption == nil || resumable.contains(interruption ?? "")
}

/// Expected endings still relock, but need no fault acknowledgement in root.
func cleanCoveredEnding(_ reason: String) -> Bool {
    ["completed", "duration_expired", "operator_paused", "paused", "cancelled", "client_disconnected", "operator_quit", "resident_stopping"].contains(reason)
}

/// Only the healthy resident's admission callback may make this distinction.
/// Guardian EOF and missing resident heartbeats remain owner-disconnection faults.
func coveredAdmissionEnding(_ reason: String) -> String {
    switch reason {
    case "owner_disconnected": return "client_disconnected"
    case "paused": return "operator_paused"
    default: return reason
    }
}

/// Private, measured OS lock primitive; success is always checked via IOKit.
enum ConsoleRelock {
    private static let library = dlopen("/System/Library/PrivateFrameworks/login.framework/login", RTLD_NOW)
    private static let symbol = library.flatMap { dlsym($0, "SACLockScreenImmediate") }
    static var available: Bool { symbol != nil }
    static func request(for session: [String:Any]? = nil) {
        if let session, !sameConsoleSession(session, nativeSessionObservation()) { return }
        if let symbol { unsafeBitCast(symbol, to: (@convention(c) () -> Void).self)() }
    }
}

/// Shared between the event-tap thread and native provider dispatch. Physical
/// input cannot wait behind a long AX call on the resident's main thread.
final class LockedUseSafety {
    private let lock = NSLock()
    private var armed = false
    private var interrupted: String?

    var reason: String? { lock.lock(); defer { lock.unlock() }; return interrupted }
    var blocksPhysicalInput: Bool { lock.lock(); defer { lock.unlock() }; return armed }
    func arm() { lock.lock(); armed = true; interrupted = nil; lock.unlock() }
    func disarm() { lock.lock(); armed = false; interrupted = nil; lock.unlock() }
    @discardableResult
    func interrupt(_ reason: String) -> Bool {
        lock.lock(); defer { lock.unlock() }
        guard armed, interrupted == nil else { return false }
        interrupted = reason
        return true
    }
    static func physical(sourcePID: Int64) -> Bool { sourcePID <= 0 }
}

private func lockedUseEventTap(_ proxy: CGEventTapProxy, _ type: CGEventType,
                               _ event: CGEvent, _ context: UnsafeMutableRawPointer?) -> Unmanaged<CGEvent>? {
    guard let context else { return Unmanaged.passUnretained(event) }
    let guardObject = Unmanaged<PhysicalInputGuard>.fromOpaque(context).takeUnretainedValue()
    if type == .tapDisabledByTimeout || type == .tapDisabledByUserInput {
        guardObject.interrupt("input_guard_unavailable")
        return Unmanaged.passUnretained(event)
    }
    if LockedUseSafety.physical(sourcePID: event.getIntegerValueField(.eventSourceUnixProcessID)) { guardObject.activity?() }
    if guardObject.safety.blocksPhysicalInput,
       LockedUseSafety.physical(sourcePID: event.getIntegerValueField(.eventSourceUnixProcessID)) {
        guardObject.interrupt("physical_presence")
        // Swallow the entire physical sequence until the OS lock is observed.
        // Our synthesized events carry a nonzero source process ID.
        return nil
    }
    return Unmanaged.passUnretained(event)
}

final class PhysicalInputGuard {
    let safety: LockedUseSafety
    var activity: (() -> Void)?
    var session: [String:Any]?
    private var thread: Thread?
    private var runLoop: CFRunLoop?
    private var tap: CFMachPort?
    private let stateLock = NSLock()

    init(safety: LockedUseSafety) { self.safety = safety }
    func interrupt(_ reason: String) {
        if safety.interrupt(reason) {
            // Never run an OS probe on the event-tap callback: a blocked
            // callback can cause macOS to disable the tap and release input.
            DispatchQueue.global(qos:.userInteractive).async { [self] in
                ConsoleRelock.request(for:session)
            }
        }
    }
    func start() throws {
        let ready = DispatchSemaphore(value: 0)
        let worker = Thread { [self] in
            let types: [CGEventType] = [.keyDown, .keyUp, .flagsChanged, .mouseMoved,
                .leftMouseDown, .leftMouseUp, .rightMouseDown, .rightMouseUp,
                .otherMouseDown, .otherMouseUp, .leftMouseDragged, .rightMouseDragged,
                .otherMouseDragged, .scrollWheel]
            let mask = types.reduce(CGEventMask(0)) { $0 | (CGEventMask(1) << $1.rawValue) }
            let port = CGEvent.tapCreate(tap: .cghidEventTap, place: .headInsertEventTap,
                options: .defaultTap, eventsOfInterest: mask, callback: lockedUseEventTap,
                userInfo: Unmanaged.passUnretained(self).toOpaque())
            stateLock.lock(); tap = port; runLoop = CFRunLoopGetCurrent(); stateLock.unlock()
            guard let port, let source = CFMachPortCreateRunLoopSource(nil, port, 0) else {
                ready.signal(); return
            }
            CFRunLoopAddSource(CFRunLoopGetCurrent(), source, .commonModes)
            CGEvent.tapEnable(tap: port, enable: true)
            ready.signal()
            CFRunLoopRun()
            CGEvent.tapEnable(tap: port, enable: false)
            CFMachPortInvalidate(port)
            stateLock.lock(); tap = nil; runLoop = nil; stateLock.unlock()
        }
        worker.name = "Machine Control physical-presence guard"
        thread = worker; worker.start()
        guard ready.wait(timeout: .now() + 2) == .success, healthy else {
            stop(); throw MacUIError.permission("locked_use_input_guard_unavailable")
        }
    }
    var healthy: Bool {
        stateLock.lock(); defer { stateLock.unlock() }
        return tap.map { CGEvent.tapIsEnabled(tap: $0) } ?? false
    }
    func stop() {
        stateLock.lock(); let loop = runLoop; stateLock.unlock()
        if let loop { CFRunLoopStop(loop); CFRunLoopWakeUp(loop) }
        thread = nil
    }
}

private final class LockedUseCover: NSPanel {
    override var canBecomeKey: Bool { false }
    override var canBecomeMain: Bool { false }
}

final class DisplayCovers {
    private(set) var windows: [NSWindow] = []
    private var screens: [String] = []
    var windowIDs: Set<Int> { Set(windows.map(\.windowNumber)) }
    static var currentLayout: [String] {
        NSScreen.screens.map { "\($0.deviceDescription[NSDeviceDescriptionKey("NSScreenNumber")] ?? "unknown"):\($0.frame):\($0.backingScaleFactor)" }.sorted()
    }
    var healthy: Bool {
        !windows.isEmpty && screens == Self.currentLayout && windows.allSatisfy { $0.isVisible && $0.isOpaque }
    }
    func install() throws {
        guard windows.isEmpty, !NSScreen.screens.isEmpty else {
            throw MacUIError.action("locked_use_display_unavailable")
        }
        screens = Self.currentLayout
        for screen in NSScreen.screens {
            let panel = LockedUseCover(contentRect: screen.frame,
                styleMask: [.borderless, .nonactivatingPanel], backing: .buffered, defer: false)
            panel.title = "Machine Control locked use"
            panel.level = NSWindow.Level(rawValue: NSWindow.Level.screenSaver.rawValue + 1)
            panel.collectionBehavior = [.canJoinAllSpaces, .fullScreenAuxiliary, .stationary, .ignoresCycle]
            panel.hidesOnDeactivate = false; panel.isOpaque = true; panel.hasShadow = false
            panel.backgroundColor = NSColor(calibratedWhite: 0.08, alpha: 1)
            panel.ignoresMouseEvents = true; panel.isReleasedWhenClosed = false
            let stack = NSStackView()
            stack.orientation = .vertical; stack.spacing = 14
            let title = NSTextField(labelWithString: "Machine Control is working")
            title.font = .systemFont(ofSize: 25, weight: .semibold); title.textColor = .white
            let hint = NSTextField(labelWithString: "Press any key or move the pointer to take over.")
            hint.font = .systemFont(ofSize: 15); hint.textColor = NSColor(calibratedWhite: 0.8, alpha: 1)
            stack.addArrangedSubview(title); stack.addArrangedSubview(hint)
            stack.translatesAutoresizingMaskIntoConstraints = false
            panel.contentView!.addSubview(stack)
            NSLayoutConstraint.activate([
                stack.centerXAnchor.constraint(equalTo: panel.contentView!.centerXAnchor),
                stack.centerYAnchor.constraint(equalTo: panel.contentView!.centerYAnchor),
            ])
            windows.append(panel)
            panel.orderFrontRegardless(); panel.display()
        }
        guard healthy else { throw MacUIError.action("locked_use_cover_unavailable") }
    }
    /// Only call after independently observed lock, or when unlock was never armed.
    func removeAfterLock() {
        for window in windows { window.orderOut(nil); window.close() }
        windows.removeAll(); screens.removeAll()
    }
}

/// ScreenCaptureKit is required for covered full-display capture. Excluding
/// the resident application hides every cover without dropping other apps.
@available(macOS 14.0, *)
func captureCoveredDisplay(to url: URL, displayID: CGDirectDisplayID) throws {
    let complete = DispatchSemaphore(value: 0)
    let resultLock = NSLock()
    var result: Result<CGImage, Error>?
    func finish(_ value: Result<CGImage, Error>) {
        resultLock.lock(); result = value; resultLock.unlock(); complete.signal()
    }
    SCShareableContent.getExcludingDesktopWindows(false, onScreenWindowsOnly: false) { content, error in
        guard let content, let display = content.displays.first(where: { $0.displayID == displayID }) else {
            finish(.failure(error ?? MacUIError.action("covered_capture_display_unavailable"))); return
        }
        let excluded = content.applications.filter { $0.processID == getpid() || $0.bundleIdentifier == Bundle.main.bundleIdentifier }
        guard !excluded.isEmpty else {
            finish(.failure(MacUIError.action("covered_capture_filter_unavailable"))); return
        }
        let filter = SCContentFilter(display: display, excludingApplications: excluded, exceptingWindows: [])
        let configuration = SCStreamConfiguration()
        configuration.width = CGDisplayPixelsWide(display.displayID)
        configuration.height = CGDisplayPixelsHigh(display.displayID)
        configuration.showsCursor = true
        SCScreenshotManager.captureImage(contentFilter: filter, configuration: configuration) { image, error in
            if let image { finish(.success(image)) }
            else { finish(.failure(error ?? MacUIError.action("covered_capture_failed"))) }
        }
    }
    guard complete.wait(timeout: .now() + 3) == .success else {
        throw MacUIError.action("covered_capture_timeout")
    }
    resultLock.lock(); let value = result; resultLock.unlock()
    let image = try value!.get()
    guard let png = NSBitmapImageRep(cgImage: image).representation(using: .png, properties: [:]) else {
        throw MacUIError.action("covered_capture_encoding_failed")
    }
    try png.write(to: url, options: .atomic)
}

/// Serial main-thread coordinator. The input latch and root watchdog remain
/// effective when this thread stalls or the process dies.
final class MacLockedUse {
    let broker: GrantBroker
    let service: ResidentService
    private let safetyLock = NSLock()
    private var currentSafety = LockedUseSafety()
    var safety: LockedUseSafety {
        safetyLock.lock(); defer { safetyLock.unlock() }
        return currentSafety
    }
    /// A previous guardian must never interrupt a later lease. The input
    /// thread reads the current latch through the same synchronized source.
    func prepareSessionSafety() {
        safetyLock.lock(); defer { safetyLock.unlock() }
        currentSafety = LockedUseSafety()
    }
    private var guardian: CoveredGuardianClient?
    private var hiddenOperatorWindows: [NSWindow] = []
    private var coveredScreenLayout: [String] = []
    var coveredWindowIDs: Set<Int> { guardian?.windowIDs ?? [] }
    private(set) var lease: ControlSessionLease?
    private var owner: Int32 = -1
    private var ownerBuffer = Data()
    private var ownerRequest: [String: Any] = [:]
    private var lastHelperHeartbeat: TimeInterval = 0
    private(set) var endReason: String?
    private(set) var phase = "off"
    private var relockFallbackDeadline: TimeInterval = 0
    private var shouldForceRelock: Bool {
        guardian == nil || !cleanCoveredEnding(endReason ?? "") ||
            ProcessInfo.processInfo.systemUptime >= relockFallbackDeadline
    }
    private let preferences: UserDefaults
    let permission: LockedUsePermissionManaging
    private let setupObservation: () -> [String:Any]
    var locallyDisabled: Bool {
        get { preferences.object(forKey:"lockedUseLocallyDisabled") == nil || preferences.bool(forKey:"lockedUseLocallyDisabled") }
        set { preferences.set(newValue, forKey:"lockedUseLocallyDisabled") }
    }
    var setupState: String { permission.setupState }
    var setupError: String? { permission.setupError }

    /// A preference only: never requests macOS consent, installs a helper,
    /// launches a subprocess, or performs capture preparation.
    func configure(enabled: Bool) throws {
        if !enabled { locallyDisabled = true; end("disabled"); return }
        guard !isCovered, lease == nil, broker.pending == nil,
              broker.policy.grantMode == .approval,
              setupObservation()["desktopState"] as? String == "unlocked" else {
            throw MacUIError.action("Finish active control and unlock before changing locked use")
        }
        guard permission.ready, setupState == "idle" else {
            throw MacUIError.permission("Finish setup in Permissions before enabling locked use")
        }
        locallyDisabled = false
    }

    func preparePermission() throws {
        guard !isCovered, lease == nil, broker.pending == nil,
              broker.policy.grantMode == .approval,
              setupObservation()["desktopState"] as? String == "unlocked" else {
            throw MacUIError.action("Finish active control and unlock before changing permissions")
        }
        try permission.request()
    }

    func removePermission() throws {
        guard !isCovered, lease == nil, broker.pending == nil,
              broker.policy.grantMode == .approval,
              setupObservation()["desktopState"] as? String == "unlocked" else {
            throw MacUIError.action("Finish active control and unlock before removing permissions")
        }
        locallyDisabled = true
        try permission.remove()
    }

    init(broker: GrantBroker, service: ResidentService, preferences: UserDefaults = .standard,
         permission: LockedUsePermissionManaging? = nil,
         setupObservation: @escaping () -> [String:Any] = { nativeSessionObservation() }) {
        self.broker = broker; self.service = service; self.preferences = preferences
        self.permission = permission ?? MacLockedUsePermission(service:service, preferences:preferences)
        self.setupObservation = setupObservation
        service.coveredWindowIDs = { [weak self] in self?.coveredWindowIDs ?? [] }
        service.inputCancellation = { [weak self] in self?.safety.reason }
        NSWorkspace.shared.notificationCenter.addObserver(forName: NSWorkspace.willSleepNotification,
            object: nil, queue: .main) { [weak self] _ in self?.end("system_sleep") }
        NSWorkspace.shared.notificationCenter.addObserver(forName:NSWorkspace.screensDidSleepNotification,
            object:nil, queue:.main) { [weak self] _ in self?.end("display_sleep") }
        NotificationCenter.default.addObserver(forName: NSApplication.didChangeScreenParametersNotification,
            object: nil, queue: .main) { [weak self] _ in
                guard let self, self.isCovered,
                      self.coveredScreenLayout != DisplayCovers.currentLayout else { return }
                self.end("display_changed")
            }
    }
    var isCovered: Bool { guardian != nil }
    var enabled: Bool {
        guard !locallyDisabled, permission.ready else { return false }
        let value = service.unlockStatus()
        return value["profile"] as? String == "locked_use" && value["policy"] as? String == "enabled"
    }
    var status: [String: Any] {
        let helper = service.unlockStatus()
        let approval = permission.approvalState
        let ready = permission.ready(helper:helper, approval:approval)
        let enabled = !locallyDisabled && ready && helper["profile"] as? String == "locked_use" && helper["policy"] as? String == "enabled"
        let available: Bool
        if #available(macOS 14.0, *) { available = ConsoleRelock.available } else { available = false }
        return ["supported":available, "enabled":enabled,
            "phase": lease == nil && !isCovered ? (helper["lockedUsePaused"] as? Bool == true ? "paused" : enabled ? "ready" : "off") : phase,
            "permissionReady":ready, "helperApproval":approval,
            "setupState":setupState, "setupError":setupError.map { $0 as Any } ?? NSNull(),
            "helperHealthy":helper["installation"] as? String == "healthy" && helper["callerEligibility"] as? String == "allowed",
            "pauseReason":helper["lockedUsePauseReason"] ?? NSNull(),
            "pausedUntilManualUnlock":helper["lockedUsePaused"] as? Bool == true &&
                !["physical_presence", "local_use_episode"].contains(helper["lockedUsePauseReason"] as? String ?? ""),
            "controlSessionId":lease.map { $0.id as Any } ?? NSNull(),
            "remainingSeconds":lease.map { max(0, Int($0.deadline - ProcessInfo.processInfo.systemUptime)) as Any } ?? NSNull(),
            "coveredDisplays":coveredWindowIDs.count, "closedLidSupported":false,
            "provider":"macos-native", "activeSessionRequired":true,
            "binding":"approved_target_wide_access_and_live_owner_connection",
            "lastEndedReason":endReason.map { $0 as Any } ?? NSNull()]
    }

    func begin(_ request: [String: Any], owner: Int32) throws -> [String: Any] {
        guard #available(macOS 14.0, *), ConsoleRelock.available else {
            throw MacUIError.action("locked_use_unsupported")
        }
        guard enabled, !locallyDisabled, setupState == "idle" else { throw MacUIError.action("locked_use_disabled") }
        guard lease == nil, !isCovered else { throw MacUIError.action("control_session_busy") }
        guard broker.policy.grantMode == .approval, broker.pending == nil,
              let grant = broker.activeGrant, [.observe, .control].allSatisfy(grant.scopes.contains) else {
            throw MacUIError.permission("approval_required")
        }
        let helper = service.unlockStatus()
        guard helper["installation"] as? String == "healthy", helper["callerEligibility"] as? String == "allowed",
              helper["relockAvailable"] as? Bool == true else { throw MacUIError.action("locked_use_helper_unavailable") }
        guard helper["lockedUsePaused"] as? Bool != true else { throw MacUIError.action("locked_use_paused") }
        let keys: Set<String> = ["schema", "operation", "requestId", "claimId", "durationSeconds"]
        guard Set(request.keys).isSubset(of: keys), let duration = ControlSessionLease.duration(request["durationSeconds"]) else {
            throw MacUIError.usage("control_session_invalid_request")
        }
        service.refreshSession()
        let session = nativeSessionObservation()
        guard ["unlocked", "locked"].contains(session["desktopState"] as? String ?? ""),
              (session["uid"] as? NSNumber)?.uint32Value == getuid(),
              !macLidClosed(), CGPreflightScreenCaptureAccess(), AXIsProcessTrusted(), CGPreflightPostEventAccess() else {
            throw MacUIError.permission("locked_use_prerequisites_unavailable")
        }
        let now = ProcessInfo.processInfo.systemUptime
        let remaining = grant.expiresAt.map { max(0, $0.timeIntervalSince(broker.now())) } ?? Double(duration)
        guard remaining > 1 else { throw MacUIError.permission("approval_expired") }
        // Until-stopped access is still capped by a finite active-control lease.
        lease = ControlSessionLease(id: UUID().uuidString.lowercased(), grantID: grant.id,
            session: session, deadline: now + min(Double(duration), remaining), heartbeatDeadline: now + 5)
        prepareSessionSafety()
        self.owner = owner; ownerRequest = request; endReason = nil; phase = "waiting_for_lock"
        return service.acceptance(request, data: status)
    }

    /// Poll bounded nonblocking protocol lines; never block the event loop
    /// while a controller is missing or sends a partial heartbeat.
    private func receive(_ fd: Int32, buffer: inout Data) throws -> [[String: Any]] {
        var poller = pollfd(fd: fd, events: Int16(POLLIN | POLLHUP), revents: 0)
        guard poll(&poller, 1, 0) > 0 else { return [] }
        var bytes = [UInt8](repeating: 0, count: 4096)
        let count = recv(fd, &bytes, bytes.count, MSG_DONTWAIT)
        guard count > 0 else { throw MacUIError.action("owner_disconnected") }
        buffer.append(bytes, count: count)
        guard buffer.count <= 4096 else { throw MacUIError.usage("invalid_heartbeat") }
        var messages: [[String: Any]] = []
        while let newline = buffer.firstIndex(of: 0x0a) {
            let line = Data(buffer[..<newline]); buffer.removeSubrange(...newline)
            guard let message = try JSONSerialization.jsonObject(with: line) as? [String: Any] else {
                throw MacUIError.usage("invalid_heartbeat")
            }
            messages.append(message)
        }
        return messages
    }

    func tick() {
        permission.tick()
        guard var current = lease else { return }
        let now = ProcessInfo.processInfo.systemUptime
        if phase == "relocking" {
            let observation = nativeSessionObservation()
            if observation["desktopState"] as? String == "locked" || consoleSessionReplaced(current.session, observation) { finishAfterLock() }
            else if shouldForceRelock { ConsoleRelock.request(for:current.session) }
            return
        }
        do {
            for message in try receive(owner, buffer: &ownerBuffer) {
                guard message.count == 1, message["operation"] as? String == "heartbeat" else {
                    end("owner_disconnected"); return
                }
                current.heartbeatDeadline = now + 5
            }
            lease = current
        } catch { end("owner_disconnected"); return }
        let observation = nativeSessionObservation()
        if let reason = safety.reason { end(reason); return }
        if let reason = current.refusal(now: now, grantID: broker.activeGrant?.id, session: observation) {
            end(reason); return
        }
        if !enabled { end("disabled"); return }
        let screen = observation["desktopState"] as? String ?? "unknown"
        if phase == "waiting_for_lock" {
            if screen == "locked" { activate() }
            else if screen != "unlocked" { end("session_state_unknown") }
            return
        }
        if phase == "active" {
            guard screen == "unlocked", guardian?.healthy == true, !macLidClosed() else {
                end(screen == "locked" ? "desktop_locked" : safety.reason ?? "safety_guard_unavailable"); return
            }
            if now - lastHelperHeartbeat >= 1 {
                do { try guardian?.heartbeat(); lastHelperHeartbeat = now }
                catch { end("guardian_disconnected") }
            }
        }
    }

    private func activate() {
        guard let lease else { return }
        phase = "unlocking"; safety.arm()
        do {
            // Preserve self-interface protection without leaving invisible
            // operator rectangles over the application's pointer targets.
            hiddenOperatorWindows = NSApp.windows.filter(\.isVisible)
            hiddenOperatorWindows.forEach { $0.orderOut(nil) }
            coveredScreenLayout = DisplayCovers.currentLayout
            let child = CoveredGuardianClient(safety:safety)
            guardian = child
            let remaining = Int(lease.deadline - ProcessInfo.processInfo.systemUptime)
            guard remaining >= 1 else { throw MacUIError.action("duration_expired") }
            try child.start(duration:remaining, deadline:lease.deadline)
            guard safety.reason == nil, child.healthy else { throw MacUIError.action("safety_guard_unavailable") }
            phase = "active"; lastHelperHeartbeat = 0
        } catch {
            end(safety.reason ?? String(describing:error))
        }
    }

    func end(_ reason: String) {
        guard lease != nil else { return }
        guard phase != "relocking" else {
            // A dead owner cannot prevent the lock-readback cleanup path.
            if nativeSessionObservation()["desktopState"] as? String == "locked" { finishAfterLock() }
            else if shouldForceRelock { ConsoleRelock.request(for:lease?.session) }
            return
        }
        endReason = reason
        if isCovered {
            phase = "relocking"
            relockFallbackDeadline = ProcessInfo.processInfo.systemUptime + 5
            _ = safety.interrupt(reason)
            guardian?.stop(reason:reason)
            // For a clean end, let the guardian deliver completion to the
            // watchdog before locking. Racing it would persist a false pause.
            // Its independent heartbeat/deadline guards still bound failure.
            if shouldForceRelock { ConsoleRelock.request(for:lease?.session) }
        } else { finishAfterLock() }
        if reason == "physical_presence" {
            try? broker.pause(reason: "physical_activity", seconds: 30)
        }
        if !cleanCoveredEnding(reason) && reason != "physical_presence" {
            broker.revoke(reason: reason == "physical_presence" ? "interrupted_by_physical_presence" : reason)
            service.invalidateReferences()
        }
    }

    private func finishAfterLock() {
        guardian?.closeAfterLock(); guardian = nil; safety.disarm()
        hiddenOperatorWindows.forEach { $0.orderFront(nil) }
        hiddenOperatorWindows.removeAll()
        coveredScreenLayout.removeAll()
        if owner >= 0 {
            var response = service.acceptance(ownerRequest, data: ["ended":true, "reason":endReason ?? "completed",
                "lockObserved":nativeSessionObservation()["desktopState"] as? String == "locked"])
            if endReason == "physical_presence" {
                response = service.refusal(ownerRequest, code:"interrupted_by_physical_presence",
                    message:"Physical input paused control; inspect availability before starting a fresh session")
            }
            try? writeSocket(owner, data: encodeJSONLine(response)); Darwin.close(owner)
        }
        owner = -1; lease = nil; ownerBuffer.removeAll(); phase = "ready"
        service.invalidateReferences()
    }

    var preservesGrantAcrossLock: Bool {
        // A prepared opt-in also covers idle locks and clean task completion.
        // Unlock authority still requires a separate finite connection lease.
        let helper = service.unlockStatus()
        return retainLockedUseAccess(enabled:enabled,
            paused:helper["lockedUsePaused"] as? Bool ?? true,
            phase:phase, interruption:safety.reason, endReason:endReason,
            pauseReason:helper["lockedUsePauseReason"] as? String)
    }
    func refusal(_ request: [String: Any]) -> GrantRefusal? {
        guard lease != nil else { return nil }
        if let reason = safety.reason {
            return GrantRefusal(reason == "physical_presence" ? "interrupted_by_physical_presence" : "locked_use_interrupted",
                "Covered control has been interrupted; unlock manually before continuing")
        }
        if ["unlocking", "relocking"].contains(phase) {
            return GrantRefusal("locked_use_transition", "Wait for covered-session state to settle")
        }
        if isCovered, request["provider"] as? String == "cua" {
            return GrantRefusal("provider_unsupported", "Covered control currently requires macos-native")
        }
        return nil
    }
}
