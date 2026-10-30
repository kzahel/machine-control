import CoreGraphics

/// Literal Unicode must not inherit shortcut modifiers from preceding input.
func literalTextEvents(_ character: Character,
                       create: (Bool) -> CGEvent? = {
                           CGEvent(keyboardEventSource: CGEventSource(stateID: .privateState), virtualKey:0, keyDown:$0)
                       }) throws -> (CGEvent, CGEvent) {
    guard let down = create(true), let up = create(false) else {
        throw MacUIError.action("Unable to create text event")
    }
    down.flags = []; up.flags = []
    // Unicode LF on an A-key event is ignored by native text clients (including
    // Chrome). Deliver a line break as Return, whose macOS character is CR.
    // Swift treats CRLF as one Character, so it must produce only one Return.
    let lineBreak = character == "\n" || character == "\r" || character == "\r\n"
    if lineBreak {
        down.setIntegerValueField(.keyboardEventKeycode, value: 36)
        up.setIntegerValueField(.keyboardEventKeycode, value: 36)
    }
    let units = Array((lineBreak ? "\r" : String(character)).utf16)
    units.withUnsafeBufferPointer { buffer in
        down.keyboardSetUnicodeString(stringLength:units.count, unicodeString:buffer.baseAddress!)
        up.keyboardSetUnicodeString(stringLength:units.count, unicodeString:buffer.baseAddress!)
    }
    return (down, up)
}
