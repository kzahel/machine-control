package dev.machinecontrol.android.spike;

import android.app.Activity;
import android.content.Intent;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.provider.DocumentsContract;
import android.provider.MediaStore;
import android.view.WindowInsets;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.TextView;

/** Operator-only selection/arming surface. No accessibility enablement needed. */
public final class DataActivity extends Activity {
    private TextView status;
    @Override public void onCreate(Bundle state) {
        super.onCreate(state);
        LinearLayout layout = new LinearLayout(this);
        layout.setOrientation(LinearLayout.VERTICAL);
        layout.setOnApplyWindowInsetsListener((view, insets) -> {
            android.graphics.Insets bars = insets.getInsets(WindowInsets.Type.systemBars());
            view.setPadding(24 + bars.left, 24 + bars.top, 24 + bars.right, 24 + bars.bottom);
            return insets;
        });
        status = new TextView(this); layout.addView(status);
        button(layout, R.string.pick_photo, () -> {
            Intent pick = Build.VERSION.SDK_INT >= 33 ? new Intent(MediaStore.ACTION_PICK_IMAGES) :
                new Intent(Intent.ACTION_OPEN_DOCUMENT).addCategory(Intent.CATEGORY_OPENABLE);
            pick.setType("image/*");
            pick.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION | Intent.FLAG_GRANT_PERSISTABLE_URI_PERMISSION);
            startActivityForResult(pick, 101);
        });
        button(layout, R.string.pick_tree, () -> {
            Intent pick = new Intent(Intent.ACTION_OPEN_DOCUMENT_TREE)
                .addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION | Intent.FLAG_GRANT_PERSISTABLE_URI_PERMISSION);
            // A debug caller may suggest the owned test folder; the system
            // picker still owns selection and consent, never this extra.
            String hint = getIntent().getStringExtra("initialTree");
            if (BuildConfig.DEBUG && hint != null) pick.putExtra(DocumentsContract.EXTRA_INITIAL_URI, Uri.parse(hint));
            startActivityForResult(pick, 102);
        });
        button(layout, R.string.arm_data, () -> startForegroundService(new Intent(this, DataService.class)));
        button(layout, R.string.stop_data, () -> stopService(new Intent(this, DataService.class)));
        button(layout, R.string.revoke_photo, () -> { DataSelections.revoke(this, "photo"); refresh(); });
        button(layout, R.string.revoke_tree, () -> { DataSelections.revoke(this, "tree"); refresh(); });
        button(layout, R.string.forget_data, () -> { DataSelections.forget(this); refresh(); });
        setContentView(layout);
    }
    @Override protected void onResume() { super.onResume(); refresh(); }
    private void refresh() {
        status.setText(getString(R.string.data_status,
            DataSelections.available(this, DataSelections.selected(this, "photo")),
            DataSelections.available(this, DataSelections.selected(this, "tree"))));
    }
    private void button(LinearLayout layout, int label, Runnable action) {
        Button button = new Button(this); button.setText(label);
        button.setOnClickListener(view -> action.run()); layout.addView(button);
    }
    @Override protected void onActivityResult(int request, int result, Intent data) {
        super.onActivityResult(request, result, data);
        if (result != RESULT_OK || data == null || data.getData() == null) return;
        try {
            Uri uri = data.getData();
            if (request == 102 && !DocumentsContract.isTreeUri(uri)) throw new IllegalArgumentException("Tree required");
            if (request == 101 && !String.valueOf(getContentResolver().getType(uri)).startsWith("image/"))
                throw new IllegalArgumentException("Image required");
            if (request != 101 && request != 102) return;
            DataSelections.select(this, request == 101 ? "photo" : "tree", uri);
            refresh();
        } catch (Exception error) { status.setText(R.string.selection_failed); }
    }
}
