using MachineControl.Windows;

/// Typed text uses keystrokes the receiving layout can produce exactly, and
/// Unicode packets otherwise. A packet's character is recovered only when the
/// receiver translates it, so a late receiver can substitute or lose it.
internal static class TextStrokeFixtures
{
    internal static void Run()
    {
        // A US-like layout: VkKeyScanEx semantics.
        static short Layout(char character) => character switch
        {
            >= 'a' and <= 'z' => (short)char.ToUpperInvariant(character),
            >= 'A' and <= 'Z' => (short)(0x100 | character),
            >= '0' and <= '9' => (short)character,
            ' ' => 0x20,
            '!' => 0x131,
            '\t' => 0x09,
            '€' => 0x645, // AltGr (Ctrl+Alt) + E
            '^' => 0x1DE, // a dead key on this layout
            _ => -1,
        };
        static bool Produces(char character, ushort virtualKey, bool shift) => character != '^';

        var plain = TextStrokes.Plan("Hi there 0!", true, Layout, Produces);
        Require(plain.All(stroke => stroke.Layout), "Characters on the layout are layout keystrokes");
        Require(plain[0] == new TextStroke('H', 0x48, true) && plain[1] == new TextStroke('i', 0x49, false),
            "Upper case adds Shift, lower case does not");
        Require(plain[2] == new TextStroke(' ', 0x20) && plain[^1] == new TextStroke('!', 0x31, true), "Space and shifted punctuation");
        Require(TextStrokes.Route(plain) == "windows.native/send_input_layout_keys", "All-layout route");

        var mixed = TextStrokes.Plan("a\té€^b😀", true, Layout, Produces);
        Require(mixed[0].Layout && mixed[5].Layout, "Layout characters around packets");
        Require(!mixed[1].Layout, "Tab stays a packet: the Tab key navigates");
        Require(!mixed[2].Layout, "A character missing from the layout is a packet");
        Require(!mixed[3].Layout, "AltGr would inject Ctrl+Alt; it is a packet");
        Require(!mixed[4].Layout, "A dead key would compose with the next key; it is a packet");
        Require(!mixed[6].Layout && !mixed[7].Layout, "Both surrogate halves are packets");
        Require(mixed.Select(stroke => stroke.Character).SequenceEqual("a\té€^b😀"), "Every UTF-16 unit is planned once, in order");
        Require(TextStrokes.Route(mixed) == "windows.native/send_input_layout_keys+unicode", "Mixed route");

        var refused = TextStrokes.Plan("abc", false, Layout, Produces);
        Require(refused.All(stroke => !stroke.Layout), "Without a usable layout every character is a packet");
        Require(TextStrokes.Route(refused) == "windows.native/send_input_unicode", "Packet route");
        Require(TextStrokes.Plan("", true, Layout, Produces).Length == 0, "Empty text plans nothing");
        Console.WriteLine("Windows typed-text stroke contracts passed");
    }

    private static void Require(bool value, string message) { if (!value) throw new Exception(message); }
}
