namespace MachineControl.Windows;

/// One parsed virtual-key stroke. Extended marks the navigation cluster so
/// SendInput does not deliver the numeric-keypad alias.
internal readonly record struct KeyStroke(ushort VirtualKey, bool Extended = false);

/// Bounded chord grammar for virtual-key input: zero or more modifiers and
/// one main key joined with '+'. Parsing completes before any delivery, so an
/// unknown name is refused without a partial chord.
internal static class KeyChord
{
    internal const int MaxLength = 64;
    private const ushort Shift = 0x10, Control = 0x11, Alt = 0x12, Logo = 0x5B;

    private static ushort? Modifier(string name) => name switch
    {
        "ctrl" or "control" => Control,
        "alt" or "option" => Alt,
        "shift" => Shift,
        "win" or "windows" or "cmd" or "command" or "meta" or "super" => Logo,
        _ => null,
    };

    private static KeyStroke? Named(string name)
    {
        if (name.Length == 1 && name[0] is >= 'a' and <= 'z') return new((ushort)char.ToUpperInvariant(name[0]));
        if (name.Length == 1 && name[0] is >= '0' and <= '9') return new(name[0]);
        if (name.Length is 2 or 3 && name[0] == 'f' && int.TryParse(name.AsSpan(1), System.Globalization.NumberStyles.None,
                System.Globalization.CultureInfo.InvariantCulture, out var function) && function is >= 1 and <= 24)
            return new((ushort)(0x70 + function - 1));
        return name switch
        {
            "enter" or "return" => new(0x0D),
            "escape" or "esc" => new(0x1B),
            "tab" => new(0x09),
            "space" => new(0x20),
            "backspace" => new(0x08),
            "delete" or "del" => new(0x2E, true),
            "insert" => new(0x2D, true),
            "home" => new(0x24, true),
            "end" => new(0x23, true),
            "pageup" => new(0x21, true),
            "pagedown" => new(0x22, true),
            "up" => new(0x26, true),
            "down" => new(0x28, true),
            "left" => new(0x25, true),
            "right" => new(0x27, true),
            _ => null,
        };
    }

    /// Returns the press order (modifiers first, main key last), or null for
    /// an unknown, empty, oversized or multi-key chord. Punctuation resolves
    /// through the supplied layout mapping (VkKeyScanW semantics: low byte
    /// virtual key, high byte shift state 1=Shift, 2=Ctrl, 4=Alt).
    internal static KeyStroke[]? Parse(string? chord, Func<char, short>? layout = null)
    {
        if (string.IsNullOrWhiteSpace(chord) || chord.Length > MaxLength) return null;
        var text = chord.Trim().ToLowerInvariant();
        var parts = text.Split('+').Select(part => part.Trim()).ToList();
        // A trailing empty part means the main key itself is "+".
        if (parts.Count >= 2 && parts[^1] == "" && parts[^2] == "") { parts.RemoveAt(parts.Count - 1); parts[^1] = "+"; }
        if (parts.Count == 0 || parts.Any(part => part.Length == 0)) return null;
        var strokes = new List<KeyStroke>();
        for (var index = 0; index < parts.Count - 1; index++)
        {
            if (Modifier(parts[index]) is not { } modifier || strokes.Any(stroke => stroke.VirtualKey == modifier)) return null;
            strokes.Add(new(modifier));
        }
        var last = parts[^1];
        if (Named(last) is { } main) strokes.Add(main);
        else if (Modifier(last) is { } lone)
        {
            // A modifier alone ("win") is a key in its own right.
            if (strokes.Any(stroke => stroke.VirtualKey == lone)) return null;
            strokes.Add(new(lone));
        }
        else if (last.Length == 1 && !char.IsLetterOrDigit(last[0]) && !char.IsControl(last[0]) &&
            !char.IsWhiteSpace(last[0]) && last[0] <= 0x7E && layout?.Invoke(last[0]) is { } scanned && scanned != -1)
        {
            var virtualKey = (ushort)(scanned & 0xFF);
            var state = (scanned >> 8) & 0xFF;
            if (virtualKey == 0 || (state & ~0x07) != 0) return null;
            foreach (var (bit, modifier) in new[] { (1, Shift), (2, Control), (4, Alt) })
                if ((state & bit) != 0 && strokes.All(stroke => stroke.VirtualKey != modifier))
                    strokes.Add(new(modifier));
            // Layout modifiers precede the main key regardless of their bit order.
            strokes.Add(new(virtualKey));
        }
        else return null;
        return strokes.ToArray();
    }
}
