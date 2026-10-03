import Foundation

/// Metadata-only mailbox on the resident's serial queue. The Tauri process
/// supplies results; callers can only queue discovery, never install or approve.
final class DesktopUpdates {
    private var state: [String: Any]?
    private var requested = false

    func sync(_ snapshot: [String: Any]) -> Bool {
        state = snapshot
        let queued = requested
        requested = false
        if queued, snapshot["installing"] as? Bool != true {
            // Keep completion polling busy until the next authoritative result.
            state?["checking"] = true
            state?["phase"] = "checking"
            state?["reason"] = "manual"
        }
        return queued
    }

    func request(check: Bool) -> [String: Any]? {
        guard let state else { return nil }
        if check, state["checking"] as? Bool != true,
           state["installing"] as? Bool != true { requested = true }
        return ["queued": requested, "update": state]
    }
}
