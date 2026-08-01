import AppKit
import CoreGraphics
import Foundation

struct UTMWindow: Codable {
    let id: Int
    let pid: Int32
    let x: Double
    let y: Double
    let width: Double
    let height: Double
}

enum ControlError: Error, CustomStringConvertible {
    case message(String)
    var description: String {
        switch self { case let .message(value): return value }
    }
}

func fail(_ error: Error) -> Never {
    fputs("\(error)\n", stderr)
    exit(1)
}

func number(_ dictionary: [String: Any], _ key: String) -> Double? {
    (dictionary[key] as? NSNumber)?.doubleValue
}

func findWindow(named vmName: String) throws -> UTMWindow {
    let options: CGWindowListOption = [.optionOnScreenOnly, .excludeDesktopElements]
    guard let windows = CGWindowListCopyWindowInfo(options, kCGNullWindowID)
            as? [[String: Any]] else {
        throw ControlError.message("Unable to query the macOS window list")
    }
    let candidates = windows.compactMap { window -> UTMWindow? in
        guard let owner = window[kCGWindowOwnerName as String] as? String,
              owner == "UTM",
              let name = window[kCGWindowName as String] as? String,
              name == vmName,
              let layer = (window[kCGWindowLayer as String] as? NSNumber)?.intValue,
              layer == 0,
              let id = (window[kCGWindowNumber as String] as? NSNumber)?.intValue,
              let pid = (window[kCGWindowOwnerPID as String] as? NSNumber)?.int32Value,
              let bounds = window[kCGWindowBounds as String] as? [String: Any],
              let x = number(bounds, "X"), let y = number(bounds, "Y"),
              let width = number(bounds, "Width"),
              let height = number(bounds, "Height") else { return nil }
        return UTMWindow(id: id, pid: pid, x: x, y: y,
                         width: width, height: height)
    }
    guard let selected = candidates.max(by: {
        $0.width * $0.height < $1.width * $1.height
    }) else {
        throw ControlError.message("No visible UTM window named '\(vmName)' was found")
    }
    return selected
}

func activate(_ window: UTMWindow) {
    NSRunningApplication(processIdentifier: window.pid)?.activate(options: [.activateAllWindows])
    usleep(200_000)
}

func point(window: UTMWindow, displayWidth: Double, displayHeight: Double,
           x: Double, y: Double) throws -> CGPoint {
    guard x >= 0, x < displayWidth, y >= 0, y < displayHeight else {
        throw ControlError.message("Coordinate is outside the configured guest display")
    }
    let titleHeight = max(0, window.height - displayHeight)
    let contentHeight = window.height - titleHeight
    return CGPoint(x: window.x + x * window.width / displayWidth,
                   y: window.y + titleHeight + y * contentHeight / displayHeight)
}

func postMouse(_ type: CGEventType, _ point: CGPoint, _ button: CGMouseButton) {
    CGEvent(mouseEventSource: nil, mouseType: type,
            mouseCursorPosition: point, mouseButton: button)?.post(tap: .cghidEventTap)
}

func click(window: UTMWindow, width: Double, height: Double,
           x: Double, y: Double, buttonName: String) throws {
    let target = try point(window: window, displayWidth: width,
                           displayHeight: height, x: x, y: y)
    let button: CGMouseButton
    let down: CGEventType
    let up: CGEventType
    switch buttonName {
    case "left": button = .left; down = .leftMouseDown; up = .leftMouseUp
    case "right": button = .right; down = .rightMouseDown; up = .rightMouseUp
    case "middle": button = .center; down = .otherMouseDown; up = .otherMouseUp
    default: throw ControlError.message("Unknown mouse button: \(buttonName)")
    }
    activate(window)
    CGWarpMouseCursorPosition(target)
    usleep(75_000)
    postMouse(down, target, button)
    usleep(75_000)
    postMouse(up, target, button)
}

func drag(window: UTMWindow, width: Double, height: Double,
          x1: Double, y1: Double, x2: Double, y2: Double) throws {
    let start = try point(window: window, displayWidth: width,
                          displayHeight: height, x: x1, y: y1)
    let end = try point(window: window, displayWidth: width,
                        displayHeight: height, x: x2, y: y2)
    activate(window)
    CGWarpMouseCursorPosition(start)
    usleep(100_000)
    postMouse(.leftMouseDown, start, .left)
    for step in 1...20 {
        let fraction = Double(step) / 20.0
        let current = CGPoint(x: start.x + (end.x - start.x) * fraction,
                              y: start.y + (end.y - start.y) * fraction)
        postMouse(.leftMouseDragged, current, .left)
        usleep(25_000)
    }
    postMouse(.leftMouseUp, end, .left)
}

let args = Array(CommandLine.arguments.dropFirst())
guard let command = args.first else { fail(ControlError.message("Missing command")) }

do {
    switch command {
    case "permissions":
        let payload = ["screenCapture": CGPreflightScreenCaptureAccess(),
                       "postEvent": CGPreflightPostEventAccess()]
        let data = try JSONSerialization.data(withJSONObject: payload,
                                               options: [.sortedKeys])
        print(String(decoding: data, as: UTF8.self))
    case "window-info":
        guard args.count == 2 else { throw ControlError.message("Usage: window-info VM") }
        print(String(decoding: try JSONEncoder().encode(findWindow(named: args[1])),
                     as: UTF8.self))
    case "click":
        guard args.count == 7, let width = Double(args[2]),
              let height = Double(args[3]), let x = Double(args[4]),
              let y = Double(args[5]) else {
            throw ControlError.message("Usage: click VM WIDTH HEIGHT X Y BUTTON")
        }
        try click(window: findWindow(named: args[1]), width: width, height: height,
                  x: x, y: y, buttonName: args[6])
    case "drag":
        guard args.count == 8, let width = Double(args[2]),
              let height = Double(args[3]), let x1 = Double(args[4]),
              let y1 = Double(args[5]), let x2 = Double(args[6]),
              let y2 = Double(args[7]) else {
            throw ControlError.message("Usage: drag VM WIDTH HEIGHT X1 Y1 X2 Y2")
        }
        try drag(window: findWindow(named: args[1]), width: width, height: height,
                 x1: x1, y1: y1, x2: x2, y2: y2)
    default: throw ControlError.message("Unknown host-control command: \(command)")
    }
} catch { fail(error) }
