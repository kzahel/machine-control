package dev.machinecontrol.android.hid;

import java.util.HashMap;
import java.util.Locale;
import java.util.Map;

/**
 * Text and chord to HID keyboard usage translation. Pure Java, no Android
 * dependencies, so it is covered by local unit tests.
 *
 * HID reports carry key positions; the host's configured layout decides the
 * character. The layout argument names the host layout so we press the key
 * that produces the requested character there.
 */
public final class Keymap {
    public static final int CTRL = 0x01, SHIFT = 0x02, ALT = 0x04, META = 0x08;

    /** US key positions in row order, unshifted, and what a Dvorak host produces there. */
    private static final String US_POSITIONS = "`1234567890-=qwertyuiop[]\\asdfghjkl;'zxcvbnm,./";
    private static final String DVORAK_AT_US = "`1234567890[]',.pyfgcrl/=\\aoeuidhtns-;qjkxbmwvz";
    private static final String SHIFT_FROM = "`1234567890-=[]\\;',./";
    private static final String SHIFT_TO = "~!@#$%^&*()_+{}|:\"<>?";

    private static final Map<Character, Integer> US_USAGE = new HashMap<>();
    private static final Map<String, Integer> NAMED = new HashMap<>();
    private static final Map<String, Integer> MODIFIERS = new HashMap<>();

    static {
        for (char c = 'a'; c <= 'z'; c++) US_USAGE.put(c, 0x04 + (c - 'a'));
        for (char c = '1'; c <= '9'; c++) US_USAGE.put(c, 0x1e + (c - '1'));
        US_USAGE.put('0', 0x27);
        String punct = "-=[]\\";
        for (int i = 0; i < punct.length(); i++) US_USAGE.put(punct.charAt(i), 0x2d + i);
        US_USAGE.put(';', 0x33);
        US_USAGE.put('\'', 0x34);
        US_USAGE.put('`', 0x35);
        US_USAGE.put(',', 0x36);
        US_USAGE.put('.', 0x37);
        US_USAGE.put('/', 0x38);

        NAMED.put("enter", 0x28); NAMED.put("return", 0x28);
        NAMED.put("escape", 0x29); NAMED.put("esc", 0x29);
        NAMED.put("backspace", 0x2a);
        NAMED.put("tab", 0x2b);
        NAMED.put("space", 0x2c);
        NAMED.put("capslock", 0x39);
        for (int i = 1; i <= 12; i++) NAMED.put("f" + i, 0x3a + i - 1);
        NAMED.put("printscreen", 0x46);
        NAMED.put("scrolllock", 0x47);
        NAMED.put("pause", 0x48);
        NAMED.put("insert", 0x49);
        NAMED.put("home", 0x4a);
        NAMED.put("pageup", 0x4b);
        NAMED.put("delete", 0x4c);
        NAMED.put("end", 0x4d);
        NAMED.put("pagedown", 0x4e);
        NAMED.put("right", 0x4f);
        NAMED.put("left", 0x50);
        NAMED.put("down", 0x51);
        NAMED.put("up", 0x52);

        MODIFIERS.put("ctrl", CTRL); MODIFIERS.put("control", CTRL);
        MODIFIERS.put("shift", SHIFT);
        MODIFIERS.put("alt", ALT);
        MODIFIERS.put("meta", META); MODIFIERS.put("search", META);
        MODIFIERS.put("super", META); MODIFIERS.put("win", META); MODIFIERS.put("cmd", META);
    }

    private Keymap() { }

    public static boolean knownLayout(String layout) {
        return "us".equals(layout) || "dvorak".equals(layout);
    }

    /** Returns {modifiers, usage} for one character, or null when unsupported. */
    public static int[] stroke(char c, String layout) {
        if (c == '\n' || c == '\r') return new int[] {0, 0x28};
        if (c == '\t') return new int[] {0, 0x2b};
        if (c == ' ') return new int[] {0, 0x2c};
        int modifiers = 0;
        char base = c;
        if (c >= 'A' && c <= 'Z') {
            modifiers = SHIFT;
            base = Character.toLowerCase(c);
        } else {
            int shifted = SHIFT_TO.indexOf(c);
            if (shifted >= 0) {
                modifiers = SHIFT;
                base = SHIFT_FROM.charAt(shifted);
            }
        }
        if (!US_USAGE.containsKey(base)) return null;
        char position = base;
        if ("dvorak".equals(layout)) {
            int index = DVORAK_AT_US.indexOf(base);
            if (index < 0) return null;
            position = US_POSITIONS.charAt(index);
        } else if (!"us".equals(layout)) {
            return null;
        }
        return new int[] {modifiers, US_USAGE.get(position)};
    }

    /**
     * Translates all of the text before anything is sent, so unsupported input
     * is refused without a partial delivery. A CRLF pair becomes one Enter.
     */
    public static int[][] text(String text, String layout) {
        int[][] strokes = new int[text.length()][];
        int count = 0;
        for (int i = 0; i < text.length(); i++) {
            char c = text.charAt(i);
            if (c == '\r' && i + 1 < text.length() && text.charAt(i + 1) == '\n') continue;
            int[] stroke = stroke(c, layout);
            if (stroke == null) throw new IllegalArgumentException("Unsupported character at index " + i);
            strokes[count++] = stroke;
        }
        int[][] result = new int[count][];
        System.arraycopy(strokes, 0, result, 0, count);
        return result;
    }

    /** Parses chords such as "ctrl+alt+t", "shift+tab", "enter" or "search". */
    public static int[] chord(String spec, String layout) {
        String[] parts = spec.trim().toLowerCase(Locale.ROOT).split("\\+", -1);
        int modifiers = 0;
        int usage = 0;
        for (int i = 0; i < parts.length; i++) {
            String part = parts[i].trim();
            if (part.isEmpty()) throw new IllegalArgumentException("Empty key in chord");
            boolean last = i == parts.length - 1;
            Integer modifier = MODIFIERS.get(part);
            if (modifier != null && !last) {
                modifiers |= modifier;
                continue;
            }
            if (!last) throw new IllegalArgumentException("Only the final chord key may be a non-modifier");
            if (modifier != null) {
                // A lone modifier tap, for example "search" to open the launcher.
                // Modifiers live only in the modifier byte; the key array is empty.
                modifiers |= modifier;
                usage = 0;
            } else if (NAMED.containsKey(part)) {
                usage = NAMED.get(part);
            } else if (part.length() == 1) {
                int[] stroke = stroke(part.charAt(0), layout);
                if (stroke == null) throw new IllegalArgumentException("Unsupported chord key");
                modifiers |= stroke[0];
                usage = stroke[1];
            } else {
                throw new IllegalArgumentException("Unknown key name");
            }
        }
        return new int[] {modifiers, usage};
    }
}
