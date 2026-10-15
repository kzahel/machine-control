// Replica sender for keyboard-layout experiments. It reproduces the
// resident's event construction outside the resident so behavior can be
// compared without an access grant. Post only to the keyboard fixture.
//
//   keysend PID ansi CHORD        Resident.sendKey: US-ANSI key code table
//   keysend PID layout CHORD      candidate: resolve the character through
//                                 the current (then ASCII-capable) layout
//   keysend PID credential TEXT   Resident.sendCredential/physicalKey replica
//   keysend 0 ansi CHORD          HID tap; refuses unless the fixture is frontmost
//   keysend - modifiers [release] read (or release) session modifier state
import AppKit
import Carbon
import CoreGraphics

let ansi: [String: CGKeyCode] = [
    "a": 0, "s": 1, "d": 2, "f": 3, "h": 4, "g": 5, "z": 6, "x": 7, "c": 8, "v": 9,
    "b": 11, "q": 12, "w": 13, "e": 14, "r": 15, "y": 16, "t": 17, "1": 18, "2": 19,
    "3": 20, "4": 21, "6": 22, "5": 23, "=": 24, "9": 25, "7": 26, "-": 27, "8": 28,
    "0": 29, "]": 30, "o": 31, "u": 32, "[": 33, "i": 34, "p": 35, "l": 37, "j": 38,
    "'": 39, "k": 40, ";": 41, "\\": 42, ",": 43, "/": 44, "n": 45, "m": 46, ".": 47,
]

func layoutData(_ source: TISInputSource) -> UnsafePointer<UCKeyboardLayout>? {
    guard let raw = TISGetInputSourceProperty(source, kTISPropertyUnicodeKeyLayoutData) else { return nil }
    let data = Unmanaged<CFData>.fromOpaque(raw).takeUnretainedValue()
    return UnsafeRawPointer(CFDataGetBytePtr(data)).assumingMemoryBound(to: UCKeyboardLayout.self)
}

func translate(_ layout: UnsafePointer<UCKeyboardLayout>, _ code: UInt16, shift: Bool) -> String {
    var dead: UInt32 = 0, length = 0
    var chars = [UniChar](repeating: 0, count: 4)
    UCKeyTranslate(layout, code, UInt16(kUCKeyActionDown), shift ? UInt32(shiftKey >> 8) : 0,
                   UInt32(LMGetKbdType()), OptionBits(kUCKeyTranslateNoDeadKeysBit),
                   &dead, 4, &length, &chars)
    return String(utf16CodeUnits: chars, count: length)
}

func resolve(_ character: String) -> (CGKeyCode, Bool)? {
    let sources = [TISCopyCurrentKeyboardLayoutInputSource().takeRetainedValue(),
                   TISCopyCurrentASCIICapableKeyboardLayoutInputSource().takeRetainedValue()]
    for source in sources {
        guard let layout = layoutData(source) else { continue }
        for shift in [false, true] {
            for code in UInt16(0)..<128 where translate(layout, code, shift: shift) == character {
                return (CGKeyCode(code), shift)
            }
        }
    }
    return nil
}

func modifiers() -> String {
    let flags = CGEventSource.flagsState(.hidSystemState)
    return "cmd=\(flags.contains(.maskCommand)) shift=\(flags.contains(.maskShift)) raw=\(String(flags.rawValue, radix: 16))"
}

func post(_ pid: pid_t, _ code: CGKeyCode, _ flags: CGEventFlags) {
    let down = CGEvent(keyboardEventSource: nil, virtualKey: code, keyDown: true)!
    let up = CGEvent(keyboardEventSource: nil, virtualKey: code, keyDown: false)!
    down.flags = flags
    up.flags = flags
    if pid == 0 {
        guard NSWorkspace.shared.frontmostApplication?.bundleIdentifier == "org.machine-control.keyboard-fixture" else {
            print("refused: keyboard fixture is not frontmost"); exit(3)
        }
        down.post(tap: .cghidEventTap); up.post(tap: .cghidEventTap)
    } else {
        down.postToPid(pid); up.postToPid(pid)
    }
}

let args = CommandLine.arguments
guard args.count >= 3 else { print("usage: keysend PID ansi|layout|credential VALUE | keysend - modifiers [release]"); exit(2) }
if args[2] == "modifiers" {
    if args.count > 3, args[3] == "release" {
        let release = CGEvent(keyboardEventSource: nil, virtualKey: 55, keyDown: false)!
        release.type = .flagsChanged
        release.flags = []
        release.post(tap: .cghidEventTap)
        usleep(200_000)
    }
    print(modifiers()); exit(0)
}
let pid = pid_t(args[1])!
if args[2] == "credential" {
    for character in args[3] {
        let text = String(character), lower = text.lowercased()
        guard let code = ansi[lower] else { print("unsupported \(text)"); exit(2) }
        post(pid, code, text != lower ? .maskShift : [])
        usleep(18_000)
    }
} else {
    let parts = args[3].split(separator: "+").map(String.init)
    var flags: CGEventFlags = []
    for modifier in parts.dropLast() {
        switch modifier.lowercased() {
        case "cmd": flags.insert(.maskCommand)
        case "shift": flags.insert(.maskShift)
        case "ctrl": flags.insert(.maskControl)
        case "option": flags.insert(.maskAlternate)
        default: print("unknown modifier \(modifier)"); exit(2)
        }
    }
    let key = parts.last!
    if args[2] == "layout" {
        guard let (code, shift) = resolve(key) else { print("unresolvable \(key)"); exit(2) }
        if shift { flags.insert(.maskShift) }
        post(pid, code, flags)
        print("code=\(code)")
    } else {
        guard let code = ansi[key.lowercased()] else { print("unsupported \(key)"); exit(2) }
        post(pid, code, flags)
    }
}
// postToPid delivers asynchronously; exiting at once can drop the events.
usleep(300_000)
