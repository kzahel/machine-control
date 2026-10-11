import CoreGraphics

/// Literal Unicode must not inherit shortcut modifiers from preceding input.
func literalTextEvents(_ character: Character,
                       create: (Bool) -> CGEvent? = {
                           CGEvent(keyboardEventSource:nil, virtualKey:0, keyDown:$0)
                       }) throws -> (CGEvent, CGEvent) {
    guard let down = create(true), let up = create(false) else {
        throw MacUIError.action("Unable to create text event")
    }
    down.flags = []; up.flags = []
    let units = Array(String(character).utf16)
    units.withUnsafeBufferPointer { buffer in
        down.keyboardSetUnicodeString(stringLength:units.count, unicodeString:buffer.baseAddress!)
        up.keyboardSetUnicodeString(stringLength:units.count, unicodeString:buffer.baseAddress!)
    }
    return (down, up)
}
