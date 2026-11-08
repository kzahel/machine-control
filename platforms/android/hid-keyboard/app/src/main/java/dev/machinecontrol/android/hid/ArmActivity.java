package dev.machinecontrol.android.hid;

import android.Manifest;
import android.app.Activity;
import android.bluetooth.BluetoothAdapter;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.os.Bundle;

/**
 * Invisible trampoline for agents. The manifest requires
 * {@code android.permission.DUMP} to start it, which the ADB shell holds and
 * ordinary apps cannot, so other apps cannot rotate the grant or raise
 * discoverability prompts. Being a visible activity for a moment also lets it
 * start the foreground service under Android 12+ background-start rules.
 */
public final class ArmActivity extends Activity {
    static final String ACTION_ARM = "dev.machinecontrol.android.hid.ARM";
    static final String ACTION_DISCOVERABLE = "dev.machinecontrol.android.hid.DISCOVERABLE";

    @Override public void onCreate(Bundle state) {
        super.onCreate(state);
        Intent intent = getIntent();
        String action = intent == null ? null : intent.getAction();
        boolean stoppedByOperator = getSharedPreferences("hid", MODE_PRIVATE)
            .getBoolean(HidService.PREF_OPERATOR_STOPPED, false);
        if (stoppedByOperator && (intent == null || !intent.getBooleanExtra("override", false))) {
            // The operator pressed Stop; only a person relaunching the app, or an
            // explicit override, may arm again. The CLI reports stopped_by_operator.
            finish();
            return;
        }
        if (checkSelfPermission(Manifest.permission.BLUETOOTH_CONNECT) != PackageManager.PERMISSION_GRANTED) {
            finish();
            return;
        }
        getSharedPreferences("hid", MODE_PRIVATE).edit()
            .putBoolean(HidService.PREF_OPERATOR_STOPPED, false).apply();
        if (HidService.current == null || ACTION_ARM.equals(action)) {
            try {
                startForegroundService(new Intent(this, HidService.class).setAction(HidService.ACTION_START));
            } catch (IllegalStateException | SecurityException refused) {
                // For example behind a locked keyguard: no grant is published and the
                // CLI reports arm_failed instead of the app crashing.
                finish();
                return;
            }
        }
        if (ACTION_DISCOVERABLE.equals(action)) {
            int seconds = Math.max(1, Math.min(intent.getIntExtra("seconds", 120), 3600));
            startActivity(new Intent(BluetoothAdapter.ACTION_REQUEST_DISCOVERABLE)
                .putExtra(BluetoothAdapter.EXTRA_DISCOVERABLE_DURATION, seconds));
        }
        finish();
    }
}
