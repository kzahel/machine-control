import Foundation

/// Closed, secret-free predicates. Keep all failures when expiry and a health
/// fault coincide; the existing external reason retains its precedence.
struct GuardianDiagnostics: Codable {
    enum DesktopState: String, Codable { case locked, unlocked, unknown }
    enum ProbeFailure: String, Codable {
        case cancelled, stderr_unavailable, launch_failed, timeout, read_failed
        case output_limit, nonzero_exit, invalid_response
    }
    let sameConsole: Bool
    let desktopState: DesktopState
    let coversHealthy: Bool
    let inputGuardHealthy: Bool
    let lidClosed: Bool
    let parentAlive: Bool
    let startedUptime: Double
    let observedUptime: Double
    let deadlineUptime: Double
    let parentHeartbeatDeadline: Double
    let helperHeartbeatUptime: Double
    var sessionProbeFailure: ProbeFailure? = nil

    var failedChecks: [String] {
        var result: [String] = []
        if !sameConsole { result.append("console_identity_unavailable_or_changed") }
        if desktopState != .unlocked { result.append(desktopState == .unknown ? "session_observation_unknown" : "desktop_locked") }
        if !coversHealthy { result.append("covers_unhealthy") }
        if !inputGuardHealthy { result.append("input_guard_unhealthy") }
        if lidClosed { result.append("lid_closed") }
        if observedUptime >= deadlineUptime { result.append("duration_expired") }
        if observedUptime >= parentHeartbeatDeadline { result.append("owner_heartbeat_expired") }
        if !parentAlive { result.append("parent_gone") }
        return result
    }
    var refusal: String? {
        if !sameConsole || desktopState != .unlocked || !coversHealthy || !inputGuardHealthy || lidClosed {
            return "guardian_safety_unavailable"
        }
        if observedUptime >= deadlineUptime { return "duration_expired" }
        if observedUptime >= parentHeartbeatDeadline || !parentAlive { return "owner_disconnected" }
        return nil
    }
    var json: [String:Any] {
        var value = (try? JSONSerialization.jsonObject(with:JSONEncoder().encode(self))) as? [String:Any] ?? [:]
        value["component"] = "guardian"
        value["failedChecks"] = failedChecks
        value["remainingMs"] = Int((deadlineUptime - observedUptime) * 1000)
        value["elapsedMs"] = max(0, Int((observedUptime - startedUptime) * 1000))
        value["helperHeartbeatAgeMs"] = max(0, Int((observedUptime - helperHeartbeatUptime) * 1000))
        return value
    }
    static func decode(_ value: Any?) -> GuardianDiagnostics? {
        guard let value, JSONSerialization.isValidJSONObject(value),
              let data = try? JSONSerialization.data(withJSONObject:value),
              let result = try? JSONDecoder().decode(Self.self, from:data),
              [result.startedUptime, result.observedUptime, result.deadlineUptime,
               result.parentHeartbeatDeadline, result.helperHeartbeatUptime].allSatisfy({ $0.isFinite && $0 >= 0 && $0 < 1e10 }) else { return nil }
        return result
    }
}
