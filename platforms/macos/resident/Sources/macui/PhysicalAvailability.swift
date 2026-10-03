import ApplicationServices
import Foundation
import IOKit

/// Pass-through monitor using the existing HID event permission. It never
/// suppresses input or prompts for a new permission. Covered control retains
/// its separate independent guard and root watchdog.
final class PhysicalAvailability {
    private var guardTap = PhysicalInputGuard(safety: LockedUseSafety())
    private let lock = NSLock()
    private var lastPhysical: Double?
    private var activeBaseline: Double?
    private var active = false
    private var retryAt = 0.0
    var now: () -> Double = { ProcessInfo.processInfo.systemUptime }
    var idleObservation: () -> Double? = PhysicalAvailability.hidIdle
    private(set) var enabled = false
    var respectRecentActivity = true
    private var publishedActivity: Double?
    private var publishedReason: String?

    static func hidIdle() -> Double? {
        let service = IOServiceGetMatchingService(kIOMainPortDefault, IOServiceMatching("IOHIDSystem"))
        guard service != 0 else { return nil }
        defer { IOObjectRelease(service) }
        guard let value = IORegistryEntryCreateCFProperty(service, "HIDIdleTime" as CFString, kCFAllocatorDefault, 0)?.takeRetainedValue() as? NSNumber else { return nil }
        let seconds = value.doubleValue / 1e9
        return seconds.isFinite && seconds >= 0 ? seconds : nil
    }
    init() {
        guardTap.activity = { [weak self] in self?.recordPhysical() }
    }
    func recordPhysical() {
        lock.lock(); lastPhysical = now(); lock.unlock()
    }
    func arm(baseline: Double?) { lock.lock(); activeBaseline = baseline; active = true; lock.unlock() }
    /// Explicit Start now acknowledges only the observed activity episode.
    /// A later hardware event immediately interrupts again; unknown cannot clear.
    func acknowledgeCurrentActivity() {
        guard healthy else { return }
        lock.lock(); lastPhysical = now() - 30; lock.unlock()
    }
    func disarm() { lock.lock(); active = false; activeBaseline = nil; lock.unlock() }
    var interruption: String? {
        guard enabled else { return nil }
        lock.lock(); defer { lock.unlock() }
        guard active else { return nil }
        guard let baseline = activeBaseline, let lastPhysical else { return "activity_unknown" }
        return lastPhysical > baseline ? "physical_presence" : nil
    }
    func enable() { enabled = true }
    func stop() { enabled = false; guardTap.stop() }
    deinit { guardTap.stop() }
    var physicalAt: Double? { lock.lock(); defer { lock.unlock() }; return lastPhysical }
    var healthy: Bool { guardTap.healthy }
    static func reason(healthy: Bool, physicalAt: Double?, now: Double) -> String? {
        guard healthy, let physicalAt, physicalAt.isFinite, now.isFinite, now >= physicalAt else { return "activity_unknown" }
        return now < physicalAt + 30 ? "physical_activity" : nil
    }
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
        let activity = physicalAt
        var reason = Self.reason(healthy:healthy, physicalAt:activity, now:time)
        if !respectRecentActivity && reason == "physical_activity" && interruption == nil { reason = nil }
        if publishedReason != reason || (reason == "physical_activity" && publishedActivity != activity) {
            if let reason { try? broker.admission.pause("desktop", reason:reason,
                seconds:reason == "physical_activity" ? max(0.001, (activity ?? time) + 30 - time) : nil) }
            if publishedReason != reason, let old = publishedReason { broker.admission.resume("desktop", reason:old) }
            publishedReason = reason; publishedActivity = activity
        }
        let rootReason = helper["lockedUsePauseReason"] as? String ?? ""
        let reasons = broker.admission.blocks("desktop")
        let local = rootReason == "local_use_episode"
        if local && !reasons.contains("local_use_episode") {
            try? broker.admission.pause("desktop", reason:"local_use_episode")
        } else if !local && reasons.contains("local_use_episode") {
            broker.admission.resume("desktop", reason:"local_use_episode")
        }
        let physical = rootReason == "physical_presence"
        if physical && !reasons.contains("covered_takeover") {
            try? broker.admission.pause("desktop", reason:"covered_takeover")
        } else if !physical && reasons.contains("covered_takeover") {
            broker.admission.resume("desktop", reason:"covered_takeover")
        }
    }
    var status: [String:Any] {
        ["supported":true, "enabled":enabled, "healthy":healthy,
         "quietSeconds":30, "physicalClassification":"hid_event_source_pid",
         "unknownBlocksAdmission":true]
    }
}
