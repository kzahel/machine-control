package dev.machinecontrol.android.spike;

import android.app.Activity;
import android.content.Intent;
import android.os.Bundle;
import android.provider.Settings;
import android.view.View;
import android.view.WindowInsets;
import android.widget.Button;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.TextView;
import java.io.File;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;

/** Owned native fixture; its private result file is an independent action oracle. */
public final class FixtureActivity extends Activity {
    private LinearLayout layout;
    private EditText input;
    private TextView result;

    @Override public void onCreate(Bundle state) {
        super.onCreate(state);
        layout = new LinearLayout(this);
        layout.setOrientation(LinearLayout.VERTICAL);
        layout.setPadding(24, 24, 24, 24);
        layout.setOnApplyWindowInsetsListener((v, insets) -> {
            android.graphics.Insets bars = insets.getInsets(WindowInsets.Type.systemBars());
            v.setPadding(24 + bars.left, 24 + bars.top, 24 + bars.right, 24 + bars.bottom);
            return insets;
        });
        TextView title = new TextView(this);
        title.setText(R.string.title);
        layout.addView(title);
        addInput(1);
        button(R.string.apply, v -> {
            String value = input.getText().toString();
            try {
                Files.write(new File(getFilesDir(), "fixture-result.txt").toPath(), value.getBytes(StandardCharsets.UTF_8));
                result.setText(getString(R.string.result, value));
            } catch (java.io.IOException error) { result.setText(R.string.write_failed); }
        }).setId(R.id.fixture_apply);
        button(R.string.replace, v -> {
            layout.removeView(input);
            addInput(1);
            result.setText(R.string.input_replaced);
        }).setId(R.id.fixture_replace);
        result = new TextView(this);
        result.setText(R.string.pending);
        layout.addView(result);
        button(R.string.enable, v -> startActivity(new Intent(Settings.ACTION_ACCESSIBILITY_SETTINGS)));
        button(R.string.arm, v -> {
            ResidentService service = ResidentService.current;
            if (service == null) result.setText(R.string.enable_first);
            else {
                try { service.arm(); result.setText(R.string.armed); }
                catch (Exception error) { result.setText(R.string.arm_failed); }
            }
        });
        button(R.string.stop, v -> {
            if (ResidentService.current != null) ResidentService.current.revoke();
            result.setText(R.string.stopped);
        });
        setContentView(layout);
    }

    private void addInput(int index) {
        input = new EditText(this);
        input.setId(R.id.fixture_input);
        input.setSingleLine(true);
        input.setHint(R.string.input_hint);
        input.setContentDescription(getString(R.string.input_hint));
        input.setImportantForAutofill(View.IMPORTANT_FOR_AUTOFILL_NO);
        layout.addView(input, index);
    }

    private Button button(int label, View.OnClickListener listener) {
        Button button = new Button(this);
        button.setText(label);
        button.setOnClickListener(listener);
        layout.addView(button);
        return button;
    }
}
