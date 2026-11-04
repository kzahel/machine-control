import ApplicationServices
import Foundation
import IOKit

/// Native physical facts only. Shared policy owns ordinary takeover/cooldown;
/// the protected helper retains its separate quiet/local-use safety ceiling.
final class PhysicalAvailability {
    private var guardTap = PhysicalInputGuard(safety: LockedUseSafety())
    private let lock = NSLock()
    private var lastPhysical: Double?
    private var activeBaseline: Double?
    private var acknowledgedThrough = -Double.infinity
    private var publishedThrough = -Double.infinity
    private var active = false
    private var published = Set<String>()
    private var retryAt = 0.0
    var now: () -> Double = { ProcessInfo.processInfo.systemUptime }
    var idleObservation: () -> Double? = PhysicalAvailability.hidIdle
    var lockedObservation: () -> Bool? = { nil }
    private(set) var enabled = false

    static func hidIdle() -> Double? {
        let service = IOServiceGetMatchingService(kIOMainPortDefault, IOServiceMatching("IOHIDSystem"))
        guard service != 0 else { return nil }; defer { IOObjectRelease(service) }
        guard let value = IORegistryEntryCreateCFProperty(service, "HIDIdleTime" as CFString, kCFAllocatorDefault, 0)?.takeRetainedValue() as? NSNumber else { return nil }
        let seconds = value.doubleValue / 1e9
        return seconds.isFinite && seconds >= 0 ? seconds : nil
    }
    init() { guardTap.activity = { [weak self] in self?.recordPhysical() } }
    func recordPhysical() { lock.lock(); lastPhysical = now(); lock.unlock() }
    func arm(baseline: Double?) { lock.lock(); activeBaseline = baseline; active = true; lock.unlock() }
    func acknowledgeCurrentActivity() {
        guard healthy else { return }
        lock.lock(); acknowledgedThrough = now(); activeBaseline = lastPhysical; lock.unlock()
    }
    func disarm() { lock.lock(); active = false; activeBaseline = nil; lock.unlock() }
    var interruption: String? {
        guard enabled else { return nil }
        lock.lock(); defer { lock.unlock() }
        guard active else { return nil }
        guard let baseline = activeBaseline, let lastPhysical else { return "activity_unknown" }
        return lastPhysical > baseline && lastPhysical > acknowledgedThrough ? "physical_presence" : nil
    }
    func enable() { enabled = true }
    func stop() { enabled = false; guardTap.stop() }
    deinit { guardTap.stop() }
    var physicalAt: Double? { lock.lock(); defer { lock.unlock() }; return lastPhysical }
    var healthy: Bool { guardTap.healthy }

    func tick(_ broker: GrantBroker, helper: [String: Any]) {
        guard enabled else { return }
        let time = now()
        if !healthy && time >= retryAt {
            guardTap.stop(); retryAt = time + 5
            guardTap = PhysicalInputGuard(safety: LockedUseSafety())
            guardTap.activity = { [weak self] in self?.recordPhysical() }
            if AXIsProcessTrusted(), CGPreflightPostEventAccess() {
                let idle = idleObservation()
                try? guardTap.start()
                if healthy, let idle {
                    lock.lock()
                    lastPhysical = max(lastPhysical ?? 0, time - min(idle, time))
                    lock.unlock()
                }
            }
        }
        lock.lock()
        let physical = lastPhysical, acknowledged = acknowledgedThrough
        let fresh = physical.map { $0 > publishedThrough && $0 > acknowledged } ?? false
        if let physical, fresh { publishedThrough = physical }
        lock.unlock()
        if fresh {
            broker.admission.input("desktop", kind:"key")
            broker.admission.input("browser", kind:"key")
        }
        let locked = lockedObservation()
        let idle = idleObservation()
        let checkQuiet = locked == true && !broker.admission.activeDesktop
        let known = healthy && locked != nil && physical.map { $0.isFinite && time >= $0 } == true
        broker.admission.setInputReady(known && (!checkQuiet || idle != nil))
        if checkQuiet && (idle == nil || idle! < 30) {
            publish("protected_quiet", true, broker)
        } else { publish("protected_quiet", false, broker) }
        // Only independently healthy helper state can clear these native
        // protected pauses. Clearing one never clears the shared cooldown.
        guard helper["installation"] as? String == "healthy" ||
              helper["installation"] as? String == "missing" else { return }
        let reason = helper["lockedUsePauseReason"] as? String ?? ""
        for (native, shared) in [("local_use_episode", "local_use_episode"), ("physical_presence", "covered_takeover")] {
            publish(shared, reason == native, broker)
        }
    }
    private func publish(_ reason: String, _ blocked: Bool, _ broker: GrantBroker) {
        if blocked && published.insert(reason).inserted { try? broker.admission.pause("desktop", reason:reason) }
        else if !blocked && published.remove(reason) != nil { broker.admission.resume("desktop", reason:reason) }
    }
    var status: [String: Any] {
        ["supported":true, "enabled":enabled, "healthy":healthy, "movementInterrupts":false,
         "deliberateInput":"key_down_button_down_scroll", "physicalClassification":"hid_event_source_pid",
         "protectedQuietSeconds":30, "ordinaryCooldownSeconds":60, "unknownBlocksAdmission":true]
    }
}
