import CoreGraphics
import Foundation

/// What the resident knows about its own user interface when it screens a
/// control request.
struct OwnInterface {
    var processID: pid_t
    var identifiers: Set<String>
    var windowFrames: [CGRect]
    var hasKeyWindow: Bool
    var menuOpen: Bool
    var pointer: CGPoint?
}

/// Refuses control aimed at the resident's own menu, prompt, or windows, so
/// an approved session cannot extend or approve its own access. This screens
/// Machine Control requests only; other programs with Accessibility
/// permission can still operate the interface.
func selfTargetRefusal(_ request: [String: Any], own: OwnInterface,
                       referencedProcess: pid_t?) -> GrantRefusal? {
    let operation = request["operation"] as? String ?? ""
    func refusal(_ message: String) -> GrantRefusal {
        GrantRefusal("self_target_refused", message, requiredScope: nil)
    }
    if own.menuOpen {
        return refusal("Control is paused while the Machine Control menu is open")
    }
    for key in ["target", "applicationId"] {
        if let value = request[key] as? String,
           own.identifiers.contains(value.lowercased()) || value == String(own.processID) {
            return refusal("Machine Control does not operate its own interface")
        }
    }
    if let referencedProcess, referencedProcess == own.processID {
        return refusal("Machine Control does not operate its own interface")
    }
    guard operation.hasPrefix("input.") else { return nil }
    if ["input.key", "input.text"].contains(operation), request["target"] == nil,
       own.hasKeyWindow {
        return refusal("Keyboard input would reach a Machine Control window")
    }
    var points: [CGPoint] = []
    for (xKey, yKey) in [("x", "y"), ("x2", "y2")] {
        if let x = (request[xKey] as? NSNumber)?.doubleValue,
           let y = (request[yKey] as? NSNumber)?.doubleValue {
            points.append(CGPoint(x: x, y: y))
        }
    }
    if points.isEmpty, ["input.scroll", "input.click"].contains(operation),
       let pointer = own.pointer {
        points.append(pointer)
    }
    if points.contains(where: { point in own.windowFrames.contains { $0.contains(point) } }) {
        return refusal("Pointer input would reach a Machine Control window")
    }
    return nil
}
