package dev.machinecontrol.android.hid;

import android.Manifest;
import android.annotation.SuppressLint;
import android.app.Activity;
import android.bluetooth.BluetoothAdapter;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.graphics.Color;
import android.os.Build;
import android.os.Bundle;
import android.view.MotionEvent;
import android.view.WindowInsets;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.TextView;

/**
 * Status plus an in-a-pinch touchpad. Agents normally use the control socket;
 * ADB arms the service through {@link ArmActivity}. Launching this activity
 * starts the service unless a person pressed Stop; then only an on-screen
 * Start tap resumes it, because any app can send this exported launcher intent.
 * There is deliberately no text field, so no IME or suggestion strip appears.
 */
public final class MainActivity extends Activity {
    private static final String[] PERMISSIONS = {
        Manifest.permission.BLUETOOTH_CONNECT, Manifest.permission.BLUETOOTH_ADVERTISE,
        Manifest.permission.BLUETOOTH_SCAN};
    private TextView status;
    private boolean offeredDiscoverable;

    @Override public void onCreate(Bundle state) {
        super.onCreate(state);
        LinearLayout layout = new LinearLayout(this);
        layout.setOrientation(LinearLayout.VERTICAL);
        layout.setBackgroundColor(Color.rgb(18, 20, 24));
        layout.setOnApplyWindowInsetsListener((v, insets) -> {
            android.graphics.Insets bars = insets.getInsets(WindowInsets.Type.systemBars());
            v.setPadding(16 + bars.left, 16 + bars.top, 16 + bars.right, 16 + bars.bottom);
            return insets;
        });
        status = new TextView(this);
        status.setTextColor(Color.WHITE);
        status.setTextSize(18);
        status.setPadding(8, 8, 8, 16);
        layout.addView(status);

        LinearLayout top = row();
        top.addView(button(R.string.discoverable, () -> requestDiscoverable(120)), weight());
        top.addView(button(R.string.start, () -> {
            getSharedPreferences("hid", MODE_PRIVATE).edit()
                .putBoolean(HidService.PREF_OPERATOR_STOPPED, false).apply();
            handle(getIntent());
        }), weight());
        top.addView(button(R.string.stop, () -> {
            startService(new Intent(this, HidService.class).setAction(HidService.ACTION_STOP));
            refresh();
        }), weight());
        layout.addView(top);

        layout.addView(new TouchpadView(this), new LinearLayout.LayoutParams(
            LinearLayout.LayoutParams.MATCH_PARENT, 0, 1));

        LinearLayout bottom = row();
        bottom.addView(holdButton(R.string.left, Reports.BUTTON_LEFT), weight());
        bottom.addView(holdButton(R.string.right, Reports.BUTTON_RIGHT), weight());
        layout.addView(bottom);
        setContentView(layout);
        handle(getIntent());
    }

    @Override protected void onNewIntent(Intent intent) {
        super.onNewIntent(intent);
        setIntent(intent);
        handle(intent);
    }

    // Listen while visible, not only while resumed: the system discoverability
    // dialog pauses this activity while the service is starting.
    @Override protected void onStart() {
        super.onStart();
        HidService.listener = this::refresh;
        refresh();
    }

    @Override protected void onStop() {
        HidService.listener = null;
        super.onStop();
    }

    private boolean permitted() {
        for (String permission : PERMISSIONS)
            if (checkSelfPermission(permission) != PackageManager.PERMISSION_GRANTED) return false;
        return true;
    }

    private void handle(Intent intent) {
        if (!permitted()) {
            // The notification permission is optional; the service runs without it.
            if (Build.VERSION.SDK_INT >= 33)
                requestPermissions(new String[] {PERMISSIONS[0], PERMISSIONS[1], PERMISSIONS[2],
                    Manifest.permission.POST_NOTIFICATIONS}, 1);
            else requestPermissions(PERMISSIONS, 1);
            return;
        }
        if (HidService.current == null) {
            if (getSharedPreferences("hid", MODE_PRIVATE).getBoolean(HidService.PREF_OPERATOR_STOPPED, false)) {
                status.setText(R.string.operator_stopped);
                return;
            }
            try {
                startForegroundService(new Intent(this, HidService.class).setAction(HidService.ACTION_START));
            } catch (IllegalStateException | SecurityException refused) {
                status.setText(R.string.start_refused);
                return;
            }
        }
        if (!offeredDiscoverable && !hasSavedHost()) {
            // Default to waiting discoverably: ChromeOS-like hosts start pairing themselves.
            requestDiscoverable(120);
        }
    }

    private boolean hasSavedHost() {
        // Either transport's host counts: LE pairing windows open whenever the
        // handheld is discoverable, so do not offer one needlessly.
        android.content.SharedPreferences prefs = getSharedPreferences("hid", MODE_PRIVATE);
        return prefs.getString("host", null) != null || prefs.getString("bleHost", null) != null;
    }

    @Override public void onRequestPermissionsResult(int code, String[] permissions, int[] results) {
        if (permitted()) handle(getIntent());
        else status.setText(R.string.permissions_required);
    }

    private void requestDiscoverable(int seconds) {
        offeredDiscoverable = true;
        startActivity(new Intent(BluetoothAdapter.ACTION_REQUEST_DISCOVERABLE)
            .putExtra(BluetoothAdapter.EXTRA_DISCOVERABLE_DURATION, Math.max(1, Math.min(seconds, 3600))));
    }

    private void refresh() {
        HidService service = HidService.current;
        boolean operatorStopped = getSharedPreferences("hid", MODE_PRIVATE)
            .getBoolean(HidService.PREF_OPERATOR_STOPPED, false);
        if (service == null) status.setText(operatorStopped ? R.string.operator_stopped : R.string.stopped);
        else status.setText(service.summary());
    }

    private LinearLayout row() {
        LinearLayout row = new LinearLayout(this);
        row.setOrientation(LinearLayout.HORIZONTAL);
        return row;
    }

    private static LinearLayout.LayoutParams weight() {
        LinearLayout.LayoutParams params = new LinearLayout.LayoutParams(0,
            LinearLayout.LayoutParams.WRAP_CONTENT, 1);
        params.setMargins(6, 6, 6, 6);
        return params;
    }

    private Button button(int label, Runnable action) {
        Button button = new Button(this);
        button.setText(label);
        button.setOnClickListener(v -> action.run());
        return button;
    }

    /** Press-and-hold mouse buttons, so a drag can use the touchpad with another finger. */
    @SuppressLint("ClickableViewAccessibility")
    private Button holdButton(int label, int mask) {
        Button button = new Button(this);
        button.setText(label);
        button.setMinHeight(180);
        button.setOnTouchListener((v, event) -> {
            HidService service = HidService.current;
            int action = event.getActionMasked();
            if (service != null && action == MotionEvent.ACTION_DOWN) {
                service.pointerAsync(() -> service.button(mask, true));
                v.setPressed(true);
            } else if (service != null && (action == MotionEvent.ACTION_UP || action == MotionEvent.ACTION_CANCEL)) {
                service.pointerAsync(() -> service.button(mask, false));
                v.setPressed(false);
                if (action == MotionEvent.ACTION_UP) v.performClick();
            }
            return true;
        });
        return button;
    }
}
