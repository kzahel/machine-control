package dev.machinecontrol.android.hid;

import static org.junit.Assert.assertArrayEquals;
import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertNull;
import static org.junit.Assert.assertThrows;

import org.junit.Test;

public final class KeymapTest {
    @Test public void usLettersDigitsAndShiftedSymbols() {
        assertArrayEquals(new int[] {0, 0x04}, Keymap.stroke('a', "us"));
        assertArrayEquals(new int[] {Keymap.SHIFT, 0x1d}, Keymap.stroke('Z', "us"));
        assertArrayEquals(new int[] {0, 0x27}, Keymap.stroke('0', "us"));
        assertArrayEquals(new int[] {Keymap.SHIFT, 0x1f}, Keymap.stroke('@', "us"));
        assertArrayEquals(new int[] {Keymap.SHIFT, 0x34}, Keymap.stroke('"', "us"));
        assertArrayEquals(new int[] {Keymap.SHIFT, 0x31}, Keymap.stroke('|', "us"));
        assertArrayEquals(new int[] {0, 0x2c}, Keymap.stroke(' ', "us"));
        assertArrayEquals(new int[] {0, 0x28}, Keymap.stroke('\n', "us"));
    }

    @Test public void dvorakPressesTheKeyThatProducesTheCharacter() {
        // On a Dvorak host the US 'd' position produces 'e', and US 'q' produces '\''.
        assertArrayEquals(new int[] {0, 0x07}, Keymap.stroke('e', "dvorak"));
        assertArrayEquals(new int[] {0, 0x14}, Keymap.stroke('\'', "dvorak"));
        assertArrayEquals(new int[] {Keymap.SHIFT, 0x07}, Keymap.stroke('E', "dvorak"));
        // US 'z' position produces ';' on Dvorak; ':' is its shifted form.
        assertArrayEquals(new int[] {Keymap.SHIFT, 0x1d}, Keymap.stroke(':', "dvorak"));
        assertArrayEquals(new int[] {0, 0x1e}, Keymap.stroke('1', "dvorak"));
    }

    @Test public void textIsTranslatedCompletelyOrRefused() {
        assertEquals(3, Keymap.text("a\r\nb", "us").length);
        assertThrows(IllegalArgumentException.class, () -> Keymap.text("ok é", "us"));
        assertNull(Keymap.stroke('a', "colemak"));
    }

    @Test public void chords() {
        assertArrayEquals(new int[] {Keymap.CTRL | Keymap.ALT, 0x17}, Keymap.chord("ctrl+alt+t", "us"));
        assertArrayEquals(new int[] {Keymap.SHIFT, 0x2b}, Keymap.chord("Shift+Tab", "us"));
        assertArrayEquals(new int[] {0, 0x3e}, Keymap.chord("f5", "us"));
        assertArrayEquals(new int[] {Keymap.META, 0}, Keymap.chord("search", "us"));
        assertArrayEquals(new int[] {Keymap.CTRL, 0x0c}, Keymap.chord("ctrl+c", "dvorak"));
        assertThrows(IllegalArgumentException.class, () -> Keymap.chord("a+ctrl", "us"));
        assertThrows(IllegalArgumentException.class, () -> Keymap.chord("ctrl+", "us"));
        assertThrows(IllegalArgumentException.class, () -> Keymap.chord("hyper+x", "us"));
    }

    @Test public void reportsAndMotionSplitting() {
        assertArrayEquals(new byte[] {2, 0, 4, 0, 0, 0, 0, 0}, Reports.keyboard(2, 4));
        assertArrayEquals(new byte[] {1, 127, -127, 0, 0}, Reports.mouse(1, 400, -400, 0, 0));
        assertEquals(3, Reports.stepCount(300, -10));
        int[] steps = Reports.spread(300, 3);
        assertEquals(300, steps[0] + steps[1] + steps[2]);
        for (int step : steps) assertEquals(true, Math.abs(step) <= 127);
        assertEquals(1, Reports.stepCount(0));
    }
}
