import AppKit
import CoreGraphics
import Foundation

struct TartWindow: Codable {
    let id: Int
    let pid: Int32
    let x: Double
    let y: Double
    let width: Double
    let height: Double
}

enum HostControlError: Error, CustomStringConvertible {
    case usage(String)
    case noWindow(String)
    case invalidCoordinate(String)
    case invalidKey(String)
    case invalidText(String)

    var description: String {
        switch self {
        case let .usage(message), let .noWindow(message),
             let .invalidCoordinate(message), let .invalidKey(message),
             let .invalidText(message):
            return message
        }
    }
}

func fail(_ error: Error) -> Never {
    fputs("\(error)\n", stderr)
    exit(1)
}

func number(_ dictionary: [String: Any], _ key: String) -> Double? {
    (dictionary[key] as? NSNumber)?.doubleValue
}

func findWindow(named vmName: String) throws -> TartWindow {
    let options: CGWindowListOption = [.optionOnScreenOnly, .excludeDesktopElements]
    guard let windows = CGWindowListCopyWindowInfo(options, kCGNullWindowID)
            as? [[String: Any]] else {
        throw HostControlError.noWindow("Unable to query the macOS window list")
    }

    let candidates = windows.compactMap { window -> TartWindow? in
        guard let owner = window[kCGWindowOwnerName as String] as? String,
              owner == "Tart",
              let name = window[kCGWindowName as String] as? String,
              name == vmName,
              let layer = (window[kCGWindowLayer as String] as? NSNumber)?.intValue,
              layer == 0,
              let id = (window[kCGWindowNumber as String] as? NSNumber)?.intValue,
              let pid = (window[kCGWindowOwnerPID as String] as? NSNumber)?.int32Value,
              let bounds = window[kCGWindowBounds as String] as? [String: Any],
              let x = number(bounds, "X"),
              let y = number(bounds, "Y"),
              let width = number(bounds, "Width"),
              let height = number(bounds, "Height") else {
            return nil
        }
        return TartWindow(id: id, pid: pid, x: x, y: y,
                          width: width, height: height)
    }

    guard let selected = candidates.max(by: {
        $0.width * $0.height < $1.width * $1.height
    }) else {
        throw HostControlError.noWindow(
            "No visible Tart window named '\(vmName)' was found; run without --no-graphics"
        )
    }
    return selected
}

func activate(_ window: TartWindow) {
    NSRunningApplication(processIdentifier: window.pid)?.activate(options: [.activateAllWindows])
    usleep(200_000)
}

func postMouse(type: CGEventType, point: CGPoint, button: CGMouseButton) {
    guard let event = CGEvent(mouseEventSource: nil, mouseType: type,
                              mouseCursorPosition: point, mouseButton: button) else {
        return
    }
    event.post(tap: .cghidEventTap)
}

func guestPoint(window: TartWindow, displayWidth: Double, displayHeight: Double,
                guestX: Double, guestY: Double) throws -> CGPoint {
    guard guestX >= 0, guestX < displayWidth,
          guestY >= 0, guestY < displayHeight else {
        throw HostControlError.invalidCoordinate(
            "Guest coordinate (\(guestX), \(guestY)) is outside " +
            "0..<\(Int(displayWidth)), 0..<\(Int(displayHeight))"
        )
    }

    let titleHeight = max(0, window.height - displayHeight)
    let contentHeight = window.height - titleHeight
    return CGPoint(
        x: window.x + guestX * window.width / displayWidth,
        y: window.y + titleHeight + guestY * contentHeight / displayHeight
    )
}

func click(window: TartWindow, displayWidth: Double, displayHeight: Double,
           guestX: Double, guestY: Double, buttonName: String) throws {
    let point = try guestPoint(
        window: window, displayWidth: displayWidth, displayHeight: displayHeight,
        guestX: guestX, guestY: guestY
    )

    let button: CGMouseButton
    let down: CGEventType
    let up: CGEventType
    switch buttonName {
    case "left":
        button = .left
        down = .leftMouseDown
        up = .leftMouseUp
    case "right":
        button = .right
        down = .rightMouseDown
        up = .rightMouseUp
    case "middle":
        button = .center
        down = .otherMouseDown
        up = .otherMouseUp
    default:
        throw HostControlError.usage("Unknown mouse button: \(buttonName)")
    }

    activate(window)
    CGWarpMouseCursorPosition(point)
    usleep(75_000)
    postMouse(type: down, point: point, button: button)
    usleep(75_000)
    postMouse(type: up, point: point, button: button)
}

func drag(window: TartWindow, displayWidth: Double, displayHeight: Double,
          fromX: Double, fromY: Double, toX: Double, toY: Double) throws {
    let start = try guestPoint(
        window: window, displayWidth: displayWidth, displayHeight: displayHeight,
        guestX: fromX, guestY: fromY
    )
    let end = try guestPoint(
        window: window, displayWidth: displayWidth, displayHeight: displayHeight,
        guestX: toX, guestY: toY
    )

    activate(window)
    CGWarpMouseCursorPosition(start)
    usleep(100_000)
    postMouse(type: .leftMouseDown, point: start, button: .left)
    usleep(100_000)
    for step in 1...20 {
        let fraction = Double(step) / 20.0
        let point = CGPoint(
            x: start.x + (end.x - start.x) * fraction,
            y: start.y + (end.y - start.y) * fraction
        )
        postMouse(type: .leftMouseDragged, point: point, button: .left)
        usleep(25_000)
    }
    postMouse(type: .leftMouseUp, point: end, button: .left)
}

let keyCodes: [String: CGKeyCode] = [
    "a": 0, "s": 1, "d": 2, "f": 3, "h": 4, "g": 5,
    "z": 6, "x": 7, "c": 8, "v": 9, "b": 11,
    "q": 12, "w": 13, "e": 14, "r": 15, "y": 16, "t": 17,
    "1": 18, "2": 19, "3": 20, "4": 21, "6": 22, "5": 23,
    "=": 24, "9": 25, "7": 26, "-": 27, "8": 28, "0": 29,
    "]": 30, "o": 31, "u": 32, "[": 33, "i": 34, "p": 35,
    "enter": 36, "return": 36, "l": 37, "j": 38, "'": 39,
    "k": 40, ";": 41, "\\": 42, ",": 43, "/": 44,
    "n": 45, "m": 46, ".": 47, "tab": 48, "space": 49,
    "`": 50, "delete": 51, "backspace": 51, "escape": 53, "esc": 53,
    "f17": 64, "volume-up": 72, "volume-down": 73, "mute": 74,
    "f18": 79, "f19": 80, "f5": 96, "f6": 97, "f7": 98,
    "f3": 99, "f8": 100, "f9": 101, "f11": 103, "f13": 105,
    "f16": 106, "f14": 107, "f10": 109, "f12": 111, "f15": 113,
    "help": 114, "home": 115, "page-up": 116, "forward-delete": 117,
    "f4": 118, "end": 119, "f2": 120, "page-down": 121,
    "f1": 122, "left": 123, "right": 124, "down": 125, "up": 126,
]

func parseChord(_ chord: String) throws -> (CGKeyCode, [(CGKeyCode, CGEventFlags)]) {
    var parts = chord.lowercased().split(separator: "-").map(String.init)
    var modifiers: [(CGKeyCode, CGEventFlags)] = []

    while parts.count > 1 {
        switch parts[0] {
        case "cmd", "command": modifiers.append((55, .maskCommand))
        case "shift": modifiers.append((56, .maskShift))
        case "option", "alt": modifiers.append((58, .maskAlternate))
        case "control", "ctrl": modifiers.append((59, .maskControl))
        case "fn": modifiers.append((63, .maskSecondaryFn))
        default:
            break
        }
        if ["cmd", "command", "shift", "option", "alt", "control", "ctrl", "fn"]
            .contains(parts[0]) {
            parts.removeFirst()
        } else {
            break
        }
    }

    let keyName = parts.joined(separator: "-")
    guard let code = keyCodes[keyName] else {
        throw HostControlError.invalidKey("Unknown key or chord: \(chord)")
    }
    return (code, modifiers)
}

func sendKey(window: TartWindow, chord: String) throws {
    let (code, modifiers) = try parseChord(chord)
    activate(window)

    var flags: CGEventFlags = []
    for (modifierCode, modifierFlag) in modifiers {
        flags.insert(modifierFlag)
        guard let event = CGEvent(keyboardEventSource: nil,
                                  virtualKey: modifierCode, keyDown: true) else {
            continue
        }
        event.flags = flags
        event.post(tap: .cghidEventTap)
        usleep(40_000)
    }

    for isDown in [true, false] {
        guard let event = CGEvent(keyboardEventSource: nil,
                                  virtualKey: code, keyDown: isDown) else {
            continue
        }
        event.flags = flags
        event.post(tap: .cghidEventTap)
        usleep(60_000)
    }

    for (modifierCode, modifierFlag) in modifiers.reversed() {
        flags.remove(modifierFlag)
        guard let event = CGEvent(keyboardEventSource: nil,
                                  virtualKey: modifierCode, keyDown: false) else {
            continue
        }
        event.flags = flags
        event.post(tap: .cghidEventTap)
        usleep(40_000)
    }
}

func textStroke(_ character: Character) throws -> (CGKeyCode, Bool) {
    let string = String(character)
    guard string.unicodeScalars.count == 1,
          let scalar = string.unicodeScalars.first else {
        throw HostControlError.invalidText(
            "macvm type currently supports printable ASCII, tab, and newline"
        )
    }

    switch scalar.value {
    case 65...90:
        let lowercase = UnicodeScalar(scalar.value + 32)!
        return (keyCodes[String(lowercase)]!, true)
    case 97...122:
        return (keyCodes[string]!, false)
    default:
        break
    }

    if character == "\n" || character == "\r" { return (36, false) }
    if character == "\t" { return (48, false) }
    if let code = keyCodes[string] { return (code, false) }

    let shiftedBase: [Character: String] = [
        "!": "1", "@": "2", "#": "3", "$": "4", "%": "5",
        "^": "6", "&": "7", "*": "8", "(": "9", ")": "0",
        "_": "-", "+": "=", "{": "[", "}": "]", "|": "\\",
        ":": ";", "\"": "'", "<": ",", ">": ".", "?": "/",
        "~": "`",
    ]
    if let base = shiftedBase[character], let code = keyCodes[base] {
        return (code, true)
    }

    throw HostControlError.invalidText(
        "macvm type cannot synthesize character \(String(reflecting: string)); " +
        "only printable ASCII, tab, and newline are supported"
    )
}

func postKeyboard(code: CGKeyCode, keyDown: Bool, flags: CGEventFlags) {
    guard let event = CGEvent(keyboardEventSource: nil,
                              virtualKey: code, keyDown: keyDown) else {
        return
    }
    event.flags = flags
    event.post(tap: .cghidEventTap)
    usleep(25_000)
}

func typeText(window: TartWindow, text: String) throws {
    activate(window)
    for character in text {
        let (code, shifted) = try textStroke(character)
        if shifted {
            postKeyboard(code: 56, keyDown: true, flags: .maskShift)
        }
        postKeyboard(code: code, keyDown: true,
                     flags: shifted ? .maskShift : [])
        postKeyboard(code: code, keyDown: false,
                     flags: shifted ? .maskShift : [])
        if shifted {
            postKeyboard(code: 56, keyDown: false, flags: [])
        }
    }
}

func printPermissions() throws {
    let payload: [String: Bool] = [
        "screenCapture": CGPreflightScreenCaptureAccess(),
        "postEvent": CGPreflightPostEventAccess(),
    ]
    let data = try JSONSerialization.data(withJSONObject: payload, options: [.sortedKeys])
    print(String(decoding: data, as: UTF8.self))
}

let arguments = Array(CommandLine.arguments.dropFirst())
guard let command = arguments.first else {
    fail(HostControlError.usage("Usage: host-control.swift COMMAND [ARG...]"))
}

do {
    switch command {
    case "permissions":
        try printPermissions()
    case "window-info":
        guard arguments.count == 2 else {
            throw HostControlError.usage("Usage: host-control.swift window-info VM")
        }
        let data = try JSONEncoder().encode(findWindow(named: arguments[1]))
        print(String(decoding: data, as: UTF8.self))
    case "click":
        guard arguments.count == 7,
              let displayWidth = Double(arguments[2]),
              let displayHeight = Double(arguments[3]),
              let x = Double(arguments[4]),
              let y = Double(arguments[5]) else {
            throw HostControlError.usage(
                "Usage: host-control.swift click VM DISPLAY_W DISPLAY_H X Y BUTTON"
            )
        }
        try click(window: findWindow(named: arguments[1]),
                  displayWidth: displayWidth, displayHeight: displayHeight,
                  guestX: x, guestY: y, buttonName: arguments[6])
    case "key":
        guard arguments.count == 3 else {
            throw HostControlError.usage("Usage: host-control.swift key VM CHORD")
        }
        try sendKey(window: findWindow(named: arguments[1]), chord: arguments[2])
    case "drag":
        guard arguments.count == 8,
              let displayWidth = Double(arguments[2]),
              let displayHeight = Double(arguments[3]),
              let fromX = Double(arguments[4]),
              let fromY = Double(arguments[5]),
              let toX = Double(arguments[6]),
              let toY = Double(arguments[7]) else {
            throw HostControlError.usage(
                "Usage: host-control.swift drag VM DISPLAY_W DISPLAY_H X1 Y1 X2 Y2"
            )
        }
        try drag(window: findWindow(named: arguments[1]),
                 displayWidth: displayWidth, displayHeight: displayHeight,
                 fromX: fromX, fromY: fromY, toX: toX, toY: toY)
    case "type":
        guard arguments.count == 3 else {
            throw HostControlError.usage("Usage: host-control.swift type VM TEXT")
        }
        try typeText(window: findWindow(named: arguments[1]), text: arguments[2])
    default:
        throw HostControlError.usage("Unknown host-control command: \(command)")
    }
} catch {
    fail(error)
}
