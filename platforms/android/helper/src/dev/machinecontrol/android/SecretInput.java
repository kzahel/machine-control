package dev.machinecontrol.android;

import android.app.Instrumentation;
import android.view.KeyEvent;
import java.io.IOException;
import java.util.Arrays;

/** One-shot shell-UID PIN key injection. Emits no credential or diagnostic output. */
public final class SecretInput {
    private static final int MIN_PIN_BYTES = 4;
    private static final int MAX_PIN_BYTES = 16;

    private SecretInput() {}

    public static void main(String[] arguments) {
        byte[] pin = null;
        try {
            pin = readPin();
            Instrumentation instrumentation = new Instrumentation();
            for (byte value : pin) {
                instrumentation.sendKeyDownUpSync(
                    KeyEvent.KEYCODE_0 + (value - (byte) '0')
                );
            }
            instrumentation.sendKeyDownUpSync(KeyEvent.KEYCODE_ENTER);
        } catch (Exception error) {
            System.exit(2);
        } finally {
            if (pin != null) {
                Arrays.fill(pin, (byte) 0);
            }
        }
    }

    private static byte[] readPin() throws IOException {
        byte[] raw = new byte[MAX_PIN_BYTES + 2];
        int length = 0;
        while (length < raw.length) {
            int value = System.in.read();
            if (value < 0 || value == '\n') {
                break;
            }
            if (value != '\r') {
                raw[length++] = (byte) value;
            }
        }
        if (length < MIN_PIN_BYTES || length > MAX_PIN_BYTES) {
            Arrays.fill(raw, (byte) 0);
            throw new IOException("invalid PIN length");
        }
        for (int index = 0; index < length; index++) {
            byte value = raw[index];
            if (value < (byte) '0' || value > (byte) '9') {
                Arrays.fill(raw, (byte) 0);
                throw new IOException("PIN must contain digits only");
            }
        }
        byte[] pin = Arrays.copyOf(raw, length);
        Arrays.fill(raw, (byte) 0);
        return pin;
    }
}
