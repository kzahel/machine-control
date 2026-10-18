package dev.machinecontrol.android.spike;

import android.content.Context;
import android.content.Intent;
import android.content.SharedPreferences;
import android.net.Uri;
import java.util.UUID;

/** Durable selection identity is separate from Android's current URI grant. */
final class DataSelections {
    private DataSelections() { }
    static SharedPreferences store(Context context) {
        return context.getSharedPreferences("data-selections-v1", Context.MODE_PRIVATE);
    }
    static Uri selected(Context context, String kind) {
        String value = store(context).getString(kind, null);
        return value == null ? null : Uri.parse(value);
    }
    static boolean available(Context context, Uri uri) {
        return uri != null && context.getContentResolver().getPersistedUriPermissions().stream()
            .anyMatch(grant -> grant.getUri().equals(uri) && grant.isReadPermission());
    }
    static void select(Context context, String kind, Uri uri) {
        if (!"content".equals(uri.getScheme())) throw new IllegalArgumentException("Content URI required");
        context.getContentResolver().takePersistableUriPermission(uri, Intent.FLAG_GRANT_READ_URI_PERMISSION);
        Uri old = selected(context, kind);
        if (!store(context).edit().putString(kind, uri.toString())
            .putString("epoch", UUID.randomUUID().toString()).commit()) throw new IllegalStateException("Selection not saved");
        if (old != null && !old.equals(uri)) release(context, old);
    }
    static void revoke(Context context, String kind) {
        Uri uri = selected(context, kind);
        if (uri != null) release(context, uri);
        // Keep selection identity so revocation is visible rather than silently empty.
    }
    private static void release(Context context, Uri uri) {
        if (available(context, uri)) context.getContentResolver()
            .releasePersistableUriPermission(uri, Intent.FLAG_GRANT_READ_URI_PERMISSION);
    }
    static void forget(Context context) {
        revoke(context, "photo"); revoke(context, "tree");
        if (!store(context).edit().clear().commit()) throw new IllegalStateException("Selection cleanup failed");
    }
}
