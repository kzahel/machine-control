package dev.machinecontrol.android.hid;

/** Report descriptor and report builders for a combined keyboard and mouse. */
public final class Reports {
    public static final int KEYBOARD_ID = 1;
    public static final int MOUSE_ID = 2;
    public static final int KEYBOARD_SIZE = 8;
    public static final int MOUSE_SIZE = 5;
    public static final int BUTTON_LEFT = 0x01, BUTTON_RIGHT = 0x02, BUTTON_MIDDLE = 0x04;

    public static final byte[] DESCRIPTOR = bytes(
        // Keyboard, report ID 1: modifiers, reserved, LED output, six keys.
        0x05, 0x01, 0x09, 0x06, 0xa1, 0x01, 0x85, KEYBOARD_ID,
        0x05, 0x07, 0x19, 0xe0, 0x29, 0xe7, 0x15, 0x00, 0x25, 0x01, 0x75, 0x01, 0x95, 0x08, 0x81, 0x02,
        0x95, 0x01, 0x75, 0x08, 0x81, 0x01,
        0x95, 0x05, 0x75, 0x01, 0x05, 0x08, 0x19, 0x01, 0x29, 0x05, 0x91, 0x02,
        0x95, 0x01, 0x75, 0x03, 0x91, 0x01,
        0x95, 0x06, 0x75, 0x08, 0x15, 0x00, 0x25, 0x65, 0x05, 0x07, 0x19, 0x00, 0x29, 0x65, 0x81, 0x00,
        0xc0,
        // Mouse, report ID 2: five buttons, relative X, Y, wheel and horizontal pan.
        0x05, 0x01, 0x09, 0x02, 0xa1, 0x01, 0x85, MOUSE_ID, 0x09, 0x01, 0xa1, 0x00,
        0x05, 0x09, 0x19, 0x01, 0x29, 0x05, 0x15, 0x00, 0x25, 0x01, 0x95, 0x05, 0x75, 0x01, 0x81, 0x02,
        0x95, 0x01, 0x75, 0x03, 0x81, 0x01,
        0x05, 0x01, 0x09, 0x30, 0x09, 0x31, 0x09, 0x38, 0x15, 0x81, 0x25, 0x7f, 0x75, 0x08, 0x95, 0x03, 0x81, 0x06,
        0x05, 0x0c, 0x0a, 0x38, 0x02, 0x15, 0x81, 0x25, 0x7f, 0x75, 0x08, 0x95, 0x01, 0x81, 0x06,
        0xc0, 0xc0);

    private Reports() { }

    public static byte[] keyboard(int modifiers, int usage) {
        byte[] report = new byte[KEYBOARD_SIZE];
        report[0] = (byte) modifiers;
        report[2] = (byte) usage;
        return report;
    }

    public static byte[] mouse(int buttons, int dx, int dy, int wheel, int pan) {
        return new byte[] {(byte) buttons, clamp(dx), clamp(dy), clamp(wheel), clamp(pan)};
    }

    /** How many reports a relative motion needs to fit the signed 8-bit fields. */
    public static int stepCount(int... totals) {
        int count = 1;
        for (int total : totals) count = Math.max(count, (Math.abs(total) + 126) / 127);
        return count;
    }

    /** Splits a relative motion evenly across {@code count} reports. */
    public static int[] spread(int total, int count) {
        int[] result = new int[count];
        int remaining = total;
        for (int i = 0; i < count; i++) {
            int step = remaining / (count - i);
            result[i] = step;
            remaining -= step;
        }
        return result;
    }

    /** Wheel and pan as single-notch steps, both axes advancing together. */
    public static int[][] notches(int wheel, int pan) {
        int count = Math.max(Math.abs(wheel), Math.abs(pan));
        int[][] result = new int[count][2];
        for (int i = 0; i < count; i++) {
            result[i][0] = i < Math.abs(wheel) ? Integer.signum(wheel) : 0;
            result[i][1] = i < Math.abs(pan) ? Integer.signum(pan) : 0;
        }
        return result;
    }

    private static byte clamp(int value) {
        return (byte) Math.max(-127, Math.min(127, value));
    }

    private static byte[] bytes(int... values) {
        byte[] result = new byte[values.length];
        for (int i = 0; i < values.length; i++) result[i] = (byte) values[i];
        return result;
    }
}
