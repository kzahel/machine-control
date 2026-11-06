namespace MachineControl.Windows;

/// One typed UTF-16 unit: a keystroke on the receiving keyboard layout
/// (virtual key, optionally with Shift) or, when VirtualKey is 0, a Unicode
/// packet (VK_PACKET).
internal readonly record struct TextStroke(char Character, ushort VirtualKey = 0, bool Shift = false)
{
    internal bool Layout => VirtualKey != 0;
}

/// Chooses how each character of typed text is delivered.
///
/// A Unicode packet does not carry its character in the key message: the
/// receiver recovers it when it translates the key. A receiver whose text
/// pipeline falls behind (Windows 11 Notepad with spell check on, live) then
/// translates several queued packets as the most recent one or loses them,
/// so "the quick brown" became "the iiick nnnnn". A layout keystroke names
/// its key, so a late receiver still reads the right character. Packets
/// remain for characters the layout cannot produce with at most Shift, and
/// for control characters, whose layout keys (Tab, Enter) navigate.
internal static class TextStrokes
{
    /// layout follows VkKeyScanEx semantics for the receiving thread's layout
    /// (low byte virtual key, high byte shift state 1=Shift, 2=Ctrl, 4=Alt).
    /// produces confirms that the key and Shift state yield exactly the
    /// character on that layout, without a dead key.
    internal static TextStroke[] Plan(string text, bool layoutAllowed, Func<char, short> layout,
        Func<char, ushort, bool, bool> produces)
    {
        var strokes = new TextStroke[text.Length];
        for (var index = 0; index < text.Length; index++)
        {
            var character = text[index];
            strokes[index] = new(character);
            if (!layoutAllowed || char.IsControl(character) || char.IsSurrogate(character)) continue;
            var scanned = layout(character);
            if (scanned == -1) continue;
            var virtualKey = (ushort)(scanned & 0xFF);
            var state = (scanned >> 8) & 0xFF;
            // AltGr (Ctrl+Alt) and other shift states stay packets: injecting
            // Ctrl or Alt could reach an application shortcut instead.
            if (virtualKey == 0 || (state & ~0x01) != 0) continue;
            var shift = state == 0x01;
            if (!produces(character, virtualKey, shift)) continue;
            strokes[index] = new(character, virtualKey, shift);
        }
        return strokes;
    }

    /// The route actually used for a typed text, for the result.
    internal static string Route(IReadOnlyCollection<TextStroke> strokes) =>
        strokes.Count == 0 || strokes.All(stroke => !stroke.Layout) ? "windows.native/send_input_unicode"
        : strokes.All(stroke => stroke.Layout) ? "windows.native/send_input_layout_keys"
        : "windows.native/send_input_layout_keys+unicode";
}
