import Carbon
import CoreGraphics
import Foundation

enum KeyboardInputError: String, Error {
    case layoutUnavailable = "keyboard_layout_unavailable"
    case layoutChanged = "keyboard_layout_changed"
    case keyUnavailable = "key_unavailable_in_keyboard_layout"
    case credentialUnavailable = "credential_character_unavailable_in_keyboard_layout"
}

/// A request takes one snapshot. Never cache the user's selected layout across
/// requests, and never resolve credential bytes through an ASCII fallback.
struct KeyboardLayoutSnapshot {
    let id: String
    let inputSourceID: String
    let keyboardType: UInt32
    let translate: (CGKeyCode, CGEventFlags) -> String?

    static func sourceID(_ source: TISInputSource) -> String {
        guard let value = TISGetInputSourceProperty(source, kTISPropertyInputSourceID) else { return "unknown" }
        return Unmanaged<CFString>.fromOpaque(value).takeUnretainedValue() as String
    }

    static func current() throws -> Self {
        let selected = TISCopyCurrentKeyboardInputSource().takeRetainedValue()
        let source = TISCopyCurrentKeyboardLayoutInputSource().takeRetainedValue()
        guard let value = TISGetInputSourceProperty(source, kTISPropertyUnicodeKeyLayoutData) else {
            throw KeyboardInputError.layoutUnavailable
        }
        let data = Unmanaged<CFData>.fromOpaque(value).takeUnretainedValue() as Data
        let type = UInt32(LMGetKbdType())
        return Self(id: sourceID(source), inputSourceID: sourceID(selected), keyboardType: type) { code, flags in
            data.withUnsafeBytes { bytes in
                guard let base = bytes.baseAddress else { return nil }
                var modifiers: UInt32 = 0
                if flags.contains(.maskCommand) { modifiers |= UInt32(cmdKey) }
                if flags.contains(.maskShift) { modifiers |= UInt32(shiftKey) }
                if flags.contains(.maskAlternate) { modifiers |= UInt32(optionKey) }
                if flags.contains(.maskControl) { modifiers |= UInt32(controlKey) }
                var dead: UInt32 = 0, length = 0
                var units = [UniChar](repeating: 0, count: 16)
                // Do not disable dead keys: they must be detected and refused
                // for exact credential entry rather than emitting an accent.
                let status = UCKeyTranslate(base.assumingMemoryBound(to: UCKeyboardLayout.self), code,
                    UInt16(kUCKeyActionDown), modifiers >> 8, type, 0, &dead,
                    units.count, &length, &units)
                guard status == noErr, dead == 0, length > 0 else { return nil }
                return String(utf16CodeUnits: units, count: length)
            }
        }
    }

    func verifyCurrent() throws {
        let now = try Self.current()
        guard now.id == id, now.inputSourceID == inputSourceID, now.keyboardType == keyboardType else {
            throw KeyboardInputError.layoutChanged
        }
    }

    func resolve(_ character: String, modifiers: CGEventFlags = [], allowOption: Bool = false) -> ResolvedKeyboardKey? {
        // Command can select a different mapping (Dvorak–QWERTY Command).
        // Option/Control describe the requested chord, not its base key name.
        let command: CGEventFlags = modifiers.contains(.maskCommand) ? .maskCommand : []
        let levels: [CGEventFlags] = allowOption ? [[], .maskShift, .maskAlternate, [.maskAlternate, .maskShift]] : [[], .maskShift]
        for level in levels {
            for code in CGKeyCode(0)..<128 where !Self.nonCharacterCodes.contains(code) {
                if translate(code, command.union(level)) == character {
                    let flags = modifiers.union(level)
                    return ResolvedKeyboardKey(code: code, flags: flags, layoutID: id,
                        fallback: false)
                }
            }
        }
        return nil
    }

    static let namedCodes: [String: CGKeyCode] = [
        "enter":36, "return":36, "tab":48, "space":49, "delete":51,
        "backspace":51, "escape":53, "esc":53, "forwarddelete":117,
        "home":115, "end":119, "pageup":116, "pagedown":121,
        "left":123, "right":124, "down":125, "up":126,
        "f1":122, "f2":120, "f3":99, "f4":118, "f5":96, "f6":97,
        "f7":98, "f8":100, "f9":101, "f10":109, "f11":103, "f12":111,
    ]
    static let nonCharacterCodes = Set(namedCodes.values).subtracting([49])
}

struct ResolvedKeyboardKey {
    let code: CGKeyCode
    let flags: CGEventFlags
    let layoutID: String
    var fallback: Bool
    var data: [String: Any] {
        ["resolvedKeyCode": Int(code), "layoutId": layoutID, "fallbackLayoutUsed": fallback,
         "modifierFlags": flags.rawValue]
    }
}

func resolveKeyboardChord(_ chord: String, layout: KeyboardLayoutSnapshot) throws -> ResolvedKeyboardKey {
    var key = normalizedKeyChord(chord).lowercased()
    var flags: CGEventFlags = []
    let modifiers: [String: CGEventFlags] = ["cmd":.maskCommand, "command":.maskCommand,
        "shift":.maskShift, "option":.maskAlternate, "alt":.maskAlternate,
        "ctrl":.maskControl, "control":.maskControl]
    while let separator = key.firstIndex(of: "-"), separator != key.startIndex {
        let name = String(key[..<separator])
        guard let flag = modifiers[name] else { throw MacUIError.usage("Unsupported key modifier: \(name)") }
        flags.insert(flag); key = String(key[key.index(after: separator)...])
    }
    if let code = KeyboardLayoutSnapshot.namedCodes[key] {
        return ResolvedKeyboardKey(code: code, flags: flags, layoutID: layout.id, fallback: false)
    }
    guard key.count == 1 else { throw MacUIError.usage("Unsupported key chord") }
    guard layout.inputSourceID == layout.id else { throw KeyboardInputError.layoutUnavailable }
    if let resolved = layout.resolve(key, modifiers: flags) { return resolved }
    // An ASCII fallback is unsafe unless the effective Command mapping has
    // been proved for this layout. Refuse instead of dispatching another key.
    throw KeyboardInputError.keyUnavailable
}

func privateInputSource() throws -> CGEventSource {
    guard let source = CGEventSource(stateID: .privateState) else { throw MacUIError.action("input_source_unavailable") }
    source.localEventsSuppressionInterval = 0
    return source
}

func keyboardEvents(_ key: ResolvedKeyboardKey, source: CGEventSource) throws -> (CGEvent, CGEvent) {
    guard let down = CGEvent(keyboardEventSource: source, virtualKey: key.code, keyDown: true),
          let up = CGEvent(keyboardEventSource: source, virtualKey: key.code, keyDown: false) else {
        throw MacUIError.action("Unable to create keyboard event")
    }
    for event in [down, up] {
        event.flags = key.flags
    }
    return (down, up)
}

func postKeyboardKey(_ key: ResolvedKeyboardKey, processID: pid_t? = nil,
                     cancellation: () -> String? = { nil }) throws {
    let source = try privateInputSource()
    let (down, up) = try keyboardEvents(key, source: source)
    let initial = CGEventSource.flagsState(.combinedSessionState)
    let modifiers: [(CGEventFlags, CGKeyCode)] = [(.maskCommand,55), (.maskShift,56), (.maskAlternate,58), (.maskControl,59)]
    var releases: [CGEvent] = []
    if processID == nil {
        for (flag, code) in modifiers where key.flags.contains(flag) && !initial.contains(flag) {
            guard let event = CGEvent(keyboardEventSource: source, virtualKey: code, keyDown: false) else {
                throw MacUIError.action("Unable to create modifier release")
            }
            event.type = .flagsChanged
            event.flags = initial
            releases.append(event)
        }
    }
    if let reason = cancellation() { throw MacUIError.action(reason) }
    if let processID { down.postToPid(processID); up.postToPid(processID) }
    else {
        down.post(tap: .cghidEventTap)
        // Once pressed, release even if authority is withdrawn.
        up.post(tap: .cghidEventTap)
        for event in releases.reversed() { event.post(tap: .cghidEventTap) }
    }
}

/// Resolve the whole secret before any field clearing or input. Printable
/// ASCII is the declared credential transport; no dead keys, fallback or prefix.
func credentialKeyboardPlan(_ credential: Data, layout: KeyboardLayoutSnapshot) throws -> [ResolvedKeyboardKey] {
    guard !credential.isEmpty, credential.count <= 256 else { throw MacUIError.usage("credential_size_invalid") }
    guard layout.inputSourceID == layout.id else { throw KeyboardInputError.credentialUnavailable }
    return try credential.map { byte in
        guard (32...126).contains(byte), let key = layout.resolve(String(UnicodeScalar(byte)), allowOption: true) else {
            throw KeyboardInputError.credentialUnavailable
        }
        return key
    }
}

func credentialLayoutPreflight(_ layout: KeyboardLayoutSnapshot) throws {
    // The one-shot protocol does not disclose a secret alphabet before reading.
    // Require the complete supported alphabet up front, not a guessed subset.
    _ = try credentialKeyboardPlan(Data((32...126).map(UInt8.init)), layout: layout)
}
