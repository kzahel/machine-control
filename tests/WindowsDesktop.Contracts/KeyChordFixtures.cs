using MachineControl.Windows;

/// The virtual-key chord grammar replaces a fixed allowlist. Every chord the
/// old allowlist accepted keeps its exact press order.
internal static class KeyChordFixtures
{
    internal static void Run()
    {
        var legacy = new Dictionary<string, ushort[]>
        {
            ["enter"] = [0x0D],
            ["escape"] = [0x1B],
            ["tab"] = [0x09],
            ["space"] = [0x20],
            ["alt+y"] = [0x12, 0x59],
            ["alt+n"] = [0x12, 0x4E],
            ["alt+tab"] = [0x12, 0x09],
            ["alt+f4"] = [0x12, 0x73],
            ["ctrl+a"] = [0x11, 0x41],
            ["ctrl+escape"] = [0x11, 0x1B],
            ["ctrl+s"] = [0x11, 0x53],
            ["ctrl+w"] = [0x11, 0x57],
            ["shift+f10"] = [0x10, 0x79],
            ["win"] = [0x5B],
            ["win+a"] = [0x5B, 0x41],
            ["win+d"] = [0x5B, 0x44],
            ["win+e"] = [0x5B, 0x45],
            ["win+i"] = [0x5B, 0x49],
            ["win+l"] = [0x5B, 0x4C],
            ["win+n"] = [0x5B, 0x4E],
            ["win+r"] = [0x5B, 0x52],
            ["win+s"] = [0x5B, 0x53],
        };
        foreach (var (chord, expected) in legacy)
        {
            var parsed = KeyChord.Parse(chord);
            Require(parsed is not null && parsed.Select(stroke => stroke.VirtualKey).SequenceEqual(expected) && parsed.All(stroke => !stroke.Extended),
                "Legacy chord unchanged: " + chord);
            Require(KeyChord.Parse(chord.ToUpperInvariant())?.Select(stroke => stroke.VirtualKey).SequenceEqual(expected) == true, "Case-insensitive: " + chord);
        }
        static ushort[]? Keys(string chord, Func<char, short>? layout = null) => KeyChord.Parse(chord, layout)?.Select(stroke => stroke.VirtualKey).ToArray();
        Require(Keys("cmd+shift+g")!.SequenceEqual(new ushort[] { 0x5B, 0x10, 0x47 }), "cmd is the logo key and modifiers keep their order");
        Require(Keys("command+l")!.SequenceEqual(new ushort[] { 0x5B, 0x4C }) && Keys("meta+l")!.SequenceEqual(new ushort[] { 0x5B, 0x4C }) &&
            Keys("super+l")!.SequenceEqual(new ushort[] { 0x5B, 0x4C }), "Logo-key aliases");
        Require(Keys("control+option+delete")!.SequenceEqual(new ushort[] { 0x11, 0x12, 0x2E }), "control/option aliases");
        Require(Keys("return")!.SequenceEqual(new ushort[] { 0x0D }) && Keys("esc")!.SequenceEqual(new ushort[] { 0x1B }), "enter/escape aliases");
        Require(Keys("f1")![0] == 0x70 && Keys("f12")![0] == 0x7B && Keys("f24")![0] == 0x87 && Keys("f25") is null && Keys("f0") is null, "Function keys f1-f24 only");
        Require(Keys("ctrl+0")!.SequenceEqual(new ushort[] { 0x11, 0x30 }) && Keys("z")!.SequenceEqual(new ushort[] { 0x5A }), "Letters and digits");
        foreach (var (name, key) in new[] { ("backspace", 0x08), ("insert", 0x2D), ("home", 0x24), ("end", 0x23), ("pageup", 0x21), ("pagedown", 0x22),
            ("up", 0x26), ("down", 0x28), ("left", 0x25), ("right", 0x27) })
            Require(Keys(name)!.SequenceEqual(new[] { (ushort)key }), "Named key " + name);
        Require(KeyChord.Parse("left")!.Single().Extended && KeyChord.Parse("delete")!.Single().Extended && !KeyChord.Parse("backspace")!.Single().Extended,
            "Navigation keys are extended");
        // Punctuation resolves through the active layout (VkKeyScanW).
        short Layout(char character) => character switch { '/' => 0x00BF, '?' => 0x01BF, '+' => 0x01BB, '=' => 0x00BB, _ => -1 };
        Require(Keys("ctrl+/", Layout)!.SequenceEqual(new ushort[] { 0x11, 0xBF }), "Unshifted punctuation");
        Require(Keys("ctrl+?", Layout)!.SequenceEqual(new ushort[] { 0x11, 0x10, 0xBF }), "Layout shift precedes the key");
        Require(Keys("shift+?", Layout)!.SequenceEqual(new ushort[] { 0x10, 0xBF }), "An explicit shift is not doubled");
        Require(Keys("ctrl++", Layout)!.SequenceEqual(new ushort[] { 0x11, 0x10, 0xBB }) && Keys("+", Layout)!.SequenceEqual(new ushort[] { 0x10, 0xBB }),
            "A trailing + is the plus key");
        Require(Keys("~", Layout) is null && Keys("ctrl+/") is null, "Unmapped punctuation or no layout refuses");
        foreach (var invalid in new[] { "", " ", "ctrl+", "ctrl+ctrl+a", "ctrl+a+b", "a+ctrl", "hyper+a", "ctrl+enterr", "ctrl++a", "win+win",
            "é", "ctrl+\u0001", new string('a', 65) })
            Require(KeyChord.Parse(invalid, Layout) is null, "Refused without partial delivery: " + invalid);
        Console.WriteLine("Windows virtual-key chord contracts passed");
    }

    private static void Require(bool value, string message) { if (!value) throw new Exception(message); }
}
